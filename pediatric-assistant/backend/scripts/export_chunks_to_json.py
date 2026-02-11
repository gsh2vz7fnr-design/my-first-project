#!/usr/bin/env python3
"""
将过滤后的chunks导出为JSON文件，方便查看

用法:
    python scripts/export_chunks_to_json.py
"""
import os
import sys
import json
import re
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass, field, asdict

import tiktoken
from tqdm import tqdm
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
    md_file_part1: str = "/Users/zhang/Desktop/Claude/pediatric-assistant/knowledge_base/raw/《美国儿科学会育儿百科》1-600.md"
    md_file_part2: str = "/Users/zhang/Desktop/Claude/pediatric-assistant/knowledge_base/raw/《美国儿科学会育儿百科》601-1054.md"
    max_chunk_size: int = 800
    chunk_overlap: int = 100
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


class ChunkFilter:
    """Chunk过滤器 - 清理噪音内容"""

    BLACKLIST_KEYWORDS = [
        "ISBN", "Copyright", "版权所有", "印张", "开本", "字数",
        "责任编辑", "责任校对", "责任印制", "CIP数据", "著作权合同",
        "图书在版编目", "致谢", "致读者", "推荐序", "前言",
        "全球销量", "权威品牌", "译 者", "策划编辑", "图文制作",
        "出 版 人", "社 址", "邮政编码", "电话传真", "网 址",
        "印 刷", "版 次", "印 次", "升级修订", "电子检索",
        "谨以本书献给",
    ]

    BLACKLIST_H1 = [
        "升级修订", "美国儿科学会", "育儿百科", "第7版", "·第7版·",
        "目录", "新版新增", "电子检索功能", "推荐序", "致谢", "致读者",
        "前言", "第7版序", "谨以本书献给", "孩子给你的礼物",
        "你给孩子的礼物", '使"给予"成为家庭日常生活的一部分',
    ]

    H1_PREFIX_BLACKLIST = [
        "引言", "孩子给你的", "你给孩子的", "使",
        "培养孩子的韧性", "第一部分", "新版新增",
    ]

    def __init__(self):
        self.noise_pattern = re.compile(r'\$\textcircled\{[^}]*\}\$')
        self.page_number_pattern = re.compile(r'^[\s\s]*\d{1,4}\s*$', re.MULTILINE)

    def is_blacklisted_by_keyword(self, text: str) -> bool:
        text_lower = text.lower()
        for keyword in self.BLACKLIST_KEYWORDS:
            if keyword.lower() in text_lower:
                return True
        return False

    def is_blacklisted_by_title(self, h1: str, h2: str) -> bool:
        if h1 in self.BLACKLIST_H1:
            return True
        if h2 == "目录":
            return True
        for prefix in self.H1_PREFIX_BLACKLIST:
            if h1.startswith(prefix):
                return True
        return False

    def is_table_of_contents(self, text: str) -> bool:
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        if len(lines) < 5:
            return False
        avg_line_length = sum(len(line) for line in lines) / len(lines)
        if avg_line_length < 15:
            page_number_count = 0
            for line in lines:
                if self.page_number_pattern.match(line):
                    page_number_count += 1
                elif line.rstrip().isdigit() and len(line) < 5:
                    page_number_count += 1
            if page_number_count / len(lines) > 0.3:
                return True
        return False

    def is_low_density(self, text: str) -> bool:
        content = text
        if "【背景:" in content:
            content = content.split("】", 1)[-1] if "】" in content else content
        content = content.strip()
        if len(content) < 50:
            has_punctuation = any(c in content for c in '。，！？；：、,.!?;:')
            if not has_punctuation:
                return True
        if content.startswith("![image](") and len(content) < 200:
            remaining = content.replace("![image](", "").replace(")", "")
            remaining = remaining.replace("http://", "").replace("https://", "")
            if len(remaining.strip()) < 50:
                return True
        return False

    def is_copyright_or_meta(self, text: str) -> bool:
        copyright_patterns = [r'©\s*\d{4}', r'著作权合同', r'ISBN\s*\d', r'书名原文']
        for pattern in copyright_patterns:
            if re.search(pattern, text):
                return True
        return False

    def clean_noise_symbols(self, text: str) -> str:
        text = self.noise_pattern.sub('', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def should_keep(self, doc: Document) -> bool:
        content = doc.page_content
        h1 = doc.metadata.get('h1', '')
        h2 = doc.metadata.get('h2', '')
        if self.is_blacklisted_by_title(h1, h2):
            return False
        if self.is_blacklisted_by_keyword(content):
            return False
        if self.is_table_of_contents(content):
            return False
        if self.is_low_density(content):
            return False
        if self.is_copyright_or_meta(content):
            return False
        return True

    def filter_documents(self, documents: List[Document]) -> List[Document]:
        filtered_docs = []
        dropped_count = 0
        drop_reasons = {
            "title_blacklist": 0, "keyword_blacklist": 0,
            "table_of_contents": 0, "low_density": 0, "copyright_meta": 0,
        }
        for doc in tqdm(documents, desc="过滤噪音"):
            content = doc.page_content
            h1 = doc.metadata.get('h1', '')
            h2 = doc.metadata.get('h2', '')
            if self.is_blacklisted_by_title(h1, h2):
                drop_reasons["title_blacklist"] += 1
                dropped_count += 1
                continue
            if self.is_blacklisted_by_keyword(content):
                drop_reasons["keyword_blacklist"] += 1
                dropped_count += 1
                continue
            if self.is_table_of_contents(content):
                drop_reasons["table_of_contents"] += 1
                dropped_count += 1
                continue
            if self.is_low_density(content):
                drop_reasons["low_density"] += 1
                dropped_count += 1
                continue
            if self.is_copyright_or_meta(content):
                drop_reasons["copyright_meta"] += 1
                dropped_count += 1
                continue
            doc.page_content = self.clean_noise_symbols(content)
            filtered_docs.append(doc)
        print(f"\n过滤统计: 原始 {len(documents)} -> 保留 {len(filtered_docs)}")
        for reason, count in drop_reasons.items():
            if count > 0:
                print(f"  - {reason}: {count}")
        return filtered_docs


class MarkdownProcessor:
    """Markdown处理器"""

    def __init__(self, config: IngestConfig):
        self.config = config
        self.token_counter = TokenCounter()

    def load_markdown_file(self, file_path: str) -> str:
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")
        print(f"读取文件: {file_path}")
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
        print("\n执行Markdown结构切片...")
        markdown_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=self.config.markdown_headers,
            strip_headers=False
        )
        docs = markdown_splitter.split_text(content)
        print(f"  切片后得到 {len(docs)} 个文档块")
        for doc in docs:
            doc.metadata["source_file"] = source_tag
            doc.metadata["page_range"] = page_range
        return docs

    def enrich_document_context(self, documents: List[Document]) -> List[Document]:
        print("\n执行上下文增强...")
        enriched_docs = []
        for doc in tqdm(documents, desc="上下文增强"):
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
        print(f"\n检查并切分超过 {self.config.max_chunk_size} tokens的chunk...")
        recursive_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.config.max_chunk_size,
            chunk_overlap=self.config.chunk_overlap,
            length_function=self.token_counter.count_tokens,
            separators=["\n\n\n", "\n\n", "\n", "。", "！", "？", " ", ""]
        )
        final_docs = []
        split_count = 0
        for doc in tqdm(documents, desc="二次切分"):
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

    def process_file(
        self,
        file_path: str,
        source_tag: str,
        page_range: str,
        apply_filter: bool = True
    ) -> List[Document]:
        print(f"\n{'='*60}")
        print(f"开始处理: {source_tag} ({page_range})")
        print(f"{'='*60}")
        content = self.load_markdown_file(file_path)
        docs = self.split_by_markdown_structure(content, source_tag, page_range)
        docs = self.enrich_document_context(docs)
        docs = self.split_large_chunks(docs)
        if apply_filter:
            chunk_filter = ChunkFilter()
            docs = chunk_filter.filter_documents(docs)
        print(f"\n处理完成! 最终得到 {len(docs)} 个文档块")
        return docs


