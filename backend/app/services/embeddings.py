"""Embedding provider.

Groq does not expose an embeddings endpoint, so embeddings are produced locally:

* ``fastembed`` — ONNX port of sentence-transformers/all-MiniLM-L6-v2 (384 dims).
  Real semantic embeddings, no API key, ~90 MB one-off model download.
* ``hash`` — deterministic lexical hashing embedder used as a zero-download
  fallback. It matches on token overlap rather than meaning, and is reported as
  such in document metadata.

The provider is chosen once per process so indexing and querying always use the
same model and preprocessing.
"""
from __future__ import annotations

import hashlib
import math
import re
import threading

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9]+")


class HashEmbedder:
    """Deterministic bag-of-ngrams hashing embedder (fallback only)."""

    name = "hash-ngram-v1"

    def __init__(self, dim: int) -> None:
        self.dim = dim

    def _tokens(self, text: str) -> list[str]:
        words = _TOKEN_RE.findall(text.lower())
        tokens = list(words)
        tokens.extend(f"{a}_{b}" for a, b in zip(words, words[1:]))
        return tokens

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            vec = [0.0] * self.dim
            for token in self._tokens(text):
                digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
                bucket = int.from_bytes(digest[:4], "big") % self.dim
                sign = 1.0 if digest[4] % 2 == 0 else -1.0
                vec[bucket] += sign * (1.0 + math.log(1 + len(token)))
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            vectors.append([v / norm for v in vec])
        return vectors


class FastEmbedEmbedder:
    name = "fastembed:" + settings.embedding_model

    def __init__(self) -> None:
        from fastembed import TextEmbedding

        self._model = TextEmbedding(model_name=settings.embedding_model)

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[float(x) for x in vec] for vec in self._model.embed(texts)]


_lock = threading.Lock()
_embedder = None


def _build_embedder():
    provider = settings.embedding_provider.lower()
    if provider in {"auto", "fastembed"}:
        try:
            embedder = FastEmbedEmbedder()
            logger.info("Embeddings: %s", embedder.name)
            return embedder
        except Exception as exc:  # pragma: no cover - depends on local install
            if provider == "fastembed":
                raise RuntimeError(
                    "EMBEDDING_PROVIDER=fastembed but the model could not be loaded. "
                    "Install fastembed or set EMBEDDING_PROVIDER=hash."
                ) from exc
            logger.warning("fastembed unavailable (%s); using hashing embedder", exc)
    embedder = HashEmbedder(settings.embedding_dim)
    logger.info("Embeddings: %s", embedder.name)
    return embedder


def get_embedder():
    global _embedder
    if _embedder is None:
        with _lock:
            if _embedder is None:
                _embedder = _build_embedder()
    return _embedder


def embedding_model_name() -> str:
    return getattr(get_embedder(), "name", "unknown")


def embed_texts(texts: list[str], batch_size: int = 32) -> list[list[float]]:
    """Embed a list of texts in batches."""
    embedder = get_embedder()
    vectors: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        vectors.extend(embedder.embed(texts[start : start + batch_size]))
    return vectors


def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]
