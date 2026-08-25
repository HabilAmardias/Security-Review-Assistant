"""In-memory fakes implementing the repository ports (no DB, no Chroma, no Ollama)."""

from __future__ import annotations

import hashlib
import json
import math

from ase_security_review.domain.enums import DocType
from ase_security_review.domain.models import Chunk, RetrievedChunk
from ase_security_review.repository.base import LlmPort, VectorRepository

DEFAULT_FACTS = {
    "app_name": "Payment Portal",
    "app_type": "web",
    "exposure": "internet-facing",
    "change_scope": "infra_config_change",
    "change_scope_evidence": "No change to business logic or business process.",
    "technologies": ["react", "python"],
    "data_classes": ["payment", "pii"],
    "features": ["authentication", "integration", "internet-facing"],
    "auth_model": "oauth2",
    "roles": ["admin", "user"],
    "key_features": ["payment checkout", "transaction history", "admin dashboard"],
    "integrations": ["payment gateway"],
    "compliance_refs": ["PCI DSS"],
    "nfr_highlights": ["availability 99.9%", "encryption at rest"],
    "summary": "An internet-facing payment portal processing cardholder data with admin roles.",
}

DEFAULT_DECISION = {
    "requires_pentest": True,
    "test_level": "pentest",
    "classification_reason": "Payment portal processing cardholder data; rule R-01 fired; previous review of similar payment app required pentest.",
    "risk_factors": ["cardholder data", "internet-facing", "admin authz"],
    "scope": {
        "in_scope": ["web app", "REST APIs", "auth flows"],
        "out_of_scope": ["infrastructure"],
        "test_methods": ["OWASP ASVS L2", "API scanning", "manual authz testing"],
        "environments": ["staging pre-release"],
        "effort_estimate": "3-5 person-days",
    },
}


def _vec(text: str) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return [b / 255.0 for b in digest[:32]]


class FakeLlm(LlmPort):
    def __init__(self, facts: dict | None = None, decision: dict | None = None):
        self.facts = facts or DEFAULT_FACTS
        self.decision = decision or DEFAULT_DECISION
        self.generate_calls: list[str] = []
        self.embed_calls: list[list[str]] = []

    def generate(self, prompt, system=None, format=None, temperature=None):
        self.generate_calls.append(prompt)
        if system and "security requirements analyst" in system:
            return json.dumps(self.facts)
        return json.dumps(self.decision)

    def embed(self, texts):
        self.embed_calls.append(texts)
        return [_vec(t) for t in texts]

    def list_models(self):
        return ["fake-model"]

    def ping(self):
        return True

    def close(self):
        pass


class InMemoryVectorRepository(VectorRepository):
    def __init__(self):
        self._chunks: dict[str, Chunk] = {}
        self._embs: dict[str, list[float]] = {}

    def upsert_chunks(self, chunks):
        for c in chunks:
            self._chunks[c.id] = c
            if c.embedding:
                self._embs[c.id] = c.embedding

    def delete_document(self, document_id):
        for cid in [k for k, v in self._chunks.items() if v.document_id == document_id]:
            del self._chunks[cid]
            self._embs.pop(cid, None)

    def search(self, query_embedding, top_k, doc_types=None):
        scored = []
        for cid, emb in self._embs.items():
            chunk = self._chunks[cid]
            if doc_types and chunk.doc_type not in doc_types:
                continue
            sim = sum(a * b for a, b in zip(query_embedding, emb))
            scored.append((sim, chunk))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            RetrievedChunk(chunk=chunk, score=max(0.0, sim))
            for sim, chunk in scored[:top_k]
        ]

    def all_chunks(self, doc_types=None):
        if doc_types:
            return [c for c in self._chunks.values() if c.doc_type in doc_types]
        return list(self._chunks.values())

    def count(self):
        return len(self._chunks)

    def reset_collection(self):
        self._chunks.clear()
        self._embs.clear()

    def dimension_matches(self, embedding_dim):
        for emb in self._embs.values():
            if len(emb) != embedding_dim:
                return False
        return True
