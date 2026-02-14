# 开发指南 - 智能儿科分诊与护理助手

> 版本: 1.1
> 更新日期: 2026-02-14

---

## 快速启动

### 1. 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

### 2. 配置环境变量

已提供 `.env` 文件，包含必要的配置：
- DeepSeek API Key
- 数据库连接
- 安全配置

### 3. 启动后端服务

```bash
cd backend
python app/main.py
# 或使用 uvicorn
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

服务启动后访问：
- API文档: http://localhost:8000/docs
- 健康检查: http://localhost:8000/health

### 4. 启动前端

```bash
cd frontend
python3 -m http.server 8002
```

访问: http://localhost:8002

---

## 项目结构

```
pediatric-assistant/
├── backend/
│   ├── app/
│   │   ├── config.py              # 配置管理
│   │   ├── main.py                # FastAPI入口
│   │   ├── models/                # 数据模型
│   │   │   ├── user.py           # 用户、对话、安全模型
│   │   │   └── evaluation.py     # 评估相关模型
│   │   ├── routers/              # API路由
│   │   │   ├── chat.py           # 对话API
│   │   │   └── profile.py        # 档案API
│   │   ├── services/             # 业务逻辑
│   │   │   ├── llm_service.py    # LLM调用
│   │   │   ├── rag_service.py    # RAG检索
│   │   │   ├── triage_engine.py  # 分诊引擎
│   │   │   ├── safety_filter.py  # 安全过滤
│   │   │   ├── stream_filter.py  # 流式安全过滤
│   │   │   ├── profile_service.py # 档案服务
│   │   │   ├── conversation_service.py # 对话服务
│   │   │   └── evaluation_service.py # 评估服务
│   │   ├── middleware/           # 中间件
│   │   │   └── performance.py    # 性能监控
│   │   └── data/                # 数据文件
│   │       ├── knowledge_base/   # 知识库（7个JSON文件）
│   │       ├── triage_rules/     # 分诊规则
│   │       └── blacklist/        # 黑名单（2个TXT文件）
│   ├── evaluation/              # 评估脚本
│   │   └── run_evaluation.py    # 自动化评估
│   └── requirements.txt         # Python依赖
└── frontend/                   # 前端文件
    ├── index.html              # 主页面
    ├── app.js                  # 应用逻辑
    ├── components.js           # 组件库
    └── styles.css              # 样式
```

---

## API接口说明

### 对话接口

#### 发送消息（流式）
```
POST /api/v1/chat/stream
Content-Type: application/json

{
  "user_id": "test_user_001",
  "member_id": "optional_member_id",
  "conversation_id": "optional_conversation_id",
  "message": "宝宝发烧38度怎么办"
}
```

响应格式（Server-Sent Events）：
```
data: {"type": "metadata", "metadata": {"intent": "triage", ...}}

data: {"type": "content", "content": "部分回复内容"}

data: {"type": "done"}
```

成员一致性约束：
- 若 `conversation_id` 已绑定其他 `member_id`，接口返回 `member_mismatch`
- 前端收到 `member_mismatch` 后，必须提示用户新建会话，不可继续沿用旧会话

#### 发送消息（非流式）
```
POST /api/v1/chat/send
Content-Type: application/json

{
  "user_id": "test_user_001",
  "member_id": "optional_member_id",
  "conversation_id": "optional_conversation_id",
  "message": "宝宝昨晚发烧到39度"
}
```

#### 归档会话
```
POST /api/v1/chat/archive
Content-Type: application/json

{
  "user_id": "test_user_001",
  "conversation_id": "required_conversation_id",
  "member_id": "optional_for_double_check"
}
```

归档规则：
- 会话归档以会话记录中已绑定的 `member_id` 为准
- 若请求体携带 `member_id` 且与会话绑定不一致，返回 `member_mismatch` 并拒绝归档
- 若用户无成员档案，返回 `need_member_creation`

#### 获取对话历史
```
GET /api/v1/chat/history/{conversation_id}
```

### 健康档案接口

#### 获取档案
```
GET /api/v1/profile/{user_id}
```

#### 确认档案更新
```
POST /api/v1/profile/{user_id}/confirm
Content-Type: application/json

{
  "confirm": [...],
  "reject": [...]
}
```

---

## 运行评估

```bash
cd backend

# 运行自动化评估
python evaluation/run_evaluation.py \
  --test-file app/data/test_cases.json \
  --output-file evaluation_report.json

# 查看评估报告
cat evaluation_report.json
```

---

## 开发注意事项

### 1. 知识库更新

在 `app/data/knowledge_base/` 目录下添加或修改JSON文件，格式参考：

```json
{
  "topic": "症状名",
  "category": "分类",
  "source": "来源",
  "last_updated": "YYYY-MM",
  "entries": [
    {
      "id": "唯一ID",
      "title": "标题",
      "content": "内容",
      "source": "来源",
      "tags": ["标签1", "标签2"],
      "age_range": "适用年龄"
    }
  ]
}
```

### 2. 黑名单更新

编辑 `app/data/blacklist/` 目录下的TXT文件：
- 每行一个关键词
- `#` 开头的行为注释

### 3. 分诊规则更新

编辑 `app/data/triage_rules/danger_signals.json`

### 4. 安全规则

- **输入安全**: 检查处方意图、黑名单关键词
- **输出安全**: 流式输出时实时检测违禁词
- **合规要求**: 拒绝开具处方、不能确诊疾病

### 5. 多成员会话隔离（新增）

- 首条消息确定并绑定会话 `member_id`（不可变）
- 切换就诊人时，前端需要清空当前会话上下文并创建新会话
- 前端使用 `localStorage` 持久化 `last_active_member_id:<user_id>`，刷新后恢复
- `age_months` 在推理阶段可由用户输入兜底，但档案与长期上下文应以 `birth_date` 动态计算

### 6. 数据迁移脚本

为解决历史数据中 `user_id/member_id` 混用问题，新增迁移脚本：

```bash
cd backend
python scripts/migrate_user_member_records.py --dry-run
python scripts/migrate_user_member_records.py --apply
```

说明：
- `--dry-run` 只输出待迁移统计，不写入数据库
- `--apply` 实际执行迁移，将旧记录统一绑定到真实成员

---

## 故障排查

### 后端无法启动

1. 检查依赖是否完整：`pip list | grep fastapi`
2. 检查端口占用：`lsof -i :8000`
3. 检查 `.env` 文件配置

### LLM调用失败

1. 检查 API Key: `echo $DEEPSEEK_API_KEY`
2. 检查网络连接: `curl https://api.deepseek.com/v1`

### 前端连接失败

1. 检查后端是否运行: `curl http://localhost:8000/health`
2. 检查浏览器控制台错误信息

---

## 性能指标

| 指标 | 目标值 | 说明 |
|-----|-------|------|
| 首字延迟 | < 1.5s | 流式输出第一个字符的延迟 |
| 急症召回率 | 100% | 危险症状识别准确率 |
| 拒答准确率 | > 95% | 安全拦截准确率 |

---

## 更新日志

### 2026-02-06
- 完成流式输出安全熔断
- 扩充知识库至7个主题（56条知识）
- 添加首次进入免责声明弹窗
- 完善自动化评估系统
