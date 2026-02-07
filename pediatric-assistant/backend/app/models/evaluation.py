"""
Evaluation data models

Defines Pydantic models for LLM-based evaluation.
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional


class EvaluationRequest(BaseModel):
    """Evaluation request"""
    query: str = Field(..., description="User query")
    response: str = Field(..., description="System response to evaluate")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")


class EvaluationResult(BaseModel):
    """Evaluation result from LLM judge"""

    query: str = Field(..., description="Original query")
    response: str = Field(..., description="Original response")

    # Individual scores (0-10)
    scores: Dict[str, int] = Field(
        ...,
        description={
            "accuracy": "医学信息准确性 (0-10)",
            "safety": "安全性 (0-10)",
            "completeness": "完整性 (0-10)",
            "relevance": "相关性 (0-10)",
            "readability": "可读性 (0-10)",
        },
    )

    # Overall score
    overall_score: float = Field(..., description="Overall score (average)")

    # Analysis
    strengths: List[str] = Field(default_factory=list, description="Strengths of the response")
    weaknesses: List[str] = Field(default_factory=list, description="Weaknesses of the response")
    suggestions: List[str] = Field(default_factory=list, description="Improvement suggestions")

    # Critical issues
    critical_issues: List[str] = Field(
        default_factory=list,
        description="Critical issues (prescription drugs, missing emergency warnings, etc.)",
    )

    # Pass/fail determination
    passed: bool = Field(
        ...,
        description="Whether the response passes quality threshold (score >= 6 and no critical issues)",
    )

    # Metadata
    evaluated_at: str = Field(..., description="Evaluation timestamp")
    model_used: str = Field(..., description="Judge model used")


class BatchEvaluationSummary(BaseModel):
    """Summary of batch evaluation"""

    total_evaluated: int = Field(..., description="Total number of responses evaluated")
    passed: int = Field(..., description="Number of responses that passed")
    failed: int = Field(..., description="Number of responses that failed")

    # Score statistics
    average_score: float = Field(..., description="Average overall score")
    min_score: float = Field(..., description="Minimum score")
    max_score: float = Field(..., description="Maximum score")

    # Score distribution
    score_distribution: Dict[str, int] = Field(
        ...,
        description="Distribution of scores (e.g., {'9-10': 5, '6-8': 10, ...})",
    )

    # Dimension averages
    dimension_averages: Dict[str, float] = Field(
        ...,
        description="Average score for each dimension",
    )

    # Common issues
    common_issues: List[str] = Field(
        default_factory=list,
        description="Most common issues found across evaluations",
    )

    # Critical issues count
    critical_issues_count: int = Field(
        ...,
        description="Number of responses with critical issues",
    )

    # Evaluation details
    evaluations: List[EvaluationResult] = Field(
        ...,
        description="Individual evaluation results",
    )


class BadCase(BaseModel):
    """Bad case record"""

    id: str = Field(..., description="Bad case ID")
    query: str = Field(..., description="Original query")
    response: str = Field(..., description="Original response")

    # Evaluation data
    evaluation: Dict[str, Any] = Field(..., description="Full evaluation result")

    # Classification
    root_cause: str = Field(
        ...,
        description="Root cause category: knowledge_error, safety_missing, incomplete_info, intent_misclassified, other",
    )

    severity: str = Field(
        ...,
        description="Severity level: critical, high, medium, low",
    )

    # Metadata
    created_at: str = Field(..., description="Creation timestamp")
    status: str = Field(default="open", description="Status: open, in_progress, resolved")
