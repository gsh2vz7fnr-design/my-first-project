"""流式安全过滤器单元测试"""
import pytest
from app.services.stream_filter import StreamSafetyFilter


class TestStreamSafetyFilterChunkCounting:
    """P0-4: 验证 chunk 不被重复计算"""
    def setup_method(self):
        self.filter = StreamSafetyFilter()

    def test_safe_chunk_passes(self):
        """TC-SF-001: 安全内容不被拦截"""
        result = self.filter.check_chunk("宝宝发烧了怎么办")
        assert result.should_abort is False

    def test_buffer_not_double_counted(self):
        """TC-SF-002: 分两次发送"自"+"杀"，buffer 应为"自杀"而非"自自杀杀" """
        self.filter.check_chunk("自")
        assert self.filter.buffer == "自"
        result = self.filter.check_chunk("杀")
        assert self.filter.buffer == "自杀"
        assert result.should_abort is True

    def test_single_chunk_blacklisted(self):
        """TC-SF-003: 单 chunk 含违禁词应拦截"""
        result = self.filter.check_chunk("这是炸弹的做法")
        assert result.should_abort is True

    def test_reset_clears_state(self):
        """TC-SF-004: reset 后 buffer 清空"""
        self.filter.check_chunk("一些内容")
        self.filter.reset()
        assert self.filter.buffer == ""
        assert self.filter.aborted is False
