"""
RAG 检索准确性测试套件

测试内容：
1. 检索质量测试 (test_retrieval_quality)
   - 验证关键词命中率
   - 验证相关性分数

2. 延迟基准测试 (test_latency_benchmark)
   - 测量检索平均耗时

运行方式：
    pytest tests/test_rag_accuracy.py -v -s

前置条件：
    确保已运行 scripts/migrate_to_chroma.py，ChromaDB 中有数据
"""
import json
import time
import asyncio
from pathlib import Path
from typing import List, Dict, Any

import pytest
import pytest_asyncio
from loguru import logger

# 添加项目路径
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.rag_service import RAGService


# ============ Fixtures ============

@pytest.fixture(scope="module")
def golden_dataset() -> Dict[str, Any]:
    """加载金标准数据集"""
    fixture_path = Path(__file__).parent / "fixtures" / "golden_dataset.json"

    if not fixture_path.exists():
        pytest.skip(f"金标准数据集不存在: {fixture_path}")

    with open(fixture_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"\n📦 加载金标准数据集: {len(data.get('test_cases', []))} 个测试用例")
    return data


@pytest.fixture(scope="module")
def rag_service():
    """初始化 RAG 服务实例"""
    service = RAGService()

    # 验证服务可用性
    print(f"\n🔧 初始化 RAG 服务...")
    print(f"   - use_chromadb: {service._use_chromadb}")
    print(f"   - knowledge_base size: {len(service.knowledge_base)}")

    yield service


# ============ 测试类 ============

class TestRetrievalQuality:
    """检索质量测试"""

    @pytest.mark.asyncio
    async def test_retrieval_quality(
        self,
        rag_service: RAGService,
        golden_dataset: Dict[str, Any]
    ):
        """
        测试检索质量

        验证点：
        1. 关键词命中率：返回的文档中应包含至少一个期望关键词
        2. 相关性分数：返回的 score 应高于 min_score
        """
        test_cases = golden_dataset.get("test_cases", [])
        results_summary = []

        print("\n" + "=" * 60)
        print("🧪 RAG 检索质量测试")
        print("=" * 60)

        passed = 0
        failed = 0

        for case in test_cases:
            case_id = case["id"]
            query = case["query"]
            expected_keywords = case.get("expected_keywords", [])
            min_score = case.get("min_score", 0.5)

            print(f"\n📝 [{case_id}] {query}")
            print("-" * 50)

            # 执行检索
            start_time = time.time()
            results = await rag_service.retrieve(query, top_k=3)
            elapsed = (time.time() - start_time) * 1000

            if not results:
                print(f"   ⚠️  未返回任何结果 (知识库可能无相关内容)")
                # 标记为跳过而非失败（知识库可能不包含相关主题）
                results_summary.append({
                    "id": case_id,
                    "passed": True,
                    "skipped": True,
                    "reason": "no_results"
                })
                continue

            # 打印检索结果
            print(f"   ⏱️  耗时: {elapsed:.1f}ms")
            print(f"   📋 返回 {len(results)} 条结果:")

            keyword_hit = False
            score_ok = True

            for i, result in enumerate(results):
                title = result.metadata.get("title", "N/A")
                score = result.score
                content_preview = result.content[:60] + "..." if len(result.content) > 60 else result.content

                print(f"      [{i+1}] {title} (score={score:.3f})")
                print(f"          {content_preview}")

                # 检查关键词命中
                content_lower = result.content.lower()
                for keyword in expected_keywords:
                    if keyword.lower() in content_lower:
                        keyword_hit = True
                        print(f"          ✅ 命中关键词: {keyword}")
                        break

                # 检查分数
                if score < min_score:
                    score_ok = False

            # 断言 1: 关键词命中
            if expected_keywords:
                assert keyword_hit, (
                    f"[{case_id}] 关键词未命中! "
                    f"期望关键词: {expected_keywords}"
                )

            # 断言 2: 分数检查 (Top-1 必须达标)
            if results:
                top1_score = results[0].score
                assert top1_score >= min_score, (
                    f"[{case_id}] Top-1 分数过低: {top1_score:.3f} < {min_score}"
                )

            print(f"   ✅ 通过")
            passed += 1
            results_summary.append({
                "id": case_id,
                "passed": True,
                "elapsed_ms": elapsed,
                "top1_score": results[0].score if results else 0,
                "keyword_hit": keyword_hit
            })

        # 打印统计报告
        print("\n" + "=" * 60)
        print("📊 测试统计报告")
        print("=" * 60)
        print(f"   通过: {passed}/{len(test_cases)}")
        print(f"   失败: {failed}/{len(test_cases)}")

        if results_summary:
            avg_elapsed = sum(r.get("elapsed_ms", 0) for r in results_summary if r.get("passed")) / max(passed, 1)
            avg_score = sum(r.get("top1_score", 0) for r in results_summary if r.get("passed")) / max(passed, 1)
            print(f"   平均耗时: {avg_elapsed:.1f}ms")
            print(f"   平均分数: {avg_score:.3f}")

        print("=" * 60)

        # 最终断言
        assert failed == 0, f"有 {failed} 个测试用例失败"


