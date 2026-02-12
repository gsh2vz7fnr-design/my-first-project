"""
单据保存数据一致性测试

测试内容：
1. 处方记录保存：验证diagnosis字段正确保存
2. 问诊记录保存：验证summary包含诊断信息
3. 数据关联：验证member_id、时间戳一致性
4. 记录查询：验证查询返回的诊断信息完整
"""
import pytest
import sqlite3
import json
import tempfile
import os
from datetime import datetime
from unittest.mock import Mock, patch

# 导入被测试的服务
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.profile_service import HealthRecordsService
from app.models.user import Relationship, Gender, IdCardType


class TestDataConsistency:
    """数据一致性测试套件"""

    @pytest.fixture
    def db_service(self):
        """创建测试用的数据库服务实例"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        service = HealthRecordsService(db_path)
        service.init_records_tables()

        yield service, db_path

        # 清理
        try:
            os.unlink(db_path)
        except:
            pass

    @pytest.fixture
    def test_member(self, db_service):
        """创建测试成员（用于关联测试）"""
        service, db_path = db_service

        # 首先初始化成员表和服务
        from app.services.profile_service import MemberProfileService, MemberProfile
        member_service = MemberProfileService(db_path)
        member_service.init_member_tables()

        # 创建测试成员
        member = MemberProfile(
            id="test_member_consistency_001",
            user_id="test_user_consistency",
            name="测试儿童",
            relationship=Relationship.CHILD,
            id_card_type=IdCardType.ID_CARD,
            id_card_number="110101202001011234",
            gender=Gender.MALE,
            birth_date="2020-01-01",
            phone="13800138000"
        )
        member_service.create_member(member)

        return member.id

    # ==================== 测试用例 1: 处方记录保存 ====================

    def test_01_prescription_diagnosis_save(self, db_service, test_member):
        """
        TC-01: 处方记录保存 - 验证diagnosis字段正确保存

        步骤：
        1. 调用add_prescription添加处方记录，包含diagnosis字段
        2. 直接查询数据库验证diagnosis字段保存
        3. 验证保存值与输入值一致

        预期结果：diagnosis字段正确保存且可检索
        """
        service, db_path = db_service

        # 准备测试数据
        test_diagnosis = "急性上呼吸道感染"
        test_drugs = [
            {"name": "布洛芬混悬液", "dosage": "5ml/次", "frequency": "每8小时一次"},
            {"name": "小儿氨酚黄那敏颗粒", "dosage": "1袋/次", "frequency": "每日2次"}
        ]

        # 执行：添加处方记录
        record_id = service.add_prescription(
            member_id=test_member,
            date="2024-01-15",
            drugs=test_drugs,
            doctor="张医生",
            hospital="北京儿童医院",
            diagnosis=test_diagnosis
        )

        # 验证：直接查询数据库
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM prescription_records WHERE id = ?",
            (record_id,)
        ).fetchone()
        conn.close()

        # 断言
        assert row is not None, "记录未保存到数据库"
        assert row["member_id"] == test_member, "member_id不一致"
        assert row["diagnosis"] == test_diagnosis, f"diagnosis字段不一致: 期望'{test_diagnosis}', 实际'{row['diagnosis']}'"

        # 验证drugs字段正确序列化
        saved_drugs = json.loads(row["drugs"])
        assert saved_drugs == test_drugs, "drugs字段保存不一致"

        return {
            "test_case": "TC-01",
            "name": "处方记录diagnosis字段保存",
            "status": "PASS",
            "details": f"diagnosis='{test_diagnosis}' 正确保存"
        }

    def test_02_prescription_without_diagnosis(self, db_service, test_member):
        """
        TC-02: 处方记录保存 - 验证无diagnosis时也能正常保存

        步骤：
        1. 调用add_prescription不传diagnosis
        2. 验证记录仍能保存，diagnosis为NULL或空字符串

        预期结果：记录正常保存，diagnosis为NULL
        """
        service, db_path = db_service

        test_drugs = [{"name": "维生素C", "dosage": "1片/次", "frequency": "每日1次"}]

        # 执行：添加无diagnosis的处方
        record_id = service.add_prescription(
            member_id=test_member,
            date="2024-01-16",
            drugs=test_drugs,
            doctor=None,
            hospital=None,
            diagnosis=None
        )

        # 验证
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM prescription_records WHERE id = ?",
            (record_id,)
        ).fetchone()
        conn.close()

        assert row is not None, "记录未保存"
        assert row["diagnosis"] is None, f"diagnosis应为None，实际为'{row['diagnosis']}'"

        return {
            "test_case": "TC-02",
            "name": "处方记录无diagnosis保存",
            "status": "PASS",
            "details": "diagnosis为None时正确保存"
        }

    def test_03_prescription_special_characters(self, db_service, test_member):
        """
        TC-03: 处方记录保存 - 验证diagnosis中特殊字符处理

        步骤：
        1. 保存包含特殊字符（引号、换行符等）的diagnosis
        2. 验证特殊字符正确保存和读取

        预期结果：特殊字符正确保存，无SQL注入或转义问题
        """
        service, db_path = db_service

        # 包含特殊字符的诊断
        test_diagnosis = "急性支气管炎（\"喘息型\"），伴有\n咳嗽、发热等症状"

        test_drugs = [{"name": "阿莫西林", "dosage": "0.25g/次", "frequency": "每日3次"}]

        record_id = service.add_prescription(
            member_id=test_member,
            date="2024-01-17",
            drugs=test_drugs,
            diagnosis=test_diagnosis
        )

        # 验证
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM prescription_records WHERE id = ?",
            (record_id,)
        ).fetchone()
        conn.close()

        assert row["diagnosis"] == test_diagnosis, "特殊字符处理不正确"

        return {
            "test_case": "TC-03",
            "name": "处方记录特殊字符处理",
            "status": "PASS",
            "details": "特殊字符正确保存和读取"
        }

    # ==================== 测试用例 2: 问诊记录保存 ====================

    def test_04_consultation_summary_with_diagnosis(self, db_service, test_member):
        """
        TC-04: 问诊记录保存 - 验证summary包含诊断信息

        步骤：
        1. 添加包含诊断信息的summary问诊记录
        2. 验证summary正确保存
        3. 验证查询返回的诊断信息完整

        预期结果：summary字段正确保存且包含完整诊断信息
        """
        service, db_path = db_service

        # 包含诊断信息的问诊摘要
        test_summary = """患儿因发热3天就诊，体温最高39.2℃，伴有咳嗽、流涕。
