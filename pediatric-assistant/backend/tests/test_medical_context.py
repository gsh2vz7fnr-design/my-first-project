"""
MedicalContext 单元测试

测试 MedicalContext 数据模型的功能：
- merge_entities() 实体合并
- get_missing_slots() 缺失槽位计算
- JSON 序列化/反序列化
- 辅助方法
"""
import pytest
from datetime import datetime
from app.models.medical_context import (
    MedicalContext,
    DialogueState,
    IntentType
)


def test_create_medical_context():
    """测试创建 MedicalContext"""
    ctx = MedicalContext(
        conversation_id="conv_001",
        user_id="user_001"
    )

    assert ctx.conversation_id == "conv_001"
    assert ctx.user_id == "user_001"
    assert ctx.dialogue_state == DialogueState.INITIAL
    assert ctx.current_intent is None
    assert ctx.symptom is None
    assert ctx.slots == {}
    assert ctx.turn_count == 0
    assert isinstance(ctx.created_at, datetime)
    assert isinstance(ctx.updated_at, datetime)


def test_merge_entities_basic():
    """测试基本实体合并"""
    ctx = MedicalContext(
        conversation_id="conv_001",
        user_id="user_001"
    )

    entities = {
        "symptom": "发烧",
        "age_months": 8,
        "temperature": "38.5度"
    }

    ctx.merge_entities(entities)

    assert ctx.slots["symptom"] == "发烧"
    assert ctx.slots["age_months"] == 8
    assert ctx.slots["temperature"] == "38.5度"


def test_merge_entities_override():
    """测试实体覆盖（last-write-wins）"""
    ctx = MedicalContext(
        conversation_id="conv_001",
        user_id="user_001"
    )
    ctx.slots = {"temperature": "38度"}

    # 新值覆盖旧值
    ctx.merge_entities({"temperature": "38.5度"})
    assert ctx.slots["temperature"] == "38.5度"


def test_merge_entities_empty_filter():
    """测试空值不覆盖已有值"""
    ctx = MedicalContext(
        conversation_id="conv_001",
        user_id="user_001"
    )
    ctx.slots = {"symptom": "发烧", "age_months": 8}

    # 空字符串不覆盖
    ctx.merge_entities({"symptom": "", "duration": "1天"})

    assert ctx.slots["symptom"] == "发烧"  # 保持原值
    assert ctx.slots["age_months"] == 8
    assert ctx.slots["duration"] == "1天"  # 新值被添加


def test_merge_entities_none_filter():
    """测试 None 值不覆盖已有值"""
    ctx = MedicalContext(
        conversation_id="conv_001",
        user_id="user_001"
    )
    ctx.slots = {"symptom": "发烧"}

    # None 不覆盖
    ctx.merge_entities({"symptom": None, "duration": "1天"})

    assert ctx.slots["symptom"] == "发烧"
    assert ctx.slots["duration"] == "1天"


def test_merge_entities_accompanying_symptoms():
    """测试伴随症状的合并（字符串追加）"""
    ctx = MedicalContext(
        conversation_id="conv_001",
        user_id="user_001"
    )
    ctx.slots = {"accompanying_symptoms": "咳嗽"}

    ctx.merge_entities({"accompanying_symptoms": "流鼻涕"})

    # 应该追加而不是覆盖
    assert "咳嗽" in ctx.slots["accompanying_symptoms"]
    assert "流鼻涕" in ctx.slots["accompanying_symptoms"]


def test_get_missing_slots_basic():
    """测试基本缺失槽位计算"""
    ctx = MedicalContext(
        conversation_id="conv_001",
        user_id="user_001"
    )
    ctx.slots = {"symptom": "发烧", "age_months": 8}

    required = ["symptom", "age_months", "temperature", "duration"]
    missing = ctx.get_missing_slots(required)

    assert "symptom" not in missing
    assert "age_months" not in missing
    assert "temperature" in missing
    assert "duration" in missing


