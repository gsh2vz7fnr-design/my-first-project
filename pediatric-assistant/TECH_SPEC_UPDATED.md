# 智能儿科分诊与护理助手 — 技术方案文档

> **版本**: v4.0 (基于代码审计同步)
> **更新日期**: 2026-02-10
> **文档性质**: 技术实现方案 — 与代码实现完全对齐

---

## 一、方案概览

智能儿科分诊与护理助手将 DeepSeek LLM 的深层语义理解能力与确定性的医学规则引擎深度耦合。系统在严格执行医疗安全零容忍机制的前提下，为用户提供极具共情与个性化的护理指导。

### 核心设计原则

1. **安全优先**：处方拦截 → 危险信号熔断 → 黑名单过滤 → 流式安全检测，四层防线
2. **双重降级**：LLM 不可用时自动降级为本地 Regex 引擎，确保核心功能不中断
3. **有据可查**：所有建议必须溯源到权威知识库，无源则拒答

---

## 二、模块详细方案

### 2.1 意图路由模块 (Intent Router)

**文件**: `app/routers/chat.py`

**处理流程** (按优先级排序):

```
1. 处方意图检测 (SafetyFilter.check_prescription_intent)
   ↓ 未命中
2. LLM 意图与实体提取 (LLMService.extract_intent_and_entities)
   ↓ 失败时降级为 _extract_intent_and_entities_fallback
3. 意图路由分发:
   ├── greeting     → 静态问候语 + 功能介绍
   ├── slot_filling → 症状恢复 → 危险信号检测 → 槽位检查 → 追问/决策
   ├── triage       → 危险信号检测 → 槽位检查 → 追问/决策
   └── consult/medication/care → 情绪检测 → RAG 检索生成 → 安全过滤
4. 后处理:
   ├── 添加免责声明
   ├── 存储对话历史
   └── 异步档案提取任务入队 (30min 延迟)
```

**流式接口特殊处理**:
- 先发送 `type="metadata"` 块（含 intent、triage_level、missing_slots 等）
- 再发送 `type="content"` 块（按 50 字符分块）
- 实时流式安全检测（StreamSafetyFilter）
- 命中违禁词时发送 `type="abort"` 信号

**辅助函数**:
- `_recover_symptom_from_history()`: 从最近 10 条历史中恢复症状
- `_get_slot_type/label/options/min/max/step()`: 12 种槽位的 UI 表单定义

### 2.2 LLM 服务模块 (LLM Service)

**文件**: `app/services/llm_service.py`

**远程可用性管理**:
- `remote_available` 属性：检查 API Key 是否配置 + 冷却期是否结束
- 失败后自动进入 60 秒冷却期，期间所有请求走本地兜底

**意图提取 Prompt 设计**:
```
System: 你是一个专业的儿科医疗意图识别助手...
- 6 种意图类型 (triage/consult/medication/care/greeting/slot_filling)
- 13 种实体字段
- 输出格式: JSON { intent, intent_confidence, entities }
- Temperature: 0.1 (低温确保确定性)
```

**本地兜底规则** (`_extract_intent_and_entities_fallback`):
1. Greeting 检测：完全匹配 + 排除含医疗关键词的混合意图
2. Slot-filling 检测：正则匹配 `key: value` 格式
3. 症状/实体提取：关键词列表 + 正则表达式
4. 置信度：LLM 提取 0.9，本地兜底 0.4

**后处理链**:
1. `_normalize_intent_entities()`: 归一化意图类型和置信度
2. `_normalize_symptom()`: 同义词映射（12 组）
3. `_postprocess_entities()`: 基于原始输入纠错和补全

**情绪检测** (`detect_emotion`):
- 10 个焦虑关键词触发
- 5 种场景化安抚话术（哭闹/发烧/摔倒/呕吐/通用）

**引导提问** (`generate_follow_up_suggestions`):
- 8 类症状 × 3 个引导问题 = 24 个预设问题
- 通用兜底 3 个问题

**档案提取** (`extract_profile_updates`):
- Temperature: 0.1
- 提取字段: baby_info, allergy_history, medical_history, medication_history
- 严格约束: 只提取明确陈述的信息，不推测

---

### 2.3 RAG 检索模块 (RAG Service)

**文件**: `app/services/rag_service.py`

**知识库加载**:
- 启动时遍历 `KNOWLEDGE_BASE_PATH` 下所有 JSON 文件
- 展开 entries，附加 topic 和 category 元数据
- 预构建本地 token 计数索引 (`_build_local_index`)

**自定义分词器** (`_text_to_counter`):
- 优先匹配长医学词汇（按长度降序）：呼吸困难、精神萎靡、拉肚子、腹泻...
- 已匹配部分替换为空格避免重复
- 剩余文本按单字切分（中文字符 + 英文字母数字）

