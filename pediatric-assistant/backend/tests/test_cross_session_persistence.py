"""
跨会话持久化综合测试

测试场景：
1. 会话内数据更新：MedicalContext 正确更新
2. 跨会话数据保留：重启后数据完整性
3. 用户数据隔离：不同用户数据不混淆
4. 事务处理：失败回滚正确
5. 并发访问：多线程安全性
6. 缓存一致性：内存与数据库同步
"""
import pytest
import tempfile
import os
import threading
import time
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.services.conversation_state_service import ConversationStateService
from app.services.conversation_service import ConversationService
from app.services.profile_service import ProfileService
from app.models.medical_context import (
    MedicalContext,
    DialogueState,
    IntentType,
    TriageSnapshot
)


@pytest.fixture
def temp_db():
    """创建临时数据库"""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    try:
        os.unlink(path)
    except:
        pass


@pytest.fixture
def services(temp_db):
    """创建带数据库的服务实例"""
    state_service = ConversationStateService(db_path=temp_db)
    state_service.init_db()

    conv_service = ConversationService(db_path=temp_db)
    conv_service.init_db()

    profile_service = ProfileService(db_path=temp_db)
    profile_service.init_db()

    return {
        "state": state_service,
        "conversation": conv_service,
        "profile": profile_service
    }


# ============ 测试 1: 会话内数据更新 ============

class TestInSessionUpdates:
    """测试会话内的数据更新"""

    def test_medical_context_update_during_conversation(self, services):
        """测试对话过程中 MedicalContext 的更新"""
        state_service = services["state"]

        # 模拟多轮对话
        ctx = state_service.load_medical_context("conv_001", "user_001")

        # 第一轮：用户说"我家孩子发烧了"
        ctx.symptom = "发烧"
        ctx.slots = {"age_months": 8}
        ctx.turn_count = 1
        state_service.save_medical_context(ctx)

        # 第二轮：用户提供更多症状
        loaded = state_service.load_medical_context("conv_001", "user_001")
        loaded.slots["temperature"] = "38.5度"
        loaded.slots["duration"] = "1天"
        loaded.turn_count = 2
        state_service.save_medical_context(loaded)

        # 验证最终状态
        final = state_service.load_medical_context("conv_001", "user_001")
        assert final.symptom == "发烧"
        assert final.slots["age_months"] == 8
        assert final.slots["temperature"] == "38.5度"
        assert final.slots["duration"] == "1天"
        assert final.turn_count == 2

    def test_entity_accumulation_across_turns(self, services):
        """测试实体在多轮对话中的累积"""
        state_service = services["state"]

        # 使用 merge_entities 方法
        ctx = state_service.load_medical_context("conv_accum", "user_001")

        # 第一轮实体
        entities1 = {"symptom": "咳嗽", "age_months": 12}
        ctx.merge_entities(entities1)
        state_service.save_medical_context(ctx)

        # 第二轮实体（追加）
        loaded = state_service.load_medical_context("conv_accum", "user_001")
        entities2 = {"accompanying_symptoms": "流鼻涕", "duration": "3天"}
        loaded.merge_entities(entities2)
        state_service.save_medical_context(loaded)

        # 验证累积结果
        final = state_service.load_medical_context("conv_accum", "user_001")
        assert final.slots["symptom"] == "咳嗽"
        assert final.slots["age_months"] == 12
        assert final.slots["accompanying_symptoms"] == "流鼻涕"
        assert final.slots["duration"] == "3天"

    def test_dialogue_state_transitions(self, services):
        """测试对话状态转换的持久化"""
        state_service = services["state"]

        ctx = state_service.load_medical_context("conv_state", "user_001")

        # INITIAL -> COLLECTING_SLOTS
        ctx.dialogue_state = DialogueState.COLLECTING_SLOTS
        state_service.save_medical_context(ctx)

        loaded = state_service.load_medical_context("conv_state", "user_001")
        assert loaded.dialogue_state == DialogueState.COLLECTING_SLOTS

        # COLLECTING_SLOTS -> READY_FOR_TRIAGE
        loaded.dialogue_state = DialogueState.READY_FOR_TRIAGE
        state_service.save_medical_context(loaded)

        final = state_service.load_medical_context("conv_state", "user_001")
        assert final.dialogue_state == DialogueState.READY_FOR_TRIAGE


