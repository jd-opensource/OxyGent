from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger("oxybank.chunking_service")


# ---------------------------------------------------------------------------
# Text extraction per file type
# ---------------------------------------------------------------------------

def _extract_text_docx(file_path: str) -> str:
    """Extract text from a .docx file using python-docx."""
    from docx import Document

    doc = Document(file_path)
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n".join(paragraphs)


def _extract_text_pdf(file_path: str) -> str:
    """Extract text from a .pdf file using PyPDF2."""
    from PyPDF2 import PdfReader

    reader = PdfReader(file_path)
    pages_text: list[str] = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages_text.append(text)
    return "\n".join(pages_text)


def _extract_text_plain(file_path: str) -> str:
    """Read a plain text or markdown file."""
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


_EXTRACTORS = {
    ".docx": _extract_text_docx,
    ".pdf": _extract_text_pdf,
    ".txt": _extract_text_plain,
    ".md": _extract_text_plain,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def chunk_file(
    file_path: str,
    file_type: str | None = None,
    chunk_size: int = 512,
    chunk_overlap: int = 50,
) -> list[str]:
    """Split a file into text chunks.

    Parameters
    ----------
    file_path : str
        Path to the file on disk.
    file_type : str, optional
        File extension (e.g. ".pdf"). If not provided, it is inferred from the path.
    chunk_size : int
        Target chunk size in characters for the SentenceSplitter.
    chunk_overlap : int
        Overlap between consecutive chunks.

    Returns
    -------
    list[str]
        List of chunk strings.
    """
    if not file_type:
        file_type = Path(file_path).suffix.lower()
    else:
        file_type = file_type.lower()
        if not file_type.startswith("."):
            file_type = f".{file_type}"

    extractor = _EXTRACTORS.get(file_type)
    if extractor is None:
        raise ValueError(
            f"Unsupported file type '{file_type}'. "
            f"Supported types: {', '.join(_EXTRACTORS.keys())}"
        )

    text = extractor(file_path)
    if not text.strip():
        return []

    # Use llama-index SentenceSplitter
    from llama_index.core.node_parser import SentenceSplitter

    splitter = SentenceSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    chunks = splitter.split_text(text)
    logger.info(
        "Chunked file %s (%s) into %d chunks (size=%d, overlap=%d)",
        file_path, file_type, len(chunks), chunk_size, chunk_overlap,
    )
    return chunks
