"""
意图识别路由单元测试

测试内容：
1. 规则匹配测试
2. LLM 分类测试
3. 响应生成测试
"""
import pytest
import asyncio
from unittest.mock import MagicMock, patch

from app.services.intent_router import (
    IntentRouter,
    Intent,
    IntentResult
)


class TestIntentRouter:
    """意图路由器测试"""

    @pytest.fixture
    def router(self):
        """创建路由器实例"""
        return IntentRouter()

    # ============ 规则匹配测试 ============

    def test_greeting_keywords(self, router):
        """测试打招呼关键词"""
        test_cases = [
            "你好",
            "您好",
            "hi",
            "hello",
            "在吗",
        ]

        for query in test_cases:
            result = router._rule_based_classify(query)  # 同步方法
            assert result.intent == Intent.GREETING, f"Failed for: {query}"

    def test_exit_keywords(self, router):
        """测试告别关键词"""
        test_cases = [
            "再见",
            "拜拜",
            "bye",
            "谢谢",
        ]

        for query in test_cases:
            result = router._rule_based_classify(query)  # 同步方法
            assert result.intent == Intent.EXIT, f"Failed for: {query}"

    def test_medical_keywords(self, router):
        """测试医疗关键词"""
        test_cases = [
            ("宝宝发烧怎么办", Intent.MEDICAL_QUERY),
            ("咳嗽有痰", Intent.MEDICAL_QUERY),
            ("腹泻怎么护理", Intent.MEDICAL_QUERY),
            ("泰诺林用量", Intent.MEDICAL_QUERY),
        ]

        for query, expected in test_cases:
            result = router._rule_based_classify(query)  # 同步方法
            assert result.intent == expected, f"Failed for: {query}"

    def test_data_entry_detection(self, router):
        """测试数据录入检测"""
        test_cases = [
            "已经发烧2天了",
            "体温38.5度",
            "一天拉了5次",
        ]

        for query in test_cases:
            result = router._rule_based_classify(query)  # 同步方法
            # 数据录入或有医疗关键词都是合理的分类
            assert result.intent in (Intent.DATA_ENTRY, Intent.MEDICAL_QUERY), \
                f"Failed for: {query}, got {result.intent}"

    def test_empty_query(self, router):
        """测试空输入"""
        result = router._rule_based_classify("")  # 同步方法
        assert result.intent == Intent.UNKNOWN

    # ============ 响应生成测试 ============

    def test_get_greeting_response(self, router):
        """测试问候响应"""
        response = router.get_greeting_response()
        assert len(response) > 0
        # 应该包含友好问候或服务相关词汇
        assert any(kw in response for kw in ["儿科", "助手", "宝宝", "帮您", "您好", "症状"])

    def test_get_exit_response(self, router):
        """测试告别响应"""
        response = router.get_exit_response()
        assert len(response) > 0
        # 应该包含祝福或告别
        assert any(kw in response for kw in ["祝", "再见", "健康", "快乐"])

    def test_get_unknown_response(self, router):
        """测试未知意图响应"""
        response = router.get_unknown_response()
        assert len(response) > 0
        # 应该引导用户
        assert "描述" in response or "请问" in response

    # ============ IntentResult 测试 ============

    def test_intent_result_is_medical(self):
        """测试 is_medical 方法"""
        medical_intents = [Intent.MEDICAL_QUERY, Intent.DATA_ENTRY, Intent.UNKNOWN]
        non_medical_intents = [Intent.GREETING, Intent.EXIT]

        for intent in medical_intents:
            result = IntentResult(intent=intent)
            assert result.is_medical() is True, f"Failed for: {intent}"

        for intent in non_medical_intents:
            result = IntentResult(intent=intent)
            assert result.is_medical() is False, f"Failed for: {intent}"

    def test_intent_result_is_simple_response(self):
        """测试 is_simple_response 方法"""
        simple_intents = [Intent.GREETING, Intent.EXIT]
        complex_intents = [Intent.MEDICAL_QUERY, Intent.DATA_ENTRY, Intent.UNKNOWN]

        for intent in simple_intents:
            result = IntentResult(intent=intent)
            assert result.is_simple_response() is True, f"Failed for: {intent}"

        for intent in complex_intents:
            result = IntentResult(intent=intent)
            assert result.is_simple_response() is False, f"Failed for: {intent}"

    # ============ 集成测试 ============

    @pytest.mark.asyncio
    async def test_classify_with_rules(self, router):
        """测试规则分类（不调用 LLM）"""
        # 规则匹配置信度高时，不会调用 LLM
        result = await router.classify("你好")
        assert result.intent == Intent.GREETING
        assert result.confidence >= 0.9

    @pytest.mark.asyncio
    async def test_classify_fallback_to_medical(self, router):
        """测试默认回退到医疗查询"""
        # 模糊输入应该默认为医疗查询
        result = await router.classify("宝宝好像有点不舒服")
        # 应该是医疗查询或未知（都会触发检索）
        assert result.is_medical() is True


class TestIntentEnum:
    """意图枚举测试"""

    def test_intent_values(self):
        """测试枚举值"""
        assert Intent.GREETING.value == "GREETING"
        assert Intent.MEDICAL_QUERY.value == "MEDICAL_QUERY"
        assert Intent.DATA_ENTRY.value == "DATA_ENTRY"
        assert Intent.EXIT.value == "EXIT"
        assert Intent.UNKNOWN.value == "UNKNOWN"

    def test_intent_string_conversion(self):
        """测试字符串转换"""
        assert str(Intent.GREETING) == "Intent.GREETING"
        assert Intent.MEDICAL_QUERY.value == "MEDICAL_QUERY"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