# ============ 测试 2: 跨会话数据保留 ============

class TestCrossSessionRetention:
    """测试跨会话的数据保留"""

    def test_service_restart_data_persistence(self, temp_db):
        """测试服务重启后数据的保留"""
        # 第一阶段：创建数据
        service1 = ConversationStateService(db_path=temp_db)
        service1.init_db()

        ctx = MedicalContext(
            conversation_id="conv_restart",
            user_id="user_restart",
            symptom="发烧",
            slots={"temperature": "39度", "age_months": 6}
        )
        service1.save_medical_context(ctx)

        # 第二阶段：模拟重启（新实例）
        service2 = ConversationStateService(db_path=temp_db)
        service2.init_db()

        # 验证数据仍然存在
        loaded = service2.load_medical_context("conv_restart", "user_restart")
        assert loaded.symptom == "发烧"
        assert loaded.slots["temperature"] == "39度"
        assert loaded.slots["age_months"] == 6

    def test_conversation_history_persistence(self, services):
        """测试对话历史的持久化"""
        conv_service = services["conversation"]

        # 添加多条消息
        conv_service.append_message("conv_hist", "user_001", "user", "你好")
        conv_service.append_message("conv_hist", "user_001", "assistant", "您好，有什么可以帮助您？")
        conv_service.append_message("conv_hist", "user_001", "user", "我家孩子发烧了")

        # 获取历史
        history = conv_service.get_history("conv_hist")
        assert len(history) == 3
        assert history[0]["content"] == "你好"
        assert history[1]["role"] == "assistant"
        assert history[2]["content"] == "我家孩子发烧了"

    def test_multiple_conversations_per_user(self, services):
        """测试用户多个对话的数据保留"""
        state_service = services["state"]

        # 用户创建多个对话
        for i in range(3):
            conv_id = f"conv_multi_{i}"
            ctx = MedicalContext(
                conversation_id=conv_id,
                user_id="user_multi",
                symptom=f"症状{i}",
                turn_count=i + 1
            )
            state_service.save_medical_context(ctx)

        # 获取所有对话
        contexts = state_service.get_user_contexts("user_multi")
        assert len(contexts) == 3

        # 验证每个对话的数据
        for ctx in contexts:
            assert ctx.user_id == "user_multi"

    def test_profile_data_persistence(self, services):
        """测试用户档案数据的持久化"""
        profile_service = services["profile"]

        from app.models.user import HealthProfile, BabyInfo

        # 创建并保存档案
        profile = HealthProfile(
            user_id="user_profile",
            baby_info=BabyInfo(age_months=12, weight_kg=10)
        )
        profile_service.save_profile(profile)

        # 重新加载
        loaded = profile_service.get_profile("user_profile")
        assert loaded.user_id == "user_profile"
        assert loaded.baby_info.age_months == 12
        assert loaded.baby_info.weight_kg == 10


# ============ 测试 3: 用户数据隔离 ============

