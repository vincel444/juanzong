"""推理客户端：通过本地推理服务的 API 调用 Spark-X2.5 双模型。

双模型分别有自己的服务地址（SMALL_BASE_URL / LARGE_BASE_URL），支持两种后端：
- "openai":  OpenAI 兼容 /v1/chat/completions（自建 serve_transformers.py /
             llama-server / vLLM / SGLang），思考档位用
             chat_template_kwargs.enable_thinking
- "ollama":  Ollama 原生 /api/chat，思考档位用 think=true/false

流式：chat_stream() 以 SSE/NDJSON 逐 token 产出，深档/中档思考可"边想边看"，
大幅缓解 4B 深档 40s 等待的体感问题（P0-#1）。
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from enum import Enum
from typing import Generator, Literal

import requests

from config import (BACKEND_STYLE, GEN_KWARGS, LARGE_BASE_URL, LARGE_MODEL,
                    SMALL_BASE_URL, SMALL_MODEL, TIMEOUT_SECONDS)

# 本地推理服务一律直连:忽略系统/环境代理(HTTP_PROXY 等),
# 否则代理进程(如 Clash)会把 127.0.0.1 的请求劫持成 502
_SESSION = requests.Session()
_SESSION.trust_env = False


class Tier(str, Enum):
    """思考档位（三档自适应，均由官方 chat template 开关驱动）：
    LOW    1.7B 关闭思考 —— 快问快答，目标 <1s
    MEDIUM 1.7B 开启思考 —— 日常推理，兼顾质量与时延
    HIGH   4B 开启思考   —— 跨文档深度审阅
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


def think_enabled(tier: Tier) -> bool:
    return tier in (Tier.MEDIUM, Tier.HIGH)


def model_for(tier: Tier) -> tuple[str, str]:
    """返回 (模型名, 服务地址)。"""
    if tier == Tier.HIGH:
        return LARGE_MODEL, LARGE_BASE_URL
    return SMALL_MODEL, SMALL_BASE_URL


