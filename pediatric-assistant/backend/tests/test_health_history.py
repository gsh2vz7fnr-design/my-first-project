"""
健康史管理单元测试
测试过敏史、既往病史、家族病史、用药史的CRUD操作

测试范围：
- TC-ME-007: 添加过敏记录
- TC-ME-008: 添加既往病史
- TC-ME-009: 添加用药记录
- INT-4: 添加过敏 -> 首页过敏计数 +1
"""
import pytest
import tempfile
import os
from app.services.profile_service import HealthHistoryService
from app.models.user import (
    MemberProfile,
    Relationship,
    Gender
)


class TestAllergyHistory:
    """过敏史测试"""

    def setup_method(self):
        """每个测试方法执行前设置"""
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.service = HealthHistoryService(self.db_path)
        self.service.init_history_tables()
        self.member_id = "test_member_001"

    def teardown_method(self):
        """每个测试方法执行后清理"""
        try:
            os.unlink(self.db_path)
        except:
            pass

    def test_add_allergy_record(self):
        """
        TC-ME-007: 添加过敏记录
        填写过敏原"鸡蛋"、反应"呕吐"、严重程度"中度" -> 保存成功
        """
        record_id = self.service.add_allergy(
            member_id=self.member_id,
            allergen="鸡蛋",
            reaction="呕吐",
            severity="moderate",
            date="2024-01-01"
        )

        assert record_id is not None
        assert record_id.startswith("allergy_")

        # 验证记录已保存
        history = self.service.get_allergy_history(self.member_id)
        assert len(history) == 1
        assert history[0]["allergen"] == "鸡蛋"
        assert history[0]["reaction"] == "呕吐"

    def test_get_allergy_history_empty(self):
        """测试获取空的过敏史"""
        history = self.service.get_allergy_history(self.member_id)
        assert history == []

    def test_get_allergy_history_multiple(self):
        """测试获取多条过敏记录"""
        # 添加3条过敏记录
        for i, allergen in enumerate(["鸡蛋", "牛奶", "花生"]):
            self.service.add_allergy(
                member_id=self.member_id,
                allergen=allergen,
                reaction="皮疹",
                severity="mild"
            )

        history = self.service.get_allergy_history(self.member_id)
        assert len(history) == 3

    def test_allergy_count_in_summary(self):
        """
        TC-HP-008: 过敏记录计数
        已添加 3 条过敏记录 -> 过敏卡片显示"3"
        """
        # 添加3条过敏记录
        for allergen in ["鸡蛋", "牛奶", "花生"]:
            self.service.add_allergy(
                member_id=self.member_id,
                allergen=allergen,
                reaction="皮疹",
                severity="mild"
            )

        summary = self.service.get_history_summary(self.member_id)
        assert summary["allergy_count"] == 3

    def test_allergy_preview_text(self):
        """测试过敏史预览文本"""
        self.service.add_allergy(
            member_id=self.member_id,
            allergen="鸡蛋",
            reaction="皮疹",
            severity="mild"
        )

        summary = self.service.get_history_summary(self.member_id)
        assert "鸡蛋" in summary["allergy_preview"]
        assert "1项" in summary["allergy_preview"]


class TestMedicalHistory:
    """既往病史测试"""

    def setup_method(self):
        """每个测试方法执行前设置"""
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.service = HealthHistoryService(self.db_path)
        self.service.init_history_tables()
        self.member_id = "test_member_001"

    def teardown_method(self):
        """每个测试方法执行后清理"""
        try:
            os.unlink(self.db_path)
        except:
            pass

    def test_add_medical_history(self):
        """
        TC-ME-008: 添加既往病史
        填写疾病名"热性惊厥"、诊断日期 -> 保存成功
        """
        record_id = self.service.add_medical_history(
            member_id=self.member_id,
            condition="热性惊厥",
            diagnosis_date="2024-03-15",
            treatment="观察",
            status="recovered"
        )

        assert record_id is not None
        assert record_id.startswith("medical_")

        # 验证记录已保存
        history = self.service.get_medical_history(self.member_id)
        assert len(history) == 1
        assert history[0]["condition"] == "热性惊厥"

    def test_get_medical_history_empty(self):
        """测试获取空的既往病史"""
        history = self.service.get_medical_history(self.member_id)
        assert history == []

    def test_medical_count_in_summary(self):
        """测试既往病史计数"""
        # 添加2条病史
        for condition in ["热性惊厥", "支气管炎"]:
            self.service.add_medical_history(
                member_id=self.member_id,
                condition=condition,
                diagnosis_date="2024-01-01"
            )

        summary = self.service.get_history_summary(self.member_id)
        assert summary["medical_count"] == 2


