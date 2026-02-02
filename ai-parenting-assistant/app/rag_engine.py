"""
RAG知识库引擎
基于ChromaDB的向量检索系统
"""
import os
from typing import List, Dict
from pathlib import Path
import chromadb
from chromadb.config import Settings


class RAGEngine:
    """RAG知识库引擎"""

    def __init__(
        self,
        collection_name: str = "parenting_knowledge",
        persist_directory: str = "./chroma_db"
    ):
        """初始化RAG引擎"""
        self.collection_name = collection_name
        self.persist_directory = persist_directory

        # 初始化ChromaDB客户端
        self.client = chromadb.Client(Settings(
            persist_directory=persist_directory,
            anonymized_telemetry=False
        ))

        # 获取或创建集合
        try:
            self.collection = self.client.get_collection(name=collection_name)
        except:
            self.collection = self.client.create_collection(
                name=collection_name,
                metadata={"description": "育儿知识库"}
            )

    def add_documents(self, documents: List[Dict]):
        """
        添加文档到知识库

        Args:
            documents: 文档列表，每个文档包含 id, text, metadata
        """
        ids = [doc["id"] for doc in documents]
        texts = [doc["text"] for doc in documents]
        metadatas = [doc.get("metadata", {}) for doc in documents]

        self.collection.add(
            ids=ids,
            documents=texts,
            metadatas=metadatas
        )

    def search(self, query: str, top_k: int = 3) -> List[Dict]:
        """
        检索相关文档

        Args:
            query: 查询文本
            top_k: 返回top k个结果

        Returns:
            相关文档列表
        """
        results = self.collection.query(
            query_texts=[query],
            n_results=top_k
        )

        # 格式化结果
        documents = []
        if results['documents'] and len(results['documents']) > 0:
            for i, doc in enumerate(results['documents'][0]):
                documents.append({
                    "text": doc,
                    "metadata": results['metadatas'][0][i] if results['metadatas'] else {},
                    "distance": results['distances'][0][i] if results['distances'] else 0
                })

        return documents

    def get_context(self, query: str, top_k: int = 3) -> str:
        """
        获取查询的上下文文本

        Args:
            query: 查询文本
            top_k: 返回top k个结果

        Returns:
            拼接后的上下文文本
        """
        documents = self.search(query, top_k)

        if not documents:
            return ""

        context_parts = []
        for i, doc in enumerate(documents, 1):
            context_parts.append(f"[参考资料{i}]\n{doc['text']}")

        return "\n\n".join(context_parts)


# 测试代码
if __name__ == "__main__":
    # 初始化引擎
    engine = RAGEngine()

    # 添加示例文档
    sample_docs = [
        {
            "id": "fever_001",
            "text": "婴儿发烧的处理：当宝宝体温超过38.5度时，可以考虑使用退烧药。常用的退烧药有对乙酰氨基酚（泰诺林）和布洛芬（美林）。3个月以下的婴儿发烧必须立即就医。",
            "metadata": {"category": "发烧", "source": "AAP育儿百科"}
        },
        {
            "id": "constipation_001",
            "text": "婴儿便秘的处理：如果宝宝便秘，可以尝试增加水分摄入，对于已添加辅食的宝宝，可以给予西梅泥、梨泥等富含纤维的食物。腹部按摩也有助于促进肠道蠕动。",
            "metadata": {"category": "便秘", "source": "中国儿科指南"}
        }
    ]

    engine.add_documents(sample_docs)

    # 测试检索
    query = "宝宝发烧了怎么办"
    print(f"查询: {query}\n")
    context = engine.get_context(query)
    print(f"检索到的上下文:\n{context}")