@dataclass
class GenResult:
    text: str
    thinking: str
    latency_ms: int
    prompt_tokens: int
    eval_tokens: int
    model: str
    tier: Tier
    first_token_ms: int = 0  # 首个 token 到达时延（流式体验指标，非流式为 0）


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
    r = _SESSION.post(f"{base_url}/v1/chat/completions", json=payload,
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
    r = _SESSION.post(f"{base_url}/api/chat", json=payload, timeout=TIMEOUT_SECONDS)
    r.raise_for_status()
    return r.json()


def chat(model: str, base_url: str, messages: list[dict], tier: Tier,
         max_tokens: int = 1024) -> GenResult:
    """调用一次对话补全，返回带性能埋点的结果（消融实验直接取数）。"""
    think = think_enabled(tier)
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


StreamEvent = Literal["thinking", "content", "done"]


def chat_stream(model: str, base_url: str, messages: list[dict], tier: Tier,
                max_tokens: int = 1024
                ) -> Generator[tuple[StreamEvent, object], None, None]:
    """流式对话（P0-#1 深档流式输出）。

    逐 delta 产出 ("thinking", 增量) 与 ("content", 增量)，
    结束时产出 ("done", GenResult)（含完整文本与性能埋点，first_token_ms 为
    首个可见 token 的时延，用于 UI 展示"多久开始出字"）。
    """
    think = think_enabled(tier)
    start = time.perf_counter()
    first_ms = 0
    text_parts: list[str] = []
    thinking_parts: list[str] = []
    prompt_tokens = eval_tokens = 0

    def touch_first():
        nonlocal first_ms
        if not first_ms:
            first_ms = int((time.perf_counter() - start) * 1000)

    if BACKEND_STYLE == "ollama":
        payload = {
            "model": model, "messages": messages, "stream": True,
            "think": think, "options": {**GEN_KWARGS, "num_predict": max_tokens},
        }
        r = _SESSION.post(f"{base_url}/api/chat", json=payload,
                          timeout=TIMEOUT_SECONDS, stream=True)
        r.raise_for_status()
        r.encoding = "utf-8"  # SSE 头无 charset 时 requests 会按 ISO-8859-1 解码 → 中文乱码
        for line in r.iter_lines(decode_unicode=True):
            if not line:
                continue
            data = json.loads(line)
            msg = data.get("message", {})
            t = msg.get("thinking") or ""
            c = msg.get("content") or ""
            if t:
                touch_first()
                thinking_parts.append(t)
                yield ("thinking", t)
            if c:
                touch_first()
                text_parts.append(c)
                yield ("content", c)
            if data.get("done"):
                prompt_tokens = data.get("prompt_eval_count", 0) or 0
                eval_tokens = data.get("eval_count", 0) or 0
    else:
        payload = {
            "model": model, "messages": messages, "stream": True,
            "max_tokens": max_tokens,
            "chat_template_kwargs": {"enable_thinking": think},
            "stream_options": {"include_usage": True},  # llama-server: 最后 chunk 带 usage
            **GEN_KWARGS,
        }
        r = _SESSION.post(f"{base_url}/v1/chat/completions", json=payload,
                          timeout=TIMEOUT_SECONDS, stream=True)
        r.raise_for_status()
        r.encoding = "utf-8"  # llama-server SSE 头不带 charset,默认 ISO-8859-1 会导致中文乱码
        for raw in r.iter_lines(decode_unicode=True):
            if not raw or not raw.startswith("data: "):
                continue
            body = raw[len("data: "):].strip()
            if body == "[DONE]":
                break
            try:
                chunk = json.loads(body)
            except json.JSONDecodeError:
                continue
            usage = chunk.get("usage")
            if usage:
                prompt_tokens = usage.get("prompt_tokens", 0) or 0
                eval_tokens = usage.get("completion_tokens", 0) or 0
            choices = chunk.get("choices") or []
            if not choices:
                continue
            delta = choices[0].get("delta", {}) or {}
            t = delta.get("reasoning_content") or ""
            c = delta.get("content") or ""
            if t:
                touch_first()
                thinking_parts.append(t)
                yield ("thinking", t)
            if c:
                touch_first()
                text_parts.append(c)
                yield ("content", c)

    latency_ms = int((time.perf_counter() - start) * 1000)
    result = GenResult(text="".join(text_parts).strip(),
                       thinking="".join(thinking_parts).strip(),
                       latency_ms=latency_ms, prompt_tokens=prompt_tokens,
                       eval_tokens=eval_tokens, model=model, tier=tier,
                       first_token_ms=first_ms)
    yield ("done", result)


# 三个档位的便捷入口
def ask_small(question: str, system: str = "", max_tokens: int = 1024) -> GenResult:
    """轻档：1.7B 关闭思考。"""
    messages = ([{"role": "system", "content": system}] if system else []) + [
        {"role": "user", "content": question}
    ]
    return chat(SMALL_MODEL, SMALL_BASE_URL, messages, Tier.LOW, max_tokens)


def ask_medium(question: str, system: str = "", max_tokens: int = 3072) -> GenResult:
    """中档：1.7B 开启思考（思考本身耗 token，上限需留足）。"""
    messages = ([{"role": "system", "content": system}] if system else []) + [
        {"role": "user", "content": question}
    ]
    return chat(SMALL_MODEL, SMALL_BASE_URL, messages, Tier.MEDIUM, max_tokens)


def ask_large(question: str, system: str = "", max_tokens: int = 4096) -> GenResult:
    """高档：4B 开启思考。思考过程本身会消耗较多 token，故默认上限取 4096。"""
    messages = ([{"role": "system", "content": system}] if system else []) + [
        {"role": "user", "content": question}
    ]
    return chat(LARGE_MODEL, LARGE_BASE_URL, messages, Tier.HIGH, max_tokens)
