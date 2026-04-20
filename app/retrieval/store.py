"""Hybrid BM25 + dense retrieval store with reciprocal-rank fusion.

In-process, no external services. Dense index uses cosine similarity over the
embedding adapter's vectors.
"""
from __future__ import annotations

import math
import re
from collections.abc import Iterable
from pathlib import Path

from rank_bm25 import BM25Okapi

from ..adapters import EmbeddingAdapter, build_embedding_adapter
from ..config import ModelRole
from .chunker import Chunk, chunk_text_file

_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9\-']+")


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN.findall(text)]


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    s = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return s / (na * nb)


class RetrievalStore:
    def __init__(self, chunks: list[Chunk], embedder: EmbeddingAdapter) -> None:
        self.chunks = chunks
        self.embedder = embedder
        self._tokens = [_tokenize(c.text) for c in chunks]
        self._bm25 = BM25Okapi(self._tokens) if chunks else None
        self._embeddings: list[list[float]] = []
        if chunks:
            resp = embedder.embed([c.text for c in chunks])
            self._embeddings = resp.vectors

    def _bm25_scores(self, query: str) -> list[float]:
        if not self._bm25:
            return []
        return list(self._bm25.get_scores(_tokenize(query)))

    def _dense_scores(self, query: str) -> list[float]:
        if not self._embeddings:
            return []
        qv = self.embedder.embed([query]).vectors[0]
        return [_cosine(qv, v) for v in self._embeddings]

    def search(
        self,
        query: str,
        *,
        k: int = 10,
        bm25_weight: float = 0.5,
        chapter_ids: Iterable[str] | None = None,
        source_types: Iterable[str] | None = None,
    ) -> list[tuple[Chunk, float]]:
        """Return top-k chunks with fused scores using reciprocal-rank fusion."""
        if not self.chunks:
            return []
        bm = self._bm25_scores(query)
        de = self._dense_scores(query)
        # Normalize each score list to [0,1] then fuse.

        def _norm(xs: list[float]) -> list[float]:
            if not xs:
                return []
            mn = min(xs)
            mx = max(xs)
            rng = mx - mn or 1.0
            return [(x - mn) / rng for x in xs]

        bmn = _norm(bm)
        den = _norm(de)
        fused = [bm25_weight * b + (1 - bm25_weight) * d for b, d in zip(bmn, den, strict=False)]
        order = sorted(range(len(fused)), key=lambda i: fused[i], reverse=True)
        allow_ch = set(chapter_ids) if chapter_ids is not None else None
        allow_st = set(source_types) if source_types is not None else None
        out: list[tuple[Chunk, float]] = []
        for idx in order:
            c = self.chunks[idx]
            if allow_ch and c.chapter_id not in allow_ch:
                continue
            if allow_st and c.source_type not in allow_st:
                continue
            out.append((c, fused[idx]))
            if len(out) >= k:
                break
        return out


def build_store(
    *,
    chapter_sources_dir: str | Path,
    markschemes_dir: str | Path | None,
    chapters: list[dict],
    embeddings_model: ModelRole,
) -> RetrievalStore:
    """Build a retrieval store by chunking every file under the given dirs.

    `chapters` is a list of ChapterSpec-like dicts. Files are mapped to chapters
    by filename-stem match against chapter ids / titles / aliases.
    """
    chapter_sources_dir = Path(chapter_sources_dir)
    chunks: list[Chunk] = []

    def _match_chapter_id(stem: str) -> str:
        s = stem.lower().replace("-", "_")
        for ch in chapters:
            candidates = [ch["chapter_id"].lower()]
            candidates += [a.lower() for a in ch.get("aliases", []) + [ch.get("title", "")]]
            if any(s == c or s in c or c in s for c in candidates if c):
                return ch["chapter_id"]
        return f"ch_{stem.lower()}"

    if chapter_sources_dir.exists():
        for p in sorted(chapter_sources_dir.iterdir()):
            if not p.is_file():
                continue
            if p.suffix.lower() not in (".md", ".txt"):
                continue
            chapter_id = _match_chapter_id(p.stem)
            chunks.extend(
                chunk_text_file(path=p, chapter_id=chapter_id, source_type="textbook")
            )

    if markschemes_dir is not None:
        mdir = Path(markschemes_dir)
        if mdir.exists():
            for p in sorted(mdir.iterdir()):
                if not p.is_file():
                    continue
                if p.suffix.lower() not in (".md", ".txt"):
                    continue
                chapter_id = _match_chapter_id(p.stem)
                chunks.extend(
                    chunk_text_file(path=p, chapter_id=chapter_id, source_type="markscheme")
                )

    embedder = build_embedding_adapter(embeddings_model.provider, embeddings_model.model)
    return RetrievalStore(chunks, embedder)
