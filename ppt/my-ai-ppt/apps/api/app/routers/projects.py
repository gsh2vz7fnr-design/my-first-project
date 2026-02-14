from __future__ import annotations

from datetime import datetime
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import FileResponse

from app.models.memory_store import ProjectRecord, SnapshotRecord, store
from app.schemas.dsl import ProjectDSL, Slide, SlideContent
from app.schemas.project import (
    AddSlideRequest,
    CreateExportRequest,
    CreateProjectRequest,
    ExportSummary,
    GenerateDslRequest,
    ProjectSummary,
    RegenerateSlideRequest,
    ReorderSlidesRequest,
    SnapshotSummary,
    TaskSummary,
    UpdateSlideLayoutRequest,
    UpdateSourceRequest,
    UpdateSlideRequest,
)
from app.services.export.pptx_exporter import export_editable_pptx, export_image_fallback_pptx
from app.services.llm.planner import plan_slides, regenerate_slide_content

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


def _now() -> datetime:
    return datetime.utcnow()


def _ensure_project(project_id: str) -> ProjectRecord:
    project = store.projects.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"project not found: {project_id}")
    return project


def _ensure_dsl(project_id: str) -> ProjectDSL:
    dsl = store.dsls.get(project_id)
    if not dsl:
        raise HTTPException(status_code=404, detail="dsl not generated")
    return dsl


def _build_initial_dsl(project: ProjectRecord) -> ProjectDSL:
    plan = plan_slides(project.source_text or project.title)
    slides = [
        Slide(
            slide_id=item["slide_id"],
            page_type=item["page_type"],
            layout_id=item["layout_id"],
            content=SlideContent(**item.get("content", {})),
            constraints=item.get("constraints", {}),
        )
        for item in plan.get("slides", [])
    ]
    return ProjectDSL(
        project_id=project.project_id,
        theme=plan.get("theme", {}),
        slides=slides,
    )


def _create_task(project_id: str, task_type: str, message: str) -> dict:
    task_id = f"task_{uuid.uuid4().hex[:10]}"
    now = _now()
    item = TaskSummary(
        task_id=task_id,
        task_type=task_type,
        status="queued",
        progress=0,
        message=message,
        created_at=now,
        updated_at=now,
    ).model_dump()
    store.tasks.setdefault(project_id, {})[task_id] = item
    return item


def _patch_task(project_id: str, task_id: str, **changes) -> None:
    task = store.tasks.get(project_id, {}).get(task_id)
    if not task:
        return
    task.update(changes)
    task["updated_at"] = _now()


def _run_generate_dsl_task(project_id: str, task_id: str, force: bool) -> None:
    project = store.projects.get(project_id)
    if not project:
        _patch_task(project_id, task_id, status="failed", progress=100, error=f"project not found: {project_id}")
        return
    _patch_task(project_id, task_id, status="running", progress=20, message="开始生成分页大纲")
    try:
        if force or project_id not in store.dsls:
            dsl = _build_initial_dsl(project)
            store.dsls[project_id] = dsl
            project.updated_at = _now()
        _patch_task(
            project_id,
            task_id,
            status="completed",
            progress=100,
            message="生成完成",
            result={"dsl": store.dsls[project_id].model_dump()},
        )
    except RuntimeError as exc:
        _patch_task(project_id, task_id, status="failed", progress=100, error=str(exc))


def _run_export_task(project_id: str, task_id: str, mode: str) -> None:
    dsl = store.dsls.get(project_id)
    if not dsl:
        _patch_task(project_id, task_id, status="failed", progress=100, error="dsl not generated")
        return
    _patch_task(project_id, task_id, status="running", progress=30, message="开始导出")
    now = _now()
    try:
        if mode == "editable_text":
            download_path = export_editable_pptx(project_id, task_id, dsl)
        else:
            download_path = export_image_fallback_pptx(project_id, task_id, dsl)
        download_url = f"/api/v1/projects/{project_id}/exports/{task_id}/download"
        export_item = ExportSummary(
            job_id=task_id,
            mode=mode,
            status="completed",
            download_path=download_path,
            download_url=download_url,
            created_at=now,
            updated_at=now,
        ).model_dump()
        store.exports.setdefault(project_id, []).insert(0, export_item)
        del store.exports[project_id][20:]
        _patch_task(project_id, task_id, status="completed", progress=100, message="导出完成", result={"item": export_item})
    except RuntimeError as exc:
        _patch_task(project_id, task_id, status="failed", progress=100, error=str(exc))


