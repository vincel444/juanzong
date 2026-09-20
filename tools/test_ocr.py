"""OCR 链路端到端验证：首次装载（含 OCR）vs 二次装载（缓存命中）计时。"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pypdf import PdfReader

from retrieval import _extract_pdf, ocr_info

PDF = Path(__file__).resolve().parent.parent / "data" / "papers" / "扫描论文-OCR测试.pdf"

# 1) 确认无文字层
raw = [p.extract_text() or "" for p in PdfReader(str(PDF)).pages]
print("文字层字符数:", [len(t.strip()) for t in raw], "→", 
      "无文字层 ✓" if all(len(t.strip()) < 5 for t in raw) else "有文字层 ✗")
print("资料卡标记:", ocr_info(PDF))

# 2) 首次装载（触发 OCR）
t0 = time.perf_counter()
pages = _extract_pdf(PDF)
t1 = time.perf_counter()
print(f"首次装载: {t1-t0:.1f}s，各页字符数: {[len(p) for p in pages]}")
print("首页 OCR 前 60 字:", pages[0].replace(chr(10), ' / ')[:60])

# 3) 二次装载（缓存）
t0 = time.perf_counter()
pages2 = _extract_pdf(PDF)
t1 = time.perf_counter()
same = pages == pages2
print(f"二次装载: {(t1-t0)*1000:.0f}ms，内容一致: {same}")
print("标记:", ocr_info(PDF))
