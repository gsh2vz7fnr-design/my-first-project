"""
意图识别路由服务

功能：
1. 识别用户输入的意图类型
2. 提取医疗相关实体
3. 路由到不同的处理流程

设计原则：
- 速度优先：使用轻量级模型或规则匹配
- 容错性：LLM 失败时使用规则兜底
- 默认安全：无法识别时默认为 MEDICAL_QUERY（宁可错查，不可漏查）
"""
import json
import re
import time
from enum import Enum
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from loguru import logger
from openai import OpenAI

from app.config import settings


class Intent(str, Enum):
    """用户意图类型"""
    GREETING = "GREETING"           # 闲聊、打招呼
    MEDICAL_QUERY = "MEDICAL_QUERY" # 医疗咨询
    DATA_ENTRY = "DATA_ENTRY"       # 数据录入（如更新症状信息）
    EXIT = "EXIT"                   # 结束对话
    UNKNOWN = "UNKNOWN"             # 无法识别


@dataclass
class IntentResult:
    """意图识别结果"""
    intent: Intent
    confidence: float = 1.0
    detected_symptoms: List[str] = field(default_factory=list)
    entities: Dict[str, Any] = field(default_factory=dict)
    raw_response: str = ""

    def is_medical(self) -> bool:
        """是否需要医疗检索"""
        return self.intent in (Intent.MEDICAL_QUERY, Intent.DATA_ENTRY, Intent.UNKNOWN)

    def is_simple_response(self) -> bool:
        """是否可以直接回复（不需要检索）"""
        return self.intent in (Intent.GREETING, Intent.EXIT)