@router.get("/", response_model=dict)
def list_projects() -> dict:
    items = [
        ProjectSummary(
            project_id=p.project_id,
            title=p.title,
            created_at=p.created_at,
            updated_at=p.updated_at,
        ).model_dump()
        for p in sorted(store.projects.values(), key=lambda x: x.updated_at, reverse=True)
    ]
    return {"items": items}


@router.post("/", response_model=dict)
def create_project(payload: CreateProjectRequest) -> dict:
    project_id = f"proj_{uuid.uuid4().hex[:10]}"
    now = _now()
    project = ProjectRecord(
        project_id=project_id,
        title=payload.title or "Untitled Project",
        source_text=payload.source_text or "",
        created_at=now,
        updated_at=now,
    )
    store.projects[project_id] = project
    store.snapshots[project_id] = []
    store.exports[project_id] = []
    store.tasks[project_id] = {}
    return {"project_id": project_id, "created_at": now.isoformat()}


@router.post("/{project_id}/dsl", response_model=dict)
def generate_dsl(project_id: str, payload: GenerateDslRequest) -> dict:
    project = _ensure_project(project_id)
    try:
        if payload.force or project_id not in store.dsls:
            store.dsls[project_id] = _build_initial_dsl(project)
            project.updated_at = _now()
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"dsl": store.dsls[project_id].model_dump()}


@router.post("/{project_id}/tasks/generate-dsl", response_model=dict)
def create_generate_dsl_task(project_id: str, payload: GenerateDslRequest, background_tasks: BackgroundTasks) -> dict:
    _ensure_project(project_id)
    task = _create_task(project_id, "generate_dsl", "等待生成")
    background_tasks.add_task(_run_generate_dsl_task, project_id, task["task_id"], payload.force)
    return {"item": task}


@router.post("/{project_id}/tasks/export-pptx", response_model=dict)
def create_export_task(project_id: str, payload: CreateExportRequest, background_tasks: BackgroundTasks) -> dict:
    _ensure_project(project_id)
    task = _create_task(project_id, "export_pptx", "等待导出")
    background_tasks.add_task(_run_export_task, project_id, task["task_id"], payload.mode)
    return {"item": task}


@router.get("/{project_id}/tasks/{task_id}", response_model=dict)
def get_task(project_id: str, task_id: str) -> dict:
    _ensure_project(project_id)
    task = store.tasks.get(project_id, {}).get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"task not found: {task_id}")
    return {"item": task}


@router.put("/{project_id}/source", response_model=dict)
def update_source(project_id: str, payload: UpdateSourceRequest) -> dict:
    project = _ensure_project(project_id)
    project.source_text = payload.source_text or ""
    project.updated_at = _now()
    return {"ok": True}


@router.get("/{project_id}/dsl", response_model=dict)
def get_dsl(project_id: str, snapshot_id: Optional[str] = Query(default=None)) -> dict:
    _ensure_project(project_id)

    if snapshot_id:
        snapshots = store.snapshots.get(project_id, [])
        for snapshot in snapshots:
            if snapshot.snapshot_id == snapshot_id:
                return {"dsl": snapshot.dsl.model_dump(), "snapshot_id": snapshot_id}
        raise HTTPException(status_code=404, detail=f"snapshot not found: {snapshot_id}")

    dsl = store.dsls.get(project_id)
    if not dsl:
        raise HTTPException(status_code=404, detail="dsl not generated")
    return {"dsl": dsl.model_dump()}


@router.put("/{project_id}/slides/{slide_id}", response_model=dict)
def update_slide(project_id: str, slide_id: str, payload: UpdateSlideRequest) -> dict:
    project = _ensure_project(project_id)
    dsl = _ensure_dsl(project_id)

    target = next((s for s in dsl.slides if s.slide_id == slide_id), None)
    if not target:
        raise HTTPException(status_code=404, detail=f"slide not found: {slide_id}")

    if payload.title is not None:
        target.content.title = payload.title
    if payload.subtitle is not None:
        target.content.subtitle = payload.subtitle
    if payload.footer is not None:
        target.content.footer = payload.footer
    if payload.body is not None:
        target.content.body = payload.body

    project.updated_at = _now()
    return {"dsl": dsl.model_dump()}


