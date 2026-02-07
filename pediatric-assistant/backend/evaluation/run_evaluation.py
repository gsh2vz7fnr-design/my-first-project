"""
自动化评估脚本 - 批量运行测试用例并生成报告

Usage:
    python evaluation/run_evaluation.py --test-file app/data/test_cases.json --output-file evaluation_report.json
    python evaluation/run_evaluation.py --test-file app/data/test_cases.json --concurrent 5
"""
import argparse
import asyncio
import json
from pathlib import Path
from datetime import datetime
from typing import List, Optional
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pydantic import BaseModel
from httpx import AsyncClient, TimeoutException


# ============================================
# Data Models
# ============================================

class EvaluationResult(BaseModel):
    """单个测试用例的评估结果"""
    test_case_id: str
    category: str
    passed: bool
    actual_intent: Optional[str] = None
    actual_triage_level: Optional[str] = None
    has_required_keywords: bool = True
    response_snippet: Optional[str] = None
    error_message: Optional[str] = None


class EvaluationReport(BaseModel):
    """评估报告"""
    timestamp: str
    total_cases: int
    passed_cases: int
    failed_cases: int
    total_pass_rate: float
    emergency_recall_rate: float  # 急症召回率
    refusal_accuracy: float  # 拒答准确率
    category_pass_rates: dict
    failed_test_cases: List[dict]


# ============================================
# Evaluation Functions
# ============================================

async def run_single_test(
    test_case: dict,
    api_base: str = "http://localhost:8000",
    client: Optional[AsyncClient] = None
) -> EvaluationResult:
    """
    运行单个测试用例

    Args:
        test_case: 测试用例字典
        api_base: API基础URL
        client: HTTP客户端（可选）

    Returns:
        EvaluationResult: 评估结果
    """
    test_id = test_case.get("id", "unknown")
    category = test_case.get("category", "unknown")
    input_text = test_case.get("input", "")
    expected = test_case.get("expected", {})

    # 如果需要，创建客户端
    should_close = False
    if client is None:
        client = AsyncClient(timeout=30.0)
        should_close = True

    try:
        # 发送请求到流式接口
        response = await client.post(
            f"{api_base}/api/v1/chat/stream",
            json={
                "user_id": "test_user",
                "conversation_id": f"test_{test_id}",
                "message": input_text
            }
        )

        if response.status_code != 200:
            return EvaluationResult(
                test_case_id=test_id,
                category=category,
                passed=False,
                error_message=f"HTTP {response.status_code}: {response.text[:200]}"
            )

        # 解析流式响应
        content = ""
        metadata = {}
        lines = response.text.strip().split("\n")

        for line in lines:
            if line.startswith("data: "):
                try:
                    data = json.loads(line[6:])
                    if data.get("type") == "content":
                        content += data.get("content", "")
                    elif data.get("type") == "metadata":
                        metadata = data.get("metadata", {})
                except json.JSONDecodeError:
                    continue

        # 检查是否通过
        passed = True
        actual_intent = metadata.get("intent")
        actual_triage_level = metadata.get("triage_level")

        # 检查意图
        if "intent" in expected:
            if actual_intent != expected["intent"]:
                passed = False

        # 检查分诊级别
        if "triage_level" in expected:
            if actual_triage_level != expected["triage_level"]:
                passed = False

        # 检查必须包含的关键词
        has_keywords = True
        if "must_include" in expected:
            for keyword in expected["must_include"]:
                if keyword not in content:
                    has_keywords = False
                    passed = False
                    break

        return EvaluationResult(
            test_case_id=test_id,
            category=category,
            passed=passed,
            actual_intent=actual_intent,
            actual_triage_level=actual_triage_level,
            has_required_keywords=has_keywords,
            response_snippet=content[:200] if content else None
        )

    except TimeoutException:
        return EvaluationResult(
            test_case_id=test_id,
            category=category,
            passed=False,
            error_message="Request timeout"
        )
    except Exception as e:
        return EvaluationResult(
            test_case_id=test_id,
            category=category,
            passed=False,
            error_message=str(e)
        )
    finally:
        if should_close:
            await client.aclose()


async def run_all_tests(
    test_cases_path: str,
    concurrent_limit: int = 5,
    api_base: str = "http://localhost:8000"
) -> List[EvaluationResult]:
    """
    运行所有测试用例

    Args:
        test_cases_path: 测试用例文件路径
        concurrent_limit: 并发数限制
        api_base: API基础URL

    Returns:
        List[EvaluationResult]: 所有评估结果
    """
    # 加载测试用例
    test_file = Path(test_cases_path)
    if not test_file.exists():
        raise FileNotFoundError(f"Test file not found: {test_cases_path}")

    with open(test_file, "r", encoding="utf-8") as f:
        test_cases = json.load(f)

    print(f"Loaded {len(test_cases)} test cases from {test_cases_path}")

    # 创建共享的HTTP客户端
    client = AsyncClient(timeout=30.0)

    # 创建信号量限制并发
    semaphore = asyncio.Semaphore(concurrent_limit)

    async def run_with_semaphore(test_case):
        async with semaphore:
            return await run_single_test(test_case, api_base, client)

    # 并发运行所有测试
    results = await asyncio.gather(
        *[run_with_semaphore(tc) for tc in test_cases],
        return_exceptions=True
    )

    # 关闭客户端
    await client.aclose()

    # 处理异常结果
    final_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            final_results.append(EvaluationResult(
                test_case_id=test_cases[i].get("id", "unknown"),
                category=test_cases[i].get("category", "unknown"),
                passed=False,
                error_message=str(result)
            ))
        else:
            final_results.append(result)

    return final_results


