"""代码质量与配置测试"""
import pytest
import tempfile
import os
from pydantic import ValidationError


class TestConfigSecurity:
    """P2-1: 配置安全"""
    def test_default_secret_key_is_empty(self):
        """TC-CQ-001: 默认 SECRET_KEY 不应是已知占位符"""
        from app.config import Settings
        s = Settings(DEEPSEEK_API_KEY="test")
        assert s.SECRET_KEY != "your-secret-key-change-in-production"

    def test_allowed_origins_not_wildcard_by_default(self):
        """TC-CQ-002: 默认 ALLOWED_ORIGINS 不应为 ['*']"""
        from app.config import Settings
        s = Settings(DEEPSEEK_API_KEY="test")
        assert s.ALLOWED_ORIGINS != ["*"]


class TestBabyInfoGenderType:
    """P2-4: BabyInfo.gender 类型"""
    def test_gender_accepts_enum(self):
        """TC-CQ-003: BabyInfo 接受 Gender 枚举"""
        from app.models.user import BabyInfo, Gender
        baby = BabyInfo(gender=Gender.MALE)
        assert baby.gender == Gender.MALE

    def test_gender_accepts_none(self):
        """TC-CQ-004: BabyInfo.gender 可为 None"""
        from app.models.user import BabyInfo
        baby = BabyInfo()
        assert baby.gender is None


class TestHistorySummaryPerformance:
    """P2-3: 查询优化"""
    def test_summary_returns_correct_structure(self):
        """TC-CQ-005: get_history_summary 返回正确结构"""
        from app.services.profile_service import HealthHistoryService
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        svc = HealthHistoryService(db_path)
        svc.init_history_tables()
        summary = svc.get_history_summary("nonexistent")
        assert "allergy_count" in summary
        assert "medical_count" in summary
        assert "family_count" in summary
        assert "medication_count" in summary
        assert summary["allergy_preview"] == "暂无记录"
        os.unlink(db_path)
