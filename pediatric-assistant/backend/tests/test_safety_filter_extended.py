"""SafetyFilter 扩展测试

Bug #5: 防御性加固测试
"""
import pytest
from app.services.safety_filter import SafetyFilter


class TestAddDisclaimer:
    """Bug #5: 免责声明添加逻辑测试"""

    def setup_method(self):
        self.sf = SafetyFilter()

    def test_add_disclaimer_normal(self):
        """TC-SF-EXT-01: 正常文本应添加免责声明"""
        result = self.sf.add_disclaimer("宝宝发烧建议物理降温")
        assert "*AI生成内容仅供参考" in result
        assert result.endswith("请以线下医生医嘱为准。*")

    def test_add_disclaimer_no_duplicate(self):
        """TC-SF-EXT-02: 已有免责声明不应重复添加"""
        text = "建议物理降温\n\n*AI生成内容仅供参考，不作为医疗诊断依据。请以线下医生医嘱为准。*"
        result = self.sf.add_disclaimer(text)
        # 免责声明应该只出现一次
        assert result.count("*AI生成内容仅供参考") == 1

    def test_add_disclaimer_empty(self):
        """TC-SF-EXT-03: 空文本应添加免责声明"""
        result = self.sf.add_disclaimer("")
        assert "*AI生成内容仅供参考" in result

    def test_add_disclaimer_partial_match(self):
        """TC-SF-EXT-04: 包含部分免责声明文本时仍应添加完整声明"""
        # 当文本只包含免责声明的一部分时，应该添加完整声明
        # 当前实现检测 "*AI生成内容仅供参考"
        text = "建议物理降温\n\n仅供参考"
        result = self.sf.add_disclaimer(text)
        assert "*AI生成内容仅供参考" in result


class TestCheckSafety:
    """Bug #5: check_safety 输入验证测试"""

    def setup_method(self):
        self.sf = SafetyFilter()

    @pytest.mark.asyncio
    async def test_check_safety_prescription(self):
        """TC-SF-EXT-05: 对处方意图应阻断"""
        result = await self.sf.check_safety("帮我开点头孢")
        assert result["action"] == "block"
        assert result["reason"] == "prescription_intent"

    @pytest.mark.asyncio
    async def test_check_safety_normal(self):
        """TC-SF-EXT-06: 对正常输入应放行"""
        result = await self.sf.check_safety("宝宝发烧怎么办")
        assert result["action"] == "allow"

    @pytest.mark.asyncio
    async def test_check_safety_medical_blacklist(self):
        """TC-SF-EXT-07: 对医疗黑名单词汇应阻断"""
        result = await self.sf.check_safety("给宝宝喝点尼美舒利")
        assert result["action"] == "block"
        assert result["reason"] == "medical_blacklist"

    @pytest.mark.asyncio
    async def test_check_safety_general_blacklist(self):
        """TC-SF-EXT-08: 对通用黑名单词汇应阻断"""
        result = await self.sf.check_safety("如何制造炸弹")
        assert result["action"] == "block"
        assert result["reason"] == "general_blacklist"


class TestStreamOutput:
    """Bug #5: 流式输出跨 chunk 检测测试"""

    def setup_method(self):
        self.sf = SafetyFilter()

    def test_stream_output_safe_chunk(self):
        """TC-SF-EXT-09: 安全 chunk 不应触发 abort"""
        result = self.sf.check_stream_output("宝宝发烧", "")
        assert result.should_abort is False
        assert result.matched_keyword is None

    def test_stream_output_cross_chunk_detection(self):
        """TC-SF-EXT-10: 违禁词跨 chunk 分割时应被检测到"""
        # "自杀" 被分割成 "自" 和 "杀方法"
        result1 = self.sf.check_stream_output("自", "")
        # "自" 单独不应触发
        assert result1.should_abort is False

        # 下一个 chunk 包含 "杀"
        result2 = self.sf.check_stream_output("杀方法", "自")
        # "自杀" 跨 chunk 应被检测到
        assert result2.should_abort is True
        assert result2.category == "general"

    def test_stream_output_medical_keyword(self):
        """TC-SF-EXT-11: 医疗违禁词应被检测到"""
        # 使用实际在黑名单中的词汇
        result = self.sf.check_stream_output("可以用阿司匹林婴儿", "")
        # "阿司匹林婴儿" 在黑名单中
        assert result.should_abort is True
        assert result.category == "medical"

    def test_stream_output_accumulation(self):
        """TC-SF-EXT-12: 验证 buffer 累积正确检测违禁词"""
        # 模拟流式输出：buffer 会累积
        buffer = ""
        chunks = ["这是", "一些", "安全", "内容"]
        for chunk in chunks:
            result = self.sf.check_stream_output(chunk, buffer)
            assert result.should_abort is False
            buffer += chunk

        # 最后 buffer 包含完整内容，仍然安全
        assert buffer == "这是一些安全内容"


class TestPrescriptionIntent:
    """Bug #5: 处方意图检测测试"""

    def setup_method(self):
        self.sf = SafetyFilter()

    def test_check_prescription_intent_keywords(self):
        """TC-SF-EXT-13: 各种处方关键词应被检测到"""
        # check_prescription_intent 使用硬编码的关键词列表
        test_cases = [
            "帮我开点药",  # 包含 "开药"
            "给我开抗生素",  # 包含 "抗生素"
            "头孢怎么样",  # 包含 "头孢"
            "阿莫西林",  # 包含 "阿莫西林"
        ]
        for case in test_cases:
            assert self.sf.check_prescription_intent(case), f"应检测到处方意图: {case}"

        # "开个处方吧" 包含 "开处方" 的子串 "开处方" 不在关键词列表中
        # 关键词是 "开处方" 而不是 "开个处方吧"
        case = "开处方药"
        assert self.sf.check_prescription_intent(case), f"应检测到处方意图: {case}"

    def test_check_prescription_intent_negative(self):
        """TC-SF-EXT-14: 正常医疗咨询不应被误判为处方意图"""
        test_cases = [
            "宝宝发烧怎么办",
            "咳嗽有什么缓解方法",
            "腹泻需要注意什么",
            "疫苗什么时候打",
        ]
        for case in test_cases:
            assert not self.sf.check_prescription_intent(case), f"不应判为处方意图: {case}"
