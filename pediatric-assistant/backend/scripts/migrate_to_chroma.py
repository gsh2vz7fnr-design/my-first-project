#!/usr/bin/env python3
"""
数据迁移脚本 - 将 JSON 知识库迁移到 ChromaDB

功能：
1. 读取 backend/data/knowledge_base/ 目录下的所有 JSON 文件
2. 转换为统一的 Document 对象
3. 批量写入 ChromaDB
4. 支持断点续传、重置和验证

用法：
    # 基本用法（增量迁移）
    python scripts/migrate_to_chroma.py

    # 重置并迁移（清空旧数据）
    python scripts/migrate_to_chroma.py --reset

    # 验证模式（不写入，只检查数据）
    python scripts/migrate_to_chroma.py --dry-run

    # 迁移并验证
    python scripts/migrate_to_chroma.py --verify

    # 从中断处继续
    python scripts/migrate_to_chroma.py --resume

    # 自定义批次大小
    python scripts/migrate_to_chroma.py --batch-size 50

选项：
    --dry-run       仅验证数据，不实际写入
    --reset         迁移前清空旧的 Collection
    --verify        迁移完成后随机抽取 5 条数据验证
    --resume        从上次中断处继续（断点续传）
    --batch-size    自定义批次大小（默认 100）
"""
import argparse
import asyncio
import json
import logging
import random
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Set

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 检查 tqdm 是否安装
try:
    from tqdm import tqdm
except ImportError:
    print("错误: 需要安装 tqdm 库")
    print("请运行: pip install tqdm")
    sys.exit(1)

from app.config import settings
from app.services.vector_store import (
    ChromaStore,
    Document,
    VectorStoreError
)


# 配置错误日志
def setup_error_logger(log_file: str = "migration_errors.log") -> logging.Logger:
    """设置错误日志记录器"""
    logger = logging.getLogger("migration_errors")
    logger.setLevel(logging.ERROR)

    # 文件处理器
    fh = logging.FileHandler(log_file, encoding='utf-8')
    fh.setLevel(logging.ERROR)

    # 格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    fh.setFormatter(formatter)

    logger.addHandler(fh)
    return logger


error_logger = setup_error_logger()


