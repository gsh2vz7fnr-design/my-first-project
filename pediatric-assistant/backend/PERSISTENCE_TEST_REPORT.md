# 数据持久化与跨会话测试报告

**测试日期**: 2025-02-12
**测试人员**: persistence-tester
**测试范围**: 儿科助手后端数据持久化机制

---

## 一、执行摘要

本次测试全面评估了儿科助手后端的数据持久化机制，包括：
- 会话内数据更新
- 跨会话数据保留
- 用户数据隔离
- 并发访问安全性
- 缓存一致性

### 测试结果概览

| 测试类别 | 测试数量 | 通过 | 失败 | 通过率 |
|---------|---------|------|------|--------|
| 现有持久化测试 | 11 | 11 | 0 | 100% |
| 新增跨会话测试 | 21 | 21 | 0 | 100% |
| **合计** | **32** | **32** | **0** | **100%** |

---

## 二、持久化机制分析

### 2.1 数据存储架构

系统使用 **SQLite** 作为主要持久化存储，数据存储在 `data/pediatric_assistant.db`。

#### 核心数据表

| 表名 | 用途 | 主键 | 索引 |
|-----|------|------|------|
| `medical_contexts` | 对话上下文 | `conversation_id` | `user_id` |
| `conversation_messages` | 消息历史 | `id (auto)` | - |
| `conversations` | 对话元数据 | `id` | `user_id` |
| `profiles` | 用户健康档案 | `user_id` | - |
| `members` | 家庭成员档案 | `id` | `user_id` |
| `task_queue` | 延迟任务队列 | `id` | `status`, `execute_at` |

### 2.2 核心服务类

| 服务类 | 文件位置 | 主要功能 |
|--------|---------|---------|
| `ConversationStateService` | `services/conversation_state_service.py` | 医疗上下文持久化 |
| `ConversationService` | `services/conversation_service.py` | 对话历史管理 |
| `ProfileService` | `services/profile_service.py` | 用户档案管理 |

### 2.3 数据模型

```python
MedicalContext:
    - conversation_id: str      # 对话ID（主键）
    - user_id: str             # 用户ID
    - dialogue_state: Enum     # 对话状态
    - current_intent: Enum     # 当前意图
    - symptom: str             # 主要症状
    - slots: Dict              # 累积实体槽位
    - triage_level: str        # 分诊级别
    - turn_count: int          # 对话轮次
    - created_at/updated_at: datetime
```

---

## 三、测试详情

### 3.1 会话内数据更新测试

#### 测试用例 1: 多轮对话中的上下文更新
**文件**: `test_cross_session_persistence.py::TestInSessionUpdates`

**测试场景**:
1. 第一轮：用户提供症状"发烧"和年龄"8个月"
2. 第二轮：追加体温"38.5度"和持续时间"1天"

**测试结果**: PASSED
- 数据正确累积
- 原有数据被保留
- 新数据正确追加

#### 测试用例 2: 实体累积机制
**测试场景**: 使用 `merge_entities()` 方法合并多轮实体

**关键发现**:
- 代码逻辑正确实现了 last-write-wins 策略
- 空值（None、空字符串）不会覆盖已有数据
- `accompanying_symptoms` 字段特殊处理为追加模式

### 3.2 跨会话数据保留测试

#### 测试用例 3: 服务重启后数据保留
**测试结果**: PASSED

**验证方法**:
1. 使用同一个数据库文件创建两个不同的 `ConversationStateService` 实例
2. 第一个实例保存数据
3. 第二个实例加载数据
4. 验证数据完整性

**结论**: 数据正确持久化到 SQLite，重启后可恢复。

#### 测试用例 4: 对话历史持久化
**测试结果**: PASSED

**验证点**:
- 消息按正确顺序存储
- 角色字段（user/assistant）正确保存
- 多条消息可完整恢复

### 3.3 用户数据隔离测试

#### 测试用例 5: 用户上下文隔离
**测试结果**: PASSED

**验证**:
- 用户1只能看到自己的对话上下文
- 用户2只能看到自己的对话上下文
- `get_user_contexts()` 正确按 `user_id` 过滤

#### 测试用例 6: 用户档案隔离
**测试结果**: PASSED

**验证**:
- 每个用户的档案数据独立存储
- 加载时按 `user_id` 精确匹配

