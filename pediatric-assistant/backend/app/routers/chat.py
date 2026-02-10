"""
对话路由
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger
import json
import asyncio
import uuid
from typing import AsyncGenerator, Optional, List, Dict

from app.models.user import ChatRequest, StreamChunk
from app.services.llm_service import llm_service
from app.services.triage_engine import triage_engine
from app.services.safety_filter import safety_filter
from app.services.stream_filter import StreamSafetyFilter
from app.services.rag_service import rag_service
from app.config import settings
from app.services.profile_service import profile_service
from app.services.conversation_service import conversation_service

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
        # 0. 加载用户档案
        profile = profile_service.get_profile(request.user_id)
        context = {
            "baby_info": profile.baby_info.model_dump(),
            "allergy_history": [x.model_dump() for x in profile.allergy_history],
            "medical_history": [x.model_dump() for x in profile.medical_history]
        }

        # 1. 检查处方意图
        if safety_filter.check_prescription_intent(request.message):
            conversation_id = request.conversation_id or f"conv_{uuid.uuid4().hex[:12]}"
            conversation_service.append_message(conversation_id, request.user_id, "user", request.message)
            return {
                "code": 0,
                "data": {
                    "conversation_id": conversation_id,
                    "message": safety_filter.get_prescription_refusal_message(),
                    "sources": [],
                    "metadata": {"blocked": True, "reason": "prescription_intent"}
                }
            }

        # 2. 提取意图和实体
        intent_result = await llm_service.extract_intent_and_entities(
            user_input=request.message,
            context=context
        )

        logger.info(f"意图识别结果: {intent_result}")

        # 2.5a 问候/闲聊路由
        if intent_result.intent.type == "greeting":
            conversation_id = request.conversation_id or f"conv_{uuid.uuid4().hex[:12]}"
            greeting_reply = (
                "您好！我是智能儿科助手 👋\n\n"
                "我可以帮您：\n"
                "• 评估宝宝的症状（发烧、咳嗽、腹泻等）\n"
                "• 提供科学的居家护理建议\n"
                "• 判断是否需要就医\n\n"
                "请描述宝宝的情况，例如：「宝宝8个月，发烧38.5度，精神不好」"
            )
            greeting_reply = safety_filter.add_disclaimer(greeting_reply)
            conversation_service.append_message(conversation_id, request.user_id, "user", request.message)
            conversation_service.append_message(conversation_id, request.user_id, "assistant", greeting_reply)
            return {
                "code": 0,
                "data": {
                    "conversation_id": conversation_id,
                    "message": greeting_reply,
                    "sources": [],
                    "metadata": {"intent": "greeting"}
                }
            }

        # 2.5b Slot-filling 路由
        if intent_result.intent.type == "slot_filling":
            conversation_id = request.conversation_id or f"conv_{uuid.uuid4().hex[:12]}"
            conversation_service.append_message(conversation_id, request.user_id, "user", request.message)

            merged_entities = intent_result.entities.copy()
            if not merged_entities.get("symptom"):
                history = conversation_service.get_history(conversation_id, limit=10)
                recovered_symptom = _recover_symptom_from_history(history)
                if recovered_symptom:
                    merged_entities["symptom"] = recovered_symptom

            symptom = merged_entities.get("symptom", "")
            if not symptom:
                follow_up = "为了继续分诊，请先告诉我宝宝的主要症状（如发烧、咳嗽、腹泻等）。"
                conversation_service.append_message(conversation_id, request.user_id, "assistant", follow_up)
                return {
                    "code": 0,
                    "data": {
                        "conversation_id": conversation_id,
                        "message": follow_up,
                        "sources": [],
                        "metadata": {
                            "intent": "slot_filling",
                            "need_follow_up": True,
                            "missing_slots": ["symptom"]
                        }
                    }
                }

            danger_alert = triage_engine.check_danger_signals(merged_entities)
            if danger_alert:
                conversation_service.append_message(conversation_id, request.user_id, "assistant", danger_alert)
                return {
                    "code": 0,
                    "data": {
                        "conversation_id": conversation_id,
                        "message": danger_alert,
                        "sources": [],
                        "metadata": {
                            "intent": "triage",
                            "origin_intent": "slot_filling",
                            "triage_level": "emergency",
                            "danger_signal": True
                        }
                    }
                }

            missing_slots = triage_engine.get_missing_slots(
                symptom,
                merged_entities,
                profile_context=context
            )

            if missing_slots:
                follow_up = triage_engine.generate_follow_up_question(symptom, missing_slots)
                conversation_service.append_message(conversation_id, request.user_id, "assistant", follow_up)
                return {
                    "code": 0,
                    "data": {
                        "conversation_id": conversation_id,
                        "message": follow_up,
                        "sources": [],
                        "metadata": {
                            "intent": "triage",
                            "origin_intent": "slot_filling",
                            "need_follow_up": True,
                            "missing_slots": missing_slots
                        }
                    }
                }

            decision = triage_engine.make_triage_decision(symptom, merged_entities)
            response_message = f"**{decision.reason}**\n\n{decision.action}"
            response_message = safety_filter.add_disclaimer(response_message)
            conversation_service.append_message(conversation_id, request.user_id, "assistant", response_message)

            return {
                "code": 0,
                "data": {
                    "conversation_id": conversation_id,
                    "message": response_message,
                    "sources": [],
                    "metadata": {
                        "intent": "triage",
                        "origin_intent": "slot_filling",
                        "triage_level": decision.level,
                        "entities": merged_entities
                    }
                }
            }

        # 3. 如果是分诊意图，进行分诊
        if intent_result.intent.type == "triage":
            conversation_id = request.conversation_id or f"conv_{uuid.uuid4().hex[:12]}"
            conversation_service.append_message(conversation_id, request.user_id, "user", request.message)
            # 检查危险信号
            danger_alert = triage_engine.check_danger_signals(intent_result.entities)
            if danger_alert:
                conversation_service.append_message(conversation_id, request.user_id, "assistant", danger_alert)
                return {
                    "code": 0,
                    "data": {
                        "conversation_id": conversation_id,
                        "message": danger_alert,
                        "sources": [],
                        "metadata": {
                            "intent": "triage",
                            "triage_level": "emergency",
                            "danger_signal": True
                        }
                    }
                }

            # 检查缺失槽位（传入档案上下文以支持自动填充）
            symptom = intent_result.entities.get("symptom", "")
            missing_slots = triage_engine.get_missing_slots(
                symptom,
                intent_result.entities,
                profile_context=context
            )

            if missing_slots:
                # 需要追问
                follow_up = triage_engine.generate_follow_up_question(symptom, missing_slots)
                conversation_service.append_message(conversation_id, request.user_id, "assistant", follow_up)
                return {
                    "code": 0,
                    "data": {
                        "conversation_id": conversation_id,
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
            conversation_service.append_message(conversation_id, request.user_id, "assistant", response_message)

            return {
                "code": 0,
                "data": {
                    "conversation_id": conversation_id,
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
        # 检测情绪并添加情绪承接
        emotion_support = llm_service.detect_emotion(request.message)

        rag_result = await rag_service.generate_answer_with_sources(
            query=request.message,
            context=context
        )

        # 安全过滤
        safety_result = safety_filter.filter_output(rag_result.answer)
        if not safety_result.is_safe:
            conversation_id = request.conversation_id or f"conv_{uuid.uuid4().hex[:12]}"
            conversation_service.append_message(conversation_id, request.user_id, "user", request.message)
            conversation_service.append_message(conversation_id, request.user_id, "assistant", safety_result.fallback_message)
            return {
                "code": 0,
                "data": {
                    "conversation_id": conversation_id,
                    "message": safety_result.fallback_message,
                    "sources": [],
                    "metadata": {"blocked": True, "reason": "safety_filter"}
                }
            }

        # 添加情绪承接（如果有）
        if emotion_support:
            response_message = f"{emotion_support}\n\n{rag_result.answer}"
        else:
            response_message = rag_result.answer

        # 添加免责声明
        response_message = safety_filter.add_disclaimer(response_message)
        conversation_id = request.conversation_id or f"conv_{uuid.uuid4().hex[:12]}"
        conversation_service.append_message(conversation_id, request.user_id, "user", request.message)
        conversation_service.append_message(conversation_id, request.user_id, "assistant", response_message)

        # 安排延迟档案提取（30分钟后）
        asyncio.create_task(
            profile_service.schedule_delayed_extraction(
                user_id=request.user_id,
                conversation_id=conversation_id,
                delay_minutes=30
            )
        )

        # 添加来源元数据
        sources_metadata = rag_service.get_sources_metadata(rag_result.sources)
        return {
            "code": 0,
            "data": {
                "conversation_id": conversation_id,
                "message": response_message,
                "sources": sources_metadata,
                "metadata": {
                    "intent": intent_result.intent.type,
                    "has_source": rag_result.has_source,
                    "emotion_detected": emotion_support is not None
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
            conversation_id = request.conversation_id or f"conv_{request.user_id}_{int(asyncio.get_event_loop().time())}"

            # 0. 加载用户档案
            profile = profile_service.get_profile(request.user_id)
            context = {
                "baby_info": profile.baby_info.model_dump(),
                "allergy_history": [x.model_dump() for x in profile.allergy_history],
                "medical_history": [x.model_dump() for x in profile.medical_history]
            }

            # 1. 检查处方意图
            if safety_filter.check_prescription_intent(request.message):
                # Send metadata first
                metadata_chunk = StreamChunk(
                    type="metadata",
                    metadata={"blocked": True, "reason": "prescription_intent"}
                )
                yield f"data: {metadata_chunk.model_dump_json()}\n\n"

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
                context=context
            )

            # 2.5a 问候/闲聊路由
            if intent_result.intent.type == "greeting":
                greeting_reply = (
                    "您好！我是智能儿科助手 👋\n\n"
                    "我可以帮您：\n"
                    "• 评估宝宝的症状（发烧、咳嗽、腹泻等）\n"
                    "• 提供科学的居家护理建议\n"
                    "• 判断是否需要就医\n\n"
                    "请描述宝宝的情况，例如：「宝宝8个月，发烧38.5度，精神不好」"
                )
                greeting_reply = safety_filter.add_disclaimer(greeting_reply)
                conversation_service.append_message(conversation_id, request.user_id, "user", request.message)
                conversation_service.append_message(conversation_id, request.user_id, "assistant", greeting_reply)

                metadata_chunk = StreamChunk(type="metadata", metadata={"intent": "greeting"})
                yield f"data: {metadata_chunk.model_dump_json()}\n\n"

                chunk = StreamChunk(type="content", content=greeting_reply)
                yield f"data: {chunk.model_dump_json()}\n\n"
                yield "data: {\"type\": \"done\"}\n\n"
                return

            # 2.5b Slot-filling 路由
            if intent_result.intent.type == "slot_filling":
                conversation_service.append_message(conversation_id, request.user_id, "user", request.message)

                merged_entities = intent_result.entities.copy()
                if not merged_entities.get("symptom"):
                    history = conversation_service.get_history(conversation_id, limit=10)
                    recovered_symptom = _recover_symptom_from_history(history)
                    if recovered_symptom:
                        merged_entities["symptom"] = recovered_symptom

                symptom = merged_entities.get("symptom", "")
                if not symptom:
                    follow_up = "为了继续分诊，请先告诉我宝宝的主要症状（如发烧、咳嗽、腹泻等）。"
                    conversation_service.append_message(conversation_id, request.user_id, "assistant", follow_up)
                    metadata_chunk = StreamChunk(
                        type="metadata",
                        metadata={
                            "intent": "slot_filling",
                            "need_follow_up": True,
                            "missing_slots": ["symptom"]
                        }
                    )
                    yield f"data: {metadata_chunk.model_dump_json()}\n\n"

                    chunk = StreamChunk(type="content", content=follow_up)
                    yield f"data: {chunk.model_dump_json()}\n\n"
                    yield "data: {\"type\": \"done\"}\n\n"
                    return

                danger_alert = triage_engine.check_danger_signals(merged_entities)
                if danger_alert:
                    conversation_service.append_message(conversation_id, request.user_id, "assistant", danger_alert)

                    metadata_chunk = StreamChunk(
                        type="metadata",
                        metadata={
                            "intent": "triage",
                            "origin_intent": "slot_filling",
                            "triage_level": "emergency",
                            "danger_signal": True
                        }
                    )
                    yield f"data: {metadata_chunk.model_dump_json()}\n\n"

                    chunk = StreamChunk(type="content", content=danger_alert)
                    yield f"data: {chunk.model_dump_json()}\n\n"
                    yield "data: {\"type\": \"done\"}\n\n"
                    return

                missing_slots = triage_engine.get_missing_slots(
                    symptom,
                    merged_entities,
                    profile_context=context
                )

                if missing_slots:
                    follow_up = triage_engine.generate_follow_up_question(symptom, missing_slots)
                    conversation_service.append_message(conversation_id, request.user_id, "assistant", follow_up)

                    slot_definitions = {}
                    for slot in missing_slots:
                        slot_definitions[slot] = {
                            "type": _get_slot_type(slot),
                            "label": _get_slot_label(slot),
                            "required": True,
                            "options": _get_slot_options(slot),
                            "min": _get_slot_min(slot),
                            "max": _get_slot_max(slot),
                            "step": _get_slot_step(slot)
                        }

                    metadata_chunk = StreamChunk(
                        type="metadata",
                        metadata={
                            "intent": "triage",
                            "origin_intent": "slot_filling",
                            "need_follow_up": True,
                            "missing_slots": slot_definitions
                        }
                    )
                    yield f"data: {metadata_chunk.model_dump_json()}\n\n"

                    chunk = StreamChunk(type="content", content=follow_up)
                    yield f"data: {chunk.model_dump_json()}\n\n"
                    yield "data: {\"type\": \"done\"}\n\n"
                    return

                decision = triage_engine.make_triage_decision(symptom, merged_entities)
                response_message = f"**{decision.reason}**\n\n{decision.action}"
                response_message = safety_filter.add_disclaimer(response_message)
                conversation_service.append_message(conversation_id, request.user_id, "assistant", response_message)

                metadata_chunk = StreamChunk(
                    type="metadata",
                    metadata={
                        "intent": "triage",
                        "origin_intent": "slot_filling",
                        "triage_level": decision.level,
                        "entities": merged_entities
                    }
                )
                yield f"data: {metadata_chunk.model_dump_json()}\n\n"

                asyncio.create_task(
                    profile_service.schedule_delayed_extraction(
                        user_id=request.user_id,
                        conversation_id=conversation_id,
                        delay_minutes=30
                    )
                )

                chunk_size = settings.STREAM_CHUNK_SIZE
                for i in range(0, len(response_message), chunk_size):
                    text_chunk = response_message[i:i + chunk_size]
                    chunk = StreamChunk(type="content", content=text_chunk)
                    yield f"data: {chunk.model_dump_json()}\n\n"

                yield "data: {\"type\": \"done\"}\n\n"
                return

            # 3. 如果是分诊意图
            if intent_result.intent.type == "triage":
                conversation_service.append_message(conversation_id, request.user_id, "user", request.message)

                # 检查危险信号
                danger_alert = triage_engine.check_danger_signals(intent_result.entities)
                if danger_alert:
                    conversation_service.append_message(conversation_id, request.user_id, "assistant", danger_alert)

                    metadata_chunk = StreamChunk(
                        type="metadata",
                        metadata={
                            "intent": "triage",
                            "triage_level": "emergency",
                            "danger_signal": True
                        }
                    )
                    yield f"data: {metadata_chunk.model_dump_json()}\n\n"

                    chunk = StreamChunk(type="content", content=danger_alert)
                    yield f"data: {chunk.model_dump_json()}\n\n"
                    yield "data: {\"type\": \"done\"}\n\n"
                    return

                # 检查缺失槽位
                symptom = intent_result.entities.get("symptom", "")
                missing_slots = triage_engine.get_missing_slots(
                    symptom,
                    intent_result.entities,
                    profile_context=context
                )

                if missing_slots:
                    follow_up = triage_engine.generate_follow_up_question(symptom, missing_slots)
                    conversation_service.append_message(conversation_id, request.user_id, "assistant", follow_up)

                    slot_definitions = {}
                    for slot in missing_slots:
                        slot_definitions[slot] = {
                            "type": _get_slot_type(slot),
                            "label": _get_slot_label(slot),
                            "required": True,
                            "options": _get_slot_options(slot),
                            "min": _get_slot_min(slot),
                            "max": _get_slot_max(slot),
                            "step": _get_slot_step(slot)
                        }

                    metadata_chunk = StreamChunk(
                        type="metadata",
                        metadata={
                            "intent": "triage",
                            "need_follow_up": True,
                            "missing_slots": slot_definitions
                        }
                    )
                    yield f"data: {metadata_chunk.model_dump_json()}\n\n"

                    chunk = StreamChunk(type="content", content=follow_up)
                    yield f"data: {chunk.model_dump_json()}\n\n"
                    yield "data: {\"type\": \"done\"}\n\n"
                    return

                decision = triage_engine.make_triage_decision(symptom, intent_result.entities)
                response_message = f"**{decision.reason}**\n\n{decision.action}"
                response_message = safety_filter.add_disclaimer(response_message)
                conversation_service.append_message(conversation_id, request.user_id, "assistant", response_message)

                metadata_chunk = StreamChunk(
                    type="metadata",
                    metadata={
                        "intent": "triage",
                        "triage_level": decision.level,
                        "entities": intent_result.entities
                    }
                )
                yield f"data: {metadata_chunk.model_dump_json()}\n\n"

                asyncio.create_task(
                    profile_service.schedule_delayed_extraction(
                        user_id=request.user_id,
                        conversation_id=conversation_id,
                        delay_minutes=30
                    )
                )

                chunk_size = settings.STREAM_CHUNK_SIZE
                for i in range(0, len(response_message), chunk_size):
                    text_chunk = response_message[i:i + chunk_size]
                    chunk = StreamChunk(type="content", content=text_chunk)
                    yield f"data: {chunk.model_dump_json()}\n\n"

                yield "data: {\"type\": \"done\"}\n\n"
                return

            # 4. 其他意图 - 使用RAG生成完整答案后再流式输出
            conversation_service.append_message(conversation_id, request.user_id, "user", request.message)

            # 检测情绪并添加情绪承接
            emotion_support = llm_service.detect_emotion(request.message)

            rag_result = await rag_service.generate_answer_with_sources(
                query=request.message,
                context=context
            )

            # 添加情绪承接（如果有）
            if emotion_support:
                response_message = f"{emotion_support}\n\n{rag_result.answer}"
            else:
                response_message = rag_result.answer

            # 添加免责声明
            response_message = safety_filter.add_disclaimer(response_message)

            # Send metadata
            # 添加来源元数据
            sources_metadata = rag_service.get_sources_metadata(rag_result.sources)
            metadata_chunk = StreamChunk(
                type="metadata",
                metadata={
                    "intent": intent_result.intent.type,
                    "has_source": rag_result.has_source,
                    "emotion_detected": emotion_support is not None,
                    "sources": sources_metadata
                }
            )
            yield f"data: {metadata_chunk.model_dump_json()}\n\n"

            asyncio.create_task(
                profile_service.schedule_delayed_extraction(
                    user_id=request.user_id,
                    conversation_id=conversation_id,
                    delay_minutes=30
                )
            )

            # 流式安全检查 - 在输出过程中实时检测违禁词
            stream_filter = StreamSafetyFilter()
            full_output = ""
            chunk_size = settings.STREAM_CHUNK_SIZE
            for i in range(0, len(response_message), chunk_size):
                text_chunk = response_message[i:i + chunk_size]

                # 检查当前块是否包含违禁词
                safety_check = stream_filter.check_chunk(text_chunk)
                if safety_check.should_abort:
                    # 发送中止信号和安全警示
                    abort_chunk = StreamChunk(type="abort", content=safety_check.fallback_message)
                    yield f"data: {abort_chunk.model_dump_json()}\n\n"
                    yield "data: {\"type\": \"done\"}\n\n"
                    # 记录安全拦截
                    conversation_service.append_message(conversation_id, request.user_id, "assistant", safety_check.fallback_message)
                    return

                full_output += text_chunk
                chunk = StreamChunk(type="content", content=text_chunk)
                yield f"data: {chunk.model_dump_json()}\n\n"

            conversation_service.append_message(conversation_id, request.user_id, "assistant", full_output)
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
    try:
        messages = conversation_service.get_history(conversation_id)
        return {
            "code": 0,
            "data": {
                "conversation_id": conversation_id,
                "messages": messages
            }
        }
    except Exception as e:
        logger.error(f"获取对话历史失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/source/{entry_id}")
async def get_source_snippet(entry_id: str):
    """
    获取知识库原文片段

    Args:
        entry_id: 知识库条目ID

    Returns:
        dict: 原文片段
    """
    try:
        entry = rag_service.get_entry_by_id(entry_id)
        if not entry:
            raise HTTPException(status_code=404, detail="来源未找到")

        return {
            "code": 0,
            "data": {
                "id": entry.get("id"),
                "title": entry.get("title"),
                "source": entry.get("source"),
                "content": entry.get("content"),
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取来源失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============ Helper Functions ============


def _recover_symptom_from_history(history: List[Dict[str, str]]) -> Optional[str]:
    """从对话历史中恢复最近的症状"""
    for item in reversed(history):
        if item.get("role") != "user":
            continue
        content = (item.get("content") or "").strip()
        if not content:
            continue
        result = llm_service._extract_intent_and_entities_fallback(content)
        symptom = result.entities.get("symptom")
        if symptom:
            return symptom
    return None

def _get_slot_type(slot_name: str) -> str:
    """Get slot input type"""
    slot_type_map = {
        "age_months": "number",
        "temperature": "number",
        "duration": "text",
        "frequency": "text",
        "mental_state": "select",
        "accompanying_symptoms": "multiselect",
        "fall_height": "select",
        "stool_character": "select",
        "cough_type": "select",
        "rash_location": "select",
        "rash_appearance": "select",
        "cry_pattern": "select",
    }
    return slot_type_map.get(slot_name, "text")


def _get_slot_label(slot_name: str) -> str:
    """Get slot display label"""
    slot_labels = {
        "age_months": "宝宝月龄",
        "temperature": "体温（°C）",
        "duration": "持续时间",
        "frequency": "频率/次数",
        "mental_state": "精神状态",
        "accompanying_symptoms": "伴随症状",
        "fall_height": "坠落高度",
        "stool_character": "大便性状",
        "cough_type": "咳嗽类型",
        "rash_location": "皮疹位置",
        "rash_appearance": "皮疹外观",
        "cry_pattern": "哭闹模式",
    }
    return slot_labels.get(slot_name, slot_name)


def _get_slot_options(slot_name: str) -> list:
    """Get slot options for select/multiselect types"""
    slot_options = {
        "mental_state": [
            {"value": "正常", "label": "正常玩耍"},
            {"value": "精神差", "label": "精神差/蔫"},
            {"value": "嗜睡", "label": "嗜睡"},
            {"value": "烦躁", "label": "烦躁不安"},
            {"value": "昏迷", "label": "昏迷"},
        ],
        "accompanying_symptoms": [
            {"value": "咳嗽", "label": "咳嗽"},
            {"value": "呕吐", "label": "呕吐"},
            {"value": "腹泻", "label": "腹泻"},
            {"value": "皮疹", "label": "皮疹"},
            {"value": "呼吸急促", "label": "呼吸急促"},
            {"value": "抽搐", "label": "抽搐"},
            {"value": "无", "label": "无其他症状"},
        ],
        "fall_height": [
            {"value": "床", "label": "床（<50cm）"},
            {"value": "沙发", "label": "沙发（<100cm）"},
            {"value": "楼梯", "label": "楼梯（>100cm）"},
            {"value": "窗户", "label": "窗户/阳台（>200cm）"},
            {"value": "其他", "label": "其他"},
        ],
        "stool_character": [
            {"value": "水样", "label": "水样便"},
            {"value": "糊状", "label": "糊状便"},
            {"value": "黏液", "label": "黏液便"},
            {"value": "脓血", "label": "脓血便"},
            {"value": "脂肪", "label": "脂肪便（奶瓣）"},
        ],
        "cough_type": [
            {"value": "干咳", "label": "干咳"},
            {"value": "有痰", "label": "有痰咳"},
            {"value": "犬吠样", "label": "犬吠样咳嗽"},
            {"value": "痉挛性", "label": "痉挛性咳嗽"},
        ],
        "rash_location": [
            {"value": "面部", "label": "面部"},
            {"value": "躯干", "label": "躯干"},
            {"value": "四肢", "label": "四肢"},
            {"value": "全身", "label": "全身"},
            {"value": "尿布区", "label": "尿布区"},
        ],
        "rash_appearance": [
            {"value": "红点", "label": "红点/红斑"},
            {"value": "水泡", "label": "水泡"},
            {"value": "脓包", "label": "脓包"},
            {"value": "脱皮", "label": "脱皮"},
            {"value": "紫癜", "label": "紫癜"},
        ],
        "cry_pattern": [
            {"value": "间歇性", "label": "间歇性"},
            {"value": "持续性", "label": "持续性"},
            {"value": "尖叫样", "label": "尖叫样哭"},
            {"value": "呻吟", "label": "呻吟"},
        ],
    }
    return slot_options.get(slot_name, [])


def _get_slot_min(slot_name: str) -> float:
    """Get minimum value for numeric slots"""
    slot_min = {
        "age_months": 0,
        "temperature": 35.0,
    }
    return slot_min.get(slot_name)


def _get_slot_max(slot_name: str) -> float:
    """Get maximum value for numeric slots"""
    slot_max = {
        "age_months": 216,  # 18 years
        "temperature": 42.0,
    }
    return slot_max.get(slot_name)


def _get_slot_step(slot_name: str) -> float:
    """Get step value for numeric slots"""
    slot_step = {
        "age_months": 1,
        "temperature": 0.1,
    }
    return slot_step.get(slot_name)


@router.get("/conversations/{user_id}")
async def get_user_conversations(user_id: str):
    """
    获取用户的所有对话

    Args:
        user_id: 用户ID

    Returns:
        dict: 对话列表
    """
    try:
        conversations = conversation_service.get_user_conversations(user_id)
        return {
            "code": 0,
            "data": {
                "conversations": conversations,
                "total": len(conversations)
            }
        }
    except Exception as e:
        logger.error(f"获取对话列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/conversations/{user_id}/{conversation_id}")
async def delete_conversation(user_id: str, conversation_id: str):
    """
    删除指定对话

    Args:
        user_id: 用户ID
        conversation_id: 对话ID

    Returns:
        dict: 删除结果
    """
    try:
        success = conversation_service.delete_conversation(conversation_id, user_id)
        if not success:
            raise HTTPException(status_code=404, detail="对话未找到")

        return {
            "code": 0,
            "data": {
                "conversation_id": conversation_id,
                "deleted": True
            },
            "message": "对话已删除"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除对话失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/conversations/{user_id}")
async def create_conversation(user_id: str):
    """
    创建新对话

    Args:
        user_id: 用户ID

    Returns:
        dict: 新对话信息
    """
    try:
        conversation_id = f"conv_{uuid.uuid4().hex[:12]}"
        conversation = conversation_service.create_conversation(conversation_id, user_id)

        return {
            "code": 0,
            "data": conversation
        }
    except Exception as e:
        logger.error(f"创建对话失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
