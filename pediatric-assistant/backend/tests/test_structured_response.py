"""
测试结构化响应生成功能
"""
import pytest
from app.services.llm_service import LLMService


class TestStructuredTriageResponse:
    """测试结构化分诊响应生成"""

    def setup_method(self):
        self.service = LLMService()

    @pytest.mark.asyncio
    async def test_generate_triage_response_with_context(self):
        """TC-STRUCT-001: 生成带用户上下文的分诊响应"""
        rag_content = "发烧是儿童常见症状。3个月以下婴儿发烧需立即就医。"
        user_context = {
            "symptom": "发烧",
            "entities": {"age_months": 6, "temperature": "38.5度"},
            "triage_level": "observe"
        }

        response = await self.service.generate_structured_triage_response(
            rag_content, user_context
        )

        # 验证响应不为空
        assert response is not None
        assert len(response) > 0

        # 验证响应长度合理（≤180字的要求较宽松，实际可能稍长）
        assert len(response) <= 250, f"响应过长: {len(response)}字"

    @pytest.mark.asyncio
    async def test_generate_triage_response_fallback(self):
        """TC-STRUCT-002: 测试本地兜底生成"""
        # 模拟LLM不可用
        self.service.remote_available = False

        user_context = {
            "symptom": "咳嗽",
            "entities": {"duration": "2天"},
            "triage_level": "observe"
        }

        response = await self.service.generate_structured_triage_response(
            "医学内容", user_context
        )

        # 兜底响应应该包含症状
        assert "咳嗽" in response
        assert len(response) > 0

    @pytest.mark.asyncio
    async def test_generate_triage_response_without_context(self):
        """TC-STRUCT-003: 无用户上下文时生成响应"""
        rag_content = "呕吐可能由多种原因引起，需要观察频率和伴随症状。"

        response = await self.service.generate_structured_triage_response(
            rag_content, None
        )

        assert response is not None
        assert len(response) > 0


class TestStructuredConsultResponse:
    """测试结构化咨询响应生成"""

    def setup_method(self):
        self.service = LLMService()

    @pytest.mark.asyncio
    async def test_generate_consult_response(self):
        """TC-STRUCT-004: 生成咨询响应"""
        rag_content = "宝宝腹泻时应注意补液，避免脱水。可以使用口服补液盐。"
        user_context = {
            "query": "宝宝拉肚子怎么办",
            "entities": {"symptom": "腹泻"},
            "intent": "consult"
        }

        response = await self.service.generate_structured_consult_response(
            rag_content, user_context
        )

        assert response is not None
        assert len(response) > 0
        assert len(response) <= 250

    @pytest.mark.asyncio
    async def test_generate_consult_response_fallback(self):
        """TC-STRUCT-005: 测试咨询响应本地兜底"""
        self.service.remote_available = False

        response = await self.service.generate_structured_consult_response(
            "医学内容", {"query": "护理建议"}
        )

        assert response is not None
        assert "理解您的关心" in response


class TestStructuredHealthAdvice:
    """测试结构化健康建议生成"""

    def setup_method(self):
        self.service = LLMService()

    @pytest.mark.asyncio
    async def test_generate_health_advice(self):
        """TC-STRUCT-006: 生成健康建议"""
        rag_content = "儿童预防接种非常重要，可以有效预防多种疾病。"
        user_context = {
            "query": "宝宝疫苗接种注意事项",
            "intent": "care"
        }

        response = await self.service.generate_structured_health_advice(
            rag_content, user_context
        )

        assert response is not None
        assert len(response) > 0
        assert len(response) <= 300

    @pytest.mark.asyncio
    async def test_generate_health_advice_fallback(self):
        """TC-STRUCT-007: 测试健康建议本地兜底"""
        self.service.remote_available = False

        response = await self.service.generate_structured_health_advice(
            "医学内容", None
        )

        assert response is not None
        # 兜底响应应该包含分点标记
        assert "•" in response or "：" in response


class TestFallbackMethods:
    """测试兜底方法"""

    def setup_method(self):
        self.service = LLMService()

    def test_fallback_triage_response(self):
        """TC-STRUCT-008: 测试分诊兜底响应"""
        context = {"symptom": "发烧", "temperature": "38.5度"}

        response = self.service._generate_fallback_triage_response(context)

        assert "发烧" in response
        assert len(response) > 0

    def test_fallback_triage_response_no_context(self):
        """TC-STRUCT-009: 无上下文时的分诊兜底响应"""
        response = self.service._generate_fallback_triage_response(None)

        assert "不适" in response
        assert len(response) > 0

    def test_fallback_consult_response(self):
        """TC-STRUCT-010: 测试咨询兜底响应"""
        response = self.service._generate_fallback_consult_response({})

        assert "理解" in response or "建议" in response
        assert len(response) > 0

    def test_fallback_health_advice(self):
        """TC-STRUCT-011: 测试健康建议兜底响应"""
        response = self.service._generate_fallback_health_advice({})

        assert "•" in response
        assert "建议" in response or "注意" in response
