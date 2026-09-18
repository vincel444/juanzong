"""GGUF 推理服务（llama.cpp / llama-cpp-python）：OpenAI 兼容 API。

用途：官方 eager attention 的 transformers 路线在 GPU 上速度不佳（约 3.5 tok/s），
改用官方 GGUF 量化版 + llama.cpp 推理，速度显著提升、显存/内存占用大幅下降。

用法：
    python scripts/serve_gguf.py --model models/Spark-X2.5-1.7B-Q4_K_M.gguf --port 11435
    python scripts/serve_gguf.py --model models/Spark-X2.5-4B-Q4_K_M.gguf  --port 11436

思考档位：chat template 的 enable_thinking 参数（官方模板默认开启思考）。
若当前 llama-cpp-python 版本不支持直接传模板参数，则回退为手工渲染模板。
"""
from __future__ import annotations

import argparse
import os
import time

import uvicorn
from fastapi import FastAPI
from llama_cpp import Llama
from pydantic import BaseModel

app = FastAPI(title="Spark-X2.5 GGUF server")
state: dict = {}
THINK_OPEN, THINK_CLOSE = "<think>", "</think>"


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: str = "spark"
    messages: list[Message]
    max_tokens: int = 512
    temperature: float = 1.0
    top_p: float = 0.95
    chat_template_kwargs: dict = {}


def split_thinking(text: str) -> tuple[str, str]:
    if THINK_CLOSE in text:
        head, _, body = text.partition(THINK_CLOSE)
        think = head.split(THINK_OPEN, 1)[1] if THINK_OPEN in head else head
        return think.strip(), body.strip()
    return "", text.strip()


@app.on_event("startup")
def load() -> None:
    n_threads = max(1, (os.cpu_count() or 4) - 1)
    llm = Llama(
        model_path=state["model_path"],
        n_ctx=state["n_ctx"],
        n_threads=n_threads,
        n_gpu_layers=state["n_gpu_layers"],
        chat_template=state["chat_template"],  # 可空，自动读取 GGUF 内置模板
        verbose=False,
    )
    state["llm"] = llm
    print(f"[gguf] 加载完成 {state['model_path']} n_ctx={state['n_ctx']} "
          f"threads={n_threads} gpu_layers={state['n_gpu_layers']}", flush=True)


@app.post("/v1/chat/completions")
def completions(req: ChatRequest):
    llm: Llama = state["llm"]
    think = bool(req.chat_template_kwargs.get("enable_thinking", False))
    msgs = [m.model_dump() for m in req.messages]

    t0 = time.perf_counter()
    kwargs = dict(
        messages=msgs,
        max_tokens=req.max_tokens,
        temperature=req.temperature,
        top_p=req.top_p,
    )
    if state["chat_template"]:
        kwargs["chat_template"] = state["chat_template"]
    try:
        out = llm.create_chat_completion(chat_template_kwargs={"enable_thinking": think}, **kwargs)
    except TypeError:  # 版本不支持 chat_template_kwargs：手工渲染后走 completion
        prompt = llm.tokenize  # 占位，避免静态检查误报
        del prompt
        out = _fallback_completion(llm, msgs, think, req)
    latency_ms = int((time.perf_counter() - t0) * 1000)

    content_raw = out["choices"][0]["message"]["content"] or ""
    thinking, content = split_thinking(content_raw)
    usage = out.get("usage", {}) or {}
    return {
        "id": f"gguf-{time.time_ns()}",
        "object": "chat.completion",
        "model": req.model,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": content,
                        "reasoning_content": thinking},
            "finish_reason": "stop",
        }],
        "usage": {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        },
        "latency_ms": latency_ms,
    }


def _fallback_completion(llm: Llama, msgs: list[dict], think: bool, req: ChatRequest):
    """手工渲染 chat template，再走底层 completion（保证档位开关依然生效）。"""
    template = (llm.metadata or {}).get("tokenizer.chat_template", "")
    from jinja2 import Template

    prompt = Template(template).render(
        messages=msgs, add_generation_prompt=True,
        enable_thinking=think, **({"bos_token": ""}),
    )
    return llm.create_completion(prompt=prompt, max_tokens=req.max_tokens,
                                temperature=req.temperature, top_p=req.top_p)


@app.get("/health")
def health():
    return {"ok": state.get("llm") is not None}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, help="GGUF 文件绝对路径")
    parser.add_argument("--port", type=int, default=11435)
    parser.add_argument("--n-ctx", type=int, default=8192,
                        help="上下文长度；CPU 内存有限，默认 8192，可按需调大")
    parser.add_argument("--n-gpu-layers", type=int, default=0,
                        help="卸载到 GPU 的层数；CPU 版 llama-cpp-python 留 0")
    parser.add_argument("--chat-template", default="", help="自定义 chat template 文件路径")
    args = parser.parse_args()
    state["model_path"] = args.model
    state["n_ctx"] = args.n_ctx
    state["n_gpu_layers"] = args.n_gpu_layers
    state["chat_template"] = args.chat_template
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
