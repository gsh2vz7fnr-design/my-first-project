"""
Bad Cases Collection and Analysis

Automatically collects, analyzes, and reports on poor quality responses.
"""
import json
import uuid
from pathlib import Path
from datetime import datetime
from typing import List, Dict
from collections import Counter

from app.models.evaluation import EvaluationResult, BadCase


def classify_root_cause(evaluation_result: EvaluationResult) -> str:
    """
    Infer root cause from evaluation results

    Args:
        evaluation_result: Evaluation result

    Returns:
        Root cause category
    """
    scores = evaluation_result.scores

    # Safety issues take priority
    if scores.get("safety", 10) < 5:
        return "safety_missing"

    # Knowledge/accuracy issues
    if scores.get("accuracy", 10) < 5:
        return "knowledge_error"

    # Completeness issues
    if scores.get("completeness", 10) < 5:
        return "incomplete_info"

    # Relevance issues
    if scores.get("relevance", 10) < 5:
        return "intent_misclassified"

    # Default
    return "other"


def classify_severity(evaluation_result: EvaluationResult) -> str:
    """
    Classify severity based on critical issues and scores

    Args:
        evaluation_result: Evaluation result

    Returns:
        Severity level: critical, high, medium, low
    """
    # Critical: prescription drugs, missing emergency warnings
    critical_keywords = ["处方药", "诊断", "用药剂量", "急症未提示", "未就医"]

    for issue in evaluation_result.critical_issues:
        for keyword in critical_keywords:
            if keyword in issue:
                return "critical"

    # High: safety score < 5 or accuracy < 5
    if evaluation_result.scores.get("safety", 10) < 5:
        return "high"

    if evaluation_result.scores.get("accuracy", 10) < 5:
        return "high"

    # Medium: overall score < 4
    if evaluation_result.overall_score < 4:
        return "medium"

    # Low: 4-6 score
    if evaluation_result.overall_score < 6:
        return "low"

    return "low"


def collect_bad_cases(
    evaluation_results: List[EvaluationResult],
    output_path: str = "app/data/bad_cases.jsonl",
) -> List[BadCase]:
    """
    Automatically collect bad cases from evaluation results

    Args:
        evaluation_results: List of evaluation results
        output_path: Path to save bad cases

    Returns:
        List of BadCase objects
    """
    bad_cases = []

    # Filter: score < 6 OR has critical issues
    for result in evaluation_results:
        if result.overall_score < 6 or result.critical_issues:
            bad_case = BadCase(
                id=f"bc_{uuid.uuid4().hex[:8]}",
                query=result.query,
                response=result.response,
                evaluation=result.model_dump(),
                root_cause=classify_root_cause(result),
                severity=classify_severity(result),
                created_at=datetime.now().isoformat(),
                status="open",
            )
            bad_cases.append(bad_case)

    # Save to JSONL file
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "a", encoding="utf-8") as f:
        for case in bad_cases:
            f.write(json.dumps(case.model_dump(), ensure_ascii=False) + "\n")

    print(f"✅ Collected {len(bad_cases)} bad cases to {output_path}")

    return bad_cases


def load_bad_cases(input_path: str = "app/data/bad_cases.jsonl") -> List[BadCase]:
    """
    Load bad cases from JSONL file

    Args:
        input_path: Path to bad cases file

    Returns:
        List of BadCase objects
    """
    path = Path(input_path)

    if not path.exists():
        print(f"⚠️  Bad cases file not found: {input_path}")
        return []

    bad_cases = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                bad_cases.append(BadCase(**data))

    return bad_cases


def analyze_bad_cases(bad_cases: List[BadCase]) -> Dict:
    """
    Analyze bad cases and generate statistics

    Args:
        bad_cases: List of BadCase objects

    Returns:
        Analysis results dict
    """
    if not bad_cases:
        return {
            "total_cases": 0,
            "root_cause_distribution": {},
            "severity_distribution": {},
            "priority_list": [],
            "top_cases": [],
        }

    # Root cause distribution
    root_cause_counts = Counter(case.root_cause for case in bad_cases)
    root_cause_dist = {
        cause: {"count": count, "percentage": count / len(bad_cases) * 100}
        for cause, count in root_cause_counts.items()
    }

    # Severity distribution
    severity_counts = Counter(case.severity for case in bad_cases)
    severity_dist = {
        severity: {"count": count, "percentage": count / len(bad_cases) * 100}
        for severity, count in severity_counts.items()
    }

    # Priority list (severity × frequency)
    severity_weights = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    cause_priority = {}

    for cause in root_cause_counts:
        cases_with_cause = [c for c in bad_cases if c.root_cause == cause]
        weighted_score = sum(
            severity_weights.get(c.severity, 1) for c in cases_with_cause
        )
        cause_priority[cause] = {
            "score": weighted_score,
            "count": len(cases_with_cause),
            "description": _get_cause_description(cause),
        }

    priority_list = sorted(cause_priority.items(), key=lambda x: x[1]["score"], reverse=True)

    # Top 5 worst cases
    sorted_by_severity = sorted(
        bad_cases,
        key=lambda c: (
            severity_weights.get(c.severity, 1),
            c.evaluation.get("overall_score", 0),
        ),
        reverse=True,
    )
    top_cases = sorted_by_severity[:5]

    return {
        "total_cases": len(bad_cases),
        "root_cause_distribution": root_cause_dist,
        "severity_distribution": severity_dist,
        "priority_list": priority_list,
        "top_cases": top_cases,
    }


def _get_cause_description(cause: str) -> str:
    """Get human-readable description for root cause"""
    descriptions = {
        "safety_missing": "安全机制缺失（未提示急症就医、缺少免责声明）",
        "knowledge_error": "医学知识错误（不准确、过时、矛盾）",
        "incomplete_info": "信息不完整（遗漏关键内容）",
        "intent_misclassified": "意图识别错误（答非所问）",
        "rag_failure": "RAG检索失败",
        "other": "其他问题",
    }
    return descriptions.get(cause, cause)


