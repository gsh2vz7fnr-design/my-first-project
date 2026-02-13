"""
认证系统单元测试
"""
import pytest
import tempfile
import os
from datetime import datetime

from app.services.conversation_service import ConversationService


class TestAuthSystem:
    """认证系统测试"""

    @pytest.fixture
    def service(self):
        """创建测试用的 ConversationService"""
        # 使用临时文件
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)

        service = ConversationService(db_path)
        service.init_db()

        yield service

        # 清理
        os.unlink(db_path)

    def test_upsert_user_create_new(self, service):
        """测试创建新用户"""
        user = service.upsert_user(
            user_id="test_user_123",
            nickname="测试用户",
            email="test@example.com"
        )

        assert user["user_id"] == "test_user_123"
        assert user["nickname"] == "测试用户"
        assert user["email"] == "test@example.com"
        assert user["created_at"] is not None
        assert user["last_login"] is not None

    def test_upsert_user_update_existing(self, service):
        """测试更新已有用户"""
        # 创建用户
        user1 = service.upsert_user(
            user_id="test_user_456",
            nickname="初始昵称",
            email="initial@example.com"
        )
        created_at = user1["created_at"]

        # 更新用户
        user2 = service.upsert_user(
            user_id="test_user_456",
            nickname="新昵称"
        )

        assert user2["user_id"] == "test_user_456"
        assert user2["nickname"] == "新昵称"
        assert user2["email"] == "initial@example.com"  # email 保持不变
        assert user2["created_at"] == created_at  # 创建时间不变
        assert user2["last_login"] != user1["last_login"]  # 登录时间更新

    def test_upsert_user_update_last_login_only(self, service):
        """测试只更新 last_login"""
        # 创建用户
        user1 = service.upsert_user(
            user_id="test_user_789",
            nickname="测试",
            email="test789@example.com"
        )

        # 只更新 last_login（不传 nickname 和 email）
        user2 = service.upsert_user(user_id="test_user_789")

        assert user2["nickname"] == "测试"
        assert user2["email"] == "test789@example.com"
        assert user2["last_login"] != user1["last_login"]

    def test_get_user_existing(self, service):
        """测试获取已存在的用户"""
        service.upsert_user(
            user_id="test_user_abc",
            nickname="ABC用户",
            email="abc@example.com"
        )

        user = service.get_user("test_user_abc")

        assert user is not None
        assert user["user_id"] == "test_user_abc"
        assert user["nickname"] == "ABC用户"
        assert user["email"] == "abc@example.com"

    def test_get_user_not_found(self, service):
        """测试获取不存在的用户"""
        user = service.get_user("nonexistent_user")
        assert user is None

    def test_deterministic_user_id_from_email(self):
        """测试从邮箱生成确定性用户ID"""
        # 模拟前端生成用户ID的逻辑
        email = "user@example.com"
        cleaned = email.strip().lower().replace(" ", "")
        user_id = "user_" + "".join(c for c in cleaned if c.isalnum())

        assert user_id == "user_userexamplecom"

        # 相同邮箱应生成相同ID
        email2 = "  USER@example.com  "
        cleaned2 = email2.strip().lower().replace(" ", "")
        user_id2 = "user_" + "".join(c for c in cleaned2 if c.isalnum())

        assert user_id == user_id2

    def test_users_table_exists(self, service):
        """测试 users 表已创建"""
        with service._connect() as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
            )
            result = cursor.fetchone()
            assert result is not None
            assert result["name"] == "users"

    def test_user_persistence(self, service):
        """测试用户数据持久化"""
        # 创建用户
        service.upsert_user(
            user_id="persist_test",
            nickname="持久化测试",
            email="persist@test.com"
        )

        # 重新创建 service 实例（模拟应用重启）
        service2 = ConversationService(service.db_path)

        # 检查用户是否仍然存在
        user = service2.get_user("persist_test")

        assert user is not None
        assert user["nickname"] == "持久化测试"
        assert user["email"] == "persist@test.com"
