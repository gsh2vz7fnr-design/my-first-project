import os

from pydantic import BaseModel

class Settings(BaseModel):
    app_name: str = "my-ai-ppt"
    llm_enabled: bool = False
    openai_api_key: str = ""
    openai_base_url: str = "https://api.deepseek.com"
    openai_model: str = "deepseek-chat"


def _to_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


settings = Settings(
    llm_enabled=_to_bool(os.getenv("LLM_ENABLED", "false")),
    openai_api_key=os.getenv("OPENAI_API_KEY", ""),
    openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com"),
    openai_model=os.getenv("OPENAI_MODEL", "deepseek-chat"),
)