class TestFamilyHistory:
    """家族病史测试"""

    def setup_method(self):
        """每个测试方法执行前设置"""
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.service = HealthHistoryService(self.db_path)
        self.service.init_history_tables()
        self.member_id = "test_member_001"

    def teardown_method(self):
        """每个测试方法执行后清理"""
        try:
            os.unlink(self.db_path)
        except:
            pass

    def test_add_family_history(self):
        """测试添加家族病史"""
        record_id = self.service.add_family_history(
            member_id=self.member_id,
            condition="高血压",
            relative="父亲"
        )

        assert record_id is not None
        assert record_id.startswith("family_")

        # 验证记录已保存
        history = self.service.get_family_history(self.member_id)
        assert len(history) == 1
        assert history[0]["condition"] == "高血压"

    def test_family_count_in_summary(self):
        """测试家族病史计数"""
        # 添加2条家族病史
        self.service.add_family_history(
            member_id=self.member_id,
            condition="高血压",
            relative="父亲"
        )
        self.service.add_family_history(
            member_id=self.member_id,
            condition="糖尿病",
            relative="母亲"
        )

        summary = self.service.get_history_summary(self.member_id)
        assert summary["family_count"] == 2


class TestMedicationHistory:
    """用药史测试"""

    def setup_method(self):
        """每个测试方法执行前设置"""
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.service = HealthHistoryService(self.db_path)
        self.service.init_history_tables()
        self.member_id = "test_member_001"

    def teardown_method(self):
        """每个测试方法执行后清理"""
        try:
            os.unlink(self.db_path)
        except:
            pass

    def test_add_medication_history(self):
        """
        TC-ME-009: 添加用药记录
        填写药名"布洛芬"、剂量"5ml"、频率"每6小时" -> 保存成功
        """
        record_id = self.service.add_medication_history(
            member_id=self.member_id,
            drug_name="布洛芬",
            dosage="5ml",
            frequency="每6小时",
            start_date="2024-06-01",
            end_date="2024-06-03",
            reason="发热"
        )

        assert record_id is not None
        assert record_id.startswith("med_")

        # 验证记录已保存
        history = self.service.get_medication_history(self.member_id)
        assert len(history) == 1
        assert history[0]["drug_name"] == "布洛芬"

    def test_medication_count_in_summary(self):
        """测试用药史计数"""
        # 添加2条用药记录
        for drug in ["布洛芬", "对乙酰氨基酚"]:
            self.service.add_medication_history(
                member_id=self.member_id,
                drug_name=drug,
                dosage="5ml",
                frequency="每6小时"
            )

        summary = self.service.get_history_summary(self.member_id)
        assert summary["medication_count"] == 2


class TestHistorySummary:
    """健康史摘要测试"""

    def setup_method(self):
        """每个测试方法执行前设置"""
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.service = HealthHistoryService(self.db_path)
        self.service.init_history_tables()
        self.member_id = "test_member_001"

    def teardown_method(self):
        """每个测试方法执行后清理"""
        try:
            os.unlink(self.db_path)
        except:
            pass

    def test_summary_with_all_types(self):
        """测试包含所有类型健康史的摘要"""
        # 添加各类型记录
        self.service.add_allergy(
            member_id=self.member_id,
            allergen="鸡蛋",
            reaction="皮疹"
        )
        self.service.add_medical_history(
            member_id=self.member_id,
            condition="热性惊厥"
        )
        self.service.add_family_history(
            member_id=self.member_id,
            condition="高血压",
            relative="父亲"
        )
        self.service.add_medication_history(
            member_id=self.member_id,
            drug_name="布洛芬"
        )

        summary = self.service.get_history_summary(self.member_id)

        assert summary["allergy_count"] == 1
        assert summary["medical_count"] == 1
        assert summary["family_count"] == 1
        assert summary["medication_count"] == 1

    def test_summary_empty_returns_zeros(self):
        """测试空健康史摘要返回0计数"""
        summary = self.service.get_history_summary(self.member_id)

        assert summary["allergy_count"] == 0
        assert summary["medical_count"] == 0
        assert summary["family_count"] == 0
        assert summary["medication_count"] == 0

    def test_preview_text_with_multiple_items(self):
        """测试多项记录时的预览文本"""
        # 添加3条过敏记录
        for allergen in ["鸡蛋", "牛奶", "花生"]:
            self.service.add_allergy(
                member_id=self.member_id,
                allergen=allergen,
                reaction="皮疹"
            )

        summary = self.service.get_history_summary(self.member_id)
        # 应该显示"鸡蛋等3项"
        assert "鸡蛋" in summary["allergy_preview"]
        assert "3项" in summary["allergy_preview"]

    def test_preview_text_empty(self):
        """测试空记录的预览文本"""
        summary = self.service.get_history_summary(self.member_id)

        assert summary["allergy_preview"] == "暂无记录"
        assert summary["medical_preview"] == "暂无记录"
