"""Chroma-backed vector repository (embedded mode, on-disk)."""

from __future__ import annotations

from pathlib import Path

import chromadb
from chromadb.api.models.Collection import Collection

from ..domain.enums import DocType
from ..domain.models import Chunk, RetrievedChunk
from ..repository.base import VectorRepository

_COLLECTION = "security_docs"


class ChromaVectorRepository(VectorRepository):
    def __init__(self, chroma_dir: Path, embedding_dim: int = 1024):
        chroma_dir.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(chroma_dir))
        self._embedding_dim = embedding_dim
        self._collection: Collection = self._get_or_create(embedding_dim)

    def _get_or_create(self, embedding_dim: int) -> Collection:
        return self._client.get_or_create_collection(
            name=_COLLECTION,
            metadata={"hnsw:space": "cosine", "embedding_dim": embedding_dim},
        )

    def reset_collection(self) -> None:
        """Delete and recreate the collection with a fresh index. Needed when the
        embedding model (and thus the vector dimension) changes: Chroma pins a
        collection's dimension at creation and rejects vectors of any other size."""
        try:
            self._client.delete_collection(_COLLECTION)
        except Exception:
            pass
        self._collection = self._get_or_create(self._embedding_dim)

    def dimension_matches(self, embedding_dim: int) -> bool:
        """True if the stored collection uses the given vector dimension."""
        try:
            meta = dict(self._collection.metadata or {})
            if "embedding_dim" in meta:
                return int(meta["embedding_dim"]) == embedding_dim
        except Exception:
            pass
        # legacy collection created before we stored the dimension in metadata:
        # infer it from a stored vector, if any.
        try:
            got = self._collection.get(limit=1, include=["embeddings"])
            embs = got.get("embeddings")
            if embs is not None and len(embs) > 0:
                return len(embs[0]) == embedding_dim
        except Exception:
            pass
        # Unknown (legacy empty collection's dimension is still pinned by its
        # index) -> safest to rebuild.
        return False

    def upsert_chunks(self, chunks: list[Chunk]) -> None:
        if not chunks:
            return
        embedded = [c for c in chunks if c.embedding]
        plain = [c for c in chunks if not c.embedding]
        if embedded:
            self._collection.upsert(
                ids=[c.id for c in embedded],
                documents=[c.text for c in embedded],
                embeddings=[c.embedding for c in embedded],
                metadatas=[self._meta(c) for c in embedded],
            )
        if plain:
            self._collection.upsert(
                ids=[c.id for c in plain],
                documents=[c.text for c in plain],
                metadatas=[self._meta(c) for c in plain],
            )

    @staticmethod
    def _meta(c: Chunk) -> dict:
        return {
            "document_id": c.document_id,
            "doc_name": c.doc_name,
            "doc_type": c.doc_type.value,
            "chunk_index": c.chunk_index,
            "source": c.source,
        }

    def delete_document(self, document_id: str) -> None:
        try:
            self._collection.delete(where={"document_id": document_id})
        except Exception:
            # chroma raises if no records match; ignore
            pass

    def search(
        self,
        query_embedding: list[float],
        top_k: int,
        doc_types: list[DocType] | None = None,
    ) -> list[RetrievedChunk]:
        where = {"doc_type": {"$in": [d.value for d in doc_types]}} if doc_types else None
        result = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        out: list[RetrievedChunk] = []
        ids = (result.get("ids") or [[]])[0]
        docs = (result.get("documents") or [[]])[0]
        metas = (result.get("metadatas") or [[]])[0]
        dists = (result.get("distances") or [[]])[0]
        for i, cid in enumerate(ids):
            meta = metas[i] or {}
            score = 1.0 - dists[i] if i < len(dists) else 0.0
            out.append(
                RetrievedChunk(
                    chunk=Chunk(
                        id=cid,
                        document_id=meta.get("document_id", ""),
                        doc_type=DocType(meta.get("doc_type", "sop")),
                        doc_name=meta.get("doc_name", ""),
                        text=docs[i],
                        chunk_index=int(meta.get("chunk_index", 0)),
                        source=meta.get("source", ""),
                    ),
                    score=max(0.0, score),
                    source=meta.get("source", ""),
                    doc_type=DocType(meta.get("doc_type", "sop")),
                    doc_name=meta.get("doc_name", ""),
                )
            )
        return out

    def all_chunks(self, doc_types: list[DocType] | None = None) -> list[Chunk]:
        where = {"doc_type": {"$in": [d.value for d in doc_types]}} if doc_types else None
        offset = 0
        limit = 500
        chunks: list[Chunk] = []
        while True:
            batch = self._collection.get(where=where, limit=limit, offset=offset, include=["documents", "metadatas"])
            ids = batch.get("ids") or []
            if not ids:
                break
            for i, cid in enumerate(ids):
                meta = (batch.get("metadatas") or [])[i] or {}
                chunks.append(
                    Chunk(
                        id=cid,
                        document_id=meta.get("document_id", ""),
                        doc_type=DocType(meta.get("doc_type", "sop")),
                        doc_name=meta.get("doc_name", ""),
                        text=(batch.get("documents") or [])[i],
                        chunk_index=int(meta.get("chunk_index", 0)),
                        source=meta.get("source", ""),
                    )
                )
            offset += limit
            if len(ids) < limit:
                break
        return chunks

    def count(self) -> int:
        return self._collection.count()
