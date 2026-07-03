from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger("oxybank.vearch")


def vearch_space_name(bank_id: str) -> str:
    """Generate a Vearch-safe space name (no hyphens)."""
    return f"bank_{bank_id.replace('-', '_')}"


class VearchClient:
    """Vearch 3.3.x client for space management and vector CRUD."""

    def __init__(self, master_url: str, router_url: str, db_name: str):
        self._master = master_url.rstrip("/")
        self._router = router_url.rstrip("/")
        self._db = db_name
        self._ensure_db()

    def _ensure_db(self):
        try:
            httpx.put(
                f"{self._master}/db/_create",
                json={"name": self._db},
                timeout=10,
            )
        except Exception:
            pass

    def create_space(self, space_name: str, properties: dict, engine: dict | None = None) -> dict:
        engine = engine or {
            "index_size": 70000,
            "id_type": "String",
            "retrieval_type": "FLAT",
            "retrieval_param": {"metric_type": "InnerProduct"},
        }
        space_config = {
            "name": space_name,
            "partition_num": 1,
            "replica_num": 1,
            "engine": engine,
            "properties": properties,
        }
        resp = httpx.put(
            f"{self._master}/space/{self._db}/_create",
            json=space_config,
            timeout=10,
        )
        return resp.json()

    def get_space(self, space_name: str) -> dict | None:
        try:
            resp = httpx.get(
                f"{self._master}/space/{self._db}/{space_name}",
                timeout=10,
            )
            data = resp.json()
            if data.get("msg") == "success":
                return data.get("data", data)
            return None
        except Exception:
            return None

    def delete_space(self, space_name: str) -> bool:
        try:
            resp = httpx.delete(
                f"{self._master}/space/{self._db}/{space_name}",
                timeout=10,
            )
            return resp.json().get("msg") == "success"
        except Exception:
            return False

    def insert(self, space_name: str, doc_id: str, doc: dict) -> dict:
        resp = httpx.post(
            f"{self._router}/{self._db}/{space_name}/{doc_id}",
            json=doc,
            timeout=30,
        )
        return resp.json()

    def bulk_insert(self, space_name: str, docs: list[tuple[str, dict]], refresh: bool = True) -> dict:
        import json as json_mod
        lines = ""
        for doc_id, doc in docs:
            lines += json_mod.dumps({"index": {"_id": doc_id}}) + "\n"
            lines += json_mod.dumps(doc) + "\n"
        url = f"{self._router}/{self._db}/{space_name}/_bulk"
        if refresh:
            url += "?refresh=true"
        resp = httpx.post(url, content=lines, timeout=60)
        return resp.json()

    def delete_doc(self, space_name: str, doc_id: str) -> bool:
        try:
            httpx.delete(
                f"{self._router}/{self._db}/{space_name}/{doc_id}?refresh=true",
                timeout=10,
            )
            return True
        except Exception:
            return False

    def delete_by_query(self, space_name: str, filter_clauses: list[dict]) -> dict:
        query = {"query": {"filter": filter_clauses}}
        try:
            resp = httpx.post(
                f"{self._router}/{self._db}/{space_name}/_delete_by_query",
                json=query,
                timeout=60,
            )
            return resp.json()
        except Exception as e:
            logger.error("delete_by_query failed: %s", e)
            return {}

    def search(
        self,
        space_name: str,
        vector_field: str,
        feature: list[float],
        top_k: int = 10,
        filter_clauses: list[dict] | None = None,
        fields: list[str] | None = None,
    ) -> list[dict]:
        return self.search_multi(
            space_name,
            sum_entries=[{"field": vector_field, "feature": feature}],
            top_k=top_k,
            filter_clauses=filter_clauses,
            fields=fields,
        )

    def search_multi(
        self,
        space_name: str,
        sum_entries: list[dict],
        top_k: int = 10,
        filter_clauses: list[dict] | None = None,
        fields: list[str] | None = None,
    ) -> list[dict]:
        """Multi-vector search: pass N {field, feature} entries, Vearch sums their scores."""
        query: dict = {
            "query": {
                "sum": list(sum_entries),
            },
            "is_brute_search": 1,
            "size": top_k,
        }
        if filter_clauses:
            query["query"]["filter"] = list(filter_clauses)
        if fields:
            query["fields"] = fields
        try:
            resp = httpx.post(
                f"{self._router}/{self._db}/{space_name}/_search",
                json=query,
                timeout=30,
            )
            data = resp.json()
            hits = data.get("hits", {}).get("hits", [])
            results = []
            for h in hits:
                item = {"_id": h["_id"], "_score": h.get("_score", 0)}
                source = h.get("_source", {})
                item.update(source)
                results.append(item)
            return results
        except Exception as e:
            logger.error("Vearch search failed: %s", e)
            return []

    def get_doc(self, space_name: str, doc_id: str) -> dict | None:
        try:
            resp = httpx.get(
                f"{self._router}/{self._db}/{space_name}/{doc_id}",
                timeout=10,
            )
            data = resp.json()
            if data.get("found"):
                return data.get("_source", {})
            return None
        except Exception:
            return None

    def update_doc(self, space_name: str, doc_id: str, fields: dict) -> bool:
        """Update specific fields of a document in Vearch by rewriting the full doc."""
        try:
            doc = self.get_doc(space_name, doc_id)
            if doc is None:
                return False
            doc.pop("_id", None)
            doc.update(fields)
            resp = httpx.post(
                f"{self._router}/{self._db}/{space_name}/{doc_id}",
                json=doc,
                timeout=10,
            )
            return resp.status_code < 400
        except Exception as e:
            logger.error("Vearch update_doc failed for %s: %s", doc_id, e)
            return False
