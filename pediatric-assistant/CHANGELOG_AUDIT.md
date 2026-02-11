# 变更日志 - 代码审计报告 (Code Audit Change Log)

> **审计日期**: 2026-02-10
> **审计范围**: 全量后端代码 + 前端代码 vs master_plan.md
> **审计结论**: 文档严重滞后于代码实现，发现 **37 处遗漏/过时/不准确** 的描述

---

## 一、文档中没写但代码已实现的"隐形功能" (Undocumented Features)

### A. 逻辑层 (Logic)

| # | 隐形功能 | 代码位置 | 说明 |
|---|---------|---------|------|
| 1 | **症状历史恢复** | `chat.py:750-762` | 当 slot_filling 意图缺少 symptom 时，系统自动回溯最近 10 条对话历史，用 regex fallback 提取上一轮的症状实体 |
| 2 | **结构化槽位表单定义** | `chat.py:764-889` | 为 12 种槽位定义了 type/label/options/min/max/step，前端据此渲染 select/multiselect/number 表单控件 |
| 3 | **远程 API 冷却机制** | `llm_service.py:27-40`, `rag_service.py:37-47` | LLM 和 RAG 服务均有 60 秒冷却：API 调用失败后自动降级为本地处理，60 秒后恢复 |
| 4 | **本地 Regex 兜底意图提取** | `llm_service.py:350-493` | 完整的本地规则引擎：greeting 检测（排除混合意图）、slot_filling 检测（key:value 格式）、症状/实体 regex 提取 |
| 5 | **症状同义词归一化** | `llm_service.py:513-533` | 将口语化表达映射为标准术语（"发热"→"发烧"、"拉肚子"→"腹泻"等 12 组映射） |
| 6 | **实体后处理纠错** | `llm_service.py:535-574` | LLM 提取后二次校验：修复症状误判（如"摔"相关文本被误判为"呕吐"时纠正为"摔倒"）、补全伴随症状、去重 |
| 7 | **引导提问生成** | `llm_service.py:186-263` | 基于 8 类症状的规则化引导问题生成（每类 3 个高价值后续问题） |
| 8 | **轻症追问放松** | `triage_engine.py:285-300` | 发烧场景：月龄≥3 且体温<38.5 且精神正常时，跳过追问直接给建议 |
| 9 | **中文数字解析** | `triage_engine.py:141-158` | 支持"三个月"、"十二个月"等中文数字转 float |
| 10 | **持续时长转换** | `triage_engine.py:378-389` | "2天"→48h、"3小时"→3h、"30分钟"→0.5h |
| 11 | **完整对话管理 CRUD** | `chat.py:892-970`, `conversation_service.py` | 创建/列表/删除/切换对话，自动生成标题（首条用户消息前 30 字） |
| 12 | **性能监控中间件** | `middleware/performance.py` | P50/P90/P95/P99 延迟统计、慢请求告警（>1s/2s）、X-Response-Time 响应头 |
| 13 | **SQLite 任务队列** | `profile_service.py:59-72, 222-262` | 持久化任务队列（pending/completed/failed/cancelled），60 秒轮询执行到期任务 |
| 14 | **家庭成员管理系统** | `profile_service.py:415-702` | 完整的 CRUD + 体征管理（BMI 自动计算）+ 生活习惯管理 |
| 15 | **健康史管理服务** | `profile_service.py:708-939` | 过敏史/既往病史/家族病史/用药史的独立 CRUD |
| 16 | **健康记录管理服务** | `profile_service.py:944-1181` | 问诊/处方/挂号/病历/体检记录的完整管理 |
| 17 | **Embedding 缓存** | `rag_service.py:84-98` | 内存级缓存，避免重复调用 Embedding API |
| 18 | **医学术语分词器** | `rag_service.py:555-588` | 自定义分词：优先匹配长医学词汇（"呼吸困难"、"精神萎靡"等），剩余按单字切分 |
| 19 | **本地检索索引** | `rag_service.py:499-504` | 启动时预构建全量文档的 token 计数索引 |

### B. 硬编码阈值 (Hardcoded Thresholds) — 文档未记录或记录错误

