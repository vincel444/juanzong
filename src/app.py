"""「卷宗」端侧主入口：Gradio 三栏设计系统界面（v2 · 流式）。

视觉：与 PPT 同源的 #0F172A 深蓝设计系统（design/DESIGN-SPEC.md）
布局：左栏（模型服务 + 资料库）｜中栏（对话流 + 路由预测输入）｜右栏（溯源明细）
启动：
1. python scripts/start_llama_servers.py
2. python src/app.py  （桌面壳 desktop.py 会自动完成这两步）
"""
from __future__ import annotations

import html as _html
import shutil
import subprocess
from pathlib import Path

import gradio as gr

from config import DATA_DIR, LARGE_BASE_URL, LARGE_MODEL, SMALL_BASE_URL, SMALL_MODEL
from inference import chat, Tier

# ---------------------------------------------------------------- 设计 tokens
CSS = """
:root{--bg:#0F172A;--panel:#1E293B;--panel2:#243147;--bd:#334155;--bd2:#2A3A54;
--hi:#F1F5F9;--mid:#94A3B8;--low:#7C8BA1;--blue:#3B82F6;--blued:#2563EB;
--cyan:#06B6D4;--ok:#34D399;--warn:#FBBF24;--err:#F87171;
--mono:'JetBrains Mono','Cascadia Mono',Consolas,monospace}
.gradio-container{background:var(--bg)!important;color:var(--hi)!important;
font-family:'Microsoft YaHei UI','PingFang SC',system-ui,sans-serif!important}
.gradio-container footer{display:none!important}
/* 左右栏卡片 */
.jz-card{background:var(--panel2);border:1px solid var(--bd2);border-radius:10px;
padding:12px 14px;margin-bottom:10px}
.jz-card h3{font-size:11px;font-weight:600;color:var(--low);letter-spacing:2px;margin:0 0 8px}
.jz-svc{display:flex;align-items:center;gap:8px;padding:4px 0;font-size:12.5px}
.jz-dot{width:8px;height:8px;border-radius:50%;flex:none}
.jz-dot.on{background:var(--ok);box-shadow:0 0 0 0 rgba(52,211,153,.5);animation:jzp 2.4s infinite}
.jz-dot.off{background:var(--err)}
@keyframes jzp{0%,100%{box-shadow:0 0 0 0 rgba(52,211,153,.5)}50%{box-shadow:0 0 0 5px rgba(52,211,153,0)}}
.jz-svc .n{flex:1;color:var(--hi)} .jz-svc .m{font-family:var(--mono);font-size:10.5px;color:var(--low)}
.jz-vram{height:5px;border-radius:3px;background:#0F172A;overflow:hidden;margin:6px 0 3px}
.jz-vram i{display:block;height:100%;background:linear-gradient(90deg,var(--blue),var(--cyan))}
.jz-meta{display:flex;justify-content:space-between;font-size:10.5px;color:var(--low);font-family:var(--mono)}
.jz-doc{display:flex;align-items:center;gap:8px;padding:6px 0;font-size:12.5px;border-bottom:1px dashed var(--bd2)}
.jz-doc:last-child{border-bottom:none}
.jz-doc svg{flex:none}
.jz-doc .fn{flex:1;min-width:0}
.jz-doc .fn b{display:block;font-weight:500;color:var(--hi);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.jz-doc .fn small{font-size:10.5px;color:var(--low);font-family:var(--mono)}
/* 三档图例 */
.jz-tier{display:flex;gap:6px;margin-top:8px}
.jz-tier span{flex:1;text-align:center;font-size:10.5px;padding:4px 2px;border-radius:6px;border:1px solid var(--bd)}
.jz-tier .t1{color:var(--cyan);border-color:rgba(6,182,212,.4)}
.jz-tier .t2{color:var(--blue);border-color:rgba(59,130,246,.4)}
.jz-tier .t3{background:var(--blued);border-color:var(--blued);color:#fff}
/* 路由预测 pill */
#route-pill .pill{display:inline-flex;align-items:center;gap:6px;font-size:11px;
color:var(--mid);background:var(--panel2);border:1px solid var(--bd2);border-radius:99px;
padding:3px 12px;transition:all .2s}
#route-pill .pill i{width:7px;height:7px;border-radius:50%;background:var(--cyan)}
#route-pill .pill.deep{color:#fff;background:var(--blued);border-color:var(--blued)}
#route-pill .pill.deep i{background:#fff}
/* 右栏溯源 */
.jz-cite{background:var(--panel);border:1px solid var(--bd2);border-radius:10px;padding:10px 12px;margin-bottom:8px}
.jz-cite .row{display:flex;align-items:center;gap:6px;margin-bottom:4px}
.jz-cite .row b{font-size:12px;color:var(--hi);flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.jz-cite .pg{font-family:var(--mono);font-size:10.5px;color:var(--cyan);
border:1px solid rgba(6,182,212,.4);border-radius:4px;padding:1px 7px;flex:none}
.jz-cite .q{font-size:12.5px;color:var(--mid);line-height:1.7;border-left:2px solid var(--bd);padding-left:8px;margin-bottom:6px}
.jz-cite .q.ok{border-color:var(--ok)} .jz-cite .q.part{border-color:var(--warn)} .jz-cite .q.miss{border-color:var(--err)}
.jz-hit{display:flex;align-items:center;gap:8px;font-size:10.5px;color:var(--low)}
.jz-hit .hb{flex:1;height:4px;border-radius:2px;background:#0F172A;overflow:hidden}
.jz-hit .hb i{display:block;height:100%}
.jz-legend{display:flex;gap:10px;font-size:10.5px;color:var(--mid);margin-bottom:10px}
.jz-legend span{display:flex;align-items:center;gap:4px}
.jz-legend i{width:14px;height:3px;border-radius:2px;display:inline-block}
/* 聊天气泡轻覆盖 */
.chatbot{background:transparent!important;border:none!important}
.chatbot .message{border-radius:12px!important}
/* 品牌 */
.jz-brand{display:flex;align-items:center;gap:10px;margin-bottom:6px}
.jz-seal{width:38px;height:38px;border-radius:10px;background:var(--panel2);
border-left:4px solid var(--blue);display:flex;align-items:center;justify-content:center;
font-size:19px;font-weight:700;flex:none}
.jz-brand h1{font-size:17px;letter-spacing:4px;font-weight:600;margin:0;color:var(--hi)}
.jz-brand p{font-size:10.5px;color:var(--low);margin:0;letter-spacing:1px}
.jz-offline{display:flex;align-items:center;gap:6px;font-size:11px;color:var(--low);
margin-top:4px;justify-content:center}
.jz-offline i{width:7px;height:7px;border-radius:50%;background:var(--ok)}
/* 上传入口 */
#upload-box{font-size:12px;margin-top:2px}
#upload-box label span, #upload-box button span{font-size:11.5px!important;color:var(--mid)!important}
#upload-box .upload-container, #upload-box [class*="upload"]{border-color:var(--bd2)!important}
/* 资料库多选列表（卡片化） */
#docs-list{background:var(--panel2);border:1px solid var(--bd2);border-radius:10px;
padding:10px 12px;margin-bottom:10px}
#docs-list > div > span, #docs-list label.container > span{
font-size:11px!important;font-weight:600!important;color:var(--low)!important;letter-spacing:2px}
#docs-list label{display:flex!important;gap:8px;align-items:flex-start;
padding:7px 6px;border-radius:6px;cursor:pointer;
border-bottom:1px dashed var(--bd2);transition:background var(--tr-fast);margin:0}
#docs-list label:hover{background:rgba(59,130,246,.08)}
#docs-list input[type="checkbox"]{accent-color:var(--blue)!important;
width:15px;height:15px;margin-top:3px;flex:none}
#docs-list label span:not(.ellipsis){font-size:12.5px!important;
color:var(--hi)!important;line-height:1.55!important;word-break:break-all}
"""

