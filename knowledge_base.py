"""建筑规范知识库：支持本地 PDF / Word / Markdown / TXT 检索。"""
from __future__ import annotations

import os
import re
from pathlib import Path

from langchain.tools import tool

KNOWLEDGE_DIR = Path(os.getenv("KNOWLEDGE_DIR", "knowledge"))
_SUPPORTED_SUFFIXES = {".md", ".txt", ".pdf", ".docx"}
_CHUNK_SIZE = 800
_CHUNK_OVERLAP = 120
_TOP_K = 3

_index_cache: dict = {"key": None, "chunks": []}


def _chunk_text(text: str, size: int = _CHUNK_SIZE, overlap: int = _CHUNK_OVERLAP) -> list[str]:
    """按固定窗口切分文本，重叠部分避免切断语义。"""
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= size:
        return [text] if text else []

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = end - overlap
    return chunks


def _extract_text(path: Path) -> list[tuple[str, str]]:
    """按文件类型提取文本，返回 (来源描述, 文本) 列表。"""
    suffix = path.suffix.lower()
    if suffix in {".md", ".txt"}:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(encoding="gbk", errors="ignore")
        return [(path.name, text)]

    if suffix == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        pages = []
        for index, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            if text.strip():
                pages.append((f"{path.name} 第{index}页", text))
        return pages

    if suffix == ".docx":
        from docx import Document

        doc = Document(str(path))
        text = "\n".join(paragraph.text for paragraph in doc.paragraphs)
        return [(path.name, text)]

    return []


def _index_key() -> tuple:
    """用文件路径、修改时间和大小作为索引缓存 key。"""
    if not KNOWLEDGE_DIR.exists():
        return ()
    return tuple(
        (
            str(path.relative_to(KNOWLEDGE_DIR)),
            path.stat().st_mtime_ns,
            path.stat().st_size,
        )
        for path in sorted(KNOWLEDGE_DIR.rglob("*"))
        if path.is_file() and path.suffix.lower() in _SUPPORTED_SUFFIXES
    )


def _build_index() -> list[dict]:
    """惰性构建文档分块索引，文件变化后自动重建。"""
    key = _index_key()
    if key == _index_cache["key"]:
        return _index_cache["chunks"]

    chunks: list[dict] = []
    for path in sorted(KNOWLEDGE_DIR.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in _SUPPORTED_SUFFIXES:
            continue
        for source, text in _extract_text(path):
            for part in _chunk_text(text):
                if part:
                    chunks.append({"source": source, "text": part})

    _index_cache["key"] = key
    _index_cache["chunks"] = chunks
    return chunks


def _tokenize(text: str) -> list[str]:
    """英文按单词、中文按单字切分，适合规范条文检索。"""
    return re.findall(r"[a-zA-Z0-9]+|[\u4e00-\u9fff]", text.lower())


def get_knowledge_file_count() -> int:
    """返回知识库中的规范文件数量，用于页面状态展示。"""
    if not KNOWLEDGE_DIR.exists():
        return 0
    return sum(
        1
        for path in KNOWLEDGE_DIR.rglob("*")
        if path.is_file() and path.suffix.lower() in _SUPPORTED_SUFFIXES
    )


@tool
def search_building_code(query: str) -> str:
    """从本地建筑规范知识库检索相关条文。参数 query 是问题或关键词，例如“楼梯踏步高度”或“住宅层高”。"""
    chunks = _build_index()
    if not chunks:
        return (
            "知识库为空。请把建筑规范 PDF、Word、Markdown 或 TXT 文件放入 knowledge/ 目录后重试。"
            "在没有规范依据时，不要编造条文编号或强制条款。"
        )

    query_terms = _tokenize(query)
    scored = []
    for chunk in chunks:
        score = sum(chunk["text"].lower().count(term) for term in query_terms)
        if score > 0:
            scored.append((score, chunk))
    scored.sort(key=lambda item: item[0], reverse=True)

    if not scored:
        return f"未在知识库中找到与“{query}”相关的内容，请确认规范文件已放入 knowledge/ 目录。"

    lines = [f"找到以下规范依据（共 {min(len(scored), _TOP_K)} 条）："]
    for _, chunk in scored[:_TOP_K]:
        snippet = chunk["text"][:600].replace("\n", " ")
        lines.append(f"- 来源：{chunk['source']}\n  {snippet}")
    return "\n\n".join(lines)
