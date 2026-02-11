# 儿科健康助手 — RAG 输出质量优化修复计划

> **版本**: v1.0
> **日期**: 2025-02-10
> **目标**: 解决当前 RAG 回答"格式混乱、过度拒绝、来源干扰、语气僵硬"四大核心问题

---

## 一、问题诊断总览

| # | 问题 | 根因定位 | 严重度 | 涉及文件 |
|---|------|---------|--------|---------|
| P1 | **格式混乱** — 输出大量 `**` Markdown 符号，移动端显示差 | 1) System Prompt 要求 `**加粗**` 格式输出；2) 前端 `formatMessage()` 只做了简单正则替换，无完整 Markdown 渲染 | 🔴 高 | `rag_service.py:638-674`, `app.js:146-156` |
| P2 | **过度拒绝** — "文档未提供具体步骤，无法给出建议" | 1) RAG Prompt 强制要求"答案必须100%基于文档，不要编造"；2) `_build_rag_prompt` 第1条规则"不要添加文档中没有的信息"过于严格 | 🔴 高 | `rag_service.py:627-634`, `rag_service.py:638-674` |
| P3 | **来源干扰** — 正文中夹杂 `【来源:cough_003】` | 1) RAG Prompt 第3条要求"每条建议后必须加【来源:ID】角标"；2) `format_with_citations()` 又在末尾追加一遍来源 | 🟡 中 | `rag_service.py:629-630`, `rag_service.py:676-694` |
| P4 | **语气僵硬** — 像论文摘要，无亲和力 | 1) System Prompt 缺少语气/人格指令；2) RAG System Prompt 核心原则全是"禁止/不要"，无正向引导 | 🟡 中 | `rag_service.py:638-674`, `llm_service.py:576-605` |
| P5 | **安全过滤误杀** — "抗生素"在黑名单中，但百日咳知识库原文就提到抗生素治疗 | `safety_filter.py` 医疗黑名单包含"抗生素"，导致 LLM 引用知识库原文时被流式安全熔断 | 🟡 中 | `safety_filter.py:52` |

---

## 二、修复方案（按优先级排序）

### Fix 1: 重写 RAG System Prompt — 解决 P2 + P4

**文件**: `backend/app/services/rag_service.py` → `_get_rag_system_prompt()` (L638-674)

**当前问题**:
- "答案必须100%基于提供的权威文档，不要编造或推测" → 导致 LLM 遇到文档未明确写出的常识性护理建议时直接拒绝
- 全是"禁止"指令，缺少正向人格引导 → 语气僵硬

**修改方案**:

```python
def _get_rag_system_prompt(self) -> str:
    return """你是「小儿安」，一位温暖、专业的儿科健康顾问。你的用户是焦虑的新手爸妈，请用朋友般的口吻和他们交流。

## 回答原则
1. 优先引用知识库文档中的内容作为核心依据
2. 当文档提供了部分信息但不够完整时，你可以基于儿科常识进行合理补充（如基础护理建议：多休息、注意观察、保持通风等），但需标注"一般建议"
3. 当文档完全没有相关信息时，坦诚告知，并给出就医建议，而不是简单拒绝
4. 绝不编造具体数据（如药物剂量、体温阈值），数据必须来自文档

## 语气要求
- 像一位有经验的儿科护士在和家长聊天，温暖但不啰嗦
- 用"宝宝""您"等亲切称呼
- 避免学术论文式的长句，多用短句和口语化表达
- 适当使用 emoji 增加亲和力（不超过3个）

## 输出格式（纯文本，不要使用 Markdown 符号）
用以下结构组织回答，每个部分用换行分隔，不要使用 ** 或 # 等格式符号：

[一句话核心结论]

护理建议：
1. 具体步骤1
2. 具体步骤2
3. ...

需要注意：
· 注意点1
· 注意点2

⚠️ 这些情况请立即就医：
· 就医信号1
· 就医信号2

您可能还想了解：
· 引导问题1
· 引导问题2
· 引导问题3

## 禁止事项
- 不要推荐具体处方药名称或剂量
- 不要做出确诊性判断（如"您的宝宝得了XX"）
- 不要使用绝对化承诺"""
```

