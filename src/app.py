"""「卷宗」端侧主入口：Gradio 离线界面（流式版）。

启动前：
1. 启动推理后端：python scripts/start_llama_servers.py
   （或 Ollama 路线：ollama serve + ollama pull 两个模型）
2. .venv 激活后运行：python src/app.py

演示要点：
- 流式输出：思考过程与回答逐字上屏，深档 40s 不再是黑屏等待（P0-#1）
- 溯源校验：回答逐句回查原文，未溯源句标出，提示人工复核（P0-#3）
- 每轮回答显示档位、首字时延、总时延与 token 数
"""
from __future__ import annotations

import gradio as gr

from config import DATA_DIR, LARGE_BASE_URL, LARGE_MODEL, SMALL_BASE_URL, SMALL_MODEL
from inference import chat, Tier


def refresh_docs():
    from retrieval import scan_documents

    files = scan_documents()
    if not files:
        return f"资料库为空，请把文档放入：{DATA_DIR}"
    return "\n".join(f"- {p.name}" for p in files)


def check_backend():
    ok_small = _ping(SMALL_MODEL, SMALL_BASE_URL)
    ok_large = _ping(LARGE_MODEL, LARGE_BASE_URL)
    return (f"1.7B({SMALL_BASE_URL}): {'✓ 可用' if ok_small else '✗ 未启动'}    "
            f"4B({LARGE_BASE_URL}): {'✓ 可用' if ok_large else '✗ 未启动'}")


def _ping(model: str, base_url: str) -> bool:
    try:
        chat(model, base_url, [{"role": "user", "content": "ping"}], Tier.LOW, max_tokens=8)
        return True
    except Exception:
        return False


TIER_LABEL = {Tier.LOW: "轻档·1.7B快答", Tier.MEDIUM: "中档·1.7B推理", Tier.HIGH: "深档·4B审阅"}


def _render(thinking: list[str], content: list[str], notices: list[str]) -> str:
    """把流式累积内容渲染成单条 assistant 消息。"""
    prefix = "".join(f"> ℹ️ {n}\n\n" for n in notices)
    thinking_acc, content_acc = "".join(thinking), "".join(content)
    note = ""
    if thinking_acc:
        label = "思考中…" if not content_acc else f"思考过程（{len(thinking_acc)} 字）"
        note = (f"<details open><summary>{label}</summary>\n\n"
                f"{thinking_acc}\n\n</details>")
    body = content_acc or ("思考中…" if thinking_acc else "…")
    sep = "\n\n" if note and content_acc else ""
    return prefix + note + sep + body


def chat_turn_stream(question: str, history: list):
    """流式对话轮（生成器：每收到增量就 yield 一次界面更新）。"""
    from citation import collect_sources, summarize, verify_answer
    from router import answer_stream

    if not question.strip():
        yield history, ""
        return

    history = history + [{"role": "user", "content": question}]
    reply_idx = len(history)
    history = history + [{"role": "assistant", "content": "…"}]
    yield history, ""

    thinking: list[str] = []
    content: list[str] = []
    notices: list[str] = []
    outcome = None
    try:
        for kind, payload in answer_stream(question):
            if kind == "thinking":
                thinking.append(payload)
            elif kind == "content":
                content.append(payload)
            elif kind == "notice":
                notices.append(payload)
            elif kind == "done":
                outcome = payload
            history[reply_idx] = {"role": "assistant",
                                  "content": _render(thinking, content, notices)}
            yield history, ""

        result, refs, citation_index = outcome
        items = verify_answer(result.text, citation_index) if result.text else []
        total, ok, missed = summarize(items)
        cites = "、".join(collect_sources(items)) or "无"

        footer = (
            f"\n\n---\n档位：{TIER_LABEL.get(result.tier, result.tier.value)}"
            f"（{result.model}）｜首字 {result.first_token_ms/1000:.2f} s｜"
            f"总时延 {result.latency_ms/1000:.1f} s｜输出 {result.eval_tokens} tok\n"
            f"出处：{cites}｜溯源校验：{ok}/{total} 句命中原文"
        )
        if missed:
            pure = [m for m in missed if m.ratio < 0.01]      # 与原文完全对不上
            partial = [m for m in missed if m.ratio >= 0.01]  # 模型综合/改写，部分命中
            warn = []
            if pure:
                warn.append("未溯源: " + "；".join(m.sentence[:32] for m in pure[:3]))
            if partial:
                warn.append("部分溯源: " + "；".join(m.sentence[:32] for m in partial[:3]))
            footer += "\n⚠️ 建议人工复核 —— " + " ｜ ".join(warn) + ("…" if len(missed) > 3 else "")
        else:
            footer += " ✅"

        history[reply_idx] = {"role": "assistant",
                              "content": _render(thinking, content, notices) + footer}
        yield history, ""
    except Exception as e:  # 后端未启动 / 网络异常等
        history[reply_idx] = {"role": "assistant",
                              "content": f"调用失败：{e}\n请确认推理服务已启动。"}
        yield history, ""


with gr.Blocks(title="卷宗 · 本地长文档工作台") as demo:
    gr.Markdown(
        "## 卷宗 — 隐私优先的本地长文档智能工作台\n"
        "Spark-X2.5 端侧三档自适应：轻档 1.7B 快答（<1s）→ 中档 1.7B 推理 → 深档 4B 跨文档审阅。"
        "全程离线，数据不出设备。回答逐句回查原文，未溯源句自动标出。"
    )
    status = gr.Textbox(label="后端状态", value="点击检测", interactive=False)
    check_btn = gr.Button("检测模型服务")
    check_btn.click(check_backend, outputs=status)

    with gr.Row():
        docs = gr.Textbox(label="资料库文件", lines=6, interactive=False)
        refresh_btn = gr.Button("刷新资料库")
    refresh_btn.click(refresh_docs, outputs=docs)

    chatbot = gr.Chatbot(label="问答（流式 + 溯源校验）", height=460)
    msg = gr.Textbox(label="你的问题（问句越长/越复杂，会自动路由到 4B 深度档）")
    clear = gr.Button("清空对话")

    msg.submit(chat_turn_stream, [msg, chatbot], [chatbot, msg])
    clear.click(lambda: [], outputs=chatbot)

if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1")  # 仅本机访问
