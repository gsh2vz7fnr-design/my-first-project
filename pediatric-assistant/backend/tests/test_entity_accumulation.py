"""
测试实体累积功能 - 验证首次消息的实体会被保存并在后续轮次使用
"""
import pytest
from app.services.conversation_state_service import ConversationStateService


def test_entity_accumulation():
    """测试实体在多轮对话中的累积"""
    service = ConversationStateService()
    conversation_id = "test_conv_001"

    # 第一轮：用户首次消息
    first_entities = {
        "symptom": "发烧",
        "age_months": 8,
        "temperature": "38.5度",
        "mental_state": "精神不好"
    }
    merged_1 = service.merge_entities(conversation_id, first_entities)

    assert merged_1["symptom"] == "发烧"
    assert merged_1["age_months"] == 8
    assert merged_1["temperature"] == "38.5度"
    assert merged_1["mental_state"] == "精神不好"

    # 第二轮：用户补充持续时间
    second_entities = {
        "duration": "1天"
    }
    merged_2 = service.merge_entities(conversation_id, second_entities)

    # 验证：第一轮的实体仍然存在
    assert merged_2["symptom"] == "发烧"
    assert merged_2["age_months"] == 8
    assert merged_2["temperature"] == "38.5度"
    assert merged_2["mental_state"] == "精神不好"
    # 验证：新实体也被添加
    assert merged_2["duration"] == "1天"

    # 第三轮：用户补充伴随症状
    third_entities = {
        "accompanying_symptoms": "流鼻涕"
    }
    merged_3 = service.merge_entities(conversation_id, third_entities)

    # 验证：所有实体都存在
    assert merged_3["symptom"] == "发烧"
    assert merged_3["age_months"] == 8
    assert merged_3["temperature"] == "38.5度"
    assert merged_3["mental_state"] == "精神不好"
    assert merged_3["duration"] == "1天"
    assert merged_3["accompanying_symptoms"] == "流鼻涕"

    # 清理
    service.clear_entities(conversation_id)
    assert service.get_entities(conversation_id) == {}


def test_entity_update_override():
    """测试实体更新（用户修正信息）"""
    service = ConversationStateService()
    conversation_id = "test_conv_002"

    # 第一轮
    first_entities = {
        "temperature": "38度"
    }
    service.merge_entities(conversation_id, first_entities)

    # 第二轮：用户修正体温
    second_entities = {
        "temperature": "38.5度"
    }
    merged = service.merge_entities(conversation_id, second_entities)

    # 验证：新值覆盖旧值
    assert merged["temperature"] == "38.5度"

    # 清理
    service.clear_entities(conversation_id)


def test_empty_entity_handling():
    """测试空实体不会覆盖已有值"""
    service = ConversationStateService()
    conversation_id = "test_conv_003"

    # 第一轮
    first_entities = {
        "symptom": "发烧",
        "age_months": 8
    }
    service.merge_entities(conversation_id, first_entities)

    # 第二轮：包含空值
    second_entities = {
        "symptom": "",  # 空字符串
        "duration": "1天"
    }
    merged = service.merge_entities(conversation_id, second_entities)

    # 验证：空值不会覆盖已有值
    assert merged["symptom"] == "发烧"
    assert merged["age_months"] == 8
    assert merged["duration"] == "1天"

    # 清理
    service.clear_entities(conversation_id)


def test_bug_scenario():
    """
    测试 Bug 场景：
    1. 用户首次消息："宝宝8个月，发烧38.5度，精神不好"
    2. Bot 询问："持续多久了？"
    3. 用户回答："1天"
    4. Bot 询问："就医前的症状？"
    5. 用户回答："流鼻涕"
    6. Bot 应该不再询问年龄（因为已经在第一轮提供了）
    """
    service = ConversationStateService()
    conversation_id = "test_bug_scenario"

    # Turn 1: 首次消息
    turn1_entities = {
        "symptom": "发烧",
        "age_months": 8,
        "temperature": "38.5度",
        "mental_state": "精神不好"
    }
    merged_1 = service.merge_entities(conversation_id, turn1_entities)
    assert merged_1["age_months"] == 8

    # Turn 2: 补充持续时间
    turn2_entities = {
        "duration": "1天"
    }
    merged_2 = service.merge_entities(conversation_id, turn2_entities)
    assert merged_2["age_months"] == 8  # 年龄仍然存在
    assert merged_2["duration"] == "1天"

    # Turn 3: 补充伴随症状
    turn3_entities = {
        "accompanying_symptoms": "流鼻涕"
    }
    merged_3 = service.merge_entities(conversation_id, turn3_entities)
    assert merged_3["age_months"] == 8  # 年龄仍然存在！

    # 验证：不应该询问年龄，因为已经在 merged_3 中
    # 模拟 get_missing_slots 的逻辑
    required_slots = ["age_months", "temperature", "duration", "mental_state"]
    missing = [slot for slot in required_slots if slot not in merged_3]

    # 年龄不应该在缺失列表中
    assert "age_months" not in missing
    print(f"✅ Bug 已修复：年龄在所有轮次中都被保留，缺失槽位: {missing}")

    # 清理
    service.clear_entities(conversation_id)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
