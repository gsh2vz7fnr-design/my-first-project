"""分诊引擎单元测试"""
import pytest
from app.services.triage_engine import TriageEngine


class TestMakeTriageDecision:
    """P0-1: 验证规则引擎路径生效"""
    def setup_method(self):
        self.engine = TriageEngine()

    def test_rule_engine_is_active(self):
        """TC-TE-001: 3个月以下发烧 -> emergency"""
        entities = {"symptom": "发烧", "age_months": 2, "temperature": "38度"}
        decision = self.engine.make_triage_decision("发烧", entities)
        assert decision.level == "emergency"

    def test_duration_hours_preprocessing(self):
        """TC-TE-002: duration=3天 应计算为72小时，触发就医"""
        entities = {"symptom": "发烧", "age_months": 12,
                    "temperature": "38.5度", "duration": "3天", "mental_state": "正常"}
        decision = self.engine.make_triage_decision("发烧", entities)
        assert decision.level == "emergency"

    def test_fallback_for_unknown_symptom(self):
        """TC-TE-003: 未知症状 -> observe"""
        decision = self.engine.make_triage_decision("头痛", {"symptom": "头痛"})
        assert decision.level == "observe"


class TestFeverTemperatureComparison:
    """P0-2: 验证温度数值比较"""
    def setup_method(self):
        self.engine = TriageEngine()

    def test_40_degrees_triggers_emergency(self):
        """TC-TE-004: 40度+萎靡 -> emergency（旧代码漏判）"""
        entities = {"symptom": "发烧", "age_months": 12,
                    "temperature": "40度", "mental_state": "精神萎靡"}
        assert self.engine._triage_fever(entities).level == "emergency"

    def test_39_5_triggers_emergency(self):
        """TC-TE-005: 39.5度+萎靡 -> emergency"""
        entities = {"symptom": "发烧", "age_months": 12,
                    "temperature": "39.5℃", "mental_state": "精神萎靡"}
        assert self.engine._triage_fever(entities).level == "emergency"

    def test_38_9_no_false_positive(self):
        """TC-TE-006: 38.9度+萎靡 -> 不触发高热emergency"""
        entities = {"symptom": "发烧", "age_months": 12,
                    "temperature": "38.9度", "mental_state": "精神萎靡"}
        result = self.engine._triage_fever(entities)
        assert result.level != "emergency" or "高热" not in result.reason

    def test_exactly_39(self):
        """TC-TE-007: 恰好39度+萎靡 -> emergency"""
        entities = {"symptom": "发烧", "age_months": 12,
                    "temperature": "39度", "mental_state": "精神萎靡"}
        assert self.engine._triage_fever(entities).level == "emergency"


class TestDurationHours:
    """P1-3: 验证分钟单位"""
    def setup_method(self):
        self.engine = TriageEngine()

    def test_minutes(self):
        """TC-TE-008: 30分钟 -> 0.5h"""
        assert self.engine._duration_hours("30分钟") == pytest.approx(0.5)

    def test_hours(self):
        """TC-TE-009: 2小时 -> 2.0h"""
        assert self.engine._duration_hours("2小时") == pytest.approx(2.0)

    def test_days(self):
        """TC-TE-010: 3天 -> 72.0h"""
        assert self.engine._duration_hours("3天") == pytest.approx(72.0)

    def test_unknown_unit(self):
        """TC-TE-011: 5周 -> 0.0"""
        assert self.engine._duration_hours("5周") == pytest.approx(0.0)

    def test_no_number(self):
        """TC-TE-012: 很久了 -> 0.0"""
        assert self.engine._duration_hours("很久了") == pytest.approx(0.0)


class TestToNumberChinese:
    """Bug #3: 修复 _to_number() 中文数字解析"""
    def setup_method(self):
        self.engine = TriageEngine()

    def test_to_number_chinese_36(self):
        """TC-TE-NUM-01: '三十六个月' 应解析为 36"""
        assert self.engine._to_number("三十六个月") == 36.0

    def test_to_number_chinese_12(self):
        """TC-TE-NUM-02: '十二个月' 应解析为 12"""
        assert self.engine._to_number("十二个月") == 12.0

    def test_to_number_chinese_10(self):
        """TC-TE-NUM-03: '十个月' 应解析为 10"""
        assert self.engine._to_number("十个月") == 10.0

    def test_to_number_chinese_23(self):
        """TC-TE-NUM-04: '二十三个月' 应解析为 23"""
        assert self.engine._to_number("二十三个月") == 23.0

    def test_to_number_chinese_15(self):
        """TC-TE-NUM-05: '十五个月' 应解析为 15"""
        assert self.engine._to_number("十五个月") == 15.0

    def test_to_number_arabic(self):
        """TC-TE-NUM-06: '2个月' 应解析为 2"""
        assert self.engine._to_number("2个月") == 2.0

    def test_to_number_none(self):
        """TC-TE-NUM-07: None 输入应返回 None"""
        assert self.engine._to_number(None) is None

    def test_to_number_simple_chinese(self):
        """TC-TE-NUM-08: '三个月' 应解析为 3"""
        assert self.engine._to_number("三个月") == 3.0

    def test_to_number_fourteen(self):
        """TC-TE-NUM-09: '十四个月' 应解析为 14"""
        assert self.engine._to_number("十四个月") == 14.0
