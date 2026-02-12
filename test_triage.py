#!/usr/bin/env python3
"""测试分诊逻辑"""

import sys
sys.path.insert(0, '/Users/zhang/Desktop/Claude/pediatric-assistant/backend')

from app.services.triage_engine import TriageEngine

triage_engine = TriageEngine()

# 测试用例
test_cases = [
    {"symptom": "流鼻涕", "entities": {"age_months": 8}},
    {"symptom": "哭闹", "entities": {"age_months": 8, "duration": "1天"}},
    {"symptom": "发烧", "entities": {"age_months": 8, "temperature": "38.5度"}},
    {"symptom": "流鼻涕", "entities": {"age_months": 8, "duration": "2天", "accompanying_symptoms": "咳嗽"}},
    {"symptom": "咳嗽", "entities": {"age_months": 12, "duration": "3天", "cough_type": "有痰咳"}},
    {"symptom": "未知症状", "entities": {"age_months": 6}},
]

print("测试分诊逻辑：")
print("=" * 70)

for i, test_case in enumerate(test_cases):
    print(f"测试 {i+1}:")
    print(f"  症状: {test_case['symptom']}")
    print(f"  实体: {test_case['entities']}")

    try:
        decision = triage_engine.make_triage_decision(test_case['symptom'], test_case['entities'])
        print(f"  分诊级别: {decision.level}")
        print(f"  理由: {decision.reason}")
        print(f"  建议: {decision.action[:100]}...")
    except Exception as e:
        print(f"  错误: {e}")

    print("-" * 70)