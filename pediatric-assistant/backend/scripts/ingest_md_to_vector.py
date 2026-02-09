#!/usr/bin/env python3
"""
Markdown到向量数据库的摄入脚本
处理《美国儿科学会育儿百科》的分册文件

功能：
1. 读取两个Markdown分册文件
2. 基于Markdown标题结构进行切片
3. 上下文增强：将标题路径拼接到正文前
4. 二次切片：处理超过800 tokens的长文本
5. 使用ChromaDB + Qwen3-Embedding-8B（硅基流动）
6. 批量处理 + 进度显示
"""

import os
import sys
import hashlib
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

import tiktoken
from tqdm import tqdm
from dotenv import load_dotenv

# LangChain相关
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter
)
from langchain_core.documents import Document
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings

# ============ 配置类 ============

@dataclass
class IngestConfig:
    """摄入配置"""

    # 文件路径
    md_file_part1: str = "/Users/zhang/Desktop/Claude/《美国儿科学会育儿百科》1-600.md"
    md_file_part2: str = "/Users/zhang/Desktop/Claude/《美国儿科学会育儿百科》601-1054.md"

    # ChromaDB配置
    persist_directory: str = "./chroma_db"
    collection_name: str = "parenting_encyclopedia"

    # Embedding配置
    embedding_model: str = "BAAI/bge-m3"  # 硅基流动embedding模型（支持8192 tokens）
    openai_api_key: Optional[str] = None
    openai_api_base: Optional[str] = None

    # Token限制（bge-m3支持更长的输入）
    max_input_tokens: int = 8000  # 安全限制

    # 硅基流动配置
    siliconflow_api_key: Optional[str] = None
    siliconflow_base_url: str = "https://api.siliconflow.cn/v1"
    use_siliconflow: bool = True  # 默认使用硅基流动

    # 切片配置
    max_chunk_size: int = 800  # token限制（bge-m3支持8192）
    chunk_overlap: int = 100

    # 批处理配置（硅基流动限制最多32）
    batch_size: int = 32

    # Markdown标题层级定义
    markdown_headers: List[tuple] = field(default_factory=lambda: [
        ("#", "h1"),
        ("##", "h2"),
        ("###", "h3"),
    ])

    def __post_init__(self):
        """初始化后处理"""
        # 优先使用硅基流动配置
        if self.use_siliconflow:
            if self.siliconflow_api_key is None:
                self.siliconflow_api_key = os.getenv("SILICONFLOW_API_KEY")
            # 从环境变量获取Base URL
            base_url = os.getenv("SILICONFLOW_BASE_URL")
            if base_url:
                self.siliconflow_base_url = base_url
            # 使用硅基流动的配置作为主要配置
            self.openai_api_key = self.siliconflow_api_key
            self.openai_api_base = self.siliconflow_base_url
        else:
            # 使用OpenAI配置
            if self.openai_api_key is None:
                self.openai_api_key = os.getenv("OPENAI_API_KEY")
            if self.openai_api_base is None:
                self.openai_api_base = os.getenv("OPENAI_API_BASE")

        # 检查API Key
        if not self.openai_api_key:
            if self.use_siliconflow:
                raise ValueError(
                    "未找到SILICONFLOW_API_KEY！请在.env文件中配置或通过参数传入"
                )
            else:
                raise ValueError(
                    "未找到OPENAI_API_KEY！请在.env文件中配置或通过参数传入"
                )


# ============ Token计数工具 ============

class TokenCounter:
    """Token计数器"""

    def __init__(self, model: str = "gpt-3.5-turbo"):
        try:
            self.encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            self.encoding = tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str) -> int:
        """计算文本的token数量"""
        return len(self.encoding.encode(text))


# ============ 主类：MarkdownRAGIngestor ============

