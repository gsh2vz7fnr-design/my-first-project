"""
DialogueStateMachine 单元测试

测试状态机的状态转移逻辑：
- 7 种状态转移路径
- 各种条件组合下的正确转移
- 元数据正确传递
"""
import pytest
from app.services.dialogue_state_machine import (
    DialogueStateMachine,
    Action,
    TransitionResult
)
from app.models.medical_context import DialogueState, IntentType


@pytest.fixture
def state_machine():
    """创建状态机实例"""
    return DialogueStateMachine()


def test_greeting_intent_transition(state_machine):
    """测试路径1: 问候意图 → GREETING, SEND_GREETING"""
    result = state_machine.transition(
        intent=IntentType.GREETING,
        has_symptom=False,
        danger_alert=None,
        missing_slots=None
    )

    assert result.new_state == DialogueState.GREETING
    assert result.action == Action.SEND_GREETING
    assert result.metadata == {}


def test_danger_signal_transition(state_machine):
    """测试路径2: 危险信号 → DANGER_DETECTED, SEND_DANGER_ALERT"""
    result = state_machine.transition(
        intent=IntentType.TRIAGE,
        has_symptom=True,
        danger_alert="检测到惊厥，需要立即就医",
        missing_slots=None
    )

    assert result.new_state == DialogueState.DANGER_DETECTED
    assert result.action == Action.SEND_DANGER_ALERT
    assert result.metadata["danger_alert"] == "检测到惊厥，需要立即就医"


def test_no_symptom_transition(state_machine):
    """测试路径3: 没有症状 → COLLECTING_SLOTS, ASK_FOR_SYMPTOM"""
    result = state_machine.transition(
        intent=IntentType.TRIAGE,
        has_symptom=False,
        danger_alert=None,
        missing_slots=None
    )

    assert result.new_state == DialogueState.COLLECTING_SLOTS
    assert result.action == Action.ASK_FOR_SYMPTOM


def test_missing_slots_transition(state_machine):
    """测试路径4: 有缺失槽位 → COLLECTING_SLOTS, ASK_MISSING_SLOTS"""
    result = state_machine.transition(
        intent=IntentType.TRIAGE,
        has_symptom=True,
        danger_alert=None,
        missing_slots=["age_months", "temperature"]
    )

    assert result.new_state == DialogueState.COLLECTING_SLOTS
    assert result.action == Action.ASK_MISSING_SLOTS
    assert result.metadata["missing_slots"] == ["age_months", "temperature"]


def test_triage_ready_transition(state_machine):
    """测试路径5: 分诊意图且信息完整 → READY_FOR_TRIAGE, MAKE_TRIAGE_DECISION"""
    result = state_machine.transition(
        intent=IntentType.TRIAGE,
        has_symptom=True,
        danger_alert=None,
        missing_slots=None
    )

    assert result.new_state == DialogueState.READY_FOR_TRIAGE
    assert result.action == Action.MAKE_TRIAGE_DECISION


def test_slot_filling_ready_transition(state_machine):
    """测试路径6: slot_filling 意图且信息完整 → READY_FOR_TRIAGE"""
    result = state_machine.transition(
        intent=IntentType.SLOT_FILLING,
        has_symptom=True,
        danger_alert=None,
        missing_slots=None
    )

    assert result.new_state == DialogueState.READY_FOR_TRIAGE
    assert result.action == Action.MAKE_TRIAGE_DECISION


def test_consult_intent_transition(state_machine):
    """测试路径7: 咨询意图 → RAG_QUERY, RUN_RAG_QUERY"""
    result = state_machine.transition(
        intent=IntentType.CONSULT,
        has_symptom=True,
        danger_alert=None,
        missing_slots=None
    )

    assert result.new_state == DialogueState.RAG_QUERY
    assert result.action == Action.RUN_RAG_QUERY


def test_medication_intent_transition(state_machine):
    """测试: 用药意图 → RAG_QUERY"""
    result = state_machine.transition(
        intent=IntentType.MEDICATION,
        has_symptom=True,
        danger_alert=None,
        missing_slots=None
    )

    assert result.new_state == DialogueState.RAG_QUERY
    assert result.action == Action.RUN_RAG_QUERY