BRAND = """
<div class="jz-brand"><div class="jz-seal">卷</div>
<div><h1>卷宗</h1><p>本地长文档智能工作台</p></div></div>
"""

DOC_SVG = ('<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="#94A3B8" '
           'stroke-width="1.8"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12'
           'a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg>')


# ---------------------------------------------------------------- 左栏渲染
def _gpu_mem() -> tuple[str, int]:
    """返回 (显存文本, 占用百分比)。失败返回占位。"""
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=3).stdout.strip()
        used, total = [int(x) for x in out.splitlines()[0].split(",")]
        return f"{used/1024:.1f} / {total/1024:.1f} GB", round(used / total * 100)
    except Exception:
        return "— / —", 0


def check_backend_html() -> str:
    def ping(model: str, base_url: str) -> bool:
        try:
            chat(model, base_url, [{"role": "user", "content": "ping"}],
                 Tier.LOW, max_tokens=4)
            return True
        except Exception:
            return False

    ok_s = ping(SMALL_MODEL, SMALL_BASE_URL)
    ok_l = ping(LARGE_MODEL, LARGE_BASE_URL)
    dot = lambda ok: '<span class="jz-dot on"></span>' if ok else '<span class="jz-dot off"></span>'
    mem, pct = _gpu_mem()
    return f"""
<div class="jz-card"><h3>模型服务</h3>
  <div class="jz-svc">{dot(ok_s)}<span class="n">Spark-X2.5 · 1.7B</span>
    <span class="m">{SMALL_BASE_URL.split(':')[-1]}</span></div>
  <div class="jz-svc">{dot(ok_l)}<span class="n">Spark-X2.5 · 4B</span>
    <span class="m">{LARGE_BASE_URL.split(':')[-1]}</span></div>
  <div class="jz-vram"><i style="width:{pct}%"></i></div>
  <div class="jz-meta"><span>显存占用</span><span>{mem}</span></div>
  <div class="jz-tier"><span class="t1">轻·快答</span><span class="t2">中·推理</span>
    <span class="t3">深·4B审阅</span></div>
</div>"""


