"""
VectorStore 工厂类 - 统一创建向量存储实例

提供便捷的工厂方法来创建不同类型的向量存储。
"""
from typing import Optional, Any

from loguru import logger

from app.config import settings
from app.services.vector_store.base import VectorStore
from app.services.vector_store.chroma_store import ChromaStore


class VectorStoreFactory:
    """
    向量存储工厂类

    提供静态方法来创建配置好的向量存储实例。

    Example:
        >>> store = VectorStoreFactory.create()
        >>> store = VectorStoreFactory.create_chroma(collection_name="custom")
    """

    @staticmethod
    def create(
        backend: str = "chroma",
        collection_name: Optional[str] = None,
        **kwargs: Any
    ) -> VectorStore:
        """
        创建向量存储实例

        Args:
            backend: 后端类型，目前支持 "chroma"
            collection_name: 集合名称，默认使用配置中的值
            **kwargs: 传递给具体实现的额外参数

        Returns:
            VectorStore: 向量存储实例

        Raises:
            ValueError: 不支持的后端类型
        """
        if backend == "chroma":
            return VectorStoreFactory.create_chroma(
                collection_name=collection_name,
                **kwargs
            )
        else:
            raise ValueError(f"不支持的向量存储后端: {backend}")

    @staticmethod
    def create_chroma(
        collection_name: Optional[str] = None,
        persist_directory: Optional[str] = None,
        embedding_model: Optional[str] = None,
        **kwargs: Any
    ) -> ChromaStore:
        """
        创建 ChromaDB 向量存储实例

        Args:
            collection_name: 集合名称，默认使用配置
            persist_directory: 持久化目录，默认使用配置
            embedding_model: 嵌入模型名称，默认使用配置
            **kwargs: 传递给 ChromaStore 的额外参数

        Returns:
            ChromaStore: ChromaDB 向量存储实例
        """
        # 使用配置中的默认值
        if collection_name is None:
            collection_name = settings.CHROMA_COLLECTION_NAME

        if persist_directory is None:
            persist_directory = settings.CHROMA_PERSIST_DIR or settings.VECTOR_DB_PATH

        if embedding_model is None:
            embedding_model = settings.CHROMA_EMBEDDING_MODEL

        logger.info(
            f"创建 ChromaStore: collection={collection_name}, "
            f"persist_dir={persist_directory}, model={embedding_model}"
        )

        return ChromaStore(
            collection_name=collection_name,
            persist_directory=persist_directory,
            embedding_model_name=embedding_model,
            **kwargs
        )


# 便捷导出
__all__ = ["VectorStoreFactory"]
