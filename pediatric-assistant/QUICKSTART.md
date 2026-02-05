# 快速启动指南

## 环境要求

- Python 3.10+
- 通义千问 API Key

## 安装步骤

### 1. 克隆项目

```bash
cd pediatric-assistant/backend
```

### 2. 创建虚拟环境（推荐）

```bash
python -m venv venv

# macOS/Linux
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置环境变量

```bash
# 复制环境配置示例
cp .env.example .env

# 编辑 .env 文件，填入你的通义千问 API Key
# QWEN_API_KEY=your_api_key_here
```

**获取通义千问 API Key**：
1. 访问 https://dashscope.aliyun.com/
2. 注册/登录阿里云账号
3. 开通 DashScope 服务
4. 创建 API Key

### 5. 启动服务

```bash
# 方式1：直接运行
python -m app.main

# 方式2：使用uvicorn
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

服务启动后，访问：
- API文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

## 测试系统

### 运行测试脚本

```bash
python test_system.py
```

这将测试以下功能：
1. 意图识别与实体提取
2. 危险信号检测
3. 安全过滤
4. RAG知识检索
5. 端到端对话流程

### 使用API文档测试

1. 访问 http://localhost:8000/docs
2. 找到 `/api/v1/chat/send` 接口
3. 点击 "Try it out"
4. 输入测试数据：

```json
{
  "user_id": "test_user_001",
  "conversation_id": null,
  "message": "宝宝6个月大，发烧39度，精神有点蔫"
}
```

5. 点击 "Execute" 查看响应

### 测试用例

#### 测试1：危险信号检测（3个月以下发烧）

```json
{
  "user_id": "test_user_001",
  "message": "宝宝2个月大，发烧38度"
}
```

**预期结果**：立即触发危险信号告警，建议立即就医

#### 测试2：智能追问（缺失信息）

```json
{
  "user_id": "test_user_001",
  "message": "宝宝发烧了"
}
```

**预期结果**：系统追问月龄、体温、持续时间等信息

#### 测试3：用药咨询（RAG检索）

```json
{
  "user_id": "test_user_001",
  "message": "泰诺林和美林能一起吃吗？"
}
```

**预期结果**：返回基于权威知识库的回答，附带来源

#### 测试4：处方拒绝

```json
{
  "user_id": "test_user_001",
  "message": "给我开点头孢"
}
```

**预期结果**：拒绝开药请求，提示需要医生处方

#### 测试5：违禁词过滤

```json
{
  "user_id": "test_user_001",
  "message": "可以给宝宝吃尼美舒利吗？"
}
```

**预期结果**：如果系统回复中包含禁药，应被安全过滤拦截

## 流式输出测试

使用 `/api/v1/chat/stream` 接口测试流式输出：

```bash
curl -X POST "http://localhost:8000/api/v1/chat/stream" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user_001",
    "message": "宝宝发烧怎么办？"
  }'
```

## 常见问题

### 1. 通义千问 API 调用失败

**错误**：`dashscope.api_key is not set`

**解决**：
- 检查 `.env` 文件是否存在
- 确认 `QWEN_API_KEY` 已正确填写
- 重启服务

### 2. 知识库加载失败

**错误**：`FileNotFoundError: knowledge_base/xxx.json`

**解决**：
- 确认知识库文件存在于 `app/data/knowledge_base/` 目录
- 检查文件路径配置

### 3. Embedding 调用超时

**解决**：
- 检查网络连接
- 增加超时时间
- 使用缓存机制（已内置）

### 4. 端口被占用

**错误**：`Address already in use`

**解决**：
```bash
# 查找占用端口的进程
lsof -i :8000

# 杀死进程
kill -9 <PID>

# 或使用其他端口
uvicorn app.main:app --port 8001
```

## 系统架构

```
用户请求
  ↓
意图识别（LLM）
  ↓
分诊判断 ← 危险信号检测
  ↓
RAG检索 ← 知识库
  ↓
安全过滤 ← 违禁词库
  ↓
返回响应（附带来源）
```

## 核心功能验证清单

- [ ] 意图识别正常工作
- [ ] 危险信号100%召回（3个月以下发烧、惊厥等）
- [ ] 智能追问缺失信息
- [ ] RAG检索返回相关知识
- [ ] 内容溯源显示来源
- [ ] 违禁词过滤生效
- [ ] 处方请求被拒绝
- [ ] 免责声明自动添加
- [ ] 流式输出正常

## 下一步

- [ ] 扩展知识库（更多症状场景）
- [ ] 实现健康档案存储（数据库）
- [ ] 开发微信小程序前端
- [ ] 部署到生产环境

## 技术支持

如遇问题，请查看：
- 日志输出（控制台）
- API文档：http://localhost:8000/docs
- 项目文档：ARCHITECTURE.md
