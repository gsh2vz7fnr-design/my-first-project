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


class TriageSnapshot(BaseModel):
    """分诊结果快照，分诊完成时一次性写入"""
    level: str = Field(..., description="分诊级别: emergency/urgent/observe/online/self_care")
    reason: str = Field(..., description="分诊原因")
    action: str = Field(..., description="分诊建议行动")
    decided_at: datetime = Field(default_factory=datetime.now, description="决定时间")


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
    triage_snapshot: Optional[TriageSnapshot] = Field(
        default=None,
        description="分诊结果快照，分诊完成时一次性写入"
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

    @property
    def triage_level(self) -> Optional[str]:
        """向后兼容：从 triage_snapshot 读取 level"""
        return self.triage_snapshot.level if self.triage_snapshot else None

    @triage_level.setter
    def triage_level(self, value: Optional[str]):
        """向后兼容：设置 triage_level 时自动创建/更新 snapshot"""
        if value is None:
            return
        if self.triage_snapshot is None:
            self.triage_snapshot = TriageSnapshot(level=value, reason="", action="")
        else:
            self.triage_snapshot.level = value

    @property
    def triage_reason(self) -> Optional[str]:
        """向后兼容：从 triage_snapshot 读取 reason"""
        return self.triage_snapshot.reason if self.triage_snapshot else None

    @triage_reason.setter
    def triage_reason(self, value: Optional[str]):
        """向后兼容：设置 triage_reason 时更新 snapshot"""
        if value is None:
            return
        if self.triage_snapshot is None:
            self.triage_snapshot = TriageSnapshot(level="", reason=value, action="")
        else:
            self.triage_snapshot.reason = value

    @property
    def triage_action(self) -> Optional[str]:
        """向后兼容：从 triage_snapshot 读取 action"""
        return self.triage_snapshot.action if self.triage_snapshot else None

    @triage_action.setter
    def triage_action(self, value: Optional[str]):
        """向后兼容：设置 triage_action 时更新 snapshot"""
        if value is None:
            return
        if self.triage_snapshot is None:
            self.triage_snapshot = TriageSnapshot(level="", reason="", action=value)
        else:
            self.triage_snapshot.action = value

    def merge_entities(self, new_entities: Dict[str, Any]) -> None:
        """
        合并新实体到已有槽位 (增量更新)

        规则：
        1. 新值覆盖旧值（last-write-wins），除非新值为 None/空
        2. 列表类型（如 symptoms）进行合并去重
        3. 字符串类型若为 'unknown' 或 '未提及' 则忽略
        """
        for key, value in new_entities.items():
            # 忽略空值
            if value in [None, "", [], {}]:
                continue
            
            # 忽略无效占位符
            if isinstance(value, str) and value.lower() in ["unknown", "n/a", "未提及", "不清楚"]:
                continue

            # 处理列表合并 (symptoms, accompanying_symptoms)
            if key in ["symptoms", "accompanying_symptoms", "symptom_list"]:
                current = self.slots.get(key, [])
                if not isinstance(current, list):
                    current = [current] if current else []
                
                new_vals = value if isinstance(value, list) else [value]
                # 合并并去重
                merged = list(set(current + new_vals))
                self.slots[key] = merged
            
            # 特殊处理：如果提取到了 age 但 slots 里是 age_months，尝试转换或保留
            # 这里简单处理：直接更新
            else:
                self.slots[key] = value

        # 同步更新主症状字段 (如果有)
        if "symptom" in new_entities and new_entities["symptom"]:
             self.symptom = new_entities["symptom"]
        elif "symptoms" in self.slots and isinstance(self.slots["symptoms"], list) and len(self.slots["symptoms"]) > 0:
             # 如果没有主症状但有症状列表，取第一个作为主症状
             if not self.symptom:
                 self.symptom = self.slots["symptoms"][0]

        # 更新时间戳
        self.updated_at = datetime.now()

    def has_required_slots(self, required_slots: List[str]) -> bool:
        """
        检查是否已收集所有必需槽位
        """
        for slot in required_slots:
            if slot not in self.slots or self.slots[slot] in [None, ""]:
                return False
        return True

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
        # triage_snapshot 中的 datetime 转换
        if self.triage_snapshot:
            data["triage_snapshot"]["decided_at"] = self.triage_snapshot.decided_at.isoformat()
        return json.dumps(data, ensure_ascii=False)

    @classmethod
    def from_db_json(cls, json_str: str) -> "MedicalContext":
        """
        从数据库 JSON 字符串恢复 MedicalContext

        兼容旧格式：如果数据中有 triage_level/triage_reason/triage_action
        但没有 triage_snapshot，则自动迁移为 snapshot 格式。

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
        # triage_snapshot 中的 datetime 恢复
        if data.get("triage_snapshot") and isinstance(data["triage_snapshot"].get("decided_at"), str):
            data["triage_snapshot"]["decided_at"] = datetime.fromisoformat(data["triage_snapshot"]["decided_at"])
        # 兼容旧数据：从分散的字段迁移到 triage_snapshot
        if data.get("triage_snapshot") is None:
            old_level = data.pop("triage_level", None)
            old_reason = data.pop("triage_reason", None)
            old_action = data.pop("triage_action", None)
            if old_level:
                data["triage_snapshot"] = {
                    "level": old_level,
                    "reason": old_reason or "",
                    "action": old_action or "",
                    "decided_at": data.get("updated_at", datetime.now()),
                }
        else:
            # 移除旧字段（如果存在）
            data.pop("triage_level", None)
            data.pop("triage_reason", None)
            data.pop("triage_action", None)
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
