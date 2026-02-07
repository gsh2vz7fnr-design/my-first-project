"""
健康记录管理单元测试
测试问诊、处方、挂号、病历存档、体检检验记录的CRUD操作

测试范围：
- BUG-006: HealthRecordsService 完全未测试
- 各类记录的添加和计数
- 记录摘要的正确性
"""
import pytest
import tempfile
import os
from app.services.profile_service import HealthRecordsService


class TestHealthRecordsService:
    """健康记录服务测试"""

    def setup_method(self):
        """每个测试方法执行前设置"""
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.service = HealthRecordsService(self.db_path)
        self.service.init_records_tables()
        self.member_id = "test_member_001"

    def teardown_method(self):
        """每个测试方法执行后清理"""
        try:
            os.unlink(self.db_path)
        except:
            pass

    def test_add_consultation_record(self):
        """测试添加问诊记录"""
        record_id = self.service.add_consultation(
            member_id=self.member_id,
            date="2024-06-15",
            summary="发热3天，体温最高39度",
            doctor="张医生",
            hospital="北京儿童医院",
            department="儿科"
        )

        assert record_id is not None
        assert record_id.startswith("consult_")

    def test_add_prescription_record(self):
        """测试添加处方记录"""
        drugs = [
            {"name": "布洛芬", "dosage": "5ml", "frequency": "每6小时"},
            {"name": "对乙酰氨基酚", "dosage": "10ml", "frequency": "每8小时"}
        ]

        record_id = self.service.add_prescription(
            member_id=self.member_id,
            date="2024-06-15",
            drugs=drugs,
            doctor="李医生",
            hospital="北京儿童医院",
            diagnosis="上呼吸道感染"
        )

        assert record_id is not None
        assert record_id.startswith("presc_")

    def test_add_appointment_record(self):
        """测试添加挂号记录"""
        record_id = self.service.add_appointment(
            member_id=self.member_id,
            date="2024-06-20",
            department="儿科",
            hospital="北京儿童医院",
            doctor="王医生"
        )

        assert record_id is not None
        assert record_id.startswith("appoint_")

    def test_add_document_record(self):
        """测试添加病历存档"""
        record_id = self.service.add_document(
            member_id=self.member_id,
            date="2024-06-15",
            doc_type="report",
            title="血常规检查报告",
            file_url="http://example.com/report.pdf",
            description="白细胞计数正常",
            hospital="北京儿童医院"
        )

        assert record_id is not None
        assert record_id.startswith("doc_")

    def test_add_checkup_record(self):
        """测试添加体检检验记录"""
        record_id = self.service.add_checkup(
            member_id=self.member_id,
            date="2024-06-15",
            checkup_type="血常规",
            hospital="北京儿童医院",
            summary="各项指标正常",
            results="白细胞: 6.5, 血红蛋白: 120",
            abnormal_items=[]
        )

        assert record_id is not None
        assert record_id.startswith("checkup_")

    def test_get_records_summary(self):
        """测试获取记录摘要，验证各类计数正确"""
        # 添加各类记录
        self.service.add_consultation(
            member_id=self.member_id,
            date="2024-06-15",
            summary="发热"
        )

        self.service.add_prescription(
            member_id=self.member_id,
            date="2024-06-15",
            drugs=[{"name": "布洛芬"}]
        )

        self.service.add_appointment(
            member_id=self.member_id,
            date="2024-06-20",
            department="儿科",
            hospital="北京儿童医院"
        )

        self.service.add_document(
            member_id=self.member_id,
            date="2024-06-15",
            doc_type="report",
            title="血常规"
        )

        self.service.add_checkup(
            member_id=self.member_id,
            date="2024-06-15",
            checkup_type="血常规"
        )

        # 获取摘要
        summary = self.service.get_records_summary(self.member_id)

        assert summary["consultation_count"] == 1
        assert summary["prescription_count"] == 1
        assert summary["appointment_count"] == 1
        assert summary["document_count"] == 1
        assert summary["checkup_count"] == 1

    def test_empty_records_summary(self):
        """测试无记录时摘要应全为 0"""
        summary = self.service.get_records_summary(self.member_id)

        assert summary["consultation_count"] == 0
        assert summary["prescription_count"] == 0
        assert summary["appointment_count"] == 0
        assert summary["document_count"] == 0
        assert summary["checkup_count"] == 0

    def test_multiple_consultation_records(self):
        """测试添加多条问诊记录"""
        # 添加3条问诊记录
        for i in range(3):
            self.service.add_consultation(
                member_id=self.member_id,
                date="2024-06-15",
                summary=f"第{i+1}次问诊"
            )

        summary = self.service.get_records_summary(self.member_id)
        assert summary["consultation_count"] == 3

    def test_consultation_with_all_fields(self):
        """测试包含所有字段的问诊记录"""
        record_id = self.service.add_consultation(
            member_id=self.member_id,
            date="2024-06-15",
            summary="发热伴咳嗽",
            doctor="张医生",
            hospital="北京儿童医院",
            department="呼吸科"
        )

        assert record_id is not None

        # 验证摘要计数增加
        summary = self.service.get_records_summary(self.member_id)
        assert summary["consultation_count"] == 1

    def test_prescription_with_empty_drugs(self):
        """测试空药物列表的处方记录"""
        record_id = self.service.add_prescription(
            member_id=self.member_id,
            date="2024-06-15",
            drugs=[]  # 空药物列表
        )

        assert record_id is not None
        summary = self.service.get_records_summary(self.member_id)
        assert summary["prescription_count"] == 1

    def test_checkup_with_abnormal_items(self):
        """测试包含异常项的体检记录"""
        abnormal_items = ["白细胞偏高", "淋巴细胞偏低"]

        record_id = self.service.add_checkup(
            member_id=self.member_id,
            date="2024-06-15",
            checkup_type="血常规",
            abnormal_items=abnormal_items
        )

        assert record_id is not None
        summary = self.service.get_records_summary(self.member_id)
        assert summary["checkup_count"] == 1

    def test_document_without_file_url(self):
        """测试没有文件URL的病历存档"""
        record_id = self.service.add_document(
            member_id=self.member_id,
            date="2024-06-15",
            doc_type="report",
            title="手工记录",
            description="门诊病历记录"
            # 没有 file_url
        )

        assert record_id is not None
        summary = self.service.get_records_summary(self.member_id)
        assert summary["document_count"] == 1


