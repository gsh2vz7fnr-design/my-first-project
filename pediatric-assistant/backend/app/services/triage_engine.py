"""
分诊状态机 - 基于硬编码规则的分诊引擎
"""
import json
from typing import Dict, Any, Optional, List
from loguru import logger

from app.config import settings
from app.models.user import TriageDecision


class TriageEngine:
    """分诊引擎"""

    def __init__(self):
        """初始化"""
        self.danger_signals = self._load_danger_signals()
        self.slot_definitions = self._load_slot_definitions()

    def _load_danger_signals(self) -> Dict[str, Any]:
        """加载危险信号配置"""
        try:
            with open(settings.DANGER_SIGNALS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning("危险信号配置文件不存在，使用默认配置")
            return self._get_default_danger_signals()

    def _load_slot_definitions(self) -> Dict[str, Any]:
        """加载槽位定义"""
        try:
            with open(settings.SLOT_DEFINITIONS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning("槽位定义文件不存在，使用默认配置")
            return self._get_default_slot_definitions()

    def check_danger_signals(self, entities: Dict[str, Any]) -> Optional[str]:
        """
        检查危险信号

        Args:
            entities: 提取的实体

        Returns:
            Optional[str]: 如果检测到危险信号，返回告警文案；否则返回None
        """
        symptom = entities.get("symptom", "").lower()

        # 检查通用危险信号
        for signal in self.danger_signals.get("universal", []):
            keywords = signal.get("keywords", [])
            for keyword in keywords:
                if keyword in entities.get("mental_state", "").lower() or \
                   keyword in entities.get("accompanying_symptoms", "").lower() or \
                   keyword in str(entities.values()).lower():
                    return signal.get("alert_message")

        # 检查症状特定的危险信号
        if symptom in self.danger_signals.get("symptom_specific", {}):
            symptom_signals = self.danger_signals["symptom_specific"][symptom]

            for signal in symptom_signals:
                conditions = signal.get("conditions", {})
                matched = True

                for key, value in conditions.items():
                    entity_value = entities.get(key)
                    if not self._check_condition(entity_value, value):
                        matched = False
                        break

                if matched:
                    return signal.get("alert_message")

        return None

    def _check_condition(self, entity_value: Any, condition: Any) -> bool:
        """检查条件是否满足"""
        if entity_value is None:
            return False

        if isinstance(condition, dict):
            # 范围条件
            if "lt" in condition:
                return float(entity_value) < condition["lt"]
            if "gt" in condition:
                return float(entity_value) > condition["gt"]
            if "contains" in condition:
                return condition["contains"] in str(entity_value).lower()
        else:
            # 精确匹配
            return str(entity_value).lower() == str(condition).lower()

        return False

    def get_missing_slots(self, symptom: str, entities: Dict[str, Any]) -> List[str]:
        """
        获取缺失的槽位

        Args:
            symptom: 症状
            entities: 已提取的实体

        Returns:
            List[str]: 缺失的槽位列表
        """
        if symptom not in self.slot_definitions:
            return []

        required_slots = self.slot_definitions[symptom].get("required", [])
        missing = []

        for slot in required_slots:
            if slot not in entities or entities[slot] is None:
                missing.append(slot)

        return missing

    def generate_follow_up_question(self, missing_slots: List[str]) -> str:
        """
        生成追问问题

        Args:
            missing_slots: 缺失的槽位

        Returns:
            str: 追问问题
        """
        if not missing_slots:
            return ""

        # 获取第一个缺失槽位的问题模板
        slot = missing_slots[0]
        questions = {
            "age_months": "请问宝宝现在多大了？（月龄）",
            "temperature": "请问宝宝现在的体温是多少度？",
            "duration": "这个症状持续多久了？",
            "mental_state": "宝宝的精神状态怎么样？是玩耍正常还是比较蔫？",
            "accompanying_symptoms": "除了这个症状，还有其他不舒服的地方吗？比如咳嗽、呕吐等？",
        }

        return questions.get(slot, f"请补充：{slot}")

    def make_triage_decision(
        self,
        symptom: str,
        entities: Dict[str, Any]
    ) -> TriageDecision:
        """
        做出分诊决策

        Args:
            symptom: 症状
            entities: 实体

        Returns:
            TriageDecision: 分诊决策
        """
        # 1. 首先检查危险信号
        danger_alert = self.check_danger_signals(entities)
        if danger_alert:
            return TriageDecision(
                level="emergency",
                reason="检测到危险信号",
                action=danger_alert,
                danger_signal=danger_alert
            )

        # 2. 基于症状和实体做决策
        if symptom == "发烧":
            return self._triage_fever(entities)
        elif symptom == "摔倒":
            return self._triage_fall(entities)
        elif symptom == "呕吐":
            return self._triage_vomit(entities)
        elif symptom == "腹泻":
            return self._triage_diarrhea(entities)
        else:
            # 默认建议
            return TriageDecision(
                level="observe",
                reason="症状不明确",
                action="建议先在家观察，如症状加重请及时就医"
            )

    def _triage_fever(self, entities: Dict[str, Any]) -> TriageDecision:
        """发烧分诊"""
        age_months = entities.get("age_months")
        temperature = entities.get("temperature")
        duration = entities.get("duration")
        mental_state = entities.get("mental_state", "")

        # 3个月以下发烧 -> 立即就医
        if age_months and age_months < 3:
            return TriageDecision(
                level="emergency",
                reason="3个月以下婴儿发烧属于高危情况",
                action="⚠️ 请立即前往医院就诊！3个月以下婴儿发烧可能提示严重感染，需要医生评估。"
            )

        # 高热 + 精神萎靡 -> 立即就医
        if temperature and "39" in str(temperature) and "萎靡" in mental_state:
            return TriageDecision(
                level="emergency",
                reason="高热且精神状态不佳",
                action="⚠️ 建议尽快就医！宝宝高热且精神萎靡，需要医生评估是否有严重感染。"
            )

        # 持续高热超过48小时 -> 就医
        if duration and ("2天" in duration or "48小时" in duration or "3天" in duration):
            return TriageDecision(
                level="emergency",
                reason="持续高热超过48小时",
                action="建议前往医院就诊。持续高热可能需要进一步检查。"
            )

        # 一般发烧 -> 居家观察
        return TriageDecision(
            level="observe",
            reason="一般发烧，精神状态尚可",
            action="可以先在家观察，注意物理降温和补液。如果出现以下情况请立即就医：\n"
                   "1. 体温超过39.5℃且持续不退\n"
                   "2. 精神萎靡、嗜睡、难以唤醒\n"
                   "3. 出现抽搐、惊厥\n"
                   "4. 持续高热超过48小时"
        )

    def _triage_fall(self, entities: Dict[str, Any]) -> TriageDecision:
        """摔倒分诊"""
        accompanying_symptoms = entities.get("accompanying_symptoms", "").lower()

        # 有昏迷或呕吐 -> 立即就医
        if "昏迷" in accompanying_symptoms or "呕吐" in accompanying_symptoms:
            return TriageDecision(
                level="emergency",
                reason="摔倒后出现昏迷或呕吐",
                action="⚠️ 请立即前往医院急诊！摔倒后出现昏迷或呕吐可能提示颅脑损伤，需要紧急处理。"
            )

        # 一般摔倒 -> 观察
        return TriageDecision(
            level="observe",
            reason="一般摔倒，无明显危险信号",
            action="可以先在家观察24-48小时。注意观察以下情况，如出现请立即就医：\n"
                   "1. 出现呕吐\n"
                   "2. 精神状态异常、嗜睡\n"
                   "3. 头部肿胀明显或有凹陷\n"
                   "4. 哭闹不止、安抚无效"
        )

    def _triage_vomit(self, entities: Dict[str, Any]) -> TriageDecision:
        """呕吐分诊"""
        # 简化版，实际需要更复杂的规则
        return TriageDecision(
            level="observe",
            reason="呕吐症状",
            action="注意观察呕吐频率和精神状态。如果出现以下情况请就医：\n"
                   "1. 频繁呕吐（每小时多次）\n"
                   "2. 呕吐物带血\n"
                   "3. 精神萎靡、脱水征象\n"
                   "4. 伴随高热"
        )

    def _triage_diarrhea(self, entities: Dict[str, Any]) -> TriageDecision:
        """腹泻分诊"""
        return TriageDecision(
            level="observe",
            reason="腹泻症状",
            action="注意补液，预防脱水。如果出现以下情况请就医：\n"
                   "1. 大便带血或黏液\n"
                   "2. 频繁腹泻（每小时多次）\n"
                   "3. 出现脱水征象（尿少、哭时无泪、皮肤干燥）\n"
                   "4. 伴随高热或精神萎靡"
        )

    def _get_default_danger_signals(self) -> Dict[str, Any]:
        """获取默认危险信号配置"""
        return {
            "universal": [
                {
                    "keywords": ["惊厥", "抽搐", "抽风"],
                    "alert_message": "⚠️ 紧急情况！宝宝出现惊厥/抽搐，请立即拨打120或前往最近的医院急诊！"
                },
                {
                    "keywords": ["呼吸困难", "口唇发紫", "喘不过气"],
                    "alert_message": "⚠️ 紧急情况！宝宝呼吸困难，请立即拨打120或前往最近的医院急诊！"
                },
                {
                    "keywords": ["昏迷", "昏睡", "难以唤醒"],
                    "alert_message": "⚠️ 紧急情况！宝宝意识不清，请立即拨打120或前往最近的医院急诊！"
                }
            ],
            "symptom_specific": {
                "发烧": [
                    {
                        "conditions": {"age_months": {"lt": 3}},
                        "alert_message": "⚠️ 请立即前往医院！3个月以下婴儿发烧属于高危情况，需要医生评估。"
                    }
                ]
            }
        }

    def _get_default_slot_definitions(self) -> Dict[str, Any]:
        """获取默认槽位定义"""
        return {
            "发烧": {
                "required": ["age_months", "temperature", "duration", "mental_state"],
                "optional": ["accompanying_symptoms"]
            },
            "摔倒": {
                "required": ["age_months", "mental_state"],
                "optional": ["accompanying_symptoms"]
            },
            "呕吐": {
                "required": ["age_months", "duration", "mental_state"],
                "optional": ["accompanying_symptoms"]
            },
            "腹泻": {
                "required": ["age_months", "duration"],
                "optional": ["accompanying_symptoms"]
            }
        }


# 创建全局实例
triage_engine = TriageEngine()
