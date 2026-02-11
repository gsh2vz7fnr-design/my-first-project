"""
VectorStore 模块 - 向量存储抽象层

提供统一的向量存储接口，支持多种后端实现：
- ChromaStore: 基于 ChromaDB 的本地向量存储
- (未来可扩展) MilvusStore, PineconeStore 等

Example:
    >>> from app.services.vector_store import VectorStoreFactory
    >>> store = VectorStoreFactory.create_chroma()
    >>> results = await store.search("发烧怎么办", top_k=3)
"""
from app.services.vector_store.base import (
    VectorStore,
    Document,
    SearchResult
)
from app.services.vector_store.chroma_store import (
    ChromaStore,
    VectorStoreError
)
from app.services.vector_store.factory import VectorStoreFactory
from app.services.vector_store.embedding import (
    EmbeddingService,
    EmbeddingResult,
    SiliconFlowEmbedding,
    LocalEmbedding,
    HybridEmbeddingService
)

__all__ = [
    # 基类和数据模型
    "VectorStore",
    "Document",
    "SearchResult",
    # 实现
    "ChromaStore",
    "VectorStoreError",
    # 工厂
    "VectorStoreFactory",
    # Embedding 服务
    "EmbeddingService",
    "EmbeddingResult",
    "SiliconFlowEmbedding",
    "LocalEmbedding",
    "HybridEmbeddingService",
]
