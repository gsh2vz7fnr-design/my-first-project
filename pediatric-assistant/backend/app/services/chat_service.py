"""
聊天服务 - 统一的对话处理入口

整合了：
- 意图识别（IntentRouter）
- RAG 检索（RAGService）
- 分诊逻辑（TriageEngine）
- 安全过滤（SafetyFilter）

设计原则：
- 先识别意图，再决定处理流程
- 简单问候直接回复，节省资源
- 医疗查询才进行 RAG 检索
- 统一使用 AsyncGenerator，消除流式/非流式重复代码
"""
import asyncio
import uuid
from dataclasses import dataclass, field
from typing import AsyncGenerator, Optional, List, Dict, Any

from loguru import logger

from app.config import settings
from app.models.user import RAGResult, KnowledgeSource
from app.services.intent_router import IntentRouter, Intent, IntentResult, get_intent_router
from app.services.rag_service import RAGService, get_rag_service
from app.services.triage_engine import TriageEngine
from app.services.safety_filter import SafetyFilter
from app.services.llm_service import LLMService
from app.services.profile_service import ProfileService
from app.services.conversation_service import ConversationService


@dataclass
class ChatContext:
    """聊天上下文，封装请求相关的所有信息"""
    user_id: str
    message: str
    conversation_id: str = field(default_factory=lambda: f"conv_{uuid.uuid4().hex[:12]}")
    profile_context: Dict[str, Any] = field(default_factory=dict)
    baby_info: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        user_id: str,
        message: str,
        conversation_id: Optional[str] = None,
        profile: Optional[Any] = None
    ) -> "ChatContext":
        """创建上下文实例"""
        ctx = cls(
            user_id=user_id,
            message=message,
            conversation_id=conversation_id or f"conv_{uuid.uuid4().hex[:12]}"
        )

        if profile:
            ctx.profile_context = {
                "baby_info": profile.baby_info.model_dump() if hasattr(profile, 'baby_info') else {},
                "allergy_history": [x.model_dump() for x in getattr(profile, 'allergy_history', [])],
                "medical_history": [x.model_dump() for x in getattr(profile, 'medical_history', [])]
            }
            ctx.baby_info = ctx.profile_context.get("baby_info", {})

        return ctx


@dataclass
class ChatResponse:
    """聊天响应结果"""
    message: str
    conversation_id: str
    intent: str
    sources: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "code": 0,
            "data": {
                "conversation_id": self.conversation_id,
                "message": self.message,
                "sources": self.sources,
                "metadata": self.metadata
            }
        }


