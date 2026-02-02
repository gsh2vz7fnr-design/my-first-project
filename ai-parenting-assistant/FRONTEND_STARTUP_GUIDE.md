# 🚀 前端启动完整指南

## 问题诊断

你遇到"无法访问 http://localhost:8501/"的原因是：
- ❌ Streamlit服务还没有启动
- ❌ 依赖包还没有安装完成

## 解决方案（3种方式）

---

### 方式1：完整启动（推荐）

#### 步骤1：创建虚拟环境

```bash
cd /Users/zhang/Desktop/Claude安装/ai-parenting-assistant

# 创建虚拟环境
python3 -m venv venv_ai_parenting

# 激活虚拟环境
source venv_ai_parenting/bin/activate
```

#### 步骤2：安装依赖

```bash
# 在虚拟环境中安装
pip install streamlit fastapi uvicorn openai python-dotenv requests

# 或者安装完整依赖（需要等待5-10分钟）
pip install -r requirements.txt
```

#### 步骤3：配置API密钥（可选）

```bash
# 如果你有DeepSeek API密钥
echo "DEEPSEEK_API_KEY=sk-your-key-here" > .env

# 如果暂时没有，可以先跳过这步，只看界面
```

#### 步骤4：启动前端

```bash
# 启动Streamlit前端
streamlit run frontend/streamlit_app.py
```

浏览器会自动打开 http://localhost:8501

---

### 方式2：仅安装Streamlit（快速预览界面）

如果你只想快速看到界面效果，不需要完整功能：

```bash
# 激活虚拟环境
source venv_ai_parenting/bin/activate

# 只安装streamlit（很快）
pip install streamlit

# 启动预览版界面
streamlit run frontend/demo_preview.py
```

这个预览版会显示界面布局，但不会真正调用AI。

---

### 方式3：使用系统Python（不推荐）

如果你不想用虚拟环境：

```bash
# 使用--break-system-packages标志
pip3 install --break-system-packages streamlit fastapi uvicorn openai python-dotenv requests

# 启动前端
streamlit run frontend/streamlit_app.py
```

⚠️ 注意：这种方式可能影响系统Python环境。

---

## 启动后的效果

### 1. 终端输出

```
  You can now view your Streamlit app in your browser.

  Local URL: http://localhost:8501
  Network URL: http://192.168.x.x:8501
```

### 2. 浏览器自动打开

- 显示"👶 AI育儿助手 Demo"标题
- 左侧有使用说明和测试场景
- 中间是聊天对话区域
- 底部有输入框

### 3. 如果后端未启动

界面会显示：
- ❌ 后端服务未启动
- 💡 提示如何启动后端

---

## 完整启动流程（前端+后端）

### 终端1：启动后端

```bash
cd /Users/zhang/Desktop/Claude安装/ai-parenting-assistant
source venv_ai_parenting/bin/activate

# 配置API密钥（必须）
echo "DEEPSEEK_API_KEY=sk-your-key" > .env

# 启动后端
python3 app/main.py
```

看到以下输出说明成功：
```
INFO:     Started server process
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 终端2：启动前端

```bash
cd /Users/zhang/Desktop/Claude安装/ai-parenting-assistant
source venv_ai_parenting/bin/activate

# 启动前端
streamlit run frontend/streamlit_app.py
```

---

## 常见问题

### Q1: 虚拟环境激活失败

```bash
# 确保在正确的目录
cd /Users/zhang/Desktop/Claude安装/ai-parenting-assistant

# 重新创建虚拟环境
rm -rf venv_ai_parenting
python3 -m venv venv_ai_parenting
source venv_ai_parenting/bin/activate
```

### Q2: pip安装很慢

```bash
# 使用国内镜像源
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple streamlit fastapi uvicorn openai python-dotenv requests
```

### Q3: 端口8501被占用

```bash
# 查看占用端口的进程
lsof -i :8501

# 杀死进程
kill -9 <PID>

# 或使用其他端口
streamlit run frontend/streamlit_app.py --server.port 8502
```

### Q4: 浏览器没有自动打开

手动访问：http://localhost:8501

### Q5: 显示"后端服务未启动"

这是正常的！说明前端已经成功启动了。

要使用完整功能，需要：
1. 获取DeepSeek API密钥
2. 配置.env文件
3. 启动后端服务

---

## 快速命令（复制粘贴）

### 最简单的启动方式（仅看界面）

```bash
cd /Users/zhang/Desktop/Claude安装/ai-parenting-assistant
python3 -m venv venv_ai_parenting
source venv_ai_parenting/bin/activate
pip install streamlit
streamlit run frontend/demo_preview.py
```

### 完整功能启动

```bash
cd /Users/zhang/Desktop/Claude安装/ai-parenting-assistant
source venv_ai_parenting/bin/activate
pip install streamlit fastapi uvicorn openai python-dotenv requests
echo "DEEPSEEK_API_KEY=sk-your-key" > .env
python3 app/main.py &
streamlit run frontend/streamlit_app.py
```

---

## 下一步

1. ✅ 先启动前端，看到界面
2. ✅ 获取DeepSeek API密钥（访问 https://platform.deepseek.com/）
3. ✅ 配置.env文件
4. ✅ 启动后端服务
5. ✅ 测试完整功能

---

## 需要帮助？

查看文档：
- **START_HERE.md** - 一站式使用指南
- **DEEPSEEK_GUIDE.md** - API配置指南
- **QUICKSTART.md** - 快速启动指南
