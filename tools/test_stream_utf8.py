# -*- coding: utf-8 -*-
"""验证流式解码修复:SSE 中文应正常显示,无 mojibake。"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, r"G:\私\新建文件夹\星火ai应用\juanzong\src")

from inference import chat_stream, Tier, SMALL_MODEL, SMALL_BASE_URL

parts = []
for ev, payload in chat_stream(SMALL_MODEL, SMALL_BASE_URL,
                               [{"role": "user", "content": "用一句话介绍你自己"}],
                               Tier.LOW, max_tokens=128):
    if ev == "content":
        parts.append(payload)

text = "".join(parts)
print("ANSWER:", text[:200])
bad = any(0xE000 <= ord(ch) <= 0xF8FF or "Ã" in text or "æ" in text for ch in text)
print("MOJIBAKE:", bad)
