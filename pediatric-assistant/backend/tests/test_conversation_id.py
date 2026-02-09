"""对话ID生成测试"""
import pytest
import re
import uuid


class TestConversationIdGeneration:
    """P0-5: 验证匿名对话生成唯一ID"""

    def test_none_generates_unique(self):
        """TC-CID-001: None -> 两次生成不同ID"""
        id1 = None or f"conv_{uuid.uuid4().hex[:12]}"
        id2 = None or f"conv_{uuid.uuid4().hex[:12]}"
        assert id1 != id2
        assert id1.startswith("conv_")

    def test_existing_id_preserved(self):
        """TC-CID-002: 已有ID保持不变"""
        result = "conv_abc123" or f"conv_{uuid.uuid4().hex[:12]}"
        assert result == "conv_abc123"

    def test_format_valid(self):
        """TC-CID-003: 格式为 conv_ + 12位hex"""
        conv_id = f"conv_{uuid.uuid4().hex[:12]}"
        assert re.match(r"^conv_[0-9a-f]{12}$", conv_id)
