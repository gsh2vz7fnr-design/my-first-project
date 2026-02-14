from __future__ import annotations

import json
from typing import Any, Dict, List
from urllib import error, request

from app.core.config import settings
from app.services.llm.prompts import get_active_prompts


def _post_chat_json(system_prompt: str, user_content: str) -> Dict[str, Any]:
    endpoint = settings.openai_base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": settings.openai_model,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content[:12000]},
        ],
        "temperature": 0.2,
    }
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        endpoint,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.openai_api_key}",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"LLM HTTP {exc.code}: {body}") from exc
    parsed = json.loads(raw)
    content = parsed["choices"][0]["message"]["content"]
    return json.loads(content)


def _llm_outline(text: str) -> Dict[str, Any]:
    prompts = get_active_prompts()
    result = _post_chat_json(prompts["outline_prompt"], text)
    if not isinstance(result, dict) or "slides" not in result:
        raise ValueError("invalid outline json")
    if not isinstance(result["slides"], list) or not result["slides"]:
        raise ValueError("empty outline slides")
    return result


def _llm_slide_detail(source_text: str, outline_slide: Dict[str, Any], index: int, total: int) -> Dict[str, Any]:
    user_payload = json.dumps(
        {
            "source_text": source_text[:12000],
            "slide_index": index + 1,
            "slide_total": total,
            "outline_slide": outline_slide,
        },
        ensure_ascii=False,
    )
    prompts = get_active_prompts()
    result = _post_chat_json(prompts["detail_prompt"], user_payload)
    if not isinstance(result, dict) or "content" not in result:
        raise ValueError("invalid slide detail json")
    return result


def regenerate_slide_content(
    source_text: str,
    slide_payload: Dict[str, Any],
    user_instruction: str,
    locked_fields: List[str],
) -> Dict[str, Any]:
    if not settings.llm_enabled:
        raise RuntimeError("LLM is required. Set LLM_ENABLED=true.")
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required when LLM_ENABLED=true.")

    prompt = (
        "你是PPT页面改写专家。根据用户的修改意图，只重写当前这一页。"
        "严格返回 JSON 对象，字段必须是：page_type,layout_id,content,constraints。"
        "content 可含：title,subtitle,body,footer,bullets,image_src。"
        "不要输出 markdown。"
    )
    user_payload = json.dumps(
        {
            "source_text": source_text[:12000],
            "current_slide": slide_payload,
            "user_instruction": user_instruction,
            "locked_fields": locked_fields,
        },
        ensure_ascii=False,
    )
    try:
        result = _post_chat_json(prompt, user_payload)
    except (error.URLError, ValueError, KeyError, json.JSONDecodeError, TimeoutError) as exc:
        raise RuntimeError(f"LLM slide regenerate failed: {exc}") from exc
    if not isinstance(result, dict) or "content" not in result:
        raise RuntimeError("LLM slide regenerate failed: invalid json schema")
    return result


def plan_slides(text: str) -> Dict[str, Any]:
    if not settings.llm_enabled:
        raise RuntimeError("LLM is required. Set LLM_ENABLED=true.")
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required when LLM_ENABLED=true.")

    try:
        outline = _llm_outline(text)
        outline_slides = outline.get("slides", [])
        final_slides: List[Dict[str, Any]] = []
        for idx, item in enumerate(outline_slides):
            detail = _llm_slide_detail(text, item, idx, len(outline_slides))
            final_slides.append(
                {
                    "slide_id": item.get("slide_id") or f"s{idx + 1}",
                    "page_type": detail.get("page_type") or item.get("page_type") or "content",
                    "layout_id": detail.get("layout_id") or item.get("layout_id") or "cover_centered_01",
                    "content": detail.get("content", {}),
                    "constraints": detail.get("constraints", {}),
                }
            )
        return {"theme": outline.get("theme", {}), "slides": final_slides}
    except (error.URLError, ValueError, KeyError, json.JSONDecodeError, TimeoutError) as exc:
        raise RuntimeError(f"LLM planning failed: {exc}") from exc
