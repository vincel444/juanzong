"""引用防幻觉校验（P0-#3）：对模型回答逐句回查资料原文。

原理：中文字符级 8-gram 滑窗命中检测。回答的每个句子按 8 字滑窗切成
片段，逐个在资料原文的 8-gram 索引中查找；命中率低于阈值的句子视为
「未溯源」，提示用户人工复核。

特点：
- 字面回查而非语义判断 —— 毫秒级、可解释、零额外推理开销；
- 直接复用「整卷装载」已进内存的原文，不增加内存压力；
- 顺带定位每个命中片段的来源（文档名 + 页码），比"把全卷页码
  都列成出处"更诚实：出处列表 = 回答实际踩中的原文位置。

局限（如实说明）：改写复述（同义换词）会漏检、碰巧命中的常见短语
会误检。因此定位为"防幻觉底线"：全部句子均可溯源 → 高置信；
存在未溯源句 → 标黄提示人工复核，而不是直接判错。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

NGRAM = 8          # 中文字符滑窗长度
GRAM_STEP = 4      # 滑窗步进（重叠 4 字，保证连续改写片段仍会被覆盖）
MIN_SENT_CHARS = 6  # 规范化后不足 6 字的短句不参与校验（"可以。"之类）
HIT_THRESHOLD = 0.5  # 命中比例低于该值的句子标记为未溯源

# 去空白与标点：标点会因模型排版差异造成错位，匹配只在"实质字符"上进行
_STRIP_RE = re.compile(
    r"[\s，。！？；：、·…—–\-.,!?;:\"'“”‘’（）()【】\[\]《》<>{}]+"
)


def _normalize(text: str) -> str:
    return _STRIP_RE.sub("", text)


def split_sentences(text: str) -> list[str]:
    """按中英文句末标点/换行分句。"""
    parts = re.split(r"(?<=[。！？!?；;\n])", text)
    return [p.strip() for p in parts if p and p.strip()]


@dataclass
class CheckItem:
    """单个句子的校验结果。"""

    sentence: str
    ratio: float                       # 8-gram 命中比例 0~1
    verified: bool                     # ratio >= HIT_THRESHOLD
    sources: set[tuple[str, int]] = field(default_factory=set)  # (文档名, 页码)


@dataclass
class CitationIndex:
    """8-gram 主索引 + 规范化原文列表（短句子串兜底用）。"""

    grams: dict[str, set[tuple[str, int]]]
    texts: list[tuple[str, int, str]]  # (文档名, 页码, 规范化后原文)


def build_citation_index(chunks) -> CitationIndex:
    """构建 8-gram -> {(文档名, 页码)} 索引与原文列表。

    chunks 为 retrieval.Chunk 列表（整卷装载时的全部块，或检索兜底时的
    召回块）。约 40 万字资料约产生 40 万索引条目，构建耗时 ~0.5s，
    内存 ~50MB，对话开始时构建一次即可。
    """
    grams: dict[str, set[tuple[str, int]]] = {}
    texts: list[tuple[str, int, str]] = []
    for c in chunks:
        norm = _normalize(c.text)
        key = (c.doc_name, c.page)
        texts.append((c.doc_name, c.page, norm))
        for i in range(len(norm) - NGRAM + 1):
            grams.setdefault(norm[i : i + NGRAM], set()).add(key)
    return CitationIndex(grams=grams, texts=texts)


def _grams(sentence_norm: str) -> list[str]:
    """滑窗 8-gram（含末尾窗口，保证句尾也被覆盖）。"""
    n = NGRAM
    if len(sentence_norm) <= n:
        return [sentence_norm] if sentence_norm else []
    gs = [sentence_norm[i : i + n] for i in range(0, len(sentence_norm) - n + 1, GRAM_STEP)]
    tail = sentence_norm[-n:]
    if gs and gs[-1] != tail:
        gs.append(tail)
    return gs


def verify_answer(answer_text: str, index: CitationIndex,
                  max_sources: int = 6) -> list[CheckItem]:
    """逐句校验回答，返回句子级结果列表（仅实质性句子）。

    >= 8 字句子走 8-gram 滑窗；< 8 字短句在原文规范化文本上做直接子串
    搜索兜底。注意：概括性改写（跳过修饰词）会漏检而标为未溯源，
    属设计取向 —— 宁可误标请人工复核，不可漏掉幻觉。
    """
    items: list[CheckItem] = []
    for sent in split_sentences(answer_text):
        norm = _normalize(sent)
        if len(norm) < MIN_SENT_CHARS:
            continue
        if len(norm) < NGRAM:
            hits = {(doc, page) for (doc, page, t) in index.texts if norm and norm in t}
            items.append(CheckItem(sentence=sent, ratio=1.0 if hits else 0.0,
                                   verified=bool(hits), sources=set(sorted(hits)[:max_sources])))
            continue
        gs = _grams(norm)
        if not gs:
            continue
        hits = [g for g in gs if g in index.grams]
        ratio = len(hits) / len(gs)
        sources: set[tuple[str, int]] = set()
        for g in hits:
            sources.update(index.grams[g])
        items.append(CheckItem(sentence=sent, ratio=round(ratio, 2),
                               verified=ratio >= HIT_THRESHOLD,
                               sources=set(sorted(sources)[:max_sources])))
    return items


def summarize(items: list[CheckItem]) -> tuple[int, int, list[CheckItem]]:
    """返回 (总句数, 命中句数, 未溯源句列表)。"""
    total = len(items)
    ok = sum(1 for i in items if i.verified)
    missed = [i for i in items if not i.verified]
    return total, ok, missed


def collect_sources(items: list[CheckItem]) -> list[str]:
    """汇总全部命中句的来源页，渲染为 '文档名 p页码' 去重排序列表。"""
    merged: set[tuple[str, int]] = set()
    for i in items:
        merged.update(i.sources)
    return [f"{doc} p{page}" for doc, page in sorted(merged)]
