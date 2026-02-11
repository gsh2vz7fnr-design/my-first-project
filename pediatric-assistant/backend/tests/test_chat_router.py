"""
TDD 红灯测试: ChatBot 路由层三大阻断 Bug

Bug 现象:
  1. "你好" → 兜底拒答 (应为闲聊回复)
  2. Slot-filling 结构化数据 → 兜底拒答 (应继续分诊流程)
  3. "宝宝拉肚子" → 兜底拒答 (应触发分诊或 RAG 命中腹泻知识)

根因: 系统缺少前置意图路由, 所有输入强制走 RAG 检索
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.services.llm_service import LLMService
from app.models.user import IntentAndEntities, Intent


# ============ Fixtures ============

@pytest.fixture
async def client():
    """创建测试客户端"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


FALLBACK_KEYWORDS = ["无记录", "暂无关于此问题", "没有相关信息", "无法回答"]
"""兜底拒答的特征词 — 任何一个出现都说明路由失败

注意: "咨询医生" 不是兜底拒答词，因为在给出具体建议后建议咨询医生是合理的医疗建议。
"""


# ============ Case 1: Greeting / Chitchat ============

class TestGreetingRoute:
    """
    Bug #1: 用户发送 "你好", Bot 不应走 RAG 检索,
    而应直接返回友好的闲聊回复。
    """

    @pytest.mark.asyncio
    async def test_greeting_not_rejected(self, client):
        """TC-ROUTE-01: "你好" 不能触发兜底拒答"""
        response = await client.post("/api/v1/chat/send", json={
            "user_id": "test_user_route",
            "message": "你好"
        })
        assert response.status_code == 200
        data = response.json()
        reply = data["data"]["message"]

        for keyword in FALLBACK_KEYWORDS:
            assert keyword not in reply, (
                f"Greeting '你好' 触发了兜底拒答, 回复中包含 '{keyword}': {reply[:100]}"
            )

    @pytest.mark.asyncio
    async def test_greeting_has_friendly_reply(self, client):
        """TC-ROUTE-02: "你好" 必须包含友好的自我介绍"""
        response = await client.post("/api/v1/chat/send", json={
            "user_id": "test_user_route",
            "message": "你好"
        })
        assert response.status_code == 200
        data = response.json()
        reply = data["data"]["message"]

        friendly_markers = ["您好", "你好", "儿科", "助手", "帮助", "欢迎"]
        assert any(m in reply for m in friendly_markers), (
            f"Greeting 回复缺少友好标识, 实际回复: {reply[:100]}"
        )


# ============ Case 2: Slot-Filling Structured Data ============

class TestSlotFillingRoute:
    """
    Bug #2: 前端表单提交 "mental_state: 正常\nduration: 1天" 格式的数据,
    后端应识别为 slot-filling 并继续分诊流程, 而非当作新查询走 RAG。
    """

    @pytest.mark.asyncio
    async def test_slot_data_not_rejected(self, client):
        """TC-ROUTE-03: 结构化 slot 数据不能触发兜底拒答"""
        # 模拟前端表单提交的格式 (与 app.js:485-492 一致)
        slot_message = "mental_state: 正常\nduration: 1天"

        response = await client.post("/api/v1/chat/send", json={
            "user_id": "test_user_route",
            "message": slot_message
        })
        assert response.status_code == 200
        data = response.json()
        reply = data["data"]["message"]

        for keyword in FALLBACK_KEYWORDS:
            assert keyword not in reply, (
                f"Slot-filling 数据触发了兜底拒答, 回复中包含 '{keyword}': {reply[:100]}"
            )

    @pytest.mark.asyncio
    async def test_slot_data_continues_triage(self, client):
        """TC-ROUTE-04: Slot 数据应被解析并推进分诊流程"""
        slot_message = "mental_state: 正常\nduration: 1天"

        response = await client.post("/api/v1/chat/send", json={
            "user_id": "test_user_route",
            "message": slot_message
        })
        assert response.status_code == 200
        data = response.json()
        metadata = data["data"].get("metadata", {})

        # 应该进入分诊流程 (triage), 或至少不是 RAG 兜底
        reply = data["data"]["message"]
        # 回复应包含分诊相关内容 (观察/就医/建议), 而非 "无记录"
        triage_markers = ["观察", "就医", "建议", "注意", "症状", "分诊"]
        has_triage_content = any(m in reply for m in triage_markers)
        is_follow_up = metadata.get("need_follow_up", False)

        assert has_triage_content or is_follow_up, (
            f"Slot 数据未推进分诊流程, 实际回复: {reply[:100]}"
        )


