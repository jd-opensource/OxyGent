from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


# --- Inline step types -----------------------------------------------------
# Inline agents are built out of a linear list of steps executed in order by
# annotation_service.run_inline_agent. Each step's shape is validated loosely
# (dict) here because the runner does its own field checks; we don't want to
# over-constrain the schema and force a code change every time we add a step
# type.

class AgentCreate(BaseModel):
    name: str
    trigger_statuses: list[str]
    # kind:
    #   "url"    (default, back-compat)   — POST samples to service_url
    #   "inline" — execute `steps` server-side (see annotation_service.run_inline_agent)
    kind: str = "url"
    service_url: str = ""             # required when kind="url"
    steps: list[dict[str, Any]] = []  # required when kind="inline"


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    trigger_statuses: Optional[list[str]] = None
    kind: Optional[str] = None
    service_url: Optional[str] = None
    steps: Optional[list[dict[str, Any]]] = None
    enabled: Optional[bool] = None


class AgentResponse(BaseModel):
    id: str
    bank_id: str
    name: str
    kind: str = "url"
    service_url: str = ""
    steps: list[dict[str, Any]] = []
    trigger_statuses: list[str]
    enabled: bool = True
    created_by: str = ""
    created_at: str = ""
