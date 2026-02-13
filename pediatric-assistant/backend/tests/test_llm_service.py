"""LLM服务单元测试"""
import pytest
import time
from app.services.llm_service import LLMService


class TestRemoteAvailabilityCooldown:
    """P0-3: 验证冷却恢复机制"""
    def setup_method(self):
        self.service = LLMService()

    def test_disabled_after_error(self):
        """TC-LLM-001: 设 False 后暂时不可用"""
        self.service.remote_available = False
        assert self.service.remote_available is False

    def test_recovers_after_cooldown(self):
        """TC-LLM-002: 冷却期过后自动恢复"""
        self.service.remote_available = False
        self.service._remote_cooldown_until = time.time() - 1
        if self.service._api_key_configured:
            assert self.service.remote_available is True

    def test_stays_available_on_success(self):
        """TC-LLM-003: 未出错时保持可用"""
        self.service._remote_cooldown_until = 0.0
        self.service._api_key_configured = True
        assert self.service.remote_available is True


class TestPostprocessEntities:
    """P1-2: 验证呕吐不被重复添加"""
    def setup_method(self):
        self.service = LLMService()

    def test_vomit_not_duplicated_as_main(self):
        """TC-LLM-004: 主症状为呕吐时不加入伴随症状"""
        entities = {"symptom": "呕吐"}
        result = self.service._postprocess_entities("宝宝呕吐了", entities)
        assert "呕吐" not in result.get("accompanying_symptoms", "")

    def test_vomit_added_when_not_main(self):
        """TC-LLM-005: 主症状为发烧时呕吐加入伴随症状"""
        entities = {"symptom": "发烧"}
        result = self.service._postprocess_entities("宝宝发烧还吐了", entities)
        assert "呕吐" in result.get("accompanying_symptoms", "")

    def test_vomit_not_duplicated_in_existing(self):
        """TC-LLM-006: 伴随症状已有呕吐时不重复"""
        entities = {"symptom": "发烧", "accompanying_symptoms": "呕吐"}
        result = self.service._postprocess_entities("宝宝发烧还吐了", entities)
        assert result.get("accompanying_symptoms", "").count("呕吐") <= 2


class TestAccompanyingSymptomsDuplicates:
    """Bug #2: 修复伴随症状重复问题"""
    def setup_method(self):
        self.service = LLMService()

    def test_accompanying_symptoms_no_duplicates(self):
        """TC-LLM-DUP-01: 当用户输入包含'呕吐'且已在伴随症状中时，不应重复添加"""
        result = self.service._extract_intent_and_entities_fallback("宝宝发烧39度，还呕吐了")
        symptoms = result.entities.get("accompanying_symptoms", "")
        # "呕吐" 应该只出现一次
        assert symptoms.count("呕吐") == 1, f"呕吐出现 {symptoms.count('呕吐')} 次，内容: {symptoms}"

    def test_blood_symptom_no_duplicates(self):
        """TC-LLM-DUP-02: 当用户输入包含'有血'且已在伴随症状中时，不应重复添加"""
        result = self.service._extract_intent_and_entities_fallback("宝宝腹泻，大便有血")
        symptoms = result.entities.get("accompanying_symptoms", "")
        assert symptoms.count("有血") <= 1, f"有血出现 {symptoms.count('有血')} 次，内容: {symptoms}"
        assert symptoms.count("带血") <= 1, f"带血出现 {symptoms.count('带血')} 次，内容: {symptoms}"

    def test_vomit_with_multiple_symptoms(self):
        """TC-LLM-DUP-03: 多个伴随症状时呕吐不应重复"""
        result = self.service._extract_intent_and_entities_fallback("宝宝发烧咳嗽，还呕吐了")
        symptoms = result.entities.get("accompanying_symptoms", "")
        assert symptoms.count("呕吐") == 1, f"呕吐出现 {symptoms.count('呕吐')} 次，内容: {symptoms}"
        # 咳嗽也应该只出现一次
        assert symptoms.count("咳嗽") == 1, f"咳嗽出现 {symptoms.count('咳嗽')} 次，内容: {symptoms}"


