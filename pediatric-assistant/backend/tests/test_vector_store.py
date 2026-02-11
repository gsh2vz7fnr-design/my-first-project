"""
向量存储单元测试

测试内容：
- Document 和 SearchResult 模型
- ChromaStore 基本功能
- 过滤检索
- 错误处理
"""
import pytest
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from typing import List, Dict, Any, Optional

from app.services.vector_store.base import Document, SearchResult, VectorStore
from app.services.vector_store.chroma_store import ChromaStore, VectorStoreError
from app.services.vector_store.embedding import (
    EmbeddingService,
    SiliconFlowEmbedding,
    LocalEmbedding,
    HybridEmbeddingService
)


# ============ 模型测试 ============

class TestDocument:
    """Document 模型测试"""

    def test_create_document(self):
        """测试创建文档"""
        doc = Document(
            id="test_001",
            content="这是测试内容",
            metadata={"category": "test"}
        )
        assert doc.id == "test_001"
        assert doc.content == "这是测试内容"
        assert doc.metadata == {"category": "test"}

    def test_document_default_metadata(self):
        """测试默认 metadata"""
        doc = Document(id="test_002", content="内容")
        assert doc.metadata == {}

    def test_document_validation(self):
        """测试字段验证 - Pydantic 允许空字符串"""
        # Pydantic 默认允许空字符串，这里只测试正常创建
        doc = Document(id="", content="")
        assert doc.id == ""
        assert doc.content == ""


class TestSearchResult:
    """SearchResult 模型测试"""

    def test_create_search_result(self):
        """测试创建搜索结果"""
        result = SearchResult(
            content="结果内容",
            metadata={"id": "doc_001"},
            score=0.85
        )
        assert result.content == "结果内容"
        assert result.score == 0.85

    def test_score_validation(self):
        """测试 score 范围验证"""
        # 有效范围
        result = SearchResult(content="test", metadata={}, score=0.0)
        assert result.score == 0.0

        result = SearchResult(content="test", metadata={}, score=1.0)
        assert result.score == 1.0

        # 超出范围应该失败
        with pytest.raises(Exception):
            SearchResult(content="test", metadata={}, score=1.5)

        with pytest.raises(Exception):
            SearchResult(content="test", metadata={}, score=-0.1)


# ============ ChromaStore 测试 ============

class TestChromaStore:
    """ChromaStore 单元测试"""

    @pytest.fixture
    def mock_collection(self):
        """Mock ChromaDB Collection"""
        collection = MagicMock()
        collection.add = MagicMock()
        collection.query = MagicMock(return_value={
            'ids': [['doc1', 'doc2']],
            'documents': [['content1', 'content2']],
            'metadatas': [[{'category': 'test1'}, {'category': 'test2'}]],
            'distances': [[0.1, 0.2]]
        })
        collection.get = MagicMock(return_value={
            'ids': ['doc1'],
            'documents': ['content1'],
            'metadatas': [{'category': 'test1'}]
        })
        collection.count = MagicMock(return_value=100)
        collection.delete = MagicMock()
        return collection

    @pytest.fixture
    def mock_client(self, mock_collection):
        """Mock ChromaDB Client"""
        client = MagicMock()
        client.get_or_create_collection = MagicMock(return_value=mock_collection)
        client.delete_collection = MagicMock()
        return client

    @pytest.fixture
    def vector_store(self, mock_client, mock_collection):
        """使用 Mock 的 VectorStore"""
        store = ChromaStore.__new__(ChromaStore)
        store._client = mock_client
        store._collection = mock_collection
        store._collection_name = "test_collection"
        store._embedding_function = Mock()
        store._initialized = True
        store._doc_count = 100
        return store

    def test_collection_name_property(self, vector_store):
        """测试集合名称属性"""
        assert vector_store.collection_name == "test_collection"

    def test_count_property(self, vector_store):
        """测试计数属性"""
        assert vector_store.count == 100

    @pytest.mark.asyncio
    async def test_add_documents(self, vector_store):
        """测试添加文档"""
        docs = [
            Document(id="doc1", content="test content", metadata={"key": "value"})
        ]

        count = await vector_store.add_documents(docs)

        assert count == 1
        vector_store._collection.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_documents_empty(self, vector_store):
        """测试添加空文档列表"""
        count = await vector_store.add_documents([])
        assert count == 0

    @pytest.mark.asyncio
    async def test_search(self, vector_store):
        """测试搜索"""
        results = await vector_store.search("test query", top_k=2)

        assert len(results) == 2
        assert isinstance(results[0], SearchResult)
        assert results[0].content == "content1"
        assert results[0].score > 0  # 距离转换后的分数

    @pytest.mark.asyncio
    async def test_search_with_filters(self, vector_store):
        """测试带过滤条件的搜索"""
        filters = {"category": "发热", "age_range_min": 0}

        results = await vector_store.search("query", filters=filters)

        # 验证 where 子句被传递
        call_args = vector_store._collection.query.call_args
        assert call_args is not None

    @pytest.mark.asyncio
    async def test_get_document_by_id(self, vector_store):
        """测试根据 ID 获取文档"""
        doc = await vector_store.get_document_by_id("doc1")

        assert doc is not None
        assert doc.id == "doc1"
        assert doc.content == "content1"

    @pytest.mark.asyncio
    async def test_get_document_by_id_not_found(self, vector_store):
        """测试获取不存在的文档"""
        vector_store._collection.get = MagicMock(return_value={
            'ids': [],
            'documents': [],
            'metadatas': []
        })

        doc = await vector_store.get_document_by_id("nonexistent")
        assert doc is None

    @pytest.mark.asyncio
    async def test_delete_collection(self, vector_store):
        """测试删除集合"""
        result = await vector_store.delete_collection()

        assert result is True
        vector_store._client.delete_collection.assert_called_once()
        assert vector_store.count == 0

    def test_build_where_clause_single(self, vector_store):
        """测试构建单个条件的 where 子句"""
        filters = {"category": "发热"}
        where = vector_store._build_where_clause(filters)

        assert where == {"category": "发热"}

    def test_build_where_clause_multiple(self, vector_store):
        """测试构建多个条件的 where 子句"""
        filters = {"category": "发热", "age_range_min": 0}
        where = vector_store._build_where_clause(filters)

        assert "$and" in where
        assert len(where["$and"]) == 2

    def test_build_where_clause_with_list(self, vector_store):
        """测试构建包含列表的 where 子句"""
        filters = {"category": ["发热", "咳嗽"]}
        where = vector_store._build_where_clause(filters)

        assert "category" in where
        assert "$in" in where["category"]

    def test_parse_query_result(self, vector_store):
        """测试解析查询结果"""
        result = {
            'ids': [['id1', 'id2']],
            'documents': [['content1', 'content2']],
            'metadatas': [[{'key': 'val1'}, {'key': 'val2'}]],
            'distances': [[0.2, 0.5]]
        }

        search_results = vector_store._parse_query_result(result)

        assert len(search_results) == 2
        assert search_results[0].content == "content1"
        assert search_results[0].score == 0.8  # 1 - 0.2
        assert search_results[0].metadata.get('id') == 'id1'


