"""
LLM Evaluation Test Script

Evaluates system responses using DeepSeek as judge.

Usage:
    # Evaluate predefined test cases
    python -m evaluation.evaluate_responses

    # Evaluate from conversation database
    python -m evaluation.evaluate_responses --source database --limit 20

    # Evaluate from generated responses
    python -m evaluation.evaluate_responses --source responses --responses evaluation/test_responses.json

    # Evaluate specific test file
    python -m evaluation.evaluate_responses --file test_cases.json
"""
import argparse
import asyncio
import json
import sqlite3
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.services.evaluation_service import evaluation_service
from app.models.evaluation import EvaluationRequest, BatchEvaluationSummary
from evaluation.analyze_bad_cases import collect_bad_cases


def load_test_cases(file_path: str = None) -> List[Dict]:
    """
    Load test cases from file

    Args:
        file_path: Path to test cases JSON file

    Returns:
        List of test cases
    """
    if file_path is None:
        # Use default test cases
        return [
            {
                "query": "宝宝发烧39度怎么办",
                "response": "宝宝发烧39度属于高烧，建议采取以下措施：\n\n1. **物理降温**：用温水擦拭身体，多喝温水\n2. **药物治疗**：可以服用儿童退烧药如布洛芬或对乙酰氨基酚\n3. **观察症状**：注意宝宝精神状态，如有异常及时就医\n\n注意：以上建议仅供参考，如有疑问请咨询医生。",
            },
            {
                "query": "3岁宝宝咳嗽有痰怎么办",
                "response": "咳嗽有痰建议：\n1. 多喝温水帮助稀释痰液\n2. 保持室内湿度适宜\n3. 可以适当拍背帮助排痰\n4. 如症状持续或伴有发热，建议及时就医",
            },
            {
                "query": "宝宝拉肚子一天了",
                "response": "腹泻一天建议注意以下事项：\n\n1. **预防脱水**：适量补充口服补液盐\n2. **饮食调整**：清淡易消化食物，少量多餐\n3. **观察情况**：注意大便次数、性状，是否有发热、呕吐等\n\n如有以下情况请立即就医：\n- 大便带血\n- 持续高烧\n- 精神萎靡\n- 脱水症状（口干、尿少）",
            },
            {
                "query": "美林一次吃多少",
                "response": "美林（布洛芬）的剂量需要根据宝宝体重计算：\n\n- 一般每次每公斤体重5-10mg\n- 每6-8小时可重复一次\n- 每日不超过4次\n\n具体剂量请参考说明书或咨询医生，切勿超量使用。",
            },
            {
                "query": "宝宝过敏可以吃药吗",
                "response": "过敏反应需要专业医生诊断和治疗，不能自行用药。建议：\n\n1. **立即就医**：过敏反应可能很严重，需要医生评估\n2. **记录症状**：记录过敏症状、可能的过敏原\n3. **避免接触**：如已知过敏原，避免再次接触\n\n请不要自行购买药物治疗，以免加重病情。",
            },
        ]

    # Load from file
    path = Path(file_path)
    if not path.exists():
        print(f"❌ Test file not found: {file_path}")
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return _normalize_test_cases(data)
    elif isinstance(data, dict) and "test_cases" in data:
        return _normalize_test_cases(data["test_cases"])
    else:
        print(f"❌ Invalid test file format")
        sys.exit(1)


def load_responses_file(file_path: str) -> List[Dict]:
    """
    Load evaluation cases from a generated responses file.

    Supported formats:
    1) {"results": [{"input": "...", "response": "..."}]}
    2) [{"query": "...", "response": "..."}] or [{"input": "...", "response": "..."}]
    """
    path = Path(file_path)
    if not path.exists():
        print(f"❌ Responses file not found: {file_path}")
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict) and "results" in data:
        return _normalize_test_cases(data["results"])
    if isinstance(data, list):
        return _normalize_test_cases(data)

    print("❌ Invalid responses file format")
    sys.exit(1)


def _normalize_test_cases(raw_cases: List[Dict]) -> List[Dict]:
    """
    Normalize raw cases into {query, response, context?} list.
    """
    normalized = []
    for item in raw_cases:
        if "query" in item and "response" in item:
            normalized.append(
                {
                    "query": item["query"],
                    "response": item["response"],
                    "context": item.get("context"),
                }
            )
            continue
        if "input" in item and "response" in item:
            normalized.append(
                {
                    "query": item["input"],
                    "response": item["response"],
                    "context": item.get("metadata"),
                }
            )
            continue
        # Skip entries without required fields
    return normalized