| # | 参数 | 代码实际值 | 文档描述值 | 位置 |
|---|------|-----------|-----------|------|
| 1 | 相似度阈值 | **0.3** | 0.6 | `config.py:67` |
| 2 | 本地检索阈值 | **0.2** | 未提及 | `rag_service.py:534` |
| 3 | 本地模式重排阈值 | **0.1** | 未提及 | `rag_service.py:334` |
| 4 | RAG Top-K | **3** | 5 | `config.py:66` |
| 5 | 意图提取 Temperature | **0.1** | 未提及 | `llm_service.py:71` |
| 6 | RAG 生成 Temperature | **0.3** | 未提及 | `rag_service.py:442` |
| 7 | 流式生成 Temperature | **0.7** | 未提及 | `llm_service.py:110` |
| 8 | 流式 Chunk 大小 | **50 字符** | 未提及 | `config.py:57` |
| 9 | 首字延迟目标 | **1.5s** | < 1.5s ✅ | `config.py:58` |
| 10 | 会话超时 | **1800s (30min)** | 30min ✅ | `config.py:53` |
| 11 | 最大对话历史 | **20 条** | 未提及 | `config.py:52` |
| 12 | 限流 | **20次/分, 500次/天** | 未提及 | `config.py:61-62` |
| 13 | API 冷却时间 | **60 秒** | 未提及 | `llm_service.py:38` |
| 14 | 任务轮询间隔 | **60 秒** | 未提及 | `profile_service.py:85` |
| 15 | 标题匹配加权 | **+0.5** | 未提及 | `rag_service.py:208` |
| 16 | 标签匹配加权 | **+0.2** | 未提及 | `rag_service.py:223` |
| 17 | 精确短语匹配奖励 | **+0.2** | 未提及 | `rag_service.py:297` |
| 18 | 医学实体匹配奖励 | **+0.3** | 未提及 | `rag_service.py:302` |

### C. 依赖与技术栈差异 (Dependency Discrepancies)

| # | 文档描述 | 代码实际 | 影响 |
|---|---------|---------|------|
| 1 | GPT-4 / GPT-4o-mini | **DeepSeek (deepseek-chat)** | LLM 提供商完全不同 |
| 2 | 未指定 Embedding | **SiliconFlow + BAAI/bge-m3** | 新增外部依赖 |
| 3 | MongoDB / Supabase JSONB | **SQLite** | 存储引擎完全不同 |
| 4 | Redis Key Expiration | **SQLite 任务队列 + asyncio 轮询** | 任务调度方案不同 |
| 5 | Celery 定时任务 | **asyncio.sleep(60) 轮询** | 无 Celery 依赖 |
| 6 | Cross-Encoder / BGE-Reranker | **启发式规则重排序** | 无 ML 重排模型 |
| 7 | React / TypeScript 组件 | **Vanilla JavaScript (ES6)** | 前端框架完全不同 |
| 8 | jieba 分词 | **自定义医学术语分词器** | 无 jieba 依赖 |
| 9 | 未提及 | **loguru** (日志) | 新增依赖 |
| 10 | 未提及 | **pydantic-settings** (配置) | 新增依赖 |
| 11 | 未提及 | **numpy** (性能统计) | 新增依赖 |

---

## 二、文档中描述但代码未实现或实现不同的功能 (Documented but Different/Missing)

| # | 文档描述 | 实际状态 | 说明 |
|---|---------|---------|------|
| 1 | "六步闭环"输出结构 | **部分实现** | RAG System Prompt 定义了模板（核心结论→护理建议→注意→就医信号→引导问题），但非强制执行 |
| 2 | 引用角标 `【来源:xxx】` | **已移除** | `format_with_citations()` 现在是**清理**来源标记而非添加，来源通过 metadata 独立返回 |
| 3 | 点击查证展开原文 | **已实现** | 通过 `/source/{entry_id}` API + 前端 SourceSheet 组件 |
| 4 | 话题漂移处理 | **未实现** | 文档描述了 Topic Drift Handling，但代码中 Global Router 无此逻辑 |
| 5 | 用户确认"洞察卡片" | **已实现** | 通过 `pending_confirmations` + `confirm_updates` API |
| 6 | 图文增强（示意图） | **未实现** | P1 规划中的功能，代码无相关实现 |
| 7 | 地图导航按钮 | **未实现** | 文档提到急症弹窗附带地图导航，代码无此功能 |

---

## 三、文档结构性问题

1. **master_plan.md 包含两个版本** (v3.1 和 v2.0)，内容重复且不一致
2. **Phase 状态过时**: Phase 1.5 标记为 Pending，但 Bug 已修复（如身份证不可变规则已在代码中实现）
3. **文件清单过时**: "需要新建的文件"中列出的文件大部分已创建（stream_filter.py、blacklist 文件等）
4. **前端组件描述过时**: 文档列出独立组件文件（HealthDashboard.js 等），实际全部合并在 components.js 中
