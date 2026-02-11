# 重构计划：动态病例单 (Dynamic Medical Context)

## Context

系统当前的对话管理逻辑存在严重架构问题：`chat.py` 路由文件超过 1050 行，`slot_filling` 和 `triage` 两条路径共享 90% 相同逻辑但完全复制了两遍（send + stream 端点又各复制一遍，实际是 4 份）。刚修复的"重复询问年龄" Bug 虽然通过 `ConversationStateService` 临时解决，但状态是纯内存的（重启丢失），且实体合并逻辑仍散落在路由层各处。本次重构目标：引入正式的 `MedicalContext` 数据模型和 `DialogueStateMachine`，将对话管理从路由层抽离为独立的 Pipeline 服务。

## 1. MedicalContext 数据模型

**新建文件**: `backend/app/models/medical_context.py`

```python
class DialogueState(str, Enum):
    INITIAL = "initial"                   # 首条消息
    COLLECTING_SLOTS = "collecting_slots" # 追问中
    READY_FOR_TRIAGE = "ready_for_triage" # 槽位齐全
    TRIAGE_COMPLETE = "triage_complete"   # 已出决策
    DANGER_DETECTED = "danger_detected"   # 危险信号
    RAG_QUERY = "rag_query"              # 知识检索
    GREETING = "greeting"                 # 问候

class IntentType(str, Enum):
    GREETING = "greeting"
    TRIAGE = "triage"
    SLOT_FILLING = "slot_filling"
    CONSULT = "consult"
    MEDICATION = "medication"
    CARE = "care"

class MedicalContext(BaseModel):
    conversation_id: str
    user_id: str
    dialogue_state: DialogueState = DialogueState.INITIAL
    current_intent: Optional[IntentType] = None
    chief_complaint: Optional[str] = None      # 用户首次原始描述
    symptom: Optional[str] = None              # 归一化症状键
    slots: Dict[str, Any] = {}                 # 所有累积实体
    triage_level: Optional[str] = None         # 分诊结果
    triage_reason: Optional[str] = None
    triage_action: Optional[str] = None
    danger_signal: Optional[str] = None
    turn_count: int = 0
    created_at: datetime
    updated_at: datetime

    def merge_entities(self, new_entities: Dict[str, Any]) -> None:
        """合并实体：非空值覆盖旧值，保留未更新的历史实体"""
        for key, value in new_entities.items():
            if value is not None and value != "":
                self.slots[key] = value
        if "symptom" in self.slots:
            self.symptom = self.slots["symptom"]
```

**设计要点**：
- `slots` 是扁平 Dict，保留现有 13 个实体键名不变
- `missing_slots` 不存储在模型上，每次实时计算（通过 `triage_engine.get_missing_slots()`）
- 可序列化为 JSON 存入 SQLite

## 2. 对话状态机

**新建文件**: `backend/app/services/dialogue_state_machine.py`

```
class Action(Enum):
    SEND_GREETING        # 返回问候
    ASK_FOR_SYMPTOM      # 追问主要症状
    SEND_DANGER_ALERT    # 危险信号告警
    ASK_MISSING_SLOTS    # 追问缺失槽位
    MAKE_TRIAGE_DECISION # 执行分诊决策
    RUN_RAG_QUERY        # 知识库检索

class DialogueStateMachine:
    def transition(ctx, intent, danger_alert, missing_slots, has_symptom)
        -> TransitionResult(new_state, action, metadata)
```

**状态流转逻辑**（伪代码）：
```
IF intent == GREETING       → GREETING,          SEND_GREETING
IF intent in [CONSULT, ..]  → RAG_QUERY,         RUN_RAG_QUERY
# --- 以下为 triage / slot_filling 统一路径 ---
IF no symptom               → COLLECTING_SLOTS,  ASK_FOR_SYMPTOM
IF danger_alert              → DANGER_DETECTED,   SEND_DANGER_ALERT
IF missing_slots             → COLLECTING_SLOTS,  ASK_MISSING_SLOTS
ELSE                        → READY_FOR_TRIAGE,  MAKE_TRIAGE_DECISION
```

