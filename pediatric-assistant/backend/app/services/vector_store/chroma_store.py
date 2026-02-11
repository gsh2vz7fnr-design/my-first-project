"""
ChromaStore - 基于 ChromaDB 的向量存储实现

使用 ChromaDB 作为后端，支持本地持久化和高效的向量检索。
默认使用 sentence-transformers 作为嵌入模型。
"""
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional

from loguru import logger

from app.services.vector_store.base import (
    VectorStore,
    Document,
    SearchResult
)


class VectorStoreError(Exception):
    """向量存储操作异常"""
    pass


class ChromaStore(VectorStore):
    """
    基于 ChromaDB 的向量存储实现

    Features:
        - 本地持久化存储
        - 自动嵌入生成（使用 sentence-transformers）
        - 元数据过滤搜索
        - 批量操作支持

    Example:
        >>> store = ChromaStore(
        ...     collection_name="pediatric_kb",
        ...     persist_directory="./data/vector_db"
        ... )
        >>> await store.add_documents([
        ...     Document(id="1", content="发烧的护理方法", metadata={"category": "发热"})
        ... ])
        >>> results = await store.search("宝宝发烧怎么办", top_k=3)
    """

    def __init__(
        self,
        collection_name: str = "default",
        persist_directory: Optional[str] = None,
        embedding_model_name: str = "BAAI/bge-small-zh-v1.5",
        **kwargs: Any
    ) -> None:
        """
        初始化 ChromaStore

        Args:
            collection_name: ChromaDB 集合名称
            persist_directory: 数据持久化目录，None 表示使用内存模式
            embedding_model_name: 嵌入模型名称（HuggingFace 模型）
            **kwargs: 其他 ChromaDB 配置参数
        """
        self._collection_name = collection_name
        self._persist_directory = persist_directory
        self._embedding_model_name = embedding_model_name
        self._kwargs = kwargs

        # 延迟初始化的组件
        self._client: Optional[Any] = None
        self._collection: Optional[Any] = None
        self._embedding_function: Optional[Any] = None
        self._initialized = False
        self._doc_count: int = 0

    async def _ensure_initialized(self) -> None:
        """
        确保存储已初始化（延迟初始化模式）

        Raises:
            VectorStoreError: 初始化失败
        """
        if self._initialized:
            return

        try:
            # 在线程池中执行同步初始化
            await asyncio.get_event_loop().run_in_executor(
                None,
                self._init_sync
            )
            self._initialized = True
            logger.info(
                f"ChromaStore 初始化完成: collection={self._collection_name}, "
                f"persist_dir={self._persist_directory}"
            )
        except Exception as e:
            logger.error(f"ChromaStore 初始化失败: {e}", exc_info=True)
            raise VectorStoreError(f"初始化失败: {e}") from e

    def _init_sync(self) -> None:
        """
        同步初始化逻辑（在独立线程中执行）
        """
        import chromadb
        from chromadb.config import Settings

        # 配置 ChromaDB 客户端
        if self._persist_directory:
            # 确保持久化目录存在
            Path(self._persist_directory).mkdir(parents=True, exist_ok=True)

            self._client = chromadb.PersistentClient(
                path=self._persist_directory,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
        else:
            # 内存模式
            self._client = chromadb.EphemeralClient(
                settings=Settings(
                    anonymized_telemetry=False
                )
            )

        # 初始化嵌入函数
        self._embedding_function = self._create_embedding_function()

        # 获取或创建集合
        self._collection = self._client.get_or_create_collection(
            name=self._collection_name,
            embedding_function=self._embedding_function,
            metadata={"hnsw:space": "cosine"}  # 使用余弦相似度
        )

        # 更新文档计数
        self._doc_count = self._collection.count()

    def _create_embedding_function(self) -> Any:
        """
        创建嵌入函数

        Returns:
            嵌入函数实例

        Note:
            优先使用 sentence-transformers，如果不可用则使用 ChromaDB 默认
        """
        try:
            from chromadb.utils import embedding_functions

            # 使用 Sentence Transformers
            embedding_func = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=self._embedding_model_name,
                device="cpu"  # 服务器环境通常使用 CPU
            )
            logger.info(f"使用嵌入模型: {self._embedding_model_name}")
            return embedding_func

        except ImportError:
            logger.warning(
                "sentence-transformers 未安装，使用 ChromaDB 默认嵌入函数"
            )
            # 使用默认嵌入函数
            from chromadb.utils import embedding_functions
            return embedding_functions.DefaultEmbeddingFunction()

    @property
    def collection_name(self) -> str:
        """获取集合名称"""
        return self._collection_name

    @property
    def count(self) -> int:
        """
        获取集合中的文档数量

        Returns:
            int: 文档数量
        """
        return self._doc_count

    async def add_documents(self, documents: List[Document]) -> int:
        """
        批量添加文档到向量存储

        Args:
            documents: 要添加的文档列表

        Returns:
            int: 成功添加的文档数量

        Raises:
            VectorStoreError: 添加失败
        """
        if not documents:
            return 0

        await self._ensure_initialized()

        try:
            # 准备数据
            ids = [doc.id for doc in documents]
            contents = [doc.content for doc in documents]
            metadatas = [doc.metadata or {} for doc in documents]

            # 在线程池中执行同步添加操作
            def _add_sync() -> None:
                self._collection.add(
                    ids=ids,
                    documents=contents,
                    metadatas=metadatas
                )

            await asyncio.get_event_loop().run_in_executor(None, _add_sync)

            # 更新文档计数
            self._doc_count = self._collection.count()

            logger.info(f"成功添加 {len(documents)} 个文档到集合 {self._collection_name}")
            return len(documents)

        except Exception as e:
            logger.error(f"添加文档失败: {e}", exc_info=True)
            raise VectorStoreError(f"添加文档失败: {e}") from e

    async def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """
        文本相似度搜索

        Args:
            query: 查询文本
            top_k: 返回结果数量
            filters: 元数据过滤条件

        Returns:
            List[SearchResult]: 搜索结果列表

        Raises:
            VectorStoreError: 搜索失败
        """
        await self._ensure_initialized()

        try:
            # 构建 where 过滤条件
            where = self._build_where_clause(filters) if filters else None

            def _query_sync() -> Any:
                return self._collection.query(
                    query_texts=[query],
                    n_results=top_k,
                    where=where,
                    include=["documents", "metadatas", "distances"]
                )

            result = await asyncio.get_event_loop().run_in_executor(
                None, _query_sync
            )

            # 解析结果
            return self._parse_query_result(result)

        except Exception as e:
            logger.error(f"搜索失败: {e}", exc_info=True)
            raise VectorStoreError(f"搜索失败: {e}") from e

    async def delete_collection(self) -> bool:
        """
        删除整个集合

        Returns:
            bool: 成功返回 True
        """
        await self._ensure_initialized()

        try:
            def _delete_sync() -> None:
                self._client.delete_collection(self._collection_name)

            await asyncio.get_event_loop().run_in_executor(None, _delete_sync)

            # 重置状态
            self._collection = None
            self._doc_count = 0
            self._initialized = False

            logger.warning(f"集合 {self._collection_name} 已删除")
            return True

        except Exception as e:
            logger.error(f"删除集合失败: {e}", exc_info=True)
            return False

    async def get_document_by_id(self, document_id: str) -> Optional[Document]:
        """
        根据 ID 获取文档

        Args:
            document_id: 文档 ID

        Returns:
            Optional[Document]: 文档对象或 None
        """
        await self._ensure_initialized()

        try:
            def _get_sync() -> Any:
                return self._collection.get(
                    ids=[document_id],
                    include=["documents", "metadatas"]
                )

            result = await asyncio.get_event_loop().run_in_executor(
                None, _get_sync
            )

            ids = result.get("ids", [])
            documents = result.get("documents", [])
            metadatas = result.get("metadatas", [])

            if not ids:
                return None

            return Document(
                id=ids[0],
                content=documents[0] if documents else "",
                metadata=metadatas[0] if metadatas else {}
            )

        except Exception as e:
            logger.error(f"获取文档失败: {e}", exc_info=True)
            return None

    def _build_where_clause(
        self,
        filters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        构建 ChromaDB where 子句

        Args:
            filters: 过滤条件字典

        Returns:
            Dict[str, Any]: ChromaDB where 子句

        Example:
            {"category": "发热", "age_range": "0-36"}
            -> {"$and": [{"category": "发热"}, {"age_range": "0-36"}]}
        """
        if not filters:
            return {}

        conditions = []
        for key, value in filters.items():
            if isinstance(value, list):
                # 多值匹配：使用 $in 操作符
                conditions.append({key: {"$in": value}})
            elif isinstance(value, dict):
                # 已经是操作符格式，直接使用
                conditions.append({key: value})
            else:
                # 精确匹配
                conditions.append({key: value})

        if len(conditions) == 1:
            return conditions[0]
        elif len(conditions) > 1:
            return {"$and": conditions}

        return {}

    def _parse_query_result(
        self,
        result: Any
    ) -> List[SearchResult]:
        """
        解析 ChromaDB 查询结果

        Args:
            result: ChromaDB 查询返回结果

        Returns:
            List[SearchResult]: 标准化的搜索结果列表
        """
        search_results = []

        # ChromaDB 返回的结果是按查询分组的
        # 例如 query_texts=["a", "b"] 会返回 [[a的results], [b的results]]
        # 这里我们只处理第一个查询（单查询场景）
        ids = result.get("ids", [[]])[0] if result.get("ids") else []
        documents = result.get("documents", [[]])[0] if result.get("documents") else []
        metadatas = result.get("metadatas", [[]])[0] if result.get("metadatas") else []
        distances = result.get("distances", [[]])[0] if result.get("distances") else []

        for i, doc_id in enumerate(ids):
            # 将距离转换为相似度分数（余弦距离 -> 相似度）
            # ChromaDB 使用 cosine 空间时，distance = 1 - similarity
            distance = distances[i] if i < len(distances) else 1.0
            score = max(0.0, min(1.0, 1.0 - distance))

            content = documents[i] if i < len(documents) else ""
            metadata = metadatas[i] if i < len(metadatas) else {}

            # 将 id 添加到 metadata 中
            metadata["id"] = doc_id

            search_results.append(SearchResult(
                content=content,
                metadata=metadata,
                score=score
            ))

        return search_results
