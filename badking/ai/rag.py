"""RAG ساده و بدون وابستگی — جستجوی متنی روی اسناد (قابل تعویض با vector store)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _normalize(text: str) -> str:
    """نرمال‌سازی فارسی: ی/ک عربی، اعداد فارسی، ZWNJ."""
    text = text.replace("ي", "ی").replace("ك", "ک").replace("\u200c", " ")
    text = re.sub(r"[ًٌٍَُِّْ]", "", text)
    return re.sub(r"\s+", " ", text).strip().lower()


@dataclass
class Chunk:
    text: str
    source: str
    index: int


class SimpleRAG:
    """تقسیم اسناد به chunk و بازیابی بر اساس امتیاز واژه‌ای."""

    def __init__(self, chunk_size: int = 500, overlap: int = 50):
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.chunks: list[Chunk] = []

    def add_text(self, text: str, source: str = "inline") -> None:
        words = _normalize(text).split()
        step = max(1, self.chunk_size - self.overlap)
        for i in range(0, max(1, len(words)), step):
            piece = " ".join(words[i:i + self.chunk_size])
            if piece:
                self.chunks.append(Chunk(piece, source, len(self.chunks)))

    def add_file(self, path: str | Path) -> None:
        p = Path(path)
        self.add_text(p.read_text(encoding="utf-8", errors="ignore"), source=str(p))

    def search(self, query: str, top_k: int = 3) -> list[Chunk]:
        q = set(_normalize(query).split())
        if not q:
            return []
        scored: list[tuple[float, Chunk]] = []
        for chunk in self.chunks:
            words = set(chunk.text.split())
            if not words:
                continue
            score = len(q & words) / len(q)
            if score > 0:
                scored.append((score, chunk))
        scored.sort(key=lambda x: -x[0])
        return [c for _, c in scored[:top_k]]

    def context(self, query: str, top_k: int = 3) -> str:
        return "\n\n".join(c.text for c in self.search(query, top_k))
