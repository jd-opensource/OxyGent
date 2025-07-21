"""Web response in base model."""

from pydantic import BaseModel, Field


class WebResponse(BaseModel):
    code: int = Field(200)
    message: str = Field("SUCCESS")
    data: dict = Field(default_factory=dict)

    def to_dict(self):
        return self.model_dump()
