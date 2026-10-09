"""Bounded AvalAI embedding requests; no local model loading or import-time calls."""
from __future__ import annotations
import threading
import time

import httpx
import numpy as np
from pydantic import SecretStr


class AvalAIEmbeddings:
    document_prefix = query_prefix = ""

    def __init__(self, config, api_key=None, *, transport=None):
        self.config = config
        self.model_id, self.revision = config.embedding_model, config.embedding_revision
        self.dimension, self.max_tokens = config.embedding_dimension, config.embedding_max_tokens
        self.endpoint = config.embedding_base_url.rstrip("/") + "/embeddings"
        self._api_key = SecretStr(api_key) if isinstance(api_key, str) else api_key
        self._transport, self._tokenizer = transport, None
        self._lock = threading.RLock()
        self.requests = self.prompt_tokens = 0

    def count_tokens(self, text):
        from retrieval import EmbeddingUnavailable
        with self._lock:
            if self._tokenizer is None:
                try:
                    import tiktoken
                    self._tokenizer = tiktoken.get_encoding("cl100k_base")
                except Exception:
                    raise EmbeddingUnavailable("Embedding tokenizer unavailable; install tiktoken or prepare its vocabulary cache.") from None
        return len(self._tokenizer.encode(text, disallowed_special=()))

    def encode(self, texts, *, query=False):
        from retrieval import EmbeddingUnavailable
        if not self._api_key:
            raise EmbeddingUnavailable("AvalAI embedding key missing; set AVALAI_API_KEY or TUTOR_EMBEDDING_API_KEY.")
        if not texts:
            return np.empty((0, self.dimension), dtype=np.float32)
        if len(texts) > 32768 or any(not isinstance(text, str) or not text.strip() for text in texts):
            raise EmbeddingUnavailable("Embedding inputs must be nonempty bounded text records.")
        counts = [self.count_tokens(text) for text in texts]
        if any(count > self.max_tokens for count in counts):
            raise EmbeddingUnavailable("A complete embedding input exceeds the token limit; no text was truncated.")
        # Bound both number of inputs and aggregate tokens per request. All
        # batches share one deadline; raw provider errors/headers are never shown.
        batches, current, tokens = [], [], 0
        for text, count in zip(texts, counts):
            if current and (len(current) >= 32 or tokens + count > 32000):
                batches.append(current)
                current, tokens = [], 0
            current.append(text)
            tokens += count
        if current:
            batches.append(current)
        deadline = time.monotonic() + self.config.limits.request_timeout_seconds
        vectors = []
        try:
            with httpx.Client(transport=self._transport, follow_redirects=False) as client:
                for batch in batches:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise EmbeddingUnavailable("AvalAI embedding deadline exceeded.")
                    response = client.post(self.endpoint, headers={"Authorization": "Bearer " + self._api_key.get_secret_value()},
                        json={"model": self.model_id, "input": batch, "encoding_format": "float", "dimensions": self.dimension}, timeout=remaining)
                    if response.status_code != 200:
                        raise EmbeddingUnavailable(f"AvalAI embeddings returned HTTP {response.status_code}; check key, credits, model access or service availability.")
                    if len(response.content) > 16_000_000:
                        raise EmbeddingUnavailable("Embedding response exceeds the size budget.")
                    payload = response.json()
                    if payload.get("model", self.model_id) != self.model_id:
                        raise EmbeddingUnavailable("Provider embedding model does not match the selected model.")
                    rows = payload["data"]
                    if len(rows) != len(batch):
                        raise EmbeddingUnavailable("Embedding response omitted or duplicated input records.")
                    ordered = [None] * len(batch)
                    for row in rows:
                        index = row["index"]
                        if type(index) is not int or not 0 <= index < len(batch) or ordered[index] is not None:
                            raise EmbeddingUnavailable("Embedding response indexes are invalid or duplicated.")
                        values = row["embedding"]
                        if not isinstance(values, list) or len(values) != self.dimension or any(type(v) not in {int, float} for v in values):
                            raise EmbeddingUnavailable("Embedding response dimension or numeric values are invalid.")
                        ordered[index] = values
                    array = np.asarray(ordered, dtype=np.float32)
                    norms = np.linalg.norm(array, axis=1, keepdims=True)
                    if not np.isfinite(array).all() or not np.isfinite(norms).all() or np.any(norms <= 0):
                        raise EmbeddingUnavailable("Embedding response contains nonfinite or zero vectors.")
                    vectors.extend(array / norms)
                    with self._lock:
                        self.requests += 1
                        usage = payload.get("usage", {}).get("prompt_tokens", 0)
                        if type(usage) is int and usage >= 0:
                            self.prompt_tokens += usage
        except EmbeddingUnavailable:
            raise
        except (httpx.HTTPError, OSError):
            raise EmbeddingUnavailable("AvalAI embedding connection failed or timed out.") from None
        except Exception:
            raise EmbeddingUnavailable("AvalAI embedding response is malformed; no successful vectors were recorded.") from None
        return np.asarray(vectors, dtype=np.float32)