class MigrationState:
    """迁移状态管理（支持断点续传）"""

    def __init__(self, state_file: Path):
        self.state_file = state_file
        self.migrated_files: Set[str] = set()
        self.migrated_ids: Set[str] = set()
        self._load()

    def _load(self) -> None:
        """加载状态"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.migrated_files = set(data.get('files', []))
                    self.migrated_ids = set(data.get('ids', []))
                print(f"加载迁移状态: {len(self.migrated_files)} 个文件, {len(self.migrated_ids)} 条记录")
            except Exception as e:
                print(f"警告: 加载状态文件失败: {e}")

    def save(self) -> None:
        """保存状态"""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump({
                'files': list(self.migrated_files),
                'ids': list(self.migrated_ids),
                'updated_at': datetime.now().isoformat()
            }, f, ensure_ascii=False, indent=2)

    def mark_file_done(self, filename: str) -> None:
        """标记文件已完成"""
        self.migrated_files.add(filename)

    def is_file_done(self, filename: str) -> bool:
        """检查文件是否已完成"""
        return filename in self.migrated_files

    def add_ids(self, ids: List[str]) -> None:
        """添加已迁移的 ID"""
        self.migrated_ids.update(ids)

    def clear(self) -> None:
        """清除状态"""
        self.migrated_files.clear()
        self.migrated_ids.clear()
        if self.state_file.exists():
            self.state_file.unlink()


class KnowledgeBaseMigrator:
    """知识库迁移器"""

    # Embedding 失败重试配置
    MAX_RETRIES = 3
    RETRY_DELAY = 2.0  # 秒

    def __init__(
        self,
        knowledge_base_path: Path,
        persist_directory: Path,
        collection_name: str = "pediatric_knowledge_base",
        batch_size: int = 100,
        dry_run: bool = False,
        resume: bool = False,
        reset: bool = False
    ):
        self.knowledge_base_path = knowledge_base_path
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        self.batch_size = batch_size
        self.dry_run = dry_run
        self.reset = reset

        # 状态文件
        self.state = MigrationState(
            persist_directory / ".migration_state.json"
        ) if resume else None

        # 如果是重置模式，清除状态
        if reset and self.state:
            self.state.clear()

        # 统计信息
        self.stats = {
            'total_files': 0,
            'total_entries': 0,
            'migrated_entries': 0,
            'skipped_entries': 0,
            'failed_entries': 0,
            'retry_count': 0,
            'start_time': None,
            'end_time': None
        }

        # 存储所有文档 ID（用于验证）
        self._all_doc_ids: List[str] = []

        # 向量存储（延迟初始化）
        self._store: Optional[ChromaStore] = None

    async def _get_store(self) -> ChromaStore:
        """获取向量存储实例"""
        if self._store is None:
            self._store = ChromaStore(
                collection_name=self.collection_name,
                persist_directory=str(self.persist_directory),
            )
            await self._store._ensure_initialized()
        return self._store

    def _load_json_file(self, filepath: Path) -> List[Dict[str, Any]]:
        """
        加载单个 JSON 文件

        Args:
            filepath: JSON 文件路径

        Returns:
            List[Dict]: 条目列表

        Raises:
            json.JSONDecodeError: JSON 解析错误
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        entries = []
        file_topic = data.get('topic', '')
        file_category = data.get('category', '')
        file_source = data.get('source', '')

        for entry in data.get('entries', []):
            # 合并文件级别的元数据
            enriched_entry = {
                **entry,
                'topic': entry.get('topic') or file_topic,
                'category': entry.get('category') or file_category,
                'source': entry.get('source') or file_source,
            }
            entries.append(enriched_entry)

        return entries

    def _entry_to_document(self, entry: Dict[str, Any]) -> Optional[Document]:
        """
        将知识库条目转换为 Document 对象

        Args:
            entry: 知识库条目

        Returns:
            Document: 文档对象，转换失败返回 None
        """
        try:
            # 构建元数据（按 Schema 要求）
            metadata = {
                'id': entry.get('id', ''),
                'title': entry.get('title', ''),
                'source': entry.get('source', ''),
                'topic': entry.get('topic', ''),
                'category': entry.get('category', ''),
                'alert_level': entry.get('alert_level', ''),
                'tags': ','.join(entry.get('tags', [])) if isinstance(entry.get('tags'), list) else (entry.get('tags', '') or ''),
                'h1': entry.get('h1', ''),
                'h2': entry.get('h2', ''),
                'source_file': entry.get('source_file', ''),
                'page_range': entry.get('page_range', ''),
                'token_count': entry.get('token_count', 0),
            }

            # 处理年龄范围（转换为数值便于过滤）
            age_range = entry.get('age_range', '')
            if age_range:
                try:
                    if '-' in str(age_range) and '个月' in str(age_range):
                        parts = str(age_range).replace('个月', '').split('-')
                        metadata['age_range_min'] = int(parts[0])
                        metadata['age_range_max'] = int(parts[1])
                        metadata['age_range'] = age_range  # 保留原始字符串
                except (ValueError, IndexError) as e:
                    error_logger.error(f"解析年龄范围失败: {age_range}, error: {e}")

            content = entry.get('content', '')
            if not content:
                error_logger.error(f"文档内容为空: {entry.get('id', 'unknown')}")
                return None

            return Document(
                id=entry.get('id', f"auto_{hash(content) % 10000000}"),
                content=content,
                metadata=metadata
            )

        except Exception as e:
            error_logger.error(f"转换文档失败: {entry.get('id', 'unknown')}, error: {e}")
            return None

    async def _add_documents_with_retry(
        self,
        store: ChromaStore,
        documents: List[Document]
    ) -> int:
        """
        带重试机制的批量添加文档

        Args:
            store: 向量存储实例
            documents: 文档列表

        Returns:
            int: 成功添加的文档数量
        """
        last_error = None

        for attempt in range(self.MAX_RETRIES):
            try:
                count = await store.add_documents(documents)
                return count

            except VectorStoreError as e:
                last_error = e
                self.stats['retry_count'] += 1

                if attempt < self.MAX_RETRIES - 1:
                    wait_time = self.RETRY_DELAY * (2 ** attempt)  # 指数退避
                    error_logger.error(
                        f"批量写入失败 (尝试 {attempt + 1}/{self.MAX_RETRIES}), "
                        f"{wait_time}s 后重试: {e}"
                    )
                    print(f"\n⚠️ 写入失败，{wait_time}s 后重试 ({attempt + 1}/{self.MAX_RETRIES})...")
                    await asyncio.sleep(wait_time)
                else:
                    error_logger.error(f"批量写入最终失败: {e}")

        # 所有重试都失败了
        print(f"\n❌ 批次写入失败（已重试 {self.MAX_RETRIES} 次）: {last_error}")
        return 0

    async def migrate(self) -> bool:
        """
        执行迁移

        Returns:
            bool: 迁移是否成功
        """
        self.stats['start_time'] = time.time()

        # 1. 收集所有 JSON 文件
        json_files = list(self.knowledge_base_path.glob('*.json'))
        self.stats['total_files'] = len(json_files)

        if not json_files:
            print(f"错误: 未找到 JSON 文件 ({self.knowledge_base_path})")
            return False

        print("ChromaDB 数据迁移脚本")
        print("=" * 50)
        print(f"知识库路径:   {self.knowledge_base_path}")
        print(f"持久化目录:   {self.persist_directory}")
        print(f"集合名称:     {self.collection_name}")
        print(f"找到文件:     {len(json_files)} 个")
        print(f"批次大小:     {self.batch_size}")
        print(f"模式:         {'验证模式 (dry-run)' if self.dry_run else '迁移模式'}")
        if self.state:
            print(f"断点续传:     启用")
        print("=" * 50)
        print()

        # 2. 初始化向量存储
        if not self.dry_run:
            store = await self._get_store()
            print(f"向量存储初始化完成")
            print(f"当前文档数: {store.count}")

            # 重置模式：清空旧 Collection
            if self.reset:
                print("\n🗑️  重置模式：清空旧 Collection...")
                await store.delete_collection()
                # 重新初始化
                self._store = None
                store = await self._get_store()
                print(f"Collection 已重置，当前文档数: {store.count}")

            print()

        # 3. 遍历文件，解析文档
        all_documents: List[Document] = []
        parse_errors: int = 0

        for json_file in tqdm(json_files, desc="📂 读取文件"):
            # 检查是否已迁移（断点续传）
            if self.state and self.state.is_file_done(json_file.name):
                continue

            try:
                entries = self._load_json_file(json_file)
                self.stats['total_entries'] += len(entries)

                for entry in entries:
                    doc = self._entry_to_document(entry)
                    if doc:
                        all_documents.append(doc)
                        self._all_doc_ids.append(doc.id)
                    else:
                        parse_errors += 1
                        self.stats['failed_entries'] += 1

                # 标记文件已读取
                if self.state:
                    self.state.mark_file_done(json_file.name)

            except json.JSONDecodeError as e:
                parse_errors += 1
                error_logger.error(f"JSON 解析错误 ({json_file.name}): {e}")
            except Exception as e:
                parse_errors += 1
                error_logger.error(f"文件读取错误 ({json_file.name}): {e}")

        if parse_errors > 0:
            print(f"\n⚠️  解析过程中发现 {parse_errors} 个错误，已记录到 migration_errors.log")

        print(f"\n📋 共解析 {len(all_documents)} 个有效文档")

        # 4. dry-run 模式：显示样例后退出
        if self.dry_run:
            print("\n📝 数据样例 (前 3 条):")
            print("-" * 50)
            for i, doc in enumerate(all_documents[:3], 1):
                print(f"\n文档 {i}:")
                print(f"  ID: {doc.id}")
                print(f"  标题: {doc.metadata.get('title', 'N/A')}")
                print(f"  分类: {doc.metadata.get('category', 'N/A')}")
                print(f"  内容: {doc.content[:100]}...")
                print(f"  元数据: {list(doc.metadata.keys())}")

            print("\n✅ 验证模式完成，数据格式正确！")
            self.stats['end_time'] = time.time()
            self._print_summary()
            return True

        # 5. 批量写入
        if not all_documents:
            print("⚠️  没有需要迁移的文档")
            return True

        store = await self._get_store()

        # 分批
        batches = [
            all_documents[i:i + self.batch_size]
            for i in range(0, len(all_documents), self.batch_size)
        ]

        print(f"\n🚀 开始写入 {len(batches)} 个批次...")
        print()

        with tqdm(total=len(all_documents), desc="📝 写入文档", unit="条") as pbar:
            for batch_idx, batch in enumerate(batches, 1):
                count = await self._add_documents_with_retry(store, batch)

                if count > 0:
                    self.stats['migrated_entries'] += count
                    pbar.update(len(batch))

                    # 更新状态（断点续传）
                    if self.state:
                        self.state.add_ids([doc.id for doc in batch])
                        # 每 5 个批次保存一次
                        if batch_idx % 5 == 0:
                            self.state.save()
                else:
                    self.stats['failed_entries'] += len(batch)
                    pbar.update(len(batch))  # 即使失败也更新进度条

        # 最终保存状态
        if self.state:
            self.state.save()

        self.stats['end_time'] = time.time()

        # 6. 打印统计
        self._print_summary()

        return self.stats['failed_entries'] == 0

    async def verify(self, sample_size: int = 5) -> bool:
        """
        验证迁移结果（随机抽取样本）

        Args:
            sample_size: 抽样数量

        Returns:
            bool: 验证是否通过
        """
        store = await self._get_store()

        print(f"\n🔍 验证迁移结果...")
        print(f"总文档数: {store.count}")
        print()

        all_passed = True

        # 1. 随机抽取 ID 验证（如果有记录）
        if self._all_doc_ids and len(self._all_doc_ids) >= sample_size:
            sample_ids = random.sample(self._all_doc_ids, sample_size)

            print(f"📋 随机抽样验证 ({sample_size} 条):")
            print("-" * 40)

            for i, doc_id in enumerate(sample_ids, 1):
                doc = await store.get_document_by_id(doc_id)
                if doc:
                    print(f"  ✅ [{i}] ID: {doc_id}")
                    print(f"      标题: {doc.metadata.get('title', 'N/A')[:30]}...")
                else:
                    print(f"  ❌ [{i}] ID: {doc_id} - 未找到")
                    all_passed = False
                    error_logger.error(f"验证失败: 文档 {doc_id} 未找到")

        print()

        # 2. 搜索功能验证
        print("🔎 搜索功能验证:")
        print("-" * 40)

        test_queries = [
            "发烧怎么办",
            "腹泻",
            "咳嗽",
            "泰诺林",
            "美林",
        ]

        for query in test_queries:
            try:
                results = await store.search(query, top_k=3)
                if results:
                    top_score = results[0].score
                    print(f"  ✅ '{query}': {len(results)} 条结果 (Top-1 score: {top_score:.3f})")
                else:
                    print(f"  ⚠️  '{query}': 无结果")
            except Exception as e:
                print(f"  ❌ '{query}': 失败 - {e}")
                all_passed = False
                error_logger.error(f"搜索验证失败: {query}, error: {e}")

        return all_passed

    def _print_summary(self) -> None:
        """打印迁移摘要"""
        duration = self.stats['end_time'] - self.stats['start_time']

        print("\n" + "=" * 50)
        print("📊 迁移摘要")
        print("=" * 50)
        print(f"总文件数:       {self.stats['total_files']}")
        print(f"总条目数:       {self.stats['total_entries']}")
        print(f"已迁移:         {self.stats['migrated_entries']}")
        print(f"跳过:           {self.stats['skipped_entries']}")
        print(f"失败:           {self.stats['failed_entries']}")
        print(f"重试次数:       {self.stats['retry_count']}")
        print("-" * 50)
        print(f"耗时:           {duration:.2f} 秒")
        if duration > 0 and self.stats['migrated_entries'] > 0:
            rate = self.stats['migrated_entries'] / duration
            print(f"速率:           {rate:.1f} 条/秒")
        print("=" * 50)


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='将 JSON 知识库迁移到 ChromaDB',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/migrate_to_chroma.py                    # 基本迁移
  python scripts/migrate_to_chroma.py --reset            # 重置并迁移
  python scripts/migrate_to_chroma.py --dry-run          # 验证模式
  python scripts/migrate_to_chroma.py --verify           # 迁移并验证
  python scripts/migrate_to_chroma.py --resume           # 断点续传
        """
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='仅验证数据，不实际写入'
    )
    parser.add_argument(
        '--reset',
        action='store_true',
        help='迁移前清空旧的 Collection'
    )
    parser.add_argument(
        '--verify',
        action='store_true',
        help='迁移完成后随机抽取 5 条数据验证'
    )
    parser.add_argument(
        '--resume',
        action='store_true',
        help='从上次中断处继续（断点续传）'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=100,
        help='批次大小（默认 100）'
    )
    parser.add_argument(
        '--knowledge-base',
        type=str,
        default=None,
        help='知识库路径（默认使用配置）'
    )
    parser.add_argument(
        '--persist-dir',
        type=str,
        default=None,
        help='持久化目录（默认使用配置）'
    )

    args = parser.parse_args()

    # 确定路径
    backend_dir = Path(__file__).parent.parent
    knowledge_base_path = Path(args.knowledge_base) if args.knowledge_base else Path(settings.KNOWLEDGE_BASE_PATH)
    persist_dir = Path(args.persist_dir) if args.persist_dir else Path(settings.VECTOR_DB_PATH)

    # 检查知识库路径
    if not knowledge_base_path.exists():
        print(f"❌ 错误: 知识库路径不存在: {knowledge_base_path}")
        sys.exit(1)

    # 创建迁移器
    migrator = KnowledgeBaseMigrator(
        knowledge_base_path=knowledge_base_path,
        persist_directory=persist_dir,
        collection_name="pediatric_knowledge_base",
        batch_size=args.batch_size,
        dry_run=args.dry_run,
        resume=args.resume,
        reset=args.reset
    )

    # 执行迁移
    success = await migrator.migrate()

    # 验证
    if args.verify and success and not args.dry_run:
        verify_success = await migrator.verify()
        if not verify_success:
            print("\n⚠️  验证发现问题，请检查 migration_errors.log")
            sys.exit(1)

    if success:
        print("\n✅ 迁移完成!")
    else:
        print("\n❌ 迁移过程中出现错误，请检查 migration_errors.log")
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
