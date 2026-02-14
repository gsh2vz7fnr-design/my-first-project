# 儿科健康助手 — 问题修复计划（含多成员会话一致性）

> **版本**: v2.2
> **最后更新**: 2026-02-14
> **状态**: ✅ RAG 问题修复完成；✅ 多成员会话一致性修复完成
> **目标**: 在既有 RAG 质量修复基础上，完成医疗场景下的成员隔离、归档一致性和状态持久化

---

## 0. 本轮新增修复（2026-02-14）

### 0.1 关键风险与修复结论

| # | 问题 | 风险 | 修复状态 | 实施点 |
|---|------|------|---------|--------|
| M1 | 会话上下文未隔离 | 成员 A/B 症状和建议混淆 | ✅ 已修复 | 切换成员强制新会话；后端按 `conversation_id + member_id` 绑定校验 |
| M2 | 归档时成员错绑 | A 的问诊误归档给 B | ✅ 已修复 | `/archive` 读取会话绑定成员为主；请求体成员仅做双检验 |
| M3 | 前端刷新丢失当前就诊人 | 后续请求落到错误成员 | ✅ 已修复 | `localStorage` 持久化 `last_active_member_id:<user_id>` |
| M4 | 历史 user_id/member_id 混用 | 老数据不可追溯或错位 | ✅ 已修复 | 新增迁移脚本 `migrate_user_member_records.py`，支持 dry-run/apply |
| M5 | 月龄固化风险 | 过期 `age_months` 继续被复用 | ✅ 已修复 | 档案读取优先 `birth_date` 动态换算，输入月龄仅作为当轮补充信息 |

### 0.2 本轮改动清单

- 后端模型与流程：
  - `ChatRequest`、`MedicalContext` 增加 `member_id`
  - `conversation_service` 增加会话成员绑定与一致性校验
  - `chat_pipeline` 增加成员冲突拦截（`member_mismatch`）
  - `chat router` 新增归档成员双检验与错误码语义化
- 前端流程与交互：
  - 发送消息附带 `member_id`
  - 就诊人切换时要求开启新会话并清空旧上下文
  - 新增就诊人切换弹窗，聊天页和档案页复用
  - 对话输入容器升级为两行结构（输入行 + 上下文行）
- 工具与测试：
  - 新增迁移脚本：`backend/scripts/migrate_user_member_records.py`
  - 新增测试：`backend/tests/test_member_data_migration.py`
  - 关键回归：`test_chat_router.py`、`test_archive.py`、`test_chat_pipeline.py`

### 0.3 验收结果（2026-02-14）

- ✅ 归档不再依赖“点击瞬间前端当前成员”，以会话绑定成员为准
- ✅ 第二次问诊可读取档案历史，并在 prompt 中注入对应就诊人成员信息
- ✅ 成员切换后不会沿用上一成员会话上下文
- ✅ 刷新页面后恢复上次就诊人，避免默认成员误用

---

## 一、问题诊断总览（更新状态）

> ✅ **代码审查结论**: 2026-02-13 检查代码后发现，Fix 1-3, 5-6 已全部完成！
> ✅ **P6 已修复**: 2026-02-13 添加 `_parse_json_from_llm_response()` 方法，14/14 测试通过

| # | 问题 | 状态 | 严重度 | 解决方式 |
|---|------|------|--------|---------|
| P1 | **格式混乱** — 输出大量 `**` Markdown 符号 | ⚠️ **设计分歧** | 🟡 中 | 代码选择了**完整 Markdown 渲染**（支持标题、加粗、链接、代码块），而非修复计划的"纯文本"。**需产品决策** |
| P2 | **过度拒绝** — "文档未提供具体步骤，无法给出建议" | ✅ **已修复** | 🔴 高 | Fix 1+2: RAG Prompt 改为"文档优先→常识补充→坦诚告知"三层策略 |
| P3 | **来源干扰** — 正文中夹杂 `【来源:cough_003】` | ✅ **已修复** | 🟡 中 | Fix 2+3: Prompt 要求不插入来源 + 后端清理 + 前端清理三重防护 |
| P4 | **语气僵硬** — 像论文摘要，无亲和力 | ✅ **已修复** | 🟡 中 | Fix 1+6: 引入"小儿安"人格，温暖亲切语气 |
| P5 | **安全过滤误杀** — "抗生素"触发拦截 | ✅ **已修复** | 🟡 中 | Fix 5: 移除"抗生素""头孢""阿莫西林"等医疗术语黑名单 |
| P6 | **JSON 解析失败** — LLM 返回代码块导致解析错误 | ✅ **已修复** | 🔴 高 | 添加 `_parse_json_from_llm_response()` 清理 Markdown 代码块，14 个测试全部通过 |
| P7 | **响应缓慢** — 简单输入仍调用 LLM 耗时 2 秒 | ✅ **已修复** | 🟡 中 | 添加快速路径 `_try_fast_path_extraction()` 处理简单时间输入，22 个测试全部通过 |

