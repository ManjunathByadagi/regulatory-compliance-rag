from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import fitz


@dataclass
class PDFPage:
    page_num: int
    text: str


@dataclass
class ParsedDocument:
    title: str
    path: str
    pages: list[PDFPage]
    page_count: int


def parse_pdf(file_path: str) -> ParsedDocument:
    path = Path(file_path)
    pages: list[PDFPage] = []

    doc = fitz.open(file_path)
    try:
        for idx, page in enumerate(doc, start=1):
            text = page.get_text("text") or ""
            pages.append(PDFPage(page_num=idx, text=text.strip()))
    finally:
        doc.close()

    return ParsedDocument(
        title=path.stem,
        path=str(path.resolve()),
        pages=pages,
        page_count=len(pages),
    )
