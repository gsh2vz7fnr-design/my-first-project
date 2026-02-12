# 动态问诊单系统 — 架构设计文档

> **文档版本**: v2.0
> **日期**: 2026-02-12
> **状态**: 评审修订版

---

## 目录

1. [改造动机](#1-改造动机)
2. [核心数据模型设计](#2-核心数据模型设计)
3. [生命周期与状态流转](#3-生命周期与状态流转)
4. [数据示例](#4-数据示例)
5. [验收标准](#5-验收标准)
6. [集成改造路线图](#6-集成改造路线图)

---

## 1. 改造动机

### 1.1 现有 MedicalContext 的具体问题

| 问题 | 现状 | 影响 |
|------|------|------|
| 分诊数据分散 | `triage_level`、`triage_reason`、`triage_action` 分别作为独立字段存储（`medical_context.py:72-82`） | 读取分诊结果需要拼装 3 个字段，无法作为独立快照传递给前端或写入用户档案 |
| 缺少结构化对话日志 | 对话记录存储在 `conversation_messages` 表，仅有 `role` + `content`，无元数据 | 无法追溯每轮对话中提取了哪些实体、触发了什么分诊结果，不利于质量回溯 |
| 缓存无淘汰机制 | `_context_cache` 为普通 dict，只增不减（`conversation_state_service.py`） | 长期运行后内存持续增长 |

### 1.2 本次改造不做的事

| 项目 | 理由 |
|------|------|
| 不改 Session ID 格式 | 现有 `conv_{uuid12}` 格式功能完整，改格式带来兼容成本但收益有限。按时间排序可直接查 `created_at` 字段 |
| 不引入归档机制 | 30 分钟超时归档会中断用户问诊体验（家长可能去量体温、喂药后回来继续）。内存管理用 LRU 缓存淘汰即可，不需要改变业务状态 |
| 不强制意图轨迹列表 | 当前系统没有消费意图历史的场景，`current_intent` 足够状态机决策。预留扩展接口但不在本期实现 |

### 1.3 改造范围总结

本次改造聚焦于 **数据结构整合** 和 **可观测性增强**，具体包括：

1. **triage_snapshot 聚合**：将分散的分诊字段聚合为独立快照，分诊完成时一次性写入
2. **dialogue_logs 增强**：在现有对话记录基础上增加元数据（每轮提取的实体增量、分诊结果）
3. **LRU 缓存淘汰**：替换现有的无限增长 dict 缓存
4. **状态扩展**：新增 `COMPLETED` 状态，区分"分诊完成但用户可能继续提问"与"正在收集信息"

---

## 2. 核心数据模型设计

### 2.1 MedicalContext 改造（增量修改，非全量替换）

在现有 `MedicalContext` 模型基础上进行增量修改，**不新建 ConsultationRecord 类**：

```
现有 MedicalContext 字段保留情况：
+--------------------------------------------------------------------+
|  保留字段（不变）                                                    |
|    conversation_id    -- 保持 conv_{uuid12} 格式                    |
|    user_id                                                          |
|    dialogue_state     -- 扩展枚举值                                  |
|    current_intent     -- 保持单值，后续按需改为列表                    |
|    chief_complaint                                                   |
|    symptom                                                           |
|    slots              -- 即 extracted_entities，保持现有合并逻辑      |
|    danger_signal                                                     |
|    turn_count                                                        |
|    created_at / updated_at                                           |
|                                                                      |
|  新增字段                                                            |
|    triage_snapshot     -- 聚合分诊结果快照（替代分散的 3 个字段）      |
|                                                                      |
|  废弃字段（triage_snapshot 写入后不再单独更新）                        |
|    triage_level        -- 由 triage_snapshot.level 替代              |
|    triage_reason       -- 由 triage_snapshot.reason 替代             |
|    triage_action       -- 由 triage_snapshot.action 替代             |
+--------------------------------------------------------------------+
```

### 2.2 triage_snapshot 结构

```json
{
  "triage_snapshot": {
    "type": ["object", "null"],
    "description": "分诊完成时一次性写入的快照",
    "properties": {
      "level":      { "type": "string", "enum": ["emergency", "urgent", "observe", "online", "self_care"] },
      "reason":     { "type": "string" },
      "action":     { "type": "string" },
      "decided_at": { "type": "string", "format": "date-time" }
    }
  }
}
```

**写入时机**：Pipeline Step 10 中，当 `Action.MAKE_TRIAGE_DECISION` 执行后，一次性写入 `triage_snapshot`。

**向后兼容**：保留 `triage_level` / `triage_reason` / `triage_action` 字段的 getter 方法，内部代理到 `triage_snapshot`，确保下游代码（如前端 metadata 返回）无需同步修改。

### 2.3 dialogue_logs 增强

在现有 `conversation_messages` 表的基础上，为 Bot 回复添加结构化元数据：

```json
{
  "metadata": {
    "intent":         "slot_filling",
    "entities_delta": { "age_months": 8, "temperature": "38.5度" },
    "triage_result":  null,
    "danger_signal":  null
  }
}
```

**实现方式**：在 `conversation_service.append_message()` 中增加可选的 `metadata` 参数，序列化为 JSON 存入新增的 `metadata` 列。

### 2.4 DialogueState 枚举扩展

```python
class DialogueState(str, Enum):
    INITIAL = "initial"
    COLLECTING_SLOTS = "collecting_slots"
    READY_FOR_TRIAGE = "ready_for_triage"
    TRIAGE_COMPLETE = "triage_complete"      # 现有，对应 COMPLETED
    DANGER_DETECTED = "danger_detected"
    RAG_QUERY = "rag_query"
    GREETING = "greeting"
    # 无新增状态。现有 TRIAGE_COMPLETE 已覆盖 "分诊完成" 语义。
    # WAITING_INPUT 不引入 —— Bot 追问后状态为 COLLECTING_SLOTS，语义已足够。
```

**决定不引入的状态**：
- `WAITING_INPUT`：现有 `COLLECTING_SLOTS` 已表达"等待用户补充信息"的语义
- `ARCHIVED`：不引入归档机制，详见 1.2

### 2.5 LRU 缓存替换

将 `conversation_state_service.py` 中的 `_context_cache: Dict` 替换为 `functools.lru_cache` 或手动实现的 LRU dict：

```python
from collections import OrderedDict

class LRUCache:
    """基于 OrderedDict 的 LRU 缓存，限制最大条目数"""

    def __init__(self, max_size: int = 200):
        self._cache = OrderedDict()
        self._max_size = max_size

    def get(self, key: str):
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def put(self, key: str, value):
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = value
        if len(self._cache) > self._max_size:
            self._cache.popitem(last=False)  # 淘汰最久未访问的

    def remove(self, key: str):
        self._cache.pop(key, None)
```

**max_size 选择**：200 个会话的 MedicalContext 内存占用约 10-20MB，对单体部署足够。被淘汰的条目仍可从 SQLite 重新加载，不影响功能。

---

## 3. 生命周期与状态流转

### 3.1 状态流转图（简化版）

```
                    状态流转总览

    用户首句消息
         |
         v
  +-----------------+     Bot 追问     +-------------------+
  |    INITIAL      |  ------------->  | COLLECTING_SLOTS  |
  |   (首次消息)     |                  |  (收集槽位)        |
  +-----------------+                  +--------+----------+
                                                |
                                       用户补充信息 |  <-- 循环直到槽位充足
                                                |
                                                v
                                       +-------------------+
                                       | READY_FOR_TRIAGE  |
                                       |  (可以分诊)        |
                                       +--------+----------+
                                                |
                                        执行分诊  |
                                                v
                                       +-------------------+
                                       | TRIAGE_COMPLETE   |
                                       |  (分诊完成)        |
                                       +-------------------+
                                                |
                                       用户继续提问 (consult/care/medication)
                                                |
                                                v
                                       +-------------------+
                                       |    RAG_QUERY      |
                                       | (知识查询)         |
                                       +-------------------+

  特殊路径:
  - 任意状态 + 危险信号检出 --> DANGER_DETECTED (紧急就医)
  - 任意状态 + greeting 意图 --> GREETING
```

**与现有系统的关系**：此状态图与当前 `dialogue_state_machine.py` 完全一致，不新增状态。

### 3.2 阶段 A：初始化 (Genesis)

```
触发条件: conversation_state_service 中无对应 MedicalContext

处理流程:
+--------------------------------------------------------------+
| 1. 生成 conversation_id                                       |
|    format: f"conv_{uuid4().hex[:12]}"  (保持现有格式)          |
|                                                               |
| 2. 创建 MedicalContext                                        |
|    - conversation_id = 生成的 ID                               |
|    - user_id = 请求中的 user_id                                |
|    - dialogue_state = INITIAL                                  |
|    - triage_snapshot = None                                    |
|                                                               |
| 3. Pre-fill: 调用 LLM 提取首句实体                             |
|    - chief_complaint = 用户原文                                |
|    - slots = LLM 提取结果 (merge_entities)                    |
|    - current_intent = LLM 识别的意图                           |
|                                                               |
| 4. Profile Auto-fill: 从用户档案补充                           |
|    (现有逻辑不变)                                              |
|                                                               |
| 5. 写入对话记录                                                |
|    conversation_service.append_message(                        |
|      ..., metadata={"entities_delta": 首轮提取的实体}          |
|    )                                                          |
|                                                               |
| 6. 持久化: 写入 SQLite + LRU 缓存                             |
+--------------------------------------------------------------+
```

### 3.3 阶段 B：动态更新 (Live Update)

```
触发条件: 同一 conversation_id 的后续每一轮对话

处理流程:
+--------------------------------------------------------------+
| 1. 加载: 从 LRU 缓存 / SQLite 读取 MedicalContext              |
|                                                               |
| 2. LLM 提取本轮意图 + 实体                                     |
|    (现有 Pipeline Step 4 逻辑不变)                              |
|                                                               |
| 3. 增量合并实体 (现有 merge_entities 逻辑不变)                   |
|    计算 entities_delta = 本轮新增/更新的字段                     |
|                                                               |
| 4. 写入对话记录 (带元数据)                                      |
|    用户消息: append_message(role="user", content=原文)          |
|    Bot回复:  append_message(role="assistant", content=回复,     |
|              metadata={intent, entities_delta, triage_result}) |
|                                                               |
| 5. 如果分诊完成:                                                |
|    triage_snapshot = {                                         |
|      level: decision.level,                                    |
|      reason: decision.reason,                                  |
|      action: decision.action,                                  |
|      decided_at: now()                                         |
|    }                                                          |
|    状态转移到 TRIAGE_COMPLETE                                   |
|    关联用户档案 (现有 schedule_delayed_extraction 逻辑)          |
|                                                               |
| 6. 持久化: 写入 SQLite + 更新 LRU 缓存                         |
+--------------------------------------------------------------+
```

---

## 4. 数据示例

模拟场景：**宝宝 8 个月发烧，后续补充流鼻涕**

### 4.1 MedicalContext 最终状态

```json
{
  "conversation_id": "conv_b7e2a1f9c3d6",
  "user_id": "test_user_001",
  "dialogue_state": "triage_complete",
  "current_intent": "consult",
  "chief_complaint": "我家宝宝8个月大，发烧38.5度，从昨天开始的",
  "symptom": "发烧",
  "slots": {
    "age_months": 8,
    "symptom": "发烧",
    "symptoms": ["发烧", "流鼻涕"],
    "temperature": "38.5度",
    "duration": "1天",
    "mental_state": "有点蔫",
    "accompanying_symptoms": ["流鼻涕", "偶尔咳嗽"],
    "feeding": "吃奶量减少",
    "weight_kg": 8.5
  },
  "triage_snapshot": {
    "level": "observe",
    "reason": "低热伴上呼吸道感染症状，精神尚可",
    "action": "居家观察，体温超39度或精神明显变差时就医",
    "decided_at": "2026-02-11T14:32:18+08:00"
  },
  "danger_signal": null,
  "turn_count": 4,
  "created_at": "2026-02-11T14:30:52+08:00",
  "updated_at": "2026-02-11T14:33:44+08:00"
}
```

### 4.2 增强后的对话记录（conversation_messages 表）

```
turn | speaker | content                                | metadata
-----|---------|----------------------------------------|------------------------------------------
  1  | user    | 我家宝宝8个月大，发烧38.5度...            | null
  1  | bot     | 了解，宝宝发烧确实让人担心...              | {"intent":"slot_filling", "entities_delta":{"age_months":8, "symptom":"发烧", "temperature":"38.5度", "duration":"1天"}}
  2  | user    | 精神有点蔫，吃奶量也减少了                 | null
  2  | bot     | 谢谢您补充。宝宝还有其他症状吗？           | {"intent":"slot_filling", "entities_delta":{"mental_state":"有点蔫", "feeding":"吃奶量减少"}}
  3  | user    | 有流鼻涕，偶尔咳嗽几声                    | null
  3  | bot     | 根据您的描述...分诊建议：居家观察          | {"intent":"triage", "entities_delta":{"accompanying_symptoms":["流鼻涕","偶尔咳嗽"]}, "triage_result":{"level":"observe","reason":"低热伴上呼吸道感染症状"}}
  4  | user    | 可以给宝宝吃退烧药吗？                    | null
  4  | bot     | 8个月宝宝体温38.5度，一般建议先物理降温... | {"intent":"consult", "entities_delta":{}}
```

---

## 5. 验收标准

### 5.1 triage_snapshot 聚合

| # | 检查项 | 验证方法 | 期望结果 |
|---|--------|----------|----------|
| T-1 | 快照写入 | 分诊完成后读取 `ctx.triage_snapshot` | 包含 `level`, `reason`, `action`, `decided_at` 四个字段 |
| T-2 | 快照时机 | 分诊前读取 `ctx.triage_snapshot` | 为 `None` |
| T-3 | 向后兼容 | 分诊完成后读取 `ctx.triage_level` | 返回 `triage_snapshot.level` 的值 |
| T-4 | 持久化 | 分诊完成 -> 重启服务 -> 加载同一会话 | `triage_snapshot` 内容完整恢复 |

### 5.2 dialogue_logs 元数据

| # | 检查项 | 验证方法 | 期望结果 |
|---|--------|----------|----------|
| L-1 | entities_delta 记录 | 第 1 轮提取 `age_months=8` -> 读取 Bot 回复的 metadata | `entities_delta` 包含 `{"age_months": 8}` |
| L-2 | 空 delta | 用户发送"谢谢" -> 读取 Bot 回复的 metadata | `entities_delta` 为 `{}` |
| L-3 | triage_result 记录 | 分诊完成的那轮 -> 读取 Bot 回复的 metadata | `triage_result` 包含 `level` + `reason` |
| L-4 | 用户消息无 metadata | 读取用户消息记录 | `metadata` 为 `null` |

### 5.3 LRU 缓存

| # | 检查项 | 验证方法 | 期望结果 |
|---|--------|----------|----------|
| C-1 | 缓存命中 | 连续访问同一会话 2 次 | 第 2 次从缓存返回，无 SQLite 查询 |
| C-2 | 淘汰生效 | max_size=5，创建 6 个会话 -> 访问第 1 个会话 | 缓存 miss，从 SQLite 重新加载，功能正常 |
| C-3 | 淘汰不丢数据 | 同上，被淘汰的会话数据 | SQLite 中仍完整存在 |

### 5.4 现有功能回归（不可出现退化）

| # | 检查项 | 验证方法 | 期望结果 |
|---|--------|----------|----------|
| R-1 | 实体增量合并 | 多轮对话中逐步补充实体 | `merge_entities` 行为不变 |
| R-2 | 分诊流程 | 完整的多轮分诊对话 | 分诊结果正确 |
| R-3 | RAG 查询 | 分诊后继续咨询 | RAG 回复正常 |
| R-4 | 用户档案自动填充 | 用户档案有 `age_months` -> 首句未提年龄 | 自动补充到 slots |
| R-5 | 危险信号检测 | 输入含危险信号的症状 | 正确触发紧急告警 |

---

## 6. 集成改造路线图

```
Phase 1 - MedicalContext 增量修改 (低风险)
  +-- 新增 triage_snapshot 字段 (Pydantic Optional[dict])
  +-- 添加 triage_snapshot 的 getter 兼容层
  +-- 更新 to_db_json / from_db_json 序列化
  +-- 单元测试: 序列化/反序列化含 triage_snapshot

Phase 2 - Pipeline 集成 (低风险)
  +-- Step 10: MAKE_TRIAGE_DECISION 时写入 triage_snapshot
  +-- Step 10: 计算 entities_delta 并传入 append_message
  +-- conversation_service: append_message 增加 metadata 参数
  +-- conversation_messages 表: ALTER TABLE 增加 metadata 列
  +-- 集成测试: 多轮对话后检查 triage_snapshot 和 metadata

Phase 3 - LRU 缓存 (低风险)
  +-- 实现 LRUCache 类
  +-- 替换 conversation_state_service 中的 _context_cache
  +-- 测试: 淘汰 + 重新加载
```

**总改动量预估**：
- 修改文件: 4 个 (`medical_context.py`, `chat_pipeline.py`, `conversation_service.py`, `conversation_state_service.py`)
- 新增文件: 0 个（LRUCache 可放入 `conversation_state_service.py`）
- 数据库: 1 条 ALTER TABLE（`conversation_messages` 增加 `metadata` 列）
- 无需数据迁移，无需前端改动

---

## 附录：未来可选扩展

以下功能在当前阶段不实施，但预留了扩展路径：

| 扩展项 | 触发条件 | 实现方式 |
|--------|----------|----------|
| 意图轨迹列表 | 需要分析用户意图变迁（如对话质量评估） | 将 `current_intent` 改为 `intents: List[IntentRecord]`，每轮追加 |
| 会话归档 | 有合规要求需要冻结历史记录 | 新增 `ARCHIVED` 状态 + 超时机制 |
| Session ID 含时间戳 | 需要在不查库的情况下按时间排序 | 将 `conv_{uuid12}` 改为 `YYYYMMDD-HHmmss-{uuid12}` |
| 问诊单独立模型 | MedicalContext 字段增长到难以维护 | 提取为独立的 `ConsultationRecord` 类 |
