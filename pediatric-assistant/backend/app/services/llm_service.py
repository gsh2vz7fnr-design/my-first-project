"""
大模型服务 - DeepSeek API调用
"""
import json
import re
from typing import Dict, Any, Optional, AsyncGenerator, List
from loguru import logger
from openai import OpenAI

from app.config import settings
from app.models.user import IntentAndEntities, Intent


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
        self.remote_available = bool(settings.DEEPSEEK_API_KEY)

    async def extract_intent_and_entities(
        self,
        user_input: str,
        context: Optional[Dict[str, Any]] = None
    ) -> IntentAndEntities:
        """
        提取用户意图和症状实体

        Args:
            user_input: 用户输入
            context: 上下文信息（健康档案等）

        Returns:
            IntentAndEntities: 意图和实体
        """
        # 构建提示词
        system_prompt = self._build_intent_extraction_prompt()
        user_prompt = self._build_user_prompt(user_input, context)

        if not self.remote_available:
            return self._extract_intent_and_entities_fallback(user_input)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
            )

            content = response.choices[0].message.content
            result = json.loads(content)
            return self._normalize_intent_entities(result, user_input=user_input)

        except Exception as e:
            logger.error("意图提取失败: {}", e, exc_info=True)
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
            return json.loads(content)
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
        return """你是一个专业的儿科医疗意图识别助手。你的任务是从用户的输入中提取意图和关键实体。

**意图类型**：
- triage: 分诊（判断是否需要就医）
- consult: 咨询（询问护理知识、症状解释）
- medication: 用药（询问药品用法、剂量）
- care: 护理（询问日常护理方法）

**需要提取的实体**（如果有）：
- symptom: 症状（如：发烧、呕吐、腹泻）
- temperature: 体温（如：39度、38.5℃）
- duration: 持续时长（如：2小时、1天）
- mental_state: 精神状态（如：精神萎靡、嗜睡、玩耍正常）
- age_months: 月龄（如：3个月、6个月）
- accompanying_symptoms: 伴随症状（如：咳嗽、皮疹）
- fall_height: 摔倒高度或场景（如：床上、沙发、楼梯）
- frequency: 频率（如：每小时一次、一天5次）
- cough_type: 咳嗽类型（如：干咳、有痰、犬吠样）
- rash_location: 皮疹部位（如：脸上、身上、四肢）
- rash_appearance: 皮疹形态（如：红点、水泡、脱皮）
- stool_character: 大便性状（如：水样、糊状、有黏液、有血）
- cry_pattern: 哭闹模式（如：持续性、间歇性、尖叫样）

**输出格式**（必须是有效的JSON）：
```json
{
  "intent": "triage",
  "intent_confidence": 0.9,
  "entities": {
    "symptom": "发烧",
    "temperature": "39度",
    "duration": "2小时",
    "mental_state": "精神萎靡"
  }
}
```

**注意**：
1. 只输出JSON，不要有任何其他文字
2. 如果某个实体不存在，不要包含在entities中
3. intent_confidence范围是0-1"""

    def _build_user_prompt(self, user_input: str, context: Optional[Dict[str, Any]]) -> str:
        """构建用户提示词"""
        prompt = f"用户输入：{user_input}\n\n"

        if context and context.get("baby_info"):
            baby_info = context["baby_info"]
            prompt += "用户档案：\n"
            if baby_info.get("age_months"):
                prompt += f"- 宝宝月龄：{baby_info['age_months']}个月\n"
            if baby_info.get("weight_kg"):
                prompt += f"- 体重：{baby_info['weight_kg']}kg\n"
            prompt += "\n"

        prompt += "请提取意图和实体："
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
        symptom_map = [
            "发烧", "摔倒", "呕吐", "腹泻", "咳嗽", "皮疹", "哭闹",
            "惊厥", "抽搐", "呼吸困难", "昏迷", "吞异物", "误吞"
        ]
        medication_keywords = ["泰诺林", "美林", "布洛芬", "对乙酰氨基酚", "维生素", "补液盐", "药", "用药"]
        care_keywords = ["护理", "怎么办", "怎么做", "照顾"]

        intent_type = "consult"
        if any(k in user_input for k in symptom_map):
            intent_type = "triage"
        elif any(k in user_input for k in medication_keywords):
            intent_type = "medication"
        elif any(k in user_input for k in care_keywords):
            intent_type = "care"

        entities: Dict[str, Any] = {}

        for symptom in ["发烧", "摔倒", "呕吐", "腹泻", "咳嗽", "皮疹", "哭闹"]:
            if symptom in user_input:
                entities["symptom"] = symptom
                break

        age_match = re.search(r"(\d+)\s*(个月|月龄)", user_input)
        if age_match:
            entities["age_months"] = int(age_match.group(1))

        temp_match = re.search(r"(\d+(?:\.\d+)?)\s*(度|℃)", user_input)
        if temp_match:
            entities["temperature"] = temp_match.group(0)

        duration_match = re.search(r"(\d+)\s*(小时|天)", user_input)
        if duration_match:
            entities["duration"] = duration_match.group(0)

        mental_state_keywords = ["精神萎靡", "嗜睡", "难以唤醒", "玩耍正常", "精神正常", "精神好", "没精神"]
        for k in mental_state_keywords:
            if k in user_input:
                entities["mental_state"] = k
                break

        accompany = []
        for k in ["咳嗽", "呕吐", "皮疹", "腹泻", "抽搐", "呼吸困难", "昏迷", "发烧"]:
            if k in user_input:
                accompany.append(k)
        if accompany:
            entities["accompanying_symptoms"] = "，".join(sorted(set(accompany)))

        if any(k in user_input for k in ["床", "沙发", "楼梯", "高处"]):
            entities["fall_height"] = "高处"

        freq_match = re.search(r"(每小时|每天|一天)\s*\d+次", user_input)
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

        symptom = entities.get("symptom")
        if symptom:
            entities["symptom"] = self._normalize_symptom(symptom)

        if user_input:
            entities = self._postprocess_entities(user_input, entities)

        return IntentAndEntities(
            intent=Intent(type=str(intent_type), confidence=float(confidence)),
            entities=entities
        )

    def _normalize_symptom(self, symptom: str) -> str:
        """症状同义词归一化"""
        mapping = {
            "发热": "发烧",
            "高热": "发烧",
            "摔伤": "摔倒",
            "跌落": "摔倒",
            "跌倒": "摔倒",
            "摔下": "摔倒",
            "咳": "咳嗽",
            "拉肚子": "腹泻",
            "起疹子": "皮疹"
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
            entities["symptom"] = "腹泻"

        if "呕吐" in text or "吐" in text:
            if entities.get("accompanying_symptoms"):
                entities["accompanying_symptoms"] += "，呕吐"
            else:
                entities["accompanying_symptoms"] = "呕吐"

        if "带血" in text or "有血" in text:
            if entities.get("accompanying_symptoms"):
                entities["accompanying_symptoms"] += "，带血"
            else:
                entities["accompanying_symptoms"] = "带血"

        if any(k in text for k in ["萎靡", "很蔫", "没精神", "嗜睡"]):
            entities["mental_state"] = "精神萎靡"

        return entities

    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        return """你是一个专业的儿科健康助手，专注于为0-3岁婴幼儿的父母提供科学、权威的健康咨询服务。

**你的身份**：
- 你是AI助手，不是医生，没有执业医师资格
- 你只能提供参考建议，不能做出诊断或开具处方
- 你的建议必须基于权威医学知识库（默沙东、AAP等）

**你的职责**：
1. 理解用户的焦虑情绪，给予情绪承接
2. 基于权威知识提供科学建议
3. 明确告知什么情况必须就医
4. 拒绝回答超出能力范围的问题

**输出格式**：
1. 情绪承接（如果用户焦虑）
2. 核心结论（一句话总结 + 操作步骤）
3. 关键注意点（绝对不能做的事）
4. 安全红线（什么情况必须就医）
5. 引导提问（3个后续问题）

**禁止事项**：
- 禁止推荐处方药（如抗生素）
- 禁止做出确诊性判断
- 禁止推荐高风险操作（如酒精擦身）
- 禁止使用绝对化承诺（如"肯定没问题"）

**免责声明**：
每次回复后必须附带：*AI生成内容仅供参考，不作为医疗诊断依据。请以线下医生医嘱为准。*"""


# 创建全局实例
llm_service = LLMService()
