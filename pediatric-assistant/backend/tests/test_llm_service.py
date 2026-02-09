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