class TestUserDataIsolation:
    """测试用户数据隔离"""

    def test_users_cannot_access_each_others_contexts(self, services):
        """测试用户不能访问彼此的上下文"""
        state_service = services["state"]

        # 用户1的数据
        ctx1 = MedicalContext(
            conversation_id="conv_isolated_1",
            user_id="user_001",
            symptom="发烧",
            slots={"age_months": 6}
        )
        state_service.save_medical_context(ctx1)

        # 用户2的数据（不同的 conversation_id）
        ctx2 = MedicalContext(
            conversation_id="conv_isolated_2",
            user_id="user_002",
            symptom="咳嗽",
            slots={"age_months": 12}
        )
        state_service.save_medical_context(ctx2)

        # 验证用户1只能看到自己的数据
        user1_contexts = state_service.get_user_contexts("user_001")
        assert len(user1_contexts) == 1
        assert user1_contexts[0].user_id == "user_001"
        assert user1_contexts[0].symptom == "发烧"

        # 验证用户2只能看到自己的数据
        user2_contexts = state_service.get_user_contexts("user_002")
        assert len(user2_contexts) == 1
        assert user2_contexts[0].user_id == "user_002"
        assert user2_contexts[0].symptom == "咳嗽"

    def test_profile_isolation(self, services):
        """测试用户档案隔离"""
        profile_service = services["profile"]

        from app.models.user import HealthProfile, BabyInfo

        # 用户1的档案
        profile1 = HealthProfile(
            user_id="user_profile_1",
            baby_info=BabyInfo(age_months=6, weight_kg=8)
        )
        profile_service.save_profile(profile1)

        # 用户2的档案
        profile2 = HealthProfile(
            user_id="user_profile_2",
            baby_info=BabyInfo(age_months=24, weight_kg=12)
        )
        profile_service.save_profile(profile2)

        # 验证隔离
        loaded1 = profile_service.get_profile("user_profile_1")
        loaded2 = profile_service.get_profile("user_profile_2")

        assert loaded1.baby_info.age_months == 6
        assert loaded2.baby_info.age_months == 24
        assert loaded1.baby_info.weight_kg == 8
        assert loaded2.baby_info.weight_kg == 12

    def test_conversation_isolation(self, services):
        """测试对话历史隔离"""
        conv_service = services["conversation"]

        # 用户1的对话
        conv_service.append_message("conv_user1", "user_001", "user", "用户1的消息")

        # 用户2的对话
        conv_service.append_message("conv_user2", "user_002", "user", "用户2的消息")

        # 获取用户1的对话列表
        user1_convs = conv_service.get_user_conversations("user_001")
        user2_convs = conv_service.get_user_conversations("user_002")

        assert len(user1_convs) == 1
        assert len(user2_convs) == 1
        assert user1_convs[0]["conversation_id"] == "conv_user1"
        assert user2_convs[0]["conversation_id"] == "conv_user2"


# ============ 测试 4: 数据一致性和完整性 ============

class TestDataConsistency:
    """测试数据一致性和完整性"""

    def test_json_serialization_roundtrip(self, services):
        """测试 JSON 序列化/反序列化的往返一致性"""
        state_service = services["state"]

        # 创建复杂的上下文
        ctx = MedicalContext(
            conversation_id="conv_json",
            user_id="user_json",
            dialogue_state=DialogueState.COLLECTING_SLOTS,
            current_intent=IntentType.TRIAGE,
            symptom="发烧",
            triage_level="observe",
            triage_reason="体温38.5度，建议观察",
            triage_action="物理降温，多喝水",
            slots={
                "age_months": 8,
                "temperature": "38.5度",
                "duration": "1天",
                "accompanying_symptoms": "咳嗽,流鼻涕"
            },
            turn_count=3
        )

        # 保存并加载
        state_service.save_medical_context(ctx)
        loaded = state_service.load_medical_context("conv_json", "user_json")

        # 验证所有字段
        assert loaded.conversation_id == ctx.conversation_id
        assert loaded.user_id == ctx.user_id
        assert loaded.dialogue_state == DialogueState.COLLECTING_SLOTS
        assert loaded.current_intent == IntentType.TRIAGE
        assert loaded.symptom == "发烧"
        assert loaded.triage_level == "observe"
        assert loaded.triage_reason == "体温38.5度，建议观察"
        assert loaded.triage_action == "物理降温，多喝水"
        assert loaded.slots["age_months"] == 8
        assert loaded.slots["temperature"] == "38.5度"
        assert loaded.slots["duration"] == "1天"
        assert loaded.slots["accompanying_symptoms"] == "咳嗽,流鼻涕"
        assert loaded.turn_count == 3

    def test_update_preserves_existing_data(self, services):
        """测试更新保留已有数据"""
        state_service = services["state"]

        # 创建初始上下文
        ctx = MedicalContext(
            conversation_id="conv_update",
            user_id="user_update",
            symptom="发烧",
            slots={"age_months": 8, "temperature": "38.5度"}
        )
        state_service.save_medical_context(ctx)

        # 部分更新
        loaded = state_service.load_medical_context("conv_update", "user_update")
        loaded.slots["duration"] = "2天"
        loaded.turn_count = 2
        state_service.save_medical_context(loaded)

        # 验证原有数据保留
        final = state_service.load_medical_context("conv_update", "user_update")
        assert final.symptom == "发烧"  # 原有
        assert final.slots["age_months"] == 8  # 原有
        assert final.slots["temperature"] == "38.5度"  # 原有
        assert final.slots["duration"] == "2天"  # 新增
        assert final.turn_count == 2

    def test_empty_values_do_not_override(self, services):
        """测试空值不覆盖已有数据"""
        state_service = services["state"]

        ctx = MedicalContext(
            conversation_id="conv_empty",
            user_id="user_empty",
            slots={"symptom": "发烧", "age_months": 8}
        )
        state_service.save_medical_context(ctx)

        # 尝试用空值更新
        loaded = state_service.load_medical_context("conv_empty", "user_empty")
        loaded.merge_entities({"symptom": "", "temperature": "38度"})
        state_service.save_medical_context(loaded)

        # 验证 symptom 没有被覆盖
        final = state_service.load_medical_context("conv_empty", "user_empty")
        assert final.slots["symptom"] == "发烧"  # 保持原值
        assert final.slots["temperature"] == "38度"  # 新值被添加