**混合检索** (`_hybrid_search`):
```
1. 语义检索 (70%):
   - SiliconFlow Embedding API (BAAI/bge-m3)
   - 余弦相似度计算
   - 内存缓存避免重复调用

2. 关键词检索 (30%):
   - 自定义分词 + 词频余弦相似度
   - 同义词双向扩展 (口语 ↔ 标准术语)
   - 标题匹配加权 +0.5
   - 标签匹配加权 +0.2 (子字符串匹配)

3. 分数融合:
   - 远程模式: 0.7 × vector + 0.3 × keyword
   - 本地模式: 纯 keyword
   - 召回 Top-50
```

**启发式重排序** (`_rerank`):
```
基于规则模拟 Cross-Encoder:
- 精确短语匹配: +0.2
- 医学实体匹配 (泰诺林/美林): +0.3
- 同义词匹配 (腹泻/发烧/咳嗽/呕吐/皮疹): +0.2
- 阈值过滤: 远程 < 0.3 丢弃, 本地 < 0.1 丢弃
- 输出 Top-3
```

**RAG 生成 Prompt**:
```
System: 你是「小儿安」，一位温暖、专业的儿科健康顾问...
- 优先引用知识库文档
- 可基于儿科常识合理补充，标注"一般建议"
- 绝不编造具体数据
- Markdown 排版规则（标题/列表/加粗/引用块）
- Temperature: 0.3
```

**本地兜底回答** (`_build_fallback_answer`):
- 基于 Top-1 检索结果
- 结构：核心结论 → 操作建议 → 注意事项 → 就医信号 → 引导问题

---

### 2.4 分诊引擎模块 (Triage Engine)

**文件**: `app/services/triage_engine.py`

**数据驱动**:
- `danger_signals.json`: 通用 + 症状特定危险信号
- `fever_rules.json`: 发烧分诊规则（按 priority 排序）
- `slot_definitions.json`: 各症状的必填/选填槽位

**条件匹配引擎** (`_check_condition`):
- 精确匹配: `entity_value == condition`
- 范围条件: `lt`, `lte`, `gt`, `gte`
- 包含条件: `contains`
- 数值转换: 支持阿拉伯数字 + 中文数字（零到十）

**槽位管理**:
1. 从配置读取必填槽位
2. 从用户档案自动填充 (age_months, weight_kg)
3. 轻症放松: 发烧 + 月龄≥3 + 体温<38.5 + 精神正常 → 跳过追问
4. 生成追问: 优先用配置模板，回退到通用模板

**分诊决策链**:
```
1. 危险信号检测 → emergency
2. JSON 规则引擎匹配 → 按 priority 排序
3. 硬编码兜底 (发烧/摔倒/呕吐/腹泻)
4. 默认 → observe ("建议先在家观察")
```

---

### 2.5 安全过滤模块 (Safety Filter)

**文件**: `app/services/safety_filter.py`, `app/services/stream_filter.py`

**SafetyFilter**:
- 启动时加载两份黑名单文件（支持 # 注释）
- 文件不存在时使用硬编码默认值
- `filter_output()`: 先检查通用红线，再检查医疗红线
- `check_prescription_intent()`: 8 个处方关键词匹配
- `add_disclaimer()`: 自动去重的免责声明追加
- `check_stream_output()`: 累积 buffer 检查（跨 chunk 边界检测）

**StreamSafetyFilter**:
- 维护 buffer 和 aborted 标志
- `check_chunk()`: 先检查再追加到 buffer
- `reset()`: 重置状态

---

### 2.6 档案服务模块 (Profile Service)

**文件**: `app/services/profile_service.py`

**三个服务类**:

1. **ProfileService**: 用户档案 + 异步 ETL + 任务队列
2. **MemberProfileService**: 家庭成员 + 体征 + 习惯
3. **HealthHistoryService**: 过敏/病史/家族/用药史

**加上**:
4. **HealthRecordsService**: 问诊/处方/挂号/病历/体检记录

**任务队列实现**:
```python
# SQLite task_queue 表
CREATE TABLE task_queue (
    id TEXT PRIMARY KEY,
    task_type TEXT NOT NULL,      # 'extract_profile'
    payload TEXT NOT NULL,         # JSON: {user_id, conversation_id}
    execute_at TEXT NOT NULL,      # ISO 8601 时间戳
    status TEXT DEFAULT 'pending', # pending/completed/failed/cancelled
    created_at TEXT,
    updated_at TEXT
)

# 后台 worker: asyncio.sleep(60) 轮询
# 每次最多处理 10 个到期任务
```

**BMI 计算**:
```
BMI = weight_kg / (height_cm / 100)²
状态: <18.5 偏瘦 | 18.5-24 正常 | 24-28 偏胖 | ≥28 肥胖
```

