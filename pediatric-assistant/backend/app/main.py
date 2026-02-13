"""
FastAPI 应用入口
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
import time
import asyncio

from app.config import settings
from app.utils.logger import setup_logging
from app.routers import chat, profile, auth
from app.services.profile_service import profile_service
from app.services.conversation_service import conversation_service
from app.services.conversation_state_service import conversation_state_service
from app.services.archive_service import archive_service
from app.middleware.performance import performance_monitor


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # startup
    setup_logging(debug=settings.DEBUG)
    logger.info(f"{settings.APP_NAME} v{settings.APP_VERSION} 启动中...")
    logger.info(f"调试模式: {settings.DEBUG}")
    logger.info(f"大模型: {settings.DEEPSEEK_MODEL}")
    if not settings.DEEPSEEK_API_KEY:
        logger.warning("未配置 DEEPSEEK_API_KEY，LLM/RAG 调用将失败")
    if not settings.SECRET_KEY:
        logger.warning("未配置 SECRET_KEY，请在生产环境中设置")
    profile_service.init_db()
    conversation_service.init_db()
    conversation_state_service.init_db()
    archive_service.init_db()
    asyncio.create_task(profile_service.start_worker())
    yield
    # shutdown
    logger.info(f"{settings.APP_NAME} 正在关闭...")
    performance_monitor.print_statistics()


# 创建FastAPI应用
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="智能儿科分诊与护理助手API",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 开发环境允许所有来源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# 性能监控中间件
app.middleware("http")(performance_monitor.log_request)


# 全局异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理"""
    logger.error(f"Global exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "code": 500,
            "message": "服务器内部错误，请稍后重试",
            "detail": str(exc) if settings.DEBUG else None,
        },
    )


# 注册路由
app.include_router(chat.router, prefix="/api/v1/chat", tags=["对话"])
app.include_router(profile.router, prefix="/api/v1/profile", tags=["健康档案"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["认证"])


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """避免浏览器请求 favicon.ico 时报错"""
    return JSONResponse(content={}, status_code=204)


@app.get("/")
async def root():
    """根路径"""
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy"}


@app.get("/metrics/performance")
async def get_performance_metrics():
    """获取性能指标"""
    return {
        "code": 0,
        "data": performance_monitor.get_statistics(),
    }


@app.get("/metrics/performance/summary")
async def get_performance_summary():
    """获取性能指标摘要"""
    return {
        "code": 0,
        "data": performance_monitor.get_summary(),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8001,
        reload=settings.DEBUG,
        log_level="info",
    )
