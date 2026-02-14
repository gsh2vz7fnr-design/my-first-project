"""
对话状态机 - 管理对话状态的转换

DialogueStateMachine 负责根据当前上下文、意图和条件
决定下一步的状态和行动。
"""
from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from enum import Enum

from app.models.medical_context import DialogueState, IntentType


class Action(str, Enum):
    """状态机行动枚举"""
    SEND_GREETING = "send_greeting"
    ASK_FOR_SYMPTOM = "ask_for_symptom"
    SEND_DANGER_ALERT = "send_danger_alert"
    ASK_MISSING_SLOTS = "ask_missing_slots"
    MAKE_TRIAGE_DECISION = "make_triage_decision"
    RUN_RAG_QUERY = "run_rag_query"


@dataclass
class TransitionResult:
    """
    状态转移结果

    Attributes:
        new_state: 新的对话状态
        action: 需要执行的行动
        metadata: 额外的元数据（如缺失槽位列表）
    """
    new_state: DialogueState
    action: Action
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class DialogueStateMachine:
    """
    对话状态机

    根据输入的意图、危险信号、缺失槽位等信息，
    决定下一步的状态和行动。

    状态流转规则：
    ```
    IF danger_alert             → DANGER_DETECTED,   SEND_DANGER_ALERT (优先级最高)
    IF intent == GREETING       → GREETING,          SEND_GREETING
    IF no symptom               → COLLECTING_SLOTS,  ASK_FOR_SYMPTOM
    IF missing_slots            → COLLECTING_SLOTS,  ASK_MISSING_SLOTS
    IF intent in [TRIAGE, SLOT_FILLING] → READY_FOR_TRIAGE,  MAKE_TRIAGE_DECISION
    ELSE (other intents)       → RAG_QUERY,         RUN_RAG_QUERY
    ```
    """

    def transition(
        self,
        intent: Optional[IntentType],
        has_symptom: bool,
        danger_alert: Optional[str] = None,
        missing_slots: Optional[List[str]] = None,
        is_first_turn: bool = False
    ) -> TransitionResult:
        """
        根据当前条件计算状态转移

        Args:
            intent: 当前识别的意图
            has_symptom: 是否已有症状信息
            danger_alert: 危险信号（如果有）
            missing_slots: 缺失的槽位列表
            is_first_turn: 是否为首轮对话（用于决定是否优先进行分诊回应）

        Returns:
            TransitionResult: 状态转移结果
        """
        # 规则1: 危险信号 → 立即告警（优先级最高）
        if danger_alert:
            return TransitionResult(
                new_state=DialogueState.DANGER_DETECTED,
                action=Action.SEND_DANGER_ALERT,
                metadata={"danger_alert": danger_alert}
            )

        # 规则2: 问候意图 → 发送问候
        if intent == IntentType.GREETING:
            return TransitionResult(
                new_state=DialogueState.GREETING,
                action=Action.SEND_GREETING
            )

        # 规则3: 没有症状 → 询问症状
        if not has_symptom:
            return TransitionResult(
                new_state=DialogueState.COLLECTING_SLOTS,
                action=Action.ASK_FOR_SYMPTOM
            )

        # 规则4: 有缺失槽位 → 追问
        # 修改：如果是首轮对话，即使有缺失槽位，也允许进入分诊/咨询流程，以便给出共情和初步建议
        if missing_slots and not is_first_turn:
            return TransitionResult(
                new_state=DialogueState.COLLECTING_SLOTS,
                action=Action.ASK_MISSING_SLOTS,
                metadata={"missing_slots": missing_slots}
            )

        # 规则5: 分诊相关意图且信息完整（或首轮对话）→ 做出分诊决策
        if intent in (IntentType.TRIAGE, IntentType.SLOT_FILLING):
            return TransitionResult(
                new_state=DialogueState.READY_FOR_TRIAGE,
                action=Action.MAKE_TRIAGE_DECISION,
                metadata={"missing_slots": missing_slots} if missing_slots else {}
            )

        # 规则6: 其他意图（咨询、用药、护理）→ RAG 查询
        return TransitionResult(
            new_state=DialogueState.RAG_QUERY,
            action=Action.RUN_RAG_QUERY,
            metadata={"missing_slots": missing_slots} if missing_slots else {}
        )

    def get_state_description(self, state: DialogueState) -> str:
        """
        获取状态的描述性文本

        Args:
            state: 对话状态

        Returns:
            str: 状态描述
        """
        descriptions = {
            DialogueState.INITIAL: "初始状态",
            DialogueState.COLLECTING_SLOTS: "收集信息中",
            DialogueState.READY_FOR_TRIAGE: "准备分诊",
            DialogueState.TRIAGE_COMPLETE: "分诊完成",
            DialogueState.DANGER_DETECTED: "检测到危险信号",
            DialogueState.RAG_QUERY: "查询知识库",
            DialogueState.GREETING: "问候"
        }
        return descriptions.get(state, "未知状态")

    def get_action_description(self, action: Action) -> str:
        """
        获取行动的描述性文本

        Args:
            action: 行动类型

        Returns:
            str: 行动描述
        """
        descriptions = {
            Action.SEND_GREETING: "发送问候",
            Action.ASK_FOR_SYMPTOM: "询问症状",
            Action.SEND_DANGER_ALERT: "发送危险告警",
            Action.ASK_MISSING_SLOTS: "追问缺失信息",
            Action.MAKE_TRIAGE_DECISION: "做出分诊决策",
            Action.RUN_RAG_QUERY: "查询知识库"
        }
        return descriptions.get(action, "未知行动")


# 创建全局实例
dialogue_state_machine = DialogueStateMachine()