def generate_report(results: List[EvaluationResult]) -> EvaluationReport:
    """
    生成评估报告

    Args:
        results: 评估结果列表

    Returns:
        EvaluationReport: 评估报告
    """
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed

    # 总体通过率
    total_pass_rate = (passed / total * 100) if total > 0 else 0

    # 急症召回率（emergency类测试用例的通过率）
    emergency_cases = [r for r in results if "急症" in r.category or "emergency" in r.category.lower()]
    emergency_passed = sum(1 for r in emergency_cases if r.passed)
    emergency_recall_rate = (emergency_passed / len(emergency_cases) * 100) if emergency_cases else 0

    # 拒答准确率（blocked类测试用例的通过率）
    blocked_cases = [r for r in results if "拒答" in r.category or "blocked" in r.category.lower()]
    blocked_passed = sum(1 for r in blocked_cases if r.passed)
    refusal_accuracy = (blocked_passed / len(blocked_cases) * 100) if blocked_cases else 0

    # 按分类的通过率
    category_stats = {}
    for result in results:
        cat = result.category
        if cat not in category_stats:
            category_stats[cat] = {"total": 0, "passed": 0}
        category_stats[cat]["total"] += 1
        if result.passed:
            category_stats[cat]["passed"] += 1

    category_pass_rates = {}
    for cat, stats in category_stats.items():
        rate = (stats["passed"] / stats["total"] * 100) if stats["total"] > 0 else 0
        category_pass_rates[cat] = {
            "pass_rate": rate,
            "passed": stats["passed"],
            "total": stats["total"]
        }

    # 失败的测试用例
    failed_cases = [
        {
            "id": r.test_case_id,
            "category": r.category,
            "reason": r.error_message or "Keywords/Intent mismatch"
        }
        for r in results if not r.passed
    ]

    return EvaluationReport(
        timestamp=datetime.now().isoformat(),
        total_cases=total,
        passed_cases=passed,
        failed_cases=failed,
        total_pass_rate=round(total_pass_rate, 2),
        emergency_recall_rate=round(emergency_recall_rate, 2),
        refusal_accuracy=round(refusal_accuracy, 2),
        category_pass_rates=category_pass_rates,
        failed_test_cases=failed_cases
    )


def print_summary(report: EvaluationReport):
    """打印评估摘要"""
    print("=" * 70)
    print("📊 评估报告摘要")
    print("=" * 70)
    print(f"时间: {report.timestamp}")
    print(f"总测试用例: {report.total_cases}")
    print(f"通过: {report.passed_cases} ✅")
    print(f"失败: {report.failed_cases} ❌")
    print(f"总体通过率: {report.total_pass_rate}%")
    print(f"急症召回率: {report.emergency_recall_rate}%")
    print(f"拒答准确率: {report.refusal_accuracy}%")
    print()

    print("分类通过率:")
    for cat, stats in report.category_pass_rates.items():
        status = "✅" if stats["pass_rate"] >= 80 else "⚠️" if stats["pass_rate"] >= 60 else "❌"
        print(f"  {status} {cat}: {stats['pass_rate']:.1f}% ({stats['passed']}/{stats['total']})")

    if report.failed_test_cases:
        print()
        print(f"失败的测试用例 ({len(report.failed_test_cases)}):")
        for case in report.failed_test_cases[:10]:
            print(f"  - {case['id']} [{case['category']}]: {case['reason']}")
        if len(report.failed_test_cases) > 10:
            print(f"  ... 还有 {len(report.failed_test_cases) - 10} 个")

    print("=" * 70)


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="自动化评估脚本")
    parser.add_argument(
        "--test-file", "-t",
        type=str,
        default="app/data/test_cases.json",
        help="测试用例文件路径"
    )
    parser.add_argument(
        "--output-file", "-o",
        type=str,
        default="evaluation_report.json",
        help="输出报告文件路径"
    )
    parser.add_argument(
        "--concurrent", "-c",
        type=int,
        default=5,
        help="并发数限制（默认5）"
    )
    parser.add_argument(
        "--api-base",
        type=str,
        default="http://localhost:8000",
        help="API基础URL"
    )

    args = parser.parse_args()

    print("开始评估...")
    print(f"测试用例文件: {args.test_file}")
    print(f"API地址: {args.api_base}")
    print(f"并发数: {args.concurrent}")
    print()

    try:
        # 运行所有测试
        results = await run_all_tests(
            test_cases_path=args.test_file,
            concurrent_limit=args.concurrent,
            api_base=args.api_base
        )

        # 生成报告
        report = generate_report(results)

        # 打印摘要
        print_summary(report)

        # 保存报告
        output_path = Path(args.output_file)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report.model_dump(), f, ensure_ascii=False, indent=2)

        print(f"\n✅ 报告已保存到: {output_path}")

    except FileNotFoundError as e:
        print(f"❌ 错误: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 评估失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