class IntentRouter:
    """
    意图识别路由器

    使用 LLM 进行意图分类，失败时使用规则兜底。

    Example:
        >>> router = IntentRouter()
        >>> result = await router.classify("宝宝发烧怎么办")
        >>> print(result.intent)  # MEDICAL_QUERY
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None
    ):
        """
        初始化意图路由器

        Args:
            api_key: API 密钥
            base_url: API 基础 URL
            model: 使用的模型名称
        """
        self._api_key = api_key or settings.DEEPSEEK_API_KEY
        self._base_url = base_url or settings.DEEPSEEK_BASE_URL
        self._model = model or settings.DEEPSEEK_MODEL

        # 初始化客户端
        self._client: Optional[OpenAI] = None
        self._available = bool(self._api_key)

        # 规则匹配关键词
        self._greeting_keywords = [
            "你好", "您好", "嗨", "hi", "hello", "早上好", "晚上好",
            "哈喽", "在吗", "有人吗", "请问", "打扰了", "辛苦了"
        ]
        self._exit_keywords = [
            "再见", "拜拜", "bye", "88", "下次", "走了", "结束",
            "不用了", "没事了", "谢谢", "感谢", "好的知道了"
        ]
        self._medical_keywords = [
            "发烧", "发热", "咳嗽", "腹泻", "拉肚子", "呕吐", "吐奶",
            "皮疹", "湿疹", "摔倒", "跌倒", "撞到", "烫伤", "流鼻血",
            "感冒", "流鼻涕", "鼻塞", "打喷嚏", "喉咙", "肚子疼",
            "头疼", "头痛", "不舒服", "难受", "哭闹", "不吃奶",
            "不吃饭", "嗜睡", "精神差", "抽搐", "惊厥", "呼吸困难",
            "泰诺林", "美林", "退烧药", "用药", "吃药", "剂量",
            "体温", "度", "多少度", "几天", "多久", "怎么办",
            "怎么处理", "怎么护理", "需要就医吗", "去医院"
        ]

    def _get_client(self) -> OpenAI:
        """获取 OpenAI 客户端"""
        if self._client is None:
            self._client = OpenAI(
                api_key=self._api_key,
                base_url=self._base_url
            )
        return self._client

    async def classify(
        self,
        query: str,
        context: Optional[List[Dict[str, str]]] = None
    ) -> IntentResult:
        """
        分类用户意图

        Args:
            query: 用户输入
            context: 对话上下文

        Returns:
            IntentResult: 意图识别结果
        """
        start_time = time.time()

        # 1. 先尝试规则匹配（快速路径）
        rule_result = self._rule_based_classify(query)
        if rule_result.confidence >= 0.9:
            elapsed = (time.time() - start_time) * 1000
            logger.info(f"意图识别 (规则): {rule_result.intent.value}, elapsed={elapsed:.1f}ms")
            return rule_result

        # 2. 规则不确定时，调用 LLM
        if self._available:
            try:
                llm_result = await self._llm_classify(query, context)
                elapsed = (time.time() - start_time) * 1000
                logger.info(f"意图识别 (LLM): {llm_result.intent.value}, confidence={llm_result.confidence:.2f}, elapsed={elapsed:.1f}ms")
                return llm_result
            except Exception as e:
                logger.warning(f"LLM 意图识别失败，使用规则兜底: {e}")

        # 3. LLM 失败，返回规则结果或默认 MEDICAL_QUERY
        if rule_result.intent != Intent.UNKNOWN:
            return rule_result

        # 默认为医疗查询（宁可错查，不可漏查）
        return IntentResult(
            intent=Intent.MEDICAL_QUERY,
            confidence=0.5,
            entities={"fallback": True}
        )

    def _rule_based_classify(self, query: str) -> IntentResult:
        """
        基于规则的意图分类

        Args:
            query: 用户输入

        Returns:
            IntentResult: 分类结果
        """
        query_lower = query.lower().strip()

        # 空输入
        if not query_lower:
            return IntentResult(intent=Intent.UNKNOWN, confidence=0.5)

        # 检查打招呼
        for keyword in self._greeting_keywords:
            if keyword in query_lower and len(query) <= 20:
                return IntentResult(
                    intent=Intent.GREETING,
                    confidence=0.9
                )

        # 检查退出
        for keyword in self._exit_keywords:
            if keyword in query_lower and len(query) <= 15:
                return IntentResult(
                    intent=Intent.EXIT,
                    confidence=0.85
                )

        # 检查医疗关键词
        medical_matches = []
        for keyword in self._medical_keywords:
            if keyword in query_lower:
                medical_matches.append(keyword)

        if medical_matches:
            # 计算置信度：匹配的关键词数量
            confidence = min(0.9, 0.5 + len(medical_matches) * 0.1)
            return IntentResult(
                intent=Intent.MEDICAL_QUERY,
                confidence=confidence,
                detected_symptoms=medical_matches[:5]
            )

        # 检查是否为数据录入（包含数字或时间）
        has_number = bool(re.search(r'\d+', query))
        has_time = any(kw in query for kw in ["天", "小时", "分钟", "次", "度"])
        if has_number and has_time:
            return IntentResult(
                intent=Intent.DATA_ENTRY,
                confidence=0.7
            )

        # 无法识别
        return IntentResult(
            intent=Intent.UNKNOWN,
            confidence=0.3
        )

    async def _llm_classify(
        self,
        query: str,
        context: Optional[List[Dict[str, str]]] = None
    ) -> IntentResult:
        """
        使用 LLM 进行意图分类

        Args:
            query: 用户输入
            context: 对话上下文

        Returns:
            IntentResult: 分类结果
        """
        client = self._get_client()

        # 构建上下文
        context_str = ""
        if context:
            recent = context[-3:]  # 最近 3 轮对话
            context_str = "\n".join([
                f"{'用户' if msg.get('role') == 'user' else '助手'}: {msg.get('content', '')}"
                for msg in recent
            ])

        system_prompt = self._get_classifier_prompt()
        user_prompt = f"用户输入: {query}\n"
        if context_str:
            user_prompt += f"\n对话上下文:\n{context_str}\n"
        user_prompt += "\n请输出分类结果:"

        response = client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.0,  # 速度优先，低温度
            max_tokens=200,
            response_format={"type": "json_object"}
        )

        raw_content = response.choices[0].message.content

        # 解析 JSON
        try:
            data = json.loads(raw_content)
            intent_str = data.get("intent", "UNKNOWN").upper()

            # 转换为枚举
            try:
                intent = Intent[intent_str]
            except KeyError:
                intent = Intent.MEDICAL_QUERY  # 未知意图默认为医疗查询

            return IntentResult(
                intent=intent,
                confidence=float(data.get("confidence", 0.8)),
                detected_symptoms=data.get("detected_symptoms", []),
                entities=data.get("entities", {}),
                raw_response=raw_content
            )

        except json.JSONDecodeError:
            logger.warning(f"LLM 返回非 JSON 格式: {raw_content}")
            return IntentResult(
                intent=Intent.MEDICAL_QUERY,
                confidence=0.6,
                raw_response=raw_content
            )

    def _get_classifier_prompt(self) -> str:
        """获取分类器 Prompt"""
        return """你是一个儿科健康助手的意图分类器。你的任务是分析用户输入，判断用户的意图。