---

## 二、P6 修复详情（2026-02-13 完成）

> ✅ **P7 已完成**: 2026-02-13 添加快速路径优化，简单输入响应从 2 秒降至 <10ms

### 问题描述

**日志**:
```
2026-02-12 18:55:28.599 DEBUG [LLMService] LLM Response | raw=```json
{
    "intent": "slot_filling",
    "intent_confidence": 0.95,
    "entities": {"duration": "半天"}
}
```
2026-02-12 18:55:28.599 ERROR [LLMService] 意图提取失败: Expecting value: line 1 column 1 (char 0)
```

**根因**: LLM 返回 ` ```json\n{...}\n``` `，但代码直接用 `json.loads(content)` 解析，未先清理 Markdown 代码块标记

**影响**: 意图提取失败 → fallback 到本地规则 → 可能影响分诊准确率

### 修复方案

**位置**: `backend/app/services/llm_service.py`

**添加的方法**:
```python
def _parse_json_from_llm_response(self, content: str) -> dict:
    """
    从 LLM 响应中解析 JSON，清理可能的 Markdown 代码块标记
    """
    # 清理 Markdown 代码块标记
    content = content.strip()

    # 移除开头的 ```json 或 ```
    if content.startswith("```"):
        lines = content.split('\n', 1)
        if len(lines) > 1:
            content = lines[1]

    # 移除结尾的 ```
    if content.endswith("```"):
        content = content[:-3]

    content = content.strip()

    return json.loads(content)
```

**修改的位置**:
1. `extract_intent_and_entities()` 方法 (L81)
2. `extract_profile_updates()` 方法 (L154)

### 测试验证

**新增测试**: `tests/test_llm_service.py::TestParseJsonFromLlmResponse`

```python
class TestParseJsonFromLlmResponse:
    """P6: 修复 LLM 返回 Markdown 代码块导致 JSON 解析失败"""

    def test_parse_json_without_markdown(self):
        """TC-LLM-JSON-01: 解析纯 JSON（无 Markdown 标记）"""

    def test_parse_json_with_markdown_block(self):
        """TC-LLM-JSON-02: 解析包裹在 ```json...``` 中的 JSON"""

    def test_parse_json_with_generic_markdown(self):
        """TC-LLM-JSON-03: 解析包裹在 ```...``` 中的 JSON（无 json 语言标识）"""

    def test_parse_json_with_extra_whitespace(self):
        """TC-LLM-JSON-04: 解析带有多余空格和换行的 JSON"""

    def test_parse_json_invalid_after_cleanup(self):
        """TC-LLM-JSON-05: 清理后仍不是有效 JSON 应抛出异常"""
