"""一键启动 llama.cpp 双模型服务（GPU 加速，替代 transformers 路线）。

前置：
1. 已下载官方预编译包并解压到 LLAMA_BIN 目录（见 docs/backend-setup.md）
2. 已下载 GGUF 模型到 models/ 目录（Spark-X2.5-1.7B-Q4_K_M.gguf / -4B-Q4_K_M.gguf）

用法：
    python scripts/start_llama_servers.py            # 同时启动 1.7B(11435) 与 4B(11436)
    python scripts/start_llama_servers.py --only 17b # 只启动 1.7B
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BIN = Path(r"C:/Users/54780/.workbuddy/bin/llama/llama-b11026-bin-win-cuda-13.4-x64")

SERVERS = {
    "17b": dict(gguf=ROOT / "models" / "Spark-X2.5-1.7B-Q4_K_M.gguf", port=11435, ctx=32768),
    "4b": dict(gguf=ROOT / "models" / "Spark-X2.5-4B-Q4_K_M.gguf", port=11436, ctx=16384),
}


def start(bin_dir: Path, key: str, cfg: dict, ctx_override: int | None = None) -> subprocess.Popen:
    exe = bin_dir / "llama-server.exe"
    if not exe.exists():
        sys.exit(f"找不到 {exe}，请先解压 llama.cpp 预编译包并确认 --bin 路径")
    if not cfg["gguf"].exists():
        sys.exit(f"找不到模型 {cfg['gguf']}")
    cmd = [
        str(exe),
        "-m", str(cfg["gguf"]),
        "--port", str(cfg["port"]),
        "-ngl", "99",                       # 全部层卸载到 GPU（显存不足可调小）
        "-c", str(ctx_override or cfg["ctx"]),
        "-t", "8",                          # CPU 线程数（辅助）
        "--jinja",                          # 启用 Jinja 模板 → 支持 chat_template_kwargs.enable_thinking
        "--cache-reuse", "256",             # P0-#7: KV cache 前缀复用（256 token 粒度）。
                                            # 同卷多问时，资料段前缀命中即免重算 prompt，
                                            # 二次提问的首字时延显著下降
        "--no-warmup",
    ]
    print(f"[启动] {key}: {' '.join(cmd)}", flush=True)
    return subprocess.Popen(cmd, cwd=str(bin_dir))


def wait_ready(port: int, timeout: int = 300) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            if requests.get(f"http://127.0.0.1:{port}/health", timeout=3).status_code == 200:
                return True
        except requests.RequestException:
            pass
        time.sleep(3)
    return False


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin", default=str(DEFAULT_BIN), help="llama.cpp 解压目录")
    ap.add_argument("--only", choices=["17b", "4b"], help="只启动其中一个")
    ap.add_argument("--ctx", type=int, help="覆盖上下文长度")
    args = ap.parse_args()
    bin_dir = Path(args.bin)

    keys = [args.only] if args.only else list(SERVERS)
    procs = {k: start(bin_dir, k, SERVERS[k], args.ctx) for k in keys}
    for k in keys:
        port = SERVERS[k]["port"]
        ok = wait_ready(port)
        print(f"[{'就绪' if ok else '超时'}] {k} -> http://127.0.0.1:{port}", flush=True)
    print("\n服务已启动。另开终端运行应用：python src/app.py")
    print("按 Ctrl+C 停止全部服务。")
    try:
        for p in procs.values():
            p.wait()
    except KeyboardInterrupt:
        for p in procs.values():
            p.terminate()
        print("已停止全部服务")
