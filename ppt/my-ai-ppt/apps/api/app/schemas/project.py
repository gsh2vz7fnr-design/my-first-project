from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class CreateProjectRequest(BaseModel):
    title: Optional[str] = None
    source_text: Optional[str] = None


class GenerateDslRequest(BaseModel):
    force: bool = False


class UpdateSourceRequest(BaseModel):
    source_text: str = ""


class UpdateSlideRequest(BaseModel):
    title: Optional[str] = None
    subtitle: Optional[str] = None
    body: Optional[str] = None
    footer: Optional[str] = None


class RegenerateSlideRequest(BaseModel):
    user_instruction: str
    locked_fields: List[str] = Field(default_factory=list)


class AddSlideRequest(BaseModel):
    after_slide_id: Optional[str] = None
    layout_id: str = "cover_centered_01"
    page_type: str = "content"
    title: Optional[str] = None
    subtitle: Optional[str] = None


class ReorderSlidesRequest(BaseModel):
    slide_ids: List[str] = Field(default_factory=list)


class UpdateSlideLayoutRequest(BaseModel):
    layout_id: str


class ProjectSummary(BaseModel):
    project_id: str
    title: str
    created_at: datetime
    updated_at: datetime


class SnapshotSummary(BaseModel):
    snapshot_id: str
    created_at: datetime


class CreateExportRequest(BaseModel):
    mode: str = Field(default="editable_text", pattern="^(editable_text|image_fallback)$")


class ExportSummary(BaseModel):
    job_id: str
    mode: str
    status: str
    download_path: Optional[str] = None
    download_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class TaskSummary(BaseModel):
    task_id: str
    task_type: str
    status: str
    progress: int = 0
    message: str = ""
    error: Optional[str] = None
    result: Optional[dict] = None
    created_at: datetime
    updated_at: datetime
