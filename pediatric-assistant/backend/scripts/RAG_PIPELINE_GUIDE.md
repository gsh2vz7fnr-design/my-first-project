# RAG数据管道实现总结

## 项目概述

为《美国儿科学会育儿百科》创建的RAG数据管道，将两个Markdown分册文件处理并存入ChromaDB向量数据库。

## 文件结构

```
pediatric-assistant/backend/
├── scripts/
│   ├── ingest_md_to_vector.py      # 主脚本（完整流程，含API调用）
│   ├── test_ingest_preview.py      # 测试预览脚本（不含API调用）
│   ├── README.md                    # 使用说明
│   └── RAG_PIPELINE_GUIDE.md       # 本文档
├── requirements.txt                 # 依赖配置
├── .env                            # 环境变量配置
└── chroma_db/                      # ChromaDB数据持久化目录（运行后生成）
```

## 核心功能实现

### 1. 文件读取与元数据标记

```python
# 分别处理两个文件，标记不同的元数据
part1: {"source_file": "part1", "page_range": "1-600"}
part2: {"source_file": "part2", "page_range": "601-1054"}
```

### 2. Markdown结构切片

使用 `MarkdownHeaderTextSplitter` 按标题层级切片：
- 标题层级：`[("#", "h1"), ("##", "h2"), ("###", "h3")]`
- 标题信息自动提取到metadata中

### 3. 上下文增强（关键创新）

将标题路径拼接到正文前面，确保检索时能匹配到层级关系：

```
【背景: 第1章 为新生儿的到来做准备 (来源: part1, 页码: 1-600)】

原文内容...
```

### 4. 二次切片

使用 `RecursiveCharacterTextSplitter` 处理超过800 tokens的chunk：
- chunk_size: 800 tokens
- chunk_overlap: 100 tokens
- 分隔符：`\n\n\n`, `\n\n`, `\n`, `。`, `！`, `？`, ` `, ``

### 5. 向量化与入库

- 向量数据库：ChromaDB（本地持久化）
- Embedding模型：OpenAI text-embedding-3-small
- 批处理：batch_size=100

## 处理结果统计

| 文件 | 初始chunk数 | 最终chunk数 | 总tokens |
|------|------------|------------|---------|
| part1 (1-600页) | 500 | 1144 | ~470K |
| part2 (601-1054页) | 528 | 945 | ~385K |
| **总计** | **1028** | **2089** | **~855K** |

## 快速开始

### 安装依赖

```bash
cd /Users/zhang/Desktop/Claude/pediatric-assistant/backend

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 运行测试预览（推荐第一步）

```bash
source venv/bin/activate
python scripts/test_ingest_preview.py
```

### 运行完整脚本

需要先配置OpenAI API密钥：

**方法1：修改.env文件**
```bash
# 在.env文件中添加
OPENAI_API_KEY=sk-your-api-key-here
```

**方法2：命令行传入**
```bash
python scripts/ingest_md_to_vector.py --api-key sk-your-api-key-here
```

### 命令行参数

```bash
python scripts/ingest_md_to_vector.py \
    --api-key sk-xxx \
    --collection parenting_encyclopedia \
    --batch-size 100 \
    --no-preview
```

## 示例输出

```
================================================================================
样本预览（请确认处理效果）
================================================================================

--- 样本 1 ---
Token数: 645
来源: part1
页码范围: 1-600
标题:
  h1: 第1章 为新生儿的到来做准备

内容预览:
【背景: 第1章 为新生儿的到来做准备 (来源: part1, 页码: 1-600)】

# 第1章 为新生儿的到来做准备

妊娠期是一个充满期待与兴奋、需要做许多准备工作的时期...
...
```

## 技术栈

- **Python 3.x**
- **LangChain** - 文档处理和切片
- **ChromaDB** - 向量数据库
- **OpenAI API** - text-embedding-3-small Embedding模型
- **tiktoken** - Token计数
- **tqdm** - 进度条显示

## 依赖版本

```
langchain>=0.1.0
langchain-openai>=0.0.5
langchain-community>=0.0.10
langchain-text-splitters>=0.0.1
langchain-core>=0.1.0
chromadb>=0.4.22
tiktoken>=0.5.2
tqdm>=4.66.0
```

## 注意事项

1. **API费用**: text-embedding-3-small是付费服务，使用前请了解OpenAI定价
2. **Markdown结构**: 源文件主要只有一级标题，h2/h3元数据可能为空
3. **虚拟环境**: 强烈建议使用虚拟环境隔离依赖
4. **首次运行**: 建议先运行test_ingest_preview.py确认处理效果

## 后续集成

向量数据库创建后，可在RAG应用中加载使用：

```python
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings

# 加载向量数据库
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
vector_store = Chroma(
    collection_name="parenting_encyclopedia",
    embedding_function=embeddings,
    persist_directory="./chroma_db"
)

# 检索相关文档
results = vector_store.similarity_search("宝宝发烧了怎么办", k=3)
```

## 故障排查

### 问题1：ModuleNotFoundError
```
解决方案：激活虚拟环境后安装依赖
source venv/bin/activate
pip install -r requirements.txt
```

### 问题2：未找到OPENAI_API_KEY
```
解决方案：在.env文件中配置或使用--api-key参数传入
```

### 问题3：ChromaDB版本兼容问题
```
解决方案：确保chromadb>=0.4.22
pip install --upgrade chromadb
```
