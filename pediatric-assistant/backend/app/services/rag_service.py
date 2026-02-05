"""
RAG服务 - 知识库检索与内容溯源
"""
import json
import os
from typing import List, Dict, Any, Optional
from loguru import logger
import dashscope
from dashscope import TextEmbedding
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from app.config import settings
from app.models.user import KnowledgeSource, RAGResult


class RAGService:
    """RAG检索服务"""

    def __init__(self):
        """初始化"""
        dashscope.api_key = settings.QWEN_API_KEY
        self.knowledge_base = self._load_knowledge_base()
        self.embeddings_cache = {}

    def _load_knowledge_base(self) -> List[Dict[str, Any]]:
        """加载知识库"""
        knowledge_base = []
        kb_path = settings.KNOWLEDGE_BASE_PATH

        try:
            # 遍历知识库目录下的所有JSON文件
            for filename in os.listdir(kb_path):
                if filename.endswith('.json'):
                    filepath = os.path.join(kb_path, filename)
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        # 展开entries
                        for entry in data.get('entries', []):
                            entry['topic'] = data.get('topic')
                            entry['category'] = data.get('category')
                            knowledge_base.append(entry)

            logger.info(f"加载知识库完成，共 {len(knowledge_base)} 条记录")
            return knowledge_base

        except Exception as e:
            logger.error(f"加载知识库失败: {e}", exc_info=True)
            return []

    async def get_embedding(self, text: str) -> Optional[List[float]]:
        """
        获取文本的向量表示

        Args:
            text: 文本

        Returns:
            Optional[List[float]]: 向量
        """
        # 检查缓存
        if text in self.embeddings_cache:
            return self.embeddings_cache[text]

        try:
            response = TextEmbedding.call(
                model=TextEmbedding.Models.text_embedding_v1,
                input=text
            )

            if response.status_code == 200:
                embedding = response.output['embeddings'][0]['embedding']
                # 缓存结果
                self.embeddings_cache[text] = embedding
                return embedding
            else:
                logger.error(f"获取embedding失败: {response}")
                return None

        except Exception as e:
            logger.error(f"获取embedding异常: {e}", exc_info=True)
            return None

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
            filters: 过滤条件（如age_range, category等）

        Returns:
            List[KnowledgeSource]: 检索结果
        """
        if not self.knowledge_base:
            logger.warning("知识库为空")
            return []

        try:
            # 1. 获取查询向量
            query_embedding = await self.get_embedding(query)
            if query_embedding is None:
                return []

            # 2. 计算相似度
            candidates = []
            for entry in self.knowledge_base:
                # 应用过滤条件
                if filters:
                    if not self._match_filters(entry, filters):
                        continue

                # 获取文档向量
                doc_text = f"{entry.get('title', '')} {entry.get('content', '')}"
                doc_embedding = await self.get_embedding(doc_text)

                if doc_embedding is None:
                    continue

                # 计算余弦相似度
                similarity = cosine_similarity(
                    [query_embedding],
                    [doc_embedding]
                )[0][0]

                candidates.append({
                    'entry': entry,
                    'similarity': float(similarity)
                })

            # 3. 排序并返回top_k
            candidates.sort(key=lambda x: x['similarity'], reverse=True)
            top_candidates = candidates[:top_k]

            # 4. 过滤低相似度结果
            results = []
            for candidate in top_candidates:
                if candidate['similarity'] >= settings.SIMILARITY_THRESHOLD:
                    entry = candidate['entry']
                    results.append(KnowledgeSource(
                        content=entry.get('content', ''),
                        source=entry.get('source', '未知来源'),
                        score=candidate['similarity'],
                        metadata={
                            'id': entry.get('id'),
                            'title': entry.get('title'),
                            'topic': entry.get('topic'),
                            'category': entry.get('category'),
                            'tags': entry.get('tags', []),
                            'age_range': entry.get('age_range'),
                            'alert_level': entry.get('alert_level')
                        }
                    ))

            logger.info(f"检索到 {len(results)} 条相关知识，相似度范围: {[r.score for r in results]}")
            return results

        except Exception as e:
            logger.error(f"检索失败: {e}", exc_info=True)
            return []

    def _match_filters(self, entry: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        """检查entry是否匹配过滤条件"""
        for key, value in filters.items():
            if key == 'age_months':
                # 检查年龄范围
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
            # 解析 "0-36个月" 格式
            if '-' in age_range_str and '个月' in age_range_str:
                parts = age_range_str.replace('个月', '').split('-')
                min_age = int(parts[0])
                max_age = int(parts[1])
                return min_age <= age_months <= max_age
        except:
            pass

        return True

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

        sources = await self.retrieve(query, top_k=3, filters=filters)

        # 2. 如果没有检索到相关知识，返回拒答
        if not sources:
            return RAGResult(
                answer="抱歉，我的权威知识库中暂无关于此问题的记录。建议您咨询专业医生。",
                sources=[],
                has_source=False
            )

        # 3. 构建prompt，让LLM基于检索结果生成答案
        from app.services.llm_service import llm_service

        prompt = self._build_rag_prompt(query, sources, context)

        # 4. 生成答案（非流式）
        try:
            import dashscope
            from dashscope import Generation

            response = Generation.call(
                model=settings.QWEN_MODEL,
                messages=[
                    {"role": "system", "content": self._get_rag_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                result_format="message",
                temperature=0.3,  # 低温度，确保答案忠实于原文
            )

            if response.status_code == 200:
                answer = response.output.choices[0].message.content

                # 5. 添加溯源角标
                answer_with_citations = self.format_with_citations(answer, sources)

                return RAGResult(
                    answer=answer_with_citations,
                    sources=sources,
                    has_source=True
                )
            else:
                logger.error(f"生成答案失败: {response}")
                return RAGResult(
                    answer="抱歉，系统出现异常，请稍后重试。",
                    sources=[],
                    has_source=False
                )

        except Exception as e:
            logger.error(f"生成答案异常: {e}", exc_info=True)
            return RAGResult(
                answer="抱歉，系统出现异常，请稍后重试。",
                sources=[],
                has_source=False
            )

    def _build_rag_prompt(
        self,
        query: str,
        sources: List[KnowledgeSource],
        context: Optional[Dict[str, Any]]
    ) -> str:
        """构建RAG提示词"""
        prompt = f"用户问题：{query}\n\n"

        if context and context.get('baby_info'):
            baby_info = context['baby_info']
            prompt += "用户档案：\n"
            if baby_info.get('age_months'):
                prompt += f"- 宝宝月龄：{baby_info['age_months']}个月\n"
            if baby_info.get('weight_kg'):
                prompt += f"- 体重：{baby_info['weight_kg']}kg\n"
            prompt += "\n"

        prompt += "权威知识库检索结果：\n\n"
        for i, source in enumerate(sources, 1):
            prompt += f"【文档{i}】\n"
            prompt += f"标题：{source.metadata.get('title', '未知')}\n"
            prompt += f"来源：{source.source}\n"
            prompt += f"内容：{source.content}\n\n"

        prompt += "请基于以上权威知识库内容回答用户问题。要求：\n"
        prompt += "1. 答案必须完全基于检索到的文档内容，不要添加文档中没有的信息\n"
        prompt += "2. 使用结构化格式输出（核心结论、操作步骤、注意事项、安全红线）\n"
        prompt += "3. 如果用户问题涉及剂量计算，必须结合用户档案中的体重信息\n"
        prompt += "4. 保持语言简洁、易懂，避免过于专业的术语\n"

        return prompt

    def _get_rag_system_prompt(self) -> str:
        """获取RAG系统提示词"""
        return """你是一个专业的儿科健康助手，专注于基于权威医学知识库回答问题。

