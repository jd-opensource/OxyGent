from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class SchemaField(BaseModel):
    name: str
    type: str = "string"  # string, text, integer, float, boolean, date, keyword
    description: str = ""
    source: str = "manual"  # manual, file, scene


class SearchCondition(BaseModel):
    field: str
    mode: str  # vector, exact, in, fuzzy


class RetrievalApiDef(BaseModel):
    id: str = ""
    name: str
    search_conditions: list[SearchCondition]
    output_fields: list[str]


class BankCreate(BaseModel):
    name: str
    description: str = ""
    schema_mode: str = "personalized"  # personalized, scene
    has_sys_chunk: bool = False
    scene_template_id: str = ""
    schema_fields: list[SchemaField] = []
    retrieval_apis: list[RetrievalApiDef] = []
    embedding_backend: str = "triton"
    embedding_model: str = ""


class BankUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class BankResponse(BaseModel):
    model_config = {"populate_by_name": True}

    id: str
    name: str
    description: str = ""
    schema_mode: str = ""
    has_sys_chunk: bool = False
    schema_def: dict = Field(default_factory=dict, alias="schema")
    retrieval_apis: list[dict] = []
    created_by: str = ""
    created_at: str = ""
    updated_at: str = ""
