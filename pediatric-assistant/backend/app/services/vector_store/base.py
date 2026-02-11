"""
VectorStore 抽象基类 - 定义向量存储的统一接口

所有向量存储实现（ChromaDB、Milvus、Pinecone等）都应继承此基类。
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

from pydantic import BaseModel, Field


class Document(BaseModel):
    """
    向量文档数据模型

    Attributes:
        id: 文档唯一标识符
        content: 文档文本内容
        metadata: 文档元数据（如来源、分类、标签等）
    """
    id: str = Field(..., description="文档唯一标识符")
    content: str = Field(..., description="文档文本内容")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="文档元数据")


class SearchResult(BaseModel):
    """
    向量检索结果数据模型

    Attributes:
        content: 文档文本内容
        metadata: 文档元数据
        score: 相似度分数（0-1之间，越大越相似）
    """
    content: str = Field(..., description="文档文本内容")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="文档元数据")
    score: float = Field(..., ge=0.0, le=1.0, description="相似度分数")


class VectorStore(ABC):
    """
    向量存储抽象基类

    定义了所有向量存储必须实现的接口。支持：
    - 文档的增删改查
    - 向量相似度搜索
    - 元数据过滤

    所有 IO 操作必须使用 async/await。

    Example:
        >>> store = ChromaStore(collection_name="pediatric_kb")
        >>> await store.add_documents([Document(...)])
        >>> results = await store.search("发烧怎么办", top_k=3)
    """

    @abstractmethod
    async def add_documents(self, documents: List[Document]) -> int:
        """
        批量添加文档到向量存储

        Args:
            documents: 要添加的文档列表

        Returns:
            int: 成功添加的文档数量

        Raises:
            VectorStoreError: 添加文档时发生错误
        """
        pass

    @abstractmethod
    async def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """
        根据查询文本进行相似度搜索

        Args:
            query: 查询文本
            top_k: 返回的最大结果数量，默认为 5
            filters: 元数据过滤条件，如 {"category": "发热", "age_range": "0-36"}

        Returns:
            List[SearchResult]: 搜索结果列表，按相似度降序排列

        Raises:
            VectorStoreError: 搜索时发生错误
        """
        pass

    @abstractmethod
    async def delete_collection(self) -> bool:
        """
        删除整个集合（包括所有文档和索引）

        Returns:
            bool: 删除成功返回 True，失败返回 False

        Warning:
            此操作不可逆，请谨慎使用
        """
        pass

    @abstractmethod
    async def get_document_by_id(self, document_id: str) -> Optional[Document]:
        """
        根据 ID 获取单个文档

        Args:
            document_id: 文档唯一标识符

        Returns:
            Optional[Document]: 找到返回文档对象，未找到返回 None
        """
        pass

    @property
    @abstractmethod
    def count(self) -> int:
        """
        获取集合中的文档数量

        Returns:
            int: 文档数量
        """
        pass
