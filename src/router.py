"""双模型路由 + 端到端问答。"""
from __future__ import annotations

from config import DEEP_KEYWORDS, DEEP_MIN_CHARS
from inference import GenResult, Tier, ask_large, ask_small

SYSTEM_PROMPT = (
    "你是完全在本地设备上运行的文档助手「卷宗」。"
    "仅依据用户提供的资料回答问题；引用资料时标注 [资料名 第N页]；"
    "资料不足以回答时明确说明，不要编造。"
)


def route(question: str, has_context: bool = False) -> Tier:
    """规则版路由（TODO(B-3): 升级为由 1.7B 判断意图后动态路由）。"""
    if len(question) >= DEEP_MIN_CHARS:
        return Tier.HIGH
    if any(kw in question for kw in DEEP_KEYWORDS):
        return Tier.HIGH
    return Tier.LOW


def answer(question: str) -> tuple[GenResult, list]:
    """端到端问答：解析资料 -> 优先整卷装载，超限退回检索兜底 -> 路由生成。"""
    from retrieval import full_context, load_documents, retrieve

    chunks = load_documents()
    context = full_context(chunks)
    mode = "全卷装载"
    refs = chunks
    if not context:
        refs = retrieve(question)
        context = "\n\n".join(f"[{r.doc_name} 第{r.page}页] {r.text}" for r in refs)
        mode = "检索召回"

    user_content = f"资料（{mode}）：\n{context}\n\n问题：{question}" if context else question
    if route(question) == Tier.HIGH:
        result = ask_large(user_content, system=SYSTEM_PROMPT)
    else:
        result = ask_small(user_content, system=SYSTEM_PROMPT)
    return result, refs