**关键变化**:
1. 赋予人格名称"小儿安"，建立亲和力
2. 将"100%基于文档"改为分层策略：文档优先 → 常识补充 → 坦诚告知
3. 明确要求"纯文本输出，不使用 Markdown 符号"
4. 用 `·` 代替 `-`，用数字列表代替 Markdown 列表
5. 增加语气正向引导

---

### Fix 2: 重写 RAG User Prompt — 解决 P2 + P3

**文件**: `backend/app/services/rag_service.py` → `_build_rag_prompt()` (L601-636)

**当前问题**:
- 第1条"答案必须完全基于检索到的文档内容，不要添加文档中没有的信息" → 过度限制
- 第3条"每条核心建议后面必须加【来源:ID】角标" → 来源标记污染正文

**修改方案**:

```python
def _build_rag_prompt(self, query, sources, context):
    prompt = f"家长的问题：{query}\n\n"

    if context and context.get('baby_info'):
        baby_info = context['baby_info']
        prompt += "宝宝信息：\n"
        if baby_info.get('age_months'):
            prompt += f"- 月龄：{baby_info['age_months']}个月\n"
        if baby_info.get('weight_kg'):
            prompt += f"- 体重：{baby_info['weight_kg']}kg\n"
        prompt += "\n"

    prompt += "以下是从权威医学知识库中检索到的相关内容：\n\n"
    for i, source in enumerate(sources, 1):
        prompt += f"--- 文档{i} ---\n"
        prompt += f"{source.content}\n\n"

    prompt += "请基于以上知识库内容，用温暖易懂的语言回答家长的问题。\n"
    prompt += "注意：不要在回答正文中插入来源标记或引用编号。\n"

    return prompt
```

**关键变化**:
1. 删除"答案必须完全基于文档"的硬性约束
2. 删除"必须加【来源:ID】角标"的要求
3. 简化文档展示格式，去掉 ID/标题/来源等元数据噪音
4. 将"用户问题"改为"家长的问题"，保持语境一致

---

### Fix 3: 改造来源引用机制 — 解决 P3

**文件**: `backend/app/services/rag_service.py` → `format_with_citations()` (L676-694)
**文件**: `backend/app/routers/chat.py` → 流式/非流式响应中的引用处理

**当前问题**:
- LLM 在正文中插入 `【来源:ID】`
- `format_with_citations()` 又在末尾追加来源列表
- 前端用正则把 `【来源:ID】` 转成 `<span class="citation">`，但视觉效果差

**修改方案**:

**A) 后端：来源信息与正文分离**

将来源信息作为结构化数据返回，不再拼接到正文中：

```python
# rag_service.py - 修改 format_with_citations
def format_with_citations(self, answer, sources):
    """不再拼接来源到正文，而是返回结构化数据"""
    # 清理 LLM 可能残留的来源标记
    clean_answer = re.sub(r'【来源:[^】]+】', '', answer).strip()
    return clean_answer

def get_sources_metadata(self, sources):
    """单独返回来源元数据"""
    return [
        {
            "id": s.metadata.get("id", "unknown"),
            "title": s.metadata.get("title", "未知"),
            "source": s.source
        }
        for s in sources
    ]
```

**B) 前端：来源信息折叠展示**

在聊天气泡底部添加可折叠的"查看来源"按钮，点击展开来源列表：

```javascript
// app.js - 修改消息渲染
function appendMessageWithSources(role, text, sources = []) {
    const bubble = appendMessage(role, text);
    if (sources.length > 0) {
        const sourceBtn = document.createElement("div");
        sourceBtn.className = "source-toggle";
        sourceBtn.textContent = `📚 查看来源 (${sources.length})`;
        sourceBtn.onclick = () => { /* 展开/折叠来源列表 */ };
        bubble.querySelector(".bubble").appendChild(sourceBtn);
    }
}
```

