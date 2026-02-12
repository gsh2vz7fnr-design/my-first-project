"""
统一日志系统

功能：
- 双写模式：Console (彩色) + File (每天轮转，保留 7 天)
- 格式：[Time] [Level] [SessionID] [Module] Message
- 通过 contextvars 注入 SessionID，实现跨异步调用追踪
- get_logger(name) 工厂方法，返回带模块名绑定的 logger
"""
import sys
from contextvars import ContextVar
from pathlib import Path

from loguru import logger

# ── Session ID 上下文变量 ──────────────────────────────────
_session_id_var: ContextVar[str] = ContextVar("session_id", default="-")


def set_session_id(session_id: str) -> None:
    """设置当前异步上下文的 session_id（在请求入口处调用）"""
    _session_id_var.set(session_id)


def get_session_id() -> str:
    """获取当前上下文的 session_id"""
    return _session_id_var.get()


# ── 日志格式 ───────────────────────────────────────────────
_CONSOLE_FORMAT = (
    "<green>{time:HH:mm:ss.SSS}</green> "
    "<level>{level: <8}</level> "
    "<cyan>[{extra[sid]}]</cyan> "
    "<blue>[{extra[module]}]</blue> "
    "{message}"
)

_FILE_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} "
    "{level: <8} "
    "[{extra[sid]}] "
    "[{extra[module]}] "
    "{message}"
)

_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
_initialized = False


# ── 初始化 ─────────────────────────────────────────────────
def setup_logging(debug: bool = False) -> None:
    """
    初始化日志系统（应用启动时调用一次）

    Args:
        debug: 是否启用 DEBUG 级别输出
    """
    global _initialized
    if _initialized:
        return

    # 移除 loguru 默认 handler
    logger.remove()

    level = "DEBUG" if debug else "INFO"

    # Console handler
    logger.add(
        sys.stderr,
        format=_CONSOLE_FORMAT,
        level=level,
        colorize=True,
        filter=_inject_extras,
    )

    # File handler（每天轮转，保留 7 天，UTF-8）
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger.add(
        str(_LOG_DIR / "app_{time:YYYY-MM-DD}.log"),
        format=_FILE_FORMAT,
        level="DEBUG",  # 文件始终记录 DEBUG
        rotation="00:00",
        retention="7 days",
        encoding="utf-8",
        filter=_inject_extras,
    )

    _initialized = True
    logger.bind(module="Logger", sid="-").info(
        "日志系统初始化完成 | level={} | dir={}", level, _LOG_DIR
    )


def _inject_extras(record: dict) -> bool:
    """为每条日志注入 sid 和 module（如果缺失）"""
    extra = record["extra"]
    if "sid" not in extra:
        extra["sid"] = _session_id_var.get()
    if "module" not in extra:
        extra["module"] = "Root"
    return True


# ── 工厂方法 ───────────────────────────────────────────────
def get_logger(name: str):
    """
    获取带模块名绑定的 logger

    用法:
        from app.utils.logger import get_logger
        log = get_logger("ChatPipeline")
        log.info("Processing message: {}", msg)

    日志输出示例:
        11:23:45.678 INFO     [conv_abc123] [ChatPipeline] Processing message: ...
    """
    def _dynamic_bind(record):
        """动态绑定 sid（每次日志调用时读取 contextvars）"""
        record["extra"]["sid"] = _session_id_var.get()
        record["extra"]["module"] = name
        return True

    return logger.bind(module=name).patch(
        lambda record: record["extra"].update(
            sid=_session_id_var.get(),
            module=name,
        )
    )
