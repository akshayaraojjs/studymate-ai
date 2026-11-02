"""Token-aware chunking that preserves page numbers and section headings."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

_HEADING_PATTERNS = [
    re.compile(r"^(chapter|unit|section|part|module|lesson|topic)\s+[\divxlc]+\b.*$", re.IGNORECASE),
    re.compile(r"^\d+(\.\d+){0,3}\s+[A-Z][^\n]{0,90}$"),
]
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


@dataclass
class PageText:
    page_number: int
    text: str


@dataclass
class TextChunk:
    content: str
    page_number: int
    section_title: str | None
    chunk_index: int
    token_count: int


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 characters per token) without a tokenizer."""
    return max(1, math.ceil(len(text) / 4))


def clean_text(text: str) -> str:
    """Normalise whitespace while preserving paragraph and list structure."""
    text = text.replace("\x00", " ")
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[\u00ad\u200b\ufeff]", "", text)
    # Re-join words hyphenated across line breaks.
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def looks_like_heading(line: str) -> bool:
    line = line.strip()
    if not 2 <= len(line) <= 90:
        return False
    if any(pattern.match(line) for pattern in _HEADING_PATTERNS):
        return True
    words = line.split()
    if not words or len(words) > 10:
        return False
    if line.endswith((".", ",", ";", "?", "!")):
        return False
    if line.isupper():
        return True
    capitalised = sum(1 for w in words if w[:1].isalpha() and w[:1].isupper())
    return capitalised >= max(2, len(words) - 1)


def _iter_blocks(text: str) -> list[str]:
    """Split page text into blocks, promoting heading lines to standalone blocks.

    PDF extraction often returns a heading and its body in one block, so heading
    detection must work line by line rather than on the whole paragraph.
    """
    blocks: list[str] = []
    current: list[str] = []

    def flush_current() -> None:
        if current:
            blocks.append("\n".join(current).strip())
            current.clear()

    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line:
            flush_current()
            continue
        if len(line) <= 120 and looks_like_heading(line):
            flush_current()
            blocks.append(line)
            continue
        current.append(line)
    flush_current()
    return [block for block in blocks if block]


def _split_oversized_block(block: str, max_tokens: int) -> list[str]:
    sentences = _SENTENCE_SPLIT.split(block)
    pieces: list[str] = []
    current = ""
    for sentence in sentences:
        candidate = f"{current} {sentence}".strip() if current else sentence
        if estimate_tokens(candidate) > max_tokens and current:
            pieces.append(current)
            current = sentence
        else:
            current = candidate
    if current:
        pieces.append(current)

    # Hard-split any remaining oversized piece.
    result: list[str] = []
    max_chars = max_tokens * 4
    for piece in pieces:
        if len(piece) <= max_chars:
            result.append(piece)
            continue
        for start in range(0, len(piece), max_chars):
            result.append(piece[start : start + max_chars])
    return [p.strip() for p in result if p.strip()]


def chunk_pages(
    pages: list[PageText],
    chunk_size_tokens: int = 700,
    overlap_tokens: int = 100,
) -> list[TextChunk]:
    """Split extracted pages into overlapping chunks with source metadata."""
    size = max(200, chunk_size_tokens)
    overlap = max(0, min(overlap_tokens, size // 2))

    chunks: list[TextChunk] = []
    buffer: list[tuple[int, str]] = []
    buffer_tokens = 0
    buffer_section: str | None = None
    current_section: str | None = None

    def flush(next_section: str | None) -> None:
        """Close the current buffer, optionally carrying overlap into the next one."""
        nonlocal buffer, buffer_tokens, buffer_section
        if not buffer:
            return
        content = "\n\n".join(block for _, block in buffer).strip()
        if content:
            chunks.append(
                TextChunk(
                    content=content,
                    page_number=buffer[0][0],
                    section_title=buffer_section,
                    chunk_index=len(chunks),
                    token_count=estimate_tokens(content),
                )
            )
        if next_section != buffer_section:
            buffer, buffer_tokens = [], 0
            return

        carry: list[tuple[int, str]] = []
        carried_tokens = 0
        for page_number, block in reversed(buffer):
            block_tokens = estimate_tokens(block)
            if carried_tokens + block_tokens > overlap:
                break
            carry.insert(0, (page_number, block))
            carried_tokens += block_tokens

        if not carry and overlap > 0:
            # A single block larger than the overlap budget: carry its tail so the
            # next chunk still shares context across the boundary.
            page_number, last_block = buffer[-1]
            tail = last_block[-(overlap * 4) :]
            space = tail.find(" ")
            if space != -1:
                tail = tail[space + 1 :]
            tail = tail.lstrip()
            if tail:
                carry = [(page_number, tail)]
                carried_tokens = estimate_tokens(tail)

        buffer = carry
        buffer_tokens = carried_tokens

    for page in pages:
        for raw_block in _iter_blocks(page.text):
            if looks_like_heading(raw_block) and "\n" not in raw_block:
                heading = raw_block.strip()
                flush(next_section=heading)
                current_section = heading
                buffer_section = current_section
                buffer = [(page.page_number, heading)]
                buffer_tokens = estimate_tokens(heading)
                continue

            if buffer_section is None:
                buffer_section = current_section

            for piece in _split_oversized_block(raw_block, size):
                piece_tokens = estimate_tokens(piece)
                if buffer and buffer_tokens + piece_tokens > size:
                    flush(next_section=buffer_section)
                if not buffer:
                    buffer_section = current_section
                buffer.append((page.page_number, piece))
                buffer_tokens += piece_tokens

    content = "\n\n".join(block for _, block in buffer).strip()
    if content:
        chunks.append(
            TextChunk(
                content=content,
                page_number=buffer[0][0],
                section_title=buffer_section,
                chunk_index=len(chunks),
                token_count=estimate_tokens(content),
            )
        )
    return chunks
