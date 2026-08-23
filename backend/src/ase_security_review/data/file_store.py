"""Local filesystem helpers: managed copies, plaintext cache, hashing."""

from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_of_file(path: Path, chunk: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            block = fh.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def save_upload(path: Path, content: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def save_plaintext(dir_path: Path, doc_id: str, text: str) -> Path:
    dir_path.mkdir(parents=True, exist_ok=True)
    out = dir_path / f"{doc_id}.txt"
    out.write_text(text, encoding="utf-8")
    return out


def load_plaintext(path: Path) -> str:
    return path.read_text(encoding="utf-8")
