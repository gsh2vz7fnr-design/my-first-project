"""
意图路由模块
识别用户意图：紧急分诊 / 日常护理 / 用药咨询
"""
from enum import Enum
from typing import Dict


class IntentType(Enum):
    """意图类型"""
    EMERGENCY_TRIAGE = "emergency_triage"  # 紧急分诊
    DAILY_CARE = "daily_care"              # 日常护理
    MEDICATION = "medication"              # 用药咨询
    UNKNOWN = "unknown"                    # 未知


class IntentRouter:
    """意图路由器 - 基于关键词匹配的简单实现"""

    def __init__(self):
        # 定义各类意图的关键词
        self.intent_keywords = {
            IntentType.EMERGENCY_TRIAGE: [
                "发烧", "发热", "高烧", "摔", "撞", "呕吐", "抽搐",
                "呼吸困难", "喘", "憋", "脱水", "惊厥", "意识不清",
                "嗜睡", "精神差", "急", "紧急", "严重", "要不要去医院",
                "需要就医吗", "要去急诊吗"
            ],
            IntentType.MEDICATION: [
                "药", "美林", "泰诺林", "布洛芬", "对乙酰氨基酚",
                "剂量", "用量", "吃多少", "怎么吃", "能一起吃吗",
                "间隔", "副作用", "药品", "用药"
            ],
            IntentType.DAILY_CARE: [
                "护理", "喂养", "辅食", "便秘", "湿疹", "尿布疹",
                "红点", "皮疹", "咳嗽", "流鼻涕", "鼻塞", "睡眠",
                "哭闹", "吐奶", "拉肚子", "腹泻", "怎么办", "正常吗",
                "米粉", "奶粉", "母乳", "断奶"
            ]
        }

    def route(self, user_input: str) -> Dict:
        """
        路由用户输入到对应的意图

        Args:
            user_input: 用户输入文本

        Returns:
            包含意图类型和置信度的字典
        """
        user_input_lower = user_input.lower()

        # 计算每个意图的匹配分数
        scores = {}
        for intent_type, keywords in self.intent_keywords.items():
            score = sum(1 for keyword in keywords if keyword in user_input_lower)
            scores[intent_type] = score

        # 找到最高分的意图
        max_score = max(scores.values())

        if max_score == 0:
            return {
                "intent": IntentType.UNKNOWN,
                "confidence": 0.0,
                "description": "无法识别意图"
            }

        # 找到得分最高的意图
        best_intent = max(scores.items(), key=lambda x: x[1])[0]

        # 计算置信度（简单归一化）
        confidence = min(max_score / 3.0, 1.0)  # 匹配3个关键词即为高置信度

        return {
            "intent": best_intent,
            "confidence": confidence,
            "description": self._get_intent_description(best_intent)
        }

    def _get_intent_description(self, intent: IntentType) -> str:
        """获取意图描述"""
        descriptions = {
            IntentType.EMERGENCY_TRIAGE: "紧急分诊 - 判断是否需要就医",
            IntentType.MEDICATION: "用药咨询 - 药品使用指导",
            IntentType.DAILY_CARE: "日常护理 - 育儿护理建议",
            IntentType.UNKNOWN: "未知意图"
        }
        return descriptions.get(intent, "未知")


# 测试代码
if __name__ == "__main__":
    router = IntentRouter()

    test_cases = [
        "宝宝发烧39度，要不要去医院？",
        "美林和泰诺林能一起吃吗？",
        "宝宝便秘了，吃什么能排便？",
        "宝宝今天很开心"
    ]

    for case in test_cases:
        print(f"\n输入: {case}")
        result = router.route(case)
        print(f"意图: {result['intent'].value}")
        print(f"置信度: {result['confidence']:.2f}")
        print(f"描述: {result['description']}")
