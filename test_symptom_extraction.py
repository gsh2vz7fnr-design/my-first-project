#!/usr/bin/env python3
"""测试症状提取逻辑"""

import sys
sys.path.insert(0, '/Users/zhang/Desktop/Claude/pediatric-assistant/backend')

from app.services.llm_service import LLMService

llm_service = LLMService()

# 测试用例
test_cases = [
    "流鼻涕、哭闹不安",
    "发烧、流鼻涕",
    "哭闹、流鼻涕、发烧",
    "宝宝8个月，发烧38.5度",
    "流鼻涕",
    "哭闹不安",
    "咳嗽、流鼻涕",
]

print("测试症状提取逻辑：")
print("=" * 50)

for test_input in test_cases:
    print(f"输入: {test_input}")
    result = llm_service._extract_intent_and_entities_fallback(test_input)
    print(f"  意图: {result.intent.type}")
    print(f"  主要症状: {result.entities.get('symptom', '无')}")
    print(f"  伴随症状: {result.entities.get('accompanying_symptoms', '无')}")

    # 测试症状优先级
    if result.entities.get('symptom'):
        priority = llm_service._get_symptom_priority(result.entities['symptom'])
        print(f"  症状优先级: {priority}")

    print("-" * 30)