# ============ 测试 5: 并发访问 ============

class TestConcurrentAccess:
    """测试并发访问的安全性"""

    def test_concurrent_write_same_context(self, services):
        """测试多线程同时写入同一对话上下文"""
        state_service = services["state"]

        # 创建初始上下文
        ctx = MedicalContext(
            conversation_id="conv_concurrent",
            user_id="user_concurrent",
            slots={}
        )
        state_service.save_medical_context(ctx)

        results = []
        errors = []

        def update_context(slot_name, value, thread_id):
            try:
                for i in range(10):
                    loaded = state_service.load_medical_context("conv_concurrent", "user_concurrent")
                    loaded.slots[slot_name] = f"{value}_{thread_id}_{i}"
                    state_service.save_medical_context(loaded)
                    time.sleep(0.001)  # 小延迟
                results.append(thread_id)
            except Exception as e:
                errors.append((thread_id, e))

        # 启动多个线程
        threads = []
        for i in range(5):
            t = threading.Thread(
                target=update_context,
                args=(f"slot_{i}", f"value_{i}", i)
            )
            threads.append(t)
            t.start()

        # 等待所有线程完成
        for t in threads:
            t.join()

        # 验证没有错误
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 5

        # 验证最终状态
        final = state_service.load_medical_context("conv_concurrent", "user_concurrent")
        assert len(final.slots) == 5

    def test_concurrent_different_contexts(self, services):
        """测试多线程同时写入不同对话上下文"""
        state_service = services["state"]

        def create_and_update(conv_id, user_id, n):
            for i in range(n):
                ctx = state_service.load_medical_context(conv_id, user_id)
                ctx.slots[f"turn_{i}"] = f"data_{i}"
                ctx.turn_count = i + 1
                state_service.save_medical_context(ctx)

        # 并发创建和更新多个对话
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for i in range(10):
                conv_id = f"conv_para_{i}"
                user_id = f"user_para_{i % 3}"  # 3个用户
                future = executor.submit(create_and_update, conv_id, user_id, 5)
                futures.append(future)

            # 等待完成
            for future in as_completed(futures):
                future.result()

        # 验证所有对话都已保存
        for i in range(10):
            conv_id = f"conv_para_{i}"
            loaded = state_service.load_medical_context(conv_id, f"user_para_{i % 3}")
            assert loaded.turn_count == 5
            assert len(loaded.slots) == 5