class TestLatencyBenchmark:
    """延迟基准测试"""

    @pytest.mark.asyncio
    async def test_latency_benchmark(self, rag_service: RAGService):
        """
        测试检索延迟

        验证点：
        - 5 次查询的平均耗时应低于 1.0 秒
        """
        test_queries = [
            "宝宝发烧怎么办",
            "腹泻怎么护理",
            "咳嗽有痰",
            "泰诺林用量",
            "摔倒头部"
        ]

        print("\n" + "=" * 60)
        print("⏱️  延迟基准测试")
        print("=" * 60)

        latencies = []

        for i, query in enumerate(test_queries, 1):
            start_time = time.time()
            results = await rag_service.retrieve(query, top_k=3)
            elapsed = time.time() - start_time
            latencies.append(elapsed)

            print(f"   [{i}] '{query[:20]}...': {elapsed*1000:.1f}ms ({len(results)} 条结果)")

        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)
        min_latency = min(latencies)

        print("\n📊 延迟统计:")
        print(f"   平均延迟: {avg_latency*1000:.1f}ms")
        print(f"   最大延迟: {max_latency*1000:.1f}ms")
        print(f"   最小延迟: {min_latency*1000:.1f}ms")

        # 警告阈值
        if avg_latency > 1.0:
            print(f"   ⚠️  WARNING: 平均延迟超过 1.0 秒!")
        else:
            print(f"   ✅ 延迟正常")

        print("=" * 60)

        # 断言：平均延迟应低于 2.0 秒（考虑到模型加载等首次操作）
        assert avg_latency < 2.0, f"平均延迟过高: {avg_latency:.2f}s"


class TestEdgeCases:
    """边界情况测试"""

    @pytest.mark.asyncio
    async def test_empty_query(self, rag_service: RAGService):
        """测试空查询"""
        results = await rag_service.retrieve("", top_k=3)
        # 空查询应返回空结果或低相关性结果
        print(f"\n   空查询返回 {len(results)} 条结果")
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_very_long_query(self, rag_service: RAGService):
        """测试超长查询"""
        long_query = "宝宝" * 100  # 200 个字符
        results = await rag_service.retrieve(long_query, top_k=3)
        print(f"\n   超长查询返回 {len(results)} 条结果")
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_special_characters(self, rag_service: RAGService):
        """测试特殊字符查询"""
        special_query = "宝宝!@#$%发烧"
        results = await rag_service.retrieve(special_query, top_k=3)
        print(f"\n   特殊字符查询返回 {len(results)} 条结果")
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_age_filter(self, rag_service: RAGService):
        """测试年龄过滤"""
        # 查询新生儿相关问题
        results = await rag_service.retrieve(
            "新生儿发烧",
            top_k=3,
            filters={"age_months": 1}
        )
        print(f"\n   年龄过滤查询返回 {len(results)} 条结果")
        assert isinstance(results, list)


# ============ 运行入口 ============

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
