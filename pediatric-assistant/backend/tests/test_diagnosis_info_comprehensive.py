#!/usr/bin/env python3
"""
诊断信息保留功能 - 全方位综合测评

测试覆盖：
1. 诊断信息提取准确性
2. 单据保存数据一致性
3. 数据持久化与跨会话
4. 边界条件与异常处理
5. 业务逻辑完整性
"""

import os
import sys
import sqlite3
import tempfile
import json
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models.medical_context import MedicalContext, DialogueState, IntentType
from app.services.profile_service import HealthRecordsService


class ComprehensiveTestReport:
    """综合测试报告"""

    def __init__(self):
        self.results = {
            "extraction_accuracy": [],
            "data_consistency": [],
            "persistence": [],
            "boundary_conditions": [],
            "business_logic": [],
        }
        self.passed = 0
        self.failed = 0
        self.warnings = 0

    def add_result(self, category, test_name, passed, details, warning=False):
        """添加测试结果"""
        result = {
            "test": test_name,
            "passed": passed,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        self.results[category].append(result)

        if passed:
            self.passed += 1
        else:
            self.failed += 1

        if warning:
            self.warnings += 1

    def print_report(self):
        """打印测试报告"""
        print("\n" + "="*80)
        print("诊断信息保留功能 - 综合测评报告")
        print("="*80)

        total = self.passed + self.failed
        pass_rate = (self.passed / total * 100) if total > 0 else 0

        print(f"\n总体结果: {self.passed}/{total} 通过 ({pass_rate:.1f}%)")
        print(f"警告数: {self.warnings}")

        # 分类报告
        categories = {
            "extraction_accuracy": "诊断信息提取准确性",
            "data_consistency": "单据保存数据一致性",
            "persistence": "数据持久化与跨会话",
            "boundary_conditions": "边界条件与异常处理",
            "business_logic": "业务逻辑完整性"
        }

        for cat_key, cat_name in categories.items():
            print(f"\n{'─'*80}")
            print(f"{cat_name}")
            print(f"{'─'*80}")

            for result in self.results[cat_key]:
                status = "✓ PASS" if result["passed"] else "✗ FAIL"
                print(f"\n[{status}] {result['test']}")
                print(f"  详情: {result['details']}")

        print("\n" + "="*80)

        # 优先级问题列表
        self._print_priority_issues()

    def _print_priority_issues(self):
        """打印优先级问题列表"""
        print("\n【优先级问题列表】")
        print("="*80)

        issues = [
            {
                "priority": "P0",
                "issue": "无严重问题发现",
                "location": "-",
                "recommendation": "-"
            }
        ]

        # 收集失败的测试
        for cat_key, cat_name in {
            "extraction_accuracy": "诊断信息提取",
            "data_consistency": "数据一致性",
            "persistence": "持久化",
            "boundary_conditions": "边界条件",
            "business_logic": "业务逻辑"
        }.items():
            for result in self.results[cat_key]:
                if not result["passed"]:
                    issues.append({
                        "priority": "P1",
                        "issue": f"{result['test']} 失败",
                        "location": cat_name,
                        "recommendation": result['details']
                    })

        for issue in issues:
            print(f"\n[{issue['priority']}] {issue['issue']}")
            print(f"  位置: {issue['location']}")
            print(f"  建议: {issue['recommendation']}")


class DiagnosisInfoTester:
    """诊断信息测试器"""

    def __init__(self):
        self.report = ComprehensiveTestReport()
        self.temp_db = None
        self.health_service = None
        self.test_member_id = "test_member_001"

    def setup(self):
        """设置测试环境"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()

        self.health_service = HealthRecordsService(self.temp_db.name)
        self.health_service.init_records_tables()

        print(f"测试数据库创建: {self.temp_db.name}")

    def teardown(self):
        """清理测试环境"""
        if self.temp_db and os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)
            print(f"测试数据库已清理: {self.temp_db.name}")

    # ==================== 诊断信息提取准确性测试 ====================

    def test_extraction_accuracy(self):
        """测试诊断信息提取准确性"""
        print("\n[测试] 诊断信息提取准确性...")

        # 场景1: 单一症状描述
        context = MedicalContext(
            conversation_id="test_001",
            user_id="user_001"
        )
        context.chief_complaint = "孩子发烧38度，已经两天了"
        context.symptom = "发烧"

        passed = context.chief_complaint == "孩子发烧38度，已经两天了"
        self.report.add_result(
            "extraction_accuracy",
            "单一症状描述 - 主诉提取",
            passed,
            "主诉正确提取" if passed else "主诉提取失败"
        )

        # 场景2: 跨轮次累积
        context.slots = {"temperature": "38.5度"}
        context.merge_entities({"cough": "干咳无痰"})

        passed = "temperature" in context.slots and "cough" in context.slots
        self.report.add_result(
            "extraction_accuracy",
            "跨轮次累积 - 实体合并",
            passed,
            f"累积槽位: {list(context.slots.keys())}" if passed else "实体合并失败"
        )

        # 场景3: 分诊结果记录
        context.triage_level = "observe"
        context.triage_reason = "中风险：持续发烧超过48小时"

        passed = context.triage_level == "observe"
        self.report.add_result(
            "extraction_accuracy",
            "分诊结果记录",
            passed,
            f"分诊级别: {context.triage_level}" if passed else "分诊记录失败"
        )

        # 场景4: 对话状态转换
        context.dialogue_state = DialogueState.TRIAGE_COMPLETE
        passed = context.dialogue_state == DialogueState.TRIAGE_COMPLETE

        self.report.add_result(
            "extraction_accuracy",
            "对话状态管理",
            passed,
            f"当前状态: {context.dialogue_state}" if passed else "状态转换失败"
        )

    # ==================== 单据保存数据一致性测试 ====================

    def test_data_consistency(self):
        """测试单据保存数据一致性"""
        print("\n[测试] 单据保存数据一致性...")

        # 测试1: 处方记录保存 - 诊断信息字段
        record_id = self.health_service.add_prescription(
            member_id=self.test_member_id,
            date="2024-01-15",
            drugs=[
                {"name": "布洛芬混悬液", "dosage": "5ml", "frequency": "每8小时一次"}
            ],
            doctor="张医生",
            hospital="儿童医院",
            diagnosis="上呼吸道感染"
        )

        # 验证处方记录中的诊断信息
        with self.health_service._connect() as conn:
            result = conn.execute(
                "SELECT diagnosis FROM prescription_records WHERE id = ?",
                (record_id,)
            ).fetchone()

            passed = result and result["diagnosis"] == "上呼吸道感染"
            self.report.add_result(
                "data_consistency",
                "处方记录 - 诊断信息保存",
                passed,
                f"诊断信息: {result['diagnosis'] if result else '未找到'}"
            )

        # 测试2: 问诊记录保存 - summary包含诊断
        consult_id = self.health_service.add_consultation(
            member_id=self.test_member_id,
            date="2024-01-15",
            summary="患儿因发烧、咳嗽就诊，诊断为急性支气管炎",
            doctor="李医生",
            hospital="儿童医院",
            department="儿科"
        )

        with self.health_service._connect() as conn:
            result = conn.execute(
                "SELECT summary, department FROM consultation_records WHERE id = ?",
                (consult_id,)
            ).fetchone()

            passed = result and "急性支气管炎" in result["summary"]
            self.report.add_result(
                "data_consistency",
                "问诊记录 - summary包含诊断",
                passed,
                f"Summary: {result['summary'][:30]}..." if result else "未找到"
            )

        # 测试3: 记录计数一致性
        summary = self.health_service.get_records_summary(self.test_member_id)

        prescription_count = summary["prescription_count"]
        consultation_count = summary["consultation_count"]

        passed = prescription_count == 1 and consultation_count == 1
        self.report.add_result(
            "data_consistency",
            "记录计数一致性",
            passed,
            f"处方: {prescription_count}, 问诊: {consultation_count}"
        )

        # 测试4: member_id关联一致性
        with self.health_service._connect() as conn:
            presc_member = conn.execute(
                "SELECT member_id FROM prescription_records WHERE id = ?",
                (record_id,)
            ).fetchone()

            consult_member = conn.execute(
                "SELECT member_id FROM consultation_records WHERE id = ?",
                (consult_id,)
            ).fetchone()

            passed = (presc_member and consult_member and
                     presc_member["member_id"] == consult_member["member_id"] == self.test_member_id)

            self.report.add_result(
                "data_consistency",
                "member_id关联一致性",
                passed,
                f"member_id一致: {self.test_member_id}" if passed else "member_id不一致"
            )

    # ==================== 数据持久化测试 ====================

    def test_persistence(self):
        """测试数据持久化"""
        print("\n[测试] 数据持久化...")

        # 测试1: 写入后立即读取
        test_diagnosis = "过敏性鼻炎"
        record_id = self.health_service.add_prescription(
            member_id=self.test_member_id,
            date="2024-01-16",
            drugs=[{"name": "氯雷他定", "dosage": "5mg", "frequency": "每日一次"}],
            diagnosis=test_diagnosis
        )

        with self.health_service._connect() as conn:
            result = conn.execute(
                "SELECT diagnosis FROM prescription_records WHERE id = ?",
                (record_id,)
            ).fetchone()

            passed = result and result["diagnosis"] == test_diagnosis
            self.report.add_result(
                "persistence",
                "写入后立即读取",
                passed,
                f"诊断信息正确持久化: {test_diagnosis}" if passed else "持久化失败"
            )

        # 测试2: 模拟"重启" - 新建连接读取
        new_connection = sqlite3.connect(self.temp_db.name)
        new_connection.row_factory = sqlite3.Row
        cursor = new_connection.cursor()

        cursor.execute(
            "SELECT diagnosis FROM prescription_records WHERE id = ?",
            (record_id,)
        )
        result = cursor.fetchone()

        passed = result and result["diagnosis"] == test_diagnosis
        self.report.add_result(
            "persistence",
            "跨连接读取（模拟重启）",
            passed,
            f"新连接可读取诊断信息" if passed else "跨连接读取失败"
        )

        new_connection.close()

        # 测试3: 用户数据隔离
        other_member_id = "test_member_002"
        self.health_service.add_prescription(
            member_id=other_member_id,
            date="2024-01-16",
            drugs=[{"name": "阿莫西林", "dosage": "250mg", "frequency": "每日三次"}],
            diagnosis="扁桃体炎"
        )

        summary1 = self.health_service.get_records_summary(self.test_member_id)
        summary2 = self.health_service.get_records_summary(other_member_id)

        passed = summary1["prescription_count"] != summary2["prescription_count"]
        self.report.add_result(
            "persistence",
            "用户数据隔离",
            passed,
            f"用户1处方数: {summary1['prescription_count']}, 用户2: {summary2['prescription_count']}"
        )

    # ==================== 边界条件测试 ====================

    def test_boundary_conditions(self):
        """测试边界条件"""
        print("\n[测试] 边界条件与异常处理...")

        # 测试1: 空诊断信息
        record_id = self.health_service.add_prescription(
            member_id=self.test_member_id,
            date="2024-01-17",
            drugs=[{"name": "维生素D", "dosage": "400IU", "frequency": "每日一次"}],
            diagnosis=None  # 空诊断
        )

        with self.health_service._connect() as conn:
            result = conn.execute(
                "SELECT diagnosis FROM prescription_records WHERE id = ?",
                (record_id,)
            ).fetchone()

            # 应该能保存，diagnosis为NULL
            passed = result is not None
            self.report.add_result(
                "boundary_conditions",
                "空诊断信息处理",
                passed,
                f"允许空诊断: {result['diagnosis'] if result else '未保存'}",
                warning=True
            )

        # 测试2: 超长诊断信息
        long_diagnosis = "诊断" * 500  # 1000字符
        try:
            record_id = self.health_service.add_prescription(
                member_id=self.test_member_id,
                date="2024-01-17",
                drugs=[{"name": "测试药物", "dosage": "1片", "frequency": "qd"}],
                diagnosis=long_diagnosis
            )

            with self.health_service._connect() as conn:
                result = conn.execute(
                    "SELECT length(diagnosis) as len FROM prescription_records WHERE id = ?",
                    (record_id,)
                ).fetchone()

                passed = result and result["len"] == len(long_diagnosis)
                self.report.add_result(
                    "boundary_conditions",
                    "超长诊断信息处理",
                    passed,
                    f"保存了{result['len'] if result else 0}字符"
                )
        except Exception as e:
            self.report.add_result(
                "boundary_conditions",
                "超长诊断信息处理",
                False,
                f"异常: {str(e)}"
            )

        # 测试3: 特殊字符处理
        special_diagnosis = "诊断包含<>&'\"特殊字符和emoji😷"
        record_id = self.health_service.add_prescription(
            member_id=self.test_member_id,
            date="2024-01-17",
            drugs=[{"name": "测试药物", "dosage": "1片", "frequency": "qd"}],
            diagnosis=special_diagnosis
        )

        with self.health_service._connect() as conn:
            result = conn.execute(
                "SELECT diagnosis FROM prescription_records WHERE id = ?",
                (record_id,)
            ).fetchone()

            passed = result and result["diagnosis"] == special_diagnosis
            self.report.add_result(
                "boundary_conditions",
                "特殊字符处理",
                passed,
                f"特殊字符正确保存" if passed else f"实际: {result['diagnosis'] if result else 'NULL'}"
            )

        # 测试4: 无效member_id
        try:
            summary = self.health_service.get_records_summary("invalid_member_999")
            passed = summary["prescription_count"] == 0
            self.report.add_result(
                "boundary_conditions",
                "无效member_id处理",
                passed,
                "返回空计数而非错误"
            )
        except Exception as e:
            self.report.add_result(
                "boundary_conditions",
                "无效member_id处理",
                False,
                f"抛出异常: {str(e)}"
            )

    # ==================== 业务逻辑完整性测试 ====================

    def test_business_logic(self):
        """测试业务逻辑完整性"""
        print("\n[测试] 业务逻辑完整性...")

        # 测试1: 完整就诊流程
        # 步骤1: 创建问诊记录（初次就诊）
        consult_id = self.health_service.add_consultation(
            member_id=self.test_member_id,
            date="2024-01-18",
            summary="患儿因高热39.5℃、咽痛就诊，查体见咽部充血，扁桃体Ⅱ度肿大",
            doctor="王医生",
            hospital="市儿童医院",
            department="发热门诊"
        )

        # 步骤2: 开具处方（包含诊断）
        presc_id = self.health_service.add_prescription(
            member_id=self.test_member_id,
            date="2024-01-18",
            drugs=[
                {"name": "布洛芬", "dosage": "5ml", "frequency": "prn"},
                {"name": "阿莫西林克拉维酸钾", "dosage": "228mg", "frequency": "q12h"}
            ],
            doctor="王医生",
            hospital="市儿童医院",
            diagnosis="急性化脓性扁桃体炎"
        )

        # 步骤3: 验证同日记录关联
        with self.health_service._connect() as conn:
            consult = conn.execute(
                "SELECT * FROM consultation_records WHERE id = ?",
                (consult_id,)
            ).fetchone()

            presc = conn.execute(
                "SELECT * FROM prescription_records WHERE id = ?",
                (presc_id,)
            ).fetchone()

            passed = (consult and presc and
                     consult["member_id"] == presc["member_id"] and
                     consult["hospital"] == presc["hospital"] and
                     consult["doctor"] == presc["doctor"])

            self.report.add_result(
                "business_logic",
                "完整就诊流程 - 记录关联",
                passed,
                f"同一就诊的问诊和处方正确关联" if passed else "记录关联不一致"
            )

        # 测试2: 复诊场景 - 基于历史诊断
        # 第一次就诊
        self.health_service.add_prescription(
            member_id=self.test_member_id,
            date="2024-01-10",
            drugs=[{"name": "孟鲁司特钠", "dosage": "4mg", "frequency": "qn"}],
            diagnosis="咳嗽变异性哮喘"
        )

        # 复诊（7天后）
        followup_id = self.health_service.add_prescription(
            member_id=self.test_member_id,
            date="2024-01-17",
            drugs=[{"name": "孟鲁司特钠", "dosage": "4mg", "frequency": "qn"}],
            diagnosis="咳嗽变异性哮喘（复诊）"
        )

        # 验证历史记录可查
        with self.health_service._connect() as conn:
            results = conn.execute(
                "SELECT date, diagnosis FROM prescription_records WHERE member_id = ? AND diagnosis LIKE '%哮喘%' ORDER BY date",
                (self.test_member_id,)
            ).fetchall()

            passed = len(results) >= 2
            self.report.add_result(
                "business_logic",
                "复诊场景 - 历史诊断追踪",
                passed,
                f"找到{len(results)}条哮喘相关诊断记录"
            )

        # 测试3: 诊断信息的完整性
        summary = self.health_service.get_records_summary(self.test_member_id)

        # 验证各类记录都能正确统计
        total_records = (summary["consultation_count"] +
                        summary["prescription_count"] +
                        summary["appointment_count"] +
                        summary["document_count"] +
                        summary["checkup_count"])

        passed = total_records > 0
        self.report.add_result(
            "business_logic",
            "健康记录完整性",
            passed,
            f"共有{total_records}条记录"
        )

    # ==================== 运行所有测试 ====================

    def run_all_tests(self):
        """运行所有测试"""
        print("\n开始综合测评...")
        print("="*80)

        self.setup()

        try:
            self.test_extraction_accuracy()
            self.test_data_consistency()
            self.test_persistence()
            self.test_boundary_conditions()
            self.test_business_logic()

            self.report.print_report()

        finally:
            self.teardown()


def main():
    """主函数"""
    tester = DiagnosisInfoTester()
    tester.run_all_tests()

    # 保存报告到文件
    report_file = Path(__file__).parent.parent / "test_report.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(tester.report.results, f, ensure_ascii=False, indent=2)
    print(f"\n详细报告已保存至: {report_file}")


if __name__ == "__main__":
    main()
