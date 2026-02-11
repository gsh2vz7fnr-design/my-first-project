"""
医疗上下文数据模型 - 动态病例单

MedicalContext 是一个结构化的对话状态对象，用于：
1. 跟踪多轮对话中的实体累积
2. 管理对话状态转换
3. 记录分诊结果和主诉
4. 持久化病例数据
"""
from datetime import datetime
from typing import Dict, Any, List, Optional
from enum import Enum
from pydantic import BaseModel, Field
import json


class DialogueState(str, Enum):
    """对话状态枚举"""
    INITIAL = "initial"
    COLLECTING_SLOTS = "collecting_slots"
    READY_FOR_TRIAGE = "ready_for_triage"
    TRIAGE_COMPLETE = "triage_complete"
    DANGER_DETECTED = "danger_detected"
    RAG_QUERY = "rag_query"
    GREETING = "greeting"


class IntentType(str, Enum):
    """意图类型枚举"""
    GREETING = "greeting"
    TRIAGE = "triage"
    SLOT_FILLING = "slot_filling"
    CONSULT = "consult"
    MEDICATION = "medication"
    CARE = "care"


class MedicalContext(BaseModel):
    """
    医疗上下文模型

    代表一个对话的所有累积信息，包括：
    - 对话状态
    - 当前意图
    - 累积的实体槽位
    - 分诊结果
    - 主诉和症状
    """
    conversation_id: str = Field(..., description="对话ID")
    user_id: str = Field(..., description="用户ID")
    dialogue_state: DialogueState = Field(
        default=DialogueState.INITIAL,
        description="对话状态"
    )
    current_intent: Optional[IntentType] = Field(
        default=None,
        description="当前意图"
    )
    chief_complaint: Optional[str] = Field(
        default=None,
        description="主诉（首次分诊消息）"
    )
    symptom: Optional[str] = Field(
        default=None,
        description="主要症状"
    )
    slots: Dict[str, Any] = Field(
        default_factory=dict,
        description="累积的实体槽位"
    )
    triage_level: Optional[str] = Field(
        default=None,
        description="分诊级别: emergency/observe/online"
    )
    triage_reason: Optional[str] = Field(
        default=None,
        description="分诊原因"
    )
    triage_action: Optional[str] = Field(
        default=None,
        description="分诊建议行动"
    )
    danger_signal: Optional[str] = Field(
        default=None,
        description="检测到的危险信号"
    )
    turn_count: int = Field(
        default=0,
        description="对话轮次计数"
    )
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="创建时间"
    )
    updated_at: datetime = Field(
        default_factory=datetime.now,
        description="更新时间"
    )

    def merge_entities(self, new_entities: Dict[str, Any]) -> None:
        """
        合并新实体到已有槽位

        规则：
        1. 新值覆盖旧值（last-write-wins）
        2. None 和空字符串不覆盖已有值
        3. 列表类型会合并而不是覆盖

        Args:
            new_entities: 新提取的实体字典
        """
        for key, value in new_entities.items():
            if value is None or value == "":
                continue

            if key in self.slots:
                existing = self.slots[key]
                # 如果是列表类型，进行合并
                if isinstance(existing, list) and isinstance(value, list):
                    self.slots[key] = existing + value
                elif isinstance(existing, str) and isinstance(value, str):
                    # 对于字符串，如果是伴随症状，可以追加
                    if key == "accompanying_symptoms" and value not in existing:
                        self.slots[key] = f"{existing}，{value}"
                    else:
                        self.slots[key] = value
                else:
                    self.slots[key] = value
            else:
                self.slots[key] = value

        # 更新时间戳
        self.updated_at = datetime.now()

    def get_missing_slots(
        self,
        required_slots: List[str],
        profile_context: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """
        获取缺失的必需槽位

        支持从用户档案自动填充一些槽位（如月龄）

        Args:
            required_slots: 必需槽位列表
            profile_context: 用户档案上下文

        Returns:
            List[str]: 缺失的槽位列表
        """
        missing = []

        # 创建临时副本用于检查（不影响原始 slots）
        check_slots = self.slots.copy()

        # 尝试从档案自动填充
        if profile_context and profile_context.get("baby_info"):
            baby_info = profile_context["baby_info"]

            if "age_months" in required_slots and "age_months" not in check_slots:
                if baby_info.get("age_months"):
                    check_slots["age_months"] = baby_info["age_months"]

            if "weight_kg" in required_slots and "weight_kg" not in check_slots:
                if baby_info.get("weight_kg"):
                    check_slots["weight_kg"] = baby_info["weight_kg"]

        # 检查缺失的槽位
        for slot in required_slots:
            if slot not in check_slots or check_slots[slot] is None or check_slots[slot] == "":
                missing.append(slot)

        return missing

    def to_db_json(self) -> str:
        """
        转换为数据库存储的 JSON 字符串

        Returns:
            str: JSON 序列化的上下文
        """
        data = self.model_dump(mode="json")
        # datetime 转换为 ISO 格式字符串
        data["created_at"] = self.created_at.isoformat()
        data["updated_at"] = self.updated_at.isoformat()
        # 枚举转换为字符串值
        data["dialogue_state"] = self.dialogue_state.value
        if self.current_intent:
            data["current_intent"] = self.current_intent.value
        return json.dumps(data, ensure_ascii=False)

    @classmethod
    def from_db_json(cls, json_str: str) -> "MedicalContext":
        """
        从数据库 JSON 字符串恢复 MedicalContext

        Args:
            json_str: JSON 序列化的上下文

        Returns:
            MedicalContext: 恢复的上下文对象
        """
        data = json.loads(json_str)
        # 字符串枚举值转换回枚举
        if isinstance(data.get("dialogue_state"), str):
            data["dialogue_state"] = DialogueState(data["dialogue_state"])
        if isinstance(data.get("current_intent"), str):
            data["current_intent"] = IntentType(data["current_intent"])
        # ISO 格式字符串转换回 datetime
        if isinstance(data.get("created_at"), str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if isinstance(data.get("updated_at"), str):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        return cls(**data)

    def increment_turn(self) -> None:
        """增加对话轮次计数"""
        self.turn_count += 1
        self.updated_at = datetime.now()

    def has_symptom(self) -> bool:
        """检查是否已有症状"""
        return bool(self.symptom or self.slots.get("symptom"))

    def get_symptom(self) -> Optional[str]:
        """获取当前症状（优先使用 symptom 字段，否则从 slots 获取）"""
        return self.symptom or self.slots.get("symptom")

    def get_entities_dict(self) -> Dict[str, Any]:
        """
        获取所有实体作为字典（用于兼容旧代码）

        Returns:
            Dict[str, Any]: 合并 symptom 和 slots 的实体字典
        """
        result = self.slots.copy()
        if self.symptom and "symptom" not in result:
            result["symptom"] = self.symptom
        return result