**核心设计**：`triage` 和 `slot_filling` 走**同一条路径**，消除 4 份重复代码。状态机是纯逻辑无 I/O，可直接单元测试。

## 3. ChatPipeline 统一处理流水线

**新建文件**: `backend/app/services/chat_pipeline.py`

`process_message(user_id, message, conversation_id?)` → `PipelineResult`

**10 步流水线**：
```
1. 解析 conversation_id，加载 MedicalContext
2. 处方意图安全拦截
3. 加载用户档案，LLM 提取意图+实体
4. 合并实体到 MedicalContext.slots
5. 首次 triage 消息记为 chief_complaint
6. 必要时从历史恢复 symptom
7. 危险信号检查
8. 计算缺失槽位
9. 状态机决定 action → 执行 action → 生成响应
10. 持久化 MedicalContext + 保存对话消息
```

**PipelineResult** 数据类：
```python
@dataclass
class PipelineResult:
    conversation_id: str
    message: str
    sources: List[Dict] = []
    metadata: Dict[str, Any] = {}

    def to_api_response(self) -> dict:  # /send 端点直接使用
    # /stream 端点读取 message 分块 SSE 输出
```

**Slot UI 辅助函数**（`_get_slot_type` 等 6 个函数）从 `chat.py` 迁移到此文件。

## 4. 存储持久化

**修改文件**: `backend/app/services/conversation_state_service.py`

- 新增 SQLite 表 `medical_contexts`（`conversation_id PK, user_id, context_json, created_at, updated_at`）
- 新增方法：`load_medical_context(conv_id, user_id)` / `save_medical_context(ctx)`
- 保留内存缓存避免每轮 DB 读取
- 保留 `merge_entities()` / `get_entities()` 向后兼容接口（内部代理到 MedicalContext）

**修改文件**: `backend/app/main.py`
- lifespan 中增加 `conversation_state_service.init_db()`

## 5. 路由层瘦身

**修改文件**: `backend/app/routers/chat.py`

从 ~1050 行 → ~120 行业务逻辑（加上不变的 CRUD 端点）。

```python
@router.post("/send")
async def send_message(request: ChatRequest):
    result = await get_chat_pipeline().process_message(
        user_id=request.user_id,
        message=request.message,
        conversation_id=request.conversation_id
    )
    return result.to_api_response()

@router.post("/stream")
async def send_message_stream(request: ChatRequest):
    async def generate():
        result = await get_chat_pipeline().process_message(...)
        yield metadata_chunk
        for text_chunk in split(result.message):
            yield content_chunk  # + StreamSafetyFilter
        yield done_chunk
    return StreamingResponse(generate(), ...)
```

CRUD 端点（`/history`, `/source`, `/conversations`）保持不变。

## 6. 不变的部分

以下服务接口完全不修改：
- `llm_service.extract_intent_and_entities()` — 意图+实体提取
- `triage_engine.check_danger_signals()` / `get_missing_slots()` / `make_triage_decision()` — 分诊引擎
- `conversation_service` — 对话消息持久化
- `profile_service` — 用户档案管理
- `safety_filter` / `StreamSafetyFilter` — 安全过滤
- 所有 JSON 规则文件（slot_definitions, danger_signals, triage_rules）
- 前端 API 契约（请求/响应格式、SSE 流式协议、metadata 结构）

## 7. 分步实施计划

### Phase 1: 基础模型（无行为变更）
| 步骤 | 文件 | 操作 |
|-----|------|------|
| 1.1 | `app/models/medical_context.py` | 新建：DialogueState, IntentType, MedicalContext |
| 1.2 | `app/services/dialogue_state_machine.py` | 新建：DialogueStateMachine, Action, TransitionResult |
| 1.3 | `tests/test_medical_context.py` | 新建：merge_entities、序列化测试 |
| 1.4 | `tests/test_dialogue_state_machine.py` | 新建：所有状态转移路径测试 |