---

### Fix 4: 升级前端 Markdown 渲染 — 解决 P1

**文件**: `frontend/app.js` → `formatMessage()` (L146-156)

**当前问题**:
- 只处理了 `**bold**` 和 `*italic*`，无法处理列表、标题等
- 如果 LLM 仍然输出 Markdown（Prompt 改了但不能100%保证），前端无法正确渲染

**修改方案（两步走）**:

**Step 1（短期）: 增强 formatMessage 的清理能力**

```javascript
function formatMessage(text) {
    if (!text) return "";
    let safe = escapeHtml(text);

    // 清理残留的 Markdown 符号
    safe = safe.replace(/#{1,6}\s/g, "");           // 清理标题符号
    safe = safe.replace(/\*\*(.+?)\*\*/g, "$1");    // 去掉加粗符号，保留文字
    safe = safe.replace(/\*(.+?)\*/g, "$1");         // 去掉斜体符号
    safe = safe.replace(/【来源:[^】]+】/g, "");      // 清理来源标记

    // 处理列表
    safe = safe.replace(/^[\-\*]\s/gm, "· ");        // 无序列表
    safe = safe.replace(/^\d+\.\s/gm, (m) => m);     // 有序列表保留

    safe = safe.replace(/\n/g, "<br />");
    return safe;
}
```

**Step 2（中期）: 引入轻量 Markdown 渲染库**

引入 `marked.js`（~40KB）或 `snarkdown`（~1KB）做完整渲染：

```html
<!-- index.html -->
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
```

```javascript
function formatMessage(text) {
    if (!text) return "";
    // 先清理来源标记
    let clean = text.replace(/【来源:[^】]+】/g, "");
    return marked.parse(clean);
}
```

---

### Fix 5: 优化安全过滤策略 — 解决 P5

**文件**: `backend/app/services/safety_filter.py` (L34-53)

**当前问题**:
- 医疗黑名单中包含"抗生素""头孢""阿莫西林"
- 百日咳知识库原文明确提到"百日咳需要用抗生素治疗"
- LLM 引用原文时触发安全熔断，导致回答被截断

**修改方案**:

```python
def _get_default_blacklist(self, category):
    if category == "medical":
        return [
            # 禁药类（儿童禁用）
            "尼美舒利", "安乃近",
            # 伪科学类
            "排毒", "根治", "包治百病", "转胎药", "偏方",
            # 高风险操作
            "酒精擦身", "放血", "催吐", "灌肠",
            # 合规类（绝对化承诺）
            "确诊是", "我保证", "肯定没问题", "一定能治好",
        ]
        # 注意：移除了 "抗生素""头孢""阿莫西林""开药""开处方""复方感冒药""阿司匹林"
        # 原因：知识库原文中合理提及这些药物，过滤会导致正常回答被截断
        # 替代方案：在 Prompt 层面约束 LLM 不主动推荐处方药
```

**补充措施**:
- 在 `check_prescription_intent()` 中保留对用户输入的处方意图检测（用户主动要求开药时拦截）
- 在 System Prompt 中保留"不要推荐具体处方药名称或剂量"的指令
- 这样实现"知识库可以提及药物信息 → LLM 可以转述 → 但不主动推荐"的分层策略

---

### Fix 6: 重写主 System Prompt — 解决 P4

**文件**: `backend/app/services/llm_service.py` → `_build_system_prompt()` (L576-605)

**当前问题**:
- 当前 Prompt 用于非 RAG 场景（分诊、闲聊等），但语气同样僵硬
- "拒绝回答超出能力范围的问题"表述过于生硬

**修改方案**:

