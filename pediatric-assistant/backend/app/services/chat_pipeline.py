"""
对话处理流水线 - 统一的消息处理服务

ChatPipeline 将原来分散在路由层中的逻辑整合成一个清晰的流水线：

1. 解析 conversation_id，加载/创建 MedicalContext
2. 处方意图安全拦截
3. 加载用户档案
4. LLM 提取意图+实体
5. 合并实体到 MedicalContext.slots
6. 首次 triage 消息记为 chief_complaint
7. 必要时从历史恢复 symptom
8. 危险信号检查
9. 计算缺失槽位
10. 状态机决定 action → 执行 action → 持久化
"""
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, AsyncGenerator
from datetime import datetime
from loguru import logger
import asyncio

from app.utils.logger import get_logger, set_session_id

from app.models.medical_context import (
    MedicalContext,
    DialogueState,
    IntentType,
    TriageSnapshot
)
from app.models.user import ChatRequest, StreamChunk, TriageDecision
from app.services.llm_service import llm_service
from app.services.triage_engine import triage_engine
from app.services.safety_filter import safety_filter
from app.services.rag_service import get_rag_service
from app.services.profile_service import profile_service
from app.services.conversation_service import conversation_service
from app.services.conversation_state_service import conversation_state_service
from app.services.dialogue_state_machine import (
    dialogue_state_machine,
    Action,
    TransitionResult
)
from app.config import settings


@dataclass
class PipelineResult:
    """
    流水线处理结果

    Attributes:
        conversation_id: 对话ID
        message: 回复消息
        sources: 知识来源列表
        metadata: 元数据（意图、分诊级别等）
        need_follow_up: 是否需要追问
        missing_slots: 缺失的槽位
    """
    conversation_id: str
    message: str
    sources: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    need_follow_up: bool = False
    missing_slots: Optional[List[str]] = None

    def to_api_response(self) -> Dict[str, Any]:
        """
        转换为 API 响应格式

        Returns:
            Dict[str, Any]: API 响应
        """
        response = {
            "code": 0,
            "data": {
                "conversation_id": self.conversation_id,
                "message": self.message,
                "sources": self.sources,
                "metadata": self.metadata
            }
        }

        # 添加追问相关字段
        if self.need_follow_up:
            response["data"]["metadata"]["need_follow_up"] = True
            if self.missing_slots and "missing_slots" not in self.metadata:
                # 只有当metadata中还没有missing_slots时才添加简单列表
                # 如果metadata中已经有missing_slots（如structured_slots），则保留它
                response["data"]["metadata"]["missing_slots"] = self.missing_slots

        return response

    async def to_stream_chunks(self) -> AsyncGenerator[str, None]:
        """
        生成流式输出块

        Yields:
            str: SSE 格式的数据块
        """
        # 先发送 metadata
        metadata_chunk = StreamChunk(type="metadata", metadata=self.metadata)
        yield f"data: {metadata_chunk.model_dump_json()}\n\n"

        # 分块发送消息
        chunk_size = settings.STREAM_CHUNK_SIZE
        for i in range(0, len(self.message), chunk_size):
            text_chunk = self.message[i:i + chunk_size]
            chunk = StreamChunk(type="content", content=text_chunk)
            yield f"data: {chunk.model_dump_json()}\n\n"

        # 发送结束信号，包含 conversation_id
        done_chunk = {
            "type": "done",
            "conversation_id": self.conversation_id
        }
        yield f"data: {json.dumps(done_chunk)}\n\n"


