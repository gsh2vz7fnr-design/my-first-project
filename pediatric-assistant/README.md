# 智能儿科分诊与护理助手

> **版本**: v3.4
> **最后更新**: 2026-02-13
> **状态**: 核心功能完成，性能优化完成

---

## 项目简介

这是一个基于大模型+硬编码状态机的智能儿科分诊与护理助手系统，为 0-3 岁婴幼儿的新手父母提供 **7x24 小时即时响应**、科学分诊、权威知识支持的医疗咨询服务。

---

## 核心特性

- **🏥 智能分诊**: 症状引导式分诊，危险信号熔断机制，**100% 急症召回率**
- **📚 循证问答**: 基于权威医学知识库（AAP、默沙东诊疗手册等）的 RAG 系统，所有建议可溯源
- **👶 健康档案**: 自动提取并记录宝宝健康信息（月龄、体重、过敏史等），实现个性化服务
- **💊 用药咨询**: 药品说明书查询、剂量计算、禁忌症提醒
- **🛡️ 安全防护**: 多层安全机制（危险信号熔断、违禁词过滤、处方意图拦截、免责声明）
- **🎨 现代UI**: 阿福风格设计，紫色主题，圆润友好，移动端优先
- **⚡ 高性能**: 简单输入响应 <10ms（快速路径优化），流式输出首字延迟 <1.5s

---

## 技术栈

### 后端
- **Python 3.10+** - 异步编程，高性能
- **FastAPI** - 现代异步 Web 框架，自动 OpenAPI 文档生成
- **DeepSeek API** - 国产大模型，成本优化
- **SQLite** - 轻量级关系数据库，支持会话持久化
- **BGE Embedding** - 通义千问/硅基流动向量化
- **自定义向量库** - 支持本地向量检索 + ChromaDB 可选集成

### 前端
- **原生 JavaScript (ES6+)** - 无框架依赖，轻量快速
- **CSS3** - Flexbox/Grid 布局，CSS Variables 主题系统
- **流式输出** - 打字机效果，实时用户体验
- **响应式设计** - 移动端优先，适配各种屏幕尺寸

---

## 快速开始

### 1️⃣ 后端部署

```bash
# 进入后端目录
cd backend

# 创建虚拟环境（首次）
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入 DeepSeek API Key

# 启动服务
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2️⃣ 前端部署

```bash
# 进入前端目录
cd frontend

# 启动静态服务器
python3 -m http.server 8000

# 访问 http://localhost:8000
```

### 3️⃣ 运行测试

```bash
cd backend
source venv/bin/activate
pytest tests/ -v
```

---

## 文档导航

| 文档 | 说明 |
|------|------|
| **[STATUS.md](docs/STATUS.md)** | 系统状态、最新更新、待办事项 |
| **[TODO_FIX_PLAN.md](docs/TODO_FIX_PLAN.md)** | 问题修复计划与详细进度 |
| **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** | 技术架构、系统设计 |
| **[API 文档](http://localhost:8000/docs)** | 启动后端访问自动生成的 OpenAPI 文档 |

---

## 核心指标

| 指标 | 目标 | 当前 |
|--------|------|------|
| 急症召回率 | 100% | ✅ 100% |
| 有效分诊闭环率 | >80% | ✅ >80% |
| 测试通过率 | 100% | ✅ 100% (392/392) |
| JSON 解析成功率 | 100% | ✅ 100% (P6 已修复) |
| 简单输入响应 | <100ms | ✅ <10ms (P7 已优化) |
| 测试覆盖率 | 85% | 🟡 68% (待提升) |

---

## 最新更新 (v3.4 - 2026-02-13)

### ✅ P6: JSON 解析失败修复
- **问题**: LLM 返回 Markdown 代码块导致 `json.loads()` 解析失败
- **解决**: 添加自动清理方法，支持 ````json...``` 和 ```````` 两种格式
- **测试**: ✅ 5/5 通过

### ✅ P7: 响应速度优化
- **问题**: 简单输入（如"半天"）仍调用 LLM，耗时 2 秒
- **解决**: 添加快速路径，正则表达式检测简单时间输入
- **性能**: 简单输入响应从 ~2000ms 降至 <10ms
- **测试**: ✅ 8/8 通过

详细修复内容参见 [TODO_FIX_PLAN.md](docs/TODO_FIX_PLAN.md)

---

## 项目结构

```
pediatric-assistant/
├── backend/                 # 后端服务（Python FastAPI）
│   ├── app/
│   │   ├── config.py          # 配置管理
│   │   ├── main.py            # FastAPI 入口
│   │   ├── models/            # 数据模型
│   │   ├── services/          # 核心服务
│   │   ├── routers/           # API 路由
│   │   └── data/              # 数据文件
│   ├── tests/                 # 测试用例（392个，100%通过率）
│   ├── venv/                 # Python 虚拟环境
│   └── requirements.txt       # Python 依赖
│
├── frontend/                # 前端应用（原生 JavaScript）
│   ├── index.html            # 主页面
│   ├── app.js                # 主逻辑
│   ├── components.js         # 组件库
│   └── styles.css            # 样式文件
│
├── docs/                   # 项目文档
│   ├── STATUS.md            # 系统状态（最新）
│   ├── TODO_FIX_PLAN.md    # 修复计划（最新）
│   ├── ARCHITECTURE.md      # 技术架构
│   └── archive/             # 归档文档
│       ├── progress.md        # 旧进度日志
│       ├── task_plan.md       # 原始任务规划
│       └── findings.md        # 需求分析文档
│
└── README.md               # 本文件
```

---

## 开发进度

### ✅ 已完成（Phase 1-5）
- Phase 1: 需求分析与技术架构设计
- Phase 2: 知识库构建与 RAG 系统设计
- Phase 3: 智能分诊状态机实现
- Phase 4: 大模型集成与提示词工程
- Phase 5: 安全机制与合规实现

### 🔄 部分完成（Phase 6-10）
- Phase 6: 用户档案与记忆系统（核心功能完成，扩展功能待开发）
- Phase 7: 前端交互与用户体验优化（基础功能完成，高级优化待开发）
- Phase 8: 测试评估体系构建（单元测试完成，E2E 测试待开发）
- Phase 9: 系统集成与端到端测试（核心功能集成完成）
- Phase 10: 文档编写与交付（核心文档完成，扩展文档待编写）

---

## 许可证

MIT License

---

## 联系方式

- 作者: 张杨
- 项目地址: [GitHub](https://github.com/your-repo)

---

*最后更新: 2026-02-13 by Claude Code*
