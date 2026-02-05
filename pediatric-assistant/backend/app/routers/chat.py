"""
对话路由
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger
import json
from typing import AsyncGenerator

from app.models.user import ChatRequest, StreamChunk
from app.services.llm_service import llm_service
from app.services.triage_engine import triage_engine
from app.services.safety_filter import safety_filter
from app.services.rag_service import rag_service

router = APIRouter()


@router.post("/send")
async def send_message(request: ChatRequest):
    """
    发送消息（非流式）

    Args:
        request: 聊天请求

    Returns:
        dict: 响应结果
    """
    try:
        # 1. 检查处方意图
        if safety_filter.check_prescription_intent(request.message):
            return {
                "code": 0,
                "data": {
                    "conversation_id": request.conversation_id or "new",
                    "message": safety_filter.get_prescription_refusal_message(),
                    "sources": [],
                    "metadata": {"blocked": True, "reason": "prescription_intent"}
                }
            }

        # 2. 提取意图和实体
        intent_result = await llm_service.extract_intent_and_entities(
            user_input=request.message,
            context=None  # TODO: 从数据库加载用户档案
        )

        logger.info(f"意图识别结果: {intent_result}")

        # 3. 如果是分诊意图，进行分诊
        if intent_result.intent.type == "triage":
            # 检查危险信号
            danger_alert = triage_engine.check_danger_signals(intent_result.entities)
            if danger_alert:
                return {
                    "code": 0,
                    "data": {
                        "conversation_id": request.conversation_id or "new",
                        "message": danger_alert,
                        "sources": [],
                        "metadata": {
                            "intent": "triage",
                            "triage_level": "emergency",
                            "danger_signal": True
                        }
                    }
                }

            # 检查缺失槽位
            symptom = intent_result.entities.get("symptom", "")
            missing_slots = triage_engine.get_missing_slots(symptom, intent_result.entities)

            if missing_slots:
                # 需要追问
                follow_up = triage_engine.generate_follow_up_question(missing_slots)
                return {
                    "code": 0,
                    "data": {
                        "conversation_id": request.conversation_id or "new",
                        "message": follow_up,
                        "sources": [],
                        "metadata": {
                            "intent": "triage",
                            "need_follow_up": True,
                            "missing_slots": missing_slots
                        }
                    }
                }

            # 做出分诊决策
            decision = triage_engine.make_triage_decision(symptom, intent_result.entities)

            response_message = f"**{decision.reason}**\n\n{decision.action}"
            response_message = safety_filter.add_disclaimer(response_message)

            return {
                "code": 0,
                "data": {
                    "conversation_id": request.conversation_id or "new",
                    "message": response_message,
                    "sources": [],
                    "metadata": {
                        "intent": "triage",
                        "triage_level": decision.level,
                        "entities": intent_result.entities
                    }
                }
            }

        # 4. 其他意图（咨询、用药、护理）- 使用RAG
        rag_result = await rag_service.generate_answer_with_sources(
            query=request.message,
            context=None  # TODO: 从数据库加载用户档案
        )

        # 安全过滤
        safety_result = safety_filter.filter_output(rag_result.answer)
        if not safety_result.is_safe:
            return {
                "code": 0,
                "data": {
                    "conversation_id": request.conversation_id or "new",
                    "message": safety_result.fallback_message,
                    "sources": [],
                    "metadata": {"blocked": True, "reason": "safety_filter"}
                }
            }

        # 添加免责声明
        response_message = safety_filter.add_disclaimer(rag_result.answer)

        return {
            "code": 0,
            "data": {
                "conversation_id": request.conversation_id or "new",
                "message": response_message,
                "sources": [s.model_dump() for s in rag_result.sources],
                "metadata": {
                    "intent": intent_result.intent.type,
                    "has_source": rag_result.has_source
                }
            }
        }

    except Exception as e:
        logger.error(f"处理消息失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stream")
async def send_message_stream(request: ChatRequest):
    """
    发送消息（流式）

    Args:
        request: 聊天请求

    Returns:
        StreamingResponse: 流式响应
    """
    async def generate() -> AsyncGenerator[str, None]:
        """生成流式响应"""
        try:
            # 1. 检查处方意图
            if safety_filter.check_prescription_intent(request.message):
                chunk = StreamChunk(
                    type="content",
                    content=safety_filter.get_prescription_refusal_message()
                )
                yield f"data: {chunk.model_dump_json()}\n\n"
                yield "data: {\"type\": \"done\"}\n\n"
                return

            # 2. 提取意图和实体
            intent_result = await llm_service.extract_intent_and_entities(
                user_input=request.message,
                context=None
            )

            # 3. 如果是分诊意图
            if intent_result.intent.type == "triage":
                # 检查危险信号
                danger_alert = triage_engine.check_danger_signals(intent_result.entities)
                if danger_alert:
                    chunk = StreamChunk(type="content", content=danger_alert)
                    yield f"data: {chunk.model_dump_json()}\n\n"
                    yield "data: {\"type\": \"done\"}\n\n"
                    return

                # 检查缺失槽位
                symptom = intent_result.entities.get("symptom", "")
                missing_slots = triage_engine.get_missing_slots(symptom, intent_result.entities)

                if missing_slots:
                    follow_up = triage_engine.generate_follow_up_question(missing_slots)
                    chunk = StreamChunk(type="content", content=follow_up)
                    yield f"data: {chunk.model_dump_json()}\n\n"
                    yield "data: {\"type\": \"done\"}\n\n"
                    return

                # 做出分诊决策
                decision = triage_engine.make_triage_decision(symptom, intent_result.entities)
                response_message = f"**{decision.reason}**\n\n{decision.action}"
                response_message = safety_filter.add_disclaimer(response_message)

                # 分块发送
                chunk = StreamChunk(type="content", content=response_message)
                yield f"data: {chunk.model_dump_json()}\n\n"
                yield "data: {\"type\": \"done\"}\n\n"
                return

            # 4. 其他意图 - 使用LLM流式生成
            async for text_chunk in llm_service.generate_response_stream(
                prompt=request.message,
                context=None
            ):
                # 安全过滤
                safety_result = safety_filter.filter_output(text_chunk)
                if not safety_result.is_safe:
                    chunk = StreamChunk(
                        type="content",
                        content=safety_result.fallback_message
                    )
                    yield f"data: {chunk.model_dump_json()}\n\n"
                    yield "data: {\"type\": \"done\"}\n\n"
                    return

                chunk = StreamChunk(type="content", content=text_chunk)
                yield f"data: {chunk.model_dump_json()}\n\n"

            # 添加免责声明
            disclaimer_chunk = StreamChunk(
                type="content",
                content="\n\n*AI生成内容仅供参考，不作为医疗诊断依据。请以线下医生医嘱为准。*"
            )
            yield f"data: {disclaimer_chunk.model_dump_json()}\n\n"

            yield "data: {\"type\": \"done\"}\n\n"

        except Exception as e:
            logger.error(f"流式生成失败: {e}", exc_info=True)
            error_chunk = StreamChunk(
                type="content",
                content="抱歉，系统出现异常，请稍后重试。"
            )
            yield f"data: {error_chunk.model_dump_json()}\n\n"
            yield "data: {\"type\": \"done\"}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.get("/history/{conversation_id}")
async def get_conversation_history(conversation_id: str):
    """
    获取对话历史

    Args:
        conversation_id: 对话ID

    Returns:
        dict: 对话历史
    """
    # TODO: 从数据库加载对话历史
    return {
        "code": 0,
        "data": {
            "conversation_id": conversation_id,
            "messages": []
        }
    }
