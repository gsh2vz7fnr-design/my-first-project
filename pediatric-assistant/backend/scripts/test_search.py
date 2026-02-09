#!/usr/bin/env python3
"""
测试向量数据库检索
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# 添加项目根目录到路径
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 加载环境变量
load_dotenv(PROJECT_ROOT / ".env")

from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings

print("="*80)
print("测试向量数据库检索")
print("="*80)

# 初始化embeddings
embeddings = OpenAIEmbeddings(
    model="BAAI/bge-m3",
    openai_api_key=os.getenv("SILICONFLOW_API_KEY"),
    openai_api_base=os.getenv("SILICONFLOW_BASE_URL")
)

# 加载向量数据库
vector_store = Chroma(
    collection_name="parenting_encyclopedia",
    embedding_function=embeddings,
    persist_directory=str(PROJECT_ROOT / "chroma_db")
)

# 测试检索
queries = [
    "宝宝发烧了怎么办",
    "婴儿便秘怎么处理",
    "孩子咳嗽有痰",
    "宝宝皮疹过敏",
    "小儿腹痛"
]

for query in queries:
    print(f"\n查询: {query}")
    print("-" * 40)

    results = vector_store.similarity_search_with_score(query, k=2)

    for i, (doc, score) in enumerate(results, 1):
        print(f"\n结果 {i} (相似度: {score:.4f}):")
        print(f"  来源: {doc.metadata.get('source_file', 'N/A')}")
        print(f"  页码: {doc.metadata.get('page_range', 'N/A')}")
        if 'h1' in doc.metadata:
            print(f"  章节: {doc.metadata.get('h1', 'N/A')}")
        # 显示前200字符
        content = doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content
        print(f"  内容: {content}")

print("\n" + "="*80)
