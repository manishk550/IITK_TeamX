from __future__ import annotations
from typing import Optional

"""Hybrid lexical and dense retrieval with deterministic reranking."""


import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from finsight.corpus import Passage, load_corpus
from finsight.schemas import Evidence


TOKEN = re.compile(r"[a-z0-9$%]+")
SECTION_BOUNDARY = re.compile(r"(?<=\.)\s+(?=[A-Z])")


def tokenize(text: str) -> list[str]:
    return TOKEN.findall(text.lower())


def chunk_passage(passage: Passage, strategy: str) -> list[str]:
    """Chunk text with one of the two experiment strategies."""
    if strategy == "section":
        if len(passage.text) <= 700:
            return [passage.text]
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
    tokens: list[str]
    hosted: Optional[list[float]] = None


class HybridRetriever:
    """BM25 plus a normalized term-frequency vector and a lexical reranker.

    The dense score is cosine similarity over token counts, so the experiment
    runs without an embeddings endpoint. A hosted embedding model can replace
    `embed` without changing the retrieval contract.
    """

    def __init__(self, passages: Optional[list[Passage]] = None, strategy: str = "section"):
        self.strategy = strategy
        self.chunks = self._index(passages or load_corpus())
        self._attach_hosted_embeddings()

    def _index(self, passages: list[Passage]) -> list[Chunk]:
        chunks = []
        for passage in passages:
            for text in chunk_passage(passage, self.strategy):
                tokens = tokenize(text)
                chunks.append(Chunk(passage, text, self.embed(text), tokens))
        self._df = Counter()
        for chunk in chunks:
            for token in set(chunk.tokens):
                self._df[token] += 1
        self._average_length = sum(len(chunk.tokens) for chunk in chunks) / max(len(chunks), 1)
        return chunks

    def _attach_hosted_embeddings(self) -> None:
        """Use the embeddings endpoint when FINSIGHT_EMBEDDING_MODEL is set.

        Vectors are cached on disk. A missing model, or a failed call, leaves the
        local token vectors in place so answers stay reproducible.
        """
        try:
            import hashlib
            import json
            from finsight.llm import embed, load_config
            model = load_config().embedding_model
            if not model:
                return
            cache_path = Path(__file__).resolve().parents[2] / "data" / "corpus" / "hosted_embeddings.json"
            cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
            missing = []
            for chunk in self.chunks:
                key = hashlib.sha256(f"{model}\n{chunk.text}".encode()).hexdigest()
                if key in cache:
                    chunk.hosted = cache[key]
                else:
                    missing.append((key, chunk))
            for start in range(0, len(missing), 64):
                batch = missing[start:start + 64]
                vectors = embed([chunk.text for _key, chunk in batch])
                if not vectors or len(vectors) != len(batch):
                    return
                for (key, chunk), vector in zip(batch, vectors):
                    chunk.hosted = vector
                    cache[key] = vector
            if missing:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(json.dumps(cache))
        except Exception:
            return

    @staticmethod
    def embed(text: str) -> dict[str, float]:
        counts = Counter(tokenize(text))
        norm = math.sqrt(sum(value * value for value in counts.values())) or 1.0
        return {key: value / norm for key, value in counts.items()}

    def search(self, query: str, k: int = 5, company: Optional[str] = None, period: Optional[str] = None, mode: str = "hybrid", use_priority: bool = True) -> list[Evidence]:
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
        query_hosted = self._query_hosted(expanded)
        scored = [(self._score(query_tokens, query_embed, chunk, mode, use_priority, query_hosted), chunk) for chunk in candidates]
        scored.sort(key=lambda item: item[0], reverse=True)
        reranked = sorted(scored[: max(k * 3, k)], key=lambda item: self._rerank(query_tokens, item[1]), reverse=True)
        return [self._evidence(score, chunk) for score, chunk in reranked[:k] if score > 0]

    def _query_hosted(self, text: str) -> Optional[list[float]]:
        if not any(chunk.hosted for chunk in self.chunks):
            return None
        try:
            from finsight.llm import embed
            vectors = embed([text])
        except Exception:
            return None
        if not vectors:
            return None
        return vectors[0]

    def _score(self, query_tokens: list[str], query_embed: dict[str, float], chunk: Chunk, mode: str = "hybrid", use_priority: bool = True, query_hosted: Optional[list[float]] = None) -> float:
        document_tokens = chunk.tokens
        counts = Counter(document_tokens)
        average = self._average_length
        bm25 = 0.0
        for token in set(query_tokens):
            frequency = counts[token]
            if not frequency:
                continue
            document_frequency = self._df.get(token, 0)
            idf = math.log(1 + (len(self.chunks) - document_frequency + 0.5) / (document_frequency + 0.5))
            bm25 += idf * frequency * 2.2 / (frequency + 1.2 * (0.25 + 0.75 * len(document_tokens) / average))
        if query_hosted and chunk.hosted and len(query_hosted) == len(chunk.hosted):
            denom = math.sqrt(sum(value * value for value in query_hosted)) * math.sqrt(sum(value * value for value in chunk.hosted))
            dense = sum(left * right for left, right in zip(query_hosted, chunk.hosted)) / denom if denom else 0.0
        else:
            dense = sum(query_embed.get(token, 0.0) * chunk.dense.get(token, 0.0) for token in query_embed)
        priority = chunk.passage.priority * 12 if use_priority else 0
        if mode == "bm25":
            return bm25 + priority
        if mode == "dense":
            return dense + priority
        return bm25 + dense + priority

    @staticmethod
    def _rerank(query_tokens: list[str], chunk: Chunk) -> float:
        document = set(chunk.tokens)
        overlap = len(set(query_tokens) & document) / max(len(set(query_tokens)), 1)
        exact_bonus = 0.15 if any(token.isdigit() for token in query_tokens) else 0.0
        return overlap + exact_bonus + chunk.passage.priority

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