class MarkdownRAGIngestor:
    """Markdown文档RAG数据摄入器"""

    def __init__(self, config: IngestConfig):
        """初始化摄入器

        Args:
            config: 摄入配置
        """
        self.config = config
        self.token_counter = TokenCounter()

        print("="*80)
        print("RAG数据管道 - Markdown摄入工具")
        print("="*80)

        # 显示API配置信息
        if self.config.use_siliconflow:
            print(f"使用: 硅基流动API")
            print(f"API Base: {self.config.openai_api_base}")
        else:
            print(f"使用: OpenAI API")

        print(f"Embedding模型: {self.config.embedding_model}")
        print(f"最大Chunk大小: {self.config.max_chunk_size} tokens")
        print(f"批处理大小: {self.config.batch_size}")
        print("="*80)

    def load_markdown_file(self, file_path: str) -> str:
        """读取Markdown文件内容

        Args:
            file_path: 文件路径

        Returns:
            文件内容字符串
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        print(f"\n正在读取文件: {file_path}")
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        print(f"  文件大小: {len(content):,} 字符")
        return content

    def split_by_markdown_structure(
        self,
        content: str,
        source_tag: str,
        page_range: str
    ) -> List[Document]:
        """基于Markdown结构进行切片

        Args:
            content: Markdown内容
            source_tag: 源文件标签（part1或part2）
            page_range: 页码范围

        Returns:
            切分后的文档列表
        """
        print("\n正在执行Markdown结构切片...")

        # 初始化Markdown切片器
        markdown_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=self.config.markdown_headers,
            strip_headers=False  # 保留原始标题在正文中
        )

        # 执行切片
        docs = markdown_splitter.split_text(content)
        print(f"  切片后得到 {len(docs)} 个文档块")

        # 添加源文件元数据
        for doc in docs:
            doc.metadata["source_file"] = source_tag
            doc.metadata["page_range"] = page_range

        return docs

    def enrich_document_context(self, documents: List[Document]) -> List[Document]:
        """
        上下文增强：将标题信息拼接到正文前面

        格式：【背景: h1值 > h2值 (来源: part1/p2-XXX)】原文内容...

        Args:
            documents: 文档列表

        Returns:
            增强后的文档列表
        """
        print("\n正在执行上下文增强...")

        enriched_docs = []

        for doc in tqdm(documents, desc="上下文增强"):
            # 构建标题路径
            title_parts = []

            # 从metadata中提取标题层级
            if "h1" in doc.metadata and doc.metadata["h1"]:
                title_parts.append(doc.metadata["h1"])
            if "h2" in doc.metadata and doc.metadata["h2"]:
                title_parts.append(doc.metadata["h2"])
            if "h3" in doc.metadata and doc.metadata["h3"]:
                title_parts.append(doc.metadata["h3"])

            # 获取来源信息
            source_tag = doc.metadata.get("source_file", "unknown")
            page_range = doc.metadata.get("page_range", "")

            # 构建上下文前缀
            if title_parts:
                context_prefix = f"【背景: {' > '.join(title_parts)} (来源: {source_tag}, 页码: {page_range})】"
            else:
                context_prefix = f"【背景: 通用内容 (来源: {source_tag}, 页码: {page_range})】"

            # 重写page_content
            original_content = doc.page_content
            doc.page_content = f"{context_prefix}\n\n{original_content}"

            # 计算token数
            token_count = self.token_counter.count_tokens(doc.page_content)
            doc.metadata["token_count"] = token_count
            doc.metadata["has_context"] = True

            enriched_docs.append(doc)

        avg_tokens = sum(d.metadata['token_count'] for d in enriched_docs) / len(enriched_docs)
        print(f"  增强完成，平均token数: {avg_tokens:.0f}")

        return enriched_docs

    def split_large_chunks(self, documents: List[Document]) -> List[Document]:
        """
        对超过max_chunk_size的chunk进行二次切分

        使用RecursiveCharacterTextSplitter保持上下文连贯性

        Args:
            documents: 文档列表

        Returns:
            切分后的文档列表
        """
        print(f"\n正在检查并切分超过 {self.config.max_chunk_size} tokens的chunk...")

        # 初始化递归切片器
        recursive_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.config.max_chunk_size,
            chunk_overlap=self.config.chunk_overlap,
            length_function=self.token_counter.count_tokens,
            separators=[
                "\n\n\n",  # 段落间
                "\n\n",   # 段落内
                "\n",     # 行
                "。",     # 中文句号
                "！",     # 中文感叹号
                "？",     # 中文问号
                "，",     # 中文逗号
                " ",      # 空格
                ""        # 字符级别
            ]
        )

        final_docs = []
        split_count = 0
        total_splits = 0

        for doc in tqdm(documents, desc="二次切分"):
            token_count = doc.metadata.get("token_count", 0)

            if token_count <= self.config.max_chunk_size:
                # 不需要切分
                final_docs.append(doc)
            else:
                # 需要切分
                split_docs = recursive_splitter.split_documents([doc])

                # 为分割后的文档添加序号，并重新计算token
                for i, split_doc in enumerate(split_docs):
                    split_doc.metadata["split_index"] = i
                    split_doc.metadata["total_splits"] = len(split_docs)

                    # 重新计算token数（因为切分后内容可能略有不同）
                    new_token_count = self.token_counter.count_tokens(split_doc.page_content)
                    split_doc.metadata["token_count"] = new_token_count

                    # 保留原始元数据
                    for key, value in doc.metadata.items():
                        if key not in ["split_index", "total_splits", "token_count"]:
                            split_doc.metadata[key] = value

                final_docs.extend(split_docs)
                split_count += 1
                total_splits += len(split_docs)

        print(f"  切分了 {split_count} 个长chunk，产生 {total_splits} 个子chunk")
        print(f"  最终文档数: {len(final_docs)}")

        return final_docs

    def initialize_vector_store(self) -> Chroma:
        """
        初始化向量存储

        Returns:
            Chroma向量存储实例
        """
        print(f"\n正在初始化ChromaDB...")
        print(f"  持久化目录: {self.config.persist_directory}")
        print(f"  集合名称: {self.config.collection_name}")

        # 显示API配置信息
        if self.config.use_siliconflow:
            print(f"  使用硅基流动API")
            print(f"  API Base: {self.config.openai_api_base}")
            print(f"  Embedding模型: {self.config.embedding_model}")
        else:
            print(f"  使用OpenAI API")
            print(f"  Embedding模型: {self.config.embedding_model}")

        # 创建持久化目录
        Path(self.config.persist_directory).mkdir(parents=True, exist_ok=True)

        # 初始化OpenAI Embeddings（兼容OpenAI API格式的服务）
        embeddings_kwargs = {
            "model": self.config.embedding_model,
            "openai_api_key": self.config.openai_api_key
        }

        # 如果有自定义API Base，添加到参数中
        if self.config.openai_api_base:
            embeddings_kwargs["openai_api_base"] = self.config.openai_api_base

        embeddings = OpenAIEmbeddings(**embeddings_kwargs)

        # 初始化ChromaDB
        vector_store = Chroma(
            collection_name=self.config.collection_name,
            embedding_function=embeddings,
            persist_directory=self.config.persist_directory
        )

        return vector_store

    def embed_and_store_documents(
        self,
        documents: List[Document],
        vector_store: Chroma
    ) -> None:
        """
        批量向量化并存储文档

        Args:
            documents: 文档列表
            vector_store: Chroma向量存储实例
        """
        print(f"\n正在向量化并存储 {len(documents)} 个文档...")

        # 生成唯一ID
        for i, doc in enumerate(documents):
            if not doc.metadata.get("chunk_id"):
                # 基于内容hash生成唯一ID
                content_hash = hashlib.md5(
                    doc.page_content.encode('utf-8')
                ).hexdigest()[:8]
                source_tag = doc.metadata.get('source_file', 'doc')
                doc.metadata["chunk_id"] = f"{source_tag}_{i}_{content_hash}"

        # 分批处理
        batch_size = self.config.batch_size
        total_batches = (len(documents) + batch_size - 1) // batch_size

        for batch_idx in tqdm(range(total_batches), desc="向量化入库"):
            start_idx = batch_idx * batch_size
            end_idx = min((batch_idx + 1) * batch_size, len(documents))
            batch_docs = documents[start_idx:end_idx]

            # 准备数据
            texts = [doc.page_content for doc in batch_docs]
            metadatas = [doc.metadata for doc in batch_docs]
            ids = [doc.metadata["chunk_id"] for doc in batch_docs]

            # 添加到向量库
            vector_store.add_texts(
                texts=texts,
                metadatas=metadatas,
                ids=ids
            )

        # 持久化
        print(f"\n正在持久化数据...")
        vector_store.persist()
        print(f"  完成！数据已持久化到 {self.config.persist_directory}")

    def preview_samples(self, documents: List[Document], num: int = 2) -> None:
        """
        打印处理后的样本供用户确认

        Args:
            documents: 文档列表
            num: 显示的样本数量
        """
        print("\n" + "="*80)
        print("样本预览（请确认处理效果）")
        print("="*80)

        for i in range(min(num, len(documents))):
            doc = documents[i]
            print(f"\n--- 样本 {i+1} ---")
            print(f"Token数: {doc.metadata.get('token_count', 'N/A')}")
            print(f"来源: {doc.metadata.get('source_file', 'N/A')}")
            print(f"页码范围: {doc.metadata.get('page_range', 'N/A')}")

            # 显示标题信息
            print(f"标题:")
            if "h1" in doc.metadata:
                print(f"  h1: {doc.metadata['h1']}")
            if "h2" in doc.metadata and doc.metadata["h2"]:
                print(f"  h2: {doc.metadata['h2']}")
            if "h3" in doc.metadata and doc.metadata["h3"]:
                print(f"  h3: {doc.metadata['h3']}")

            print(f"\n内容预览（前500字符）:")
            print("-" * 40)
            content_preview = doc.page_content[:500]
            print(content_preview)
            if len(doc.page_content) > 500:
                print(f"... (共 {len(doc.page_content)} 字符)")
            print("-" * 40)

        # 统计信息
        total_tokens = sum(d.metadata.get('token_count', 0) for d in documents)
        print(f"\n统计信息:")
        print(f"  总文档数: {len(documents)}")
        print(f"  总token数: {total_tokens:,}")
        print(f"  平均token/文档: {total_tokens / len(documents):.0f}")
        print("="*80 + "\n")

    def process_file(
        self,
        file_path: str,
        source_tag: str,
        page_range: str
    ) -> List[Document]:
        """
        处理单个文件的完整流程

        Args:
            file_path: 文件路径
            source_tag: 源文件标签（part1或part2）
            page_range: 页码范围

        Returns:
            处理后的文档列表
        """
        print(f"\n{'='*60}")
        print(f"开始处理: {source_tag} ({page_range})")
        print(f"{'='*60}")

        # 步骤1: 读取文件
        content = self.load_markdown_file(file_path)

        # 步骤2: Markdown结构切片
        docs = self.split_by_markdown_structure(content, source_tag, page_range)

        # 步骤3: 上下文增强
        docs = self.enrich_document_context(docs)

        # 步骤4: 二次切分
        docs = self.split_large_chunks(docs)

        print(f"\n处理完成! 最终得到 {len(docs)} 个文档块")

        return docs

    def run(self, preview: bool = True) -> None:
        """
        执行完整的摄入流程

        Args:
            preview: 是否预览样本并等待用户确认
        """
        try:
            # 初始化向量存储
            vector_store = self.initialize_vector_store()

            # 处理两个文件
            all_documents = []

            # 处理part1
            docs_part1 = self.process_file(
                file_path=self.config.md_file_part1,
                source_tag="part1",
                page_range="1-600"
            )
            all_documents.extend(docs_part1)

            # 处理part2
            docs_part2 = self.process_file(
                file_path=self.config.md_file_part2,
                source_tag="part2",
                page_range="601-1054"
            )
            all_documents.extend(docs_part2)

            print(f"\n{'='*60}")
            print(f"两个文件处理完成，总计 {len(all_documents)} 个文档块")
            print(f"{'='*60}")

            # 检查并处理超过限制的文档
            max_api_tokens = self.config.max_input_tokens
            print(f"\n检查文档token数（API限制: {max_api_tokens}）...")

            oversized_count = 0
            for doc in all_documents:
                # 使用更保守的token计算
                try:
                    encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
                except:
                    encoding = tiktoken.get_encoding("cl100k_base")
                token_count = len(encoding.encode(doc.page_content))

                if token_count >= max_api_tokens:
                    # 截断文档
                    tokens = encoding.encode(doc.page_content)
                    doc.page_content = encoding.decode(tokens[:max_api_tokens - 20])  # 留余量
                    oversized_count += 1

            if oversized_count > 0:
                print(f"  已截断 {oversized_count} 个超过限制的文档")

            # 预览样本
            if preview:
                self.preview_samples(all_documents, num=2)

                # 用户确认
                response = input("\n确认以上处理效果是否正确？(yes/no): ")
                if response.lower() not in ['yes', 'y']:
                    print("用户取消操作，未保存到向量数据库。")
                    return

            # 向量化并存储
            self.embed_and_store_documents(all_documents, vector_store)

            print("\n" + "="*80)
            print("全部完成！知识库已成功构建。")
            print("="*80)

        except Exception as e:
            print(f"\n错误: {str(e)}")
            import traceback
            traceback.print_exc()


# ============ 主入口 ============

def main():
    """主入口函数"""
    # 添加项目根目录到路径
    SCRIPT_DIR = Path(__file__).parent
    PROJECT_ROOT = SCRIPT_DIR.parent
    sys.path.insert(0, str(PROJECT_ROOT))

    # 加载环境变量
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        load_dotenv(env_file)
        print(f"已加载环境变量配置: {env_file}")
    else:
        print(f"警告: 未找到.env文件: {env_file}")

    # 解析命令行参数
    parser = argparse.ArgumentParser(
        description="Markdown文档RAG摄入工具 (支持硅基流动API)",
        epilog="""
