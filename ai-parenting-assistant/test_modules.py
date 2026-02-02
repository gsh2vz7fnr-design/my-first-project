"""
测试脚本 - 验证各个模块功能
无需启动服务器，直接测试核心逻辑
"""
import sys
sys.path.append('./app')

from danger_detector import DangerDetector
from intent_router import IntentRouter
from safety_guard import SafetyGuard

print("=" * 60)
print("AI育儿助手 - 模块测试")
print("=" * 60)

# 测试1: 危险信号检测
print("\n【测试1：危险信号检测】")
print("-" * 60)

detector = DangerDetector()

test_cases_danger = [
    "宝宝发烧39.5度，精神很差，一直在睡觉",
    "宝宝从床上摔下来了，后脑勺着地，现在在呕吐",
    "宝宝有点咳嗽，流鼻涕",
]

for case in test_cases_danger:
    print(f"\n输入: {case}")
    result = detector.detect(case)
    if result:
        print("✅ 检测到危险信号！")
        print(f"类别: {result['category']}")
        print(f"建议: {result['action']}")
    else:
        print("✓ 未检测到危险信号")

# 测试2: 意图识别
print("\n\n【测试2：意图识别】")
print("-" * 60)

router = IntentRouter()

test_cases_intent = [
    "宝宝发烧39度，要不要去医院？",
    "美林和泰诺林能一起吃吗？",
    "宝宝便秘了，吃什么能排便？",
    "宝宝今天很开心"
]

for case in test_cases_intent:
    print(f"\n输入: {case}")
    result = router.route(case)
    print(f"意图: {result['intent'].value}")
    print(f"置信度: {result['confidence']:.2f}")
    print(f"描述: {result['description']}")

# 测试3: 安全护栏
print("\n\n【测试3：安全护栏】")
print("-" * 60)

guard = SafetyGuard()

test_responses = [
    "根据您的描述，宝宝诊断为湿疹。",
    "宝宝发烧可以服用5ml美林。",
    "这种情况可能是便秘，建议增加水分摄入。",
]

for response in test_responses:
    print(f"\n原始回复: {response}")
    result = guard.check_response(response)
    print(f"是否安全: {'✅ 是' if result['is_safe'] else '❌ 否'}")

    if result['issues']:
        print("发现的问题:")
        for issue in result['issues']:
            print(f"  - {issue['message']}")

    sanitized = guard.sanitize_response(response)
    print(f"清理后: {sanitized[:100]}...")

print("\n" + "=" * 60)
print("测试完成！")
print("=" * 60)
print("\n💡 提示：")
print("1. 所有核心模块都可以独立运行")
print("2. 要测试完整流程，需要启动FastAPI服务")
print("3. 要使用LLM功能，需要配置OpenAI API密钥")
