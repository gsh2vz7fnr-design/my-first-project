# AI育儿助手 Demo

## 项目简介
一个基于LLM + RAG的智能育儿助手，提供：
- 🚨 危险信号检测与分诊
- 💬 日常护理问答
- 💊 用药咨询指导

## 技术栈
- **后端**: FastAPI (Python)
- **LLM**: DeepSeek API / OpenAI GPT-4（可选）
- **向量数据库**: ChromaDB
- **前端**: Streamlit

💡 **推荐使用DeepSeek API**：成本仅为OpenAI的1%，中文表现优秀！

## 项目结构
```
ai-parenting-assistant/
├── app/
│   ├── main.py              # FastAPI主程序
│   ├── intent_router.py     # 意图分类路由
│   ├── danger_detector.py   # 危险信号检测
│   ├── rag_engine.py        # RAG知识库引擎
│   ├── llm_service.py       # LLM调用服务
│   └── safety_guard.py      # 安全护栏
├── knowledge_base/
│   └── documents/           # 知识库文档
├── data/
│   └── danger_signals.json  # 危险信号规则
├── frontend/
│   └── streamlit_app.py     # Streamlit聊天界面
├── requirements.txt
└── README.md
```

## 快速开始

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

**方式1：使用DeepSeek API（推荐，成本低100倍）**
```bash
cp .env.example .env
# 编辑.env文件，填入：
DEEPSEEK_API_KEY=sk-your-deepseek-api-key-here
```

**方式2：使用OpenAI API**
```bash
cp .env.example .env
# 编辑.env文件，填入：
OPENAI_API_KEY=sk-your-openai-api-key-here
```

📖 **详细配置指南**：查看 [DEEPSEEK_GUIDE.md](DEEPSEEK_GUIDE.md)

### 2.5 测试API连接（推荐）
```bash
python3 test_deepseek.py
```

### 3. 初始化知识库
```bash
python3 scripts/init_knowledge_base.py
```

### 4. 启动后端服务
```bash
python3 app/main.py
```
或使用uvicorn：
```bash
uvicorn app.main:app --reload
```

### 5. 启动前端界面
```bash
streamlit run frontend/streamlit_app.py
```

## 核心功能

### 1. 危险信号检测
基于规则引擎，识别需要立即就医的紧急情况

### 2. 意图路由
自动识别用户意图：
- 紧急分诊
- 日常护理
- 用药咨询

### 3. RAG知识库
基于权威育儿指南构建的知识库，确保回答准确性

### 4. 安全护栏
- 不诊断疾病
- 不推荐具体剂量
- 强制免责声明

## 开发计划
- [x] 项目架构设计
- [x] 核心模块实现
- [x] 知识库构建
- [x] 前端界面开发
- [x] DeepSeek API集成
- [ ] 充分测试与优化
- [ ] 专家审核知识库

## 文档导航
- 📖 [快速启动指南](QUICKSTART.md)
- 💰 [DeepSeek配置指南](DEEPSEEK_GUIDE.md)（推荐阅读）
- 📊 [项目总结](PROJECT_SUMMARY.md)
