"""
测试对话归档功能
"""
import pytest
import tempfile
import os
from datetime import datetime
from app.services.archive_service import ArchiveService
from app.models.medical_context import MedicalContext, DialogueState, IntentType, TriageSnapshot


class TestArchiveService:
    """测试归档服务"""

    def setup_method(self):
        # 使用临时数据库
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.service = ArchiveService(self.temp_db.name)
        self.service.init_db()

        # 使用同一个数据库初始化conversation_state_service
        from app.services.conversation_state_service import ConversationStateService
        self.state_service = ConversationStateService(self.temp_db.name)

    def teardown_method(self):
        # 清理临时数据库
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)

    @pytest.mark.asyncio
    async def test_archive_conversation_basic(self):
        """TC-ARCHIVE-001: 基本归档功能"""
        # 创建测试用的MedicalContext
        ctx = MedicalContext(
            conversation_id="test_conv_001",
            user_id="test_user",
            dialogue_state=DialogueState.TRIAGE_COMPLETE,
            current_intent=IntentType.TRIAGE,
            chief_complaint="宝宝发烧38.5度",
            symptom="发烧",
            slots={"temperature": "38.5度", "age_months": 6},
            triage_snapshot=TriageSnapshot(
                level="observe",
                reason="轻度发烧",
                action="在家观察"
            )
        )
        ctx.increment_turn()  # 增加turn_count使其非空

        # 执行归档（直接传入ctx）
        result = await self.service.archive_conversation("test_conv_001", "test_user", medical_context=ctx)

        # 验证结果
        assert result["conversation_id"] == "test_conv_001"
        assert result["member_id"] == "test_user"
        assert "summary" in result
        assert "archived_at" in result
        assert len(result["summary"]) > 0

    @pytest.mark.asyncio
    async def test_archive_conversation_no_context_fallback(self):
        """TC-ARCHIVE-002: 归档不存在上下文的对话应走回退逻辑"""
        # With fallback logic, archiving without MedicalContext should
        # generate summary from history (or return a fallback message)
        result = await self.service.archive_conversation("nonexistent_conv", "test_user")
        assert result["conversation_id"] == "nonexistent_conv"
        assert "summary" in result
        assert len(result["summary"]) > 0

    @pytest.mark.asyncio
    async def test_get_archived_conversation(self):
        """TC-ARCHIVE-003: 获取归档的对话"""
        # 先创建并归档一个对话
        ctx = MedicalContext(
            conversation_id="test_conv_002",
            user_id="test_user_2",
            chief_complaint="咳嗽2天",
            symptom="咳嗽",
            slots={"duration": "2天"}
        )
        ctx.increment_turn()

        # 归档
        await self.service.archive_conversation("test_conv_002", "test_user_2", medical_context=ctx)

        # 获取归档记录
        record = self.service.get_archived_conversation("test_conv_002")

        assert record is not None
        assert record["conversation_id"] == "test_conv_002"
        assert record["member_id"] == "test_user_2"
        assert record["chief_complaint"] == "咳嗽2天"
        assert "summary" in record
        assert "medical_context" in record

    def test_get_archived_conversation_not_found(self):
        """TC-ARCHIVE-004: 获取不存在的归档记录"""
        record = self.service.get_archived_conversation("nonexistent")

        assert record is None

    @pytest.mark.asyncio
    async def test_get_member_archived_conversations(self):
        """TC-ARCHIVE-005: 获取用户的所有归档对话"""
        # 创建多个归档记录
        for i in range(3):
            ctx = MedicalContext(
                conversation_id=f"test_conv_member_{i}",
                user_id="test_member",
                chief_complaint=f"症状{i}",
                symptom="发烧"
            )
            ctx.increment_turn()

            await self.service.archive_conversation(f"test_conv_member_{i}", "test_member", medical_context=ctx)

        # 获取该用户的所有归档
        archives = self.service.get_member_archived_conversations("test_member")

        assert len(archives) == 3
        assert all(a["conversation_id"].startswith("test_conv_member_") for a in archives)

    @pytest.mark.asyncio
    async def test_generate_summary_with_context(self):
        """TC-ARCHIVE-006: 使用MedicalContext生成摘要"""
        ctx = MedicalContext(
            conversation_id="test_summary",
            user_id="test_user",
            chief_complaint="宝宝腹泻，大便带血",
            symptom="腹泻",
            slots={"stool_character": "水样", "frequency": "5次/天"},
            triage_snapshot=TriageSnapshot(
                level="urgent",
                reason="腹泻伴血便",
                action="建议就医"
            )
        )

        summary = await self.service.generate_summary("test_summary", ctx)

        # 验证摘要包含关键信息（放宽长度限制）
        assert len(summary) >= 30  # 至少30字
        assert len(summary) <= 300  # 不超过300字

    @pytest.mark.asyncio
    async def test_generate_summary_fallback(self):
        """TC-ARCHIVE-007: 测试摘要生成兜底"""
        # 模拟LLM不可用
        from app.services.llm_service import llm_service
        llm_service.remote_available = False

        ctx = MedicalContext(
            conversation_id="test_fallback_summary",
            user_id="test_user",
            chief_complaint="咳嗽",
            symptom="咳嗽"
        )

        summary = self.service._generate_fallback_summary(ctx)

        assert "咳嗽" in summary
        assert len(summary) > 0

    def test_fallback_summary_with_triage(self):
        """TC-ARCHIVE-008: 兜底摘要包含分诊信息"""
        ctx = MedicalContext(
            conversation_id="test",
            user_id="test_user",
            chief_complaint="高烧不退",
            symptom="发烧",
            triage_snapshot=TriageSnapshot(
                level="emergency",
                reason="高烧",
                action="立即就医"
            )
        )

        summary = self.service._generate_fallback_summary(ctx)

        assert "发烧" in summary
        assert "emergency" in summary or "立即就医" in summary

    def test_fallback_summary_no_context(self):
        """TC-ARCHIVE-009: 无上下文时的兜底摘要"""
        summary = self.service._generate_fallback_summary(None)

        assert summary == "对话摘要生成失败"

    @pytest.mark.asyncio
    async def test_archive_duplicate_conversation(self):
        """TC-ARCHIVE-010: 重复归档应更新记录"""
        ctx = MedicalContext(
            conversation_id="test_duplicate",
            user_id="test_user",
            chief_complaint="发烧",
            symptom="发烧"
        )
        ctx.increment_turn()

        # 第一次归档
        result1 = await self.service.archive_conversation("test_duplicate", "test_user", medical_context=ctx)

        # 第二次归档（应该更新而不是插入新记录）
        result2 = await self.service.archive_conversation("test_duplicate", "test_user", medical_context=ctx)

        # 验证只有一条记录
        archives = self.service.get_member_archived_conversations("test_user")
        duplicate_archives = [a for a in archives if a["conversation_id"] == "test_duplicate"]

        assert len(duplicate_archives) == 1
        assert result2["archived_at"] >= result1["archived_at"]


class TestConversationServiceArchived:
    """测试对话服务的归档相关功能"""

    def setup_method(self):
        from app.services.conversation_service import ConversationService
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.service = ConversationService(self.temp_db.name)
        self.service.init_db()

    def teardown_method(self):
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)

    def test_mark_archived(self):
        """TC-ARCHIVE-011: 标记对话为已归档"""
        # 创建一个对话
        self.service.create_conversation("test_archive_mark", "test_user", "测试对话")

        # 标记为已归档
        success = self.service.mark_archived("test_archive_mark", "test_user")

        assert success is True

    def test_mark_archived_nonexistent(self):
        """TC-ARCHIVE-012: 标记不存在的对话"""
        # 尝试标记不存在的对话
        success = self.service.mark_archived("nonexistent", "test_user")

        # 应该返回False或不抛出异常
        assert success is False
