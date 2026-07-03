from __future__ import annotations

import base64
import json
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor

import numpy as np


class Embedder(ABC):
    @abstractmethod
    def encode(self, texts: list[str]) -> np.ndarray:
        """Return L2-normalized float32 array of shape (n, dim)."""

    @abstractmethod
    def get_dimension(self) -> int:
        ...

    def encode_batched(self, texts: list[str], batch_size: int = 64, max_workers: int = 1) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.get_dimension()), dtype="float32")
        if len(texts) <= batch_size:
            return self.encode(texts)
        batches = [texts[i:i + batch_size] for i in range(0, len(texts), batch_size)]
        if max_workers <= 1:
            results = [self.encode(b) for b in batches]
        else:
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                results = list(pool.map(self.encode, batches))
        return np.vstack(results)


class OpenAIEmbedder(Embedder):
    def __init__(self, model_name: str, api_key: str, base_url: str, batch_size: int = 100, max_concurrent: int = 4):
        self._model_name = model_name
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._dim: int | None = None
        self.batch_size = batch_size
        self.max_concurrent = max_concurrent

    def encode(self, texts: list[str]) -> np.ndarray:
        import httpx
        resp = httpx.post(
            f"{self._base_url}/embeddings",
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={"model": self._model_name, "input": texts},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()["data"]
        data.sort(key=lambda d: d["index"])
        vecs = np.array([d["embedding"] for d in data], dtype="float32")
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        np.divide(vecs, norms, out=vecs, where=norms > 0)
        return vecs

    def encode_batched(self, texts: list[str], batch_size: int = 0, max_workers: int = 0) -> np.ndarray:
        return super().encode_batched(texts, batch_size or self.batch_size, max_workers or self.max_concurrent)

    def get_dimension(self) -> int:
        if self._dim is None:
            vec = self.encode(["dim probe"])
            self._dim = vec.shape[1]
        return self._dim


class TritonEmbedder(Embedder):
    def __init__(self, url: str, batch_size: int = 32, max_concurrent: int = 4):
        self._url = url
        self._dim: int | None = None
        self.batch_size = batch_size
        self.max_concurrent = max_concurrent

    def encode(self, texts: list[str]) -> np.ndarray:
        import httpx
        payload = {
            "model_name": "embedding",
            "inputs": [
                {"name": "text", "shape": [len(texts)], "datatype": "BYTES", "data": texts}
            ],
            "outputs": [{"name": "last_hidden_state_clip"}],
        }
        resp = httpx.post(self._url, headers={"Accept-Encoding": "identity"}, json=payload, timeout=120, verify=False)
        resp.raise_for_status()
        result = resp.json()
        output = result["outputs"][0]["data"]
        rows: list[np.ndarray] = []
        for item in output:
            decoded = np.array(json.loads(base64.b64decode(item).decode("utf-8")))
            if decoded.ndim == 1:
                rows.append(decoded)
            elif decoded.ndim == 2:
                for row in decoded:
                    rows.append(row)
            else:
                raise RuntimeError(f"Triton returned vector with unexpected shape {decoded.shape}")
        if not rows:
            return np.zeros((0, self.get_dimension()), dtype="float32")
        dims = {v.shape[0] for v in rows}
        if len(dims) != 1:
            raise RuntimeError(f"Triton returned mixed vector dims: {sorted(dims)}")
        if len(rows) != len(texts):
            raise RuntimeError(f"Triton returned {len(rows)} vectors for {len(texts)} texts")
        mat = np.concatenate(rows).astype("float32")
        if mat.ndim == 1:
            mat = mat.reshape(len(texts), -1)
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        norms[norms == 0] = 1
        mat = mat / norms
        return mat

    def encode_batched(self, texts: list[str], batch_size: int = 0, max_workers: int = 0) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.get_dimension()), dtype="float32")
        bs = batch_size or self.batch_size
        return super().encode_batched(texts, bs, max_workers or self.max_concurrent)

    def get_dimension(self) -> int:
        if self._dim is None:
            vec = self.encode(["dim probe"])
            self._dim = vec.shape[1]
        return self._dim


def create_embedder(backend: str, model: str | None = None, config=None) -> Embedder:
    from app.config import get_config
    cfg = config or get_config()
    if not backend or backend == "triton":
        return TritonEmbedder(cfg.triton.url, cfg.triton.batch_size, cfg.triton.max_concurrent)
    if backend == "openai":
        if not cfg.openai.api_key:
            raise ValueError("OpenAI API key is required")
        return OpenAIEmbedder(
            model or cfg.openai.model,
            cfg.openai.api_key,
            cfg.openai.base_url,
            cfg.openai.batch_size,
            cfg.openai.max_concurrent,
        )
    raise ValueError(f"Unsupported embedding backend '{backend}'. Supported: 'triton' (default), 'openai'.")