示例:
  # 使用硅基流动API (默认)
  python scripts/ingest_md_to_vector.py

  # 使用OpenAI API
  python scripts/ingest_md_to_vector.py --use-openai --api-key sk-xxx

  # 指定模型
  python scripts/ingest_md_to_vector.py --model Qwen/Qwen-Embedding-8B

支持模型 (硅基流动):
  - BAAI/bge-large-zh-v1.5 (默认，中文效果最好)
  - BAAI/bge-m3 (多语言)
  - Qwen/Qwen-Embedding-8B
  - Qwen/Qwen2-7B-Instruct
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--no-preview",
        action="store_true",
        help="跳过预览确认，直接处理"
    )
    parser.add_argument(
        "--api-key",
        type=str,
        help="OpenAI API密钥"
    )
    parser.add_argument(
        "--api-base",
        type=str,
        help="OpenAI API Base URL（用于兼容其他API服务）"
    )
    parser.add_argument(
        "--collection",
        type=str,
        default="parenting_encyclopedia",
        help="ChromaDB集合名称"
    )
    parser.add_argument(
        "--part1",
        type=str,
        help="第一部分Markdown文件路径"
    )
    parser.add_argument(
        "--part2",
        type=str,
        help="第二部分Markdown文件路径"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="批处理大小（默认: 100）"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="BAAI/bge-m3",
        help="Embedding模型名称（默认: BAAI/bge-m3，硅基流动）"
    )
    parser.add_argument(
        "--use-openai",
        action="store_true",
        help="使用OpenAI API而非硅基流动"
    )

    args = parser.parse_args()

    # 创建配置
    config = IngestConfig(
        openai_api_key=args.api_key,
        openai_api_base=args.api_base,
        collection_name=args.collection,
        md_file_part1=args.part1 if args.part1 else IngestConfig.md_file_part1,
        md_file_part2=args.part2 if args.part2 else IngestConfig.md_file_part2,
        batch_size=args.batch_size,
        embedding_model=args.model,
        use_siliconflow=not args.use_openai
    )

    # 创建摄入器并运行
    ingestor = MarkdownRAGIngestor(config)
    ingestor.run(preview=not args.no_preview)


if __name__ == "__main__":
    main()
