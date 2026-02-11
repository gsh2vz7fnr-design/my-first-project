"""
配置文件
"""
import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置"""

    # 应用基础配置
    APP_NAME: str = "智能儿科分诊与护理助手"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # DeepSeek API配置
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    DEEPSEEK_MODEL: str = "deepseek-chat"  # deepseek-chat, deepseek-coder

    # 硅基流动API配置（用于Embedding）
    SILICONFLOW_API_KEY: Optional[str] = os.getenv("SILICONFLOW_API_KEY", "")
    SILICONFLOW_BASE_URL: str = "https://api.siliconflow.cn/v1"
    SILICONFLOW_EMBEDDING_MODEL: str = "BAAI/bge-m3"

    # 数据库配置
    BASE_DIR: Path = Path(__file__).resolve().parent
    DATA_DIR: Path = BASE_DIR / "data"
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:password@localhost:5432/pediatric_assistant"
    )
    SQLITE_DB_PATH: str = str(DATA_DIR / "pediatric_assistant.db")

    # Redis配置
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # 向量数据库配置
    VECTOR_DB_PATH: str = str(DATA_DIR / "vector_db")
    EMBEDDING_MODEL: str = "local"  # local 或 OpenAI 兼容的embedding模型

    # ChromaDB 配置
    USE_CHROMADB: bool = True  # 是否使用 ChromaDB（False 则使用内存检索）
    CHROMA_COLLECTION_NAME: str = "pediatric_knowledge_base"
    CHROMA_EMBEDDING_MODEL: str = "BAAI/bge-small-zh-v1.5"  # 中文向量模型
    CHROMA_PERSIST_DIR: Optional[str] = None  # None 表示使用默认路径（VECTOR_DB_PATH）
    CHROMADB_SEARCH_TOP_K: int = 50  # ChromaDB 初次召回数量

    # 安全配置
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    ALLOWED_ORIGINS: list = os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:3000,http://localhost:8000,http://127.0.0.1:3000,http://localhost:8080,http://127.0.0.1:8080"
    ).split(",")

    # 业务配置
    MAX_CONVERSATION_HISTORY: int = 20  # 最大对话历史条数
    SESSION_TIMEOUT: int = 1800  # 会话超时时间（秒）
    PROFILE_EXTRACT_DELAY: int = 1800  # 档案提取延迟（秒）

    # 流式输出配置
    STREAM_CHUNK_SIZE: int = 50  # 流式输出每次发送的字符数
    FIRST_TOKEN_TIMEOUT: float = 1.5  # 首字延迟目标（秒）

    # 限流配置
    RATE_LIMIT_PER_MINUTE: int = 20  # 每分钟最大请求数
    RATE_LIMIT_PER_DAY: int = 500  # 每天最大请求数

    # 知识库配置
    KNOWLEDGE_BASE_PATH: str = str(DATA_DIR / "knowledge_base")
    TOP_K_RETRIEVAL: int = 3  # RAG检索返回的文档数
    SIMILARITY_THRESHOLD: float = 0.3  # 相似度阈值

    # 分诊规则配置
    TRIAGE_RULES_PATH: str = str(DATA_DIR / "triage_rules")
    DANGER_SIGNALS_PATH: str = str(DATA_DIR / "triage_rules" / "danger_signals.json")
    SLOT_DEFINITIONS_PATH: str = str(DATA_DIR / "triage_rules" / "slot_definitions.json")

    # 违禁词配置
    BLACKLIST_PATH: str = str(DATA_DIR / "blacklist")
    GENERAL_BLACKLIST_FILE: str = str(DATA_DIR / "blacklist" / "general_blacklist.txt")
    MEDICAL_BLACKLIST_FILE: str = str(DATA_DIR / "blacklist" / "medical_blacklist.txt")

    class Config:
        env_file = ".env"
        case_sensitive = True


# 创建全局配置实例
settings = Settings()
