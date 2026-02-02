"""
FastAPI主程序
整合所有模块，提供API接口
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import os
from dotenv import load_dotenv

from danger_detector import DangerDetector
from intent_router import IntentRouter, IntentType
from rag_engine import RAGEngine
from llm_service import LLMService
from safety_guard import SafetyGuard

# 加载环境变量
load_dotenv()

# 初始化FastAPI应用
app = FastAPI(
    title="AI育儿助手API",
    description="基于LLM + RAG的智能育儿助手",
    version="1.0.0"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化各个模块
danger_detector = DangerDetector()
intent_router = IntentRouter()
rag_engine = RAGEngine()
llm_service = LLMService()
safety_guard = SafetyGuard()


# 请求模型
class ChatRequest(BaseModel):
    message: str
    user_id: Optional[str] = None


# 响应模型
class ChatResponse(BaseModel):
    response: str
    intent: str
    is_danger: bool
    metadata: dict


@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "AI育儿助手API",
        "version": "1.0.0",
        "status": "running"
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    聊天接口 - 核心业务逻辑

    处理流程：
    1. 危险信号检测（最高优先级）
    2. 意图识别
    3. RAG检索
    4. LLM生成回复
    5. 安全检查
    """
    user_message = request.message

    # Step 1: 危险信号检测
    danger_result = danger_detector.detect(user_message)

    if danger_result:
        # 检测到危险信号，立即返回警告
        response = danger_detector.format_danger_response(danger_result)
        return ChatResponse(
            response=response,
            intent="emergency",
            is_danger=True,
            metadata=danger_result
        )

    # Step 2: 意图识别
    intent_result = intent_router.route(user_message)
    intent_type = intent_result["intent"]

    # Step 3: RAG检索相关知识
    context = rag_engine.get_context(user_message, top_k=3)

    # Step 4: 根据意图生成回复
    if intent_type == IntentType.EMERGENCY_TRIAGE:
        # 分诊场景
        response = llm_service.generate_triage_response(
            user_message,
            context
        )
    else:
        # 日常护理或用药咨询
        response = llm_service.generate_response(
            user_message,
            context,
            intent_type.value
        )

    # Step 5: 安全检查
    safety_result = safety_guard.check_response(response)

    if not safety_result["is_safe"]:
        # 如果不安全，进行清理
        response = safety_guard.sanitize_response(response)

    # 确保包含免责声明
    response = safety_guard.add_disclaimer(response)

    return ChatResponse(
        response=response,
        intent=intent_type.value,
        is_danger=False,
        metadata={
            "confidence": intent_result["confidence"],
            "context_found": bool(context),
            "safety_issues": safety_result["issues"]
        }
    )


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
