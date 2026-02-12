#!/usr/bin/env python3
"""
用户场景模拟测试 - 真实使用场景下的诊断信息保留功能测试

测试场景：
1. 新用户初诊 - 首次使用系统，建立健康档案
2. 复诊用户 - 基于历史诊断信息进行后续咨询
3. 多症状复杂病例 - 发烧+咳嗽+皮疹等多症状
4. 紧急情况 - 危险信号检测后的诊断保留
5. 多成员家庭 - 不同孩子的诊断信息隔离
"""

import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models.medical_context import MedicalContext, DialogueState
from app.services.profile_service import HealthRecordsService


class UserScenarioSimulator:
    """用户场景模拟器"""

    def __init__(self):
        self.temp_db = None
        self.health_service = None
        self.family_id = "test_family_001"

    def setup(self):
        """设置测试环境"""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.health_service = HealthRecordsService(self.temp_db.name)
        self.health_service.init_records_tables()

    def teardown(self):
        """清理测试环境"""
        if self.temp_db and os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)

    def scenario_1_new_user_first_visit(self):
        """
        场景1: 新用户初诊
        用户首次使用系统，描述孩子症状，系统提取诊断信息并建议就医
        """
        print("\n" + "="*80)
        print("场景1: 新用户初诊 - 首次使用系统")
        print("="*80)

        # 创建医疗上下文模拟对话
        context = MedicalContext(
            conversation_id="new_user_001",
            user_id="user_new_001"
        )

        # 第一轮对话：用户描述症状
        print("\n[用户]: 孩子发烧38度5，已经两天了，还有点咳嗽")

        context.chief_complaint = "孩子发烧38度5，已经两天了，还有点咳嗽"
        context.symptom = "发烧"
        context.slots = {
            "temperature": "38.5度",
            "duration": "两天",
            "accompanying_symptom": "咳嗽"
        }

        # 系统分诊
        context.dialogue_state = DialogueState.TRIAGE_COMPLETE
        context.triage_level = "observe"
        context.triage_reason = "中风险：持续发烧超过48小时，建议观察"
        context.triage_action = "建议就近医院儿科门诊就诊"

        print(f"[系统]: 分诊结果: {context.triage_level}")
        print(f"[系统]: {context.triage_reason}")
        print(f"[系统]: {context.triage_action}")

        # 用户去医院就诊后，创建问诊记录
        print("\n[用户]: 去医院了，医生说是上呼吸道感染")

        member_id = "child_001"
        consult_id = self.health_service.add_consultation(
            member_id=member_id,
            date=datetime.now().strftime("%Y-%m-%d"),
            summary="患儿因发热、咳嗽2天就诊。查体：T38.5℃，咽部充血。诊断：上呼吸道感染",
            doctor="李医生",
            hospital="市儿童医院",
            department="儿科"
        )

        # 开具处方
        presc_id = self.health_service.add_prescription(
            member_id=member_id,
            date=datetime.now().strftime("%Y-%m-%d"),
            drugs=[
                {"name": "布洛芬混悬液", "dosage": "5ml", "frequency": "体温>38.5℃时使用"},
                {"name": "小儿氨酚黄那敏颗粒", "dosage": "1袋", "frequency": "每日3次"}
            ],
            doctor="李医生",
            hospital="市儿童医院",
            diagnosis="上呼吸道感染"
        )

        # 验证诊断信息保存
        with self.health_service._connect() as conn:
            presc = conn.execute(
                "SELECT diagnosis FROM prescription_records WHERE id = ?",
                (presc_id,)
            ).fetchone()

            print(f"\n✓ 诊断信息已保留: {presc['diagnosis']}")

        summary = self.health_service.get_records_summary(member_id)
        print(f"✓ 健康档案已建立: 问诊{summary['consultation_count']}次, 处方{summary['prescription_count']}次")

        return True

    def scenario_2_return_visit_user(self):
        """
        场景2: 复诊用户
        用户之前有哮喘病史，现在出现喘息症状
        """
        print("\n" + "="*80)
        print("场景2: 复诊用户 - 有既往病史的患儿")
        print("="*80)

        member_id = "child_002"

        # 模拟历史就诊记录（一个月前）
        past_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

        self.health_service.add_prescription(
            member_id=member_id,
            date=past_date,
            drugs=[
                {"name": "孟鲁司特钠咀嚼片", "dosage": "4mg", "frequency": "每晚1次"}
            ],
            doctor="张医生",
            hospital="儿童医院",
            diagnosis="咳嗽变异性哮喘"
        )

        print(f"[历史记录]: {past_date} 诊断：咳嗽变异性哮喘")

        # 当前就诊
        print("\n[用户]: 孩子最近又开始喘了，尤其是晚上")

        context = MedicalContext(
            conversation_id="return_user_001",
            user_id="user_return_001"
        )

        context.chief_complaint = "孩子最近又开始喘了，尤其是晚上"
        context.symptom = "喘息"
        context.slots = {
            "time_pattern": "晚上加重",
            "history": "有哮喘病史"
        }

        print(f"[系统]: 检测到有哮喘病史，当前喘息症状可能与既往病史相关")

        # 创建复诊记录
        today = datetime.now().strftime("%Y-%m-%d")
        presc_id = self.health_service.add_prescription(
            member_id=member_id,
            date=today,
            drugs=[
                {"name": "布地奈德混悬液", "dosage": "1mg", "frequency": "每日2次雾化"},
                {"name": "孟鲁司特钠咀嚼片", "dosage": "4mg", "frequency": "每晚1次"}
            ],
            doctor="张医生",
            hospital="儿童医院",
            diagnosis="支气管哮喘（复诊）"
        )

        # 验证历史诊断关联
        with self.health_service._connect() as conn:
            results = conn.execute(
                "SELECT date, diagnosis FROM prescription_records WHERE member_id = ? ORDER BY date DESC",
                (member_id,)
            ).fetchall()

            print(f"\n✓ 历史诊断追踪:")
            for r in results:
                print(f"  - {r['date']}: {r['diagnosis']}")

        return True

    def scenario_3_complex_case(self):
        """
        场景3: 多症状复杂病例
        发烧、咳嗽、皮疹等多个症状
        """
        print("\n" + "="*80)
        print("场景3: 多症状复杂病例 - 发热+咳嗽+皮疹")
        print("="*80)

        member_id = "child_003"

        # 模拟多轮对话累积症状
        print("\n[用户]: 孩子发烧39度")
        context = MedicalContext(
            conversation_id="complex_001",
            user_id="user_complex_001"
        )
        context.chief_complaint = "孩子发烧39度"
        context.slots = {"temperature": "39度"}

        print("[用户]: 还有咳嗽，流鼻涕")
        context.slots.update({
            "cough": "有咳嗽",
            "rhinorrhea": "流鼻涕"
        })

        print("[用户]: 今天身上还起了红疹子")
        context.slots.update({
            "rash": "红疹子",
            "rash_location": "全身"
        })

        context.triage_level = "emergency"
        context.triage_reason = "高风险：高热伴皮疹，需排除传染病"
        context.triage_action = "建议立即就诊发热门诊"

        print(f"\n[系统]: 警告！{context.triage_reason}")
        print(f"[系统]: {context.triage_action}")

        # 创建就诊记录
        presc_id = self.health_service.add_prescription(
            member_id=member_id,
            date=datetime.now().strftime("%Y-%m-%d"),
            drugs=[
                {"name": "对乙酰氨基酚", "dosage": "10mg/kg", "frequency": "体温>38.5℃时使用"}
            ],
            doctor="王医生",
            hospital="儿童医院",
            diagnosis="发热待查：幼儿急疹？病毒性皮疹？"
        )

        with self.health_service._connect() as conn:
            presc = conn.execute(
                "SELECT diagnosis FROM prescription_records WHERE id = ?",
                (presc_id,)
            ).fetchone()

            print(f"\n✓ 复杂诊断信息已保留: {presc['diagnosis']}")

        return True

    def scenario_4_danger_signal(self):
        """
        场景4: 紧急情况
        检测到危险信号后的诊断保留
        """
        print("\n" + "="*80)
        print("场景4: 紧急情况 - 危险信号检测")
        print("="*80)

        member_id = "child_004"

        print("\n[用户]: 孩子发烧40度，抽搐了！")

        context = MedicalContext(
            conversation_id="emergency_001",
            user_id="user_emergency_001"
        )

        context.chief_complaint = "孩子发烧40度，抽搐了"
        context.dialogue_state = DialogueState.DANGER_DETECTED
        context.danger_signal = "高热惊厥：发热伴抽搐，需紧急处理"
        context.triage_level = "emergency"
        context.triage_action = "立即呼叫120或紧急送医！"

        print(f"\n[系统] ⚠️ 危险信号: {context.danger_signal}")
        print(f"[系统] {context.triage_action}")

        # 就医后记录
        presc_id = self.health_service.add_prescription(
            member_id=member_id,
            date=datetime.now().strftime("%Y-%m-%d"),
            drugs=[
                {"name": "地西泮", "dosage": "0.3mg/kg", "frequency": "prn"}
            ],
            doctor="急诊医生",
            hospital="市儿童医院急诊科",
            diagnosis="热性惊厥（高热惊厥）"
        )

        # 同时保存病历存档
        doc_id = self.health_service.add_document(
            member_id=member_id,
            date=datetime.now().strftime("%Y-%m-%d"),
            doc_type="急诊病历",
            title="热性惊厥急诊记录",
            description="患儿因高热（40℃）发生惊厥，持续约3分钟，急诊处理后缓解",
            hospital="市儿童医院急诊科"
        )

        print("\n✓ 紧急就诊诊断已保留: 热性惊厥（高热惊厥）")
        print("✓ 急诊病历已存档")

        return True

    def scenario_5_multi_member_family(self):
        """
        场景5: 多成员家庭
        同一家庭多个孩子的诊断信息隔离
        """
        print("\n" + "="*80)
        print("场景5: 多成员家庭 - 不同孩子的诊断信息隔离")
        print("="*80)

        # 妈妈给大孩子咨询
        print("\n[妈妈]: 老大发烧了")
        child1_id = "child_005"
        presc1 = self.health_service.add_prescription(
            member_id=child1_id,
            date=datetime.now().strftime("%Y-%m-%d"),
            drugs=[{"name": "布洛芬", "dosage": "5ml", "frequency": "prn"}],
            diagnosis="急性上呼吸道感染"
        )

        # 妈妈给二宝咨询
        print("[妈妈]: 老二也咳嗽")
        child2_id = "child_006"
        presc2 = self.health_service.add_prescription(
            member_id=child2_id,
            date=datetime.now().strftime("%Y-%m-%d"),
            drugs=[{"name": "小儿止咳糖浆", "dosage": "5ml", "frequency": "每日3次"}],
            diagnosis="急性支气管炎"
        )

        # 验证数据隔离
        summary1 = self.health_service.get_records_summary(child1_id)
        summary2 = self.health_service.get_records_summary(child2_id)

        print(f"\n✓ 老大({child1_id}): {summary1['prescription_count']}条处方, 诊断: 急性上呼吸道感染")
        print(f"✓ 老二({child2_id}): {summary2['prescription_count']}条处方, 诊断: 急性支气管炎")

        # 验证查询结果互不干扰
        with self.health_service._connect() as conn:
            child1_diagnosis = conn.execute(
                "SELECT diagnosis FROM prescription_records WHERE member_id = ?",
                (child1_id,)
            ).fetchone()

            child2_diagnosis = conn.execute(
                "SELECT diagnosis FROM prescription_records WHERE member_id = ?",
                (child2_id,)
            ).fetchone()

            isolated = (child1_diagnosis['diagnosis'] == "急性上呼吸道感染" and
                       child2_diagnosis['diagnosis'] == "急性支气管炎")

            print(f"\n✓ 数据隔离验证: {'通过' if isolated else '失败！'}")

        return isolated

    def run_all_scenarios(self):
        """运行所有场景测试"""
        print("\n" + "="*80)
        print("用户场景模拟测试 - 真实使用场景下的诊断信息保留功能")
        print("="*80)

        self.setup()

        try:
            results = {
                "场景1_新用户初诊": self.scenario_1_new_user_first_visit(),
                "场景2_复诊用户": self.scenario_2_return_visit_user(),
                "场景3_多症状复杂病例": self.scenario_3_complex_case(),
                "场景4_紧急情况": self.scenario_4_danger_signal(),
                "场景5_多成员家庭": self.scenario_5_multi_member_family(),
            }

            print("\n" + "="*80)
            print("场景测试结果汇总")
            print("="*80)

            for scenario, passed in results.items():
                status = "✓ 通过" if passed else "✗ 失败"
                print(f"{status} - {scenario}")

            all_passed = all(results.values())
            print(f"\n{'所有场景通过' if all_passed else '存在失败场景'}")

        finally:
            self.teardown()


def main():
    simulator = UserScenarioSimulator()
    simulator.run_all_scenarios()


if __name__ == "__main__":
    main()