def docs_choices() -> list[tuple[str, str]]:
    """资料库多选列表的 (显示label, 文件名) —— label 携带页数与 OCR 标记。"""
    from retrieval import ocr_info, scan_documents

    out: list[tuple[str, str]] = []
    for p in scan_documents():
        meta = ""
        try:
            if p.suffix.lower() == ".pdf":
                from pypdf import PdfReader
                meta = f" · {len(PdfReader(str(p)).pages)} 页 · {ocr_info(p)}"
            else:
                meta = f" · {p.stat().st_size // 1024} KB"
        except Exception:
            meta = " · —"
        out.append((f"{p.name}{meta}", p.name))
    return out


# ---------------------------------------------------------------- 推荐问题（随资料库自适应）
PAPER_WORDS = ("摘要", "关键词", "abstract", "keywords", "参考文献",
               "references", "arxiv", "et al.", "引言")
CONTRACT_WORDS = ("甲方", "乙方", "合同", "承租", "出租", "违约", "条款",
                  "协议", "劳动合同", "质保")

CHIP_SETS = {
    "paper": ("这篇论文的创新点是什么？", "实验设置和 baseline 有哪些？",
              "总结论文方法与局限，结论是否被实验支撑？",
              "对比几篇论文的方法与结论差异"),
    "contract": ("合同里甲方是谁？", "试用期约定合法吗？",
                 "对比三份合同的违约金", "哪份合同对我最不利？"),
    "mixed": ("这份资料的核心结论是什么？", "论文的创新点是什么？",
              "对比三份合同的违约金", "哪些内容需要人工复核？"),
}
CHIPS_EMPTY = CHIP_SETS["mixed"]


