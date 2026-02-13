"""
认证 API 集成测试
"""
import pytest
from fastapi.testclient import TestClient
import tempfile
import os

from app.main import app
from app.config import settings


@pytest.fixture
def client():
    """创建测试客户端"""
    # 使用临时数据库
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    # 临时修改配置
    original_db_path = settings.SQLITE_DB_PATH
    settings.SQLITE_DB_PATH = db_path

    # 重新初始化数据库
    from app.services.conversation_service import conversation_service
    conversation_service.db_path = db_path
    conversation_service.init_db()

    client = TestClient(app)

    yield client

    # 恢复配置
    settings.SQLITE_DB_PATH = original_db_path
    os.unlink(db_path)


class TestAuthAPI:
    """认证 API 测试"""

    def test_register_new_user(self, client):
        """测试注册新用户"""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "user_id": "test_user_123",
                "nickname": "测试用户",
                "email": "test@example.com"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["user_id"] == "test_user_123"
        assert data["data"]["nickname"] == "测试用户"
        assert data["data"]["email"] == "test@example.com"
        assert "created_at" in data["data"]
        assert "last_login" in data["data"]

    def test_register_update_existing_user(self, client):
        """测试更新已有用户"""
        # 注册用户
        client.post(
            "/api/v1/auth/register",
            json={
                "user_id": "test_user_456",
                "nickname": "初始昵称",
                "email": "initial@example.com"
            }
        )

        # 再次注册（更新）
        response = client.post(
            "/api/v1/auth/register",
            json={
                "user_id": "test_user_456",
                "nickname": "新昵称"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["nickname"] == "新昵称"
        assert data["data"]["email"] == "initial@example.com"  # email 保持不变

    def test_get_existing_user(self, client):
        """测试获取已存在的用户"""
        # 先注册用户
        client.post(
            "/api/v1/auth/register",
            json={
                "user_id": "test_user_789",
                "nickname": "测试789",
                "email": "test789@example.com"
            }
        )

        # 获取用户
        response = client.get("/api/v1/auth/user/test_user_789")

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["user_id"] == "test_user_789"
        assert data["data"]["nickname"] == "测试789"
        assert data["data"]["email"] == "test789@example.com"

    def test_get_nonexistent_user(self, client):
        """测试获取不存在的用户"""
        response = client.get("/api/v1/auth/user/nonexistent_user")

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 404
        assert data["data"] is None
        assert "不存在" in data["message"]

    def test_register_minimal_data(self, client):
        """测试只提供 user_id 的注册"""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "user_id": "minimal_user"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["user_id"] == "minimal_user"
        assert data["data"]["nickname"] is None
        assert data["data"]["email"] is None

    def test_same_email_generates_same_userid(self, client):
        """测试相同邮箱生成相同的 user_id（模拟前端逻辑）"""
        # 模拟前端生成 user_id
        email1 = "user@example.com"
        user_id1 = "user_" + email1.strip().lower().replace(" ", "").replace("@", "").replace(".", "")

        email2 = "  USER@example.com  "
        user_id2 = "user_" + email2.strip().lower().replace(" ", "").replace("@", "").replace(".", "")

        assert user_id1 == user_id2

        # 第一次注册
        response1 = client.post(
            "/api/v1/auth/register",
            json={
                "user_id": user_id1,
                "nickname": "用户1",
                "email": email1
            }
        )
        assert response1.status_code == 200

        # 第二次使用相同 user_id（应该更新）
        response2 = client.post(
            "/api/v1/auth/register",
            json={
                "user_id": user_id2,
                "nickname": "用户2"
            }
        )
        assert response2.status_code == 200

        # 检查是同一个用户（last_login 会更新）
        data = response2.json()["data"]
        assert data["user_id"] == user_id1
        assert data["nickname"] == "用户2"
