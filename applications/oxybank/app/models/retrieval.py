from __future__ import annotations

from pydantic import BaseModel


class RetrievalQuery(BaseModel):
    conditions: dict = {}  # field_name -> value
    top_k: int = 10
    page_size: int = 10
    page_number: int = 1