# ============ 测试 6: 边界和错误处理 ============

class TestBoundaryAndErrorHandling:
    """测试边界条件和错误处理"""

    def test_nonexistent_conversation_returns_new(self, services):
        """测试不存在的对话返回新上下文"""
        state_service = services["state"]

        # 尝试加载不存在的对话
        ctx = state_service.load_medical_context("nonexistent_conv", "nonexistent_user")

        # 应该返回一个新的空上下文
        assert ctx.conversation_id == "nonexistent_conv"
        assert ctx.user_id == "nonexistent_user"
        assert ctx.dialogue_state == DialogueState.INITIAL
        assert ctx.slots == {}
        assert ctx.turn_count == 0

    def test_delete_removes_data(self, services):
        """测试删除操作移除数据"""
        state_service = services["state"]

        # 创建并保存
        ctx = MedicalContext(
            conversation_id="conv_delete",
            user_id="user_delete",
            symptom="发烧"
        )
        state_service.save_medical_context(ctx)

        # 删除
        state_service.delete_medical_context("conv_delete")

        # 验证已删除（应该返回新上下文）
        loaded = state_service.load_medical_context("conv_delete", "user_delete")
        assert loaded.dialogue_state == DialogueState.INITIAL
        assert loaded.symptom is None

    def test_cache_clear_force_db_reload(self, services):
        """测试缓存清除后强制从数据库重新加载"""
        state_service = services["state"]

        # 保存数据
        ctx = MedicalContext(
            conversation_id="conv_cache_test",
            user_id="user_cache_test",
            symptom="发烧"
        )
        state_service.save_medical_context(ctx)

        # 加载到缓存
        loaded1 = state_service.load_medical_context("conv_cache_test", "user_cache_test")
        loaded1.slots["cached"] = "yes"

        # 清除缓存
        state_service.clear_cache()

        # 重新加载应该从数据库获取
        loaded2 = state_service.load_medical_context("conv_cache_test", "user_cache_test")
        assert loaded2.symptom == "发烧"
        # 缓存中的修改不应影响数据库
        assert loaded2.slots.get("cached") is None


# ============ 测试 7: 缓存一致性 ============

class TestCacheConsistency:
    """测试内存缓存与数据库的一致性"""

    def test_cache_sync_after_save(self, services):
        """测试保存后缓存与数据库同步"""
        state_service = services["state"]

        # 创建上下文
        ctx = state_service.load_medical_context("conv_sync", "user_sync")
        ctx.symptom = "发烧"
        state_service.save_medical_context(ctx)

        # 从缓存获取
        cached = state_service._context_cache.get("conv_sync")
        assert cached is not None
        assert cached.symptom == "发烧"

        # 清除缓存后从数据库重新加载
        state_service.clear_cache()
        reloaded = state_service.load_medical_context("conv_sync", "user_sync")
        assert reloaded.symptom == "发烧"

    def test_multiple_loads_return_same_cached_instance(self, services):
        """测试多次加载返回同一缓存实例"""
        state_service = services["state"]

        # 第一次加载
        ctx1 = state_service.load_medical_context("conv_same", "user_same")
        ctx1.symptom = "咳嗽"

        # 第二次加载应该返回缓存中的同一个实例
        ctx2 = state_service.load_medical_context("conv_same", "user_same")
        assert ctx1 is ctx2  # 同一对象引用
        assert ctx2.symptom == "咳嗽"

    def test_save_updates_cache(self, services):
        """测试保存操作更新缓存"""
        state_service = services["state"]

        # 加载并修改
        ctx1 = state_service.load_medical_context("conv_cache_update", "user_cache")
        ctx1.symptom = "发烧"
        state_service.save_medical_context(ctx1)

        # 从缓存获取应该是更新后的对象
        cached = state_service._context_cache.get("conv_cache_update")
        assert cached.symptom == "发烧"
        assert cached.turn_count == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