```python
def _build_system_prompt(self):
    return """你是「小儿安」，一位温暖专业的儿科健康顾问，服务对象是0-3岁宝宝的家长。

身份说明：
你是 AI 健康助手，不是医生。你提供的是参考建议，不是医疗诊断。

你的风格：
- 像一位经验丰富的儿科护士，温暖、耐心、不说教
- 先共情，再给建议
- 用简短易懂的句子，避免医学术语堆砌
- 当不确定时坦诚说"建议咨询医生"，而不是生硬拒绝

回答结构：
1. 情绪承接（如果家长明显焦虑）
2. 核心建议（简明扼要）
3. 需要注意的事项
4. 什么情况必须去医院
5. 您可能还想了解（2-3个后续问题）

底线规则：
- 不推荐具体处方药
- 不做确诊判断
- 不给绝对化承诺

每次回答末尾附带：
以上为 AI 参考建议，不作为医疗诊断依据，请以医生医嘱为准。"""
```

---

### Fix 7: 流式响应中清理来源标记 — 解决 P3

**文件**: `backend/app/routers/chat.py` → 流式响应处理 (L317+)

**当前问题**:
- 流式输出时，LLM 可能仍然输出 `【来源:xxx】`，前端实时渲染会看到这些标记闪过

**修改方案**:

在流式输出的 content chunk 中添加后处理清理：

```python
# chat.py 流式响应中
import re

def clean_stream_content(text: str) -> str:
    """清理流式输出中的来源标记"""
    return re.sub(r'【来源:[^】]*】?', '', text)
```

注意：流式清理需要处理标记被拆分到多个 chunk 的边界情况，建议维护一个 buffer。

---

## 三、实施优先级与排期

| 阶段 | 修复项 | 预期效果 | 依赖 |
|------|--------|---------|------|
| **Phase 1** (核心) | Fix 1 + Fix 2 | 解决过度拒绝 + 语气僵硬，效果提升最大 | 无 |
| **Phase 2** (体验) | Fix 3 + Fix 4 (Step 1) | 解决来源干扰 + 格式混乱 | Phase 1 |
| **Phase 3** (安全) | Fix 5 | 解决安全过滤误杀 | 无 |
| **Phase 4** (打磨) | Fix 6 + Fix 7 | 统一非 RAG 场景语气 + 流式清理 | Phase 1 |
| **Phase 5** (增强) | Fix 4 (Step 2) | 引入 Markdown 渲染库，长期方案 | Phase 2 |

---

## 四、验证测试用例

### 测试 1: 百日咳（原 Bad Case）
**输入**: "百日咳"
**期望输出**:
- 不出现 `**` 等 Markdown 符号
- 不出现 `【来源:xxx】` 标记
- 包含基础护理建议（如：卧床休息、使用加湿器、注意隔离）
- 提到就医信号（如：呼吸困难、嘴唇发紫、持续呕吐）
- 语气温暖，像在和家长聊天

### 测试 2: 过度拒绝场景
**输入**: "宝宝咳嗽怎么护理"
**期望**: 即使知识库没有"咳嗽护理步骤"的完整文档，也应给出常识性建议（多喝水、保持空气湿润、观察呼吸等），而不是"文档未提供，无法回答"

### 测试 3: 安全边界
**输入**: "宝宝发烧能吃什么药"
**期望**: 不推荐具体处方药名，但可以建议"咨询医生后使用退烧药"，不应被安全过滤完全拦截

### 测试 4: 来源展示
**输入**: 任意健康问题
**期望**: 正文中无来源标记，来源信息在气泡底部以折叠方式展示

### 测试 5: 移动端格式
**输入**: 任意问题
**期望**: 在 375px 宽度下，回答排版整洁，无溢出，无乱码符号

---

## 五、风险与注意事项

1. **Prompt 修改后需要回归测试**: 修改 System Prompt 可能影响意图识别准确率，需要用现有测试集验证
2. **安全过滤放宽需谨慎**: 移除黑名单词汇后，需确保 Prompt 层面的约束足够有效
3. **流式清理的边界问题**: `【来源:` 可能被拆分到两个 chunk，需要 buffer 机制处理
4. **LLM 输出不可控**: 即使 Prompt 要求纯文本，DeepSeek 仍可能输出 Markdown，前端清理是必要的兜底

