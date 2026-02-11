"""
ConversationStateService 持久化测试

测试 SQLite 持久化功能：
- 保存和加载 MedicalContext
- 重启后状态恢复
- 缓存机制
"""
import pytest
import tempfile
import os

from app.services.conversation_state_service import ConversationStateService
from app.models.medical_context import (
    MedicalContext,
    DialogueState,
    IntentType
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
def service_with_db(temp_db):
    """创建带数据库的服务实例"""
    service = ConversationStateService(db_path=temp_db)
    service.init_db()
    return service


def test_init_db_creates_table(service_with_db, temp_db):
    """测试数据库初始化创建表"""
    import sqlite3
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()

    # 检查表是否存在
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='medical_contexts'
    """)
    result = cursor.fetchone()
    assert result is not None

    # 检查列
    cursor.execute("PRAGMA table_info(medical_contexts)")
    columns = {row[1] for row in cursor.fetchall()}
    assert "conversation_id" in columns
    assert "user_id" in columns
    assert "context_json" in columns
    assert "created_at" in columns
    assert "updated_at" in columns

    conn.close()


def test_save_and_load_medical_context(service_with_db):
    """测试保存和加载 MedicalContext"""
    ctx = MedicalContext(
        conversation_id="conv_001",
        user_id="user_001",
        dialogue_state=DialogueState.COLLECTING_SLOTS,
        current_intent=IntentType.TRIAGE,
        symptom="发烧",
        slots={"age_months": 8, "temperature": "38.5度"}
    )

    # 保存
    success = service_with_db.save_medical_context(ctx)
    assert success is True

    # 加载
    loaded = service_with_db.load_medical_context("conv_001", "user_001")

    assert loaded is not None
    assert loaded.conversation_id == "conv_001"
    assert loaded.user_id == "user_001"
    assert loaded.dialogue_state == DialogueState.COLLECTING_SLOTS
    assert loaded.symptom == "发烧"
    assert loaded.slots["age_months"] == 8
    assert loaded.slots["temperature"] == "38.5度"


def test_load_nonexistent_context_creates_new(service_with_db):
    """测试加载不存在的上下文时创建新的"""
    ctx = service_with_db.load_medical_context("new_conv", "user_001")

    assert ctx is not None
    assert ctx.conversation_id == "new_conv"
    assert ctx.user_id == "user_001"
    assert ctx.dialogue_state == DialogueState.INITIAL
    assert ctx.slots == {}


def test_save_updates_existing_context(service_with_db):
    """测试保存更新已存在的上下文"""
    # 创建初始上下文
    ctx = MedicalContext(
        conversation_id="conv_002",
        user_id="user_002",
        slots={"symptom": "咳嗽"}
    )
    service_with_db.save_medical_context(ctx)

    # 更新
    ctx.slots = {"symptom": "咳嗽", "duration": "2天"}
    ctx.dialogue_state = DialogueState.READY_FOR_TRIAGE
    service_with_db.save_medical_context(ctx)

    # 重新加载
    loaded = service_with_db.load_medical_context("conv_002", "user_002")
    assert loaded.slots["duration"] == "2天"
    assert loaded.dialogue_state == DialogueState.READY_FOR_TRIAGE


def test_delete_medical_context(service_with_db):
    """测试删除 MedicalContext"""
    ctx = MedicalContext(
        conversation_id="conv_003",
        user_id="user_003"
    )
    service_with_db.save_medical_context(ctx)

    # 删除
    success = service_with_db.delete_medical_context("conv_003")
    assert success is True

    # 验证已删除
    loaded = service_with_db.load_medical_context("conv_003", "user_003")
    # 应该创建新的（因为旧的已删除）
    assert loaded.dialogue_state == DialogueState.INITIAL


def test_cache_reduces_db_access(service_with_db):
    """测试缓存减少数据库访问"""
    ctx = MedicalContext(
        conversation_id="conv_cache",
        user_id="user_cache",
        slots={"symptom": "发烧"}
    )
    service_with_db.save_medical_context(ctx)

    # 第一次加载 - 从数据库
    loaded1 = service_with_db.load_medical_context("conv_cache", "user_cache")
    assert loaded1.slots["symptom"] == "发烧"

    # 修改缓存中的对象
    loaded1.slots["temperature"] = "39度"

    # 第二次加载 - 应该从缓存获取（包含修改）
    loaded2 = service_with_db.load_medical_context("conv_cache", "user_cache")
    assert loaded2.slots["temperature"] == "39度"


def test_clear_cache(service_with_db):
    """测试清空缓存"""
    ctx = MedicalContext(
        conversation_id="conv_clear",
        user_id="user_clear",
        slots={"symptom": "发烧"}
    )
    service_with_db.save_medical_context(ctx)

    # 清空缓存
    service_with_db.clear_cache()

    # 重新加载应该从数据库
    loaded = service_with_db.load_medical_context("conv_clear", "user_clear")
    assert loaded.slots["symptom"] == "发烧"


def test_get_user_contexts(service_with_db):
    """测试获取用户的所有对话上下文"""
    # 创建多个对话
    ctx1 = MedicalContext(
        conversation_id="conv_1",
        user_id="user_multi",
        slots={"symptom": "发烧"}
    )
    ctx2 = MedicalContext(
        conversation_id="conv_2",
        user_id="user_multi",
        slots={"symptom": "咳嗽"}
    )
    ctx3 = MedicalContext(
        conversation_id="conv_3",
        user_id="other_user",
        slots={"symptom": "呕吐"}
    )

    service_with_db.save_medical_context(ctx1)
    service_with_db.save_medical_context(ctx2)
    service_with_db.save_medical_context(ctx3)

    # 获取用户的所有对话
    contexts = service_with_db.get_user_contexts("user_multi")

    assert len(contexts) == 2
    conv_ids = {ctx.conversation_id for ctx in contexts}
    assert "conv_1" in conv_ids
    assert "conv_2" in conv_ids
    assert "conv_3" not in conv_ids


def test_backward_compatible_get_entities(service_with_db):
    """测试向后兼容的 get_entities 方法"""
    ctx = MedicalContext(
        conversation_id="conv_compat",
        user_id="user_compat",
        symptom="发烧",
        slots={"age_months": 8}
    )
    service_with_db.save_medical_context(ctx)

    entities = service_with_db.get_entities("conv_compat")

    assert entities["symptom"] == "发烧"
    assert entities["age_months"] == 8


def test_backward_compatible_merge_entities(service_with_db):
    """测试向后兼容的 merge_entities 方法"""
    # 第一轮
    entities1 = {"symptom": "发烧", "age_months": 8}
    merged1 = service_with_db.merge_entities("conv_merge", entities1)
    assert merged1["symptom"] == "发烧"
    assert merged1["age_months"] == 8

    # 第二轮
    entities2 = {"temperature": "38.5度", "duration": "1天"}
    merged2 = service_with_db.merge_entities("conv_merge", entities2)
    assert merged2["symptom"] == "发烧"
    assert merged2["age_months"] == 8
    assert merged2["temperature"] == "38.5度"
    assert merged2["duration"] == "1天"


def test_backward_compatible_clear_entities(service_with_db):
    """测试向后兼容的 clear_entities 方法"""
    ctx = MedicalContext(
        conversation_id="conv_clear_compat",
        user_id="user_clear_compat",
        slots={"symptom": "发烧"}
    )
    service_with_db.save_medical_context(ctx)

    # 清除
    service_with_db.clear_entities("conv_clear_compat")

    # 验证已清除
    entities = service_with_db.get_entities("conv_clear_compat")
    assert entities == {}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
