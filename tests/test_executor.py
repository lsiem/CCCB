"""Tests for Claude Code executor."""
import asyncio
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from cccb.executor import execute_task, ExecutionEvent, ExecutionResult
from cccb.models import TaskDefinition, ClaudeSettings


@pytest.mark.asyncio
async def test_successful_execution(tmp_path: Path):
    """Test successful task execution."""
    # Create a minimal task
    task = TaskDefinition(
        name="Test Task",
        category="test",
        description="A test task",
        prompt="Write a simple Python script",
        claude_settings=ClaudeSettings(max_turns=3, timeout=30),
    )

    # Mock the SDK query function
    async def mock_query(prompt, options):
        """Mock query that yields two messages."""
        # First message
        msg1 = MagicMock()
        msg1.duration_ms = 500
        msg1.cost_usd = 0.01
        msg1.content = []
        yield msg1

        # Second message
        msg2 = MagicMock()
        msg2.duration_ms = 300
        msg2.cost_usd = 0.02
        msg2.content = []
        yield msg2

    mock_options = MagicMock()

    with patch("cccb.executor.SDK_AVAILABLE", True):
        with patch("cccb.executor.ClaudeAgentOptions", return_value=mock_options):
            with patch("cccb.executor.query", mock_query):
                result = await execute_task(task, tmp_path)

    assert result.is_error is False
    assert result.timed_out is False
    assert result.num_turns == 2
    assert result.total_cost_usd == 0.03
    assert result.duration_ms >= 0  # Allow fast execution
    assert isinstance(result.session_id, str)


@pytest.mark.asyncio
async def test_execution_with_events(tmp_path: Path):
    """Test that events are emitted during execution."""
    task = TaskDefinition(
        name="Test Task",
        category="test",
        description="A test task",
        prompt="Test prompt",
        claude_settings=ClaudeSettings(max_turns=2, timeout=30),
    )

    events = []

    def on_event(event: ExecutionEvent):
        events.append(event)

    async def mock_query(prompt, options):
        msg = MagicMock()
        msg.duration_ms = 100
        msg.cost_usd = 0.01
        msg.content = []
        yield msg

    mock_options = MagicMock()

    with patch("cccb.executor.SDK_AVAILABLE", True):
        with patch("cccb.executor.ClaudeAgentOptions", return_value=mock_options):
            with patch("cccb.executor.query", mock_query):
                result = await execute_task(task, tmp_path, on_event=on_event)

    # Should have events: message and complete
    assert len(events) >= 2
    assert events[-1].type == "complete"


@pytest.mark.asyncio
async def test_timeout_handling(tmp_path: Path):
    """Test timeout handling."""
    task = TaskDefinition(
        name="Test Task",
        category="test",
        description="A test task",
        prompt="Test prompt",
        claude_settings=ClaudeSettings(max_turns=5, timeout=1),  # Very short timeout
    )

    async def slow_query(prompt, options):
        """Query that takes too long."""
        await asyncio.sleep(2)  # Sleep longer than timeout
        yield MagicMock()

    mock_options = MagicMock()

    with patch("cccb.executor.SDK_AVAILABLE", True):
        with patch("cccb.executor.ClaudeAgentOptions", return_value=mock_options):
            with patch("cccb.executor.query", slow_query):
                result = await execute_task(task, tmp_path)

    assert result.timed_out is True


@pytest.mark.asyncio
async def test_process_error_handling(tmp_path: Path):
    """Test ProcessError handling."""
    task = TaskDefinition(
        name="Test Task",
        category="test",
        description="A test task",
        prompt="Test prompt",
        claude_settings=ClaudeSettings(max_turns=3, timeout=30),
    )

    async def error_query(prompt, options):
        raise Exception("Process error")
        yield  # Never reached

    mock_options = MagicMock()

    with patch("cccb.executor.SDK_AVAILABLE", True):
        with patch("cccb.executor.ClaudeAgentOptions", return_value=mock_options):
            with patch("cccb.executor.query", error_query):
                result = await execute_task(task, tmp_path)

    assert result.is_error is True


@pytest.mark.asyncio
async def test_sdk_not_available(tmp_path: Path):
    """Test error when SDK is not available."""
    task = TaskDefinition(
        name="Test Task",
        category="test",
        description="A test task",
        prompt="Test prompt",
    )

    with patch("cccb.executor.SDK_AVAILABLE", False):
        with pytest.raises(RuntimeError, match="claude-agent-sdk not installed"):
            await execute_task(task, tmp_path)


def test_execution_result_dataclass():
    """Test ExecutionResult dataclass creation."""
    result = ExecutionResult(
        duration_ms=5000,
        duration_api_ms=4000,
        total_cost_usd=0.05,
        num_turns=3,
        session_id="test-session",
        is_error=False,
        timed_out=False,
        tool_uses=["tool1", "tool2"],
    )

    assert result.duration_ms == 5000
    assert result.total_cost_usd == 0.05
    assert result.num_turns == 3
    assert len(result.tool_uses) == 2


def test_execution_event_dataclass():
    """Test ExecutionEvent dataclass creation."""
    event = ExecutionEvent(type="complete", detail="Execution finished")

    assert event.type == "complete"
    assert event.detail == "Execution finished"
