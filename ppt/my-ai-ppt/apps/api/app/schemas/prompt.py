from datetime import datetime

from pydantic import BaseModel


class UpdatePromptsRequest(BaseModel):
    outline_prompt: str
    detail_prompt: str
    note: str = "manual update"


class RestorePromptRequest(BaseModel):
    version: int


class PromptVersionSummary(BaseModel):
    version: int
    note: str
    created_at: datetime