## 意图类型
- GREETING: 打招呼、闲聊、礼貌用语（如"你好"、"谢谢"、"在吗"）
- MEDICAL_QUERY: 医疗咨询、症状询问、护理建议（如"宝宝发烧怎么办"）
- DATA_ENTRY: 提供数据、更新信息（如"体温38.5度"、"已经发烧2天了"）
- EXIT: 结束对话、告别（如"再见"、"不用了"）
- UNKNOWN: 无法判断

## 输出格式
请输出 JSON 格式：
{
  "intent": "MEDICAL_QUERY",
  "confidence": 0.95,
  "detected_symptoms": ["发烧", "咳嗽"],
  "entities": {"temperature": "38.5", "duration": "2天"}
}

## 注意事项
1. 如果用户输入涉及任何健康、症状、护理相关内容，应归类为 MEDICAL_QUERY
2. 宁可错判为 MEDICAL_QUERY，也不要漏掉真正的医疗问题
3. confidence 范围 0-1，表示分类的确定程度
4. detected_symptoms 提取提到的症状关键词
5. entities 提取关键实体（如体温、时间、年龄等）"""

    def get_greeting_response(self) -> str:
        """获取问候回复"""
        greetings = [
            "您好！我是您的儿科健康助手 👶\n\n我可以帮您：\n• 评估宝宝的症状\n• 提供护理建议\n• 判断是否需要就医\n\n请描述宝宝的情况，我会尽力帮助您。",
            "您好！很高兴为您服务 😊\n\n请问宝宝有什么不舒服吗？您可以描述一下症状。",
            "您好！我是儿科健康助手。\n\n无论是发烧、咳嗽还是其他问题，我都可以帮您分析。请问宝宝怎么了？",
            "您好！请问有什么可以帮您的？\n\n您可以告诉我宝宝的月龄和症状，我会给出专业的建议。"
        ]
        import random
        return random.choice(greetings)

    def get_exit_response(self) -> str:
        """获取告别回复"""
        exits = [
            "好的，如果还有问题随时来问我。祝宝宝健康成长！ 🌟",
            "不客气！希望宝宝早日康复。有需要随时找我。",
            "好的，再见！祝您和宝宝都健康快乐！ 👋",
            "感谢您的信任！有任何育儿问题都可以来咨询。祝好！"
        ]
        import random
        return random.choice(exits)

    def get_unknown_response(self) -> str:
        """获取未知意图回复"""
        return "抱歉，我不太理解您的意思。请问宝宝有什么不舒服吗？比如发烧、咳嗽、腹泻等，您可以详细描述一下。"


# 创建全局实例
_intent_router: Optional[IntentRouter] = None


def get_intent_router() -> IntentRouter:
    """获取意图路由器单例"""
    global _intent_router
    if _intent_router is None:
        _intent_router = IntentRouter()
    return _intent_router
