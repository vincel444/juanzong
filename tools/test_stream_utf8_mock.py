# -*- coding: utf-8 -*-
"""mock SSE 服务器验证 chat_stream 的 UTF-8 解码修复。

模拟 llama-server 行为:Content-Type: text/event-stream(无 charset),
推送中文 delta。修复前 requests 按 ISO-8859-1 解码 → 乱码;修复后应原样还原。
"""
import io
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, r"G:\私\新建文件夹\星火ai应用\juanzong\src")

SENTENCES = ["这是中文流式输出测试。", "引号与书名号《卷宗》也需原样。", "Emoji与符号✓。"]


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")  # 故意不带 charset
        self.end_headers()
        for s in SENTENCES:
            chunk = {"choices": [{"delta": {"content": s}}]}
            self.wfile.write(f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n".encode("utf-8"))
            self.wfile.flush()
        self.wfile.write(b"data: [DONE]\n\n")

    def log_message(self, *a):
        pass


srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()

from inference import chat_stream, Tier

parts = []
for ev, payload in chat_stream("mock", f"http://127.0.0.1:{port}",
                               [{"role": "user", "content": "hi"}], Tier.LOW):
    if ev == "content":
        parts.append(payload)

text = "".join(parts)
expect = "".join(SENTENCES)
print("GOT   :", text)
print("EXPECT:", expect)
print("RESULT:", "PASS" if text == expect else "FAIL")
srv.shutdown()