class ChatService:
    """
    聊天服务 - 统一的对话处理入口

    核心设计：所有处理逻辑统一返回 AsyncGenerator，通过 Generator Adapter 模式
    消除流式/非流式代码重复。

    Example:
        >>> service = ChatService()
        >>> # 流式调用
        >>> async for chunk in service.process(user_id, message):
        ...     print(chunk)
        >>> # 非流式调用
        >>> response = await service.process_sync(user_id, message)
    """

    def __init__(
        self,
        intent_router: Optional[IntentRouter] = None,
        rag_service: Optional[RAGService] = None,
        llm_service: Optional[LLMService] = None,
        triage_engine: Optional[TriageEngine] = None,
        safety_filter: Optional[SafetyFilter] = None,
        profile_service: Optional[ProfileService] = None,
        conversation_service: Optional[ConversationService] = None
    ):
        """
        初始化聊天服务

        Args:
            intent_router: 意图路由器（可选，默认自动创建）
            rag_service: RAG 服务（可选）
            llm_service: LLM 服务（可选）
            triage_engine: 分诊引擎（可选）
            safety_filter: 安全过滤器（可选）
            profile_service: 档案服务（可选）
            conversation_service: 对话服务（可选）
        """
        # 依赖注入或延迟初始化
        self._intent_router = intent_router
        self._rag_service = rag_service
        self._llm_service = llm_service
        self._triage_engine = triage_engine
        self._safety_filter = safety_filter
        self._profile_service = profile_service
        self._conversation_service = conversation_service

    # ============ 属性访问器（延迟初始化）============

    @property
    def intent_router(self) -> IntentRouter:
        """获取意图路由器"""
        if self._intent_router is None:
            self._intent_router = get_intent_router()
        return self._intent_router

    @property
    def rag_service(self) -> RAGService:
        """获取 RAG 服务"""
        if self._rag_service is None:
            self._rag_service = get_rag_service()
        return self._rag_service

    @property
    def llm_service(self) -> LLMService:
        """获取 LLM 服务"""
        if self._llm_service is None:
            from app.services.llm_service import llm_service
            self._llm_service = llm_service
        return self._llm_service

    @property
    def triage_engine(self) -> TriageEngine:
        """获取分诊引擎"""
        if self._triage_engine is None:
            from app.services.triage_engine import triage_engine
            self._triage_engine = triage_engine
        return self._triage_engine

    @property
    def safety_filter(self) -> SafetyFilter:
        """获取安全过滤器"""
        if self._safety_filter is None:
            from app.services.safety_filter import safety_filter
            self._safety_filter = safety_filter
        return self._safety_filter

    @property
    def profile_service(self) -> ProfileService:
        """获取档案服务"""
        if self._profile_service is None:
            from app.services.profile_service import profile_service
            self._profile_service = profile_service
        return self._profile_service

    @property
    def conversation_service(self) -> ConversationService:
        """获取对话服务"""
        if self._conversation_service is None:
            from app.services.conversation_service import conversation_service
            self._conversation_service = conversation_service
        return self._conversation_service

    # ============ 核心公共接口 ============

    async def process(
        self,
        user_id: str,
        message: str,
        conversation_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[str, None]:
        """
        处理用户消息（流式输出）

        内部所有逻辑统一使用 AsyncGenerator，消除流式/非流式重复代码。

        Args:
            user_id: 用户 ID
            message: 用户消息
            conversation_id: 对话 ID（可选）
            context: 上下文（可选）

        Yields:
            str: 响应片段
        """
        # 1. 构建上下文
        ctx = await self._build_context(user_id, message, conversation_id, context)

        # 2. 意图识别（带 fallback 机制）
        intent_result = await self._classify_intent(message)

        # 3. 根据意图分发处理
        async for chunk in self._dispatch_by_intent(ctx, intent_result):
            yield chunk

    async def process_sync(
        self,
        user_id: str,
        message: str,
        conversation_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> ChatResponse:
        """
        处理用户消息（非流式输出）

        内部调用 process()，消费 generator 获得完整响应。

        Args:
            user_id: 用户 ID
            message: 用户消息
            conversation_id: 对话 ID（可选）
            context: 上下文（可选）

        Returns:
            ChatResponse: 完整响应
        """
        full_message = ""
        async for chunk in self.process(user_id, message, conversation_id, context):
            full_message += chunk

        # 构建响应
        ctx = await self._build_context(user_id, message, conversation_id, context)
        intent_result = await self._classify_intent(message)

        return ChatResponse(
            message=full_message,
            conversation_id=ctx.conversation_id,
            intent=intent_result.intent.value,
            metadata={"confidence": intent_result.confidence}
        )

    # ============ 核心私有方法（逻辑提炼）============

    async def _build_context(
        self,
        user_id: str,
        message: str,
        conversation_id: Optional[str],
        context: Optional[Dict[str, Any]]
    ) -> ChatContext:
        """
        构建聊天上下文

        统一处理用户档案加载、对话 ID 生成等前置工作。

        Args:
            user_id: 用户 ID
            message: 用户消息
            conversation_id: 对话 ID
            context: 外部上下文

        Returns:
            ChatContext: 完整的聊天上下文
        """
        try:
            profile = self.profile_service.get_profile(user_id)
            return ChatContext.create(
                user_id=user_id,
                message=message,
                conversation_id=conversation_id,
                profile=profile
            )
        except Exception as e:
            logger.warning(f"获取用户档案失败: {e}")
            return ChatContext(
                user_id=user_id,
                message=message,
                conversation_id=conversation_id or f"conv_{uuid.uuid4().hex[:12]}"
            )

    async def _classify_intent(self, message: str) -> IntentResult:
        """
        统一意图识别

        带 fallback 机制：Router 失败时默认为 MEDICAL_QUERY。

        Args:
            message: 用户消息

        Returns:
            IntentResult: 意图识别结果
        """
        try:
            result = await self.intent_router.classify(message)
            logger.info(f"意图识别: {result.intent.value}, confidence={result.confidence:.2f}")
            return result
        except Exception as e:
            logger.warning(f"意图识别失败，使用默认 MEDICAL_QUERY: {e}")
            # Fallback: 默认为医疗查询（宁可错查，不可漏查）
            return IntentResult(
                intent=Intent.MEDICAL_QUERY,
                confidence=0.5,
                entities={"fallback": True, "error": str(e)}
            )

    async def _dispatch_by_intent(
        self,
        ctx: ChatContext,
        intent_result: IntentResult
    ) -> AsyncGenerator[str, None]:
        """
        根据意图分发处理

        统一的分发入口，所有分支都返回 AsyncGenerator。

        Args:
            ctx: 聊天上下文
            intent_result: 意图识别结果

        Yields:
            str: 响应片段
        """
        intent = intent_result.intent

        if intent == Intent.GREETING:
            async for chunk in self._handle_greeting_stream(ctx):
                yield chunk

        elif intent == Intent.EXIT:
            async for chunk in self._handle_exit_stream(ctx):
                yield chunk

        elif intent == Intent.UNKNOWN:
            async for chunk in self._handle_unknown_stream(ctx):
                yield chunk

        elif intent == Intent.DATA_ENTRY:
            async for chunk in self._handle_data_entry_stream(ctx, intent_result):
                yield chunk

        else:  # MEDICAL_QUERY 或其他
            async for chunk in self._handle_medical_query_stream(ctx, intent_result):
                yield chunk

    # ============ 意图处理方法（统一 AsyncGenerator）============

    async def _handle_greeting_stream(self, ctx: ChatContext) -> AsyncGenerator[str, None]:
        """处理问候（流式）"""
        response = self.intent_router.get_greeting_response()
        # 记录对话
        self._save_conversation(ctx, ctx.message, response)
        yield response

    async def _handle_exit_stream(self, ctx: ChatContext) -> AsyncGenerator[str, None]:
        """处理告别（流式）"""
        response = self.intent_router.get_exit_response()
        self._save_conversation(ctx, ctx.message, response)
        yield response

    async def _handle_unknown_stream(self, ctx: ChatContext) -> AsyncGenerator[str, None]:
        """处理未知意图（流式）"""
        response = self.intent_router.get_unknown_response()
        self._save_conversation(ctx, ctx.message, response)
        yield response

    async def _handle_data_entry_stream(
        self,
        ctx: ChatContext,
        intent_result: IntentResult
    ) -> AsyncGenerator[str, None]:
        """处理数据录入（流式）"""
        entities = intent_result.entities

        if entities:
            logger.info(f"数据录入: user={ctx.user_id}, entities={entities}")
            response = "好的，我已经记录了您提供的信息。请问还有其他问题吗？"
        else:
            response = "好的，我了解了。请问宝宝现在有什么不舒服吗？"

        self._save_conversation(ctx, ctx.message, response)
        yield response

    async def _handle_medical_query_stream(
        self,
        ctx: ChatContext,
        intent_result: IntentResult
    ) -> AsyncGenerator[str, None]:
        """
        处理医疗查询（流式）

        完整流程：
        1. 安全检查（处方意图）
        2. RAG 检索
        3. 安全过滤
        4. 添加免责声明
        """
        # 1. 安全检查：处方意图拦截
        if self.safety_filter.check_prescription_intent(ctx.message):
            response = self.safety_filter.get_prescription_refusal_message()
            self._save_conversation(ctx, ctx.message, response)
            yield response
            return

        # 2. RAG 检索
        try:
            rag_result = await self.rag_service.generate_answer_with_sources(
                query=ctx.message,
                context=ctx.profile_context
            )
        except Exception as e:
            logger.error(f"RAG 检索失败: {e}")
            response = "抱歉，检索知识库时出现错误。请稍后重试。"
            self._save_conversation(ctx, ctx.message, response)
            yield response
            return

        # 3. 安全过滤
        safety_result = self.safety_filter.filter_output(rag_result.answer)
        if not safety_result.is_safe:
            self._save_conversation(ctx, ctx.message, safety_result.fallback_message)
            yield safety_result.fallback_message
            return

        # 4. 添加免责声明
        response = self.safety_filter.add_disclaimer(rag_result.answer)

        # 5. 记录对话
        self._save_conversation(ctx, ctx.message, response)

        # 6. 返回响应
        yield response

    # ============ 辅助方法 ============

    def _save_conversation(self, ctx: ChatContext, user_message: str, assistant_message: str):
        """保存对话记录"""
        try:
            self.conversation_service.append_message(
                ctx.conversation_id, ctx.user_id, "user", user_message
            )
            self.conversation_service.append_message(
                ctx.conversation_id, ctx.user_id, "assistant", assistant_message
            )
        except Exception as e:
            logger.warning(f"保存对话记录失败: {e}")

    # ============ 兼容旧接口 ============

    async def handle_message(
        self,
        user_id: str,
        message: str,
        conversation_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[str, None]:
        """
        处理用户消息（兼容旧接口）

        保持向后兼容，内部调用 process()。

        Args:
            user_id: 用户 ID
            message: 用户消息
            conversation_id: 对话 ID（可选）
            context: 上下文（可选）

        Yields:
            str: 响应片段
        """
        async for chunk in self.process(user_id, message, conversation_id, context):
            yield chunk

    async def quick_classify(self, message: str) -> IntentResult:
        """
        快速意图分类（用于预处理）

        Args:
            message: 用户消息

        Returns:
            IntentResult: 意图识别结果
        """
        return await self._classify_intent(message)

    def should_retrieve(self, intent: Intent) -> bool:
        """
        判断是否需要进行 RAG 检索

        Args:
            intent: 意图类型

        Returns:
            bool: 是否需要检索
        """
        return intent in (Intent.MEDICAL_QUERY, Intent.DATA_ENTRY, Intent.UNKNOWN)


# ============ 全局实例管理 ============

_chat_service: Optional[ChatService] = None


def get_chat_service() -> ChatService:
    """获取聊天服务单例"""
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service
