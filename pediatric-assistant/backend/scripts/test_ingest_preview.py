#!/usr/bin/env python3
"""
预览脚本：展示Markdown处理效果，不调用API

用法：
    python scripts/test_ingest_preview.py
"""

import os
import sys
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass, field

import tiktoken
from dotenv import load_dotenv

# LangChain相关
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter
)
from langchain_core.documents import Document


@dataclass
class IngestConfig:
    """摄入配置"""
    md_file_part1: str = "/Users/zhang/Desktop/Claude/《美国儿科学会育儿百科》1-600.md"
    md_file_part2: str = "/Users/zhang/Desktop/Claude/《美国儿科学会育儿百科》601-1054.md"

    # 切片配置
    max_chunk_size: int = 800  # token限制
    chunk_overlap: int = 100

    # Markdown标题层级定义
    markdown_headers: List[tuple] = field(default_factory=lambda: [
        ("#", "h1"),
        ("##", "h2"),
        ("###", "h3"),
    ])


class TokenCounter:
    """Token计数器"""

    def __init__(self, model: str = "gpt-3.5-turbo"):
        try:
            self.encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            self.encoding = tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str) -> int:
        return len(self.encoding.encode(text))


class MarkdownProcessor:
    """Markdown处理器（不含向量存储部分）"""

    def __init__(self, config: IngestConfig):
        self.config = config
        self.token_counter = TokenCounter()

    def load_markdown_file(self, file_path: str) -> str:
        """读取Markdown文件"""
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        print(f"正在读取文件: {file_path}")
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
        """基于Markdown结构切片"""
        print("\n正在执行Markdown结构切片...")

        markdown_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=self.config.markdown_headers,
            strip_headers=False
        )

        docs = markdown_splitter.split_text(content)
        print(f"  切片后得到 {len(docs)} 个文档块")

        # 添加源元数据
        for doc in docs:
            doc.metadata["source_file"] = source_tag
            doc.metadata["page_range"] = page_range

        return docs

    def enrich_document_context(self, documents: List[Document]) -> List[Document]:
        """上下文增强"""
        print("\n正在执行上下文增强...")

        enriched_docs = []

        for doc in documents:
            # 构建标题路径
            title_parts = []

            if "h1" in doc.metadata and doc.metadata["h1"]:
                title_parts.append(doc.metadata["h1"])
            if "h2" in doc.metadata and doc.metadata["h2"]:
                title_parts.append(doc.metadata["h2"])
            if "h3" in doc.metadata and doc.metadata["h3"]:
                title_parts.append(doc.metadata["h3"])

            source_tag = doc.metadata.get("source_file", "unknown")
            page_range = doc.metadata.get("page_range", "")

            if title_parts:
                context_prefix = f"【背景: {' > '.join(title_parts)} (来源: {source_tag}, 页码: {page_range})】"
            else:
                context_prefix = f"【背景: 通用内容 (来源: {source_tag}, 页码: {page_range})】"

            doc.page_content = f"{context_prefix}\n\n{doc.page_content}"
            doc.metadata["token_count"] = self.token_counter.count_tokens(doc.page_content)
            doc.metadata["has_context"] = True

            enriched_docs.append(doc)

        avg_tokens = sum(d.metadata['token_count'] for d in enriched_docs) / len(enriched_docs)
        print(f"  增强完成，平均token数: {avg_tokens:.0f}")

        return enriched_docs

    def split_large_chunks(self, documents: List[Document]) -> List[Document]:
        """二次切分"""
        print(f"\n正在检查并切分超过 {self.config.max_chunk_size} tokens的chunk...")

        recursive_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.config.max_chunk_size,
            chunk_overlap=self.config.chunk_overlap,
            length_function=self.token_counter.count_tokens,
            separators=["\n\n\n", "\n\n", "\n", "。", "！", "？", " ", ""]
        )

        final_docs = []
        split_count = 0

        for doc in documents:
            token_count = doc.metadata.get("token_count", 0)

            if token_count <= self.config.max_chunk_size:
                final_docs.append(doc)
            else:
                split_docs = recursive_splitter.split_documents([doc])

                for i, split_doc in enumerate(split_docs):
                    split_doc.metadata["split_index"] = i
                    split_doc.metadata["total_splits"] = len(split_docs)
                    new_token_count = self.token_counter.count_tokens(split_doc.page_content)
                    split_doc.metadata["token_count"] = new_token_count

                    for key, value in doc.metadata.items():
                        if key not in ["split_index", "total_splits", "token_count"]:
                            split_doc.metadata[key] = value

                final_docs.extend(split_docs)
                split_count += 1

        print(f"  切分了 {split_count} 个长chunk")
        print(f"  最终文档数: {len(final_docs)}")

        return final_docs

    def preview_samples(self, documents: List[Document], num: int = 2) -> None:
        """预览样本"""
        print("\n" + "="*80)
        print("样本预览（请确认处理效果）")
        print("="*80)

        for i in range(min(num, len(documents))):
            doc = documents[i]
            print(f"\n--- 样本 {i+1} ---")
            print(f"Token数: {doc.metadata.get('token_count', 'N/A')}")
            print(f"来源: {doc.metadata.get('source_file', 'N/A')}")
            print(f"页码范围: {doc.metadata.get('page_range', 'N/A')}")

            print(f"标题:")
            if "h1" in doc.metadata:
                print(f"  h1: {doc.metadata['h1']}")
            if "h2" in doc.metadata and doc.metadata["h2"]:
                print(f"  h2: {doc.metadata['h2']}")
            if "h3" in doc.metadata and doc.metadata["h3"]:
                print(f"  h3: {doc.metadata['h3']}")

            print(f"\n内容预览（前600字符）:")
            print("-" * 40)
            content_preview = doc.page_content[:600]
            print(content_preview)
            if len(doc.page_content) > 600:
                print(f"... (共 {len(doc.page_content)} 字符)")
            print("-" * 40)

        # 统计信息
        total_tokens = sum(d.metadata.get('token_count', 0) for d in documents)
        print(f"\n统计信息:")
        print(f"  总文档数: {len(documents)}")
        print(f"  总token数: {total_tokens:,}")
        print(f"  平均token/文档: {total_tokens / len(documents):.0f}")

        # Token分布
        tokens = [d.metadata.get('token_count', 0) for d in documents]
        print(f"  最小token数: {min(tokens)}")
        print(f"  最大token数: {max(tokens)}")
        print(f"  超过800 tokens的chunk数: {sum(1 for t in tokens if t > 800)}")
        print("="*80 + "\n")

    def process_file(
        self,
        file_path: str,
        source_tag: str,
        page_range: str
    ) -> List[Document]:
        """处理单个文件"""
        print(f"\n{'='*60}")
        print(f"开始处理: {source_tag} ({page_range})")
        print(f"{'='*60}")

        content = self.load_markdown_file(file_path)
        docs = self.split_by_markdown_structure(content, source_tag, page_range)
        docs = self.enrich_document_context(docs)
        docs = self.split_large_chunks(docs)

        print(f"\n处理完成! 最终得到 {len(docs)} 个文档块")
        return docs


def main():
    """主入口"""
    SCRIPT_DIR = Path(__file__).parent
    PROJECT_ROOT = SCRIPT_DIR.parent
    sys.path.insert(0, str(PROJECT_ROOT))

    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        load_dotenv(env_file)
        print(f"已加载环境变量: {env_file}\n")

    config = IngestConfig()
    processor = MarkdownProcessor(config)

    all_documents = []

    # 处理part1
    docs_part1 = processor.process_file(
        file_path=config.md_file_part1,
        source_tag="part1",
        page_range="1-600"
    )
    all_documents.extend(docs_part1)

    # 处理part2
    docs_part2 = processor.process_file(
        file_path=config.md_file_part2,
        source_tag="part2",
        page_range="601-1054"
    )
    all_documents.extend(docs_part2)

    print(f"\n{'='*60}")
    print(f"两个文件处理完成，总计 {len(all_documents)} 个文档块")
    print(f"{'='*60}")

    # 预览样本
    processor.preview_samples(all_documents, num=2)


if __name__ == "__main__":
    main()
