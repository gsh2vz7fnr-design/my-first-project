"""
分类器 Prompt 模板

包含意图分类、实体提取等 Prompt 模板。
"""
from typing import Optional

CLASSIFIER_SYSTEM_PROMPT = """你是一个儿科健康助手的意图分类器。你的任务是分析用户输入，判断用户的意图。

## 意图类型
- GREETING: 打招呼、闲聊、礼貌用语（如"你好"、"谢谢"、"在吗"）
- MEDICAL_QUERY: 医疗咨询、症状询问、护理建议（如"宝宝发烧怎么办"）
- DATA_ENTRY: 提供数据、更新信息（如"体温38.5度"、"已经发烧2天了"）
- EXIT: 结束对话、告别（如"再见"、"不用了"）
- UNKNOWN: 无法判断

## 输出格式
请严格输出以下 JSON 格式，不要包含任何其他内容：
```json
{
  "intent": "MEDICAL_QUERY",
  "confidence": 0.95,
  "detected_symptoms": ["发烧", "咳嗽"],
  "entities": {
    "temperature": "38.5",
    "duration": "2天",
    "age": "8个月"
  }
}
```

## 字段说明
- intent: 必须是上述意图类型之一
- confidence: 0-1 之间的浮点数，表示分类的确定程度
- detected_symptoms: 提取的症状关键词列表
- entities: 提取的实体，可能包含：
  - temperature: 体温
  - duration: 持续时间
  - age: 年龄/月龄
  - frequency: 频率/次数
  - symptom: 主要症状

## 分类原则
1. **安全第一**: 如果用户输入涉及任何健康、症状、护理相关内容，应归类为 MEDICAL_QUERY
2. **宁可错判**: 宁可错判为 MEDICAL_QUERY，也不要漏掉真正的医疗问题
3. **简短判断**: 如果用户输入很短（<5字）且是礼貌用语，归类为 GREETING
4. **明确告别**: 如果用户明确表示结束，归类为 EXIT
5. **数据优先**: 如果用户在提供数据（体温、时间等），归类为 DATA_ENTRY

## 示例

用户: "你好"
输出: {"intent": "GREETING", "confidence": 0.95, "detected_symptoms": [], "entities": {}}

用户: "宝宝发烧38.5度怎么办"
输出: {"intent": "MEDICAL_QUERY", "confidence": 0.98, "detected_symptoms": ["发烧"], "entities": {"temperature": "38.5"}}

用户: "已经发烧2天了"
输出: {"intent": "DATA_ENTRY", "confidence": 0.85, "detected_symptoms": ["发烧"], "entities": {"duration": "2天", "symptom": "发烧"}}

用户: "谢谢再见"
输出: {"intent": "EXIT", "confidence": 0.9, "detected_symptoms": [], "entities": {}}

用户: "3个月宝宝"
输出: {"intent": "DATA_ENTRY", "confidence": 0.8, "detected_symptoms": [], "entities": {"age": "3个月"}}
"""

CLASSIFIER_USER_PROMPT_TEMPLATE = """请分析以下用户输入，输出意图分类结果。

用户输入: {query}

{context_section}

请输出分类结果（仅 JSON）:"""

CONTEXT_SECTION_TEMPLATE = """
对话上下文（最近的对话）:
{context}
"""

# 症状关键词列表（用于辅助识别）
SYMPTOM_KEYWORDS = [
    # 体温相关
    "发烧", "发热", "体温", "高温", "低烧", "高烧",
    # 呼吸系统
    "咳嗽", "咳痰", "流鼻涕", "鼻塞", "打喷嚏", "喉咙痛", "气喘", "呼吸困难",
    # 消化系统
    "腹泻", "拉肚子", "呕吐", "吐奶", "便秘", "腹胀", "肚子疼", "厌食",
    # 皮肤
    "皮疹", "湿疹", "红疹", "荨麻疹", "痱子", "尿布疹",
    # 神经系统
    "惊厥", "抽搐", "嗜睡", "烦躁", "哭闹",
    # 外伤
    "摔倒", "跌倒", "撞到", "烫伤", "烧伤", "割伤", "骨折",
    # 其他
    "黄疸", "贫血", "过敏", "脱水", "营养不良"
]

# 打招呼关键词
GREETING_KEYWORDS = [
    "你好", "您好", "嗨", "hi", "hello", "哈喽",
    "早上好", "下午好", "晚上好",
    "在吗", "有人吗", "请问", "咨询",
    "打扰了", "不好意思", "麻烦"
]

# 告别关键词
EXIT_KEYWORDS = [
    "再见", "拜拜", "bye", "88", "下次见",
    "走了", "结束", "不用了", "没事了",
    "谢谢", "感谢", "好的知道了", "明白了"
]


def build_classifier_prompt(query: str, context: Optional[str] = None) -> str:
    """
    构建分类器 Prompt

    Args:
        query: 用户输入
        context: 对话上下文

    Returns:
        str: 构建好的 Prompt
    """
    context_section = ""
    if context:
        context_section = CONTEXT_SECTION_TEMPLATE.format(context=context)

    return CLASSIFIER_USER_PROMPT_TEMPLATE.format(
        query=query,
        context_section=context_section
    )
