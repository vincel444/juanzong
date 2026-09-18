"""推理客户端：通过本地推理服务的 API 调用 Spark-X2.5 双模型。

双模型分别有自己的服务地址（SMALL_BASE_URL / LARGE_BASE_URL），支持两种后端：
- "openai":  OpenAI 兼容 /v1/chat/completions（自建 serve_transformers.py /
             llama-server / vLLM / SGLang），思考档位用
             chat_template_kwargs.enable_thinking
- "ollama":  Ollama 原生 /api/chat，思考档位用 think=true/false
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum

import requests

from config import (BACKEND_STYLE, GEN_KWARGS, LARGE_BASE_URL, LARGE_MODEL,
                    SMALL_BASE_URL, SMALL_MODEL, TIMEOUT_SECONDS)


class Tier(str, Enum):
    """思考档位：低档=1.7B 关闭思考快速应答；高档=4B 开启思考深度推理。"""

    LOW = "low"
    HIGH = "high"


@dataclass
class GenResult:
    text: str
    thinking: str
    latency_ms: int
    prompt_tokens: int
    eval_tokens: int
    model: str
    tier: Tier


def _chat_openai(base_url: str, model: str, messages: list[dict], think: bool,
                 max_tokens: int) -> dict:
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "max_tokens": max_tokens,
        "chat_template_kwargs": {"enable_thinking": think},
        **GEN_KWARGS,
    }
    r = requests.post(f"{base_url}/v1/chat/completions", json=payload,
                      timeout=TIMEOUT_SECONDS)
    r.raise_for_status()
    return r.json()


def _chat_ollama(base_url: str, model: str, messages: list[dict], think: bool,
                 max_tokens: int) -> dict:
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "think": think,
        "options": {**GEN_KWARGS, "num_predict": max_tokens},
    }
    r = requests.post(f"{base_url}/api/chat", json=payload, timeout=TIMEOUT_SECONDS)
    r.raise_for_status()
    return r.json()


def chat(model: str, base_url: str, messages: list[dict], tier: Tier,
         max_tokens: int = 1024) -> GenResult:
    """调用一次对话补全，返回带性能埋点的结果（消融实验直接取数）。"""
    think = tier == Tier.HIGH
    start = time.perf_counter()
    if BACKEND_STYLE == "ollama":
        data = _chat_ollama(base_url, model, messages, think, max_tokens)
        msg = data["message"]
        text = msg.get("content", "")
        thinking = msg.get("thinking", "") or ""
        prompt_tokens = data.get("prompt_eval_count", 0) or 0
        eval_tokens = data.get("eval_count", 0) or 0
    else:
        data = _chat_openai(base_url, model, messages, think, max_tokens)
        choice = data["choices"][0]["message"]
        text = choice.get("content", "") or ""
        thinking = choice.get("reasoning_content", "") or ""
        usage = data.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0) or 0
        eval_tokens = usage.get("completion_tokens", 0) or 0
    latency_ms = int((time.perf_counter() - start) * 1000)
    return GenResult(text=text.strip(), thinking=thinking.strip(), latency_ms=latency_ms,
                     prompt_tokens=prompt_tokens, eval_tokens=eval_tokens,
                     model=model, tier=tier)


# 两个模型的便捷入口
def ask_small(question: str, system: str = "", max_tokens: int = 1024) -> GenResult:
    messages = ([{"role": "system", "content": system}] if system else []) + [
        {"role": "user", "content": question}
    ]
    return chat(SMALL_MODEL, SMALL_BASE_URL, messages, Tier.LOW, max_tokens)


def ask_large(question: str, system: str = "", max_tokens: int = 2048) -> GenResult:
    messages = ([{"role": "system", "content": system}] if system else []) + [
        {"role": "user", "content": question}
    ]
    return chat(LARGE_MODEL, LARGE_BASE_URL, messages, Tier.HIGH, max_tokens)
