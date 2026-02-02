"""
LLM服务模块
支持OpenAI和DeepSeek API
"""
import os
from typing import Dict, List, Optional
from openai import OpenAI


class LLMService:
    """LLM服务"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        api_base: Optional[str] = None,
        provider: str = "auto"
    ):
        """
        初始化LLM服务

        Args:
            api_key: API密钥（优先使用传入的，否则从环境变量读取）
            model: 使用的模型名称（如果不指定，根据provider自动选择）
            api_base: API基础URL（如果不指定，根据provider自动选择）
            provider: API提供商 ("openai", "deepseek", "auto")
                     "auto"会根据环境变量自动判断
        """
        # 自动检测provider
        if provider == "auto":
            if os.getenv("DEEPSEEK_API_KEY"):
                provider = "deepseek"
            elif os.getenv("OPENAI_API_KEY"):
                provider = "openai"
            else:
                provider = "deepseek"  # 默认使用DeepSeek

        self.provider = provider

        # 根据provider设置默认值
        if provider == "deepseek":
            self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
            self.model = model or os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
            self.api_base = api_base or "https://api.deepseek.com"
        else:  # openai
            self.api_key = api_key or os.getenv("OPENAI_API_KEY")
            self.model = model or os.getenv("OPENAI_MODEL", "gpt-4")
            self.api_base = api_base or "https://api.openai.com/v1"

        # 初始化客户端
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.api_base
        )

        print(f"✅ LLM服务初始化成功")
        print(f"   提供商: {self.provider}")
        print(f"   模型: {self.model}")
        print(f"   API地址: {self.api_base}")

        # 系统提示词
        self.system_prompt = """你是一个专业的AI育儿助手，专门帮助新手父母解答儿童健康护理问题。

【核心原则】
1. 你不能诊断疾病，只能提供护理建议和分诊指导
2. 所有回答必须基于提供的知识库内容
3. 保持温和、专业、有同理心的语气

【回复格式】
1. 先安抚情绪："我理解您的担心..."
2. 给出分诊建议（如适用）："根据您的描述，这种情况[需要/不需要]立即就医"
3. 提供护理知识：基于知识库的具体建议
4. 观察要点："如果出现[症状]，请及时就医"

【禁止事项】
- 禁止诊断疾病（不能说"您的宝宝得了XX病"）
- 禁止推荐具体药物剂量（只能说"请遵医嘱或参考说明书"）
- 禁止给出不在知识库中的建议

【免责声明】
每次回复结尾必须加上：
"💡 提醒：我是AI助手，以上建议仅供参考，不能代替专业医疗诊断。如有疑虑请咨询医生。"
"""

    def generate_response(
        self,
        user_query: str,
        context: str = "",
        intent: str = "daily_care"
    ) -> str:
        """
        生成回复

        Args:
            user_query: 用户查询
            context: RAG检索到的上下文
            intent: 用户意图

        Returns:
            生成的回复文本
        """
        # 构建用户消息
        user_message = f"""用户问题：{user_query}

意图类型：{intent}

相关知识库内容：
{context if context else "（无相关知识库内容）"}

请基于以上信息，为用户提供专业、温和的回复。"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.7,
                max_tokens=800
            )

            return response.choices[0].message.content

        except Exception as e:
            return f"抱歉，生成回复时出现错误：{str(e)}"

    def generate_triage_response(
        self,
        user_query: str,
        context: str = ""
    ) -> str:
        """
        生成分诊回复（更严格的提示词）

        Args:
            user_query: 用户查询
            context: RAG检索到的上下文

        Returns:
            生成的回复文本
        """
        triage_prompt = """你是一个专业的AI分诊助手。

【核心任务】
判断用户描述的情况是否需要就医，并给出明确的行动建议。

【回复格式】
1. 情况评估："根据您的描述..."
2. 分诊建议：
   - 如果需要就医："建议您尽快带宝宝就医"
   - 如果可以观察："目前可以在家观察，注意以下事项..."
3. 观察要点："如果出现以下情况，请立即就医：..."
4. 免责声明

【严格要求】
- 不能诊断疾病
- 对于不确定的情况，倾向于建议就医
- 必须列出需要警惕的危险信号
"""

        user_message = f"""用户问题：{user_query}

相关医学知识：
{context if context else "（无相关知识库内容）"}

请为用户提供分诊建议。"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": triage_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.5,  # 分诊场景使用更低的温度
                max_tokens=600
            )

            return response.choices[0].message.content

        except Exception as e:
            return f"抱歉，生成回复时出现错误：{str(e)}"


# 测试代码
if __name__ == "__main__":
    # 需要设置环境变量 DEEPSEEK_API_KEY 或 OPENAI_API_KEY
    service = LLMService()

    # 测试日常护理问答
    query = "宝宝便秘了怎么办？"
    context = "婴儿便秘的处理：可以尝试增加水分摄入，给予西梅泥、梨泥等富含纤维的食物。"

    print("\n测试日常护理问答：")
    print(f"问题：{query}\n")
    response = service.generate_response(query, context, "daily_care")
    print(f"回复：\n{response}")
