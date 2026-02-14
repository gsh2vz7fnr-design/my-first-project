from fastapi import APIRouter, HTTPException

from app.schemas.prompt import PromptVersionSummary, RestorePromptRequest, UpdatePromptsRequest
from app.services.llm.prompts import get_active_prompts, list_prompt_versions, restore_prompt_version, update_prompts

router = APIRouter(prefix="/api/v1/prompts", tags=["prompts"])


@router.get("/current", response_model=dict)
def get_current_prompts() -> dict:
    return {"item": get_active_prompts()}


@router.put("/current", response_model=dict)
def set_current_prompts(payload: UpdatePromptsRequest) -> dict:
    item = update_prompts(payload.outline_prompt, payload.detail_prompt, payload.note)
    return {"item": item}


@router.get("/history", response_model=dict)
def get_prompt_history() -> dict:
    items = [
        PromptVersionSummary(version=v.version, note=v.note, created_at=v.created_at).model_dump()
        for v in list_prompt_versions()
    ]
    return {"items": items}


@router.post("/restore", response_model=dict)
def restore_prompts(payload: RestorePromptRequest) -> dict:
    try:
        item = restore_prompt_version(payload.version)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"item": item}

