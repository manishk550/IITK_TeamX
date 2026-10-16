from __future__ import annotations
from typing import Optional

"""Hybrid lexical and dense retrieval with deterministic reranking."""


import math
import re
from collections import Counter
from dataclasses import dataclass

from finsight.corpus import Passage, load_corpus
from finsight.schemas import Evidence


TOKEN = re.compile(r"[a-z0-9$%]+")
SECTION_BOUNDARY = re.compile(r"(?<=\.)\s+(?=[A-Z])")


def tokenize(text: str) -> list[str]:
    return TOKEN.findall(text.lower())


def chunk_passage(passage: Passage, strategy: str) -> list[str]:
    """Chunk text with one of the two experiment strategies."""
    if strategy == "section":
        parts = [part.strip() for part in SECTION_BOUNDARY.split(passage.text) if part.strip()]
        return parts or [passage.text]
    words = passage.text.split()
    size, overlap = 40, 10
    chunks = []
    start = 0
    while start < len(words):
        chunks.append(" ".join(words[start:start + size]))
        if start + size >= len(words):
            break
        start += size - overlap
    return chunks


@dataclass
class Chunk:
    passage: Passage
    text: str
    dense: dict[str, float]


class HybridRetriever:
    """BM25 plus overlap-based dense ranking and a lexical precision reranker.

    The dense component is a hashed embedding so the project is reproducible
    without an external embedding service. A hosted embedding endpoint can
    replace `embed` without changing the retrieval contract.
    """

    def __init__(self, passages: Optional[list[Passage]] = None, strategy: str = "section"):
        self.strategy = strategy
        self.chunks = self._index(passages or load_corpus())

    def _index(self, passages: list[Passage]) -> list[Chunk]:
        chunks = []
        for passage in passages:
            for text in chunk_passage(passage, self.strategy):
                chunks.append(Chunk(passage, text, self.embed(text)))
        return chunks

    @staticmethod
    def embed(text: str) -> dict[str, float]:
        counts = Counter(tokenize(text))
        norm = math.sqrt(sum(value * value for value in counts.values())) or 1.0
        return {key: value / norm for key, value in counts.items()}

    def search(self, query: str, k: int = 5, company: Optional[str] = None, period: Optional[str] = None) -> list[Evidence]:
        candidates = self.chunks
        if company:
            candidates = [chunk for chunk in candidates if company.lower() in chunk.passage.company.lower()]
        if period:
            candidates = [chunk for chunk in candidates if period.lower() in chunk.passage.fiscal_period.lower()]
        expanded = query
        if any(term in query.lower() for term in ("trend", "three-year", "three most recent", "every year")):
            expanded += " comparative income statements revenue net sales fiscal"
        query_tokens = tokenize(expanded)
        query_embed = self.embed(expanded)
        scored = [(self._score(query_tokens, query_embed, chunk), chunk) for chunk in candidates]
        scored.sort(key=lambda item: item[0], reverse=True)
        reranked = sorted(scored[: max(k * 3, k)], key=lambda item: self._rerank(query_tokens, item[1]), reverse=True)
        return [self._evidence(score, chunk) for score, chunk in reranked[:k] if score > 0]

    def _score(self, query_tokens: list[str], query_embed: dict[str, float], chunk: Chunk) -> float:
        document_tokens = tokenize(chunk.text)
        counts = Counter(document_tokens)
        average = sum(len(tokenize(item.text)) for item in self.chunks) / max(len(self.chunks), 1)
        bm25 = 0.0
        for token in set(query_tokens):
            frequency = counts[token]
            if not frequency:
                continue
            document_frequency = sum(token in tokenize(item.text) for item in self.chunks)
            idf = math.log(1 + (len(self.chunks) - document_frequency + 0.5) / (document_frequency + 0.5))
            bm25 += idf * frequency * 2.2 / (frequency + 1.2 * (0.25 + 0.75 * len(document_tokens) / average))
        dense = sum(query_embed.get(token, 0.0) * chunk.dense.get(token, 0.0) for token in query_embed)
        return bm25 + dense

    @staticmethod
    def _rerank(query_tokens: list[str], chunk: Chunk) -> float:
        document = set(tokenize(chunk.text))
        overlap = len(set(query_tokens) & document) / max(len(set(query_tokens)), 1)
        exact_bonus = 0.15 if any(token.isdigit() for token in query_tokens) else 0.0
        return overlap + exact_bonus

    @staticmethod
    def _evidence(score: float, chunk: Chunk) -> Evidence:
        passage = chunk.passage
        return Evidence(
            document_id=passage.document_id,
            company=passage.company,
            fiscal_period=passage.fiscal_period,
            page=passage.page,
            section=passage.section,
            excerpt=chunk.text,
            score=round(score, 4),
        )