def document_to_dict(doc: Document) -> dict:
    """将LangChain Document转换为可序列化的dict"""
    return {
        "content": doc.page_content,
        "metadata": {
            "h1": doc.metadata.get("h1", ""),
            "h2": doc.metadata.get("h2", ""),
            "h3": doc.metadata.get("h3", ""),
            "source_file": doc.metadata.get("source_file", ""),
            "page_range": doc.metadata.get("page_range", ""),
            "token_count": doc.metadata.get("token_count", 0),
        }
    }


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

    # 转换为字典列表
    chunks_data = [document_to_dict(doc) for doc in all_documents]

    # 添加统计信息
    stats = {
        "total_chunks": len(chunks_data),
        "total_tokens": sum(c["metadata"]["token_count"] for c in chunks_data),
        "avg_tokens": sum(c["metadata"]["token_count"] for c in chunks_data) / len(chunks_data) if chunks_data else 0,
        "min_tokens": min(c["metadata"]["token_count"] for c in chunks_data) if chunks_data else 0,
        "max_tokens": max(c["metadata"]["token_count"] for c in chunks_data) if chunks_data else 0,
    }

    # 输出文件
    output_file = PROJECT_ROOT / "chunks_filtered.json"
    print(f"\n正在保存到: {output_file}")

    output_data = {
        "statistics": stats,
        "chunks": chunks_data
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"✓ 保存完成!")
    print(f"\n统计信息:")
    print(f"  总chunk数: {stats['total_chunks']}")
    print(f"  总token数: {stats['total_tokens']:,}")
    print(f"  平均token/chunk: {stats['avg_tokens']:.0f}")
    print(f"  最小token数: {stats['min_tokens']}")
    print(f"  最大token数: {stats['max_tokens']}")


if __name__ == "__main__":
    main()
