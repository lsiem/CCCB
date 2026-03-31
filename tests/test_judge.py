"""Tests for LLM-as-Judge module."""
import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from cccb.judge import build_judge_prompt, parse_judge_response, evaluate_run
from cccb.models import TaskDefinition, JudgeCriteria


def test_build_judge_prompt_basic():
    """Test basic judge prompt building."""
    task = TaskDefinition(
        name="Hello World",
        category="codegen",
        description="Create a hello world script",
        prompt="Write a Python script that prints hello world",
        judge=JudgeCriteria(
            criteria=["Gibt das Script hello world aus?", "Ist der Code sauber?"],
            scale="1-10",
        ),
    )

    git_diff = """
diff --git a/hello.py b/hello.py
new file mode 100644
index 0000000..1234567
--- /dev/null
+++ b/hello.py
@@ -0,0 +1 @@
+print("hello world")
"""

    prompt = build_judge_prompt(task, git_diff)

    assert "Hello World" in prompt
    assert "hello world" in prompt
    assert "Gibt das Script hello world aus?" in prompt
    assert "Ist der Code sauber?" in prompt
    assert "Bewertungsskala" in prompt


def test_build_judge_prompt_empty_diff():
    """Test prompt building with empty diff."""
    task = TaskDefinition(
        name="Test Task",
        category="test",
        description="Test description",
        prompt="Test prompt",
        judge=JudgeCriteria(criteria=["Test criterion"]),
    )

    prompt = build_judge_prompt(task, "")

    assert "Kein Code generiert" in prompt


def test_build_judge_prompt_large_diff():
    """Test that large diffs are truncated."""
    task = TaskDefinition(
        name="Test Task",
        category="test",
        description="Test description",
        prompt="Test prompt",
    )

    # Create a diff larger than 50000 characters
    large_diff = "x" * 60000

    prompt = build_judge_prompt(task, large_diff)

    assert "gekürzt" in prompt
    assert len(prompt) < len(large_diff) + 2000  # Prompt + context, not full diff


def test_parse_judge_response_valid():
    """Test parsing a valid judge response."""
    response = json.dumps({
        "scores": {"criterion_1": 8.5, "criterion_2": 7.0},
        "reasoning": "Good solution with minor issues"
    })

    scores, reasoning = parse_judge_response(response)

    assert scores["criterion_1"] == 8.5
    assert scores["criterion_2"] == 7.0
    assert "Good solution" in reasoning


def test_parse_judge_response_clamping():
    """Test that scores are clamped to 1.0-10.0."""
    response = json.dumps({
        "scores": {"low": 0.5, "high": 11.5, "valid": 5.0},
        "reasoning": "Testing clamping"
    })

    scores, reasoning = parse_judge_response(response)

    assert scores["low"] == 1.0  # Clamped up
    assert scores["high"] == 10.0  # Clamped down
    assert scores["valid"] == 5.0  # Unchanged


def test_parse_judge_response_invalid_json():
    """Test error on invalid JSON."""
    with pytest.raises(ValueError, match="Invalid JSON|Could not find JSON"):
        parse_judge_response("This is not JSON at all!")


def test_parse_judge_response_missing_scores():
    """Test error when scores field is missing."""
    response = json.dumps({
        "reasoning": "No scores provided"
    })

    with pytest.raises(ValueError, match="Missing 'scores'"):
        parse_judge_response(response)


def test_parse_judge_response_json_in_text():
    """Test parsing JSON embedded in text."""
    response = """
    Here is the evaluation:
    {
      "scores": {"test": 7.5},
      "reasoning": "Good work"
    }
    That's my assessment.
    """

    scores, reasoning = parse_judge_response(response)

    assert scores["test"] == 7.5
    assert "Good work" in reasoning


def test_parse_judge_response_invalid_score_values():
    """Test that invalid score values are defaulted to 5.0."""
    response = json.dumps({
        "scores": {"invalid": "not a number", "valid": 8.0},
        "reasoning": "Testing invalid values"
    })

    scores, reasoning = parse_judge_response(response)

    assert scores["invalid"] == 5.0  # Defaulted to middle score
    assert scores["valid"] == 8.0


@pytest.mark.asyncio
async def test_evaluate_run_with_mock_sdk():
    """Test evaluate_run with mocked SDK."""
    task = TaskDefinition(
        name="Test Task",
        category="test",
        description="Test description",
        prompt="Test prompt",
        judge=JudgeCriteria(criteria=["Test criterion"]),
    )

    git_diff = "diff content"

    # Create mock text block
    mock_text_block = MagicMock()
    mock_text_block.text = json.dumps({
        "scores": {"test": 8.0},
        "reasoning": "Evaluated"
    })

    # Mock the SDK query
    async def mock_query(prompt, options):
        msg = MagicMock()
        msg.content = [mock_text_block]
        yield msg

    mock_options = MagicMock()

    with patch("cccb.judge.SDK_AVAILABLE", True):
        with patch("cccb.judge.ClaudeAgentOptions", return_value=mock_options):
            with patch("cccb.judge.query", mock_query):
                with patch("cccb.judge.TextBlock", MagicMock):
                    scores, reasoning = await evaluate_run(task, git_diff)

    assert scores["test"] == 8.0
    assert "Evaluated" in reasoning


@pytest.mark.asyncio
async def test_evaluate_run_sdk_not_available():
    """Test error when SDK is not available."""
    task = TaskDefinition(
        name="Test Task",
        category="test",
        description="Test",
        prompt="Test",
    )

    with patch("cccb.judge.SDK_AVAILABLE", False):
        with pytest.raises(RuntimeError, match="claude-agent-sdk not installed"):
            await evaluate_run(task, "diff")


def test_build_judge_prompt_no_criteria():
    """Test prompt building when no criteria are defined."""
    task = TaskDefinition(
        name="Test Task",
        category="test",
        description="Test description",
        prompt="Test prompt",
        judge=None,
    )

    prompt = build_judge_prompt(task, "diff")

    assert "Keine spezifischen Kriterien" in prompt
    assert "Test Task" in prompt
