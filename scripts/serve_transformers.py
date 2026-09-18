"""本地推理服务：直接加载已下载的 HF 原始权重，暴露 OpenAI 兼容 /v1/chat/completions。

用法（两个终端分别启动，1.7B 先启）：
    python scripts/serve_transformers.py --model "G:/私/科大讯飞/Spark-X2.5-1.7B" --port 11435
    python scripts/serve_transformers.py --model "G:/私/科大讯飞/Spark-X2.5-4B" --port 11436

说明：
- 自定义架构：模型目录自带 modeling_spark.py，通过 trust_remote_code 加载（需 transformers>=4.57.1）
- 思考档位：chat template 默认开启 thinking；请求体 chat_template_kwargs.enable_thinking=false 关闭
- 显存：1.7B bf16 约 3.4GB 可整卡运行；4B bf16 约 8GB，8GB 卡会自动部分 offload 到内存（较慢，
  属预期行为，消融数据如实记录即可；后续可换 GGUF 量化解决）
"""
from __future__ import annotations

import argparse
import time

import torch
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from transformers import AutoModelForCausalLM, AutoTokenizer

app = FastAPI(title="Spark-X2.5 local server")
state: dict = {}


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: str = "spark"
    messages: list[Message]
    max_tokens: int = 1024
    temperature: float = 1.0
    top_p: float = 0.95
    chat_template_kwargs: dict = {}


@app.on_event("startup")
def load() -> None:
    tok = AutoTokenizer.from_pretrained(state["model_path"], trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        state["model_path"],
        trust_remote_code=True,
        dtype=torch.bfloat16,
        device_map="auto",  # 8GB 卡：放得下就全进 GPU，放不下自动 offload
    )
    model.eval()
    # 官方 generation_config 的 top_k=-1 表示"不过滤"，但 HF generate 要求正整数，0 为等效禁用
    model.generation_config.top_k = 0
    state["tokenizer"], state["model"] = tok, model
    n_gpu = sum(1 for p in model.parameters() if p.is_cuda)
    n_all = sum(1 for _ in model.parameters())
    print(f"[server] 模型加载完成：{state['model_path']}  GPU参数层 {n_gpu}/{n_all}")


def split_thinking(text: str) -> tuple[str, str]:
    """把 <think>...</think> 拆成 (thinking, content)。"""
    if "</think>" in text:
        head, _, body = text.partition("</think>")
        think = head
        if "<think>" in think:
            think = think.split("<think>", 1)[1]
        return think.strip(), body.strip()
    return "", text.strip()


@app.post("/v1/chat/completions")
def completions(req: ChatRequest):
    tok, model = state["tokenizer"], state["model"]
    enable_thinking = bool(req.chat_template_kwargs.get("enable_thinking", False))
    msgs = [m.model_dump() for m in req.messages]
    try:
        prompt = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True,
                                         enable_thinking=enable_thinking)
    except TypeError:  # 模板不支持 enable_thinking 参数时的兜底
        prompt = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
    inputs = tok(prompt, return_tensors="pt").to(model.device)

    t0 = time.perf_counter()
    with torch.inference_mode():
        out = model.generate(
            **inputs,
            max_new_tokens=req.max_tokens,
            do_sample=True,
            temperature=req.temperature,
            top_p=req.top_p,
        )
    latency_ms = int((time.perf_counter() - t0) * 1000)
    gen = out[0][inputs["input_ids"].shape[1]:]
    text = tok.decode(gen, skip_special_tokens=True)
    thinking, content = split_thinking(text)

    return {
        "id": f"local-{time.time_ns()}",
        "object": "chat.completion",
        "model": req.model,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": content,
                        "reasoning_content": thinking},
            "finish_reason": "stop",
        }],
        "usage": {
            "prompt_tokens": int(inputs["input_ids"].shape[1]),
            "completion_tokens": int(gen.shape[0]),
            "total_tokens": int(inputs["input_ids"].shape[1] + gen.shape[0]),
        },
        "latency_ms": latency_ms,
    }


@app.get("/health")
def health():
    return {"ok": state.get("model") is not None}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, help="HF 权重目录绝对路径")
    parser.add_argument("--port", type=int, default=11435)
    args = parser.parse_args()
    state["model_path"] = args.model
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