class TestFastPathExtraction:
    """P7: 优化简单输入的响应速度，避免不必要的 LLM 调用"""
    def setup_method(self):
        self.service = LLMService()

    def test_fast_path_simple_duration(self):
        """TC-LLM-FAST-01: 快速路径识别'半天'"""
        result = self.service._try_fast_path_extraction("半天")
        assert result is not None
        assert result["intent"] == "slot_filling"
        assert result["entities"]["duration"] == "半天"
        assert result["intent_confidence"] >= 0.9

    def test_fast_path_numeric_days(self):
        """TC-LLM-FAST-02: 快速路径识别'3天'"""
        result = self.service._try_fast_path_extraction("3天")
        assert result is not None
        assert result["intent"] == "slot_filling"
        assert result["entities"]["duration"] == "3天"

    def test_fast_path_chinese_numbers(self):
        """TC-LLM-FAST-03: 快速路径识别'五天'"""
        result = self.service._try_fast_path_extraction("五天")
        assert result is not None
        assert result["intent"] == "slot_filling"
        assert result["entities"]["duration"] == "五天"

    def test_fast_path_hours(self):
        """TC-LLM-FAST-04: 快速路径识别'2小时'"""
        result = self.service._try_fast_path_extraction("2小时")
        assert result is not None
        assert result["intent"] == "slot_filling"
        assert result["entities"]["duration"] == "2小时"

    def test_fast_path_weeks(self):
        """TC-LLM-FAST-05: 快速路径识别'一周'"""
        result = self.service._try_fast_path_extraction("一周")
        assert result is not None
        assert result["intent"] == "slot_filling"
        assert result["entities"]["duration"] == "一周"

    def test_fast_path_pure_number(self):
        """TC-LLM-FAST-06: 快速路径识别纯数字'38'"""
        result = self.service._try_fast_path_extraction("38")
        assert result is not None
        assert result["intent"] == "slot_filling"
        assert result["entities"]["unknown_numeric"] == "38"

    def test_fast_path_reject_complex_input(self):
        """TC-LLM-FAST-07: 复杂输入不应走快速路径"""
        result = self.service._try_fast_path_extraction("宝宝发烧三天了怎么办")
        assert result is None  # 需要走 LLM 路径

    def test_fast_path_reject_question(self):
        """TC-LLM-FAST-08: 问题句式不应走快速路径"""
        result = self.service._try_fast_path_extraction("发烧几天了")
        assert result is None  # "几天"是疑问句，不是简单陈述


class TestParseJsonFromLlmResponse:
    """P6: 修复 LLM 返回 Markdown 代码块导致 JSON 解析失败"""
    def setup_method(self):
        self.service = LLMService()

    def test_parse_json_without_markdown(self):
        """TC-LLM-JSON-01: 解析纯 JSON（无 Markdown 标记）"""
        json_str = '{"intent": "greeting", "confidence": 0.95}'
        result = self.service._parse_json_from_llm_response(json_str)
        assert result["intent"] == "greeting"
        assert result["confidence"] == 0.95

    def test_parse_json_with_markdown_block(self):
        """TC-LLM-JSON-02: 解析包裹在 ```json...``` 中的 JSON"""
        json_str = '''```json
{
    "intent": "slot_filling",
    "intent_confidence": 0.95,
    "entities": {"duration": "半天"}
}
```'''
        result = self.service._parse_json_from_llm_response(json_str)
        assert result["intent"] == "slot_filling"
        assert result["intent_confidence"] == 0.95
        assert result["entities"]["duration"] == "半天"

    def test_parse_json_with_generic_markdown(self):
        """TC-LLM-JSON-03: 解析包裹在 ```...``` 中的 JSON（无 json 语言标识）"""
        json_str = '```\n{"intent": "consult"}\n```'
        result = self.service._parse_json_from_llm_response(json_str)
        assert result["intent"] == "consult"

    def test_parse_json_with_extra_whitespace(self):
        """TC-LLM-JSON-04: 解析带有多余空格和换行的 JSON"""
        json_str = '\n\n```json\n\n{"intent": "triage"}\n\n```\n\n'
        result = self.service._parse_json_from_llm_response(json_str)
        assert result["intent"] == "triage"

    def test_parse_json_invalid_after_cleanup(self):
        """TC-LLM-JSON-05: 清理后仍不是有效 JSON 应抛出异常"""
        invalid_json = '```json\nnot a valid json\n```'
        with pytest.raises(Exception):  # json.JSONDecodeError
            self.service._parse_json_from_llm_response(invalid_json)
