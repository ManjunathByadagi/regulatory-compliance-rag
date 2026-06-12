from __future__ import annotations

import re
from dataclasses import dataclass


SECTION_RE = re.compile(r"^(section\s+\d+[\.:]|\d+\.\d+|##\s+|chapter\s+\d+)", re.IGNORECASE)


@dataclass
class Chunk:
    chunk_id: str
    text: str
    document: str
    section: str
    page_start: int
    page_end: int


def _split_paragraphs(text: str) -> list[str]:
    parts = [p.strip() for p in text.split("\n\n")]
    return [p for p in parts if p]


def _guess_section(text: str, fallback: str) -> str:
    for line in text.splitlines():
        s = line.strip()
        if SECTION_RE.search(s):
            return s[:120]
    return fallback


def fixed_token_chunks(document: str, page_texts: list[tuple[int, str]], token_size: int) -> list[Chunk]:
    all_words: list[tuple[int, str]] = []
    for page_num, page_text in page_texts:
        words = page_text.split()
        all_words.extend((page_num, w) for w in words)

    chunks: list[Chunk] = []
    i = 0
    chunk_idx = 0
    while i < len(all_words):
        slice_words = all_words[i : i + token_size]
        if not slice_words:
            break
        page_start = slice_words[0][0]
        page_end = slice_words[-1][0]
        text = " ".join(w for _, w in slice_words)
        section = _guess_section(text, "General")
        chunks.append(
            Chunk(
                chunk_id=f"{document}-fixed-{token_size}-{chunk_idx}",
                text=text,
                document=document,
                section=section,
                page_start=page_start,
                page_end=page_end,
            )
        )
        chunk_idx += 1
        i += token_size
    return chunks


def semantic_chunks(document: str, page_texts: list[tuple[int, str]]) -> list[Chunk]:
    chunks: list[Chunk] = []
    idx = 0

    for page_num, page_text in page_texts:
        paragraphs = _split_paragraphs(page_text)
        buffer: list[str] = []
        section = "General"

        for para in paragraphs:
            is_header = bool(SECTION_RE.search(para.splitlines()[0].strip()))
            if is_header and buffer:
                text = "\n\n".join(buffer)
                chunks.append(
                    Chunk(
                        chunk_id=f"{document}-semantic-{idx}",
                        text=text,
                        document=document,
                        section=section,
                        page_start=page_num,
                        page_end=page_num,
                    )
                )
                idx += 1
                buffer = []
            if is_header:
                section = para[:120]
            buffer.append(para)

        if buffer:
            text = "\n\n".join(buffer)
            chunks.append(
                Chunk(
                    chunk_id=f"{document}-semantic-{idx}",
                    text=text,
                    document=document,
                    section=section,
                    page_start=page_num,
                    page_end=page_num,
                )
            )
            idx += 1

    return chunks


def hierarchical_chunks(document: str, page_texts: list[tuple[int, str]]) -> list[Chunk]:
    chunks: list[Chunk] = []
    idx = 0
    current_section = "General"

    for page_num, page_text in page_texts:
        paragraphs = _split_paragraphs(page_text)
        for para in paragraphs:
            first_line = para.splitlines()[0].strip() if para.splitlines() else ""
            if SECTION_RE.search(first_line):
                current_section = first_line[:120]
                continue
            # Keep critical numeric constraints together for compliance values.
            sentences = re.split(r"(?<=[.!?])\s+", para)
            sentence_buffer: list[str] = []
            for sentence in sentences:
                sentence_buffer.append(sentence)
                text = " ".join(sentence_buffer)
                if len(text.split()) >= 120 or any(key in text.lower() for key in ["crar", "%", "capital"]):
                    chunks.append(
                        Chunk(
                            chunk_id=f"{document}-hier-{idx}",
                            text=text.strip(),
                            document=document,
                            section=current_section,
                            page_start=page_num,
                            page_end=page_num,
                        )
                    )
                    idx += 1
                    sentence_buffer = []
            if sentence_buffer:
                chunks.append(
                    Chunk(
                        chunk_id=f"{document}-hier-{idx}",
                        text=" ".join(sentence_buffer).strip(),
                        document=document,
                        section=current_section,
                        page_start=page_num,
                        page_end=page_num,
                    )
                )
                idx += 1
    return chunks


def build_chunks(document: str, page_texts: list[tuple[int, str]], strategy: str) -> list[Chunk]:
    if strategy == "fixed_256":
        return fixed_token_chunks(document, page_texts, 256)
    if strategy == "fixed_512":
        return fixed_token_chunks(document, page_texts, 512)
    if strategy == "fixed_1024":
        return fixed_token_chunks(document, page_texts, 1024)
    if strategy == "semantic":
        return semantic_chunks(document, page_texts)
    return hierarchical_chunks(document, page_texts)
