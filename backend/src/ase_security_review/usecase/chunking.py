"""Hierarchical chunking: split by headings first (EN + ID patterns), then
recursively by paragraph/line on any section that still exceeds the chunk size."""

from __future__ import annotations

import re

# Heading patterns (case-insensitive where appropriate):
#   markdown:   # Title
#   numbered:   1.2.3 Title
#   indo/eng:   BAB/Pasal/CHAPTER/SECTION/ARTICLE  <word>
_HEADING_RE = re.compile(
    r"^\s*(?:"
    r"#{1,6}\s+"
    r"|(\d+(?:\.\d+){0,3})\s+(?=[A-Z0-9])"
    r"|(?:bab|pasal|psl|chapter|section|article)\s+[0-9A-Z]"
    r")",
    re.IGNORECASE,
)


def split_by_headings(text: str) -> list[tuple[str, str]]:
    """Split text into (heading, body) sections. Lines matching a heading pattern
    start a new section; preceding non-heading lines become an intro section."""
    sections: list[tuple[str, str]] = []
    current_heading = ""
    current_lines: list[str] = []

    def flush() -> None:
        body = "\n".join(current_lines).strip()
        if body:
            sections.append((current_heading.strip(), body))

    for line in text.splitlines():
        if _HEADING_RE.match(line):
            flush()
            current_heading = line.strip()
            current_lines = []
        else:
            if not current_heading and not current_lines:
                current_heading = ""
            current_lines.append(line)
    flush()

    if not sections and text.strip():
        sections.append(("", text.strip()))
    return sections


def recursive_split(text: str, chunk_size: int, overlap: int = 0) -> list[str]:
    """Recursively split a single section into chunks not exceeding chunk_size.
    ``overlap`` is accepted for API compatibility but applied once by ``chunk_text``."""
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    idx = -1
    for sep in ("\n\n", "\n", ". ", "; ", ", ", " "):
        pos = text.rfind(sep, 0, chunk_size)
        if pos > 0:
            idx = pos + len(sep)
            break
    if idx <= 0:
        idx = chunk_size

    head = text[:idx].strip()
    rest = text[idx:].strip()
    result = []
    for chunk in ([head] if head else []) + recursive_split(rest, chunk_size):
        if chunk:
            result.append(chunk)
    return result


def _apply_overlap(chunks: list[str], overlap: int) -> list[str]:
    result: list[str] = []
    for chunk in chunks:
        if not chunk:
            continue
        if result and overlap > 0:
            carry = result[-1][-overlap:].strip()
            result.append((carry + "\n" + chunk) if carry else chunk)
        else:
            result.append(chunk)
    return result


def chunk_text(text: str, chunk_size: int = 900, overlap: int = 120) -> list[str]:
    """Full pipeline: normalize whitespace, split by headings, recursively split,
    then apply overlap once across each section's chunks."""
    text = re.sub(r"[ \t]+", " ", text)
    chunks: list[str] = []
    for heading, body in split_by_headings(text):
        full = f"{heading}\n{body}" if heading else body
        pieces = recursive_split(full, chunk_size)
        pieces = _apply_overlap(pieces, overlap)
        for piece in pieces:
            if piece:
                chunks.append(piece)
    return chunks