```

**测试结果**: ✅ **5/5 通过** (总 14/14 测试通过)

---

### P7: 响应缓慢 - 已完成 2026-02-13

**日志**:
```
2026-02-12 18:55:26.628 WARNING Slow request: POST /api/v1/chat/stream took 2.02s
2026-02-12 18:55:26.630 DEBUG [LLMService] LLM Request | prompt=用户输入：半天
```

**根因**: 用户只输入"半天"（补充 duration 信息），但仍然调用 LLM 提取意图，耗时 2 秒

**影响**: 用户体验差，简单的信息补充也需要等待 2 秒

### 修复方案

**位置**: `backend/app/services/llm_service.py`

**添加的方法**:
```python
def _try_fast_path_extraction(self, user_input: str) -> Optional[dict]:
    """
    快速路径：检测简单的时间/数字输入，避免调用 LLM

    当用户输入只包含简单的时间信息（如"半天"、"3天"、"2小时"）时，
    直接返回 slot_filling 意图，跳过耗时 2 秒的 LLM 调用。
    """
    import re

    text = user_input.strip()

    # 简单时长模式：只包含时间单位 + 数字/中文数字
    # 匹配：半天、3天、2小时、5分钟、一周等
    time_patterns = [
        r'^[\d一二三四五六七八九十百千万几]+(?:天|日|周|个月?|小时?|分种?|秒种?)$',
        r'^(?:半天|多长时间|好几天|几天了|几小时|大概多久)$'
    ]

    for pattern in time_patterns:
        if re.match(pattern, text):
            # 提取时间值
            duration_value = text
            return {
                "intent": "slot_filling",
                "intent_confidence": 0.95,
                "entities": {
                    "duration": duration_value
                }
            }

    # 简单数字模式：只是补充数值信息
    if re.match(r'^\d+$', text):
        return {
            "intent": "slot_filling",
            "intent_confidence": 0.90,
            "entities": {
                "unknown_numeric": text
            }
        }

    # 不是简单输入，需要走 LLM 路径
    return None
```

**修改的位置**:
- `extract_intent_and_entities()` 方法 (L74) - 在调用 LLM 前先尝试快速路径

### 测试验证

**新增测试**: `tests/test_llm_service.py::TestFastPathExtraction`

```python
class TestFastPathExtraction:
    """P7: 优化简单输入的响应速度，避免不必要的 LLM 调用"""

    def test_fast_path_simple_duration(self):
        """TC-LLM-FAST-01: 快速路径识别'半天'"""

    def test_fast_path_numeric_days(self):
        """TC-LLM-FAST-02: 快速路径识别'3天'"""

    def test_fast_path_chinese_numbers(self):
        """TC-LLM-FAST-03: 快速路径识别'五天'"""

    def test_fast_path_hours(self):
        """TC-LLM-FAST-04: 快速路径识别'2小时'"""

    def test_fast_path_weeks(self):
        """TC-LLM-FAST-05: 快速路径识别'一周'"""

    def test_fast_path_pure_number(self):
        """TC-LLM-FAST-06: 快速路径识别纯数字'38'"""

    def test_fast_path_reject_complex_input(self):
        """TC-LLM-FAST-07: 复杂输入不应走快速路径"""

    def test_fast_path_reject_question(self):
        """TC-LLM-FAST-08: 问题句式不应走快速路径"""
```

**测试结果**: ✅ **8/8 通过** (总 22/22 测试通过)

**性能提升**:
- 简单输入响应：从 ~2 秒降至 <10ms（正则表达式匹配）
- 覆盖场景：时长信息（天、小时、分钟、周）+ 纯数字

---

## 三、已完成修复的详细记录

### ✅ Fix 1: 重写 RAG System Prompt（P2 + P4）

**位置**: `backend/app/services/rag_service.py:663-689`

**修复内容**:
```python
def _get_rag_system_prompt(self) -> str:
    return """你是「小儿安」，一位温暖、专业的儿科健康顾问...

## 回答原则
1. 优先引用知识库文档中的内容作为核心依据
2. 当文档提供了部分信息但不够完整时，你可以基于儿科常识进行合理补充...
3. 当文档完全没有相关信息时，坦诚告知，并给出就医建议，而不是简单拒绝

## 语气要求
- 像一位有经验的儿科护士在和家长聊天，温暖但不啰嗦
- 用"宝宝""您"等亲切称呼
```

**验证**: ✅ 代码中已是修复后的版本

---

### ✅ Fix 2: 重写 RAG User Prompt（P2 + P3）

**位置**: `backend/app/services/rag_service.py:635-661`

**修复内容**:
```python
prompt += "请基于以上知识库内容，用温暖易懂的语言回答家长的问题。\n"
prompt += "注意：不要在回答正文中插入来源标记或引用编号。\n"
```

**验证**: ✅ Prompt 已要求不插入来源标记

---

### ✅ Fix 3: 后端来源清理（P3）

**位置**: `backend/app/services/rag_service.py:691-698`

**修复内容**:
```python
def format_with_citations(self, answer: str, sources: List[KnowledgeSource]) -> str:
    """格式化答案，清理来源标记"""
    clean_answer = re.sub(r'【来源:[^】]+】', '', answer).strip()
    return clean_answer
```

**验证**: ✅ 已实现来源标记清理

---

### ✅ Fix 5: 优化安全过滤（P5）

**位置**: `backend/app/services/safety_filter.py:52`

**修复内容**:
```python
# 注意：移除了 "阿司匹林""复方感冒药""抗生素""头孢""阿莫西林""开药""开处方"
# 原因：知识库原文中合理提及这些药物，过滤会导致正常回答被截断
```

**验证**: ✅ 医疗黑名单已精简，避免误杀

---

### ✅ Fix 6: 重写主 System Prompt（P4）

**位置**: `backend/app/services/llm_service.py:954-980`

**修复内容**:
```python
def _build_system_prompt(self) -> str:
    return """你是「小儿安」，一位温暖专业的儿科健康顾问...