查体：咽部充血，双肺呼吸音粗，未闻及干湿性啰音。
诊断：急性上呼吸道感染
处理：退热对症治疗，多饮水，观察病情变化。"""

        # 执行
        record_id = service.add_consultation(
            member_id=test_member,
            date="2024-01-18",
            summary=test_summary,
            doctor="李医生",
            hospital="首都儿科研究所",
            department="呼吸内科"
        )

        # 验证
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM consultation_records WHERE id = ?",
            (record_id,)
        ).fetchone()
        conn.close()

        assert row is not None, "问诊记录未保存"
        assert row["summary"] == test_summary, "summary内容不一致"
        assert "诊断：急性上呼吸道感染" in row["summary"], "诊断信息未包含在summary中"

        return {
            "test_case": "TC-04",
            "name": "问诊记录summary诊断信息",
            "status": "PASS",
            "details": "summary包含完整诊断信息"
        }

    def test_05_consultation_all_fields(self, db_service, test_member):
        """
        TC-05: 问诊记录保存 - 验证所有字段正确保存

        步骤：
        1. 添加包含所有字段的问诊记录
        2. 验证每个字段都正确保存

        预期结果：所有字段（date, summary, doctor, hospital, department）都正确保存
        """
        service, db_path = db_service

        record_id = service.add_consultation(
            member_id=test_member,
            date="2024-01-19",
            summary="常规复查，一切正常",
            doctor="王主任",
            hospital="协和医院",
            department="儿科"
        )

        # 验证
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM consultation_records WHERE id = ?",
            (record_id,)
        ).fetchone()
        conn.close()

        assert row["date"] == "2024-01-19", "date不一致"
        assert row["summary"] == "常规复查，一切正常", "summary不一致"
        assert row["doctor"] == "王主任", "doctor不一致"
        assert row["hospital"] == "协和医院", "hospital不一致"
        assert row["department"] == "儿科", "department不一致"

        return {
            "test_case": "TC-05",
            "name": "问诊记录所有字段保存",
            "status": "PASS",
            "details": "所有字段正确保存"
        }

    # ==================== 测试用例 3: 数据关联一致性 ====================

    def test_06_member_id_consistency(self, db_service, test_member):
        """
        TC-06: 数据关联一致性 - 验证member_id在所有记录中一致

        步骤：
        1. 为同一member添加多种类型记录
        2. 验证所有记录的member_id一致

        预期结果：所有记录的member_id与创建时指定的值一致
        """
        service, db_path = db_service

        # 添加多种记录
        prescription_id = service.add_prescription(
            member_id=test_member,
            date="2024-01-20",
            drugs=[{"name": "测试药物", "dosage": "1片", "frequency": "qd"}],
            diagnosis="测试诊断"
        )

        consultation_id = service.add_consultation(
            member_id=test_member,
            date="2024-01-20",
            summary="测试问诊",
            doctor="测试医生"
        )

        appointment_id = service.add_appointment(
            member_id=test_member,
            date="2024-01-21",
            department="儿科",
            hospital="测试医院"
        )

        # 验证所有记录的member_id
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        presc_row = conn.execute(
            "SELECT member_id FROM prescription_records WHERE id = ?",
            (prescription_id,)
        ).fetchone()

        consult_row = conn.execute(
            "SELECT member_id FROM consultation_records WHERE id = ?",
            (consultation_id,)
        ).fetchone()

        appoint_row = conn.execute(
            "SELECT member_id FROM appointment_records WHERE id = ?",
            (appointment_id,)
        ).fetchone()

        conn.close()

        assert presc_row["member_id"] == test_member, "处方记录member_id不一致"
        assert consult_row["member_id"] == test_member, "问诊记录member_id不一致"
        assert appoint_row["member_id"] == test_member, "挂号记录member_id不一致"

        return {
            "test_case": "TC-06",
            "name": "member_id一致性验证",
            "status": "PASS",
            "details": "所有记录类型member_id一致"
        }

    def test_07_timestamp_consistency(self, db_service, test_member):
        """
        TC-07: 时间戳一致性 - 验证created_at字段

        步骤：
        1. 添加记录前记录时间
        2. 添加记录
        3. 验证created_at在合理时间范围内

        预期结果：created_at在记录创建时间前后合理范围内（1分钟内）
        """
        service, db_path = db_service

        before_time = datetime.now()

        record_id = service.add_prescription(
            member_id=test_member,
            date="2024-01-22",
            drugs=[{"name": "测试", "dosage": "1片", "frequency": "qd"}],
            diagnosis="测试"
        )

        after_time = datetime.now()

        # 验证created_at
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT created_at FROM prescription_records WHERE id = ?",
            (record_id,)
        ).fetchone()
        conn.close()

        created_at = datetime.fromisoformat(row["created_at"])

        assert before_time <= created_at <= after_time, "created_at时间不在合理范围内"

        return {
            "test_case": "TC-07",
            "name": "created_at时间戳一致性",
            "status": "PASS",
            "details": f"created_at={created_at.isoformat()} 在合理范围内"
        }

    def test_08_date_field_vs_created_at(self, db_service, test_member):
        """
        TC-08: 日期字段与created_at关系验证

        步骤：
        1. 添加指定业务日期（date）的记录
        2. 验证date与created_at是独立字段
        3. 验证date是业务日期，created_at是系统创建时间

        预期结果：date和created_at各自独立，互不影响
        """
        service, db_path = db_service

        # 使用历史日期作为业务日期
        business_date = "2023-12-01"

        record_id = service.add_prescription(
            member_id=test_member,
            date=business_date,
            drugs=[{"name": "测试", "dosage": "1片", "frequency": "qd"}],
            diagnosis="测试"
        )

        # 验证
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT date, created_at FROM prescription_records WHERE id = ?",
            (record_id,)
        ).fetchone()
        conn.close()

        assert row["date"] == business_date, "业务日期不正确"

        created_at_date = datetime.fromisoformat(row["created_at"]).date()
        from datetime import date
        today = date.today()

        # created_at应该是今天（系统创建时间），不是历史日期
        assert created_at_date == today, "created_at应为系统当前时间，不应使用业务日期"

        return {
            "test_case": "TC-08",
            "name": "业务日期与系统时间分离",
            "status": "PASS",
            "details": "date和created_at正确分离"
        }

    # ==================== 测试用例 4: 记录查询完整性 ====================

    def test_09_prescription_query_completeness(self, db_service, test_member):
        """
        TC-09: 处方查询完整性 - 验证返回的诊断信息完整

        步骤：
        1. 添加处方记录
        2. 通过多种方式查询记录
        3. 验证查询结果包含完整信息

        预期结果：查询结果包含所有必要字段
        """
        service, db_path = db_service

        test_diagnosis = "支气管肺炎"
        test_drugs = [
            {"name": "阿奇霉素", "dosage": "0.15g", "frequency": "qd"},
            {"name": "氨溴索", "dosage": "15mg", "frequency": "tid"}
        ]

        record_id = service.add_prescription(
            member_id=test_member,
            date="2024-01-23",
            drugs=test_drugs,
            doctor="张主任",
            hospital="儿童医院",
            diagnosis=test_diagnosis
        )

        # 通过summary验证记录可被查询
        summary = service.get_records_summary(test_member)

        assert summary["prescription_count"] >= 1, "处方计数不正确"

        # 直接查询验证完整信息 - 使用record_id确保查询到正确的记录
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM prescription_records WHERE id = ?",
            (record_id,)
        ).fetchone()
        conn.close()

        assert row is not None, "记录未找到"
        assert row["diagnosis"] == test_diagnosis, f"查询结果diagnosis不完整: 期望'{test_diagnosis}', 实际'{row['diagnosis']}'"
        assert row["doctor"] == "张主任", f"查询结果doctor不完整: 期望'张主任', 实际'{row['doctor']}'"
        assert row["hospital"] == "儿童医院", f"查询结果hospital不完整: 期望'儿童医院', 实际'{row['hospital']}'"

        return {
            "test_case": "TC-09",
            "name": "处方查询完整性",
            "status": "PASS",
            "details": "查询返回完整诊断信息"
        }

    def test_10_consultation_query_completeness(self, db_service, test_member):
        """
        TC-10: 问诊查询完整性 - 验证查询返回summary包含诊断

        步骤：
        1. 添加问诊记录
        2. 验证records_summary计数正确
        3. 验证查询返回的summary完整

        预期结果：summary计数和内容都完整正确
        """
        service, db_path = db_service

        test_summary = "诊断：急性扁桃体炎。建议：抗感染治疗，注意休息。"

        service.add_consultation(
            member_id=test_member,
            date="2024-01-24",
            summary=test_summary,
            doctor="刘医生",
            hospital="友谊医院",
            department="耳鼻喉科"
        )

        # 验证summary
        summary = service.get_records_summary(test_member)

        assert summary["consultation_count"] >= 1, "问诊计数不正确"

        # 验证内容 - 记录ID从函数返回，确保查询正确记录
        # 由于add_consultation返回了record_id，我们可以用它查询
        record_id = service.add_consultation(
            member_id=test_member,
            date="2024-01-24",
            summary=test_summary,
            doctor="刘医生",
            hospital="友谊医院",
            department="耳鼻喉科"
        )

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT summary FROM consultation_records WHERE id = ?",
            (record_id,)
        ).fetchone()
        conn.close()

        assert row["summary"] == test_summary, f"查询的summary不完整: 期望'{test_summary}', 实际'{row['summary']}'"

        return {
            "test_case": "TC-10",
            "name": "问诊查询完整性",
            "status": "PASS",
            "details": "summary完整返回"
        }

    def test_11_cross_record_type_query(self, db_service, test_member):
        """
        TC-11: 跨记录类型查询 - 验证同一事件的多种记录关联

        步骤：
        1. 模拟一次就诊：添加问诊、处方、挂号
        2. 使用相同日期和医院
        3. 验证可以通过日期/医院查询到所有相关记录

        预期结果：同一次就诊的各类记录可以关联查询
        """
        service, db_path = db_service

        visit_date = "2024-01-25"
        hospital = "协和医院"
        diagnosis = "急性胃肠炎"

        # 同一次就诊的记录
        appointment_id = service.add_appointment(
            member_id=test_member,
            date=visit_date,
            department="儿科",
            hospital=hospital
        )

        consultation_id = service.add_consultation(
            member_id=test_member,
            date=visit_date,
            summary=f"诊断：{diagnosis}。主诉：腹痛、呕吐。",
            hospital=hospital,
            department="儿科"
        )

        prescription_id = service.add_prescription(
            member_id=test_member,
            date=visit_date,
            drugs=[{"name": "口服补液盐", "dosage": "1袋", "frequency": "prn"}],
            hospital=hospital,
            diagnosis=diagnosis
        )

        # 验证可以通过日期和医院关联查询
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        # 查询同一天同一医院的记录
        query = """
        SELECT 'appointment' as type, id, date, hospital FROM appointment_records
        WHERE member_id = ? AND date = ? AND hospital = ?
        UNION ALL
        SELECT 'consultation' as type, id, date, hospital FROM consultation_records
        WHERE member_id = ? AND date = ? AND hospital = ?
        UNION ALL
        SELECT 'prescription' as type, id, date, hospital FROM prescription_records
        WHERE member_id = ? AND date = ? AND hospital = ?
        """
        rows = conn.execute(query, (test_member, visit_date, hospital,
                                     test_member, visit_date, hospital,
                                     test_member, visit_date, hospital)).fetchall()
        conn.close()

        assert len(rows) >= 3, f"应找到至少3条关联记录，实际找到{len(rows)}条"

        return {
            "test_case": "TC-11",
            "name": "跨记录类型关联查询",
            "status": "PASS",
            "details": f"找到{len(rows)}条同一天就诊的关联记录"
        }

    def test_12_document_record_diagnosis(self, db_service, test_member):
        """
        TC-12: 病历存档记录 - 验证description可存储诊断信息

        步骤：
        1. 添加病历存档记录，description包含诊断
        2. 验证description正确保存

        预期结果：description字段正确保存诊断信息
        """
        service, db_path = db_service

        test_description = "诊断：过敏性鼻炎。病历记录：患儿反复打喷嚏、流清水样鼻涕3个月。"

        record_id = service.add_document(
            member_id=test_member,
            date="2024-01-26",
            doc_type="report",
            title="过敏原检测报告",
            description=test_description,
            hospital="协和医院"
        )

        # 验证
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT description FROM document_records WHERE id = ?",
            (record_id,)
        ).fetchone()
        conn.close()

        assert row["description"] == test_description, "description保存不正确"

        return {
            "test_case": "TC-12",
            "name": "病历存档description诊断信息",
            "status": "PASS",
            "details": "description正确保存诊断信息"
        }

    def test_13_checkup_record_abnormal_items(self, db_service, test_member):
        """
        TC-13: 体检记录 - 验证abnormal_items数组正确保存

        步骤：
        1. 添加包含异常项的体检记录
        2. 验证abnormal_items数组正确序列化和保存

        预期结果：abnormal_items正确保存为JSON数组
        """
        service, db_path = db_service

        test_abnormal_items = [
            {"item": "白细胞计数", "value": "12.5×10^9/L", "status": "偏高"},
            {"item": "C反应蛋白", "value": "15mg/L", "status": "偏高"}
        ]

        record_id = service.add_checkup(
            member_id=test_member,
            date="2024-01-27",
            checkup_type="blood_test",
            hospital="儿童医院",
            summary="血常规检查提示轻度炎症",
            results="白细胞偏高，提示感染",
            abnormal_items=test_abnormal_items
        )

        # 验证
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT abnormal_items FROM checkup_records WHERE id = ?",
            (record_id,)
        ).fetchone()
        conn.close()

        saved_items = json.loads(row["abnormal_items"])
        assert saved_items == test_abnormal_items, "abnormal_items保存不正确"

        return {
            "test_case": "TC-13",
            "name": "体检记录abnormal_items保存",
            "status": "PASS",
            "details": "abnormal_items数组正确保存"
        }

    # ==================== 边界和异常测试 ====================

    def test_14_empty_diagnosis(self, db_service, test_member):
        """
        TC-14: 边界测试 - 空字符串diagnosis处理

        步骤：
        1. 传入空字符串作为diagnosis
        2. 验证空字符串正确保存（非NULL）

        预期结果：空字符串应正确保存
        """
        service, db_path = db_service

        record_id = service.add_prescription(
            member_id=test_member,
            date="2024-01-28",
            drugs=[{"name": "测试", "dosage": "1片", "frequency": "qd"}],
            diagnosis=""
        )

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT diagnosis FROM prescription_records WHERE id = ?",
            (record_id,)
        ).fetchone()
        conn.close()

        # 空字符串应该被保存
        assert row["diagnosis"] == "", "空字符串未正确保存"

        return {
            "test_case": "TC-14",
            "name": "空字符串diagnosis处理",
            "status": "PASS",
            "details": "空字符串正确保存"
        }

    def test_15_unicode_diagnosis(self, db_service, test_member):
        """
        TC-15: 字符编码测试 - Unicode字符诊断

        步骤：
        1. 使用包含emoji、特殊符号的diagnosis
        2. 验证Unicode字符正确保存

        预期结果：Unicode字符正确保存和读取
        """
        service, db_path = db_service

        test_diagnosis = "发热 🔥 咳嗽😷 腹痛🤢 诊断：上呼吸道感染 🏥"

        record_id = service.add_prescription(
            member_id=test_member,
            date="2024-01-29",
            drugs=[{"name": "测试药物", "dosage": "1片", "frequency": "qd"}],
            diagnosis=test_diagnosis
        )

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT diagnosis FROM prescription_records WHERE id = ?",
            (record_id,)
        ).fetchone()
        conn.close()

        assert row["diagnosis"] == test_diagnosis, "Unicode字符处理不正确"

        return {
            "test_case": "TC-15",
            "name": "Unicode诊断字符处理",
            "status": "PASS",
            "details": "Unicode字符正确保存"
        }


# ==================== 测试报告生成 ====================

class TestReportGenerator:
    """测试报告生成器"""

    @staticmethod
    def generate_report(test_results: list) -> str:
        """生成测试报告"""
        report = []
        report.append("=" * 80)
        report.append("单据保存数据一致性测试报告")
        report.append("=" * 80)
        report.append("")

        # 汇总统计
        total = len(test_results)
        passed = sum(1 for r in test_results if r.get("status") == "PASS")
        failed = total - passed

        report.append("【测试汇总】")
        report.append(f"  总用例数: {total}")
        report.append(f"  通过: {passed}")
        report.append(f"  失败: {failed}")
        report.append(f"  通过率: {passed/total*100:.1f}%")
        report.append("")

        # 详细结果
        report.append("【详细结果】")
        for result in test_results:
            status_icon = "✓" if result.get("status") == "PASS" else "✗"
            report.append(f"  {status_icon} {result.get('test_case', 'N/A')}: {result.get('name', 'N/A')}")
            report.append(f"      状态: {result.get('status', 'UNKNOWN')}")
            report.append(f"      详情: {result.get('details', 'N/A')}")
            report.append("")

        # 问题汇总
        if failed > 0:
            report.append("【发现的问题】")
            for result in test_results:
                if result.get("status") != "PASS":
                    report.append(f"  - {result.get('test_case')}: {result.get('details')}")
            report.append("")

        report.append("=" * 80)

        return "\n".join(report)


# ==================== 主测试运行器 ====================

def run_consistency_tests():
    """运行所有数据一致性测试并生成报告"""
    import tempfile

    print("开始执行单据保存数据一致性测试...")

    # 创建临时数据库
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        # 初始化服务
        from app.services.profile_service import HealthRecordsService, MemberProfileService, MemberProfile
        from app.models.user import Relationship, Gender, IdCardType

        health_records_service = HealthRecordsService(db_path)
        health_records_service.init_records_tables()

        member_service = MemberProfileService(db_path)
        member_service.init_member_tables()

        # 创建测试成员
        member = MemberProfile(
            id="test_member_report_001",
            user_id="test_user_report",
            name="测试儿童报告",
            relationship=Relationship.CHILD,
            id_card_type=IdCardType.ID_CARD,
            id_card_number="110101202001011234",
            gender=Gender.MALE,
            birth_date="2020-01-01",
        )
        member_id = member_service.create_member(member)

        # 执行测试
        test_results = []
        test_class = TestDataConsistency()

        # TC-01: 处方记录diagnosis保存
        try:
            result = test_class.test_01_prescription_diagnosis_save(
                (health_records_service, db_path), member_id
            )
            test_results.append(result)
        except Exception as e:
            test_results.append({
                "test_case": "TC-01",
                "name": "处方记录diagnosis字段保存",
                "status": "FAIL",
                "details": f"异常: {str(e)}"
            })

        # TC-02: 无diagnosis处方保存
        try:
            result = test_class.test_02_prescription_without_diagnosis(
                (health_records_service, db_path), member_id
            )
            test_results.append(result)
        except Exception as e:
            test_results.append({
                "test_case": "TC-02",
                "name": "处方记录无diagnosis保存",
                "status": "FAIL",
                "details": f"异常: {str(e)}"
            })

        # TC-03: 特殊字符处理
        try:
            result = test_class.test_03_prescription_special_characters(
                (health_records_service, db_path), member_id
            )
            test_results.append(result)
        except Exception as e:
            test_results.append({
                "test_case": "TC-03",
                "name": "处方记录特殊字符处理",
                "status": "FAIL",
                "details": f"异常: {str(e)}"
            })

        # TC-04: 问诊记录summary诊断信息
        try:
            result = test_class.test_04_consultation_summary_with_diagnosis(
                (health_records_service, db_path), member_id
            )
            test_results.append(result)
        except Exception as e:
            test_results.append({
                "test_case": "TC-04",
                "name": "问诊记录summary诊断信息",
                "status": "FAIL",
                "details": f"异常: {str(e)}"
            })

        # TC-05: 问诊记录所有字段
        try:
            result = test_class.test_05_consultation_all_fields(
                (health_records_service, db_path), member_id
            )
            test_results.append(result)
        except Exception as e:
            test_results.append({
                "test_case": "TC-05",
                "name": "问诊记录所有字段保存",
                "status": "FAIL",
                "details": f"异常: {str(e)}"
            })

        # TC-06: member_id一致性
        try:
            result = test_class.test_06_member_id_consistency(
                (health_records_service, db_path), member_id
            )
            test_results.append(result)
        except Exception as e:
            test_results.append({
                "test_case": "TC-06",
                "name": "member_id一致性验证",
                "status": "FAIL",
                "details": f"异常: {str(e)}"
            })

        # TC-07: 时间戳一致性
        try:
            result = test_class.test_07_timestamp_consistency(
                (health_records_service, db_path), member_id
            )
            test_results.append(result)
        except Exception as e:
            test_results.append({
                "test_case": "TC-07",
                "name": "created_at时间戳一致性",
                "status": "FAIL",
                "details": f"异常: {str(e)}"
            })

        # TC-08: 业务日期与系统时间分离
        try:
            result = test_class.test_08_date_field_vs_created_at(
                (health_records_service, db_path), member_id
            )
            test_results.append(result)
        except Exception as e:
            test_results.append({
                "test_case": "TC-08",
                "name": "业务日期与系统时间分离",
                "status": "FAIL",
                "details": f"异常: {str(e)}"
            })

        # TC-09: 处方查询完整性
        try:
            result = test_class.test_09_prescription_query_completeness(
                (health_records_service, db_path), member_id
            )
            test_results.append(result)
        except Exception as e:
            test_results.append({
                "test_case": "TC-09",
                "name": "处方查询完整性",
                "status": "FAIL",
                "details": f"异常: {str(e)}"
            })

        # TC-10: 问诊查询完整性
        try:
            result = test_class.test_10_consultation_query_completeness(
                (health_records_service, db_path), member_id
            )
            test_results.append(result)
        except Exception as e:
            test_results.append({
                "test_case": "TC-10",
                "name": "问诊查询完整性",
                "status": "FAIL",
                "details": f"异常: {str(e)}"
            })

        # TC-11: 跨记录类型关联查询
        try:
            result = test_class.test_11_cross_record_type_query(
                (health_records_service, db_path), member_id
            )
            test_results.append(result)
        except Exception as e:
            test_results.append({
                "test_case": "TC-11",
                "name": "跨记录类型关联查询",
                "status": "FAIL",
                "details": f"异常: {str(e)}"
            })

        # TC-12: 病历存档description
        try:
            result = test_class.test_12_document_record_diagnosis(
                (health_records_service, db_path), member_id
            )
            test_results.append(result)
        except Exception as e:
            test_results.append({
                "test_case": "TC-12",
                "name": "病历存档description诊断信息",
                "status": "FAIL",
                "details": f"异常: {str(e)}"
            })

        # TC-13: 体检记录abnormal_items
        try:
            result = test_class.test_13_checkup_record_abnormal_items(
                (health_records_service, db_path), member_id
            )
            test_results.append(result)
        except Exception as e:
            test_results.append({
                "test_case": "TC-13",
                "name": "体检记录abnormal_items保存",
                "status": "FAIL",
                "details": f"异常: {str(e)}"
            })

        # TC-14: 空字符串diagnosis
        try:
            result = test_class.test_14_empty_diagnosis(
                (health_records_service, db_path), member_id
            )
            test_results.append(result)
        except Exception as e:
            test_results.append({
                "test_case": "TC-14",
                "name": "空字符串diagnosis处理",
                "status": "FAIL",
                "details": f"异常: {str(e)}"
            })

        # TC-15: Unicode诊断字符
        try:
            result = test_class.test_15_unicode_diagnosis(
                (health_records_service, db_path), member_id
            )
            test_results.append(result)
        except Exception as e:
            test_results.append({
                "test_case": "TC-15",
                "name": "Unicode诊断字符处理",
                "status": "FAIL",
                "details": f"异常: {str(e)}"
            })

        # 生成报告
        report = TestReportGenerator.generate_report(test_results)
        print(report)

        return test_results, report

    finally:
        # 清理
        try:
            os.unlink(db_path)
        except:
            pass


if __name__ == "__main__":
    run_consistency_tests()