### 3.4 数据一致性测试

#### 测试用例 7: JSON 序列化往返
**测试结果**: PASSED

**关键验证点**:
- 枚举类型正确序列化/反序列化
- datetime 类型正确转换为 ISO 格式
- 嵌套字典结构完整保留
- 特殊字符（中文）正确处理

#### 测试用例 8: 空值不覆盖已有数据
**测试结果**: PASSED

**代码逻辑** (`conversation_state_service.py:112-114`):
```python
if value is None or value == "":
    continue  # 跳过空值，不覆盖
```

### 3.5 并发访问测试

#### 测试用例 9: 多线程同时写入同一上下文
**测试结果**: PASSED

**测试方法**:
- 启动 5 个线程
- 每个线程执行 10 次写入操作
- 验证无异常且最终状态正确

**关键发现**:
- 代码使用 `threading.Lock()` 保护临界区
- 所有数据库操作都在 `with self._lock` 保护下执行
- 未发现数据竞争或损坏

#### 测试用例 10: 多线程写入不同上下文
**测试结果**: PASSED

**验证**:
- 并发创建 10 个不同对话
- 涉及 3 个不同用户
- 所有数据正确隔离和保存

### 3.6 缓存一致性测试

#### 测试用例 11: 缓存与数据库同步
**测试结果**: PASSED

**验证点**:
- `save_medical_context()` 更新缓存
- 缓存清除后从数据库重新加载
- 缓存中的实例与数据库内容一致

---

## 四、发现的问题与风险

### 4.1 数据丢失风险

#### 风险 1: 数据库未初始化时数据仅存内存
**严重程度**: 中等

**位置**: `conversation_state_service.py:251-253`
```python
if not self._db_initialized:
    # 数据库未初始化，只保存到内存
    return True
```

**风险说明**:
- 如果 `init_db()` 未被调用，数据只存在内存中
- 服务重启后数据会丢失

**改进建议**:
1. 在 `__init__` 中自动调用 `init_db()`
2. 或在首次保存时自动初始化

#### 风险 2: SQLite 无显式事务处理
**严重程度**: 低

**位置**: 所有数据库操作

**风险说明**:
- 当前代码使用自动提交模式
- 多条相关操作不在同一事务中
- 如果中途失败可能导致部分数据不一致

**示例场景**:
```python
# conversation_service.py:67-122
# 插入消息和更新对话元数据不在同一事务中
conn.execute("INSERT INTO conversation_messages ...")  # 可能成功
conn.execute("UPDATE conversations ...")                # 可能失败
```

**改进建议**:
```python
with self._connect() as conn:
    try:
        conn.execute("BEGIN")
        # 多个操作
        conn.execute("INSERT ...")
        conn.execute("UPDATE ...")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
```

### 4.2 隔离性问题

#### 问题 1: conversation_id 碰撞风险
**严重程度**: 低

**位置**: 多处

**风险说明**:
- `conversation_id` 作为主键，如果生成策略不当可能碰撞
- 当前没有检查机制防止用户访问他人的对话（如果知道了 conversation_id）

**改进建议**:
1. 检查 `user_id` 匹配后再返回数据
2. 在 `load_medical_context` 中验证 `user_id`

```python
def load_medical_context(self, conversation_id: str, user_id: str):
    # ... 现有代码 ...
    if row:
        ctx = MedicalContext.from_db_json(row[0])
        # 添加用户验证
        if ctx.user_id != user_id:
            logger.warning(f"用户 {user_id} 尝试访问 {ctx.user_id} 的对话")
            return None
        return ctx
```

#### 问题 2: 删除操作缺少用户验证
**严重程度**: 中等

**位置**: `conversation_state_service.py:285-318`

**风险说明**:
```python
def delete_medical_context(self, conversation_id: str) -> bool:
    # 删除操作没有验证 user_id
    cursor.execute("DELETE FROM medical_contexts WHERE conversation_id = ?",
                   (conversation_id,))
```

**改进建议**:
```python
def delete_medical_context(self, conversation_id: str, user_id: str) -> bool:
    cursor.execute(
        "DELETE FROM medical_contexts WHERE conversation_id = ? AND user_id = ?",
        (conversation_id, user_id)
    )
```

