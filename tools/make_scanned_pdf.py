"""生成图片型（无文字层）扫描版 PDF 测试件：模拟论文扫描件。

内容为两页中文"论文"文字，直接位图化打包成 PDF —— pypdf 抽不到
任何文本层，用于验证 retrieval 的自动 OCR 链路。
"""
import sys
from pathlib import Path

import fitz
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent.parent / "data" / "papers" / "扫描论文-OCR测试.pdf"
W, H = 1240, 1754  # ~150dpi A4

PAGES = [
    ["基于端侧大模型的长文档审阅工作台研究",
     "",
     "摘要：本文提出一种隐私优先的端侧长文档审阅工作台，",
     "采用三级自适应路由机制，将轻量问答、链式推理与跨文档",
     "审阅任务分别调度至不同规格的本地模型，实现毫秒级首字",
     "响应与深度审阅的平衡。系统引入字符级滑窗溯源校验，",
     "对模型回答逐句回查原文，未溯源句自动标注提示人工复核，",
     "有效抑制端侧场景下的幻觉问题。",
     "",
     "关键词：端侧大模型；长文档审阅；自适应路由；溯源校验",
     "",
     "1 引言",
     "随着开源模型能力提升，本地部署的隐私计算方案逐渐",
     "可行。然而长文档场景下，单一模型难以兼顾速度与深度，",
     "本文通过双模型架构与智能降级策略解决这一矛盾。"],
    ["2 方法",
     "",
     "2.1 三级自适应路由",
     "路由器基于问题复杂度特征（关键词、长度、跨文档指代）",
     "将请求调度至 1.7B 快答档或 4B 审阅档，并在深档超时时",
     "自动降级补发，保障响应可用性。",
     "",
     "2.2 溯源校验",
     "构建字符级 8-gram 索引，对回答逐句滑窗匹配原文，",
     "命中率低于阈值的句子标记为未溯源。校验纯 CPU 毫秒级，",
     "零额外推理开销。",
     "",
     "3 实验设置",
     "baseline 为单模型直答方案，评测指标包括首字时延、",
     "总时延、token 吞吐与溯源命中率。测试集为三份真实",
     "合同的脱敏样例，覆盖试用期、违约金、质保等高频条款。"],
]


def render(lines: list[str]) -> Image.Image:
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    font = None
    for name in ("simhei.ttf", "msyh.ttc", "simsun.ttc"):
        try:
            font = ImageFont.truetype(f"C:/Windows/Fonts/{name}", 34)
            break
        except OSError:
            continue
    assert font, "no CJK font"
    y = 140
    for ln in lines:
        d.text((120, y), ln, font=font, fill=(20, 20, 20))
        y += 62
    # 加一点扫描噪点感：浅灰边框
    d.rectangle([40, 40, W - 40, H - 40], outline=(180, 180, 180), width=3)
    return img


OUT.parent.mkdir(parents=True, exist_ok=True)
doc = fitz.open()
for lines in PAGES:
    tmp = OUT.with_suffix(".png")
    render(lines).save(tmp)
    page = doc.new_page(width=595, height=842)  # A4 pt
    page.insert_image(page.rect, filename=str(tmp))
    tmp.unlink()
doc.save(str(OUT))
doc.close()
print("scanned-pdf ->", OUT)
