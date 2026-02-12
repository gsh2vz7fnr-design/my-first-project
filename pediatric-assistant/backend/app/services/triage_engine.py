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
        self.rules = self._load_symptom_rules()

    def _load_symptom_rules(self) -> Dict[str, List[Dict[str, Any]]]:
        """加载症状分诊规则"""
        rules = {}
        rules_dir = settings.TRIAGE_RULES_PATH
        if not rules_dir:
             rules_dir = "app/data/triage_rules"
             
        import os
        for filename in os.listdir(rules_dir):
            if filename.endswith("_rules.json"):
                symptom_key = filename.replace("_rules.json", "")
                # 简单的映射：fever -> 发烧
                if symptom_key == "fever": symptom_map = "发烧"
                elif symptom_key == "fall": symptom_map = "摔倒"
                else: symptom_map = symptom_key
                
                try:
                    with open(os.path.join(rules_dir, filename), "r", encoding="utf-8") as f:
                        data = json.load(f)
                        rules[symptom_map] = sorted(data.get("rules", []), key=lambda x: x["priority"])
                except Exception as e:
                    logger.error(f"加载规则失败 {filename}: {e}")
        return rules

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
        symptom = entities.get("symptom", "")
        if isinstance(symptom, list):
            symptom = symptom[0] if symptom else ""
        symptom = str(symptom).lower()

        # 准备检查用的字符串
        mental_state = entities.get("mental_state", "")
        if isinstance(mental_state, list):
            mental_state = " ".join([str(x) for x in mental_state])
        mental_state = str(mental_state).lower()

        acc_symptoms = entities.get("accompanying_symptoms", "")
        if isinstance(acc_symptoms, list):
            acc_symptoms = " ".join([str(x) for x in acc_symptoms])
        acc_symptoms = str(acc_symptoms).lower()

        # 检查通用危险信号
        for signal in self.danger_signals.get("universal", []):
            keywords = signal.get("keywords", [])
            for keyword in keywords:
                if keyword in mental_state or \
                   keyword in acc_symptoms or \
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
        # 处理 None 值
        if entity_value is None:
            # 如果条件是检查不存在，则可能通过，但在分诊逻辑中通常意味着条件不满足
            return False

        if isinstance(condition, dict):
            # 范围条件
            if "lt" in condition:
                value = self._to_number(entity_value)
                return value is not None and value < condition["lt"]
            if "lte" in condition:
                value = self._to_number(entity_value)
                return value is not None and value <= condition["lte"]
            if "gt" in condition:
                value = self._to_number(entity_value)
                return value is not None and value > condition["gt"]
            if "gte" in condition:
                value = self._to_number(entity_value)
                return value is not None and value >= condition["gte"]
            if "contains" in condition:
                return str(condition["contains"]) in str(entity_value)
        else:
            # 精确匹配
            return str(entity_value).lower() == str(condition).lower()

        return False

    def _to_number(self, value: Any) -> Optional[float]:
        """将字符串数值（如'2个月'）转换为float"""
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            import re
            match = re.search(r"\d+(?:\.\d+)?", value)
            if match:
                return float(match.group(0))
            cn_map = {
                "零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
                "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10
            }
            if "十" in value:
                parts = value.split("十")
                left = cn_map.get(parts[0], 1) if parts[0] else 1
                # 取 parts[1] 的第一个中文字符查找映射（如"六个月"取"六"）
                right = 0
                if len(parts) > 1 and parts[1]:
                    for ch in parts[1]:
                        if ch in cn_map:
                            right = cn_map[ch]
                            break
                return float(left * 10 + right)
            for ch, num in cn_map.items():
                if ch in value:
                    return float(num)
        return None

    # ... (get_missing_slots, _should_relax_follow_up, generate_follow_up_question stay same) ...

    def get_slot_options(self, slot: str) -> List[str]:
        """
        获取槽位的建议选项
        
        Args:
            slot: 槽位名称
            
        Returns:
            List[str]: 建议选项列表
        """
        # 这里可以从配置文件加载，目前先硬编码常见槽位的选项
        options_map = {
            "symptom": ["发烧", "咳嗽", "流鼻涕", "呕吐", "腹泻", "皮疹", "哭闹不安"],
            "duration": ["刚刚发现", "半天", "1天", "2天", "3天", "一周以上"],
            "temperature": ["37.5℃", "38.0℃", "38.5℃", "39.0℃", "39.5℃", "40.0℃", "不确定"],
            "mental_state": ["正常玩耍", "精神差/蔫", "嗜睡", "烦躁不安"],
            "appetite": ["正常进食", "食欲减退", "拒食", "呕吐"],
            "food_intake": ["正常进食", "进食减少", "拒食", "呕吐"],
            "urine_output": ["正常", "偏少", "明显减少", "无尿"],
            "accompanying_symptoms": ["无", "咳嗽", "呕吐", "腹泻", "皮疹", "呼吸急促"],
            "cough_type": ["干咳", "有痰咳", "犬吠样咳嗽", "痉挛性咳嗽"],
            "stool_character": ["水样便", "糊状便", "黏液便", "脓血便"],
            "breathing": ["平稳", "急促", "困难", "有异响"],
            "activity": ["正常", "减弱", "不愿动"]
        }
        
        # 处理别名
        if slot == "symptoms": return options_map["symptom"]
        
        return options_map.get(slot, [])

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
        # 1. 首先检查危险信号 (Hard Safety Check)
        danger_alert = self.check_danger_signals(entities)
        if danger_alert:
            return TriageDecision(
                level="emergency",
                reason="检测到危险信号",
                action=danger_alert,
                danger_signal=danger_alert
            )

        # 2. 预处理实体 (计算派生字段)
        processed_entities = entities.copy()
        if "duration" in entities:
            processed_entities["duration_hours"] = self._duration_hours(entities["duration"])

        # 3. 基于规则引擎做决策
        if symptom in self.rules:
            decision = self._evaluate_rules(self.rules[symptom], processed_entities)
            if decision:
                return decision

        # 4. 回退到硬编码逻辑 (为了兼容未迁移的规则)
        if symptom == "发烧":
            return self._triage_fever(entities) # 此时应该已经被规则覆盖，作为Double Check
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

    def _evaluate_rules(self, rules: List[Dict[str, Any]], entities: Dict[str, Any]) -> Optional[TriageDecision]:
        """评估规则列表"""
        for rule in rules:
            conditions = rule.get("conditions", {})
            matched = True
            
            for key, condition in conditions.items():
                entity_value = entities.get(key)
                if not self._check_condition(entity_value, condition):
                    matched = False
                    break
            
            if matched:
                decision_data = rule["decision"]
                return TriageDecision(
                    level=decision_data["level"],
                    reason=decision_data["reason"],
                    action=decision_data["action"]
                )
        return None

    def get_missing_slots(
        self,
        symptom: str,
        entities: Dict[str, Any],
        profile_context: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """
        获取缺失的槽位（支持从档案自动填充）

        Args:
            symptom: 症状
            entities: 已提取的实体
            profile_context: 用户档案上下文（可选）

        Returns:
            List[str]: 缺失的槽位列表
        """
        if symptom not in self.slot_definitions:
            return []

        required_slots = self.slot_definitions[symptom].get("required", [])

        # 尝试从档案自动填充缺失槽位
        if profile_context and profile_context.get("baby_info"):
            baby_info = profile_context["baby_info"]

            # 自动填充月龄
            if "age_months" in required_slots and "age_months" not in entities:
                if baby_info.get("age_months"):
                    entities["age_months"] = baby_info["age_months"]
                    logger.info(f"从档案自动填充月龄: {baby_info['age_months']}个月")

            # 自动填充体重（用于药物剂量计算）
            if "weight_kg" in required_slots and "weight_kg" not in entities:
                if baby_info.get("weight_kg"):
                    entities["weight_kg"] = baby_info["weight_kg"]
                    logger.info(f"从档案自动填充体重: {baby_info['weight_kg']}kg")

        if self._should_relax_follow_up(symptom, entities):
            return []

        missing = []
        for slot in required_slots:
            if slot not in entities or entities[slot] is None:
                missing.append(slot)

        return missing

    def _should_relax_follow_up(self, symptom: str, entities: Dict[str, Any]) -> bool:
        """轻症或信息充足时减少追问"""
        if symptom != "发烧":
            return False

        age_months = self._to_number(entities.get("age_months"))
        temperature = self._to_number(entities.get("temperature"))
        mental_state = entities.get("mental_state", "")

        if age_months is None or temperature is None:
            return False

        if age_months >= 3 and temperature < 38.5 and ("正常" in mental_state or "玩耍" in mental_state or "还可以" in mental_state):
            return True

        return False

    def generate_follow_up_question(self, symptom: str, missing_slots: List[str]) -> str:
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

        # 优先使用配置文件中的问题模板
        symptom_questions = self.slot_definitions.get(symptom, {}).get("questions", {})
        if slot in symptom_questions:
            return symptom_questions[slot]

        # 回退到通用模板
        questions = {
            "age_months": "请问宝宝现在多大了？（月龄）",
            "temperature": "请问宝宝现在的体温是多少度？",
            "duration": "这个症状持续多久了？",
            "mental_state": "宝宝的精神状态怎么样？是玩耍正常还是比较蔫？",
            "accompanying_symptoms": "除了这个症状，还有其他不舒服的地方吗？比如咳嗽、呕吐等？",
            "frequency": "这个症状发生的频率怎么样？",
        }

        return questions.get(slot, f"请补充：{slot}")

    def _triage_fever(self, entities: Dict[str, Any]) -> TriageDecision:
        """发烧分诊"""
        age_months = self._to_number(entities.get("age_months"))
        temperature = entities.get("temperature")
        duration = entities.get("duration")
        mental_state = entities.get("mental_state", "")

        # 3个月以下发烧 -> 立即就医
        if age_months is not None and age_months < 3:
            return TriageDecision(
                level="emergency",
                reason="3个月以下婴儿发烧属于高危情况",
                action="⚠️ 请立即前往医院就诊！3个月以下婴儿发烧可能提示严重感染，需要医生评估。"
            )

        # 高热 + 精神萎靡 -> 立即就医
        temp_value = self._to_number(temperature)
        if temp_value is not None and temp_value >= 39.0 and "萎靡" in mental_state:
            return TriageDecision(
                level="emergency",
                reason="高热且精神状态不佳",
                action="⚠️ 建议尽快就医！宝宝高热且精神萎靡，需要医生评估是否有严重感染。"
            )

        # 持续高热超过48小时 -> 就医
        if duration and self._duration_hours(duration) >= 48:
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

    def _duration_hours(self, duration: str) -> float:
        """将持续时长文本转换为小时数"""
        value = self._to_number(duration)
        if value is None:
            return 0.0
        if "天" in duration:
            return value * 24
        if "小时" in duration:
            return value
        if "分钟" in duration:
            return value / 60.0
        return 0.0

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
