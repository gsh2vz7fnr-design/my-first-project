"""
危险信号检测模块
基于规则引擎，识别需要立即就医的紧急情况
"""
import json
from typing import Dict, List, Optional
from pathlib import Path


class DangerDetector:
    """危险信号检测器"""

    def __init__(self, rules_path: str = "data/danger_signals.json"):
        """初始化检测器，加载规则"""
        self.rules = self._load_rules(rules_path)

    def _load_rules(self, rules_path: str) -> List[Dict]:
        """加载危险信号规则"""
        path = Path(rules_path)
        if not path.exists():
            return []

        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def detect(self, user_input: str) -> Optional[Dict]:
        """
        检测用户输入是否包含危险信号

        Args:
            user_input: 用户输入的文本

        Returns:
            如果检测到危险信号，返回包含警告信息的字典；否则返回None
        """
        user_input_lower = user_input.lower()

        for category_rule in self.rules:
            category = category_rule["category"]

            for signal in category_rule["signals"]:
                # 检查是否包含关键词
                keyword_matched = any(
                    keyword in user_input_lower
                    for keyword in signal["keywords"]
                )

                if not keyword_matched:
                    continue

                # 检查是否包含危险条件
                danger_matched = any(
                    condition in user_input_lower
                    for condition in signal["danger_conditions"]
                )

                if danger_matched:
                    return {
                        "is_danger": True,
                        "category": category,
                        "action": signal["action"],
                        "reason": signal["reason"],
                        "matched_conditions": [
                            cond for cond in signal["danger_conditions"]
                            if cond in user_input_lower
                        ]
                    }

        return None

    def format_danger_response(self, danger_info: Dict) -> str:
        """格式化危险信号响应"""
        response = f"""
⚠️ 【紧急提醒】

根据您的描述，宝宝可能存在以下危险信号：
{', '.join(danger_info['matched_conditions'])}

🚨 建议：{danger_info['action']}

原因：{danger_info['reason']}

⏰ 如果情况紧急，请不要犹豫，立即采取行动。

💡 免责声明：我是AI助手，以上建议仅供参考。在紧急情况下，请优先遵从医疗专业人员的指导。
"""
        return response.strip()


# 测试代码
if __name__ == "__main__":
    detector = DangerDetector()

    # 测试用例
    test_cases = [
        "宝宝发烧39.5度，精神很差，一直在睡觉",
        "宝宝从床上摔下来了，后脑勺着地，现在在呕吐",
        "宝宝有点咳嗽，流鼻涕",
        "宝宝呼吸很急促，嘴唇有点发紫"
    ]

    for case in test_cases:
        print(f"\n输入: {case}")
        result = detector.detect(case)
        if result:
            print(detector.format_danger_response(result))
        else:
            print("未检测到危险信号")
