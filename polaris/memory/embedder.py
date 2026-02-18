"""
Ollama Embedder — Local embedding via nomic-embed-text.

Uses the Ollama REST API at http://localhost:11434/api/embeddings.
Falls back gracefully when Ollama is unavailable (semantic search disabled,
keyword search used instead).
"""

import logging
import math
import struct
from typing import List, Optional

import requests

logger = logging.getLogger(__name__)

OLLAMA_EMBED_URL = "http://localhost:11434/api/embeddings"
OLLAMA_EMBED_MODEL = "nomic-embed-text"


class OllamaEmbedder:
    """Generate embeddings via Ollama's local nomic-embed-text model."""

    def __init__(
        self,
        url: str = OLLAMA_EMBED_URL,
        model: str = OLLAMA_EMBED_MODEL,
        timeout: int = 30,
    ):
        self.url = url
        self.model = model
        self.timeout = timeout
        self.available = self._check_availability()

    def _check_availability(self) -> bool:
        """Probe Ollama to see if the embedding model is reachable."""
        try:
            resp = requests.post(
                self.url,
                json={"model": self.model, "prompt": "test"},
                timeout=5,
            )
            if resp.status_code == 200 and "embedding" in resp.json():
                logger.info("OllamaEmbedder: %s is available", self.model)
                return True
        except Exception:
            pass
        logger.warning(
            "OllamaEmbedder: %s not available; semantic search disabled", self.model
        )
        return False

    def embed(self, text: str) -> Optional[List[float]]:
        """Return the embedding vector for *text*, or None on failure."""
        if not self.available:
            return None
        try:
            resp = requests.post(
                self.url,
                json={"model": self.model, "prompt": text},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json()["embedding"]
        except Exception as e:
            logger.error("Embedding failed: %s", e)
            return None

    # ------------------------------------------------------------------
    # Serialisation helpers (embedding <-> BLOB)
    # ------------------------------------------------------------------

    @staticmethod
    def to_bytes(vector: List[float]) -> bytes:
        """Pack a float list into a compact binary BLOB."""
        return struct.pack(f"{len(vector)}f", *vector)

    @staticmethod
    def from_bytes(blob: bytes) -> List[float]:
        """Unpack a binary BLOB back into a float list."""
        n = len(blob) // 4  # 4 bytes per float32
        return list(struct.unpack(f"{n}f", blob))

    # ------------------------------------------------------------------
    # Similarity
    # ------------------------------------------------------------------

    def batch_embed(self, texts: List[str]) -> List[Optional[List[float]]]:
        """Embed multiple texts. Returns a list of vectors (or None for failures)."""
        return [self.embed(t) for t in texts]

    @staticmethod
    def cosine_similarity(a: List[float], b: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)