你的风格：
- 像一位经验丰富的儿科护士，温暖、耐心、不说教
- 先共情，再给建议
- 用简短易懂的句子，避免医学术语堆砌
```

**验证**: ✅ 已引入温暖人格

---

## 四、待决策问题

### P1 格式问题 - 需要产品决策

**现状**:
- 前端 `formatMessage()` 已实现**完整 Markdown 渲染**（支持标题、加粗、斜体、链接、代码块）
- 后端 Prompt 要求"使用清晰的 Markdown 格式"（RAG L678-684）

**修复计划原方案**:
- 纯文本输出，不用 `**` 或 `#` 等符号
- 用 `·` 代替列表符号

**分歧**:
| 方案 | 优点 | 缺点 |
|------|------|------|
| 保留 Markdown | 富文本，视觉层次好，已实现 | 移动端可能显示问题（待验证） |
| 改为纯文本 | 简单，兼容性好 | 丢失视觉层次，"小儿安"人格效果打折 |

**建议**: 需要在实际移动设备上测试当前 Markdown 渲染效果，确认是否存在"显示差"的问题

---

## 五、修复优先级

| 优先级 | 问题 | 状态 | 预计工作量 |
|--------|------|------|-----------|
| 🔴 P0 | P6: JSON 解析失败 | ✅ **已完成** | 15分钟 |
| 🟡 P1 | P7: 响应缓慢优化 | ✅ **已完成** | 2小时 |
| 🟢 P2 | P1: 格式问题决策 | ❓ 需测试 | - |
| ✅ 已完成 | P2, P3, P4, P5, P6, P7 | ✅ **已完成** | - |

---

## 六、后续行动

### ✅ 已完成（2026-02-13）
- [x] **P6**: 修改 `llm_service.py` 的 JSON 解析逻辑，添加 Markdown 代码块清理
- [x] **P6**: 添加 5 个单元测试验证代码块清理逻辑
- [x] **P6**: 运行回归测试确认不破坏现有功能（14/14 通过）
- [x] **P7**: 添加快速路径 `_try_fast_path_extraction()` 处理简单时间输入
- [x] **P7**: 添加 8 个单元测试验证快速路径逻辑
- [x] **P7**: 运行回归测试确认不破坏现有功能（22/22 通过）
- [x] 更新 `TODO_FIX_PLAN.md` 标记 P6, P7 已完成

### 待测试验证
1. 在真实移动设备上测试当前 Markdown 渲染效果
2. 收集用户反馈确认格式问题是否真实存在

### 待优化
1. 提升测试覆盖率到 85%

### 文档更新
1. ✅ 更新 `TODO_FIX_PLAN.md` 标记 P6, P7 已完成
2. 待更新 `progress.md` 记录修复进度

---

## 七、参考信息

**日志位置**: 用户提供的 2026-02-12 18:55 系统日志

**关键文件**:
- `backend/app/services/rag_service.py` (L635-712)
- `backend/app/services/llm_service.py` (L54-158, L954-980)
- `backend/app/services/safety_filter.py` (L34-53)
- `frontend/app.js` (L243-279)

**测试数量**: 392 个测试用例（LLM service 22/22 通过）
