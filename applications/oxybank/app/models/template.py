from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class TemplateCreate(BaseModel):
    name: str
    description: str = ""
    editable_fields: list[str] = []
    field_constraints: dict = {}
    layout: dict = {}


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    editable_fields: Optional[list[str]] = None
    field_constraints: Optional[dict] = None
    layout: Optional[dict] = None


class TemplateResponse(BaseModel):
    id: str
    bank_id: str
    name: str
    description: str = ""
    editable_fields: list[str] = []
    field_constraints: dict = {}
    layout: dict = {}
    created_by: str = ""
    created_at: str = ""
    updated_at: str = ""


class LLMChatMessage(BaseModel):
    role: str  # user, assistant, system
    content: str


class LLMChatRequest(BaseModel):
    messages: list[LLMChatMessage]
    bank_schema: list[dict] = []
    # Optional: the template the user is currently editing. When provided, the AI
    # sees it as system context and can iterate on it ("add a field", "change the
    # radio options") instead of generating a fresh template every turn.
    current_template: Optional[dict] = None


class TemplateTestRequest(BaseModel):
    sample_data: dict