@router.post("/{project_id}/slides", response_model=dict)
def add_slide(project_id: str, payload: AddSlideRequest) -> dict:
    project = _ensure_project(project_id)
    dsl = _ensure_dsl(project_id)
    new_slide_id = f"s{uuid.uuid4().hex[:6]}"
    slide = Slide(
        slide_id=new_slide_id,
        page_type=payload.page_type,
        layout_id=payload.layout_id,
        content=SlideContent(
            title=payload.title or "新页面标题",
            subtitle=payload.subtitle or "请编辑页面内容",
            footer="",
            bullets=[],
            image_src=None,
        ),
        constraints={"overflow_strategy": "shrink_then_ellipsis"},
    )

    if payload.after_slide_id:
        idx = next((i for i, s in enumerate(dsl.slides) if s.slide_id == payload.after_slide_id), None)
        if idx is None:
            raise HTTPException(status_code=404, detail=f"slide not found: {payload.after_slide_id}")
        dsl.slides.insert(idx + 1, slide)
    else:
        dsl.slides.append(slide)

    project.updated_at = _now()
    return {"dsl": dsl.model_dump(), "slide_id": new_slide_id}


@router.delete("/{project_id}/slides/{slide_id}", response_model=dict)
def delete_slide(project_id: str, slide_id: str) -> dict:
    project = _ensure_project(project_id)
    dsl = _ensure_dsl(project_id)
    if len(dsl.slides) <= 1:
        raise HTTPException(status_code=400, detail="at least one slide is required")
    before = len(dsl.slides)
    dsl.slides = [s for s in dsl.slides if s.slide_id != slide_id]
    if len(dsl.slides) == before:
        raise HTTPException(status_code=404, detail=f"slide not found: {slide_id}")
    project.updated_at = _now()
    return {"dsl": dsl.model_dump()}


@router.post("/{project_id}/slides/reorder", response_model=dict)
def reorder_slides(project_id: str, payload: ReorderSlidesRequest) -> dict:
    project = _ensure_project(project_id)
    dsl = _ensure_dsl(project_id)
    existing = {s.slide_id: s for s in dsl.slides}
    current_ids = {s.slide_id for s in dsl.slides}
    input_ids = set(payload.slide_ids)
    if current_ids != input_ids:
        raise HTTPException(status_code=400, detail="slide_ids must contain exactly all existing slide ids")
    dsl.slides = [existing[sid] for sid in payload.slide_ids]
    project.updated_at = _now()
    return {"dsl": dsl.model_dump()}


@router.put("/{project_id}/slides/{slide_id}/layout", response_model=dict)
def update_slide_layout(project_id: str, slide_id: str, payload: UpdateSlideLayoutRequest) -> dict:
    project = _ensure_project(project_id)
    dsl = _ensure_dsl(project_id)
    target = next((s for s in dsl.slides if s.slide_id == slide_id), None)
    if not target:
        raise HTTPException(status_code=404, detail=f"slide not found: {slide_id}")
    target.layout_id = payload.layout_id
    project.updated_at = _now()
    return {"dsl": dsl.model_dump()}


