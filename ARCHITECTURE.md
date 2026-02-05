# 智能儿科分诊与护理助手 - 技术架构文档

## 系统架构图

```
┌─────────────────────────────────────────────────┐
│              微信小程序前端                        │
│  (对话界面、流式输出、溯源展示、档案管理)              │
└─────────────────┬───────────────────────────────┘
                  │ HTTPS/WebSocket
┌─────────────────▼───────────────────────────────┐
│              后端服务 (Python FastAPI)            │
│  ┌──────────────────────────────────────────┐   │
│  │  意图识别 & 实体提取 (通义千问API)         │   │
│  └──────────────┬───────────────────────────┘   │
│  ┌──────────────▼───────────────────────────┐   │
│  │  分诊状态机 (硬编码规则引擎)               │   │
│  │  - 危险信号熔断                           │   │
│  │  - 槽位填充与追问                         │   │
│  │  - 三级分诊决策                           │   │
│  └──────────────┬───────────────────────────┘   │
│  ┌──────────────▼───────────────────────────┐   │
│  │  RAG系统 (向量检索 + 知识库)               │   │
│  │  - 向量数据库 (Milvus Lite/FAISS)         │   │
│  │  - 白名单知识库                           │   │
│  │  - 内容溯源                               │   │
│  └──────────────┬───────────────────────────┘   │
│  ┌──────────────▼───────────────────────────┐   │
│  │  安全层 (违禁词过滤 + 免责声明)            │   │
│  └──────────────────────────────────────────┘   │
└─────────────────┬───────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────┐
│              数据存储层                           │
│  - MySQL/PostgreSQL (用户档案、对话历史)         │
│  - Redis (会话缓存、限流)                        │
│  - 向量数据库 (知识库向量)                       │
└─────────────────────────────────────────────────┘
```

## 技术栈选型

### 前端
- **框架**: 微信小程序原生开发
- **UI组件**: WeUI / Vant Weapp
- **状态管理**: 小程序原生 globalData + Storage
- **网络请求**: wx.request + WebSocket (流式输出)

### 后端
- **框架**: Python FastAPI (异步高性能)
- **大模型**: 通义千问 API (qwen-max / qwen-turbo)
- **向量数据库**: FAISS (轻量级，适合MVP) 或 Milvus Lite
- **数据库**: PostgreSQL (用户档案、对话历史)
- **缓存**: Redis (会话状态、限流)
- **任务队列**: Celery (异步档案提取)

### 部署
- **服务器**: 阿里云ECS / 腾讯云轻量服务器
- **容器化**: Docker + Docker Compose
- **反向代理**: Nginx
- **HTTPS**: Let's Encrypt 免费证书
- **监控**: Prometheus + Grafana (可选)

## 项目目录结构

```
pediatric-assistant/
├── backend/                    # 后端服务
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py            # FastAPI 入口
│   │   ├── config.py          # 配置文件
│   │   ├── models/            # 数据模型
│   │   │   ├── user.py
│   │   │   ├── conversation.py
│   │   │   └── health_profile.py
│   │   ├── services/          # 业务逻辑
│   │   │   ├── llm_service.py          # 大模型调用
│   │   │   ├── triage_engine.py        # 分诊状态机
│   │   │   ├── rag_service.py          # RAG检索
│   │   │   ├── safety_filter.py        # 安全过滤
│   │   │   └── profile_extractor.py    # 档案提取
│   │   ├── routers/           # API路由
│   │   │   ├── chat.py
│   │   │   ├── profile.py
│   │   │   └── health.py
│   │   ├── utils/             # 工具函数
│   │   │   ├── prompt_templates.py
│   │   │   └── validators.py
│   │   └── data/              # 数据文件
│   │       ├── knowledge_base/         # 知识库
│   │       │   ├── fever.json
│   │       │   ├── fall.json
│   │       │   └── vomit.json
│   │       ├── triage_rules/           # 分诊规则
│   │       │   ├── danger_signals.json
│   │       │   └── slot_definitions.json
│   │       └── blacklist/              # 违禁词库
│   │           ├── general_blacklist.txt
│   │           └── medical_blacklist.txt
│   ├── tests/                 # 测试
│   │   ├── test_triage.py
│   │   ├── test_rag.py
│   │   └── test_safety.py
│   ├── requirements.txt       # Python依赖
│   ├── Dockerfile
│   └── docker-compose.yml
│
├── miniprogram/               # 微信小程序前端
│   ├── pages/
│   │   ├── chat/              # 对话页面
│   │   │   ├── chat.wxml
│   │   │   ├── chat.wxss
│   │   │   ├── chat.js
│   │   │   └── chat.json
│   │   ├── profile/           # 档案页面
│   │   │   ├── profile.wxml
│   │   │   ├── profile.wxss
│   │   │   ├── profile.js
│   │   │   └── profile.json
│   │   └── index/             # 首页
│   │       ├── index.wxml
│   │       ├── index.wxss
│   │       ├── index.js
│   │       └── index.json
│   ├── components/            # 组件
│   │   ├── message-bubble/    # 消息气泡
│   │   ├── source-tag/        # 溯源角标
│   │   └── disclaimer/        # 免责声明
│   ├── utils/
│   │   ├── api.js             # API封装
│   │   └── websocket.js       # WebSocket封装
│   ├── app.js
│   ├── app.json
│   └── app.wxss
│
├── docs/                      # 文档
│   ├── api.md                 # API文档
│   ├── deployment.md          # 部署文档
│   └── testing.md             # 测试文档
│
├── scripts/                   # 脚本
│   ├── build_knowledge_base.py    # 构建知识库
│   ├── evaluate.py                # 评估脚本
│   └── import_test_cases.py       # 导入测试用例
│
├── task_plan.md               # 任务规划
├── findings.md                # 发现记录
├── progress.md                # 进度日志
└── README.md                  # 项目说明
```