**核心原则**：
1. 答案必须100%基于提供的权威文档，不要编造或推测
2. 如果文档中没有相关信息，明确告知用户
3. 对于剂量、操作步骤等关键信息，必须精确引用原文
4. 保持客观、科学，不做绝对化承诺

**输出格式**：
1. 核心结论（一句话总结）
2. 详细说明（分点列出）
3. 注意事项（如果有）
4. 安全红线（什么情况必须就医）

**禁止事项**：
- 禁止添加文档中没有的信息
- 禁止做出确诊性判断
- 禁止推荐处方药
- 禁止使用绝对化承诺"""

    def format_with_citations(self, answer: str, sources: List[KnowledgeSource]) -> str:
        """
        格式化答案，添加溯源角标

        Args:
            answer: 原始答案
            sources: 来源列表

        Returns:
            str: 添加角标后的答案
        """
        # 在答案末尾添加来源列表
        citations = "\n\n**📚 知识来源**：\n"
        for i, source in enumerate(sources, 1):
            title = source.metadata.get('title', '未知')
            citations += f"{i}. {title} - {source.source}\n"

        return answer + citations

    def get_entry_by_id(self, entry_id: str) -> Optional[Dict[str, Any]]:
        """
        根据ID获取知识库条目（用于点击角标查看原文）

        Args:
            entry_id: 条目ID

        Returns:
            Optional[Dict[str, Any]]: 条目内容
        """
        for entry in self.knowledge_base:
            if entry.get('id') == entry_id:
                return entry
        return None


# 创建全局实例
rag_service = RAGService()
