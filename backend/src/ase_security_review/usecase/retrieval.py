"""Hybrid retrieval: multi-query vector search fused with BM25 keyword search
via Reciprocal Rank Fusion (RRF)."""

from __future__ import annotations

import re
from collections import defaultdict

from rank_bm25 import BM25Okapi

from ..config.settings import AppConfig
from ..domain.enums import DocType
from ..domain.models import RetrievedChunk
from ..repository.base import LlmPort, VectorRepository

_RRF_K = 60
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall(text.lower()) if len(t) > 1]


class RetrievalService:
    def __init__(self, config: AppConfig, vectors: VectorRepository, llm: LlmPort):
        self._config = config
        self._vectors = vectors
        self._llm = llm

    def query(
        self,
        queries: list[str],
        top_k: int | None = None,
        doc_types: list[DocType] | None = None,
    ) -> list[RetrievedChunk]:
        top_k = top_k or self._config.retrieval_top_k
        queries = [q for q in queries if q and q.strip()]
        if not queries:
            return []

        ranked: dict[str, list[int]] = defaultdict(list)  # chunk_id -> ranks per source

        # 1) vector search per query
        for q in queries:
            [embedding] = self._llm.embed([q])
            hits = self._vectors.search(embedding, top_k=max(top_k * 4, 10), doc_types=doc_types)
            for rank, hit in enumerate(hits):
                ranked[hit.chunk.id].append(rank + 1)

        # 2) BM25 over the whole corpus
        corpus_chunks = self._vectors.all_chunks(doc_types=doc_types)
        if corpus_chunks:
            tokenized = [tokenize(c.text) for c in corpus_chunks]
            bm25 = BM25Okapi(tokenized)
            for q in queries:
                q_tokens = tokenize(q)
                if not q_tokens:
                    continue
                scores = bm25.get_scores(q_tokens)
                order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
                for rank, idx in enumerate(order[: top_k * 4]):
                    if scores[idx] > 0:
                        ranked[corpus_chunks[idx].id].append(rank + 1)

        # 3) RRF fusion
        by_id = {c.id: c for c in corpus_chunks}
        fused: list[tuple[str, float]] = []
        for chunk_id, ranks in ranked.items():
            score = sum(1.0 / (_RRF_K + r) for r in ranks)
            fused.append((chunk_id, score))
        fused.sort(key=lambda item: item[1], reverse=True)

        results: list[RetrievedChunk] = []
        for chunk_id, score in fused[:top_k]:
            chunk = by_id.get(chunk_id)
            if chunk is None:
                continue
            results.append(
                RetrievedChunk(
                    chunk=chunk,
                    score=round(score, 4),
                    source=chunk.source,
                    doc_type=chunk.doc_type,
                    doc_name=chunk.doc_name,
                )
            )
        return results
