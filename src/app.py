"""「卷宗」端侧主入口：Gradio 离线界面。

启动前：
1. 确认推理后端已运行（Ollama：`ollama serve` 或托盘程序）；
   模型已拉取：ollama pull SparkLLM/Spark-X2.5-1.7B / Spark-X2.5-4B
2. .venv 激活后运行：python src/app.py

演示要点：界面显示每轮回答走了哪个模型档位、时延与 token 数；回答附出处页码。
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


def chat_turn(question: str, history: list):
    from router import answer

    if not question.strip():
        return history, ""
    try:
        result, refs = answer(question)
        cites = "、".join(sorted({f"{r.doc_name} p{r.page}" for r in refs})) or "无"
        thinking_note = f"\n\n<details><summary>思考过程（{len(result.thinking)} 字）</summary>\n{result.thinking}\n</details>" if result.thinking else ""
        reply = (
            f"{result.text}\n\n---\n"
            f"档位：{result.tier.value}（{result.model}）｜时延 {result.latency_ms} ms｜"
            f"输入 {result.prompt_tokens} tok / 输出 {result.eval_tokens} tok｜出处：{cites}"
            f"{thinking_note}"
        )
        history = history + [{"role": "user", "content": question},
                             {"role": "assistant", "content": reply}]
    except Exception as e:  # 后端未启动 / 网络异常等
        history = history + [{"role": "user", "content": question},
                             {"role": "assistant", "content": f"调用失败：{e}\n请确认推理后端已启动并拉取模型。"}]
    return history, ""


with gr.Blocks(title="卷宗 · 本地长文档工作台") as demo:
    gr.Markdown(
        "## 卷宗 — 隐私优先的本地长文档智能工作台\n"
        "Spark-X2.5 双模型端侧协作：1.7B 常驻快答，4B 深度审阅。全程离线，数据不出设备。"
    )
    status = gr.Textbox(label="后端状态", value="点击检测", interactive=False)
    check_btn = gr.Button("检测模型服务")
    check_btn.click(check_backend, outputs=status)

    with gr.Row():
        docs = gr.Textbox(label="资料库文件", lines=6, interactive=False)
        refresh_btn = gr.Button("刷新资料库")
    refresh_btn.click(refresh_docs, outputs=docs)

    chatbot = gr.Chatbot(label="问答（带出处溯源）", height=420)
    msg = gr.Textbox(label="你的问题（问句越长/越复杂，会自动路由到 4B 深度档）")
    clear = gr.Button("清空对话")

    msg.submit(chat_turn, [msg, chatbot], [chatbot, msg])
    clear.click(lambda: [], outputs=chatbot)

if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1")  # 仅本机访问
