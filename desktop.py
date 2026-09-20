"""「卷宗」桌面壳：独立窗口运行本地长文档工作台。

启动方式（任选）：
- 双击 start_juanzong.bat（内部用 pythonw 运行本文件，无控制台）
- 桌面「卷宗」快捷方式

行为：
1. 弹出独立窗口（WebView2 渲染），先显示品牌加载页
2. 自动检测推理后端（11435/11436）与界面服务（7860），
   未启动则在后台静默拉起；已启动则直接复用
3. 服务就绪后窗口自动跳转到工作台
4. 关闭窗口 = 应用退出；仅清理由本程序拉起的进程，外部服务不受影响
"""
from __future__ import annotations

import os
import subprocess
import threading
import time

import webview

ROOT = os.path.dirname(os.path.abspath(__file__))
PY = os.path.join(os.environ.get("WB_PY_ENV", ""), "python.exe") \
    if os.environ.get("WB_PY_ENV") else \
    r"C:\Users\54780\.workbuddy\binaries\python\envs\default\Scripts\python.exe"

UI_URL = "http://127.0.0.1:7860"
SMALL = "http://127.0.0.1:11435/health"
LARGE = "http://127.0.0.1:11436/health"

NO_WINDOW = 0x08000000  # CREATE_NO_WINDOW

# 本程序拉起的进程（退出时清理；外部已在运行的服务不归我们管）
_owned: list[subprocess.Popen] = []


def alive(url: str) -> bool:
    import urllib.request

    # 空代理表 → 不走系统/环境代理,避免本机服务探测被代理劫持成误判
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(url, timeout=2) as r:
            return r.status < 500
    except Exception:
        return False


def ensure_backends() -> None:
    """按需拉起 llama 双服务与 Gradio（静默、无控制台窗口）。

    llama 用分离式启动（脱离本进程作业对象）：即使桌面壳异常退出,
    已加载显存的双模型也继续存活,下次打开秒级就绪。
    """
    if not (alive(SMALL) and alive(LARGE)):
        _owned.append(subprocess.Popen(
            [PY, os.path.join(ROOT, "scripts", "detach_llama.py"), "--no-wait"],
            cwd=ROOT, creationflags=NO_WINDOW))
    if not alive(UI_URL):
        _owned.append(subprocess.Popen(
            [PY, "app.py"], cwd=os.path.join(ROOT, "src"),
            creationflags=NO_WINDOW))


def wait_and_navigate(window: webview.Window) -> None:
    """轮询工作台就绪后让窗口跳转（最长等 3 分钟）。"""
    for _ in range(180):
        if alive(UI_URL):
            window.load_url(UI_URL)
            return
        time.sleep(1)
    window.load_html(
        "<body style='background:#0F172A;color:#F1F5F9;"
        "font-family:sans-serif;display:flex;align-items:center;"
        "justify-content:center;height:100vh;margin:0'>"
        "<div style='text-align:center'><h2>启动超时</h2>"
        "<p style='color:#94A3B8'>推理服务未能就绪，请重试或查看日志。</p>"
        "</div></body>")


def cleanup() -> None:
    """关窗后只杀自己拉起的进程树。"""
    for p in _owned:
        try:
            if p.poll() is None:
                subprocess.run(
                    ["taskkill", "/f", "/t", "/pid", str(p.pid)],
                    capture_output=True, creationflags=NO_WINDOW)
        except Exception:
            pass


LOADING_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><style>
  body{margin:0;height:100vh;display:flex;flex-direction:column;
       align-items:center;justify-content:center;background:#0F172A;
       font-family:"Microsoft YaHei",sans-serif;color:#F1F5F9}
  .seal{width:96px;height:96px;border-radius:24px;background:#1E293B;
        display:flex;align-items:center;justify-content:center;
        border-left:8px solid #3B82F6;font-size:52px;font-weight:700}
  h1{font-size:26px;margin:28px 0 8px;letter-spacing:6px}
  p{color:#94A3B8;font-size:14px;margin:4px}
  .bar{width:220px;height:4px;background:#1E293B;border-radius:2px;
       margin-top:26px;overflow:hidden}
  .bar i{display:block;width:40%;height:100%;background:#06B6D4;
         border-radius:2px;animation:sweep 1.2s ease-in-out infinite}
  @keyframes sweep{0%{transform:translateX(-100%)}
                   100%{transform:translateX(280%)}}
</style></head><body>
  <div class="seal">卷</div>
  <h1>卷 宗</h1>
  <p>隐私优先的本地长文档智能工作台</p>
  <p id="tip">正在启动本地推理服务…（首次加载模型约需 30 秒）</p>
  <div class="bar"><i></i></div>
</body></html>"""


def main() -> None:
    window = webview.create_window(
        "卷宗 · 本地长文档工作台", html=LOADING_HTML,
        width=1280, height=860, min_size=(960, 640),
        background_color="#0F172A")
    threading.Thread(target=ensure_backends, daemon=True).start()
    threading.Thread(target=wait_and_navigate, args=(window,), daemon=True).start()
    webview.start()
    cleanup()


if __name__ == "__main__":
    main()
