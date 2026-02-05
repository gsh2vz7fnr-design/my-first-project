"""
大模型服务 - 通义千问API调用
"""
import json
from typing import Dict, Any, Optional, AsyncGenerator
from loguru import logger
import dashscope
from dashscope import Generation

from app.config import settings
from app.models.user import IntentAndEntities, Intent


class LLMService:
    """大模型服务"""

    def __init__(self):
        """初始化"""
        dashscope.api_key = settings.QWEN_API_KEY
        self.model = settings.QWEN_MODEL

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

        try:
            # 调用通义千问API
            response = Generation.call(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                result_format="message",
                temperature=0.1,  # 低温度，确保稳定输出
            )

            if response.status_code == 200:
                # 解析响应
                content = response.output.choices[0].message.content
                result = json.loads(content)

                return IntentAndEntities(
                    intent=Intent(
                        type=result.get("intent", "consult"),
                        confidence=result.get("intent_confidence", 0.8)
                    ),
                    entities=result.get("entities", {})
                )
            else:
                logger.error(f"通义千问API调用失败: {response}")
                # 返回默认值
                return IntentAndEntities(
                    intent=Intent(type="consult", confidence=0.5),
                    entities={}
                )

        except Exception as e:
            logger.error(f"意图提取失败: {e}", exc_info=True)
            return IntentAndEntities(
                intent=Intent(type="consult", confidence=0.5),
                entities={}
            )

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
        try:
            # 调用通义千问流式API
            responses = Generation.call(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._build_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                result_format="message",
                stream=True,
                incremental_output=True,
                temperature=0.7,
            )

            for response in responses:
                if response.status_code == 200:
                    content = response.output.choices[0].message.content
                    yield content
                else:
                    logger.error(f"流式生成失败: {response}")
                    break

        except Exception as e:
            logger.error(f"流式生成异常: {e}", exc_info=True)
            yield "抱歉，系统出现异常，请稍后重试。"

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
