from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SlideContent(BaseModel):
    title: Optional[str] = None
    subtitle: Optional[str] = None
    body: Optional[str] = None
    footer: Optional[str] = None
    bullets: List[str] = Field(default_factory=list)
    image_src: Optional[str] = None


class Slide(BaseModel):
    slide_id: str
    page_type: str
    layout_id: str
    theme_override: Optional[Dict[str, Any]] = None
    content: SlideContent
    constraints: Dict[str, Any] = Field(default_factory=dict)


class ProjectDSL(BaseModel):
    project_id: str
    theme: Dict[str, Any] = Field(default_factory=dict)
    slides: List[Slide] = Field(default_factory=list)
