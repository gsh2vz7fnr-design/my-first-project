# RAG数据管道 - Markdown知识库向量化脚本

将《美国儿科学会育儿百科》的Markdown文件处理后存入向量数据库，用于RAG检索。

## 文件说明

| 文件 | 说明 |
|------|------|
| `ingest_md_to_vector.py` | 主脚本（完整流程，包含API调用） |
| `test_ingest_preview.py` | 测试预览脚本（不调用API，仅展示处理效果） |
| `setup_env.sh` | Linux/Mac环境设置脚本 |
| `setup_env.bat` | Windows环境设置脚本 |
| `verify_setup.py` | 环境验证脚本 |

## 快速开始

### 1. 设置环境

**Linux/Mac:**
```bash
cd /Users/zhang/Desktop/Claude/pediatric-assistant/backend
bash scripts/setup_env.sh
```

**Windows:**
```bash
cd pediatric-assistant\backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 验证环境

```bash
# 激活虚拟环境
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 验证安装
python scripts/verify_setup.py
```

### 3. 运行测试预览（推荐第一步）

```bash
python scripts/test_ingest_preview.py
```

### 4. 配置API密钥

在`.env`文件中配置（已预配置硅基流动API）：

```bash
# 硅基流动API配置（默认使用）
SILICONFLOW_API_KEY=sk-your-api-key-here
SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1
SILICONFLOW_EMBEDDING_MODEL=BAAI/bge-large-zh-v1.5

# 或使用OpenAI API
OPENAI_API_KEY=sk-your-openai-key-here
OPENAI_API_BASE=https://api.openai.com/v1
```

### 5. 运行完整脚本

```bash
# 默认使用硅基流动API
python scripts/ingest_md_to_vector.py

# 或使用OpenAI API
python scripts/ingest_md_to_vector.py --use-openai --api-key sk-xxx
```

## 支持的模型

### 硅基流动API（默认）

| 模型 | 说明 |
|------|------|
| `BAAI/bge-large-zh-v1.5` | 中文embedding，效果最好（默认） |
| `BAAI/bge-m3` | 多语言embedding |
| `Qwen/Qwen-Embedding-8B` | Qwen系列embedding |

### OpenAI API

| 模型 | 说明 |
|------|------|
| `text-embedding-3-small` | OpenAI轻量级embedding |
| `text-embedding-3-large` | OpenAI高质量embedding |

## 处理效果示例

```
--- 样本 1 ---
Token数: 645
来源: part1
页码范围: 1-600
标题: h1=第1章 为新生儿的到来做准备

内容:
【背景: 第1章 为新生儿的到来做准备 (来源: part1, 页码: 1-600)】

# 第1章 为新生儿的到来做准备
...
```

## 统计数据

- **总文档数**: 2089个chunk
- **总tokens**: ~855K
- **来源**: part1 (1-600页) + part2 (601-1054页)

## 命令行参数

```bash
python scripts/ingest_md_to_vector.py \
    --model BAAI/bge-large-zh-v1.5 \
    --collection parenting_encyclopedia \
    --batch-size 100 \
    --no-preview
```

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--model` | Embedding模型名称 | BAAI/bge-large-zh-v1.5 |
| `--collection` | 集合名称 | parenting_encyclopedia |
| `--batch-size` | 批处理大小 | 100 |
| `--api-key` | API密钥 | 从.env读取 |
| `--api-base` | API Base URL | 从.env读取 |
| `--use-openai` | 使用OpenAI而非硅基流动 | False |
| `--no-preview` | 跳过预览确认 | False |

## 环境变量

| 变量 | 说明 |
|------|------|
| `SILICONFLOW_API_KEY` | 硅基流动API密钥 |
| `SILICONFLOW_BASE_URL` | 硅基流动API地址 |
| `SILICONFLOW_EMBEDDING_MODEL` | 硅基流动模型名称 |
| `OPENAI_API_KEY` | OpenAI API密钥 |
| `OPENAI_API_BASE` | OpenAI API地址 |

## 注意事项

1. 默认使用硅基流动API（免费额度较高）
2. 建议使用虚拟环境
3. 首次运行建议先执行test_ingest_preview.py

详细文档请参考 `RAG_PIPELINE_GUIDE.md`