def library_kind() -> str:
    """按资料内容特征把资料库分为 paper / contract / mixed。

    扫描版 PDF 文字层为空，用其 OCR 缓存文本参与分类。
    """
    from retrieval import _ocr_cache_load, scan_documents

    score_p = score_c = 0
    try:
        for p in scan_documents():
            try:
                if p.suffix.lower() == ".pdf":
                    from pypdf import PdfReader
                    text = PdfReader(str(p)).pages[0].extract_text() or ""
                    if len("".join(text.split())) < 20:  # 扫描页 → 用 OCR 缓存
                        cached = _ocr_cache_load(p)
                        if cached:
                            text = cached.get(1, "") or next(iter(cached.values()), "")
                else:
                    text = p.read_text(encoding="utf-8", errors="ignore")[:2000]
            except Exception:
                continue
            low = text.lower()
            score_p += sum(low.count(w.lower()) for w in PAPER_WORDS)
            score_c += sum(text.count(w) for w in CONTRACT_WORDS)
    except Exception:
        pass
    if score_p == 0 and score_c == 0:
        return "empty"
    if score_c == 0:
        return "paper"
    if score_p == 0:
        return "contract"
    return "mixed"


def chips_for(kind: str) -> tuple[str, str, str, str]:
    return CHIP_SETS.get(kind, CHIPS_EMPTY)


def refresh_all():
    choices = docs_choices()
    kind = library_kind()
    # 默认全选（= 全部资料），用户可点选/取消任意文件
    return (gr.update(choices=choices,
                      value=[v for _, v in choices]),
            *chips_for(kind))


# ---------------------------------------------------------------- 上传入库
def handle_upload(files):
    """把界面上传的文档复制进 data/uploads/（自动重名编号），
    刷新资料卡与推荐问题；OCR 仍按需在问答时触发。"""
    if not files:
        return gr.update(), gr.update(), gr.update(), gr.update(), gr.update()
    dest = DATA_DIR / "uploads"
    dest.mkdir(parents=True, exist_ok=True)
    saved: list[str] = []
    for f in files or []:
        src = Path(getattr(f, "path", None) or getattr(f, "name", None) or f)
        if not Path(src).exists():
            continue
        target = dest / Path(src).name
        i = 1
        while target.exists():
            target = dest / f"{Path(src).stem}({i}){Path(src).suffix}"
            i += 1
        shutil.copy2(src, target)
        saved.append(target.name)
    gr.Info(f"已入库 {len(saved)} 份文档：{('、'.join(saved))[:60]}"
            + ("…" if len("、".join(saved)) > 60 else ""))
    choices = docs_choices()
    return (gr.update(choices=choices, value=[v for _, v in choices]),
            *chips_for(library_kind()))


# ---------------------------------------------------------------- 路由预测
DEEP_HINT = ("对比|总结|审阅|风险|差异|全面|逐条|分析|比较|评估").split("|")


def predict_route(text: str) -> str:
    v = (text or "").strip()
    if not v:
        return '<span class="pill"><i></i>输入问题，自动选择回答档位</span>'
    if any(w in v for w in DEEP_HINT):
        return ('<span class="pill deep"><i></i>复杂问题 · 将由 4B 深档审阅'
                '（约 40s，请耐心等待流式输出）</span>')
    if len(v) < 12:
        return '<span class="pill"><i></i>简短问题 · 1.7B 轻档快答（&lt;1s）</span>'
    return '<span class="pill"><i></i>一般问题 · 1.7B 中档推理（3~8s）</span>'


ROUTE_EMPTY = predict_route("")

# ---------------------------------------------------------------- 右栏溯源
CITE_LEGEND = """
<div class="jz-legend">
<span><i style="background:var(--ok)"></i>已溯源</span>
<span><i style="background:var(--warn)"></i>部分溯源</span>
<span><i style="background:var(--err)"></i>未溯源</span></div>"""

CITE_EMPTY = (CITE_LEGEND +
              '<div style="font-size:12px;color:var(--low)">回答后，这里逐句展示'
              '溯源结果：命中原文的句子标绿，改写综合标黄，无原文依据标红并建议人工复核。</div>')