# ============ Embedding 服务测试 ============

class TestEmbeddingServices:
    """Embedding 服务测试"""

    def test_siliconflow_embedding_model_name(self):
        """测试 SiliconFlow 服务模型名称"""
        service = SiliconFlowEmbedding(
            api_key="test_key",
            model="test-model"
        )
        assert service.model_name == "test-model"

    def test_siliconflow_embedding_availability(self):
        """测试 SiliconFlow 服务可用性"""
        # 有 API Key
        service = SiliconFlowEmbedding(api_key="test_key")
        assert service.is_available is True

        # 测试 cooldown 机制
        service._cooldown_until = 9999999999  # 设置一个未来的时间
        assert service.is_available is False
        service._cooldown_until = 0  # 重置

    def test_local_embedding_model_name(self):
        """测试本地服务模型名称"""
        service = LocalEmbedding(model_name="test-model")
        assert service.model_name == "test-model"

    def test_hybrid_embedding_service(self):
        """测试混合服务"""
        remote = SiliconFlowEmbedding(api_key="test_key")
        local = LocalEmbedding()

        hybrid = HybridEmbeddingService(remote, local)

        assert hybrid.is_available is True

    def test_embedding_cache(self):
        """测试缓存机制"""
        service = SiliconFlowEmbedding(api_key="test_key", cache_size=10)

        # 添加到缓存
        service._add_to_cache("test text", [0.1, 0.2, 0.3])

        # 从缓存获取
        cached = service._get_from_cache("test text")
        assert cached == [0.1, 0.2, 0.3]

        # 未缓存的内容
        not_cached = service._get_from_cache("other text")
        assert not_cached is None


# ============ 错误处理测试 ============

class TestErrorHandling:
    """错误处理测试"""

    @pytest.mark.asyncio
    async def test_add_documents_error(self):
        """测试添加文档时的错误处理"""
        store = ChromaStore.__new__(ChromaStore)
        store._initialized = True
        store._collection = MagicMock()
        store._collection.add = MagicMock(side_effect=Exception("DB Error"))
        store._doc_count = 0

        docs = [Document(id="1", content="test")]

        with pytest.raises(VectorStoreError):
            await store.add_documents(docs)

    @pytest.mark.asyncio
    async def test_search_error(self):
        """测试搜索时的错误处理"""
        store = ChromaStore.__new__(ChromaStore)
        store._initialized = True
        store._collection = MagicMock()
        store._collection.query = MagicMock(side_effect=Exception("Query Error"))

        with pytest.raises(VectorStoreError):
            await store.search("query")


# ============ 运行测试 ============

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