### 4.3 并发问题

#### 问题 1: 缓存与数据库的最终一致性
**严重程度**: 低

**位置**: `conversation_state_service.py:246-249`

**风险说明**:
```python
# 更新缓存
self._context_cache[ctx.conversation_id] = ctx
ctx.updated_at = datetime.now()

if not self._db_initialized:
    return True  # 仅缓存，未写DB

# ... 后续数据库操作可能失败 ...
```

如果数据库操作失败，缓存已经被修改，可能导致不一致。

**改进建议**:
1. 先保存数据库，成功后再更新缓存
2. 或在数据库失败时回滚缓存修改

### 4.4 性能问题

#### 问题 1: 每次操作都重新连接数据库
**严重程度**: 低

**位置**: 所有 `_connect()` 使用处

**影响**:
- 频繁的连接创建/关闭
- 每次查询都有锁竞争

**改进建议**:
考虑使用连接池，但对于 SQLite 单文件模式，当前方式也是可接受的。

---

## 五、改进建议优先级

### 高优先级
1. **添加用户验证到所有操作** - 防止越权访问
2. **自动初始化数据库** - 防止未初始化导致数据丢失

### 中优先级
3. **添加事务支持** - 保证数据一致性
4. **改进错误处理** - 数据库操作失败时回滚缓存

### 低优先级
5. **添加连接池** - 提升性能（对 SQLite 影响有限）
6. **添加数据版本控制** - 支持数据结构迁移

---

## 六、代码示例改进

### 改进 1: 添加事务支持

```python
@contextmanager
def _transaction(self):
    """事务上下文管理器"""
    with self._connect() as conn:
        try:
            conn.execute("BEGIN")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

def append_message(self, conversation_id: str, user_id: str, role: str, content: str) -> None:
    """追加消息（带事务）"""
    with self._transaction() as conn:
        # 插入消息
        conn.execute("INSERT INTO conversation_messages ...", (...))

        # 更新对话元数据
        conn.execute("UPDATE conversations ...", (...))

        # 要么全部成功，要么全部回滚
```

### 改进 2: 添加用户验证

```python
def load_medical_context(self, conversation_id: str, user_id: str) -> Optional[MedicalContext]:
    """加载医疗上下文（带用户验证）"""
    with self._lock:
        # ... 缓存检查 ...

        if self._db_initialized:
            try:
                conn = sqlite3.connect(self._db_path)
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT context_json, user_id FROM medical_contexts WHERE conversation_id = ?",
                    (conversation_id,)
                )
                row = cursor.fetchone()
                conn.close()

                if row:
                    # 验证用户
                    if row[1] != user_id:
                        logger.warning(f"用户 {user_id} 无权访问对话 {conversation_id}")
                        return None

                    ctx = MedicalContext.from_db_json(row[0])
                    self._context_cache[conversation_id] = ctx
                    return ctx
            except Exception as e:
                logger.error(f"[ConversationState] 加载上下文失败: {e}")

        # ... 创建新上下文 ...
```

---

## 七、测试覆盖率

当前测试覆盖的功能点：

| 功能 | 测试覆盖 |
|-----|---------|
| MedicalContext 创建 | 是 |
| MedicalContext 序列化/反序列化 | 是 |
| 多轮实体累积 | 是 |
| 对话状态转换 | 是 |
| SQLite 持久化 | 是 |
| 服务重启恢复 | 是 |
| 用户隔离 | 是 |
| 并发访问 | 是 |
| 缓存一致性 | 是 |
| 删除操作 | 是 |

**缺失的测试**:
- 大数据量场景（1000+ 对话）
- 网络故障模拟
- 磁盘空间不足
- 数据库文件损坏恢复

---

## 八、结论

### 总结
儿科助手后端的数据持久化机制**基本可靠**，核心功能测试全部通过。

### 优点
1. SQLite 存储稳定可靠
2. 内存缓存提升性能
3. 线程安全保护充分
4. 数据模型设计合理

### 需要关注
1. 缺少显式事务处理
2. 用户权限验证不够严格
3. 数据库初始化依赖手动调用
4. 部分操作缺少失败回滚

### 建议
建议在下一个迭代中：
1. 实现高优先级改进
2. 添加压力测试
3. 完善错误监控和日志

---

**报告结束**
