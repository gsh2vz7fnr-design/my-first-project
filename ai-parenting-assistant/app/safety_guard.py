"""
安全护栏模块
对LLM生成的内容进行安全检查
"""
import re
from typing import Dict, Optional


class SafetyGuard:
    """安全护栏"""

    def __init__(self):
        # 禁止的诊断性词汇
        self.diagnosis_keywords = [
            "诊断为", "确诊", "得了", "患有", "是XX病",
            "肯定是", "一定是"
        ]

        # 禁止的剂量相关词汇
        self.dosage_keywords = [
            "吃.*毫升", "服用.*毫克", "用.*克",
            r"\d+ml", r"\d+mg", r"\d+g"
        ]

        # 必须包含的免责声明关键词
        self.disclaimer_keywords = [
            "AI助手", "仅供参考", "不能代替", "医疗诊断"
        ]

    def check_response(self, response: str) -> Dict:
        """
        检查回复是否安全

        Args:
            response: LLM生成的回复

        Returns:
            检查结果字典
        """
        issues = []

        # 检查是否包含诊断性语言
        for keyword in self.diagnosis_keywords:
            if keyword in response:
                issues.append({
                    "type": "diagnosis",
                    "keyword": keyword,
                    "severity": "high",
                    "message": f"回复中包含诊断性语言：{keyword}"
                })

        # 检查是否包含具体剂量
        for pattern in self.dosage_keywords:
            if re.search(pattern, response):
                issues.append({
                    "type": "dosage",
                    "pattern": pattern,
                    "severity": "high",
                    "message": f"回复中包含具体剂量信息"
                })

        # 检查是否包含免责声明
        has_disclaimer = any(
            keyword in response
            for keyword in self.disclaimer_keywords
        )

        if not has_disclaimer:
            issues.append({
                "type": "missing_disclaimer",
                "severity": "medium",
                "message": "回复中缺少免责声明"
            })

        return {
            "is_safe": len([i for i in issues if i["severity"] == "high"]) == 0,
            "issues": issues,
            "response": response
        }

    def add_disclaimer(self, response: str) -> str:
        """
        为回复添加免责声明（如果缺失）

        Args:
            response: 原始回复

        Returns:
            添加免责声明后的回复
        """
        disclaimer = "\n\n💡 提醒：我是AI助手，以上建议仅供参考，不能代替专业医疗诊断。如有疑虑请咨询医生。"

        # 检查是否已有免责声明
        has_disclaimer = any(
            keyword in response
            for keyword in self.disclaimer_keywords
        )

        if not has_disclaimer:
            return response + disclaimer

        return response

    def sanitize_response(self, response: str) -> str:
        """
        清理回复中的不安全内容

        Args:
            response: 原始回复

        Returns:
            清理后的回复
        """
        # 移除诊断性语言（简单替换）
        for keyword in self.diagnosis_keywords:
            if keyword in response:
                response = response.replace(
                    keyword,
                    "可能是"
                )

        # 添加免责声明
        response = self.add_disclaimer(response)

        return response


# 测试代码
if __name__ == "__main__":
    guard = SafetyGuard()

    # 测试用例
    test_responses = [
        "根据您的描述，宝宝诊断为湿疹。建议使用保湿霜。",
        "宝宝发烧可以服用5ml美林。",
        "这种情况可能是便秘，建议增加水分摄入。",
        "建议观察，如有异常请就医。💡 提醒：我是AI助手，以上建议仅供参考。"
    ]

    for i, response in enumerate(test_responses, 1):
        print(f"\n测试用例 {i}:")
        print(f"原始回复: {response}")

        result = guard.check_response(response)
        print(f"是否安全: {result['is_safe']}")

        if result['issues']:
            print("发现的问题:")
            for issue in result['issues']:
                print(f"  - {issue['message']} (严重程度: {issue['severity']})")

        sanitized = guard.sanitize_response(response)
        print(f"清理后: {sanitized}")