@router.post("/{project_id}/slides/{slide_id}/regenerate", response_model=dict)
def regenerate_slide(project_id: str, slide_id: str, payload: RegenerateSlideRequest) -> dict:
    project = _ensure_project(project_id)
    dsl = store.dsls.get(project_id)
    if not dsl:
        raise HTTPException(status_code=404, detail="dsl not generated")
    if not payload.user_instruction.strip():
        raise HTTPException(status_code=400, detail="user_instruction is required")

    target = next((s for s in dsl.slides if s.slide_id == slide_id), None)
    if not target:
        raise HTTPException(status_code=404, detail=f"slide not found: {slide_id}")

    try:
        regenerated = regenerate_slide_content(
            source_text=project.source_text or "",
            slide_payload=target.model_dump(),
            user_instruction=payload.user_instruction,
            locked_fields=payload.locked_fields,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    content = regenerated.get("content", {})
    locked = set(payload.locked_fields)
    if "title" not in locked:
        target.content.title = content.get("title", target.content.title)
    if "subtitle" not in locked:
        target.content.subtitle = content.get("subtitle", target.content.subtitle)
    if "body" not in locked:
        target.content.body = content.get("body", target.content.body)
    if "footer" not in locked:
        target.content.footer = content.get("footer", target.content.footer)
    if "bullets" not in locked and isinstance(content.get("bullets"), list):
        target.content.bullets = content.get("bullets", target.content.bullets)
    if "image_src" not in locked:
        target.content.image_src = content.get("image_src", target.content.image_src)
    if "layout_id" not in locked:
        target.layout_id = regenerated.get("layout_id", target.layout_id)
    if "page_type" not in locked:
        target.page_type = regenerated.get("page_type", target.page_type)
    if isinstance(regenerated.get("constraints"), dict):
        target.constraints = regenerated["constraints"]

    project.updated_at = _now()
    return {"dsl": dsl.model_dump()}


@router.post("/{project_id}/snapshots", response_model=dict)
def create_snapshot(project_id: str) -> dict:
    _ensure_project(project_id)
    dsl = store.dsls.get(project_id)
    if not dsl:
        raise HTTPException(status_code=404, detail="dsl not generated")

    snapshot_id = f"snap_{uuid.uuid4().hex[:8]}"
    item = SnapshotRecord(
        snapshot_id=snapshot_id,
        created_at=_now(),
        dsl=dsl.model_copy(deep=True),
    )
    snapshots = store.snapshots.setdefault(project_id, [])
    snapshots.insert(0, item)
    del snapshots[10:]
    return {"snapshot_id": snapshot_id, "created_at": item.created_at.isoformat()}


@router.get("/{project_id}/snapshots", response_model=dict)
def list_snapshots(project_id: str) -> dict:
    _ensure_project(project_id)
    snapshots = [
        SnapshotSummary(snapshot_id=s.snapshot_id, created_at=s.created_at).model_dump()
        for s in store.snapshots.get(project_id, [])
    ]
    return {"items": snapshots}


@router.post("/{project_id}/restore/{snapshot_id}", response_model=dict)
def restore_snapshot(project_id: str, snapshot_id: str) -> dict:
    project = _ensure_project(project_id)
    snapshots = store.snapshots.get(project_id, [])
    target = next((s for s in snapshots if s.snapshot_id == snapshot_id), None)
    if not target:
        raise HTTPException(status_code=404, detail=f"snapshot not found: {snapshot_id}")

    store.dsls[project_id] = target.dsl.model_copy(deep=True)
    project.updated_at = _now()
    return {"dsl": store.dsls[project_id].model_dump(), "snapshot_id": snapshot_id}


@router.post("/{project_id}/exports/pptx", response_model=dict)
def create_export(project_id: str, payload: CreateExportRequest) -> dict:
    _ensure_project(project_id)
    dsl = store.dsls.get(project_id)
    if not dsl:
        raise HTTPException(status_code=404, detail="dsl not generated")

    now = _now()
    job_id = f"exp_{uuid.uuid4().hex[:8]}"
    if payload.mode == "editable_text":
        download_path = export_editable_pptx(project_id, job_id, dsl)
    else:
        download_path = export_image_fallback_pptx(project_id, job_id, dsl)
    download_url = f"/api/v1/projects/{project_id}/exports/{job_id}/download"

    item = ExportSummary(
        job_id=job_id,
        mode=payload.mode,
        status="completed",
        download_path=download_path,
        created_at=now,
        updated_at=now,
    ).model_dump()
    item["download_url"] = download_url
    exports = store.exports.setdefault(project_id, [])
    exports.insert(0, item)
    del exports[20:]
    return {"item": item}


@router.get("/{project_id}/exports", response_model=dict)
def list_exports(project_id: str) -> dict:
    _ensure_project(project_id)
    return {"items": store.exports.get(project_id, [])}


@router.get("/{project_id}/exports/{job_id}/download")
def download_export(project_id: str, job_id: str):
    _ensure_project(project_id)
    export_item = next((item for item in store.exports.get(project_id, []) if item["job_id"] == job_id), None)
    if not export_item:
        raise HTTPException(status_code=404, detail=f"export not found: {job_id}")

    file_path = Path(export_item.get("download_path", ""))
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="export file missing")

    return FileResponse(
        path=str(file_path),
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename=f"{project_id}-{job_id}.pptx",
    )