def test_get_missing_slots_with_profile():
    """测试从档案自动填充槽位"""
    ctx = MedicalContext(
        conversation_id="conv_001",
        user_id="user_001"
    )
    ctx.slots = {"symptom": "发烧"}

    profile_context = {
        "baby_info": {"age_months": 8, "weight_kg": 10}
    }

    required = ["symptom", "age_months", "temperature"]
    missing = ctx.get_missing_slots(required, profile_context)

    # age_months 应该从档案填充，不在缺失列表中
    assert "symptom" not in missing
    assert "age_months" not in missing
    assert "temperature" in missing


def test_get_missing_slots_empty_values():
    """测试空字符串和 None 被视为缺失"""
    ctx = MedicalContext(
        conversation_id="conv_001",
        user_id="user_001"
    )
    ctx.slots = {
        "symptom": "发烧",
        "temperature": "",
        "duration": None
    }

    required = ["symptom", "temperature", "duration"]
    missing = ctx.get_missing_slots(required)

    assert "symptom" not in missing
    assert "temperature" in missing
    assert "duration" in missing


def test_json_serialization():
    """测试 JSON 序列化和反序列化"""
    ctx = MedicalContext(
        conversation_id="conv_001",
        user_id="user_001",
        dialogue_state=DialogueState.COLLECTING_SLOTS,
        current_intent=IntentType.TRIAGE,
        symptom="发烧",
        slots={"age_months": 8, "temperature": "38.5度"},
        turn_count=2
    )

    # 序列化
    json_str = ctx.to_db_json()
    assert json_str is not None
    assert "conv_001" in json_str
    assert "发烧" in json_str

    # 反序列化
    restored = MedicalContext.from_db_json(json_str)

    assert restored.conversation_id == ctx.conversation_id
    assert restored.user_id == ctx.user_id
    assert restored.dialogue_state == DialogueState.COLLECTING_SLOTS
    assert restored.current_intent == IntentType.TRIAGE
    assert restored.symptom == "发烧"
    assert restored.slots["age_months"] == 8
    assert restored.slots["temperature"] == "38.5度"
    assert restored.turn_count == 2


def test_increment_turn():
    """测试轮次计数"""
    ctx = MedicalContext(
        conversation_id="conv_001",
        user_id="user_001"
    )

    assert ctx.turn_count == 0

    ctx.increment_turn()
    assert ctx.turn_count == 1

    ctx.increment_turn()
    assert ctx.turn_count == 2


def test_has_symptom():
    """测试 has_symptom 方法"""
    ctx = MedicalContext(
        conversation_id="conv_001",
        user_id="user_001"
    )

    assert not ctx.has_symptom()

    # 通过 symptom 字段设置
    ctx.symptom = "发烧"
    assert ctx.has_symptom()

    # 清除，通过 slots 设置
    ctx.symptom = None
    assert not ctx.has_symptom()

    ctx.slots = {"symptom": "咳嗽"}
    assert ctx.has_symptom()


def test_get_symptom():
    """测试 get_symptom 方法"""
    ctx = MedicalContext(
        conversation_id="conv_001",
        user_id="user_001"
    )

    # 优先使用 symptom 字段
    ctx.symptom = "发烧"
    ctx.slots = {"symptom": "咳嗽"}
    assert ctx.get_symptom() == "发烧"

    # symptom 字段为空时从 slots 获取
    ctx.symptom = None
    assert ctx.get_symptom() == "咳嗽"


def test_get_entities_dict():
    """测试 get_entities_dict 方法"""
    ctx = MedicalContext(
        conversation_id="conv_001",
        user_id="user_001"
    )
    ctx.symptom = "发烧"
    ctx.slots = {"age_months": 8, "temperature": "38.5度"}

    entities = ctx.get_entities_dict()

    assert entities["symptom"] == "发烧"
    assert entities["age_months"] == 8
    assert entities["temperature"] == "38.5度"


def test_get_entities_dict_without_symptom_field():
    """测试当 symptom 字段为空时从 slots 获取"""
    ctx = MedicalContext(
        conversation_id="conv_001",
        user_id="user_001"
    )
    ctx.slots = {"symptom": "咳嗽", "age_months": 8}

    entities = ctx.get_entities_dict()

    assert entities["symptom"] == "咳嗽"
    assert entities["age_months"] == 8


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
