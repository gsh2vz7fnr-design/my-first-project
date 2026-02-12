#!/usr/bin/env python3
"""测试完整的分诊流程"""

import sys
sys.path.insert(0, '/Users/zhang/Desktop/Claude/pediatric-assistant/backend')

from app.models.medical_context import MedicalContext
from app.services.llm_service import LLMService
from app.services.triage_engine import TriageEngine

llm_service = LLMService()
triage_engine = TriageEngine()

# 模拟多轮对话
print("测试完整分诊流程：")
print("=" * 70)

# 第一轮：用户输入"宝宝8个月，发烧"
user_input_1 = "宝宝8个月，发烧"
print(f"用户输入1: {user_input_1}")
result1 = llm_service._extract_intent_and_entities_fallback(user_input_1)
print(f"  提取结果: 症状={result1.entities.get('symptom')}, 年龄={result1.entities.get('age_months')}, 体温={result1.entities.get('temperature')}")

# 创建医疗上下文
ctx = MedicalContext(conversation_id="test_conv", user_id="test_user")
ctx.merge_entities(result1.entities)
print(f"  上下文槽位: {ctx.slots}")

# 第二轮：用户选择"流鼻涕、哭闹不安"
user_input_2 = "流鼻涕、哭闹不安"
print(f"\n用户输入2: {user_input_2}")
result2 = llm_service._extract_intent_and_entities_fallback(user_input_2)
print(f"  提取结果: 症状={result2.entities.get('symptom')}, 伴随症状={result2.entities.get('accompanying_symptoms')}")

# 合并到上下文
ctx.merge_entities(result2.entities)
print(f"  上下文槽位更新后: {ctx.slots}")

# 获取所有实体进行分诊
entities_dict = ctx.get_entities_dict()
symptom = ctx.get_symptom()
print(f"\n最终状态:")
print(f"  主要症状: {symptom}")
print(f"  所有实体: {entities_dict}")

# 进行分诊决策
decision = triage_engine.make_triage_decision(symptom, entities_dict)
print(f"\n分诊结果:")
print(f"  级别: {decision.level}")
print(f"  理由: {decision.reason}")
print(f"  建议: {decision.action}")