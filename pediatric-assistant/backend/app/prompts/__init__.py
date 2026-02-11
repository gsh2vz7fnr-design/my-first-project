"""
Prompts 模块

包含各种 Prompt 模板。
"""
from app.prompts.classifier_prompt import (
    CLASSIFIER_SYSTEM_PROMPT,
    CLASSIFIER_USER_PROMPT_TEMPLATE,
    SYMPTOM_KEYWORDS,
    GREETING_KEYWORDS,
    EXIT_KEYWORDS,
    build_classifier_prompt
)

__all__ = [
    "CLASSIFIER_SYSTEM_PROMPT",
    "CLASSIFIER_USER_PROMPT_TEMPLATE",
    "SYMPTOM_KEYWORDS",
    "GREETING_KEYWORDS",
    "EXIT_KEYWORDS",
    "build_classifier_prompt",
]
