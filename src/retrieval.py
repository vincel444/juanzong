"""本地资料解析与检索（文本 / PDF / Word / 扫描版 PDF-OCR）。

设计目标：整卷资料尽量直接塞进 1M 上下文；检索作为内存不足时的兜底召回。

扫描版 PDF：pypdf 抽不到文本层的页面（图片型/扫描件）自动走 RapidOCR
（CPU，onnxruntime，不占用推理 GPU），结果按文件哈希缓存到磁盘，
同一份文件只有第一次装载有 OCR 开销。
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
from dataclasses import dataclass
from pathlib import Path

from config import DATA_DIR, INDEX_PATH

# ---- 扫描页 OCR ----
OCR_DIR = INDEX_PATH.parent / "ocr_cache"
_TEXT_FLOOR = 20          # 页规范化文本低于该字符数 → 判定扫描页
_OCR_DPI = 260            # 渲染分辨率：清晰度与速度折中

_ocr_engine = None
_ocr_lock = threading.Lock()


def _get_ocr():
    """RapidOCR 懒加载单例（首次调用约 2~4s 模型初始化）。"""
    global _ocr_engine
    if _ocr_engine is None:
        with _ocr_lock:
            if _ocr_engine is None:
                from rapidocr_onnxruntime import RapidOCR
                _ocr_engine = RapidOCR()
    return _ocr_engine


def _file_key(path: Path) -> str:
    st = path.stat()
    return hashlib.md5(f"{path.name}|{st.st_size}|{st.st_mtime_ns}".encode()).hexdigest()


def _ocr_cache_load(path: Path) -> dict[int, str] | None:
    f = OCR_DIR / f"{_file_key(path)}.json"
    if not f.exists():
        return None
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
        return {int(k): v for k, v in data.get("pages", {}).items()}
    except Exception:
        return None


def _ocr_cache_save(path: Path, pages: dict[int, str]) -> None:
    try:
        OCR_DIR.mkdir(parents=True, exist_ok=True)
        (OCR_DIR / f"{_file_key(path)}.json").write_text(
            json.dumps({"pages": {str(k): v for k, v in pages.items()}},
                       ensure_ascii=False),
            encoding="utf-8")
    except Exception:
        pass  # 缓存失败不阻塞主流程


def _render_page(path: Path, page_no: int):
    """用 PyMuPDF 把指定页渲染成 RGB numpy 数组。"""
    try:
        import pymupdf as fitz
    except ImportError:  # 旧版 PyMuPDF 兼容
        import fitz
    import numpy as np

    with fitz.Document(str(path)) as doc:
        pix = doc[page_no - 1].get_pixmap(dpi=_OCR_DPI)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
            pix.height, pix.width, pix.n)
        return img[:, :, :3] if pix.n == 4 else img


def _ocr_page(path: Path, page_no: int) -> str:
    result, _ = _get_ocr()(_render_page(path, page_no))
    if not result:
        return ""
    return "\n".join(r[1] for r in result)


def ocr_info(path: Path) -> str:
    """资料卡展示用：该 PDF 的文字/扫描状态一句话标记。"""
    cached = _ocr_cache_load(path)
    if cached:
        return f"已 OCR {len(cached)} 页"
    try:
        from pypdf import PdfReader
        t = PdfReader(str(path)).pages[0].extract_text() or ""
        plain = re.sub(r"\s+", "", t)
        return "文字版" if len(plain) >= _TEXT_FLOOR else "扫描版·问答时自动OCR"
    except Exception:
        return "—"


@dataclass
class Chunk:
    doc_name: str
    page: int
    text: str


TEXT_EXTS = {".txt", ".md", ".py", ".java", ".js", ".ts", ".json", ".csv"}
PDF_EXTS = {".pdf"}
DOCX_EXTS = {".docx"}
SUPPORTED_EXTS = TEXT_EXTS | PDF_EXTS | DOCX_EXTS

MAX_CHARS_PER_DOC = 200_000  # 单文档截断保护，防止误放超大文件拖垮装载

# data/ 下同时维护资料清单、问题集和故障模板。它们不是案卷内容，不能
# 进入上下文，否则模型可能把参考答案或元信息误当成原始证据。
EXCLUDED_DIR_NAMES = {
    "questions",
    "question",
    "管理文件",
}
EXCLUDED_FILE_NAMES = {
    "manifest.csv",
    "BUG_TEMPLATE.md",
    "QUESTION_TEMPLATE.md",
    "index.sqlite",
}
EXCLUDED_FILE_NAMES_LOWER = {name.casefold() for name in EXCLUDED_FILE_NAMES}


def scan_documents() -> list[Path]:
    """扫描资料库目录下支持的文件。"""
    if not DATA_DIR.exists():
        return []
    documents: list[Path] = []
    for path in DATA_DIR.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTS:
            continue
        # 只按目录名过滤管理目录；这样 code_qa/ 下开源项目自己的 README
        # 仍可作为代码问答上下文，而 data/README.md 会被排除。
        relative_parts = path.relative_to(DATA_DIR).parts
        if any(part.casefold() in EXCLUDED_DIR_NAMES for part in relative_parts[:-1]):
            continue
        # 根目录说明文件是管理文件；资料子目录中的 README 可能是代码项目
        # 的真实文档，应保留。*_TEMPLATE.md 后缀作为兜底规则，防止未来
        # 新增的模板文件被误当成资料。
        if len(relative_parts) == 1 and (
            path.name.casefold() == "readme.md"
            or path.name.casefold() in EXCLUDED_FILE_NAMES_LOWER
            or path.name.lower().endswith("_template.md")
        ):
            continue
        documents.append(path)
    return sorted(documents)


def _extract_pdf(path: Path) -> list[str]:
    """PDF 按页提取文本。

    文字页走 pypdf 零开销；扫描页（无文本层）自动 RapidOCR（CPU），
    结果按文件哈希缓存 —— 同一份文件只有首次装载有 OCR 时间成本。
    """
    from pypdf import PdfReader

    cached = _ocr_cache_load(path)
    reader = PdfReader(str(path))
    pages: list[str] = []
    ocr_todo: list[int] = []
    for i, page in enumerate(reader.pages, start=1):
        if cached and i in cached:
            pages.append(cached[i])
            continue
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        if len(re.sub(r"\s+", "", text)) >= _TEXT_FLOOR:
            pages.append(text)
        else:
            ocr_todo.append(i)
            pages.append("")  # 占位，OCR 后回填

    if ocr_todo:
        try:
            for i in ocr_todo:
                pages[i - 1] = _ocr_page(path, i)
            merged = dict(cached or {})
            for i in ocr_todo:
                merged[i] = pages[i - 1]
            _ocr_cache_save(path, merged)
        except Exception as e:
            # OCR 失败不阻塞建索引：占位说明，保证其余页可用
            for i in ocr_todo:
                if not pages[i - 1]:
                    pages[i - 1] = f"[第{i}页为扫描页，OCR 失败: {e}]"
    return pages


def _extract_docx(path: Path) -> list[str]:
    """Word 按段落提取。"""
    import docx

    d = docx.Document(str(path))
    text = "\n".join(p.text for p in d.paragraphs)
    return [text]


def _extract_text(path: Path) -> list[str]:
    return [path.read_text(encoding="utf-8", errors="ignore")]


def load_documents() -> list[Chunk]:
    """解析全部资料为带页码的分块。PDF 按页分块，其余按 800 字分块。"""
    chunks: list[Chunk] = []
    for f in scan_documents():
        ext = f.suffix.lower()
        try:
            if ext in PDF_EXTS:
                pages = _extract_pdf(f)
            elif ext in DOCX_EXTS:
                pages = _extract_docx(f)
            else:
                pages = _extract_text(f)
        except Exception as e:  # 单个文件损坏不阻塞整体
            chunks.append(Chunk(doc_name=f.name, page=0, text=f"[解析失败: {e}]"))
            continue
        for page_no, page_text in enumerate(pages, start=1):
            page_text = page_text[:MAX_CHARS_PER_DOC]
            for i in range(0, len(page_text), 800):
                chunks.append(Chunk(doc_name=f.name, page=page_no, text=page_text[i : i + 800]))
    return chunks


def full_context(chunks: list[Chunk], max_chars: int = 400_000) -> str:
    """整卷装载：把全部资料拼进一段上下文（利用 1M token 能力）。
    超过 max_chars 时返回空串，调用方退回检索兜底。"""
    parts = [f"[{c.doc_name} 第{c.page}页]\n{c.text}" for c in chunks]
    joined = "\n\n".join(parts)
    return joined if len(joined) <= max_chars else ""


def retrieve(query: str, top_k: int = 5) -> list[Chunk]:
    """检索兜底：关键词重合度打分（TODO(B-2): 升级为 sqlite-vec 向量 + BM25 混合）。"""
    chunks = load_documents()
    if not chunks:
        return []
    terms = [w for w in query.replace("，", " ").replace("？", " ").split() if w]
    if not terms:
        terms = [query]

    def score(c: Chunk) -> int:
        return sum(c.text.count(t) for t in terms)

    scored = sorted((c for c in chunks if score(c) > 0), key=score, reverse=True)
    return scored[:top_k]


def ensure_index_dir() -> None:
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
