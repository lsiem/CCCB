"""Tests for CCCB data models."""
import pytest
from pathlib import Path


def test_check_command():
    from cccb.models import Check
    c = Check(type="command", run="pytest -v", path=None, expect_exit_code=0)
    assert c.type == "command"
    assert c.run == "pytest -v"
    assert c.expect_exit_code == 0

def test_check_file_exists():
    from cccb.models import Check
    c = Check(type="file_exists", run=None, path="main.py", expect_exit_code=0)
    assert c.type == "file_exists"
    assert c.path == "main.py"

def test_claude_settings_defaults():
    from cccb.models import ClaudeSettings
    s = ClaudeSettings(max_turns=10)
    assert s.max_turns == 10
    assert s.allowed_tools is None
    assert s.timeout == 300

def test_task_definition_from_yaml(sample_task_yaml: Path):
    from cccb.models import TaskDefinition
    task = TaskDefinition.from_yaml(sample_task_yaml)
    assert task.name == "Hello World"
    assert task.category == "codegen"
    assert len(task.checks) == 2
    assert task.checks[0].type == "file_exists"
    assert task.checks[1].type == "command"
    assert task.claude_settings.max_turns == 5

def test_task_definition_from_yaml_missing_file():
    from cccb.models import TaskDefinition
    with pytest.raises(FileNotFoundError):
        TaskDefinition.from_yaml(Path("/nonexistent/task.yaml"))

def test_config_profile_from_dir(sample_config_dir: Path):
    from cccb.models import ConfigProfile
    config = ConfigProfile.from_dir(sample_config_dir)
    assert config.name == "baseline"
    assert config.path == sample_config_dir
    assert "Baseline Config" in config.description

def test_config_profile_from_dir_missing_claude_md(tmp_path: Path):
    from cccb.models import ConfigProfile
    empty_dir = tmp_path / "empty-config"
    empty_dir.mkdir()
    with pytest.raises(ValueError, match="CLAUDE.md"):
        ConfigProfile.from_dir(empty_dir)

def test_config_profile_from_dir_with_config_yaml(sample_config_dir: Path):
    from cccb.models import ConfigProfile
    (sample_config_dir / "config.yaml").write_text(
        'name: "My Baseline"\ndescription: "A custom description"\n'
    )
    config = ConfigProfile.from_dir(sample_config_dir)
    assert config.name == "My Baseline"
    assert config.description == "A custom description"

def test_run_result_creation():
    from cccb.models import RunResult
    result = RunResult(
        config=None, task=None,
        duration_ms=5000, duration_api_ms=4000, total_cost_usd=0.05,
        num_turns=3, session_id="test-session",
        checks_passed=2, checks_total=3, check_details=[],
        judge_scores={"quality": 7.5}, judge_average=7.5, total_score=0.0,
        worktree_path=".cccb-bench/baseline/hello", branch_name="bench/baseline/hello", commit_hash="abc123",
    )
    assert result.duration_ms == 5000
    assert result.total_cost_usd == 0.05

def test_benchmark_report_winner():
    from cccb.models import BenchmarkReport
    report = BenchmarkReport(configs=[], tasks=[], results=[], winner=None, summary="Test summary")
    assert report.summary == "Test summary"
