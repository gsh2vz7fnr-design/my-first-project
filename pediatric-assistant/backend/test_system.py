"""
系统功能测试脚本
"""
import asyncio
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.llm_service import llm_service
from app.services.triage_engine import triage_engine
from app.services.safety_filter import safety_filter
from app.services.rag_service import rag_service


async def test_intent_extraction():
    """测试意图识别"""
    print("\n" + "="*50)
    print("测试1: 意图识别与实体提取")
    print("="*50)

    test_cases = [
        "宝宝6个月大，发烧39度，精神有点蔫",
        "泰诺林和美林能一起吃吗？",
        "宝宝从床上摔下来了，哭了一会儿就好了",
    ]

    for user_input in test_cases:
        print(f"\n用户输入: {user_input}")
        result = await llm_service.extract_intent_and_entities(user_input)
        print(f"意图: {result.intent.type} (置信度: {result.intent.confidence})")
        print(f"实体: {result.entities}")


def test_danger_signals():
    """测试危险信号检测"""
    print("\n" + "="*50)
    print("测试2: 危险信号检测")
    print("="*50)

    test_cases = [
        {"symptom": "发烧", "age_months": 2, "temperature": "38度"},
        {"symptom": "发烧", "age_months": 12, "temperature": "39度", "mental_state": "精神萎靡"},
        {"symptom": "摔倒", "accompanying_symptoms": "呕吐"},
        {"symptom": "发烧", "age_months": 12, "temperature": "38度", "mental_state": "玩耍正常"},
    ]

    for entities in test_cases:
        print(f"\n实体: {entities}")
        alert = triage_engine.check_danger_signals(entities)
        if alert:
            print(f"⚠️ 危险信号: {alert[:100]}...")
        else:
            print("✓ 无危险信号")


def test_safety_filter():
    """测试安全过滤"""
    print("\n" + "="*50)
    print("测试3: 安全过滤")
    print("="*50)

    test_cases = [
        "建议使用对乙酰氨基酚退烧",
        "可以给宝宝吃尼美舒利",
        "这个病肯定没问题，我保证能治好",
        "建议物理降温，多喝水",
    ]

    for text in test_cases:
        print(f"\n文本: {text}")
        result = safety_filter.filter_output(text)
        if result.is_safe:
            print("✓ 安全")
        else:
            print(f"✗ 不安全 - 类别: {result.category}")
            print(f"  匹配词: {result.matched_keywords}")


async def test_rag_retrieval():
    """测试RAG检索"""
    print("\n" + "="*50)
    print("测试4: RAG知识检索")
    print("="*50)

    test_queries = [
        "宝宝发烧怎么办？",
        "泰诺林的用法用量",
        "摔倒后什么情况需要就医？",
    ]

    for query in test_queries:
        print(f"\n查询: {query}")
        sources = await rag_service.retrieve(query, top_k=2)
        print(f"检索到 {len(sources)} 条结果:")
        for i, source in enumerate(sources, 1):
            print(f"\n  [{i}] {source.metadata.get('title')}")
            print(f"      来源: {source.source}")
            print(f"      相似度: {source.score:.3f}")
            print(f"      内容: {source.content[:100]}...")


async def test_end_to_end():
    """端到端测试"""
    print("\n" + "="*50)
    print("测试5: 端到端对话流程")
    print("="*50)

    test_cases = [
        {
            "input": "宝宝2个月大，发烧38度",
            "expected": "应该触发危险信号（3个月以下发烧）"
        },
        {
            "input": "泰诺林和美林能交替使用吗？",
            "expected": "应该返回RAG检索结果"
        },
        {
            "input": "给我开点头孢",
            "expected": "应该拒绝处方请求"
        }
    ]

    for case in test_cases:
        print(f"\n用户: {case['input']}")
        print(f"预期: {case['expected']}")

        # 1. 检查处方意图
        if safety_filter.check_prescription_intent(case['input']):
            print("结果: 检测到处方意图，已拒绝")
            print(safety_filter.get_prescription_refusal_message()[:100] + "...")
            continue

        # 2. 意图识别
        intent_result = await llm_service.extract_intent_and_entities(case['input'])
        print(f"意图: {intent_result.intent.type}")

        # 3. 分诊流程
        if intent_result.intent.type == "triage":
            danger_alert = triage_engine.check_danger_signals(intent_result.entities)
            if danger_alert:
                print(f"结果: 危险信号告警")
                print(danger_alert[:100] + "...")
                continue

            symptom = intent_result.entities.get("symptom", "")
            missing_slots = triage_engine.get_missing_slots(symptom, intent_result.entities)
            if missing_slots:
                print(f"结果: 需要追问 - {missing_slots}")
                continue

            decision = triage_engine.make_triage_decision(symptom, intent_result.entities)
            print(f"结果: 分诊决策 - {decision.level}")
            print(decision.action[:100] + "...")

        # 4. RAG检索
        else:
            rag_result = await rag_service.generate_answer_with_sources(case['input'])
            print(f"结果: RAG回答 (有来源: {rag_result.has_source})")
            print(rag_result.answer[:200] + "...")


async def main():
    """主函数"""
    print("\n" + "="*50)
    print("智能儿科分诊与护理助手 - 系统测试")
    print("="*50)

    try:
        # 运行所有测试
        await test_intent_extraction()
        test_danger_signals()
        test_safety_filter()
        await test_rag_retrieval()
        await test_end_to_end()

        print("\n" + "="*50)
        print("✓ 所有测试完成")
        print("="*50)

    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
