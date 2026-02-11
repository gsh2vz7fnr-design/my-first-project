"""
ChatPipeline integration tests

Tests the Pipeline using mocked external services.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.chat_pipeline import ChatPipeline, PipelineResult
from app.models.medical_context import (
    MedicalContext,
    DialogueState,
    IntentType
)


@pytest.fixture
def pipeline():
    """Create Pipeline instance"""
    return ChatPipeline()


@pytest.mark.asyncio
async def test_pipeline_result_to_api_response():
    """Test PipelineResult to API response conversion"""
    result = PipelineResult(
        conversation_id="test_conv",
        message="Test message",
        metadata={"intent": "triage"},
        need_follow_up=True,
        missing_slots=["age_months"]
    )

    response = result.to_api_response()

    assert response["code"] == 0
    assert response["data"]["conversation_id"] == "test_conv"
    assert response["data"]["message"] == "Test message"
    assert response["data"]["metadata"]["need_follow_up"] is True
    assert response["data"]["metadata"]["missing_slots"] == ["age_months"]


@pytest.mark.asyncio
async def test_stream_chunks_generation():
    """Test stream chunk generation"""
    result = PipelineResult(
        conversation_id="test_conv",
        message="This is a test message",
        metadata={"intent": "greeting"}
    )

    chunks = []
    async for chunk in result.to_stream_chunks():
        chunks.append(chunk)

    # Should have metadata, content, done types
    assert any("metadata" in c for c in chunks)
    assert any("content" in c for c in chunks)
    assert any('"type": "done"' in c for c in chunks)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
