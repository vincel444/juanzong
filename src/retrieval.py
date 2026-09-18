"""本地资料解析与检索（文本 / PDF / Word）。

设计目标：整卷资料尽量直接塞进 1M 上下文；检索作为内存不足时的兜底召回。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from config import DATA_DIR, INDEX_PATH


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
    """PDF 按页提取文本。"""
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:
            pages.append("")
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