def cites_html(items) -> str:
    """把 verify_answer 的句子级结果渲染成右栏明细卡。"""
    if not items:
        return CITE_EMPTY
    cards = []
    for it in items[:12]:
        lvl = "ok" if it.verified else ("part" if it.ratio >= 0.01 else "miss")
        color = {"ok": "var(--ok)", "part": "var(--warn)", "miss": "var(--err)"}[lvl]
        srcs = "、".join(f"{d.replace('.pdf', '')} p{pg}" for d, pg in sorted(it.sources)[:3]) or "无原文出处"
        sent = _html.escape(it.sentence[:64] + ("…" if len(it.sentence) > 64 else ""))
        cards.append(f"""
<div class="jz-cite"><div class="row"><b>{sent}</b>
<span class="pg">{round(it.ratio * 100)}%</span></div>
<div class="q {lvl}">{_html.escape(srcs)}</div>
<div class="jz-hit"><span>{lvl}</span>
<span class="hb"><i style="width:{round(it.ratio * 100)}%;background:{color}"></i></span></div></div>""")
    return CITE_LEGEND + "".join(cards)


# ---------------------------------------------------------------- 对话（流式）
TIER_LABEL = {Tier.LOW: "轻档·1.7B快答", Tier.MEDIUM: "中档·1.7B推理",
              Tier.HIGH: "深档·4B审阅"}


def _render(thinking: list[str], content: list[str], notices: list[str]) -> str:
    prefix = "".join(f"> ℹ️ {n}\n\n" for n in notices)
    thinking_acc, content_acc = "".join(thinking), "".join(content)
    note = ""
    if thinking_acc:
        label = "思考中…" if not content_acc else f"思考过程（{len(thinking_acc)} 字）"
        note = (f"<details open><summary>{label}</summary>\n\n"
                f"{thinking_acc}\n\n</details>")
    body = content_acc or ("思考中…" if thinking_acc else "…")
    sep = "\n\n" if note and content_acc else ""
    return prefix + note + sep + body


def chat_turn_stream(question: str, history: list, selected: list | None = None):
    """流式对话轮：yield (history, msg, 右栏溯源 HTML)。

    selected: 左栏勾选的文件名（空 = 全部资料）。
    """
    from citation import collect_sources, summarize, verify_answer
    from router import answer_stream

    if not question.strip():
        yield history, "", gr.update()
        return

    history = history + [{"role": "user", "content": question}]
    reply_idx = len(history)
    history = history + [{"role": "assistant", "content": "…"}]
    yield history, "", gr.update()

    thinking: list[str] = []
    content: list[str] = []
    notices: list[str] = []
    outcome = None
    try:
        for kind, payload in answer_stream(question, docs_filter=selected or None):
            if kind == "thinking":
                thinking.append(payload)
            elif kind == "content":
                content.append(payload)
            elif kind == "notice":
                notices.append(payload)
            elif kind == "done":
                outcome = payload
            history[reply_idx] = {"role": "assistant",
                                  "content": _render(thinking, content, notices)}
            yield history, "", gr.update()

        result, refs, citation_index = outcome
        items = verify_answer(result.text, citation_index) if result.text else []
        total, ok, missed = summarize(items)
        cites = "、".join(collect_sources(items)) or "无"

        footer = (
            f"\n\n---\n档位：{TIER_LABEL.get(result.tier, result.tier.value)}"
            f"（{result.model}）｜首字 {result.first_token_ms/1000:.2f} s｜"
            f"总时延 {result.latency_ms/1000:.1f} s｜输出 {result.eval_tokens} tok\n"
            f"出处：{cites}｜溯源校验：{ok}/{total} 句命中原文"
        )
        if missed:
            pure = [m for m in missed if m.ratio < 0.01]
            partial = [m for m in missed if m.ratio >= 0.01]
            warn = []
            if pure:
                warn.append("未溯源: " + "；".join(m.sentence[:32] for m in pure[:3]))
            if partial:
                warn.append("部分溯源: " + "；".join(m.sentence[:32] for m in partial[:3]))
            footer += ("\n⚠️ 建议人工复核 —— " + " ｜ ".join(warn)
                       + ("…" if len(missed) > 3 else ""))
        else:
            footer += " ✅"

        history[reply_idx] = {"role": "assistant",
                              "content": _render(thinking, content, notices) + footer}
        yield history, "", cites_html(items)
    except Exception as e:
        history[reply_idx] = {"role": "assistant",
                              "content": f"调用失败：{e}\n请确认推理服务已启动。"}
        yield history, "", gr.update()