### Phase 2: 存储升级（向后兼容）
| 步骤 | 文件 | 操作 |
|-----|------|------|
| 2.1 | `app/services/conversation_state_service.py` | 改造：SQLite 持久化 + 内存缓存 + 向后兼容接口 |
| 2.2 | `app/main.py` | 增加 `conversation_state_service.init_db()` |
| 2.3 | `tests/test_conversation_state_persistence.py` | 新建：持久化读写测试 |

### Phase 3: Pipeline 构建（与旧代码并行）
| 步骤 | 文件 | 操作 |
|-----|------|------|
| 3.1 | `app/services/chat_pipeline.py` | 新建：ChatPipeline + PipelineResult + slot UI helpers |
| 3.2 | `tests/test_chat_pipeline.py` | 新建：Pipeline 集成测试（mock 外部服务） |
| 3.3 | 验证 | 运行全量测试，确保旧代码不受影响 |

### Phase 4: 路由切换（行为变更点）
| 步骤 | 文件 | 操作 |
|-----|------|------|
| 4.1 | `app/routers/chat.py` | `/send` 切换到 Pipeline（旧代码注释保留） |
| 4.2 | `app/routers/chat.py` | `/stream` 切换到 Pipeline |
| 4.3 | 手动 QA | 测试 7 个场景：问候、完整分诊、多轮追问、slot-filling、危险信号、RAG 咨询、处方拦截 |
| 4.4 | 自动化 | 运行全量测试套件 |

### Phase 5: 清理
| 步骤 | 文件 | 操作 |
|-----|------|------|
| 5.1 | `app/routers/chat.py` | 删除注释掉的旧代码和迁移走的 helper 函数 |
| 5.2 | `app/services/conversation_state_service.py` | 移除纯内存 `_state` dict（已被 SQLite 替代） |
| 5.3 | 删除 | `BUGFIX_ENTITY_ACCUMULATION.md`, `VERIFICATION_GUIDE.md`（临时文档） |

## 8. 回滚策略

在 `config.py` 中添加 feature flag：
```python
USE_NEW_PIPELINE: bool = True
```

路由层检查此标志，True 走新 Pipeline，False 走旧内联代码。旧代码在 Phase 5 之前保持注释状态，支持随时回滚。

## 9. 验证方案

### 单元测试
- `test_medical_context.py` — merge_entities、JSON 序列化/反序列化
- `test_dialogue_state_machine.py` — 7 种状态转移路径覆盖
- `test_conversation_state_persistence.py` — SQLite 读写/缓存一致性

### 集成测试
- `test_chat_pipeline.py` — Mock 所有外部服务，验证每种 intent 路径的 PipelineResult

### E2E 测试
```bash
# 启动后端
.venv/bin/python3 -m app.main

# 测试完整分诊流程（3 轮对话）
curl -X POST .../api/v1/chat/send -d '{"user_id":"t1","message":"宝宝8个月发烧38.5度精神不好"}'
# 验证：提取 age=8, temp=38.5, symptom=发烧, mental_state=精神不好
# 验证：只追问 duration（不追问 age）

curl -X POST .../api/v1/chat/send -d '{"user_id":"t1","conversation_id":"<id>","message":"1天"}'
# 验证：所有槽位齐全，返回分诊决策

# 重启后端，用同一 conversation_id 发消息
# 验证：MedicalContext 从 SQLite 恢复，不丢失实体
```

### 回归测试
```bash
.venv/bin/python -m pytest tests/ -v
```
所有现有测试必须继续通过。

## 10. 架构对比

| 维度 | 重构前 | 重构后 |
|------|--------|--------|
| 路由层代码量 | ~1050 行（全部逻辑内联） | ~120 行（薄适配层） |
| 分诊逻辑重复 | 4 份（send/stream × triage/slot_filling） | 1 份（ChatPipeline） |
| 状态存储 | 内存 dict（重启丢失） | SQLite + 内存缓存 |
| 状态转移 | ad-hoc if/elif | 正式 DialogueStateMachine |
| 实体管理 | 散落的 dict 传递 | MedicalContext.merge_entities() |
| 可测试性 | 必须走 HTTP 端点 | Pipeline 和状态机可直接单元测试 |
| 病例记录 | 无正式对象 | MedicalContext（含主诉、分诊结果） |
