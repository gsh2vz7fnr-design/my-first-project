"""
RAG服务 - 知识库检索与内容溯源
"""
import json
import os
import math
import re
import time
from collections import Counter
from typing import List, Dict, Any, Optional
from loguru import logger
from openai import OpenAI

from app.config import settings
from app.models.user import KnowledgeSource, RAGResult


class RAGService:
    """RAG检索服务"""

    def __init__(self):
        """初始化"""
        self.client = OpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL
        )
        self.chat_model = settings.DEEPSEEK_MODEL
        self.embedding_model = settings.EMBEDDING_MODEL
        self.knowledge_base = self._load_knowledge_base()
        self.embeddings_cache = {}
        self._api_key_configured = bool(settings.DEEPSEEK_API_KEY)
        self._remote_cooldown_until: float = 0.0
        self._doc_token_counts: List[Counter] = []
        self._build_local_index()

    @property
    def remote_available(self) -> bool:
        if not self._api_key_configured:
            return False
        return time.time() >= self._remote_cooldown_until

    @remote_available.setter
    def remote_available(self, value: bool):
        if not value:
            self._remote_cooldown_until = time.time() + 60  # 60秒冷却
        else:
            self._remote_cooldown_until = 0.0

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
            response = self.client.embeddings.create(
                model=self.embedding_model,
                input=text
            )
            embedding = response.data[0].embedding
            self.embeddings_cache[text] = embedding
            return embedding
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
        检索相关知识（混合检索 + 重排序）
        
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
            # 1. 混合检索召回 (Recall)
            candidates = await self._hybrid_search(query, top_k=50, filters=filters)
            
            # 2. 重排序 (Rerank)
            results = await self._rerank(query, candidates, top_k=top_k)
            
            logger.info(f"检索完成: 召回{len(candidates)}条 -> 重排序选出{len(results)}条")
            return results

        except Exception as e:
            logger.error(f"检索失败: {e}", exc_info=True)
            return []

    async def _hybrid_search(
        self, 
        query: str, 
        top_k: int = 50, 
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        混合检索策略：语义检索 (70%) + 关键词检索 (30%)
        """
        # 1. 向量检索 (Semantic Search)
        vector_candidates = []
        if self.remote_available and self.embedding_model != "local":
            query_embedding = await self.get_embedding(query)
            if query_embedding:
                for entry in self.knowledge_base:
                    if filters and not self._match_filters(entry, filters):
                        continue
                        
                    doc_text = f"{entry.get('title', '')} {entry.get('content', '')}"
                    # 注意：这里应该缓存doc_embedding，简化起见假设已缓存或按需获取
                    # 实际生产中应使用向量数据库
                    doc_embedding = self.embeddings_cache.get(doc_text)
                    if not doc_embedding:
                        # 避免实时大量调用Embedding API，这里仅作演示
                        # 实际应预先计算好所有文档Embedding
                        continue
                        
                    similarity = self._cosine_similarity(query_embedding, doc_embedding)
                    vector_candidates.append({
                        "entry": entry,
                        "vector_score": float(similarity),
                        "keyword_score": 0.0
                    })

        # 2. 关键词检索 (Keyword Search - BM25-like)
        # 如果向量检索不可用或为了增强效果，计算关键词分数
        keyword_candidates = []
        query_counter = self._text_to_counter(query)

        # 同义词映射：口语化表达 → 标准术语
        synonym_mapping = {
            "拉肚子": "腹泻", "拉稀": "腹泻",
            "发烧": "发热", "高烧": "发热",
            "吐": "呕吐", "吐奶": "呕吐",
            "咳": "咳嗽",
            "起疹子": "皮疹", "湿疹": "皮疹",
            "摔伤": "摔倒", "跌倒": "摔倒", "跌落": "摔倒",
            "便秘": "大便困难"
        }

        # 对查询进行同义词扩展
        expanded_query_tokens = set(query_counter.keys())
        for token in list(query_counter.keys()):
            if token in synonym_mapping:
                expanded_query_tokens.add(synonym_mapping[token])

        # 也需要反向扩展：如果文档有标准术语，查询有口语表达，应该匹配
        reverse_synonym_mapping = {v: k for k, v in synonym_mapping.items()}
        for token in list(query_counter.keys()):
            if token in reverse_synonym_mapping:
                expanded_query_tokens.add(reverse_synonym_mapping[token])

        for idx, entry in enumerate(self.knowledge_base):
            if filters and not self._match_filters(entry, filters):
                continue

            # 使用简单的词频重合度作为关键词分数
            keyword_score = self._cosine_similarity_counts(query_counter, self._doc_token_counts[idx])

            # 标题匹配加权 - 双向检查
            title = entry.get("title", "")
            # 检查标题是否在查询中
            if title and title in query:
                keyword_score += 0.5
            # 检查查询关键词（含同义词）是否在标题中 - 使用子字符串匹配
            elif title:
                # 对于中文词汇，使用子字符串匹配更可靠
                for query_token in expanded_query_tokens:
                    if len(query_token) > 1 and query_token in title:
                        keyword_score += 0.4
                        break

            # 标签匹配加权 - 同样使用子字符串匹配
            tags = entry.get("tags", [])
            for tag in tags:
                for query_token in expanded_query_tokens:
                    if len(query_token) > 1 and query_token in tag:
                        keyword_score += 0.2
                        break

            keyword_candidates.append({
                "entry": entry,
                "keyword_score": keyword_score
            })
            
        # 3. 融合分数 (Fusion)
        # 使用简单的加权融合: 0.7 * Vector + 0.3 * Keyword
        # 需处理 vector_candidates 和 keyword_candidates 的合并
        
        # 建立 entry_id -> candidate 映射
        merged = {}
        
        # 处理向量结果
        for item in vector_candidates:
            eid = item["entry"].get("id")
            merged[eid] = item
            
        # 处理关键词结果
        for item in keyword_candidates:
            eid = item["entry"].get("id")
            if eid in merged:
                merged[eid]["keyword_score"] = item["keyword_score"]
            else:
                merged[eid] = {
                    "entry": item["entry"],
                    "vector_score": 0.0, # 未命中向量检索
                    "keyword_score": item["keyword_score"]
                }
                
        # 计算最终分数
        final_candidates = []
        for item in merged.values():
            # 归一化分数 (假设分数都在 0-1 之间)
            v_score = item.get("vector_score", 0.0)
            k_score = item.get("keyword_score", 0.0)
            
            # 混合权重
            if self.remote_available:
                final_score = 0.7 * v_score + 0.3 * k_score
            else:
                final_score = k_score # 仅使用关键词
                
            item["score"] = final_score
            final_candidates.append(item)
            
        # 排序并截取
        final_candidates.sort(key=lambda x: x["score"], reverse=True)
        return final_candidates[:top_k]

    async def _rerank(
        self, 
        query: str, 
        candidates: List[Dict[str, Any]], 
        top_k: int = 3
    ) -> List[KnowledgeSource]:
        """
        重排序 (Reranking)
        模拟 Cross-Encoder 的效果，对召回结果进行精细打分
        """
        # 由于环境限制无法运行 BGE-Reranker，使用启发式规则模拟
        reranked = []
        
        for item in candidates:
            entry = item["entry"]
            base_score = item["score"]
            rerank_score = base_score
            
            content = entry.get("content", "")
            title = entry.get("title", "")
            
            # 规则1: 精确短语匹配奖励
            if query in content:
                rerank_score += 0.2

            # 规则2: 关键医学实体匹配 (模拟)
            # 比如查询包含"泰诺林"，文档标题也包含
            if "泰诺林" in query and "泰诺林" in title:
                rerank_score += 0.3
            if "美林" in query and "美林" in title:
                rerank_score += 0.3

            # 规则3: 同义词/口语化表达匹配奖励
            # 如果查询包含 "拉肚子" 而文档包含 "腹泻"
            diarrhea_keywords = ["拉肚子", "拉稀", "腹泻"]
            if any(kw in query for kw in diarrhea_keywords) and "腹泻" in title:
                rerank_score += 0.2

            fever_keywords = ["发烧", "发热", "高烧"]
            if any(kw in query for kw in fever_keywords) and any(kw in title for kw in fever_keywords):
                rerank_score += 0.2

            cough_keywords = ["咳嗽", "咳"]
            if any(kw in query for kw in cough_keywords) and "咳嗽" in title:
                rerank_score += 0.2

            vomit_keywords = ["呕吐", "吐", "吐奶"]
            if any(kw in query for kw in vomit_keywords) and "呕吐" in title:
                rerank_score += 0.2

            rash_keywords = ["皮疹", "疹子", "湿疹"]
            if any(kw in query for kw in rash_keywords) and "皮疹" in title:
                rerank_score += 0.2
                
            # 规则3: 负向惩罚 (如果查询是"不发烧"但文档全是"发烧")
            # (略，过于复杂)
            
            # 阈值过滤
            if rerank_score < settings.SIMILARITY_THRESHOLD and not self.remote_available:
                 # 本地模式稍微放宽
                 if rerank_score < 0.1: continue
            elif rerank_score < settings.SIMILARITY_THRESHOLD:
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
                        'keyword_score': item.get('keyword_score', 0)
                    }
                }
            ))
            
        # 再次排序
        reranked.sort(key=lambda x: x.score, reverse=True)
        return reranked[:top_k]

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
        except (ValueError, IndexError):
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
        prompt = self._build_rag_prompt(query, sources, context)

        # 4. 生成答案（非流式）
        try:
            if not self.remote_available:
                answer = self._build_fallback_answer(sources)
                answer_with_citations = self.format_with_citations(answer, sources)
                return RAGResult(
                    answer=answer_with_citations,
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

            # 5. 添加溯源角标
            answer_with_citations = self.format_with_citations(answer, sources)

            return RAGResult(
                answer=answer_with_citations,
                sources=sources,
                has_source=True
            )
        except Exception as e:
            logger.error(f"生成答案异常: {e}", exc_info=True)
            self.remote_available = False
            answer = self._build_fallback_answer(sources)
            answer_with_citations = self.format_with_citations(answer, sources)
            return RAGResult(
                answer=answer_with_citations,
                sources=sources,
                has_source=True
            )

    def _build_fallback_answer(self, sources: List[KnowledgeSource]) -> str:
        """本地兜底回答（无需LLM）"""
        top = sources[0]
        entry_id = top.metadata.get("id", "unknown")
        title = top.metadata.get("title", "参考建议")
        content = top.content

        return (
            f"**核心结论**：{title}【来源:{entry_id}】\n\n"
            f"**操作建议**：\n{content}【来源:{entry_id}】\n\n"
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
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度"""
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0
        dot = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))
        if norm1 == 0.0 or norm2 == 0.0:
            return 0.0
        return dot / (norm1 * norm2)

    def _build_local_index(self) -> None:
        """构建本地检索索引"""
        self._doc_token_counts = []
        for entry in self.knowledge_base:
            doc_text = f"{entry.get('title', '')} {entry.get('content', '')}"
            self._doc_token_counts.append(self._text_to_counter(doc_text))

    def _retrieve_local(
        self,
        query: str,
        top_k: int = 3,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[KnowledgeSource]:
        """本地检索（不依赖外部embedding）"""
        query_counter = self._text_to_counter(query)
        candidates = []
        for idx, entry in enumerate(self.knowledge_base):
            if filters and not self._match_filters(entry, filters):
                continue
            similarity = self._cosine_similarity_counts(query_counter, self._doc_token_counts[idx])
            title = entry.get("title", "")
            tags = entry.get("tags", [])
            if title and title in query:
                similarity = max(similarity, 0.8)
            if tags and any(tag in query for tag in tags):
                similarity = max(similarity, 0.6)
            candidates.append({
                "entry": entry,
                "similarity": float(similarity)
            })

        candidates.sort(key=lambda x: x["similarity"], reverse=True)
        top_candidates = candidates[:top_k]

        results = []
        local_threshold = 0.2
        for candidate in top_candidates:
            if candidate["similarity"] >= local_threshold:
                entry = candidate["entry"]
                results.append(KnowledgeSource(
                    content=entry.get("content", ""),
                    source=entry.get("source", "未知来源"),
                    score=candidate["similarity"],
                    metadata={
                        "id": entry.get("id"),
                        "title": entry.get("title"),
                        "topic": entry.get("topic"),
                        "category": entry.get("category"),
                        "tags": entry.get("tags", []),
                        "age_range": entry.get("age_range"),
                        "alert_level": entry.get("alert_level")
                    }
                ))

        return results

    def _text_to_counter(self, text: str) -> Counter:
        """将文本转换为词频计数器，优先匹配常见医学词汇"""
        text_lower = text.lower()

        # 常见医学词汇列表（优先匹配长词）
        medical_terms = [
            # 症状
            "拉肚子", "腹泻", "发烧", "发热", "咳嗽", "呕吐", "皮疹", "湿疹",
            "惊厥", "抽搐", "呼吸困难", "昏迷", "便秘", "摔倒", "跌落", "摔伤",
            "脱水", "补液", "嗜睡", "精神萎靡",
            # 通用
            "宝宝", "婴儿", "幼儿", "儿童",
            # 时间
            "小时", "分钟", "天", "周", "月", "年"
        ]

        tokens = []
        remaining = text_lower

        # 先匹配医学词汇
        for term in sorted(medical_terms, key=len, reverse=True):
            while term in remaining:
                tokens.append(term)
                # 替换已匹配的部分为空格，避免重复匹配
                remaining = remaining.replace(term, " ", 1)

        # 对剩余文本按单字分词
        for char in remaining:
            if re.match(r"[a-zA-Z0-9]", char):
                tokens.append(char)
            elif re.match(r"[\u4e00-\u9fff]", char):
                tokens.append(char)

        return Counter(tokens)

    def _cosine_similarity_counts(self, c1: Counter, c2: Counter) -> float:
        if not c1 or not c2:
            return 0.0
        common = set(c1.keys()) & set(c2.keys())
        dot = sum(c1[token] * c2[token] for token in common)
        norm1 = math.sqrt(sum(v * v for v in c1.values()))
        norm2 = math.sqrt(sum(v * v for v in c2.values()))
        if norm1 == 0.0 or norm2 == 0.0:
            return 0.0
        return dot / (norm1 * norm2)

    def _build_rag_prompt(
        self,
        query: str,
        sources: List[KnowledgeSource],
        context: Optional[Dict[str, Any]]
    ) -> str:
        """构建RAG提示词"""
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
        """获取RAG系统提示词"""
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
- 适当使用 emoji 增加亲和力（不超过3个）

## 输出格式（使用标准 Markdown，确保排版清晰）

### 📋 必须遵循的排版规则

**1. 段落与换行**
- 每个段落之间必须空一行（使用两个换行符）
- 标题前后必须各空一行
- 绝不能把多个段落挤在一起

**2. 列表格式（强制要求）**
- 数字列表必须使用 Markdown 标准语法：`1. ` `2. ` `3. `（注意点号后面有空格）
- 每个列表项必须独占一行，严禁多个项写在同一行
- 列表项之间不要空行，但列表整体前后要空一行

**3. 标题层级**
- 使用 `###` 作为板块标题（如 `### 💡 核心结论`）
- 标题文字要简洁有力，加上 Emoji 增强识别

**4. 强调格式**
- 关键信息使用 `**加粗**`（如 `**体温超过39℃**`）
- 药物名称、症状词、重要数据必须加粗
- 不要使用 `_斜体_` 或 `~~删除线~~`

**5. 紧急信息突出**
- 就医警示使用 `> 🚨` 引用块格式
- 或者单独一行以 `⚠️` 开头

### 📝 输出模板（严格按此结构）

### 💡 核心结论

[一句话总结，15字以内]


### 🩺 护理建议

1. [第一个具体步骤，不超过20字]
2. [第二个具体步骤]
3. [第三个具体步骤]


### ⚠️ 需要注意

- [注意点1，用 - 开头]
- [注意点2]


> 🚨 **这些情况请立即就医**
>
> - [就医信号1]
> - [就医信号2]
> - [就医信号3]


### 💭 您可能还想了解

- [引导问题1]
- [引导问题2]
- [引导问题3]

### 🚫 禁止的排版行为

- ❌ 将 1. 2. 3. 写在同一行
- ❌ 标题后不换行直接接内容
- ❌ 整段文字没有任何换行
- ❌ 使用 【来源:xxx】 或其他角标

## 禁止事项
- 不要推荐具体处方药名称或剂量
- 不要做出确诊性判断（如"您的宝宝得了XX"）
- 不要使用绝对化承诺"""

    def format_with_citations(self, answer: str, sources: List[KnowledgeSource]) -> str:
        """
        格式化答案，清理来源标记并返回纯净答案

        Args:
            answer: 原始答案
            sources: 来源列表

        Returns:
            str: 清理后的答案（不拼接来源到正文）
        """
        # 清理 LLM 可能残留的来源标记
        clean_answer = re.sub(r'【来源:[^】]+】', '', answer).strip()
        return clean_answer

    def get_sources_metadata(self, sources: List[KnowledgeSource]) -> List[Dict[str, Any]]:
        """
        单独返回来源元数据（供前端使用）

        Args:
            sources: 来源列表

        Returns:
            List[Dict[str, Any]]: 来源元数据列表
        """
        return [
            {
                "id": s.metadata.get("id", "unknown"),
                "title": s.metadata.get("title", "未知"),
                "source": s.source
            }
            for s in sources
        ]

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
