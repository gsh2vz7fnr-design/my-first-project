#!/usr/bin/env python3
"""
查看切分结果 - 将样本输出到文件

用法:
    python scripts/show_chunks.py
"""
import os
import sys
from pathlib import Path

# 添加项目路径
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.test_ingest_preview import IngestConfig, MarkdownProcessor

def main():
    config = IngestConfig()
    processor = MarkdownProcessor(config)

    # 处理文件
    all_documents = []

    docs_part1 = processor.process_file(
        file_path=config.md_file_part1,
        source_tag="part1",
        page_range="1-600"
    )
    all_documents.extend(docs_part1)

    docs_part2 = processor.process_file(
        file_path=config.md_file_part2,
        source_tag="part2",
        page_range="601-1054"
    )
    all_documents.extend(docs_part2)

    # 输出文件
    output_file = PROJECT_ROOT / "chunks_output.txt"

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("="*80 + "\n")
        f.write("知识库切分结果预览\n")
        f.write("="*80 + "\n\n")

        f.write(f"总文档数: {len(all_documents)}\n")

        tokens_list = [d.metadata.get('token_count', 0) for d in all_documents]
        f.write(f"总token数: {sum(tokens_list):,}\n")
        f.write(f"平均token/文档: {sum(tokens_list) / len(all_documents):.0f}\n")
        f.write(f"最小token数: {min(tokens_list)}\n")
        f.write(f"最大token数: {max(tokens_list)}\n\n")

        # 写入前50个样本
        f.write("="*80 + "\n")
        f.write("前50个样本详情\n")
        f.write("="*80 + "\n\n")

        for i, doc in enumerate(all_documents[:50]):
            f.write("-"*80 + "\n")
            f.write(f"样本 #{i+1}\n")
            f.write(f"Token数: {doc.metadata.get('token_count', 'N/A')}\n")
            f.write(f"来源: {doc.metadata.get('source_file', 'N/A')}\n")
            f.write(f"页码: {doc.metadata.get('page_range', 'N/A')}\n")

            if "h1" in doc.metadata:
                f.write(f"h1: {doc.metadata['h1']}\n")
            if "h2" in doc.metadata and doc.metadata["h2"]:
                f.write(f"h2: {doc.metadata['h2']}\n")
            if "h3" in doc.metadata and doc.metadata["h3"]:
                f.write(f"h3: {doc.metadata['h3']}\n")

            f.write("\n内容:\n")
            f.write(doc.page_content[:1500])
            if len(doc.page_content) > 1500:
                f.write(f"... (共 {len(doc.page_content)} 字符)")
            f.write("\n\n")

        # 写入按token数排序的样本
        f.write("\n" + "="*80 + "\n")
        f.write("Token数最多的20个样本\n")
        f.write("="*80 + "\n\n")

        sorted_docs = sorted(all_documents, key=lambda d: d.metadata.get('token_count', 0), reverse=True)
        for i, doc in enumerate(sorted_docs[:20]):
            h1 = doc.metadata.get('h1', '')[:30]
            h2 = doc.metadata.get('h2', '')[:30] if doc.metadata.get('h2') else ''
            f.write(f"{i+1}. Token: {doc.metadata.get('token_count', 0)} | h1: {h1} | h2: {h2}\n")

    print(f"\n结果已保存到: {output_file}")
    print(f"总共 {len(all_documents)} 个文档块")


if __name__ == "__main__":
    main()
