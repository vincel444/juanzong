"""三档自适应路由 + 端到端问答。

档位策略（全部由官方 chat template 的 enable_thinking 开关驱动，无额外魔改）：
    LOW    1.7B 关思考  简明事实型问题（目标 <1s）
    MEDIUM 1.7B 开思考  需要推理但资料范围小（数秒）
    HIGH   4B  开思考   跨文档审阅 / 长文分析 / 多条款对比（数十秒）
"""
from __future__ import annotations

from config import DEEP_KEYWORDS, DEEP_MIN_CHARS
from inference import GenResult, Tier, ask_large, ask_medium, ask_small, chat_stream, model_for

SYSTEM_PROMPT = (
    "你是完全在本地设备上运行的文档助手「卷宗」。"
    "仅依据用户提供的资料回答问题；引用资料时标注 [资料名 第N页]；"
    "资料不足以回答时明确说明，不要编造。"
)

# 需要推理、但不必动用 4B 的信号词
REASON_KEYWORDS = ["为什么", "分析", "计算", "推断", "判断", "解释", "原因", "如何理解"]
REASON_MIN_CHARS = 25

# 与 ask_small / ask_medium / ask_large 的默认输出上限保持一致
TIER_MAX_TOKENS = {Tier.LOW: 1024, Tier.MEDIUM: 3072, Tier.HIGH: 4096}


def route(question: str) -> Tier:
    """规则版三档路由（TODO(B-3): 升级为由 1.7B 输出档位标签后动态路由）。"""
    if len(question) >= DEEP_MIN_CHARS or any(k in question for k in DEEP_KEYWORDS):
        return Tier.HIGH
    if len(question) >= REASON_MIN_CHARS or any(k in question for k in REASON_KEYWORDS):
        return Tier.MEDIUM
    return Tier.LOW


def _prepare(question: str) -> tuple[str, list]:
    """解析资料 -> 优先整卷装载，超限退回检索兜底。返回 (user_content, refs)。"""
    from retrieval import full_context, load_documents, retrieve

    chunks = load_documents()
    context = full_context(chunks)
    refs = chunks
    mode = "全卷装载"
    if not context:
        refs = retrieve(question)
        context = "\n\n".join(f"[{r.doc_name} 第{r.page}页] {r.text}" for r in refs)
        mode = "检索召回"
    user_content = f"资料（{mode}）：\n{context}\n\n问题：{question}" if context else question
    return user_content, refs


def answer(question: str) -> tuple[GenResult, list]:
    """端到端问答（非流式，供基准脚本/测试调用）。"""
    user_content, refs = _prepare(question)
    tier = route(question)
    if tier == Tier.HIGH:
        result = ask_large(user_content, system=SYSTEM_PROMPT)
    elif tier == Tier.MEDIUM:
        result = ask_medium(user_content, system=SYSTEM_PROMPT)
    else:
        result = ask_small(user_content, system=SYSTEM_PROMPT)

    # 智能降级：思考过程吃满输出上限仍未给出正式回答时（1.7B 思考档易发生），
    # 自动用同模型关闭思考重试一次，保证用户始终拿到答案。
    if not result.text and result.thinking:
        fallback = ask_small(user_content, system=SYSTEM_PROMPT)
        fallback.thinking = result.thinking  # 保留原思考内容，界面仍可展示
        result = fallback
    return result, refs


def answer_stream(question: str):
    """answer() 的流式版本（P0-#1）。

    依次产出：
        ("notice", 提示文本)   —— 降级等过程提示
        ("thinking", 思考增量) / ("content", 回答增量)
        ("done", (GenResult, refs, citation_index)) —— 引用索引供溯源校验
    """
    user_content, refs = _prepare(question)
    tier = route(question)
    model, base_url = model_for(tier)
    messages = ([{"role": "system", "content": SYSTEM_PROMPT}] if SYSTEM_PROMPT else []) + [
        {"role": "user", "content": user_content}
    ]

    result = None
    for kind, payload in chat_stream(model, base_url, messages, tier,
                                     max_tokens=TIER_MAX_TOKENS[tier]):
        if kind == "done":
            result = payload
        else:
            yield kind, payload

    # 智能降级（流式版）：思考吃满上限、正文为空时，关思考重试并一次性补发。
    if result is not None and not result.text and result.thinking:
        yield "notice", "思考超限未产出正式回答，已自动降级重试（关闭思考）"
        fallback = ask_small(user_content, system=SYSTEM_PROMPT)
        fallback.thinking = result.thinking
        if fallback.text:
            yield "content", fallback.text
        result = fallback

    from citation import build_citation_index

    yield "done", (result, refs, build_citation_index(refs))