def test_care_intent_transition(state_machine):
    """测试: 护理意图 → RAG_QUERY"""
    result = state_machine.transition(
        intent=IntentType.CARE,
        has_symptom=True,
        danger_alert=None,
        missing_slots=None
    )

    assert result.new_state == DialogueState.RAG_QUERY
    assert result.action == Action.RUN_RAG_QUERY


def test_danger_signal_has_highest_priority(state_machine):
    """测试危险信号优先级最高（即使有其他条件）"""
    # 即使是问候意图，如果有危险信号，也应该处理危险
    result = state_machine.transition(
        intent=IntentType.GREETING,
        has_symptom=False,
        danger_alert="检测到呼吸困难",
        missing_slots=None
    )

    assert result.new_state == DialogueState.DANGER_DETECTED
    assert result.action == Action.SEND_DANGER_ALERT


def test_no_symptom_priority_over_missing_slots(state_machine):
    """测试没症状优先于缺失槽位"""
    # 没有症状时，即使指定了缺失槽位，也应该先问症状
    result = state_machine.transition(
        intent=IntentType.TRIAGE,
        has_symptom=False,
        danger_alert=None,
        missing_slots=["age_months"]
    )

    assert result.new_state == DialogueState.COLLECTING_SLOTS
    assert result.action == Action.ASK_FOR_SYMPTOM


def test_empty_missing_slots(state_machine):
    """测试空缺失槽位列表被视为无缺失"""
    result = state_machine.transition(
        intent=IntentType.TRIAGE,
        has_symptom=True,
        danger_alert=None,
        missing_slots=[]
    )

    assert result.new_state == DialogueState.READY_FOR_TRIAGE
    assert result.action == Action.MAKE_TRIAGE_DECISION


def test_none_intent_treated_as_consult(state_machine):
    """测试 None 意图被视为咨询（走 RAG）"""
    result = state_machine.transition(
        intent=None,
        has_symptom=True,
        danger_alert=None,
        missing_slots=None
    )

    assert result.new_state == DialogueState.RAG_QUERY
    assert result.action == Action.RUN_RAG_QUERY


def test_state_description(state_machine):
    """测试状态描述方法"""
    assert "初始" in state_machine.get_state_description(DialogueState.INITIAL)
    assert "收集" in state_machine.get_state_description(DialogueState.COLLECTING_SLOTS)
    assert "分诊" in state_machine.get_state_description(DialogueState.READY_FOR_TRIAGE)
    assert "危险" in state_machine.get_state_description(DialogueState.DANGER_DETECTED)
    assert "查询" in state_machine.get_state_description(DialogueState.RAG_QUERY)


def test_action_description(state_machine):
    """测试行动描述方法"""
    assert "问候" in state_machine.get_action_description(Action.SEND_GREETING)
    assert "症状" in state_machine.get_action_description(Action.ASK_FOR_SYMPTOM)
    assert "危险" in state_machine.get_action_description(Action.SEND_DANGER_ALERT)
    assert "追问" in state_machine.get_action_description(Action.ASK_MISSING_SLOTS)
    assert "决策" in state_machine.get_action_description(Action.MAKE_TRIAGE_DECISION)
    assert "查询" in state_machine.get_action_description(Action.RUN_RAG_QUERY)


def test_transition_result_metadata_default(state_machine):
    """测试 TransitionResult 元数据默认为空字典"""
    result = TransitionResult(
        new_state=DialogueState.INITIAL,
        action=Action.SEND_GREETING
    )

    assert result.metadata == {}


def test_full_triage_flow(state_machine):
    """测试完整的分诊流程"""
    # Turn 1: 用户首次描述症状
    result1 = state_machine.transition(
        intent=IntentType.TRIAGE,
        has_symptom=True,
        danger_alert=None,
        missing_slots=["age_months", "temperature"]
    )
    assert result1.action == Action.ASK_MISSING_SLOTS

    # Turn 2: 用户补充信息，但仍有缺失
    result2 = state_machine.transition(
        intent=IntentType.SLOT_FILLING,
        has_symptom=True,
        danger_alert=None,
        missing_slots=["temperature"]
    )
    assert result2.action == Action.ASK_MISSING_SLOTS

    # Turn 3: 信息完整
    result3 = state_machine.transition(
        intent=IntentType.SLOT_FILLING,
        has_symptom=True,
        danger_alert=None,
        missing_slots=None
    )
    assert result3.action == Action.MAKE_TRIAGE_DECISION


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