## 核心模块设计

### 1. 意图识别 & 实体提取 (llm_service.py)

```python
class LLMService:
    def __init__(self):
        self.client = DashScope(api_key=config.QWEN_API_KEY)

    async def extract_intent_and_entities(self, user_input: str, context: dict):
        """
        提取用户意图和症状实体
        返回: {
            "intent": "triage" | "consult" | "medication" | "care",
            "entities": {
                "symptom": "发烧",
                "temperature": "39度",
                "duration": "2小时",
                "mental_state": "精神萎靡"
            }
        }
        """
        pass
```

### 2. 分诊状态机 (triage_engine.py)

```python
class TriageEngine:
    def __init__(self):
        self.danger_signals = load_danger_signals()
        self.slot_definitions = load_slot_definitions()

    def check_danger_signals(self, entities: dict) -> Optional[str]:
        """检查危险信号，返回告警文案或None"""
        pass

    def get_missing_slots(self, symptom: str, entities: dict) -> List[str]:
        """获取缺失的槽位"""
        pass

    def make_triage_decision(self, symptom: str, entities: dict) -> dict:
        """
        做出分诊决策
        返回: {
            "level": "emergency" | "observe" | "online",
            "reason": "...",
            "action": "..."
        }
        """
        pass
```

### 3. RAG系统 (rag_service.py)

```python
class RAGService:
    def __init__(self):
        self.vector_db = FAISS.load_local("knowledge_base_index")
        self.embeddings = DashScopeEmbeddings()

    async def retrieve(self, query: str, top_k: int = 3) -> List[dict]:
        """
        检索相关知识
        返回: [
            {
                "content": "...",
                "source": "默沙东诊疗手册 P12",
                "score": 0.95
            }
        ]
        """
        pass

    def format_with_citations(self, answer: str, sources: List[dict]) -> str:
        """格式化答案，添加溯源角标"""
        pass
```

### 4. 安全过滤 (safety_filter.py)

```python
class SafetyFilter:
    def __init__(self):
        self.general_blacklist = load_blacklist("general")
        self.medical_blacklist = load_blacklist("medical")

    def filter_output(self, text: str) -> Tuple[bool, Optional[str]]:
        """
        过滤输出内容
        返回: (is_safe, fallback_message)
        """
        pass
```

## 数据模型设计

### 用户档案 (health_profile)

```json
{
  "user_id": "wx_openid_xxx",
  "baby_info": {
    "age_months": 6,
    "weight_kg": 8.5,
    "gender": "male"
  },
  "allergy_history": [
    {
      "allergen": "蛋黄",
      "reaction": "呕吐",
      "confirmed": true,
      "date": "2026-01-15"
    }
  ],
  "medical_history": [
    {
      "condition": "热性惊厥",
      "date": "2025-12-20",
      "confirmed": true
    }
  ],
  "medication_history": [
    {
      "drug": "泰诺林",
      "note": "喂不进去",
      "date": "2026-02-01"
    }
  ],
  "created_at": "2026-01-01T00:00:00Z",
  "updated_at": "2026-02-05T10:30:00Z"
}
```

### 对话记录 (conversation)

```json
{
  "conversation_id": "conv_xxx",
  "user_id": "wx_openid_xxx",
  "messages": [
    {
      "role": "user",
      "content": "宝宝发烧39度",
      "timestamp": "2026-02-05T22:30:00Z"
    },
    {
      "role": "assistant",
      "content": "...",
      "metadata": {
        "intent": "triage",
        "entities": {...},
        "sources": [...]
      },
      "timestamp": "2026-02-05T22:30:02Z"
    }
  ],
  "status": "active" | "closed",
  "created_at": "2026-02-05T22:30:00Z"
}
```

## API接口设计

### 1. 发送消息 (流式)

```
POST /api/v1/chat/stream
Content-Type: application/json

Request:
{
  "user_id": "wx_openid_xxx",
  "conversation_id": "conv_xxx",
  "message": "宝宝发烧39度，精神有点蔫"
}

Response: (Server-Sent Events)
data: {"type": "emotion", "content": "听到宝宝发烧确实让人很揪心..."}
data: {"type": "content", "content": "根据您的描述..."}
data: {"type": "citation", "source": "默沙东 P12"}
data: {"type": "done"}
```

### 2. 获取健康档案

```
GET /api/v1/profile/{user_id}

Response:
{
  "code": 0,
  "data": {
    "baby_info": {...},
    "allergy_history": [...],
    "medical_history": [...]
  }
}
```

### 3. 更新健康档案

```
PUT /api/v1/profile/{user_id}
Content-Type: application/json

Request:
{
  "baby_info": {
    "age_months": 7,
    "weight_kg": 9.0
  }
}

Response:
{
  "code": 0,
  "message": "更新成功"
}
```

## 下一步行动

现在我将开始创建项目结构并实现核心模块。请确认是否继续？
