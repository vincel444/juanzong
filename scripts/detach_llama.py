# -*- coding: utf-8 -*-
"""分离式启动 llama 双模型:脱离父进程作业对象,WorkBuddy 会话结束后仍存活。

用法:
    python scripts/detach_llama.py            # 启动 1.7B(11435) + 4B(11436)
    python scripts/detach_llama.py --only 17b

与 start_llama_servers.py 的区别:
- start_llama_servers.py 适合自己在终端里跑(父进程阻塞管理,Ctrl+C 全停)
- 本脚本启动后立即退出,子进程以 DETACHED_PROCESS|CREATE_BREAKAWAY_FROM_JOB
  脱离作业对象,不受终端/会话关闭影响;日志写入 logs/llama_{17b,4b}.log
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BIN = Path(r"C:/Users/54780/.workbuddy/bin/llama/llama-b11026-bin-win-cuda-13.4-x64")
LOG_DIR = ROOT / "logs"

SERVERS = {
    "17b": dict(gguf=ROOT / "models" / "Spark-X2.5-1.7B-Q4_K_M.gguf", port=11435, ctx=32768),
    "4b": dict(gguf=ROOT / "models" / "Spark-X2.5-4B-Q4_K_M.gguf", port=11436, ctx=16384),
}

DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_BREAKAWAY_FROM_JOB = 0x01000000


def spawn(bin_dir: Path, key: str, cfg: dict, breakaway: bool) -> int:
    import subprocess
    exe = bin_dir / "llama-server.exe"
    if not exe.exists():
        sys.exit(f"找不到 {exe}")
    if not cfg["gguf"].exists():
        sys.exit(f"找不到模型 {cfg['gguf']}")
    LOG_DIR.mkdir(exist_ok=True)
    log = open(LOG_DIR / f"llama_{key}.log", "ab")
    flags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    if breakaway:
        flags |= CREATE_BREAKAWAY_FROM_JOB
    cmd = [
        str(exe),
        "-m", str(cfg["gguf"]),
        "--port", str(cfg["port"]),
        "-ngl", "99",
        "-c", str(cfg["ctx"]),
        "-t", "8",
        "--jinja",
        "--cache-reuse", "256",
        "--no-warmup",
    ]
    proc = subprocess.Popen(cmd, cwd=str(bin_dir), stdout=log, stderr=log,
                            stdin=subprocess.DEVNULL, close_fds=True,
                            creationflags=flags)
    print(f"[{key}] pid={proc.pid} port={cfg['port']} breakaway={breakaway}")
    return proc.pid


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
    ap.add_argument("--bin", default=str(DEFAULT_BIN))
    ap.add_argument("--only", choices=["17b", "4b"])
    ap.add_argument("--no-wait", action="store_true", help="不等健康检查直接退出")
    args = ap.parse_args()
    bin_dir = Path(args.bin)
    keys = [args.only] if args.only else list(SERVERS)

    for k in keys:
        try:
            spawn(bin_dir, k, SERVERS[k], breakaway=True)
        except OSError as e:  # 作业对象禁止 breakaway 时降级
            print(f"[{k}] breakaway 被拒({e}),降级为普通分离启动")
            spawn(bin_dir, k, SERVERS[k], breakaway=False)

    if not args.no_wait:
        for k in keys:
            port = SERVERS[k]["port"]
            ok = wait_ready(port)
            print(f"[{'就绪' if ok else '超时'}] {k} -> http://127.0.0.1:{port}")
            if not ok:
                sys.exit(1)
    print("完成:子进程已脱离会话,关闭终端/会话不影响服务。")
