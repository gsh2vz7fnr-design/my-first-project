"""
安全过滤服务 - 违禁词过滤与安全熔断
"""
import re
from typing import Tuple, Optional, List
from loguru import logger

from app.config import settings
from app.models.user import SafetyCheckResult


class SafetyFilter:
    """安全过滤器"""

    def __init__(self):
        """初始化"""
        self.general_blacklist = self._load_blacklist("general")
        self.medical_blacklist = self._load_blacklist("medical")

    def _load_blacklist(self, category: str) -> List[str]:
        """加载黑名单"""
        try:
            if category == "general":
                filepath = settings.GENERAL_BLACKLIST_FILE
            else:
                filepath = settings.MEDICAL_BLACKLIST_FILE

            with open(filepath, "r", encoding="utf-8") as f:
                return [line.strip() for line in f if line.strip() and not line.startswith("#")]
        except FileNotFoundError:
            logger.warning(f"{category}黑名单文件不存在，使用默认配置")
            return self._get_default_blacklist(category)

    def _get_default_blacklist(self, category: str) -> List[str]:
        """获取默认黑名单"""
        if category == "general":
            return [
                "炸弹", "自杀", "毒药", "色情", "赌博", "转账",
                "暴力", "恐怖", "政治", "敏感"
            ]
        else:  # medical
            return [
                # 禁药类
                "尼美舒利", "阿司匹林", "安乃近", "复方感冒药",
                # 伪科学类
                "排毒", "根治", "包治百病", "转胎药", "偏方",
                # 高风险操作
                "酒精擦身", "放血", "催吐", "灌肠",
                # 合规类
                "确诊是", "我保证", "肯定没问题", "一定能治好",
                # 处方药相关
                "开药", "开处方", "抗生素", "头孢", "阿莫西林"
            ]

    def filter_output(self, text: str) -> SafetyCheckResult:
        """
        过滤输出内容

        Args:
            text: 待检查的文本

        Returns:
            SafetyCheckResult: 安全检查结果
        """
        # 1. 检查通用红线
        matched_general = self._check_keywords(text, self.general_blacklist)
        if matched_general:
            return SafetyCheckResult(
                is_safe=False,
                matched_keywords=matched_general,
                category="general",
                fallback_message=(
                    "抱歉，我无法回答该问题。作为一个儿科健康助手，"
                    "我只专注于解答儿童护理与健康相关的咨询。"
                )
            )

        # 2. 检查医疗红线
        matched_medical = self._check_keywords(text, self.medical_blacklist)
        if matched_medical:
            return SafetyCheckResult(
                is_safe=False,
                matched_keywords=matched_medical,
                category="medical",
                fallback_message=(
                    "⚠️ 安全警示：基于安全风控原则，该回复已被系统拦截。\n\n"
                    "为了宝宝的安全，我们严禁推荐该类药物/疗法，或做出确诊性判断。\n"
                    "请您务必通过正规医院就诊，切勿轻信非专业建议。\n\n"
                    "如遇紧急情况，请立即拨打 120。"
                )
            )

        # 3. 通过检查
        return SafetyCheckResult(
            is_safe=True,
            matched_keywords=[],
            category=None,
            fallback_message=None
        )

    def _check_keywords(self, text: str, keywords: List[str]) -> List[str]:
        """
        检查文本中是否包含关键词

        Args:
            text: 文本
            keywords: 关键词列表

        Returns:
            List[str]: 匹配到的关键词
        """
        matched = []
        text_lower = text.lower()

        for keyword in keywords:
            # 使用正则表达式进行匹配，支持模糊匹配
            pattern = re.escape(keyword.lower())
            if re.search(pattern, text_lower):
                matched.append(keyword)

        return matched

    def check_prescription_intent(self, user_input: str) -> bool:
        """
        检查是否有处方意图

        Args:
            user_input: 用户输入

        Returns:
            bool: 是否有处方意图
        """
        prescription_keywords = [
            "开药", "开处方", "给我开", "帮我开",
            "抗生素", "头孢", "阿莫西林", "消炎药"
        ]

        return any(keyword in user_input for keyword in prescription_keywords)

    def get_prescription_refusal_message(self) -> str:
        """获取处方拒绝话术"""
        return (
            "抱歉，我只是AI助手，没有执业医师资格，无权开具处方药。\n\n"
            "抗生素（如头孢、阿莫西林）属于处方药，必须由医生根据验血结果开具。\n"
            "滥用抗生素可能导致耐药性，对宝宝健康有害。\n\n"
            "建议您：\n"
            "1. 前往医院就诊，由医生评估后开具处方\n"
            "2. 或使用线上互联网医院咨询真人医生\n\n"
            "*AI生成内容仅供参考，不作为医疗诊断依据。*"
        )

    def add_disclaimer(self, text: str) -> str:
        """
        添加免责声明水印

        Args:
            text: 原文本

        Returns:
            str: 添加水印后的文本
        """
        disclaimer = "\n\n*AI生成内容仅供参考，不作为医疗诊断依据。请以线下医生医嘱为准。*"

        # 如果文本已经包含免责声明，不重复添加
        if "*AI生成内容仅供参考" in text:
            return text

        return text + disclaimer


# 创建全局实例
safety_filter = SafetyFilter()
