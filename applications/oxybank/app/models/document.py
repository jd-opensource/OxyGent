from __future__ import annotations

from pydantic import BaseModel


class DocumentResponse(BaseModel):
    id: str
    bank_id: str
    filename: str
    file_type: str
    upload_time: str
    uploaded_by: str = ""
    sample_count: int = 0
    status: str = ""