class ChatPipeline:
    """
    对话处理流水线

    将原来 chat.py 中 ~1050 行的复杂逻辑
    整合成一个清晰的 10 步流水线。
    """

    def __init__(self):
        """初始化"""
        self._rag_service = None
        self.log = get_logger("ChatPipeline")

    @property
    def rag_service(self):
        """延迟获取 RAG 服务"""
        if self._rag_service is None:
            self._rag_service = get_rag_service()
        return self._rag_service

    async def process_message(
        self,
        user_id: str,
        message: str,
        conversation_id: Optional[str] = None
    ) -> PipelineResult:
        """
        处理用户消息

        Args:
            user_id: 用户ID
            message: 用户消息
            conversation_id: 对话ID（可选）

        Returns:
            PipelineResult: 处理结果
        """
        # Step 1: 解析 conversation_id，加载/创建 MedicalContext
        conversation_id = conversation_id or f"conv_{uuid.uuid4().hex[:12]}"
        set_session_id(conversation_id)  # 注入日志上下文
        ctx = conversation_state_service.load_medical_context(conversation_id, user_id)
        ctx.increment_turn()
        self.log.info("Turn {} | user_input={}", ctx.turn_count, message[:80])

        # Step 2: 处方意图安全拦截
        if safety_filter.check_prescription_intent(message):
            conversation_service.append_message(conversation_id, user_id, "user", message)
            return PipelineResult(
                conversation_id=conversation_id,
                message=safety_filter.get_prescription_refusal_message(),
                metadata={"blocked": True, "reason": "prescription_intent"}
            )

        # Step 3: 加载用户档案
        profile = profile_service.get_profile(user_id)
        profile_context = {
            "baby_info": profile.baby_info.model_dump(),
            "allergy_history": [x.model_dump() for x in profile.allergy_history],
            "medical_history": [x.model_dump() for x in profile.medical_history]
        }

        # Step 4: LLM 提取意图+实体（传入已累积的 slots 作为上下文）
        intent_result = await llm_service.extract_intent_and_entities(
            user_input=message,
            context=profile_context,
            accumulated_slots=ctx.slots if ctx.slots else None
        )
        self.log.info("Extract: intent={}, entities={}", intent_result.intent.type, intent_result.entities)

        # Step 5: 合并实体到 MedicalContext.slots
        entities_delta = ctx.merge_entities(intent_result.entities)
        ctx.current_intent = IntentType(intent_result.intent.type)
        self.log.info("Slot Update: delta={}", entities_delta)

        # Step 6: 首次 triage 消息记为 chief_complaint
        if intent_result.intent.type == "triage" and ctx.chief_complaint is None:
            ctx.chief_complaint = message

        # Step 7: 必要时从历史恢复 symptom
        symptom = ctx.get_symptom()
        if not symptom:
            history = conversation_service.get_history(conversation_id, limit=10)
            recovered_symptom = self._recover_symptom_from_history(history)
            if recovered_symptom:
                ctx.symptom = recovered_symptom
                symptom = recovered_symptom

        # Step 8: 危险信号检查
        entities_dict = ctx.get_entities_dict()
        danger_alert = triage_engine.check_danger_signals(entities_dict)
        if danger_alert:
            self.log.warning("DangerSignal: {}", danger_alert)

        # Step 9: 计算缺失槽位
        symptom = ctx.get_symptom()
        missing_slots = []
        if symptom:
            missing_slots = triage_engine.get_missing_slots(
                symptom,
                entities_dict,
                profile_context=profile_context
            )
        self.log.info(
            "SlotCheck: symptom={}, slots={}, missing={}",
            symptom, list(ctx.slots.keys()), missing_slots
        )

        # Step 10: 状态机决定 action → 执行 action → 持久化
        transition = dialogue_state_machine.transition(
            intent=ctx.current_intent,
            has_symptom=ctx.has_symptom(),
            danger_alert=danger_alert,
            missing_slots=missing_slots
        )

        self.log.info(
            "Decide: action={} ({})",
            transition.action.value,
            dialogue_state_machine.get_action_description(transition.action)
        )

        # 执行 action
        result = await self._execute_action(
            ctx=ctx,
            transition=transition,
            message=message,
            profile_context=profile_context
        )

        # 持久化 MedicalContext
        conversation_state_service.save_medical_context(ctx)

        # 保存对话记录
        conversation_service.append_message(conversation_id, user_id, "user", message)

        # Bot 回复带元数据
        bot_metadata = {
            "intent": ctx.current_intent.value if ctx.current_intent else None,
            "entities_delta": entities_delta,
        }
        if ctx.triage_snapshot and result.metadata.get("triage_level"):
            bot_metadata["triage_result"] = {
                "level": ctx.triage_snapshot.level,
                "reason": ctx.triage_snapshot.reason,
            }
        if ctx.danger_signal:
            bot_metadata["danger_signal"] = ctx.danger_signal

        conversation_service.append_message(
            conversation_id, user_id, "assistant", result.message,
            metadata=bot_metadata
        )

        # 安排延迟档案提取
        if transition.action in (Action.MAKE_TRIAGE_DECISION, Action.RUN_RAG_QUERY):
            asyncio.create_task(
                profile_service.schedule_delayed_extraction(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    delay_minutes=30
                )
            )

        return result

    async def _execute_action(
        self,
        ctx: MedicalContext,
        transition: TransitionResult,
        message: str,
        profile_context: Dict[str, Any]
    ) -> PipelineResult:
        """
        执行状态机决定的行动

        Args:
            ctx: 医疗上下文
            transition: 状态转移结果
            message: 用户消息
            profile_context: 用户档案上下文

        Returns:
            PipelineResult: 处理结果
        """
        action = transition.action

        if action == Action.SEND_GREETING:
            return self._send_greeting(ctx)

        elif action == Action.ASK_FOR_SYMPTOM:
            return self._ask_for_symptom(ctx)

        elif action == Action.SEND_DANGER_ALERT:
            return self._send_danger_alert(ctx, transition.metadata.get("danger_alert"))

        elif action == Action.ASK_MISSING_SLOTS:
            return self._ask_missing_slots(ctx, transition.metadata.get("missing_slots", []))

        elif action == Action.MAKE_TRIAGE_DECISION:
            return await self._make_triage_decision(ctx, profile_context)

        elif action == Action.RUN_RAG_QUERY:
            return await self._run_rag_query(ctx, message, profile_context)

        else:
            # 兜底
            return PipelineResult(
                conversation_id=ctx.conversation_id,
                message="抱歉，我暂时无法理解这个问题。请换个方式描述，或咨询专业医生。",
                metadata={"error": "unknown_action"}
            )

    def _send_greeting(self, ctx: MedicalContext) -> PipelineResult:
        """发送问候"""
        greeting = (
            "您好！我是智能儿科助手 👋\n\n"
            "我可以帮您：\n"
            "• 评估宝宝的症状（发烧、咳嗽、腹泻等）\n"
            "• 提供科学的居家护理建议\n"
            "• 判断是否需要就医\n\n"
            "请描述宝宝的情况，例如：「宝宝8个月，发烧38.5度，精神不好」"
        )
        greeting = safety_filter.add_disclaimer(greeting)

        ctx.dialogue_state = DialogueState.GREETING

        return PipelineResult(
            conversation_id=ctx.conversation_id,
            message=greeting,
            metadata={"intent": "greeting"}
        )

    def _ask_for_symptom(self, ctx: MedicalContext) -> PipelineResult:
        """询问症状"""
        follow_up = "为了继续分诊，请先告诉我宝宝的主要症状（如发烧、咳嗽、腹泻等）。"

        ctx.dialogue_state = DialogueState.COLLECTING_SLOTS

        # 获取建议选项
        options = triage_engine.get_slot_options("symptom")

        return PipelineResult(
            conversation_id=ctx.conversation_id,
            message=follow_up,
            metadata={
                "intent": "slot_filling",
                "need_follow_up": True,
                "missing_slots": {
                    "symptom": {
                        "label": "主要症状",
                        "options": options
                    }
                }
            },
            need_follow_up=True,
            missing_slots=["symptom"]
        )

    def _send_danger_alert(self, ctx: MedicalContext, danger_alert: str) -> PipelineResult:
        """发送危险告警"""
        ctx.dialogue_state = DialogueState.DANGER_DETECTED
        ctx.danger_signal = danger_alert
        ctx.triage_level = "emergency"

        return PipelineResult(
            conversation_id=ctx.conversation_id,
            message=danger_alert,
            metadata={
                "intent": "triage",
                "triage_level": "emergency",
                "danger_signal": True
            }
        )

    def _ask_missing_slots(
        self,
        ctx: MedicalContext,
        missing_slots: List[str]
    ) -> PipelineResult:
        """追问缺失槽位"""
        symptom = ctx.get_symptom()
        follow_up = triage_engine.generate_follow_up_question(symptom, missing_slots)

        ctx.dialogue_state = DialogueState.COLLECTING_SLOTS

        # 构建结构化的缺失槽位信息（带建议选项）
        structured_slots = {}
        # 槽位字段名到中文标签的映射
        slot_label_map = {
            "age_months": "月龄",
            "temperature": "体温",
            "duration": "持续时长",
            "mental_state": "精神状态",
            "accompanying_symptoms": "伴随症状",
            "frequency": "频率",
            "symptom": "症状"
        }
        for slot in missing_slots:
            options = triage_engine.get_slot_options(slot)
            # 使用中文标签，如果没有映射则使用字段名
            label = slot_label_map.get(slot, slot)
            structured_slots[slot] = {
                "label": label,
                "options": options
            }

        return PipelineResult(
            conversation_id=ctx.conversation_id,
            message=follow_up,
            metadata={
                "intent": "slot_filling", # 明确为 slot_filling
                "need_follow_up": True,
                "missing_slots": structured_slots
            },
            need_follow_up=True,
            missing_slots=missing_slots
        )

    async def _make_triage_decision(
        self,
        ctx: MedicalContext,
        profile_context: Dict[str, Any]
    ) -> PipelineResult:
        """做出分诊决策"""
        symptom = ctx.get_symptom()
        entities_dict = ctx.get_entities_dict()

        decision = triage_engine.make_triage_decision(symptom, entities_dict)

        # 更新上下文：triage_snapshot 一次性写入
        ctx.dialogue_state = DialogueState.TRIAGE_COMPLETE
        ctx.triage_snapshot = TriageSnapshot(
            level=decision.level,
            reason=decision.reason,
            action=decision.action
        )

        response_message = f"**{decision.reason}**\n\n{decision.action}"
        response_message = safety_filter.add_disclaimer(response_message)

        return PipelineResult(
            conversation_id=ctx.conversation_id,
            message=response_message,
            metadata={
                "intent": "triage",
                "triage_level": decision.level,
                "entities": entities_dict
            }
        )

    async def _run_rag_query(
        self,
        ctx: MedicalContext,
        query: str,
        profile_context: Dict[str, Any]
    ) -> PipelineResult:
        """执行 RAG 查询"""
        # 检测情绪
        emotion_support = llm_service.detect_emotion(query)

        # RAG 查询
        rag_result = await self.rag_service.generate_answer_with_sources(
            query=query,
            context=profile_context
        )

        # 安全过滤
        safety_result = safety_filter.filter_output(rag_result.answer)
        if not safety_result.is_safe:
            return PipelineResult(
                conversation_id=ctx.conversation_id,
                message=safety_result.fallback_message,
                metadata={"blocked": True, "reason": "safety_filter"}
            )

        # 添加情绪承接
        if emotion_support:
            response_message = f"{emotion_support}\n\n{rag_result.answer}"
        else:
            response_message = rag_result.answer

        # 添加免责声明
        response_message = safety_filter.add_disclaimer(response_message)

        ctx.dialogue_state = DialogueState.RAG_QUERY

        # 获取来源元数据
        sources_metadata = self.rag_service.get_sources_metadata(rag_result.sources)

        return PipelineResult(
            conversation_id=ctx.conversation_id,
            message=response_message,
            sources=sources_metadata,
            metadata={
                "intent": ctx.current_intent.value if ctx.current_intent else "consult",
                "has_source": rag_result.has_source,
                "emotion_detected": emotion_support is not None
            }
        )

    def _recover_symptom_from_history(
        self,
        history: List[Dict[str, str]]
    ) -> Optional[str]:
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


# 创建全局实例
chat_pipeline = ChatPipeline()


def get_chat_pipeline() -> ChatPipeline:
    """获取 ChatPipeline 单例"""
    return chat_pipeline