# ============ Case 3: Colloquial Medical Query ============

class TestMedicalRAGRoute:
    """
    Bug #3: "宝宝拉肚子" 是常见口语表达,
    系统应识别为 "腹泻" 并返回相关医疗建议。
    """

    @pytest.mark.asyncio
    async def test_diarrhea_colloquial_not_rejected(self, client):
        """TC-ROUTE-05: "宝宝拉肚子" 不能触发兜底拒答"""
        response = await client.post("/api/v1/chat/send", json={
            "user_id": "test_user_route",
            "message": "宝宝拉肚子"
        })
        assert response.status_code == 200
        data = response.json()
        reply = data["data"]["message"]

        for keyword in FALLBACK_KEYWORDS:
            assert keyword not in reply, (
                f"'宝宝拉肚子' 触发了兜底拒答, 回复中包含 '{keyword}': {reply[:100]}"
            )

    @pytest.mark.asyncio
    async def test_diarrhea_has_medical_advice(self, client):
        """TC-ROUTE-06: "宝宝拉肚子" 回复必须包含腹泻/脱水相关建议"""
        response = await client.post("/api/v1/chat/send", json={
            "user_id": "test_user_route",
            "message": "宝宝拉肚子"
        })
        assert response.status_code == 200
        data = response.json()
        reply = data["data"]["message"]

        medical_markers = ["腹泻", "脱水", "补液", "拉肚子", "大便", "观察"]
        assert any(m in reply for m in medical_markers), (
            f"'宝宝拉肚子' 回复缺少医疗建议, 实际回复: {reply[:100]}"
        )


# ============ 补充: 意图分类单元测试 ============

class TestIntentClassification:
    """
    单元测试: 验证意图分类的 fallback 逻辑能正确识别各类输入。
    这些测试不依赖网络, 直接测试本地 fallback 规则。
    """

    def setup_method(self):
        self.service = LLMService()

    def test_greeting_intent_detected(self):
        """TC-ROUTE-07: fallback 应将 '你好' 识别为 greeting 意图"""
        result = self.service._extract_intent_and_entities_fallback("你好")
        # 当前会返回 "consult", 修复后应返回 "greeting"
        assert result.intent.type == "greeting", (
            f"'你好' 应被识别为 greeting, 实际: {result.intent.type}"
        )

    def test_colloquial_symptom_triggers_triage(self):
        """TC-ROUTE-08: fallback 应将 '拉肚子' 识别为 triage 意图"""
        result = self.service._extract_intent_and_entities_fallback("宝宝拉肚子")
        assert result.intent.type == "triage", (
            f"'宝宝拉肚子' 应被识别为 triage, 实际: {result.intent.type}"
        )
        assert result.entities.get("symptom") == "腹泻", (
            f"症状应归一化为 '腹泻', 实际: {result.entities.get('symptom')}"
        )

    def test_slot_format_detected(self):
        """TC-ROUTE-09: fallback 应将 'key: value' 格式识别为 slot_filling 意图"""
        result = self.service._extract_intent_and_entities_fallback(
            "mental_state: 正常\nduration: 1天"
        )
        assert result.intent.type == "slot_filling", (
            f"Slot 格式应被识别为 slot_filling, 实际: {result.intent.type}"
        )


class TestEdgeCases:
    """边界情况测试"""

    def setup_method(self):
        self.service = LLMService()

    def test_mixed_intent_not_greeting(self):
        """混合意图 '你好，宝宝发烧' 不应被识别为纯 greeting"""
        result = self.service._extract_intent_and_entities_fallback("你好，宝宝发烧")
        assert result.intent.type != "greeting"
        assert result.intent.type == "triage"

    def test_multi_slot_parsing(self):
        """多 slot 数据应全部被解析"""
        result = self.service._extract_intent_and_entities_fallback(
            "mental_state: 正常\nduration: 1天\ntemperature: 38.5"
        )
        assert "mental_state" in result.entities
        assert "duration" in result.entities
        assert "temperature" in result.entities
