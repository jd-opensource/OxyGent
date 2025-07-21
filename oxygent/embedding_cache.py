import base64
import hashlib
import json
import logging
import os
import pickle

import httpx
import numpy as np
from tqdm import tqdm

from .config import Config

logger = logging.getLogger(__name__)


async def get_embedding(querys):
    """Retrieve L2-normalised embeddings for a batch of input texts.

    The routine wraps an asynchronous HTTP request to the embedding service
    configured in :class:`~config.Config`.  The service is expected to follow
    the Triton-style JSON inference schema and to return base64-encoded NumPy
    arrays.

    Args:
        querys (Sequence[str]): A non-empty list or tuple of UTF-8 strings for
            which to compute embeddings.

    Returns:
        np.ndarray: A 2-D float array of shape *(len(querys), embedding_dim)*
        containing unit-length embedding vectors.

    Raises:
        ValueError: If *querys* is not a list or tuple.
        Exception: Propagates any exception raised during the network call or
            result parsing.
    """
    if not isinstance(querys, (list, tuple)):
        print("input querys must be a list")
        return
    try:
        text_len = len(querys)

        data = {  # Build Triton-style JSON request
            "model_name": "embedding",
            "inputs": [
                {
                    "name": "text",
                    "shape": [text_len],
                    "datatype": "BYTES",
                    "data": querys,
                },
            ],
            "outputs": [{"name": "last_hidden_state_clip"}],
        }
        headers = {"Accept-Encoding": "identity"}

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url=Config.get_vearch_embedding_model_url(), headers=headers, json=data
            )
            result = response.json()

        # ------------------------------------------------------------------
        # The server returns a list whose elements are base64‑encoded strings
        # representing JSON‑serialised NumPy arrays.  We decode, parse, then
        # concatenate them into a single NumPy array before L2‑normalising.
        # ------------------------------------------------------------------

        output = result["outputs"][0]["data"]
        res_lis = []
        for item in output:
            item_output = base64.b64decode(item).decode("utf-8")
            # res_lis.append(np.array(eval(item_output)))
            res_lis.append(np.array(json.loads(item_output)))
        res_lis = np.concatenate(res_lis)

        norms = np.linalg.norm(res_lis, axis=1, keepdims=True)  # Compute L2 norms
        res_lis = res_lis / norms

        return res_lis

    except Exception as e:
        logger.error(e)


class EmbeddingCache:
    """Lightweight, disk‑backed cache for text embeddings.

    The cache stores the MD5 hash of an input string as the key and its
    corresponding embedding vector as the value.  Writing to disk is batched to
    minimise I/O overhead.

    Example:
        >>> async with EmbeddingCache() as cache:
        ...     vec = await cache.get("hello world")
    """

    def __init__(self, save_batch=1000):
        """Create a new cache instance and eagerly load any persisted data.

        Args:
            save_batch (int, optional): Number of *new* embeddings that can
                accumulate before the in‑memory cache is flushed to disk.
                Defaults to ``1000``.
        """
        self.file = os.path.join(Config.get_cache_save_dir(), "cache.pkl")
        self.count = 0
        self.save_batch = save_batch
        self.data = self.load()

    @staticmethod
    def get_md5(key):
        """Return the 32‑character MD5 hex digest for *key*."""
        return hashlib.md5(key.encode("utf-8")).hexdigest()

    def load(self):
        """Load the on‑disk cache if it exists; otherwise, return an empty dict."""
        if not os.path.exists(self.file):
            return dict()
        with open(self.file, "rb") as f:
            return pickle.load(f)

    # TODO: save embeddings
    def save(self):
        """Persist the in‑memory cache to disk (no‑op if nothing new)."""
        if not self.count:
            return
        try:
            with open(self.file, "wb") as f:
                pickle.dump(self.data, f)
            self.count = 0
        except Exception as e:
            logger.error("Failed to save embedding cache", e)

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------

    def is_in(self, key):
        return self.get_md5(key) in self.data

    def set(self, key, value):
        self.data[self.get_md5(key)] = value
        self.count += 1
        if self.count % self.save_batch == 0:
            self.save()
            self.count = 0

    async def get(self, key):
        """Return cached or freshly computed embeddings."""
        if isinstance(key, (list, tuple, set)):
            return await self._get_multiple(key)
        else:
            return await self._get_single(key)

    async def _get_multiple(self, keys):
        feature_list = []
        texts = []

        for k in tqdm(keys, desc="embedding tools"):
            feature = await self._get_or_queue(k, texts)
            if feature is not None:
                feature_list.append(feature)

            # Send queued texts if any
            if len(texts) >= 1:
                features = await self._embed_and_cache(texts)
                feature_list.extend(features)
                texts.clear()

        # Final flush for remaining texts
        if texts:
            features = await self._embed_and_cache(texts)
            feature_list.extend(features)

        return np.array(feature_list)

    async def _get_single(self, key):
        key_md5 = self.get_md5(key)
        if key_md5 in self.data:
            return self.data[key_md5]
        feature = (await get_embedding([key]))[0]
        self.set(key, feature)
        return feature

    async def _get_or_queue(self, key, texts):
        key_md5 = self.get_md5(key)
        if key_md5 in self.data:
            return self.data[key_md5]
        texts.append(key)
        return None

    async def _embed_and_cache(self, texts):
        features = await get_embedding(texts)
        for content, feature in zip(texts, features):
            self.set(content, feature)
        return features

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):  # autosave on exit
        self.save()