async def load_from_database(limit: int = 20) -> List[Dict]:
    """
    Load test cases from conversation database

    Args:
        limit: Maximum number of conversations to load

    Returns:
        List of test cases
    """
    db_path = Path(settings.SQLITE_DB_PATH)
    if not db_path.exists():
        print(f"⚠️  SQLite database not found: {db_path}")
        print("   Using default test cases instead")
        return load_test_cases()

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT id, conversation_id, user_id, role, content, created_at
        FROM conversation_messages
        ORDER BY id ASC
        """
    ).fetchall()
    conn.close()

    pairs = []
    last_user = None
    for row in rows:
        if row["role"] == "user":
            last_user = row
            continue
        if row["role"] == "assistant" and last_user:
            if last_user["conversation_id"] != row["conversation_id"]:
                last_user = None
                continue
            pairs.append(
                {
                    "query": last_user["content"],
                    "response": row["content"],
                    "context": {
                        "conversation_id": row["conversation_id"],
                        "user_id": row["user_id"],
                        "user_timestamp": last_user["created_at"],
                        "assistant_timestamp": row["created_at"],
                    },
                }
            )
            last_user = None

    if not pairs:
        print("⚠️  No conversation pairs found in database")
        return []

    # Use most recent pairs
    pairs.sort(key=lambda x: x["context"]["assistant_timestamp"], reverse=True)
    return pairs[:limit]


async def main():
    """Main evaluation runner"""
    parser = argparse.ArgumentParser(description="Evaluate responses using LLM-as-a-Judge")
    parser.add_argument(
        "--file", "-f", type=str, help="Test cases JSON file"
    )
    parser.add_argument(
        "--responses", "-r", type=str, help="Generated responses JSON file"
    )
    parser.add_argument(
        "--source", "-s", choices=["file", "database", "responses"], default="file",
        help="Source of test cases (default: file)"
    )
    parser.add_argument(
        "--limit", "-l", type=int, default=20,
        help="Maximum number of test cases to evaluate"
    )
    parser.add_argument(
        "--concurrent", "-c", type=int, default=5,
        help="Maximum concurrent evaluations (default: 5)"
    )
    parser.add_argument(
        "--output", "-o", type=str, default="evaluation",
        help="Output directory for reports (default: evaluation/)"
    )

    args = parser.parse_args()

    print("=" * 70)
    print("🤖 LLM-as-a-Judge Evaluation")
    print("=" * 70)
    print(f"📅 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🤖 Judge Model: {evaluation_service.model}")
    print(f"📊 Source: {args.source}")
    print("=" * 70)

    # Load test cases
    if args.source == "database":
        test_cases = await load_from_database(args.limit)
    elif args.source == "responses":
        responses_path = args.responses or str(Path("evaluation") / "test_responses.json")
        test_cases = load_responses_file(responses_path)
    else:
        test_cases = load_test_cases(args.file)

    if args.limit and len(test_cases) > args.limit:
        test_cases = test_cases[:args.limit]

    print(f"\n✓ Loaded {len(test_cases)} test case(s)\n")

    # Run evaluation
    summary: BatchEvaluationSummary = await evaluation_service.batch_evaluate(
        test_cases, concurrent_limit=args.concurrent
    )

    # Print results
    print("\n" + "=" * 70)
    print("📊 Evaluation Results")
    print("=" * 70)

    print(f"\nTotal Evaluated: {summary.total_evaluated}")
    print(f"Passed: {summary.passed} ✅")
    print(f"Failed: {summary.failed} ❌")
    print(f"Pass Rate: {summary.passed / summary.total_evaluated * 100:.1f}%")

    print(f"\nScore Statistics:")
    print(f"  Average: {summary.average_score:.1f}/10")
    print(f"  Range: {summary.min_score:.1f} - {summary.max_score:.1f}")

    print(f"\nScore Distribution:")
    for range_name, count in summary.score_distribution.items():
        percentage = count / summary.total_evaluated * 100 if summary.total_evaluated > 0 else 0
        bar = "█" * int(percentage / 5)
        print(f"  {range_name:>3}: {bar} {count} ({percentage:.0f}%)")

    print(f"\nDimension Scores:")
    for dim, avg_score in summary.dimension_averages.items():
        status = "✅" if avg_score >= 6 else "⚠️"
        print(f"  {status} {dim}: {avg_score:.1f}/10")

    if summary.critical_issues_count > 0:
        print(f"\n⚠️  Critical Issues Found: {summary.critical_issues_count}")

    if summary.common_issues:
        print(f"\nCommon Issues:")
        for i, issue in enumerate(summary.common_issues, 1):
            print(f"  {i}. {issue}")

    # Save results
    output_dir = Path(args.output)
    output_dir.mkdir(exist_ok=True)

    # Save detailed results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = output_dir / f"evaluation_results_{timestamp}.json"

    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(summary.model_dump(), f, ensure_ascii=False, indent=2)

    print(f"\n✅ Results saved to: {results_file}")

    # Generate markdown report
    report = generate_markdown_report(summary)
    report_file = output_dir / f"evaluation_report_{timestamp}.md"

    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"✅ Report saved to: {report_file}")

    # Collect bad cases
    print(f"\n{'='*70}")
    print("📦 Collecting Bad Cases...")
    print("="*70)

    bad_cases = collect_bad_cases(summary.evaluations)

    if bad_cases:
        print(f"✓ Found {len(bad_cases)} bad case(s)")

        # Analyze bad cases
        from evaluation.analyze_bad_cases import analyze_bad_cases, generate_markdown_report

        analysis = analyze_bad_cases(bad_cases)
        bad_cases_report = generate_markdown_report(analysis)

        print(f"✅ Bad cases report generated")

    # Show failed cases
    failed_cases = [e for e in summary.evaluations if not e.passed]
    if failed_cases:
        print("\n" + "=" * 70)
        print(f"⚠️  Failed Cases ({len(failed_cases)})")
        print("=" * 70)

        for i, case in enumerate(failed_cases[:5], 1):  # Show first 5
            print(f"\n{i}. Query: {case.query[:50]}...")
            print(f"   Score: {case.overall_score:.1f}/10")
            if case.critical_issues:
                print(f"   Critical: {', '.join(case.critical_issues)}")

        if len(failed_cases) > 5:
            print(f"\n... and {len(failed_cases) - 5} more")

    print("\n" + "=" * 70)
    print("✅ Evaluation complete!")
    print("=" * 70)


def generate_markdown_report(summary: BatchEvaluationSummary) -> str:
    """Generate Markdown evaluation report"""
    lines = [
        "# LLM-as-a-Judge Evaluation Report",
        "",
        f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Judge Model**: DeepSeek",
        "",
        "## Summary",
        "",
        f"- **Total Evaluated**: {summary.total_evaluated}",
        f"- **Passed**: {summary.passed} ✅",
        f"- **Failed**: {summary.failed} ❌",
        f"- **Pass Rate**: {summary.passed / summary.total_evaluated * 100:.1f}%",
        f"- **Average Score**: {summary.average_score:.1f}/10",
        "",
        "## Score Distribution",
        "",
        "| Score Range | Count | Percentage |",
        "|-------------|-------|------------|",
    ]

    for range_name, count in summary.score_distribution.items():
        percentage = count / summary.total_evaluated * 100 if summary.total_evaluated > 0 else 0
        bar_length = int(percentage / 5)
        bar = "█" * bar_length
        lines.append(f"| {range_name} | {count} | {percentage:.0f}% {bar} |")

    lines.extend([
        "",
        "## Dimension Analysis",
        "",
        "| Dimension | Average | Status |",
        "|-----------|---------|--------|",
    ])

    for dim, avg_score in summary.dimension_averages.items():
        status = "✅" if avg_score >= 6 else "⚠️"
        lines.append(f"| {dim} | {avg_score:.1f}/10 | {status} |")

    # Critical issues
    if summary.critical_issues_count > 0:
        lines.extend([
            "",
            "## ⚠️ Critical Issues",
            "",
            f"Found {summary.critical_issues_count} response(s) with critical issues:",
            "",
        ])

        critical_cases = [e for e in summary.evaluations if e.critical_issues]
        for case in critical_cases[:10]:
            lines.append(f"### {case.query[:60]}...")
            lines.append(f"- **Score**: {case.overall_score:.1f}/10")
            lines.append(f"- **Issues**: {', '.join(case.critical_issues)}")
            lines.append("")

    # Common issues
    if summary.common_issues:
        lines.extend([
            "## Common Issues",
            "",
        ])
        for i, issue in enumerate(summary.common_issues, 1):
            lines.append(f"{i}. {issue}")

    # Recommendations
    lines.extend([
        "",
        "## Recommendations",
        "",
    ])

    if summary.average_score < 6:
        lines.append("- ⚠️ Overall quality below threshold. Review and improve system responses.")

    if summary.dimension_averages.get("safety", 10) < 6:
        lines.extend([
            "",
            "### Safety Improvements Needed",
            "- Ensure emergency warnings are present for serious symptoms",
            "- Add appropriate disclaimers",
            "- Avoid any prescription drug recommendations",
        ])

    if summary.dimension_averages.get("accuracy", 10) < 6:
        lines.extend([
            "",
            "### Accuracy Improvements Needed",
            "- Review knowledge base for medical accuracy",
            "- Update outdated information",
            "- Verify alignment with current medical guidelines",
        ])

    lines.extend([
        "",
        "---",
        "*Report generated by LLM-as-a-Judge Evaluation System*",
    ])

    return "\n".join(lines)


if __name__ == "__main__":
    asyncio.run(main())