class TestRecordsCountAccumulation:
    """测试记录计数的累积"""

    def setup_method(self):
        """每个测试方法执行前设置"""
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.service = HealthRecordsService(self.db_path)
        self.service.init_records_tables()
        self.member_id = "test_member_001"

    def teardown_method(self):
        """每个测试方法执行后清理"""
        try:
            os.unlink(self.db_path)
        except:
            pass

    def test_records_count_increments(self):
        """测试记录计数正确递增"""
        # 初始计数为0
        summary = self.service.get_records_summary(self.member_id)
        assert summary["consultation_count"] == 0

        # 添加1条问诊记录
        self.service.add_consultation(
            member_id=self.member_id,
            date="2024-06-15",
            summary="发热"
        )

        # 计数应为1
        summary = self.service.get_records_summary(self.member_id)
        assert summary["consultation_count"] == 1

        # 再添加2条
        self.service.add_consultation(
            member_id=self.member_id,
            date="2024-06-16",
            summary="咳嗽"
        )
        self.service.add_consultation(
            member_id=self.member_id,
            date="2024-06-17",
            summary="皮疹"
        )

        # 计数应为3
        summary = self.service.get_records_summary(self.member_id)
        assert summary["consultation_count"] == 3

    def test_different_members_records_independent(self):
        """测试不同成员的记录独立计数"""
        # 成员A添加1条问诊记录
        self.service.add_consultation(
            member_id="member_a",
            date="2024-06-15",
            summary="发热"
        )

        # 成员B添加2条问诊记录
        self.service.add_consultation(
            member_id="member_b",
            date="2024-06-15",
            summary="咳嗽"
        )
        self.service.add_consultation(
            member_id="member_b",
            date="2024-06-16",
            summary="皮疹"
        )

        # 验证计数独立
        summary_a = self.service.get_records_summary("member_a")
        assert summary_a["consultation_count"] == 1

        summary_b = self.service.get_records_summary("member_b")
        assert summary_b["consultation_count"] == 2