def generate_markdown_report(
    analysis: Dict, output_path: str = "evaluation/bad_cases_report.md"
) -> str:
    """
    Generate Markdown bad cases analysis report

    Args:
        analysis: Analysis results from analyze_bad_cases
        output_path: Path to save report

    Returns:
        Markdown report content
    """
    lines = [
        "# Bad Cases Analysis Report",
        "",
        f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Summary",
        "",
        f"- **Total Bad Cases**: {analysis['total_cases']}",
        "",
        "## Root Cause Distribution",
        "",
        "| Root Cause | Count | Percentage | Description |",
        "|------------|-------|------------|-------------|",
    ]

    for cause, stats in sorted(
        analysis["root_cause_distribution"].items(),
        key=lambda x: x[1]["count"],
        reverse=True,
    ):
        desc = _get_cause_description(cause)
        lines.append(
            f"| {cause} | {stats['count']} | {stats['percentage']:.1f}% | {desc} |"
        )

    lines.extend([
        "",
        "## Severity Distribution",
        "",
        "| Severity | Count | Percentage |",
        "|----------|-------|------------|",
    ])

    severity_order = ["critical", "high", "medium", "low"]
    for severity in severity_order:
        if severity in analysis["severity_distribution"]:
            stats = analysis["severity_distribution"][severity]
            icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(
                severity, ""
            )
            lines.append(f"| {icon} {severity.capitalize()} | {stats['count']} | {stats['percentage']:.1f}% |")

    # Priority fix list
    lines.extend([
        "",
        "## Priority Fix List",
        "",
        "Ranked by impact (severity × frequency):",
        "",
    ])

    for i, (cause, data) in enumerate(analysis["priority_list"], 1):
        lines.append(f"### {i}. {data['description']}")
        lines.append(f"- **Impact Score**: {data['score']}")
        lines.append(f"- **Cases Affected**: {data['count']}")
        lines.append("")

    # Top 5 worst cases
    lines.extend([
        "## Top 5 Worst Cases",
        "",
    ])

    for i, case in enumerate(analysis["top_cases"], 1):
        icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(
            case.severity, ""
        )

        lines.extend([
            f"### {i}. {case.query[:60]}...",
            "",
            f"**Severity**: {icon} {case.severity.capitalize()}",
            f"**Root Cause**: {case.root_cause}",
            f"**Score**: {case.evaluation.get('overall_score', 0):.1f}/10",
            "",
        ])

        if case.evaluation.get("critical_issues"):
            lines.append("**Critical Issues**:")
            for issue in case.evaluation["critical_issues"]:
                lines.append(f"- {issue}")
            lines.append("")

        if case.evaluation.get("weaknesses"):
            lines.append("**Weaknesses**:")
            for weakness in case.evaluation["weaknesses"][:3]:
                lines.append(f"- {weakness}")
            lines.append("")

        lines.append("**Response Preview**:")
        lines.append(f"```")
        lines.append(case.response[:200] + "..." if len(case.response) > 200 else case.response)
        lines.append(f"```")
        lines.append("")

    # Recommendations
    lines.extend([
        "## Recommendations",
        "",
    ])

    critical_count = analysis["severity_distribution"].get("critical", {}).get("count", 0)
    high_count = analysis["severity_distribution"].get("high", {}).get("count", 0)

    if critical_count > 0:
        lines.append(f"### 🔴 Urgent Actions Required ({critical_count} critical cases)")
        lines.extend([
            "- Review all cases with prescription drug recommendations",
            "- Implement stricter safety filters",
            "- Add mandatory emergency warnings for serious symptoms",
            "- Consider service level adjustments until resolved",
            "",
        ])

    if high_count > 0:
        lines.extend([
            f"### 🟠 High Priority ({high_count} high severity cases)",
            "- Review and update knowledge base for accuracy",
            "- Improve RAG retrieval quality",
            "- Enhance intent classification",
            "",
        ])

    lines.extend([
        "### Continuous Improvement",
        "- Set up regular evaluation runs (e.g., weekly)",
        "- Track bad case trends over time",
        "- Use bad cases as test cases for regression testing",
        "- Share findings with development team",
        "",
        "---",
        "*Report generated by Bad Cases Analyzer*",
    ])

    report = "\n".join(lines)

    # Save report
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"✅ Report saved to: {output_path}")

    return report


async def main():
    """Main analysis runner"""
    import sys

    print("=" * 70)
    print("📊 Bad Cases Analysis")
    print("=" * 70)

    # Load bad cases
    bad_cases = load_bad_cases()

    if not bad_cases:
        print("\n⚠️  No bad cases found.")
        print("   Run evaluation first to generate bad cases:")
        print("   python -m evaluation.evaluate_responses")
        return

    print(f"\n✓ Loaded {len(bad_cases)} bad case(s)\n")

    # Analyze
    analysis = analyze_bad_cases(bad_cases)

    # Print summary
    print("Summary:")
    print(f"  Total: {analysis['total_cases']}")
    print(f"  Critical: {analysis['severity_distribution'].get('critical', {}).get('count', 0)}")
    print(f"  High: {analysis['severity_distribution'].get('high', {}).get('count', 0)}")
    print(f"  Medium: {analysis['severity_distribution'].get('medium', {}).get('count', 0)}")
    print(f"  Low: {analysis['severity_distribution'].get('low', {}).get('count', 0)}")

    # Generate report
    generate_markdown_report(analysis)

    print("\n" + "=" * 70)
    print("✅ Analysis complete!")
    print("=" * 70)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
