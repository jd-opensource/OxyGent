from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

from elasticsearch import Elasticsearch, helpers

logger = logging.getLogger("oxybank.es")

SYSTEM_FIELDS_MAPPING = {
    "sys_sample_id": {"type": "keyword"},
    "sys_document_id": {"type": "keyword"},
    "sys_template": {"type": "keyword"},
    "sys_priority": {"type": "integer"},
    "sys_status": {"type": "keyword"},
    "sys_executor": {"type": "keyword"},
    "sys_overview": {"type": "text"},
    "sys_remarks": {"type": "text"},
    "sys_create_time": {"type": "date"},
    "sys_update_time": {"type": "date"},
}

FIELD_TYPE_MAP = {
    "string": {"type": "keyword"},
    "text": {"type": "text"},
    "integer": {"type": "integer"},
    "float": {"type": "float"},
    "boolean": {"type": "boolean"},
    "date": {"type": "date"},
    "keyword": {"type": "keyword"},
}


class ESClient:
    """Elasticsearch 7.x client wrapper."""

    def __init__(self, hosts, user: str = "", password: str = "", prefix: str = "oxybank", timeout: int = 60):
        if isinstance(hosts, str):
            host_list = hosts.split(",")
        else:
            host_list = list(hosts)
        kwargs: dict[str, Any] = {
            "hosts": host_list,
            "timeout": timeout,
            "retry_on_timeout": True,
            "max_retries": 3,
            "sniff_on_connection_fail": True,
        }
        if user:
            kwargs["http_auth"] = (user, password)
        self._es = Elasticsearch(**kwargs)
        self._prefix = prefix

    def _idx(self, name: str) -> str:
        return f"{self._prefix}_{name}"

    @property
    def es(self) -> Elasticsearch:
        return self._es

    # ---- Index management ----

    def ensure_index(self, name: str, mapping: dict | None = None, settings: dict | None = None) -> bool:
        index = self._idx(name)
        if self._es.indices.exists(index=index):
            return False
        body: dict = {}
        if settings:
            body["settings"] = settings
        if mapping:
            body["mappings"] = mapping
        self._es.indices.create(index=index, body=body)
        logger.info("Created index %s", index)
        return True

    def delete_index(self, name: str) -> bool:
        index = self._idx(name)
        if not self._es.indices.exists(index=index):
            return False
        self._es.indices.delete(index=index)
        logger.info("Deleted index %s", index)
        return True

    def put_mapping(self, name: str, properties: dict):
        self._es.indices.put_mapping(
            index=self._idx(name),
            body={"properties": properties},
        )

    # ---- Document CRUD ----

    def index_doc(self, index_name: str, doc: dict, doc_id: str | None = None, refresh: bool = False) -> str:
        doc_id = doc_id or str(uuid.uuid4())
        self._es.index(
            index=self._idx(index_name),
            id=doc_id,
            body=doc,
            refresh="true" if refresh else "false",
        )
        return doc_id

    def get_doc(self, index_name: str, doc_id: str) -> dict | None:
        try:
            resp = self._es.get(index=self._idx(index_name), id=doc_id)
            source = resp["_source"]
            source["id"] = resp["_id"]
            return source
        except Exception:
            return None

    def update_doc(self, index_name: str, doc_id: str, doc: dict, refresh: bool = False):
        self._es.update(
            index=self._idx(index_name),
            id=doc_id,
            body={"doc": doc},
            refresh="true" if refresh else "false",
        )

    def delete_doc(self, index_name: str, doc_id: str, refresh: bool = False) -> bool:
        try:
            self._es.delete(
                index=self._idx(index_name),
                id=doc_id,
                refresh="true" if refresh else "false",
            )
            return True
        except Exception:
            return False

    def delete_by_query(self, index_name: str, query: dict, refresh: bool = False) -> int:
        resp = self._es.delete_by_query(
            index=self._idx(index_name),
            body={"query": query},
            refresh=refresh,
        )
        return resp.get("deleted", 0)

    # ---- Search ----

    def search(
        self,
        index_name: str,
        query: dict | None = None,
        size: int = 20,
        from_: int = 0,
        sort: list | None = None,
        source: list | None = None,
    ) -> dict:
        body: dict = {"size": size, "from": from_}
        if query:
            body["query"] = query
        else:
            body["query"] = {"match_all": {}}
        if sort:
            body["sort"] = sort
        if source:
            body["_source"] = source
        resp = self._es.search(index=self._idx(index_name), body=body)
        hits = resp.get("hits", {})
        total = hits.get("total", {})
        if isinstance(total, dict):
            total = total.get("value", 0)
        results = []
        for h in hits.get("hits", []):
            item = h["_source"]
            item["id"] = h["_id"]
            results.append(item)
        return {"total": total, "items": results}

    def count(self, index_name: str, query: dict | None = None) -> int:
        body = {"query": query} if query else {"query": {"match_all": {}}}
        resp = self._es.count(index=self._idx(index_name), body=body)
        return resp.get("count", 0)

    def terms_aggregation(
        self,
        index_name: str,
        field: str,
        query: dict | None = None,
        size: int = 100,
    ) -> list[dict]:
        """Return distinct values of `field` with their doc counts.
        Uses an ES terms aggregation — cheap even for large indices because it hits
        doc-value / column-store, not the source.

        Returns [{"key": <value>, "doc_count": <int>}, ...] ordered by count desc.
        `size` caps the number of buckets returned (default 100).
        """
        body: dict = {
            "size": 0,
            "aggs": {
                "distinct": {"terms": {"field": field, "size": size}}
            },
        }
        if query:
            body["query"] = query
        resp = self._es.search(index=self._idx(index_name), body=body)
        buckets = resp.get("aggregations", {}).get("distinct", {}).get("buckets", [])
        return [{"key": b.get("key"), "doc_count": b.get("doc_count", 0)} for b in buckets]

    # ---- Bulk ----

    def bulk_index(self, index_name: str, docs: list[dict], id_field: str = "id", refresh: bool = False) -> int:
        actions = []
        for doc in docs:
            doc_id = doc.pop(id_field, None) or str(uuid.uuid4())
            actions.append({
                "_index": self._idx(index_name),
                "_id": doc_id,
                "_source": doc,
            })
        success, _ = helpers.bulk(self._es, actions, refresh=refresh)
        return success

    # ---- Init system indices ----

    def init_system_indices(self):
        self.ensure_index("users", {
            "properties": {
                "username": {"type": "keyword"},
                "password_hash": {"type": "keyword"},
                "display_name": {"type": "text"},
                "role": {"type": "keyword"},
                "created_at": {"type": "date"},
            }
        })
        self.ensure_index("banks", {
            "properties": {
                "name": {"type": "keyword"},
                "description": {"type": "text"},
                "schema_mode": {"type": "keyword"},
                "has_sys_chunk": {"type": "boolean"},
                "scene_template_id": {"type": "keyword"},
                "schema": {"type": "object", "enabled": False},
                "embedding_backend": {"type": "keyword"},
                "embedding_model": {"type": "keyword"},
                "retrieval_apis": {"type": "object", "enabled": False},
                "created_by": {"type": "keyword"},
                "created_at": {"type": "date"},
                "updated_at": {"type": "date"},
            }
        })
        self.ensure_index("agents", {
            "properties": {
                "bank_id": {"type": "keyword"},
                "name": {"type": "text"},
                "service_url": {"type": "keyword"},
                "trigger_statuses": {"type": "keyword"},
                "enabled": {"type": "boolean"},
                "created_by": {"type": "keyword"},
                "created_at": {"type": "date"},
                "updated_at": {"type": "date"},
            }
        })
        self.ensure_index("templates", {
            "properties": {
                "bank_id": {"type": "keyword"},
                "name": {"type": "text"},
                "description": {"type": "text"},
                "editable_fields": {"type": "keyword"},
                "field_constraints": {"type": "object", "enabled": False},
                "layout": {"type": "object", "enabled": False},
                "created_by": {"type": "keyword"},
                "created_at": {"type": "date"},
                "updated_at": {"type": "date"},
            }
        })
        self.ensure_index("agent_logs", {
            "properties": {
                "bank_id": {"type": "keyword"},
                "agent_id": {"type": "keyword"},
                "agent_name": {"type": "keyword"},
                "sample_id": {"type": "keyword"},
                "input_status": {"type": "keyword"},
                "output_status": {"type": "keyword"},
                "success": {"type": "boolean"},
                "error": {"type": "text"},
                "duration_ms": {"type": "integer"},
                "timestamp": {"type": "date"},
            }
        })

    def ensure_bank_indices(self, bank_id: str, schema_fields: list[dict], has_sys_chunk: bool = False):
        """Create per-bank ES indices for documents, samples, and history."""
        self.ensure_index(f"documents_{bank_id}", {
            "properties": {
                "bank_id": {"type": "keyword"},
                "filename": {"type": "text", "fields": {"raw": {"type": "keyword"}}},
                "file_type": {"type": "keyword"},
                "upload_time": {"type": "date"},
                "uploaded_by": {"type": "keyword"},
                "sample_count": {"type": "integer"},
                "status": {"type": "keyword"},
            }
        })

        sample_props = dict(SYSTEM_FIELDS_MAPPING)
        if has_sys_chunk:
            sample_props["sys_chunk"] = {"type": "text"}
        for f in schema_fields:
            name = f.get("name", "")
            ftype = f.get("type", "string")
            if name and name not in sample_props:
                sample_props[name] = FIELD_TYPE_MAP.get(ftype, {"type": "keyword"})
        self.ensure_index(f"samples_{bank_id}", {"properties": sample_props})

        self.ensure_index(f"sample_history_{bank_id}", {
            "properties": {
                "sample_id": {"type": "keyword"},
                "version": {"type": "integer"},
                "changed_fields": {"type": "object", "enabled": False},
                "changed_by": {"type": "keyword"},
                "change_source": {"type": "keyword"},
                "timestamp": {"type": "date"},
                "full_snapshot": {"type": "object", "enabled": False},
            }
        })

    def delete_bank_indices(self, bank_id: str):
        for suffix in ["documents", "samples", "sample_history"]:
            self.delete_index(f"{suffix}_{bank_id}")
