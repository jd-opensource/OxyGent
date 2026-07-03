from __future__ import annotations

from pydantic import BaseModel


class SampleUpdate(BaseModel):
    fields: dict  # key-value pairs to update
    remarks: str = ""


class SampleHistoryResponse(BaseModel):
    id: str
    sample_id: str
    version: int
    changed_fields: dict = {}
    changed_by: str = ""
    change_source: str = ""
    timestamp: str = ""
