"""
大模型服务 - DeepSeek API调用
"""
import json
import re
import time
from typing import Dict, Any, Optional, AsyncGenerator, List
from loguru import logger
from openai import OpenAI

from app.config import settings
from app.models.user import IntentAndEntities, Intent
from app.utils.logger import get_logger


class LLMService:
    """大模型服务"""

    def __init__(self):
        """初始化"""
        self.client = OpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
            timeout=10
        )
        self.model = settings.DEEPSEEK_MODEL
        self._api_key_configured = bool(settings.DEEPSEEK_API_KEY)
        self._remote_cooldown_until: float = 0.0
        self.log = get_logger("LLMService")

    @property
    def remote_available(self) -> bool:
        if not self._api_key_configured:
            return False
        return time.time() >= self._remote_cooldown_until

    @remote_available.setter
    def remote_available(self, value: bool):
        if not value:
            self._remote_cooldown_until = time.time() + 60  # 60秒冷却
        else:
            self._remote_cooldown_until = 0.0

    def _parse_json_from_llm_response(self, content: str) -> dict:
        """
        从 LLM 响应中解析 JSON，清理可能的 Markdown 代码块标记

        Args:
            content: LLM 返回的原始内容，可能包含 ```json...``` 标记

        Returns:
            dict: 解析后的 JSON 对象

        Raises:
            json.JSONDecodeError: 如果清理后仍无法解析为有效 JSON
        """
        # 清理 Markdown 代码块标记
        content = content.strip()

        # 移除开头的 ```json 或 ```
        if content.startswith("```"):
            lines = content.split('\n', 1)
            if len(lines) > 1:
                content = lines[1]

        # 移除结尾的 ```
        if content.endswith("```"):
            content = content[:-3]

        content = content.strip()

        return json.loads(content)

    def _try_fast_path_extraction(self, user_input: str) -> Optional[dict]:
        """
        快速路径：检测简单的时间/数字输入，避免调用 LLM

        当用户输入只包含简单的时间信息（如"半天"、"3天"、"2小时"）时，
        直接返回 slot_filling 意图，跳过耗时 2 秒的 LLM 调用。

        Args:
            user_input: 用户输入

        Returns:
            Optional[dict]: 如果是简单输入则返回结果，否则返回 None
        """
        import re

        text = user_input.strip()

        # 简单时长模式：只包含时间单位 + 数字/中文数字
        # 匹配：半天、3天、2小时、5分钟、一周等
        time_patterns = [
            r'^[\d一二三四五六七八九十百千万几]+(?:天|日|周|个月?|小时?|分种?|秒种?)$',
            r'^(?:半天|多长时间|好几天|几天了|几小时|大概多久)$'
        ]

        for pattern in time_patterns:
            if re.match(pattern, text):
                # 提取时间值
                duration_value = text
                return {
                    "intent": "slot_filling",
                    "intent_confidence": 0.95,
                    "entities": {
                        "duration": duration_value
                    }
                }

        # 简单数字模式：只是补充数值信息
        if re.match(r'^\d+$', text):
            return {
                "intent": "slot_filling",
                "intent_confidence": 0.90,
                "entities": {
                    "unknown_numeric": text
                }
            }

        # 不是简单输入，需要走 LLM 路径
        return None

    async def extract_intent_and_entities(
        self,
        user_input: str,
        context: Optional[Dict[str, Any]] = None,
        accumulated_slots: Optional[Dict[str, Any]] = None
    ) -> IntentAndEntities:
        """
        提取用户意图和症状实体

        Args:
            user_input: 用户输入
            context: 上下文信息（健康档案等）
            accumulated_slots: 前几轮已累积的实体（让 LLM 知道已收集了什么）

        Returns:
            IntentAndEntities: 意图和实体
        """
        # P7 优化: 快速路径 - 检测简单的时间/数字输入，避免调用 LLM
        fast_result = self._try_fast_path_extraction(user_input)
        if fast_result:
            self.log.debug("快速路径提取: {}", fast_result)
            return self._normalize_intent_entities(fast_result, user_input=user_input)

        # 构建提示词
        system_prompt = self._build_intent_extraction_prompt()
        user_prompt = self._build_user_prompt(user_input, context, accumulated_slots)

        if not self.remote_available:
            return self._extract_intent_and_entities_fallback(user_input)

        try:
            self.log.debug("LLM Request | model={} | prompt={}", self.model, user_prompt[:200])
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
            )

            content = response.choices[0].message.content
            self.log.debug("LLM Response | raw={}", content)
            result = self._parse_json_from_llm_response(content)
            return self._normalize_intent_entities(result, user_input=user_input)

        except Exception as e:
            self.log.error("意图提取失败: {}", e, exc_info=True)
            self.remote_available = False
            return self._extract_intent_and_entities_fallback(user_input)

    async def generate_response_stream(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[str, None]:
        """
        流式生成回复

        Args:
            prompt: 提示词
            context: 上下文

        Yields:
            str: 生成的文本块
        """
        if not self.remote_available:
            yield "抱歉，系统当前无法连接大模型，请稍后重试。"
            return

        try:
            responses = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._build_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                stream=True,
                temperature=0.7,
            )

            for response in responses:
                delta = response.choices[0].delta
                if delta and delta.content:
                    yield delta.content

        except Exception as e:
            logger.error("流式生成异常: {}", e, exc_info=True)
            self.remote_available = False
            yield "抱歉，系统出现异常，请稍后重试。"

    async def extract_profile_updates(self, user_input: str) -> Dict[str, Any]:
        """
        从用户输入中抽取档案更新

        Args:
            user_input: 用户输入

        Returns:
            Dict[str, Any]: 更新内容
        """
        system_prompt = self._build_profile_extraction_prompt()
        if not self.remote_available:
            return {}

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"用户输入：{user_input}"}
                ],
                temperature=0.1,
            )

            content = response.choices[0].message.content
            return self._parse_json_from_llm_response(content)
        except Exception as e:
            logger.error("档案抽取异常: {}", e, exc_info=True)
            self.remote_available = False

        return {}

    def detect_emotion(self, user_input: str) -> Optional[str]:
        """
        检测用户情绪并返回情绪承接话术

        Args:
            user_input: 用户输入

        Returns:
            Optional[str]: 情绪承接话术，如果没有检测到焦虑则返回None
        """
        # 焦虑关键词
        anxiety_keywords = ["急", "怎么办", "哭闹", "担心", "害怕", "很急", "着急", "焦虑", "不知所措", "揪心"]

        # 检测是否包含焦虑关键词
        has_anxiety = any(keyword in user_input for keyword in anxiety_keywords)

        if not has_anxiety:
            return None

        # 根据场景返回不同的情绪承接话术
        if any(word in user_input for word in ["哭", "哭闹", "一直哭"]):
            return "听到宝宝哭闹确实让人很揪心，请先深呼吸，我们一步步来解决。"
        elif any(word in user_input for word in ["发烧", "发热", "高烧"]):
            return "看到宝宝发烧确实让人担心，别着急，我们先了解一下情况。"
        elif any(word in user_input for word in ["摔", "跌", "摔倒"]):
            return "宝宝摔倒确实让人紧张，请保持冷静，我们一起评估情况。"
        elif any(word in user_input for word in ["呕吐", "吐"]):
            return "看到宝宝呕吐确实让人心疼，别担心，我们先看看具体情况。"
        else:
            return "理解您的担心，这是一个非常好的问题，很多新手爸妈都会遇到。"

    async def generate_follow_up_suggestions(
        self,
        query: str,
        answer: str,
        context: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """
        生成引导提问（预测3个高价值后续问题）

        Args:
            query: 用户问题
            answer: 系统回答
            context: 上下文

        Returns:
            List[str]: 3个引导问题
        """
        # 本地规则生成（快速、不依赖LLM）
        suggestions = []

        # 根据问题类型生成引导问题
        if any(word in query for word in ["发烧", "发热"]):
            suggestions = [
                "什么情况下需要立即去医院？",
                "如何正确测量体温？",
                "退烧药怎么选择和使用？"
            ]
        elif any(word in query for word in ["咳嗽", "咳"]):
            suggestions = [
                "咳嗽多久需要就医？",
                "如何判断是否有痰？",
                "咳嗽时需要注意什么？"
            ]
        elif any(word in query for word in ["腹泻", "拉肚子"]):
            suggestions = [
                "如何预防脱水？",
                "什么样的大便需要就医？",
                "腹泻期间如何喂养？"
            ]
        elif any(word in query for word in ["呕吐", "吐"]):
            suggestions = [
                "呕吐后多久可以喂奶？",
                "如何判断是否脱水？",
                "什么情况需要立即就医？"
            ]
        elif any(word in query for word in ["摔倒", "摔", "跌"]):
            suggestions = [
                "摔倒后需要观察多久？",
                "哪些症状提示需要就医？",
                "如何预防宝宝摔倒？"
            ]
        elif any(word in query for word in ["皮疹", "疹子"]):
            suggestions = [
                "皮疹会传染吗？",
                "如何护理皮疹部位？",
                "什么情况需要就医？"
            ]
        elif any(word in query for word in ["药", "用药", "剂量"]):
            suggestions = [
                "药物有哪些副作用？",
                "如何正确喂药？",
                "多久可以见效？"
            ]
        elif any(word in query for word in ["护理", "照顾"]):
            suggestions = [
                "有哪些注意事项？",
                "多久会好转？",
                "如何预防复发？"
            ]
        else:
            # 通用引导问题
            suggestions = [
                "有哪些需要特别注意的地方？",
                "什么情况需要就医？",
                "如何观察宝宝的恢复情况？"
            ]

        return suggestions[:3]

    def _build_intent_extraction_prompt(self) -> str:
        """构建意图提取的系统提示词"""
        return """你是一个专业的儿科医疗意图识别助手。你的任务是从用户的输入中提取意图和所有关键实体。

**意图类型**：
- triage: 分诊（判断是否需要就医）- 用户首次描述症状，寻求医疗建议
- consult: 咨询（询问护理知识、症状解释）
- medication: 用药（询问药品用法、剂量）
- care: 护理（询问日常护理方法）
- greeting: 闲聊/打招呼（如：你好、谢谢）
- slot_filling: 补充信息（用户回复上一轮追问的答案，如回答"发烧"、"38度"、"1天"等）

**⚠️ 重要：如何区分 triage 和 slot_filling**：
- triage: 用户**首次**描述一个完整的医疗问题，包含疑问或寻求建议
  - 例: "宝宝发烧了怎么办"、"孩子咳嗽三天了要紧吗"
- slot_filling: 用户的回复是**简短的信息补充**，通常是对Bot追问的直接回答
  - 例: "发烧"、"38度"、"1天"、"精神不好"、"流鼻涕、咳嗽"
  - 如果输入**只是**症状名、数值、时长、状态等简短词汇，应该是 slot_filling

**需要提取的实体**（如果有）：
- symptom: 症状（如：发烧、呕吐、腹泻）
- temperature: 体温（如：39度、38.5℃、38.5）- 提取数值部分，统一带上"℃"或"度"
- duration: 持续时长（如：2小时、1天、半天、刚刚发现）
- mental_state: 精神状态（如：精神萎靡、嗜睡、玩耍正常、精神不好）
- age_months: 月龄（如：3个月、6个月）- 只提取数字
- accompanying_symptoms: 伴随症状（如：咳嗽、皮疹）
- fall_height: 摔倒高度或场景（如：床上、沙发、楼梯）
- frequency: 频率（如：每小时一次、一天5次）
- cough_type: 咳嗽类型（如：干咳、有痰、犬吠样）
- rash_location: 皮疹部位（如：脸上、身上、四肢）
- rash_appearance: 皮疹形态（如：红点、水泡、脱皮）
- stool_character: 大便性状（如：水样、糊状、有黏液、有血）
- cry_pattern: 哭闹模式（如：持续性、间歇性、尖叫样）

**One-shot Examples**:

用户输入："我家宝宝8个月大，发烧38.5度一天了，精神不好"
```json
{
  "intent": "triage",
  "intent_confidence": 0.99,
  "entities": {
    "symptom": "发烧",
    "age_months": 8,
    "temperature": "38.5度",
    "duration": "1天",
    "mental_state": "精神不好"
  }
}
```

用户输入："发烧、流鼻涕"
```json
{
  "intent": "slot_filling",
  "intent_confidence": 0.9,
  "entities": {
    "symptom": "发烧",
    "accompanying_symptoms": "流鼻涕"
  }
}
```

用户输入："38.5"
```json
{
  "intent": "slot_filling",
  "intent_confidence": 0.95,
  "entities": {
    "temperature": "38.5度"
  }
}
```

用户输入："刚刚发现"
```json
{
  "intent": "slot_filling",
  "intent_confidence": 0.95,
  "entities": {
    "duration": "刚刚发现"
  }
}
```

用户输入："宝宝2岁，拉肚子，一天拉了5次，水样的，怎么办"
```json
{
  "intent": "triage",
  "intent_confidence": 0.95,
  "entities": {
    "symptom": "腹泻",
    "age_months": 24,
    "frequency": "一天5次",
    "stool_character": "水样"
  }
}
```

**注意**：
1. 只输出JSON，不要有任何其他文字
2. **尽可能提取所有出现的实体**，特别是年龄(age_months)和体温(temperature)
3. intent_confidence范围是0-1
4. age_months 必须是数字（如 8 表示 8个月，2岁要转换为24）
5. duration 要保留原始表述（如 "刚刚发现"、"半天"、"1天"、"2-3天"）
6. mental_state 要标准化为：正常玩耍、精神差、嗜睡、烦躁不安 等"""

    def _build_user_prompt(self, user_input: str, context: Optional[Dict[str, Any]], accumulated_slots: Optional[Dict[str, Any]] = None) -> str:
        """构建用户提示词（包含累积上下文）"""
        prompt = f"用户输入：{user_input}\n\n"

        if context and context.get("baby_info"):
            baby_info = context["baby_info"]
            prompt += "用户档案：\n"
            if baby_info.get("age_months"):
                prompt += f"- 宝宝月龄：{baby_info['age_months']}个月\n"
            if baby_info.get("weight_kg"):
                prompt += f"- 体重：{baby_info['weight_kg']}kg\n"
            prompt += "\n"

        # 注入前几轮已累积的实体，让 LLM 知道上下文
        if accumulated_slots:
            prompt += "前几轮已收集的信息：\n"
            for k, v in accumulated_slots.items():
                # ⚠️ 核心过滤逻辑：如果 age_months 为 0 或 None，直接跳过，不写入 Prompt
                if k == "age_months" and (v is None or v == 0):
                    self.log.debug("Filtered invalid age_months: {} from LLM prompt", v)
                    continue
                prompt += f"- {k}: {v}\n"
            prompt += "\n请基于以上已知信息，从本轮用户输入中提取**新增**的意图和实体。已有信息无需重复提取。\n"
        else:
            prompt += "这是用户的首轮输入，请尽可能提取所有信息。\n"

        prompt += "\n请提取意图和实体："
        return prompt

    def _build_profile_extraction_prompt(self) -> str:
        """构建档案抽取提示词"""
        return """你是一个儿科健康档案抽取助手。请仅从用户输入中抽取明确陈述的信息，不要推测或补全。

需要抽取的字段（如无则省略）：
- baby_info: age_months, weight_kg, gender
- allergy_history: allergen, reaction
- medical_history: condition
- medication_history: drug, note

输出格式（必须是有效JSON）：
{
  "baby_info": {"age_months": 6, "weight_kg": 8.5, "gender": "male"},
  "allergy_history": [{"allergen": "鸡蛋", "reaction": "呕吐"}],
  "medical_history": [{"condition": "热性惊厥"}],
  "medication_history": [{"drug": "泰诺林", "note": "喂不进"}]
}

注意：
1. 只输出JSON，不要包含其他文字
2. 没有的信息不要输出对应字段
3. 不要进行诊断或推断"""

    def _extract_intent_and_entities_fallback(self, user_input: str) -> IntentAndEntities:
        """意图与实体抽取的本地兜底规则"""
        text = user_input.lower()

        # 0a. Greeting 检测（短文本优先，排除混合意图）
        greeting_patterns = ["你好", "您好", "嗨", "hi", "hello", "在吗", "在不在", "谢谢", "谢了"]
        text_stripped = text.strip()

        # 检测是否包含症状关键词（用于排除混合意图）
        mixed_intent_indicators = [
            "发烧", "发热", "呕吐", "腹泻", "拉肚子", "咳嗽", "皮疹", "哭闹",
            "摔", "跌", "惊厥", "抽搐", "呼吸困难", "昏迷", "便秘"
        ]
        has_medical_content = any(indicator in text_stripped for indicator in mixed_intent_indicators)

        # 只有在没有医疗内容时才判定为纯 greeting
        is_pure_greeting = (
            not has_medical_content and  # 排除混合意图
            any(text_stripped == g for g in greeting_patterns)  # 完全匹配
        )
        if is_pure_greeting:
            return self._normalize_intent_entities({
                "intent": "greeting",
                "intent_confidence": 0.9,
                "entities": {}
            }, user_input=user_input)

        # 0b. Slot-filling 检测 (key: value 格式)
        slot_pattern = re.compile(r'(\w+)\s*[:：]\s*(.+?)(?:\n|$)')
        slot_matches = slot_pattern.findall(user_input)
        known_slots = {
            "mental_state", "duration", "temperature", "age_months",
            "frequency", "accompanying_symptoms", "fall_height",
            "stool_character", "cough_type", "rash_location"
        }
        if slot_matches and any(k in known_slots for k, _ in slot_matches):
            entities = {k.strip(): v.strip() for k, v in slot_matches if k.strip()}
            return self._normalize_intent_entities({
                "intent": "slot_filling",
                "intent_confidence": 0.85,
                "entities": entities
            }, user_input=user_input)

        symptom_map = [
            "发烧", "发热", "高烧",
            "摔倒", "摔伤", "跌倒", "跌落",
            "呕吐", "吐", "吐奶",  # 添加"吐"以匹配"吐了"
            "腹泻", "拉肚子", "拉稀", "拉",  # 添加"拉"以匹配"拉了"
            "咳嗽", "咳",
            "皮疹", "起疹子", "湿疹",
            "哭闹", "哭闹不安",
            "流鼻涕", "鼻塞", "流涕",
            "惊厥", "抽搐", "呼吸困难", "昏迷", "吞异物", "误吞",
            "便秘"
        ]
        medication_keywords = ["泰诺林", "美林", "布洛芬", "对乙酰氨基酚", "维生素", "补液盐", "药", "用药"]
        care_keywords = ["护理", "怎么办", "怎么做", "照顾", "如何", "怎么", "什么"]

        intent_type = "consult"
        if any(k in user_input for k in symptom_map):
            intent_type = "triage"
        elif any(k in user_input for k in medication_keywords):
            intent_type = "medication"
        elif any(k in user_input for k in care_keywords):
            intent_type = "care"

        entities: Dict[str, Any] = {}

        # 提取所有匹配的症状
        matched_symptoms = []
        # 首先检查是否为纯顿号分隔的症状列表（前端多选格式）
        # 判断标准：整个输入只包含顿号分隔的症状，没有其他描述性文字
        is_pure_list = True
        if "、" in user_input:
            parts = [part.strip() for part in user_input.split("、") if part.strip()]
            # 检查每个部分是否都是纯症状（没有其他描述性文字）
            symptom_list = [
                "发烧", "发热", "高烧",
                "摔倒", "摔伤", "跌倒", "跌落",
                "呕吐", "吐奶",
                "腹泻", "拉肚子", "拉稀",
                "咳嗽", "咳",
                "皮疹", "起疹子", "湿疹",
                "哭闹", "哭闹不安",
                "流鼻涕", "鼻塞", "流涕",
                "惊厥", "抽搐", "呼吸困难", "昏迷", "吞异物", "误吞",
                "便秘"
            ]
            for part in parts:
                # 只有当部分完全匹配症状列表时才认为是纯列表
                if part not in symptom_list:
                    # 尝试归一化后匹配
                    normalized = self._normalize_symptom(part)
                    if normalized not in symptom_list:
                        is_pure_list = False
                        break

            # 只有纯列表格式才使用顿号分隔逻辑
            if is_pure_list:
                for part in parts:
                    normalized_symptom = self._normalize_symptom(part)
                    if normalized_symptom not in matched_symptoms:
                        matched_symptoms.append(normalized_symptom)

        # 如果没有找到顿号分隔的症状，按原逻辑搜索
        if not matched_symptoms:
            for symptom in [
                "发烧", "发热", "高烧",
                "摔倒", "摔伤", "跌倒", "跌落",
                "呕吐", "吐奶",
                "腹泻", "拉肚子", "拉稀",
                "咳嗽", "咳",
                "皮疹", "起疹子", "湿疹",
                "哭闹", "哭闹不安",
                "流鼻涕", "鼻塞", "流涕",
                "惊厥", "抽搐", "呼吸困难", "昏迷", "吞异物", "误吞",
                "便秘"
            ]:
                if symptom in user_input:
                    normalized_symptom = self._normalize_symptom(symptom)
                    if normalized_symptom not in matched_symptoms:
                        matched_symptoms.append(normalized_symptom)

        if matched_symptoms:
            # 按照优先级排序症状（优先级数字小的更严重，应该作为主要症状）
            matched_symptoms.sort(key=lambda s: self._get_symptom_priority(s))
            # 优先级最高的症状作为主要症状
            entities["symptom"] = matched_symptoms[0]
            # 如果有多个症状，其余作为伴随症状
            if len(matched_symptoms) > 1:
                # 合并伴随症状，过滤掉主要症状
                main_symptom_normalized = self._normalize_symptom(matched_symptoms[0])
                accompanying = []
                for symptom in matched_symptoms[1:]:
                    normalized_symptom = self._normalize_symptom(symptom)
                    # 检查是否与主要症状相同
                    if normalized_symptom != main_symptom_normalized:
                        # 检查是否已在伴随症状中
                        if normalized_symptom not in accompanying:
                            accompanying.append(normalized_symptom)

                # 合并已有的伴随症状
                existing_accompanying = entities.get("accompanying_symptoms", "")
                if existing_accompanying:
                    # 将字符串转换为列表
                    if isinstance(existing_accompanying, str):
                        existing_list = [s.strip() for s in existing_accompanying.split("，") if s.strip()]
                    else:
                        existing_list = []

                    # 归一化所有症状
                    normalized_existing = [self._normalize_symptom(s) for s in existing_list]
                    normalized_accompanying = [self._normalize_symptom(s) for s in accompanying]

                    # 去重合并
                    all_accompanying = []
                    for symptom in normalized_existing + normalized_accompanying:
                        if symptom not in all_accompanying:
                            all_accompanying.append(symptom)

                    entities["accompanying_symptoms"] = "，".join(all_accompanying)
                else:
                    # 归一化伴随症状
                    normalized_accompanying = [self._normalize_symptom(s) for s in accompanying]
                    # 去重
                    unique_accompanying = []
                    for symptom in normalized_accompanying:
                        if symptom not in unique_accompanying:
                            unique_accompanying.append(symptom)
                    entities["accompanying_symptoms"] = "，".join(unique_accompanying)

        # 增强年龄提取 - 支持多种格式
        # "8个月", "8 个月", "8月", "8月大", "8个月大", "宝宝8个月", "2岁", "两岁半"
        age_patterns = [
            r"(\d+)\s*个?月(?:龄|大)?",  # 8个月, 8个月大, 8月龄
            r"宝宝.*?(\d+)\s*个?月",      # 宝宝8个月
            r"(\d+)月(?:大|龄)?",         # 8月大, 8月龄
            r"(\d+)\s*岁(?:半)?",          # 2岁, 2岁半
            r"(一|两|三|四|五|六)\s*岁(?:半)?", # 两岁, 两岁半
            r"([一二三四五六七八九十])\s*个?月(?:龄|大)?", # 八个月, 六个月
            r"宝宝.*?([一二三四五六七八九十])\s*个?月", # 宝宝八个月
        ]

        cn_num_map = {"一": 1, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}

        for pattern in age_patterns:
            age_match = re.search(pattern, user_input)
            if age_match:
                raw_val = age_match.group(1)
                is_year = "岁" in age_match.group(0)
                is_half = "半" in age_match.group(0)
                
                # 转换中文数字
                num_val = cn_num_map.get(raw_val, raw_val)
                try:
                    num_val = int(num_val)
                    if is_year:
                        total_months = num_val * 12
                        if is_half:
                            total_months += 6
                        entities["age_months"] = total_months
                    else:
                        entities["age_months"] = num_val
                except ValueError:
                    continue # 无法转换则跳过
                break

        # 增强体温提取 - 支持更多格式
        # "38.5度", "38.5℃", "发烧38.5", "体温38.5", "38度5"
        temp_patterns = [
            r"(\d+)\s*度\s*(\d+)",  # 优先处理 "38度5" 格式，避免被 "38度" 先匹配
            r"(\d+(?:\.\d+)?)\s*(?:度|℃|°c)",
            r"(?:发烧|体温|烧到?)[是为]?\s*(\d+(?:\.\d+)?)",
        ]
        for pattern in temp_patterns:
            temp_match = re.search(pattern, user_input, re.IGNORECASE)
            if temp_match:
                if temp_match.lastindex >= 2:  # 如果有两个捕获组（如 38度5）
                    # 合并为小数
                    whole = temp_match.group(1)
                    decimal = temp_match.group(2)
                    temp_value = f"{whole}.{decimal}"
                else:
                    temp_value = temp_match.group(1)
                if float(temp_value) > 30 and float(temp_value) < 45:  # 合理体温范围
                    entities["temperature"] = f"{temp_value}度"
                break

        # 增强持续时间提取
        # "1天", "两天", "半天", "3小时", "刚刚发现", "昨天开始", "从前天起"
        duration_patterns = [
            r"(刚刚发现|刚开始|刚发现)",
            r"(半天|大半天)",
            r"(?:从?)(昨天|前天|今天|今早|昨晚|前天晚上)(?:开始|起)?",
            r"(\d+)\s*(?:天|日)",
            r"(一两|两三|\d+[-~]\d+)\s*天",
            r"(\d+)\s*(?:小时|个?钟头)",
            r"(一|两|三|四|五|六|七|八|九|十)(?:天|日|小时)",
        ]
        for pattern in duration_patterns:
            duration_match = re.search(pattern, user_input)
            if duration_match:
                entities["duration"] = duration_match.group(0)
                break

        # 增强精神状态提取
        mental_state_keywords = [
            ("精神萎靡", "精神萎靡"),
            ("精神不好", "精神不好"),
            ("精神差", "精神差"),
            ("没精神", "精神差"),
            ("有点蔫", "精神差"),
            ("嗜睡", "嗜睡"),
            ("难以唤醒", "嗜睡"),
            ("想睡觉", "嗜睡"),
            ("玩耍正常", "正常玩耍"),
            ("精神正常", "正常玩耍"),
            ("精神好", "正常玩耍"),
            ("精神还可以", "正常玩耍"),
            ("正常玩耍", "正常玩耍"),
            ("哭闹", "哭闹不安"),
            ("烦躁", "烦躁不安"),
        ]
        for keyword, state in mental_state_keywords:
            if keyword in user_input:
                entities["mental_state"] = state
                break

        accompany = []
        main_symptom = entities.get("symptom", "")
        main_symptom_normalized = self._normalize_symptom(main_symptom) if main_symptom else ""
        for k in ["咳嗽", "呕吐", "皮疹", "腹泻", "抽搐", "呼吸困难", "昏迷", "发烧", "流鼻涕", "鼻塞", "流涕", "哭闹", "哭闹不安"]:
            if k in user_input:
                normalized_k = self._normalize_symptom(k)
                if normalized_k != main_symptom_normalized:
                    accompany.append(k)
        if accompany:
            # 合并到已有的伴随症状
            existing_accompanying = entities.get("accompanying_symptoms", "")
            if existing_accompanying:
                # 将字符串转换为列表
                if isinstance(existing_accompanying, str):
                    existing_list = [s.strip() for s in existing_accompanying.split("，") if s.strip()]
                else:
                    existing_list = []

                # 归一化所有症状
                normalized_existing = [self._normalize_symptom(s) for s in existing_list]
                normalized_accompany = [self._normalize_symptom(s) for s in accompany]

                # 去重合并
                all_accompanying = []
                for symptom in normalized_existing + normalized_accompany:
                    if symptom not in all_accompanying:
                        all_accompanying.append(symptom)

                entities["accompanying_symptoms"] = "，".join(sorted(all_accompanying))
            else:
                # 归一化伴随症状
                normalized_accompany = [self._normalize_symptom(s) for s in accompany]
                # 去重
                unique_accompanying = []
                for symptom in normalized_accompany:
                    if symptom not in unique_accompanying:
                        unique_accompanying.append(symptom)
                entities["accompanying_symptoms"] = "，".join(sorted(unique_accompanying))

        if any(k in user_input for k in ["床", "沙发", "楼梯", "高处"]):
            entities["fall_height"] = "高处"

        freq_match = re.search(r"(每小时|每天|一天).{0,15}?\d+\s*次", user_input)
        if freq_match:
            entities["frequency"] = freq_match.group(0)

        for k in ["干咳", "有痰", "犬吠样"]:
            if k in user_input:
                entities["cough_type"] = k
                break

        for k in ["脸", "身", "四肢"]:
            if k in user_input:
                entities["rash_location"] = k
                break

        for k in ["红点", "水泡", "脱皮"]:
            if k in user_input:
                entities["rash_appearance"] = k
                break

        for k in ["水样", "糊状", "黏液", "有血"]:
            if k in user_input:
                entities["stool_character"] = k
                break

        for k in ["持续", "间歇", "尖叫"]:
            if k in user_input:
                entities["cry_pattern"] = k
                break

        return self._normalize_intent_entities({
            "intent": intent_type,
            "intent_confidence": 0.4,
            "entities": entities
        }, user_input=user_input)

    def _normalize_intent_entities(self, result: Dict[str, Any], user_input: Optional[str] = None) -> IntentAndEntities:
        """归一化意图与实体"""
        intent_type = result.get("intent") or "consult"
        confidence = result.get("intent_confidence") or 0.4
        entities = result.get("entities") or {}

        # 归一化键名：age -> age_months, month_age -> age_months
        if "age" in entities:
            entities["age_months"] = entities.pop("age")
        if "month_age" in entities:
             entities["age_months"] = entities.pop("month_age")

        # 归一化年龄值：将 "8个月" -> 8, "2岁" -> 24
        if "age_months" in entities:
            val = entities["age_months"]
            if isinstance(val, str):
                # 尝试提取数字
                match = re.search(r"(\d+)", val)
                if match:
                    num = int(match.group(1))
                    # 简单启发式：如果包含"岁"，乘12
                    if "岁" in val:
                        num *= 12
                    entities["age_months"] = num
                else:
                    # 无法解析则删除，避免脏数据
                    del entities["age_months"]

        symptom = entities.get("symptom")
        if symptom:
            entities["symptom"] = self._normalize_symptom(symptom)

        if user_input:
            entities = self._postprocess_entities(user_input, entities)

        return IntentAndEntities(
            intent=Intent(type=str(intent_type), confidence=float(confidence)),
            entities=entities
        )

    def _get_symptom_priority(self, symptom: str) -> int:
        """获取症状优先级（数字越小优先级越高）"""
        priority_map = {
            "惊厥": 1,
            "抽搐": 1,
            "呼吸困难": 1,
            "昏迷": 1,
            "吞异物": 1,
            "误吞": 1,
            "发烧": 2,
            "发热": 2,
            "高烧": 2,
            "摔倒": 3,
            "摔伤": 3,
            "跌倒": 3,
            "跌落": 3,
            "呕吐": 4,
            "吐奶": 4,
            "腹泻": 5,
            "拉肚子": 5,
            "拉稀": 5,
            "咳嗽": 6,
            "咳": 6,
            "皮疹": 7,
            "起疹子": 7,
            "湿疹": 7,
            "流鼻涕": 8,
            "鼻塞": 8,
            "流涕": 8,
            "哭闹": 9,
            "哭闹不安": 9,
            "便秘": 10
        }
        # 归一化症状
        normalized = self._normalize_symptom(symptom)
        return priority_map.get(normalized, 99)

    def _normalize_symptom(self, symptom: str) -> str:
        """症状同义词归一化"""
        mapping = {
            "发热": "发烧",
            "高热": "发烧",
            "高烧": "发烧",
            "摔伤": "摔倒",
            "跌落": "摔倒",
            "跌倒": "摔倒",
            "摔下": "摔倒",
            "咳": "咳嗽",
            "拉肚子": "腹泻",
            "拉稀": "腹泻",
            "吐奶": "呕吐",
            "起疹子": "皮疹",
            "湿疹": "皮疹",
            "鼻塞": "流鼻涕",
            "流涕": "流鼻涕",
            "哭闹不安": "哭闹"
        }
        for key, value in mapping.items():
            if key in symptom:
                return value
        return symptom

    def _postprocess_entities(self, user_input: str, entities: Dict[str, Any]) -> Dict[str, Any]:
        """根据原始输入补全/纠正实体"""
        text = user_input
        symptom = entities.get("symptom")

        fall_keywords = ["摔", "跌", "床", "沙发", "楼梯", "高处"]
        if any(k in text for k in fall_keywords):
            if symptom in (None, "", "呕吐", "腹泻", "咳嗽"):
                entities["symptom"] = "摔倒"

        if "发热" in text or "发烧" in text:
            if not symptom:
                entities["symptom"] = "发烧"

        if "拉肚子" in text or "腹泻" in text:
            # 只有当主症状为空或优先级更低时才设置腹泻为主症状
            current_symptom = entities.get("symptom")
            diarrhea_priority = self._get_symptom_priority("腹泻")
            if not current_symptom:
                entities["symptom"] = "腹泻"
            elif self._get_symptom_priority(current_symptom) > diarrhea_priority:
                # 当前症状优先级更低（数字更大），则用腹泻覆盖
                entities["symptom"] = "腹泻"

        if "流鼻涕" in text or "鼻塞" in text or "流涕" in text:
            if not symptom:
                entities["symptom"] = "流鼻涕"
            elif symptom != "流鼻涕":
                # 添加到伴随症状
                existing = entities.get("accompanying_symptoms", "")
                if "流鼻涕" not in existing and "鼻塞" not in existing and "流涕" not in existing:
                    if existing:
                        entities["accompanying_symptoms"] = existing + "，流鼻涕"
                    else:
                        entities["accompanying_symptoms"] = "流鼻涕"

        if "哭闹" in text or "哭闹不安" in text:
            if not symptom:
                entities["symptom"] = "哭闹"
            elif symptom != "哭闹":
                # 添加到伴随症状
                existing = entities.get("accompanying_symptoms", "")
                if "哭闹" not in existing and "哭闹不安" not in existing:
                    if existing:
                        entities["accompanying_symptoms"] = existing + "，哭闹"
                    else:
                        entities["accompanying_symptoms"] = "哭闹"

        # 修复 Bug #2: 追加前检查是否已包含，避免重复
        if "呕吐" in text or "吐" in text:
            current_symptom = entities.get("symptom")
            vomiting_priority = self._get_symptom_priority("呕吐")
            # 如果主症状为空或优先级更低，设置呕吐为主症状
            if not current_symptom:
                entities["symptom"] = "呕吐"
            elif current_symptom != "呕吐" and self._get_symptom_priority(current_symptom) > vomiting_priority:
                # 当前症状优先级更低，用呕吐替换
                entities["symptom"] = "呕吐"
            elif current_symptom != "呕吐":
                # 添加到伴随症状
                existing = entities.get("accompanying_symptoms", "")
                if "呕吐" not in existing:
                    if existing:
                        entities["accompanying_symptoms"] = existing + "，呕吐"
                    else:
                        entities["accompanying_symptoms"] = "呕吐"

        if "带血" in text or "有血" in text:
            existing = entities.get("accompanying_symptoms", "")
            # 检查是否已包含"带血"或"有血"
            if "带血" not in existing and "有血" not in existing:
                if existing:
                    entities["accompanying_symptoms"] = existing + "，带血"
                else:
                    entities["accompanying_symptoms"] = "带血"

        if any(k in text for k in ["萎靡", "很蔫", "没精神", "嗜睡"]):
            entities["mental_state"] = "精神萎靡"

        return entities

    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        return """你是「小儿安」，一位温暖专业的儿科健康顾问，服务对象是0-3岁宝宝的家长。

身份说明：
你是 AI 健康助手，不是医生。你提供的是参考建议，不是医疗诊断。

你的风格：
- 像一位经验丰富的儿科护士，温暖、耐心、不说教
- 先共情，再给建议
- 用简短易懂的句子，避免医学术语堆砌
- 当不确定时坦诚说"建议咨询医生"，而不是生硬拒绝

回答结构：
1. 情绪承接（如果家长明显焦虑）
2. 核心建议（简明扼要）
3. 需要注意的事项
4. 什么情况必须去医院
5. 您可能还想了解（2-3个后续问题）

底线规则：
- 不推荐具体处方药
- 不做确诊判断
- 不给绝对化承诺

每次回答末尾附带：
以上为 AI 参考建议，不作为医疗诊断依据，请以医生医嘱为准。"""

    async def generate_structured_triage_response(
        self,
        rag_content: str,
        user_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        生成结构化分诊响应（4部分格式，≤180字）

        Args:
            rag_content: RAG检索到的医学内容
            user_context: 用户上下文（症状、月龄等）

        Returns:
            str: 结构化响应文本
        """
        # 构建4部分格式的提示词
        prompt = f"""基于以下医学内容，生成一个结构化的分诊响应。

医学内容：
{rag_content}

用户上下文：
{json.dumps(user_context, ensure_ascii=False) if user_context else "无"}

请生成一个包含以下4部分的响应（总字数≤180字）：
1. 症状识别（20-30字）：简要确认症状和严重程度
2. 初步判断（30-40字）：基于医学内容的初步评估
3. 处理建议（50-60字）：具体的居家护理或就医建议
4. 观察要点（30-40字）：需要重点观察的症状变化

要求：
- 使用温暖、专业的语气
- 避免医学术语堆砌
- 每部分用换行分隔
- 不要加序号或标题

直接输出响应文本，不要解释。"""

        if not self.remote_available:
            # 本地兜底：使用简化格式
            return self._generate_fallback_triage_response(user_context)

        try:
            self.log.debug("[LLM] 开始生成结构化分诊响应，prompt长度: {}", len(prompt))
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._build_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=300
            )
            result = response.choices[0].message.content.strip()
            self.log.info("[LLM] 结构化分诊响应生成成功，长度: {}", len(result))
            return result
        except Exception as e:
            self.log.error("生成结构化分诊响应失败: {}", e, exc_info=True)
            self.remote_available = False
            return self._generate_fallback_triage_response(user_context)

    async def generate_structured_consult_response(
        self,
        rag_content: str,
        user_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        生成结构化咨询响应（3部分格式，≤180字）

        Args:
            rag_content: RAG检索到的医学内容
            user_context: 用户上下文

        Returns:
            str: 结构化响应文本
        """
        prompt = f"""基于以下医学内容，生成一个结构化的咨询响应。

医学内容：
{rag_content}

用户上下文：
{json.dumps(user_context, ensure_ascii=False) if user_context else "无"}

请生成一个包含以下3部分的响应（总字数≤180字）：
1. 核心解答（50-60字）：直接回答用户的问题
2. 补充说明（50-60字）：相关的注意事项或背景知识
3. 建议行动（30-40字）：具体的护理建议或观察要点

要求：
- 使用温暖、专业的语气
- 避免医学术语堆砌
- 每部分用换行分隔
- 不要加序号或标题

直接输出响应文本，不要解释。"""

        if not self.remote_available:
            return self._generate_fallback_consult_response(user_context)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._build_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=300
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            self.log.error("生成结构化咨询响应失败: {}", e, exc_info=True)
            self.remote_available = False
            return self._generate_fallback_consult_response(user_context)

    async def generate_structured_health_advice(
        self,
        rag_content: str,
        user_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        生成结构化健康建议（混合格式）

        Args:
            rag_content: RAG检索到的医学内容
            user_context: 用户上下文

        Returns:
            str: 结构化响应文本
        """
        prompt = f"""基于以下医学内容，生成一个结构化的健康建议。

医学内容：
{rag_content}

用户上下文：
{json.dumps(user_context, ensure_ascii=False) if user_context else "无"}

请生成包含以下部分的响应：
1. 简短引言（20-30字）
2. 关键建议（分点列出，2-3条，每条20-30字）
3. 注意事项（30-40字）

格式示例：
理解您的关心。关于XX，有几点建议：

• 第一条建议内容
• 第二条建议内容
• 第三条建议内容

需要注意：观察要点和预警信号

要求：
- 使用温暖、专业的语气
- 建议部分用"•"符号分点
- 总字数控制在200字以内

直接输出响应文本，不要解释。"""

        if not self.remote_available:
            return self._generate_fallback_health_advice(user_context)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._build_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=350
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            self.log.error("生成结构化健康建议失败: {}", e, exc_info=True)
            self.remote_available = False
            return self._generate_fallback_health_advice(user_context)

    def _generate_fallback_triage_response(self, context: Optional[Dict[str, Any]]) -> str:
        """本地兜底：生成简化的分诊响应"""
        symptom = context.get("symptom", "不适") if context else "不适"
        return f"""已收到您关于宝宝{symptom}的情况。

根据描述，建议先在家观察症状变化。

注意保持宝宝舒适，适当补充水分，观察精神状态。

如果症状加重或出现新的不适，请及时就医。"""

    def _generate_fallback_consult_response(self, context: Optional[Dict[str, Any]]) -> str:
        """本地兜底：生成简化的咨询响应"""
        return """理解您的关心。

建议您密切观察宝宝的情况，保持舒适的环境。

如有疑虑，建议咨询专业医生获取更准确的建议。"""

    def _generate_fallback_health_advice(self, context: Optional[Dict[str, Any]]) -> str:
        """本地兜底：生成简化的健康建议"""
        return """理解您的关心。关于这个问题，有几点建议：

• 密切观察宝宝的状态变化
• 保持舒适的环境和适当的水分补充
• 记录症状的发展情况

需要注意：如果情况加重或出现新症状，请及时就医。"""


# 创建全局实例
llm_service = LLMService()
