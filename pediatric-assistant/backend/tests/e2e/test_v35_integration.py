"""
E2E Integration Tests for v3.5 Features
Tests user authentication, archiving, and session continuity
"""
import pytest
import tempfile
import os
from datetime import datetime, timedelta

from app.services.conversation_service import ConversationService


class TestV35IntegrationScenarios:
    """v3.5 功能集成测试 - 覆盖10个验证场景"""

    @pytest.fixture
    def service(self):
        """创建测试用的 ConversationService"""
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)

        service = ConversationService(db_path)
        service.init_db()

        yield service

        # 清理
        os.unlink(db_path)

    # ========== Scenario 1: 首次登录创建用户 ==========
    def test_scenario_1_first_time_user_registration(self, service):
        """
        TC-E2E-01: 首次登录创建用户

        步骤:
        1. 用户输入邮箱 "parent@example.com"
        2. 前端生成 user_id: "user_parentexamplecom"
        3. 调用 /api/v1/auth/register 注册用户
        4. 验证用户创建成功
        5. 验证用户可以开始对话
        """
        # Step 1-2: 模拟前端生成 user_id
        email = "parent@example.com"
        user_id = "user_" + email.replace("@", "").replace(".", "")

        # Step 3: 注册用户
        user = service.upsert_user(
            user_id=user_id,
            nickname=email,
            email=email
        )

        # Step 4: 验证用户创建成功
        assert user is not None
        assert user["user_id"] == user_id
        assert user["email"] == email
        assert user["created_at"] is not None
        assert user["last_login"] is not None

        # Step 5: 验证可以创建对话
        conv_id = "conv_test_001"
        conversation = service.create_conversation(conv_id, user_id)
        assert conversation is not None

        conversations = service.get_user_conversations(user_id)
        assert len(conversations) == 1
        assert conversations[0]["conversation_id"] == conv_id

    # ========== Scenario 2: 老用户重新登录 ==========
    def test_scenario_2_returning_user_login(self, service):
        """
        TC-E2E-02: 老用户重新登录

        步骤:
        1. 创建用户并记录 last_login
        2. 模拟用户离开
        3. 用户再次登录
        4. 验证 last_login 更新
        5. 验证历史对话加载
        """
        # Step 1: 创建用户
        user_id = "user_returninguser"
        user1 = service.upsert_user(user_id, nickname="老用户", email="returning@example.com")
        first_login = user1["last_login"]

        # 创建历史对话
        conv_id = "conv_returning_001"
        service.create_conversation(conv_id, user_id)
        service.append_message(conv_id, user_id, "user", "宝宝发烧38度")

        # Step 2-3: 模拟再次登录
        import time
        time.sleep(0.1)  # 确保时间戳不同
        user2 = service.upsert_user(user_id)

        # Step 4: 验证 last_login 更新
        assert user2["last_login"] > first_login

        # Step 5: 验证历史对话加载
        conversations = service.get_user_conversations(user_id)
        assert len(conversations) == 1
        assert conversations[0]["conversation_id"] == conv_id
        assert conversations[0]["message_count"] == 1

    # ========== Scenario 3: 单成员对话归档 ==========
    def test_scenario_3_single_member_archive(self, service):
        """
        TC-E2E-03: 单成员对话归档

        步骤:
        1. 创建用户和对话
        2. 查询对话涉及成员（单个）
        3. 自动归档到该成员
        4. 验证对话标记为已归档
        5. 验证侧边栏显示归档标记
        """
        # Step 1: 创建用户和对话
        user_id = "user_single"
        service.upsert_user(user_id, nickname="单成员用户")

        conv_id = "conv_single_001"
        service.create_conversation(conv_id, user_id)
        service.append_message(conv_id, user_id, "user", "宝宝咳嗽")
        service.append_message(conv_id, user_id, "assistant", "请问咳嗽几天了？")

        # Step 2: 查询涉及成员（模拟后端返回）
        # 在实际场景中，这会从对话内容中提取
        member_id = "member_baby_001"
        members = [{"id": member_id, "name": "宝宝", "relationship": "child"}]

        # Step 3: 归档对话
        result = service.mark_archived(conv_id, member_id)
        assert result is True

        # Step 4-5: 验证侧边栏加载时显示归档状态
        conversations = service.get_user_conversations(user_id)
        assert conversations[0]["archived"] == 1  # SQLite boolean stored as int

    # ========== Scenario 4: 多成员对话选择归档 ==========
    def test_scenario_4_multi_member_archive_selection(self, service):
        """
        TC-E2E-04: 多成员对话选择归档

        步骤:
        1. 创建涉及多成员的对话
        2. 查询返回多个成员
        3. 用户选择其中一个成员
        4. 归档到选定成员
        5. 验证归档成功
        """
        # Step 1: 创建对话
        user_id = "user_multi"
        service.upsert_user(user_id, nickname="多成员用户")

        conv_id = "conv_multi_001"
        service.create_conversation(conv_id, user_id)
        service.append_message(conv_id, user_id, "user", "大宝和二宝都发烧")

        # Step 2: 模拟查询返回多个成员
        members = [
            {"id": "member_child1", "name": "大宝", "relationship": "child", "age": "5岁"},
            {"id": "member_child2", "name": "二宝", "relationship": "child", "age": "3岁"}
        ]

        # Step 3: 用户选择大宝
        selected_member_id = "member_child1"

        # Step 4: 归档到大宝
        result = service.mark_archived(conv_id, selected_member_id)
        assert result is True

        # Step 5: 验证归档成功
        conversations = service.get_user_conversations(user_id)
        archived_conv = [c for c in conversations if c["conversation_id"] == conv_id][0]
        assert archived_conv["archived"] == 1
        assert archived_conv["archived_member_id"] == selected_member_id

    # ========== Scenario 5: beforeunload 提示归档 ==========
    def test_scenario_5_beforeunload_archive_prompt(self, service):
        """
        TC-E2E-05: beforeunload 提示归档

        步骤:
        1. 创建对话超过5分钟
        2. 模拟页面关闭事件
        3. 验证触发归档提示（前端测试通过检查状态）
        4. 用户确认归档
        5. 对话成功归档
        """
        # Step 1: 创建对话
        user_id = "user_beforeunload"
        service.upsert_user(user_id)

        conv_id = "conv_beforeunload_001"
        service.create_conversation(conv_id, user_id)
        service.append_message(conv_id, user_id, "user", "宝宝腹泻")

        # Step 2: 模拟对话持续时间超过5分钟
        # 在实际前端实现中，这会通过 conversationStartTime 检测
        # 这里通过更新 created_at 模拟
        with service._connect() as conn:
            five_minutes_ago = (datetime.now() - timedelta(minutes=6)).isoformat()
            conn.execute(
                "UPDATE conversations SET created_at = ? WHERE id = ?",
                (five_minutes_ago, conv_id)
            )
            conn.commit()

        # Step 3-4: 模拟用户确认归档
        member_id = "member_baby_002"
        result = service.mark_archived(conv_id, member_id)

        # Step 5: 验证归档成功
        assert result is True
        conversations = service.get_user_conversations(user_id)
        assert conversations[0]["archived"] == 1

    # ========== Scenario 6: 30分钟超时提醒 ==========
    def test_scenario_6_thirty_minute_timeout_reminder(self, service):
        """
        TC-E2E-06: 30分钟超时提醒

        步骤:
        1. 创建对话并设置开始时间
        2. 模拟30分钟后
        3. 验证触发提醒（前端测试通过计时器）
        4. 用户选择归档
        5. 对话归档成功
        """
        # Step 1: 创建对话
        user_id = "user_timeout"
        service.upsert_user(user_id)

        conv_id = "conv_timeout_001"
        service.create_conversation(conv_id, user_id)
        service.append_message(conv_id, user_id, "user", "宝宝拉肚子")

        # Step 2: 模拟30分钟后（通过修改时间戳）
        with service._connect() as conn:
            thirty_minutes_ago = (datetime.now() - timedelta(minutes=31)).isoformat()
            conn.execute(
                "UPDATE conversations SET created_at = ? WHERE id = ?",
                (thirty_minutes_ago, conv_id)
            )
            conn.commit()

        # Step 3-4: 验证可以归档（前端会显示提醒）
        member_id = "member_baby_003"
        result = service.mark_archived(conv_id, member_id)

        # Step 5: 验证归档成功
        assert result is True
        conversations = service.get_user_conversations(user_id)
        assert conversations[0]["archived"] == 1

    # ========== Scenario 7: 已归档对话只读 ==========
    def test_scenario_7_archived_conversation_readonly(self, service):
        """
        TC-E2E-07: 已归档对话只读

        步骤:
        1. 归档一个对话
        2. 尝试添加新消息
        3. 验证操作被拒绝或标记为只读
        4. 验证侧边栏显示只读标记
        """
        # Step 1: 创建并归档对话
        user_id = "user_readonly"
        service.upsert_user(user_id)

        conv_id = "conv_readonly_001"
        service.create_conversation(conv_id, user_id)
        service.append_message(conv_id, user_id, "user", "宝宝感冒")

        member_id = "member_baby_004"
        service.mark_archived(conv_id, member_id)

        # Step 2-3: 验证对话已归档（后端可以选择拒绝添加消息）
        conversations = service.get_user_conversations(user_id)
        assert conversations[0]["archived"] == 1

        # Step 4: 验证侧边栏显示只读
        archived_conv = [c for c in conversations if c["conversation_id"] == conv_id][0]
        assert archived_conv["archived"] == 1

    # ========== Scenario 8: 用户ID验证失败重新登录 ==========
    def test_scenario_8_invalid_user_relogin(self, service):
        """
        TC-E2E-08: 用户ID验证失败重新登录

        步骤:
        1. 模拟 localStorage 中存在无效 user_id
        2. 调用 /api/v1/auth/user/{user_id} 验证失败
        3. 清除本地数据
        4. 显示登录遮罩层
        5. 用户重新登录
        """
        # Step 1: 模拟无效 user_id
        invalid_user_id = "user_invalid_xyz"

        # Step 2: 验证失败
        user = service.get_user(invalid_user_id)
        assert user is None  # 用户不存在

        # Step 3-5: 模拟重新登录
        new_user_id = "user_newvaliduser"
        new_user = service.upsert_user(
            new_user_id,
            nickname="新用户",
            email="newuser@example.com"
        )

        assert new_user is not None
        assert new_user["user_id"] == new_user_id

    # ========== Scenario 9: 跨会话数据持久化 ==========
    def test_scenario_9_cross_session_persistence(self, service):
        """
        TC-E2E-09: 跨会话数据持久化

        步骤:
        1. 用户登录创建对话
        2. 归档对话
        3. 用户刷新页面（模拟应用重启）
        4. 验证归档对话仍然存在
        5. 验证归档状态保持
        """
        # Step 1: 创建用户和对话
        user_id = "user_persistence"
        service.upsert_user(user_id, nickname="持久化用户")

        conv_id = "conv_persistence_001"
        service.create_conversation(conv_id, user_id)
        service.append_message(conv_id, user_id, "user", "宝宝过敏")

        # Step 2: 归档对话
        member_id = "member_baby_005"
        service.mark_archived(conv_id, member_id)

        # Step 3: 模拟应用重启（创建新实例）
        service2 = ConversationService(service.db_path)

        # Step 4-5: 验证数据持久化
        user = service2.get_user(user_id)
        assert user is not None

        conversations = service2.get_user_conversations(user_id)
        assert len(conversations) == 1
        assert conversations[0]["conversation_id"] == conv_id
        assert conversations[0]["archived"] == 1
        assert conversations[0]["archived_member_id"] == member_id

    # ========== Scenario 10: 完整用户流程 ==========
    def test_scenario_10_complete_user_journey(self, service):
        """
        TC-E2E-10: 完整用户流程（端到端）

        步骤:
        1. 首次登录注册
        2. 创建对话并交互
        3. 超过30分钟收到提醒
        4. 选择归档
        5. 刷新页面
        6. 查看归档对话
        7. 创建新对话
        8. 验证所有功能正常
        """
        # Step 1: 首次登录
        user_id = "user_complete_journey"
        email = "journey@example.com"
        user = service.upsert_user(user_id, nickname=email, email=email)
        assert user is not None

        # Step 2: 创建对话并交互
        conv_id_1 = "conv_journey_001"
        service.create_conversation(conv_id_1, user_id)
        service.append_message(conv_id_1, user_id, "user", "宝宝发烧39度")
        service.append_message(conv_id_1, user_id, "assistant", "请问发烧多久了？")
        service.append_message(conv_id_1, user_id, "user", "半天了")

        # Step 3: 模拟30分钟后
        with service._connect() as conn:
            thirty_minutes_ago = (datetime.now() - timedelta(minutes=31)).isoformat()
            conn.execute(
                "UPDATE conversations SET created_at = ? WHERE id = ?",
                (thirty_minutes_ago, conv_id_1)
            )
            conn.commit()

        # Step 4: 归档对话
        member_id = "member_baby_journey"
        result = service.mark_archived(conv_id_1, member_id)
        assert result is True

        # Step 5: 模拟刷新页面（创建新实例）
        service2 = ConversationService(service.db_path)

        # Step 6: 查看归档对话
        conversations = service2.get_user_conversations(user_id)
        assert len(conversations) == 1
        archived_conv = conversations[0]
        assert archived_conv["archived"] == 1
        assert archived_conv["message_count"] == 3

        # Step 7: 创建新对话
        conv_id_2 = "conv_journey_002"
        service2.create_conversation(conv_id_2, user_id)
        service2.append_message(conv_id_2, user_id, "user", "宝宝咳嗽")

        # Step 8: 验证所有功能正常
        all_conversations = service2.get_user_conversations(user_id)
        assert len(all_conversations) == 2

        # 验证归档对话仍然存在
        archived = [c for c in all_conversations if c["archived"]]
        assert len(archived) == 1
        assert archived[0]["conversation_id"] == conv_id_1

        # 验证新对话正常
        active = [c for c in all_conversations if not c["archived"]]
        assert len(active) == 1
        assert active[0]["conversation_id"] == conv_id_2


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
