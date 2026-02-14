from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List

from app.schemas.dsl import ProjectDSL


@dataclass
class ProjectRecord:
    project_id: str
    title: str
    source_text: str
    created_at: datetime
    updated_at: datetime


@dataclass
class SnapshotRecord:
    snapshot_id: str
    created_at: datetime
    dsl: ProjectDSL


@dataclass
class MemoryStore:
    projects: Dict[str, ProjectRecord] = field(default_factory=dict)
    dsls: Dict[str, ProjectDSL] = field(default_factory=dict)
    snapshots: Dict[str, List[SnapshotRecord]] = field(default_factory=dict)
    exports: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    tasks: Dict[str, Dict[str, Dict[str, Any]]] = field(default_factory=dict)


store = MemoryStore()