---

### 2.7 对话服务模块 (Conversation Service)

**文件**: `app/services/conversation_service.py`

**存储**: SQLite 两张表
- `conversation_messages`: id, conversation_id, user_id, role, content, created_at
- `conversations`: id, user_id, title, message_count, created_at, updated_at

**自动标题**: 首条用户消息前 30 字符

**线程安全**: 所有操作通过 `threading.Lock` 保护

---

### 2.8 性能监控中间件

**文件**: `app/middleware/performance.py`

**功能**:
- 记录每个端点的响应时间（毫秒）
- 计算统计指标: min, max, avg, median, std_dev, P50/P90/P95/P99
- 添加响应头: `X-Response-Time`, `X-Response-Time-ms`
- 慢请求告警: >1s 警告, >2s 错误
- 提供 `/metrics/performance` 端点查看统计

---

## 三、数据库 Schema

### 3.1 SQLite 表结构

```sql
-- 用户档案
CREATE TABLE profiles (
    user_id TEXT PRIMARY KEY,
    baby_info TEXT,              -- JSON
    allergy_history TEXT,        -- JSON Array
    medical_history TEXT,        -- JSON Array
    medication_history TEXT,     -- JSON Array
    pending_confirmations TEXT,  -- JSON Array
    created_at TEXT,
    updated_at TEXT
);

-- 对话消息
CREATE TABLE conversation_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT,
    user_id TEXT,
    role TEXT,                   -- 'user' | 'assistant'
    content TEXT,
    created_at TEXT
);

-- 对话元数据
CREATE TABLE conversations (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    title TEXT,
    message_count INTEGER DEFAULT 0,
    created_at TEXT,
    updated_at TEXT
);

-- 任务队列
CREATE TABLE task_queue (
    id TEXT PRIMARY KEY,
    task_type TEXT NOT NULL,
    payload TEXT NOT NULL,
    execute_at TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    created_at TEXT,
    updated_at TEXT
);

-- 家庭成员
CREATE TABLE members (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    relationship TEXT NOT NULL,
    id_card_type TEXT DEFAULT 'id_card',
    id_card_number TEXT,
    gender TEXT NOT NULL,
    birth_date TEXT NOT NULL,
    phone TEXT,
    avatar_url TEXT,
    created_at TEXT,
    updated_at TEXT
);

-- 体征信息
CREATE TABLE vital_signs (
    member_id TEXT PRIMARY KEY,
    height_cm REAL NOT NULL,
    weight_kg REAL NOT NULL,
    bmi REAL,
    bmi_status TEXT,
    blood_pressure_systolic INTEGER,
    blood_pressure_diastolic INTEGER,
    blood_sugar REAL,
    blood_sugar_type TEXT,
    updated_at TEXT
);

-- 生活习惯
CREATE TABLE health_habits (
    member_id TEXT PRIMARY KEY,
    diet_habit TEXT,
    exercise_habit TEXT,
    sleep_quality TEXT,
    smoking_drinking TEXT,
    sedentary_habit TEXT,
    mental_status TEXT,
    updated_at TEXT
);

-- 过敏史 / 既往病史 / 家族病史 / 用药史
-- (各含 member_id 外键, ON DELETE CASCADE)

-- 问诊记录 / 处方记录 / 挂号记录 / 病历存档 / 体检记录
-- (各含 member_id 外键, ON DELETE CASCADE)
```

---

## 四、前端技术方案

### 4.1 架构

- **纯 Vanilla JavaScript (ES6)**，无框架依赖
- **组件模式**: `export function createXXX()` 返回 `{ element, refs?, bindEvents? }`
- **样式系统**: CSS Variables (themes.css) + Critical CSS + 主样式
- **响应式**: Mobile-first，断点 480px / 768px / 1024px

### 4.2 流式通信

```javascript
// SSE (Server-Sent Events)
const eventSource = new EventSource('/api/v1/chat/stream');
// 消息类型: metadata → content (多个) → done
// 异常类型: abort (安全熔断)
// 重试: 最多 3 次，指数退避
```

### 4.3 状态管理

- `localStorage`: 免责声明确认状态
- 内存变量: 当前 conversation_id, user_id, 消息列表
- API 驱动: 对话列表、健康数据均从后端实时获取

---

## 五、测试与评估

### 5.1 测试覆盖

- 24 个测试文件，覆盖: API 端点、路由逻辑、档案管理、安全过滤、性能中间件、代码质量
- 目标覆盖率: ≥ 85%

### 5.2 评估系统

- 100 条测试用例 (`test_cases.json`)
- 自动化评估脚本 (`evaluation/run_evaluation.py`)
- 指标: 分诊准确率、急症召回率、拒答准确率、内容一致性 (LLM-as-Judge)

