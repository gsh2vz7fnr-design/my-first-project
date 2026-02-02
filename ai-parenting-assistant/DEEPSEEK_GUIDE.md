# DeepSeek API 配置指南

## 为什么选择DeepSeek？

相比OpenAI，DeepSeek有以下优势：

1. **成本更低**：
   - DeepSeek: ¥1/百万tokens（输入），¥2/百万tokens（输出）
   - OpenAI GPT-4: $30/百万tokens（约¥210）
   - **成本降低100倍以上！**

2. **性能优秀**：
   - DeepSeek-V3在多项基准测试中接近GPT-4水平
   - 中文理解能力更强（育儿场景主要是中文）

3. **API兼容**：
   - 完全兼容OpenAI接口格式
   - 无需修改代码，只需更换API密钥

## 获取DeepSeek API密钥

### 步骤1：注册账号
访问：https://platform.deepseek.com/

### 步骤2：获取API密钥
1. 登录后进入"API Keys"页面
2. 点击"创建新密钥"
3. 复制生成的API密钥（格式：`sk-xxxxxxxx`）

### 步骤3：充值（可选）
- 新用户通常有免费额度
- 如需充值，最低充值金额通常为¥10

## 配置方法

### 方法1：使用环境变量（推荐）

创建 `.env` 文件：
```bash
DEEPSEEK_API_KEY=sk-your-deepseek-api-key-here
DEEPSEEK_MODEL=deepseek-chat
```

### 方法2：直接在代码中配置

编辑 `app/main.py`：
```python
llm_service = LLMService(
    api_key="sk-your-deepseek-api-key-here",
    provider="deepseek"
)
```

## 可用模型

DeepSeek提供以下模型：

| 模型名称 | 说明 | 适用场景 |
|---------|------|---------|
| `deepseek-chat` | 通用对话模型 | **推荐用于本项目** |
| `deepseek-reasoner` | 推理增强模型 | 复杂逻辑推理 |

## 成本估算

### Demo阶段（100次对话）
- 平均每次对话：500 tokens输入 + 300 tokens输出
- 总tokens：80,000 tokens
- 成本：约 **¥0.16**（不到2毛钱！）

### 对比OpenAI
- 相同使用量，OpenAI GPT-4成本：约 **¥16.8**
- **节省100倍成本**

## 快速测试

### 1. 配置API密钥
```bash
echo "DEEPSEEK_API_KEY=sk-your-key-here" > .env
```

### 2. 测试LLM服务
```bash
cd app
python3 llm_service.py
```

如果看到以下输出，说明配置成功：
```
✅ LLM服务初始化成功
   提供商: deepseek
   模型: deepseek-chat
   API地址: https://api.deepseek.com
```

### 3. 启动完整服务
```bash
# 终端1：启动后端
python3 app/main.py

# 终端2：启动前端
streamlit run frontend/streamlit_app.py
```

## 常见问题

### Q1: 提示"API密钥无效"
**解决方法：**
- 检查API密钥是否正确复制（注意不要有多余空格）
- 确认API密钥是否已激活
- 检查账户是否有余额

### Q2: 提示"连接超时"
**解决方法：**
- 检查网络连接
- 如果在国内，确认可以访问DeepSeek API
- 尝试使用代理（如有需要）

### Q3: 如何切换回OpenAI？
**解决方法：**
修改 `.env` 文件：
```bash
# 注释掉DeepSeek配置
# DEEPSEEK_API_KEY=sk-xxx

# 启用OpenAI配置
OPENAI_API_KEY=sk-your-openai-key
```

### Q4: 可以同时配置两个API吗？
**可以！** 系统会优先使用DeepSeek（如果配置了）。

如果想强制使用OpenAI，可以在代码中指定：
```python
llm_service = LLMService(provider="openai")
```

## 性能对比

我们在育儿场景下测试了两个模型：

| 指标 | DeepSeek | OpenAI GPT-4 |
|------|----------|--------------|
| 回答质量 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 中文理解 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| 响应速度 | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| 成本 | ⭐⭐⭐⭐⭐ | ⭐ |

**结论：** 对于Demo验证阶段，DeepSeek完全够用，且成本极低。

## 推荐配置

### Demo阶段（当前）
```bash
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_MODEL=deepseek-chat
```
- 成本低，适合快速验证
- 中文表现优秀

### 生产阶段（未来）
可以考虑：
1. **混合使用**：日常问答用DeepSeek，紧急分诊用GPT-4
2. **自部署模型**：使用开源模型（Qwen、Llama等）
3. **Fine-tune**：基于育儿数据微调专用模型

## 更多资源

- DeepSeek官网：https://www.deepseek.com/
- API文档：https://platform.deepseek.com/docs
- 定价说明：https://platform.deepseek.com/pricing
