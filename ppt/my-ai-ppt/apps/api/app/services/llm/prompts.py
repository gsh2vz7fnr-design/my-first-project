from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from threading import Lock
from typing import Dict, List


DEFAULT_OUTLINE_SYSTEM_PROMPT = """
你是一个专业的PPT设计专家和内容策划师。

任务目标：
请根据我提供的文档内容，生成一份详细的PPT分页大纲。你需要遵循“AIPPT生成流程”，核心是“内容智能映射”。

执行步骤：
第一步：风格定义（对应视觉分析）
- 设定整体风格为：极简科技风，主色调深蓝与白色，字体干练易读。

第二步：内容分段（对应文章拆分）
- 遵循“一页一观点”原则。
- 将文档拆分为 4-10 页。
- 每页必须有清晰的主题与目标，不要把大段原文直接塞进单页。

输出格式（必须严格 JSON）：
{
  "theme": {
    "name": "string",
    "colors": {"bg": "string", "primary": "string", "text": "string"},
    "font": {"title": "string", "body": "string"}
  },
  "slides": [
    {
      "slide_id": "s1",
      "page_type": "cover|content|summary",
      "layout_id": "cover_centered_01|split_left_image_right_text|three_column_points",
      "topic": "本页主题",
      "goal": "本页目标",
      "key_points": ["要点1", "要点2"]
    }
  ]
}
"""


DEFAULT_DETAIL_SYSTEM_PROMPT = """
你是一个专业的PPT页面设计专家。

任务目标：
根据给定的大纲页与原文，生成“单页最终内容 + 布局映射”。

执行步骤：
第一步：内容映射
- 保持该页“一页一观点”，内容聚焦该页 topic/goal。

第二步：布局匹配
- layout_id 仅可使用：
  - cover_centered_01
  - split_left_image_right_text
  - three_column_points

第三步：图文约束
- bullets 最多 6 条，每条尽量不超过 30 字。
- image_src 不可编造，不确定时必须填 null。

输出格式（必须严格 JSON）：
{
  "page_type": "cover|content|summary",
  "layout_id": "cover_centered_01|split_left_image_right_text|three_column_points",
  "content": {
    "title": "string",
    "subtitle": "string",
    "body": "string",
    "footer": "string",
    "bullets": ["string"],
    "image_src": null
  },
  "constraints": {
    "overflow_strategy": "shrink_then_ellipsis|ellipsis|truncate"
  }
}
"""


@dataclass
class PromptVersion:
    version: int
    note: str
    outline_prompt: str
    detail_prompt: str
    created_at: datetime


_lock = Lock()
_current_outline = DEFAULT_OUTLINE_SYSTEM_PROMPT
_current_detail = DEFAULT_DETAIL_SYSTEM_PROMPT
_current_version = 1
_history: List[PromptVersion] = [
    PromptVersion(
        version=1,
        note="initial",
        outline_prompt=DEFAULT_OUTLINE_SYSTEM_PROMPT,
        detail_prompt=DEFAULT_DETAIL_SYSTEM_PROMPT,
        created_at=datetime.utcnow(),
    )
]


def get_active_prompts() -> Dict[str, str]:
    with _lock:
        return {
            "version": str(_current_version),
            "outline_prompt": _current_outline,
            "detail_prompt": _current_detail,
        }


def update_prompts(outline_prompt: str, detail_prompt: str, note: str = "manual update") -> Dict[str, str]:
    global _current_outline, _current_detail, _current_version
    with _lock:
        _current_version += 1
        _current_outline = outline_prompt
        _current_detail = detail_prompt
        _history.insert(
            0,
            PromptVersion(
                version=_current_version,
                note=note,
                outline_prompt=outline_prompt,
                detail_prompt=detail_prompt,
                created_at=datetime.utcnow(),
            ),
        )
        del _history[20:]
        return {
            "version": str(_current_version),
            "outline_prompt": _current_outline,
            "detail_prompt": _current_detail,
        }


def list_prompt_versions() -> List[PromptVersion]:
    with _lock:
        return list(_history)


def restore_prompt_version(version: int) -> Dict[str, str]:
    with _lock:
        target = next((item for item in _history if item.version == version), None)
        if not target:
            raise ValueError(f"prompt version not found: {version}")
    return update_prompts(target.outline_prompt, target.detail_prompt, note=f"restore-from-v{version}")
