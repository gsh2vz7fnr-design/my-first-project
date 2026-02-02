"""
简化版后端 - 不依赖ChromaDB
适用于快速演示和测试
"""
import sys
sys.path.append('.')

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import os
from dotenv import load_dotenv

from app.danger_detector import DangerDetector
from app.intent_router import IntentRouter, IntentType
from app.llm_service import LLMService
from app.safety_guard import SafetyGuard

# 加载环境变量
load_dotenv()

# 初始化FastAPI应用
app = FastAPI(
    title="AI育儿助手API（简化版）",
    description="基于LLM的智能育儿助手 - 无RAG版本",
    version="1.0.0-simple"
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
safety_guard = SafetyGuard()

# 初始化LLM服务
try:
    llm_service = LLMService()
    llm_available = True
    print("✅ LLM服务初始化成功")
except Exception as e:
    llm_available = False
    print(f"⚠️ LLM服务初始化失败: {e}")
    print("💡 提示：请配置DEEPSEEK_API_KEY或OPENAI_API_KEY环境变量")


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
        "message": "AI育儿助手API（简化版）",
        "version": "1.0.0-simple",
        "status": "running",
        "llm_available": llm_available,
        "note": "此版本不包含RAG知识库功能"
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    聊天接口 - 核心业务逻辑（简化版）

    处理流程：
    1. 危险信号检测（最高优先级）
    2. 意图识别
    3. LLM生成回复（无RAG检索）
    4. 安全检查
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

    # Step 3: LLM生成回复（无RAG）
    if not llm_available:
        # LLM不可用时的降级响应
        response = f"""
感谢您的提问："{user_message}"

⚠️ **LLM服务未配置**

要获得AI回复，请配置API密钥：

1. 获取DeepSeek API密钥：https://platform.deepseek.com/
2. 创建.env文件：
   ```
   DEEPSEEK_API_KEY=sk-your-key-here
   ```
3. 重启后端服务

💡 提示：这是简化版后端，不包含RAG知识库功能。

意图识别结果：{intent_result['description']}
置信度：{intent_result['confidence']:.2f}
"""
    else:
        # 使用LLM生成回复
        if intent_type == IntentType.EMERGENCY_TRIAGE:
            response = llm_service.generate_triage_response(
                user_message,
                context=""  # 简化版无RAG
            )
        else:
            response = llm_service.generate_response(
                user_message,
                context="",  # 简化版无RAG
                intent=intent_type.value
            )

        # Step 4: 安全检查
        safety_result = safety_guard.check_response(response)

        if not safety_result["is_safe"]:
            response = safety_guard.sanitize_response(response)

        # 确保包含免责声明
        response = safety_guard.add_disclaimer(response)

    return ChatResponse(
        response=response,
        intent=intent_type.value,
        is_danger=False,
        metadata={
            "confidence": intent_result["confidence"],
            "llm_available": llm_available,
            "version": "simple"
        }
    )


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "llm_available": llm_available
    }


if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*60)
    print("🚀 启动AI育儿助手后端服务（简化版）")
    print("="*60)
    print(f"✅ 危险信号检测：已启用")
    print(f"✅ 意图识别：已启用")
    print(f"✅ 安全护栏：已启用")
    print(f"{'✅' if llm_available else '⚠️'} LLM服务：{'已启用' if llm_available else '未配置'}")
    print(f"❌ RAG知识库：未启用（简化版）")
    print("="*60)
    print("📖 API文档：http://localhost:8000/docs")
    print("🏥 健康检查：http://localhost:8000/health")
    print("="*60 + "\n")

    uvicorn.run(app, host="0.0.0.0", port=8000)