# ---------------------------------------------------------------- 界面
with gr.Blocks(title="卷宗 · 本地长文档工作台") as demo:
    with gr.Row(equal_height=False):
        # ---- 左栏 ----
        with gr.Column(scale=1, min_width=252):
            gr.HTML(BRAND)
            svc = gr.HTML("点击下方按钮检测模型服务")
            with gr.Row():
                check_btn = gr.Button("检测服务", size="sm")
                refresh_btn = gr.Button("刷新资料", size="sm")
            docs = gr.CheckboxGroup(
                label="资料库（点击勾选 = 只问所选；全不勾 = 全部资料）",
                choices=[], value=[],
                elem_id="docs-list")
            upload = gr.File(
                label="⬆ 上传文档到资料库（PDF / Word / 文本，支持扫描件自动OCR）",
                file_count="multiple",
                file_types=[".pdf", ".docx", ".txt", ".md"],
                elem_id="upload-box")
            gr.HTML('<div class="jz-offline"><i></i>全程端侧离线 · 数据不出设备</div>')
        # ---- 中栏 ----
        with gr.Column(scale=5):
            chatbot = gr.Chatbot(label=None, height=520,
                                 elem_classes="chatbot")
            route = gr.HTML(ROUTE_EMPTY, elem_id="route-pill")
            with gr.Row():
                chip1 = gr.Button(CHIP_SETS["contract"][0], size="sm")
                chip2 = gr.Button(CHIP_SETS["contract"][1], size="sm")
                chip3 = gr.Button(CHIP_SETS["contract"][2], size="sm")
                chip4 = gr.Button(CHIP_SETS["contract"][3], size="sm")
            with gr.Row():
                msg = gr.Textbox(label=None, placeholder="向卷宗提问…（回车发送；"
                                 "问句越长/越复杂，自动路由到 4B 深度档）",
                                 lines=2, scale=6, autofocus=True,
                                 container=False)
                send = gr.Button("发送 ➤", variant="primary", scale=1)
            clear = gr.Button("清空对话", size="sm", variant="secondary")
        # ---- 右栏 ----
        with gr.Column(scale=2, min_width=290):
            gr.HTML('<div class="jz-card" style="padding:8px 12px">'
                    '<h3 style="margin:0">溯源引用 · 最近回答</h3></div>')
            cite = gr.HTML(CITE_EMPTY)

    # ---- 事件 ----
    demo.load(refresh_all, outputs=[docs, chip1, chip2, chip3, chip4])
    check_btn.click(check_backend_html, outputs=svc)
    refresh_btn.click(refresh_all, outputs=[docs, chip1, chip2, chip3, chip4])
    upload.upload(handle_upload, upload, [docs, chip1, chip2, chip3, chip4])

    msg.input(predict_route, msg, route)
    msg.submit(chat_turn_stream, [msg, chatbot, docs], [chatbot, msg, cite])
    send.click(chat_turn_stream, [msg, chatbot, docs], [chatbot, msg, cite])
    clear.click(lambda: ([], ROUTE_EMPTY, CITE_EMPTY),
                outputs=[chatbot, route, cite])

    for chip in (chip1, chip2, chip3, chip4):
        chip.click(lambda c: c, chip, msg).then(
            chat_turn_stream, [msg, chatbot, docs], [chatbot, msg, cite])


if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", css=CSS)  # 仅本机访问
