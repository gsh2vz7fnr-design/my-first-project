"""
RAG服务 - 知识库检索与内容溯源（重构版）

支持两种模式：
- ChromaDB 模式：使用向量数据库进行语义检索
- 本地模式：使用内存中的关键词检索（降级方案）
"""
import json
import os
import re
import time
from collections import Counter
from typing import List, Dict, Any, Optional, Protocol, runtime_checkable
from loguru import logger
from openai import OpenAI

from app.config import settings
from app.models.user import KnowledgeSource, RAGResult
from app.services.vector_store import (
    VectorStore,
    ChromaStore,
    SearchResult,
    HybridEmbeddingService,
    SiliconFlowEmbedding,
    LocalEmbedding
)


@runtime_checkable
class EmbeddingServiceProtocol(Protocol):
    """Embedding 服务协议"""

    @property
    def is_available(self) -> bool:
        ...

    async def embed(self, text: str) -> Optional[List[float]]:
        ...


class RAGService:
    """
    RAG检索服务（重构版）

    Features:
        - 依赖注入 VectorStore 和 EmbeddingService
        - ChromaDB 向量检索 + 本地降级
        - 混合检索策略
        - 重排序优化

    Example:
        >>> vector_store = ChromaStore()
        >>> embedding_service = HybridEmbeddingService()
        >>> rag_service = RAGService(vector_store, embedding_service)
        >>> results = await rag_service.retrieve("宝宝发烧怎么办")
    """

    def __init__(
        self,
        vector_store: Optional[VectorStore] = None,
        embedding_service: Optional[EmbeddingServiceProtocol] = None,
        use_chromadb: Optional[bool] = None
    ):
        """
        初始化 RAG 服务

        Args:
            vector_store: 向量存储实例（可选，默认自动创建）
            embedding_service: Embedding 服务实例（可选）
            use_chromadb: 是否使用 ChromaDB（可选，默认使用配置）
        """
        # 确定是否使用 ChromaDB
        self._use_chromadb = use_chromadb if use_chromadb is not None else settings.USE_CHROMADB

        # LLM 客户端
        self.client = OpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL
        )
        self.chat_model = settings.DEEPSEEK_MODEL

        # 向量存储
        self._vector_store = vector_store

        # Embedding 服务
        self._embedding_service = embedding_service

        # 本地降级：始终加载 JSON 知识库作为 fallback
        # 当 ChromaDB 不可用时自动使用本地检索
        self.knowledge_base = self._load_knowledge_base()
        self._doc_token_counts: List[Counter] = []

        # 状态控制
        self._api_key_configured = bool(settings.DEEPSEEK_API_KEY)
        self._remote_cooldown_until: float = 0.0
        self._chromadb_available: Optional[bool] = None

        # 构建本地索引（用于降级）
        if self.knowledge_base:
            self._build_local_index()

        logger.info(
            f"RAGService 初始化完成: use_chromadb={self._use_chromadb}, "
            f"kb_size={len(self.knowledge_base)}"
        )

    @property
    def vector_store(self) -> VectorStore:
        """获取向量存储实例（延迟初始化）"""
        if self._vector_store is None:
            from app.services.vector_store import VectorStoreFactory
            self._vector_store = VectorStoreFactory.create_chroma()
        return self._vector_store

    @property
    def embedding_service(self) -> EmbeddingServiceProtocol:
        """获取 Embedding 服务实例（延迟初始化）"""
        if self._embedding_service is None:
            remote = SiliconFlowEmbedding()
            local = LocalEmbedding()
            self._embedding_service = HybridEmbeddingService(remote, local)
        return self._embedding_service

    @property
    def remote_available(self) -> bool:
        """检查远程 LLM 是否可用"""
        if not self._api_key_configured:
            return False
        return time.time() >= self._remote_cooldown_until

    @remote_available.setter
    def remote_available(self, value: bool):
        """设置远程可用状态"""
        if not value:
            self._remote_cooldown_until = time.time() + 60
        else:
            self._remote_cooldown_until = 0.0

    async def _check_chromadb_available(self) -> bool:
        """
        检查 ChromaDB 是否可用

        Returns:
            bool: 可用返回 True
        """
        if self._chromadb_available is not None:
            return self._chromadb_available

        if not self._use_chromadb:
            self._chromadb_available = False
            return False

        try:
            store = self.vector_store
            if hasattr(store, '_ensure_initialized'):
                await store._ensure_initialized()

            count = store.count
            self._chromadb_available = count > 0

            if self._chromadb_available:
                logger.info(f"ChromaDB 可用，文档数: {count}")
            else:
                logger.warning("ChromaDB 集合为空，将使用本地检索")

            return self._chromadb_available

        except Exception as e:
            logger.error(f"ChromaDB 不可用: {e}", exc_info=True)
            self._chromadb_available = False
            return False

    def _load_knowledge_base(self) -> List[Dict[str, Any]]:
        """加载本地 JSON 知识库（用于降级）"""
        knowledge_base = []
        kb_path = settings.KNOWLEDGE_BASE_PATH

        try:
            if not os.path.exists(kb_path):
                logger.warning(f"知识库路径不存在: {kb_path}")
                return []

            for filename in os.listdir(kb_path):
                if filename.endswith('.json'):
                    filepath = os.path.join(kb_path, filename)
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        for entry in data.get('entries', []):
                            entry['topic'] = data.get('topic')
                            entry['category'] = data.get('category')
                            knowledge_base.append(entry)

            logger.info(f"加载本地知识库完成，共 {len(knowledge_base)} 条记录")
            return knowledge_base

        except Exception as e:
            logger.error(f"加载知识库失败: {e}", exc_info=True)
            return []

    async def retrieve(
        self,
        query: str,
        top_k: int = 3,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[KnowledgeSource]:
        """
        检索相关知识

        Args:
            query: 查询文本
            top_k: 返回的文档数
            filters: 过滤条件（如age_months, category等）

        Returns:
            List[KnowledgeSource]: 检索结果
        """
        start_time = time.time()
        results = []

        try:
            # 检查是否使用 ChromaDB
            if await self._check_chromadb_available():
                # ChromaDB 向量检索
                results = await self._retrieve_from_chromadb(query, top_k, filters)
                retrieval_method = "chromadb"
            else:
                # 降级到本地检索
                results = await self._retrieve_local(query, top_k, filters)
                retrieval_method = "local"

            elapsed = (time.time() - start_time) * 1000
            logger.info(
                f"检索完成: method={retrieval_method}, "
                f"results={len(results)}, elapsed={elapsed:.1f}ms"
            )

            return results

        except Exception as e:
            logger.error(f"检索失败: {e}", exc_info=True)
            # 尝试降级到本地检索
            if self.knowledge_base:
                logger.info("尝试降级到本地检索...")
                return await self._retrieve_local(query, top_k, filters)
            return []

    async def _retrieve_from_chromadb(
        self,
        query: str,
        top_k: int = 3,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[KnowledgeSource]:
        """
        使用 ChromaDB 进行向量检索

        Args:
            query: 查询文本
            top_k: 返回结果数
            filters: 过滤条件

        Returns:
            List[KnowledgeSource]: 检索结果
        """
        # 1. 初次召回（从 ChromaDB 获取更多候选）
        recall_k = min(settings.CHROMADB_SEARCH_TOP_K, 50)
        search_results = await self.vector_store.search(
            query=query,
            top_k=recall_k,
            filters=filters
        )

        if not search_results:
            return []

        # 2. 转换为候选列表
        candidates = []
        for result in search_results:
            candidates.append({
                "entry": {
                    "id": result.metadata.get("id", ""),
                    "content": result.content,
                    "title": result.metadata.get("title", ""),
                    "source": result.metadata.get("source", ""),
                    "topic": result.metadata.get("topic", ""),
                    "category": result.metadata.get("category", ""),
                    "tags": result.metadata.get("tags", "").split(",") if result.metadata.get("tags") else [],
                    "age_range": result.metadata.get("age_range", ""),
                    "alert_level": result.metadata.get("alert_level", ""),
                },
                "vector_score": result.score,
                "keyword_score": 0.0,
                "score": result.score
            })

        # 3. 重排序
        results = await self._rerank(query, candidates, top_k=top_k)

        return results

    async def _retrieve_local(
        self,
        query: str,
        top_k: int = 3,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[KnowledgeSource]:
        """
        本地关键词检索（降级方案）

        Args:
            query: 查询文本
            top_k: 返回结果数
            filters: 过滤条件

        Returns:
            List[KnowledgeSource]: 检索结果
        """
        if not self.knowledge_base:
            return []

        query_counter = self._text_to_counter(query)
        candidates = []

        # 同义词映射
        synonym_mapping = {
            "拉肚子": "腹泻", "拉稀": "腹泻",
            "发烧": "发热", "高烧": "发热",
            "吐": "呕吐", "吐奶": "呕吐",
            "咳": "咳嗽",
            "起疹子": "皮疹", "湿疹": "皮疹",
            "摔伤": "摔倒", "跌倒": "摔倒", "跌落": "摔倒",
            "便秘": "大便困难"
        }

        expanded_query_tokens = set(query_counter.keys())
        for token in list(query_counter.keys()):
            if token in synonym_mapping:
                expanded_query_tokens.add(synonym_mapping[token])

        for idx, entry in enumerate(self.knowledge_base):
            if filters and not self._match_filters(entry, filters):
                continue

            similarity = self._cosine_similarity_counts(
                query_counter, self._doc_token_counts[idx]
            )

            title = entry.get("title", "")
            tags = entry.get("tags", [])

            # 标题匹配加权
            if title and title in query:
                similarity = max(similarity, 0.8)

            # 同义词标题匹配
            for query_token in expanded_query_tokens:
                if len(query_token) > 1 and query_token in title:
                    similarity = max(similarity, 0.7)
                    break

            # 标签匹配
            if tags and any(tag in query for tag in tags):
                similarity = max(similarity, 0.6)

            candidates.append({
                "entry": entry,
                "score": float(similarity),
                "vector_score": 0.0,
                "keyword_score": float(similarity)
            })

        # 排序
        candidates.sort(key=lambda x: x["score"], reverse=True)
        top_candidates = candidates[:top_k * 2]  # 多取一些用于重排序

        # 重排序
        results = await self._rerank(query, top_candidates, top_k=top_k)

        return results

    async def _rerank(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        top_k: int = 3
    ) -> List[KnowledgeSource]:
        """
        重排序候选结果

        Args:
            query: 查询文本
            candidates: 候选列表
            top_k: 返回数量

        Returns:
            List[KnowledgeSource]: 重排序后的结果
        """
        reranked = []

        for item in candidates:
            entry = item.get("entry", {})
            base_score = item.get("score", 0.0)
            rerank_score = base_score

            content = entry.get("content", "")
            title = entry.get("title", "")

            # 规则1: 精确短语匹配
            if query in content:
                rerank_score += 0.2

            # 规则2: 关键医学实体匹配
            entity_rules = [
                (["泰诺林"], "泰诺林"),
                (["美林"], "美林"),
                (["拉肚子", "拉稀", "腹泻"], "腹泻"),
                (["发烧", "发热", "高烧"], ["发烧", "发热"]),
                (["咳嗽", "咳"], "咳嗽"),
                (["呕吐", "吐", "吐奶"], "呕吐"),
                (["皮疹", "疹子", "湿疹"], "皮疹"),
            ]

            for query_keywords, title_keywords in entity_rules:
                query_match = any(kw in query for kw in query_keywords)
                if isinstance(title_keywords, list):
                    title_match = any(kw in title for kw in title_keywords)
                else:
                    title_match = title_keywords in title

                if query_match and title_match:
                    rerank_score += 0.2
                    break

            # 阈值过滤
            threshold = settings.SIMILARITY_THRESHOLD
            if rerank_score < threshold:
                # 本地模式放宽阈值
                if not self._use_chromadb and rerank_score >= 0.1:
                    pass  # 允许通过
                else:
                    continue

            reranked.append(KnowledgeSource(
                content=content,
                source=entry.get('source', '未知来源'),
                score=rerank_score,
                metadata={
                    'id': entry.get('id'),
                    'title': title,
                    'topic': entry.get('topic'),
                    'category': entry.get('category'),
                    'tags': entry.get('tags', []),
                    'age_range': entry.get('age_range'),
                    'alert_level': entry.get('alert_level'),
                    'retrieval_info': {
                        'vector_score': item.get('vector_score', 0),
                        'keyword_score': item.get('keyword_score', 0),
                        'rerank_score': rerank_score
                    }
                }
            ))

        # 排序并返回 top_k
        reranked.sort(key=lambda x: x.score, reverse=True)
        return reranked[:top_k]

    def _match_filters(self, entry: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        """检查 entry 是否匹配过滤条件"""
        for key, value in filters.items():
            if key == 'age_months':
                age_range = entry.get('age_range', '')
                if not self._in_age_range(value, age_range):
                    return False
            elif key in entry:
                if entry[key] != value:
                    return False
        return True

    def _in_age_range(self, age_months: int, age_range_str: str) -> bool:
        """检查年龄是否在范围内"""
        if not age_range_str:
            return True

        try:
            if '-' in age_range_str and '个月' in age_range_str:
                parts = age_range_str.replace('个月', '').split('-')
                min_age = int(parts[0])
                max_age = int(parts[1])
                return min_age <= age_months <= max_age
        except (ValueError, IndexError):
            pass

        return True

    def _build_local_index(self) -> None:
        """构建本地检索索引"""
        self._doc_token_counts = []
        for entry in self.knowledge_base:
            doc_text = f"{entry.get('title', '')} {entry.get('content', '')}"
            self._doc_token_counts.append(self._text_to_counter(doc_text))

    def _text_to_counter(self, text: str) -> Counter:
        """将文本转换为词频计数器"""
        text_lower = text.lower()

        medical_terms = [
            "拉肚子", "腹泻", "发烧", "发热", "咳嗽", "呕吐", "皮疹", "湿疹",
            "惊厥", "抽搐", "呼吸困难", "昏迷", "便秘", "摔倒", "跌落", "摔伤",
            "脱水", "补液", "嗜睡", "精神萎靡",
            "宝宝", "婴儿", "幼儿", "儿童",
            "小时", "分钟", "天", "周", "月", "年"
        ]

        tokens = []
        remaining = text_lower

        for term in sorted(medical_terms, key=len, reverse=True):
            while term in remaining:
                tokens.append(term)
                remaining = remaining.replace(term, " ", 1)

        for char in remaining:
            if re.match(r"[a-zA-Z0-9]", char):
                tokens.append(char)
            elif re.match(r"[\u4e00-\u9fff]", char):
                tokens.append(char)

        return Counter(tokens)

    def _cosine_similarity_counts(self, c1: Counter, c2: Counter) -> float:
        """计算两个 Counter 的余弦相似度"""
        if not c1 or not c2:
            return 0.0
        common = set(c1.keys()) & set(c2.keys())
        dot = sum(c1[token] * c2[token] for token in common)
        norm1 = sum(v * v for v in c1.values()) ** 0.5
        norm2 = sum(v * v for v in c2.values()) ** 0.5
        if norm1 == 0.0 or norm2 == 0.0:
            return 0.0
        return dot / (norm1 * norm2)

    async def generate_answer_with_sources(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None
    ) -> RAGResult:
        """
        基于检索结果生成答案

        Args:
            query: 用户问题
            context: 上下文（用户档案等）

        Returns:
            RAGResult: 答案和来源
        """
        # 1. 检索相关知识
        filters = {}
        if context and context.get('baby_info', {}).get('age_months'):
            filters['age_months'] = context['baby_info']['age_months']

        sources = await self.retrieve(query, top_k=settings.TOP_K_RETRIEVAL, filters=filters)

        # 2. 如果没有检索到相关知识，返回拒答
        if not sources:
            return RAGResult(
                answer="抱歉，我的权威知识库中暂无关于此问题的记录。建议您咨询专业医生。",
                sources=[],
                has_source=False
            )

        # 3. 构建 prompt
        prompt = self._build_rag_prompt(query, sources, context)

        # 4. 生成答案
        try:
            if not self.remote_available:
                answer = self._build_fallback_answer(sources)
                return RAGResult(
                    answer=self.format_with_citations(answer, sources),
                    sources=sources,
                    has_source=True
                )

            response = self.client.chat.completions.create(
                model=self.chat_model,
                messages=[
                    {"role": "system", "content": self._get_rag_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
            )

            answer = response.choices[0].message.content

            return RAGResult(
                answer=self.format_with_citations(answer, sources),
                sources=sources,
                has_source=True
            )

        except Exception as e:
            logger.error(f"生成答案异常: {e}", exc_info=True)
            self.remote_available = False
            answer = self._build_fallback_answer(sources)
            return RAGResult(
                answer=self.format_with_citations(answer, sources),
                sources=sources,
                has_source=True
            )

    def _build_fallback_answer(self, sources: List[KnowledgeSource]) -> str:
        """构建兜底回答"""
        top = sources[0]
        entry_id = top.metadata.get("id", "unknown")
        title = top.metadata.get("title", "参考建议")
        content = top.content

        return (
            f"**核心结论**：{title}\n\n"
            f"**操作建议**：\n{content}\n\n"
            "**注意事项**：\n"
            "- 请结合宝宝实际情况观察变化\n"
            "- 如有疑问请咨询专业医生\n\n"
            "**⚠️ 立即就医信号**：\n"
            "如果出现以下情况，请立刻前往医院：\n"
            "- 症状持续加重或出现新的异常症状\n"
            "- 宝宝精神状态明显变差\n"
            "- 出现呼吸困难、持续高热等危险信号\n\n"
            "**您可能还想了解**：\n"
            "- 有哪些需要特别注意的地方？\n"
            "- 什么情况需要就医？\n"
            "- 如何观察宝宝的恢复情况？"
        )

    def _build_rag_prompt(
        self,
        query: str,
        sources: List[KnowledgeSource],
        context: Optional[Dict[str, Any]]
    ) -> str:
        """构建 RAG 提示词"""
        prompt = f"家长的问题：{query}\n\n"

        if context and context.get('baby_info'):
            baby_info = context['baby_info']
            prompt += "宝宝信息：\n"
            if baby_info.get('age_months'):
                prompt += f"- 月龄：{baby_info['age_months']}个月\n"
            if baby_info.get('weight_kg'):
                prompt += f"- 体重：{baby_info['weight_kg']}kg\n"
            prompt += "\n"

        prompt += "以下是从权威医学知识库中检索到的相关内容：\n\n"
        for i, source in enumerate(sources, 1):
            prompt += f"--- 文档{i} ---\n"
            prompt += f"{source.content}\n\n"

        prompt += "请基于以上知识库内容，用温暖易懂的语言回答家长的问题。\n"
        prompt += "注意：不要在回答正文中插入来源标记或引用编号。\n"

        return prompt

    def _get_rag_system_prompt(self) -> str:
        """获取 RAG 系统提示词"""
        return """你是「小儿安」，一位温暖、专业的儿科健康顾问。你的用户是焦虑的新手爸妈，请用朋友般的口吻和他们交流。

## 回答原则
1. 优先引用知识库文档中的内容作为核心依据
2. 当文档提供了部分信息但不够完整时，你可以基于儿科常识进行合理补充（如基础护理建议：多休息、注意观察、保持通风等），但需标注"一般建议"
3. 当文档完全没有相关信息时，坦诚告知，并给出就医建议，而不是简单拒绝
4. 绝不编造具体数据（如药物剂量、体温阈值），数据必须来自文档

## 语气要求
- 像一位有经验的儿科护士在和家长聊天，温暖但不啰嗦
- 用"宝宝""您"等亲切称呼
- 避免学术论文式的长句，多用短句和口语化表达

## 输出格式
使用清晰的 Markdown 格式，包含：
- 核心结论
- 护理建议（编号列表）
- 注意事项
- 就医警示
- 引导问题

## 禁止事项
- 不要推荐具体处方药名称或剂量
- 不要做出确诊性判断
- 不要使用绝对化承诺"""

    def format_with_citations(
        self,
        answer: str,
        sources: List[KnowledgeSource]
    ) -> str:
        """格式化答案，清理来源标记"""
        clean_answer = re.sub(r'【来源:[^】]+】', '', answer).strip()
        return clean_answer

    def get_sources_metadata(
        self,
        sources: List[KnowledgeSource]
    ) -> List[Dict[str, Any]]:
        """获取来源元数据"""
        return [
            {
                "id": s.metadata.get("id", "unknown"),
                "title": s.metadata.get("title", "未知"),
                "source": s.source
            }
            for s in sources
        ]

    def get_entry_by_id(self, entry_id: str) -> Optional[Dict[str, Any]]:
        """根据 ID 获取知识库条目"""
        # 优先从本地知识库查找
        for entry in self.knowledge_base:
            if entry.get('id') == entry_id:
                return entry

        # 如果使用 ChromaDB，可以异步查询
        # 这里保持同步接口，返回 None
        return None


# 创建全局实例（延迟初始化）
_rag_service: Optional[RAGService] = None


def get_rag_service() -> RAGService:
    """获取 RAG 服务单例"""
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
    return _rag_service


# 向后兼容：保留原有的全局实例
rag_service = None  # 延迟初始化


def _init_rag_service():
    """初始化 RAG 服务（在首次使用时调用）"""
    global rag_service
    if rag_service is None:
        rag_service = get_rag_service()


# 模块加载时不自动初始化，避免 ChromaDB 连接问题