---

## 六、文件修改清单

| 文件 | 修改内容 | Fix # |
|------|---------|-------|
| `backend/app/services/rag_service.py` | 重写 `_get_rag_system_prompt()`、`_build_rag_prompt()`、`format_with_citations()` | 1, 2, 3 |
| `backend/app/services/llm_service.py` | 重写 `_build_system_prompt()` | 6 |
| `backend/app/services/safety_filter.py` | 精简医疗黑名单 | 5 |
| `backend/app/routers/chat.py` | 添加流式内容清理、来源数据结构化返回 | 3, 7 |
| `frontend/app.js` | 重写 `formatMessage()`、添加来源折叠组件 | 4, 3 |
| `frontend/index.html` | (Phase 5) 引入 marked.js | 4 |
| `frontend/styles.css` | 添加来源折叠组件样式 | 3 |

---

## 七、实施路线图

```
Phase 1 (Day 1-2) — Prompt 层修复（零代码风险，立竿见影）
  ├── Fix 1: 重写 RAG System Prompt
  ├── Fix 2: 重写 RAG User Prompt
  └── Fix 6: 同步更新主 System Prompt
  → 验收：百日咳 Bad Case 回答质量明显改善

Phase 2 (Day 2-3) — 来源机制改造
  ├── Fix 3A: 后端来源与正文分离
  ├── Fix 3B: 前端来源折叠组件
  └── Fix 7: 流式输出清理
  → 验收：正文无来源标记，来源可折叠查看

Phase 3 (Day 3-4) — 安全策略优化
  └── Fix 5: 精简医疗黑名单 + 上下文感知
  → 验收：百日咳回答不被误杀，处方药推荐仍被拦截

Phase 4 (Day 4-5) — 前端渲染升级
  └── Fix 4 Step 1: 增强 formatMessage 清理能力
  → 验收：移动端无 Markdown 符号残留

Phase 5 (可选/后续) — 引入 Markdown 渲染库
  └── Fix 4 Step 2: 集成 marked.js
  → 验收：富文本渲染效果
```

---

## 八、预期效果对比

### 修复前（百日咳 Bad Case）:
```
**核心结论**：**百日咳是由百日咳杆菌引起的严重呼吸道传染病**

**操作建议**：
1. **接种疫苗** 【来源:pertussis_001】
2. 文档未提供具体居家护理步骤，无法给出建议

**⚠️ 立即就医信号**：
- **1岁以下婴儿** 出现百日咳症状 【来源:pertussis_002】
...

📚 知识来源：
1. 百日咳 - AAP育儿百科 【来源:pertussis_001】
```

### 修复后（预期效果）:
```
百日咳是一种由细菌引起的呼吸道感染，虽然听起来吓人，但了解它就能更好地保护宝宝 💪

护理建议：
1. 6个月以下的宝宝如果确诊百日咳，通常需要住院治疗，医生会进行吸痰和呼吸监测
2. 大一些的宝宝可以在家护理：让宝宝卧床休息，在房间使用冷雾加湿器
3. 咨询医生宝宝适合什么体位，有助于排痰和改善呼吸
4. 询问医生家里其他人是否需要接种加强针（一般建议）

需要注意：
· 百日咳传染性很强，需要和其他孩子隔离
· 普通止咳药对百日咳的痉咳效果不好，不要自行用药
· 咳嗽可能持续数月，这是正常病程，不必过度焦虑

⚠️ 这些情况请立即就医：
· 宝宝嘴唇发紫（缺氧表现）
· 咳嗽后出现呕吐或看似停止呼吸
· 宝宝变得无精打采、难以唤醒
· 出现抽搐或高烧

您可能还想了解：
· 百日咳疫苗什么时候打最好？
· 咳嗽期间怎么喂养宝宝？
· 家里其他孩子需要隔离多久？

以上内容仅供参考，不作为医疗诊断依据。请以线下医生医嘱为准。
```
