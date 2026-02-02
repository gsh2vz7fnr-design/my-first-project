# 快速启动指南

## 项目已创建完成 ✅

项目结构：
```
ai-parenting-assistant/
├── app/                      # 后端核心代码
│   ├── main.py              # FastAPI主程序（整合所有模块）
│   ├── danger_detector.py   # 危险信号检测
│   ├── intent_router.py     # 意图分类路由
│   ├── rag_engine.py        # RAG知识库引擎
│   ├── llm_service.py       # LLM调用服务
│   └── safety_guard.py      # 安全护栏
├── data/
│   └── danger_signals.json  # 危险信号规则库
├── frontend/
│   └── streamlit_app.py     # Web聊天界面
├── scripts/
│   └── init_knowledge_base.py  # 初始化知识库
├── requirements.txt         # Python依赖
└── README.md               # 项目说明
```

## 启动步骤

### 1. 安装依赖（首次运行）
```bash
cd ai-parenting-assistant
pip install -r requirements.txt
```

### 2. 配置API密钥

**推荐使用DeepSeek API（成本低100倍！）**

创建 `.env` 文件：
```bash
cp .env.example .env
```

然后编辑 `.env` 文件，填入你的API密钥：

**方式1：使用DeepSeek（推荐）**
```bash
DEEPSEEK_API_KEY=sk-your-deepseek-api-key-here
```

**方式2：使用OpenAI**
```bash
OPENAI_API_KEY=sk-your-openai-api-key-here
```

💡 **如何获取DeepSeek API密钥？** 查看 [DEEPSEEK_GUIDE.md](DEEPSEEK_GUIDE.md)

### 3. 初始化知识库
```bash
python scripts/init_knowledge_base.py
```

### 4. 启动后端服务
```bash
cd app
python main.py
```
或者使用uvicorn：
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

后端服务将在 http://localhost:8000 启动

### 5. 启动前端界面（新终端窗口）
```bash
streamlit run frontend/streamlit_app.py
```

前端界面将在 http://localhost:8501 启动

## 测试用例

### 危险信号检测（应该触发警告）
- "宝宝发烧39.5度，精神很差，一直在睡觉"
- "宝宝从床上摔下来了，后脑勺着地，现在在呕吐"
- "宝宝呼吸很急促，嘴唇有点发紫"

### 日常护理问答
- "宝宝便秘了怎么办？"
- "宝宝身上起了红点，是湿疹吗？"
- "宝宝辅食第一口吃什么？"

### 用药咨询
- "美林和泰诺林能一起吃吗？"
- "宝宝发烧什么时候需要吃退烧药？"

## 核心功能说明

### 1. 危险信号检测（最高优先级）
- 基于规则引擎，识别紧急情况
- 一旦检测到危险信号，立即返回就医建议
- 规则可在 `data/danger_signals.json` 中配置

### 2. 意图路由
- 自动识别用户意图：紧急分诊/日常护理/用药咨询
- 基于关键词匹配（Demo阶段）
- 可升级为机器学习模型

### 3. RAG知识库
- 使用ChromaDB向量数据库
- 自动检索相关育儿知识
- 知识库可持续扩充

### 4. LLM生成回复
- 调用OpenAI GPT-4 API
- 根据意图使用不同的提示词
- 确保回复专业、温和、有同理心

### 5. 安全护栏
- 检查回复中是否包含诊断性语言
- 检查是否推荐具体剂量
- 自动添加免责声明

## API文档

启动后端后，访问：
- API文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

## 下一步优化方向

1. **扩充知识库**：添加更多权威育儿知识
2. **优化意图识别**：训练专门的分类模型
3. **增强危险信号检测**：添加更多规则，引入模型辅助
4. **添加多轮对话**：支持上下文记忆
5. **用户反馈机制**：收集用户评价，持续优化
6. **专家审核系统**：建立回答质量审核流程

## 注意事项

⚠️ **这是Demo版本，仅用于产品验证，不可直接用于生产环境**

- 需要OpenAI API密钥（会产生费用）
- 知识库内容需要儿科专家审核
- 危险信号规则需要医疗专业人员制定
- 必须经过充分测试和验证
