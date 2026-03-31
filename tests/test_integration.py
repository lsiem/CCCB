"""End-to-end integration test with mocked Claude SDK."""
import asyncio
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

from cccb.models import TaskDefinition, ConfigProfile
from cccb.runner import BenchmarkRunner
from cccb.executor import ExecutionResult


@pytest.mark.asyncio
async def test_full_benchmark_pipeline(tmp_repo, sample_config_dir, sample_task_yaml):
    """Test the full pipeline: config -> task -> run -> score -> report."""
    config = ConfigProfile.from_dir(sample_config_dir)
    task = TaskDefinition.from_yaml(sample_task_yaml)

    # Need at least 2 configs for meaningful efficiency scoring
    config2_dir = tmp_repo / "configs" / "advanced"
    config2_dir.mkdir(parents=True)
    (config2_dir / "CLAUDE.md").write_text("# Advanced Config\nBe thorough.\n")
    config2 = ConfigProfile.from_dir(config2_dir)

    runner = BenchmarkRunner(
        repo_root=tmp_repo,
        configs=[config, config2],
        tasks=[task],
    )

    mock_result = ExecutionResult(
        duration_ms=3000,
        duration_api_ms=2500,
        total_cost_usd=0.03,
        num_turns=2,
        session_id="integ-test",
        is_error=False,
    )

    mock_result2 = ExecutionResult(
        duration_ms=5000,
        duration_api_ms=4000,
        total_cost_usd=0.08,
        num_turns=4,
        session_id="integ-test-2",
        is_error=False,
    )

    call_count = 0

    async def mock_execute(task, working_dir, on_event=None):
        nonlocal call_count
        call_count += 1
        return mock_result if call_count == 1 else mock_result2

    # Mock worktree manager methods
    runner.worktree_mgr.create_worktree = MagicMock(
        side_effect=[
            tmp_repo / "worktrees" / "baseline_hello-world",
            tmp_repo / "worktrees" / "advanced_hello-world",
        ]
    )
    runner.worktree_mgr.copy_config_files = MagicMock()
    runner.worktree_mgr.copy_setup_files = MagicMock()
    runner.worktree_mgr.commit_setup = MagicMock(
        side_effect=["setup1", "setup2"]
    )
    runner.worktree_mgr.commit_result = MagicMock(
        side_effect=["result1", "result2"]
    )
    runner.worktree_mgr.get_diff = MagicMock(return_value="diff content")
    runner.worktree_mgr.cleanup_all = MagicMock()

    with patch("cccb.runner.execute_task", side_effect=mock_execute), \
         patch("cccb.runner.run_checks", return_value=[]), \
         patch("cccb.runner.evaluate_run", new_callable=AsyncMock,
               return_value=({"quality": 7.0, "correctness": 8.0}, "Good work")):

        events = []
        async for event in runner.run(on_event=lambda e: events.append(e)):
            pass

        # Verify results
        assert len(runner.results) == 2
        report = runner.build_report(summary="Test summary")
        assert report.winner is not None
        assert len(report.results) == 2
        assert report.summary == "Test summary"

        # Verify events were emitted
        run_starts = [e for e in events if e.type == "run_start"]
        run_completes = [e for e in events if e.type == "run_complete"]
        benchmark_done = [e for e in events if e.type == "benchmark_done"]

        assert len(run_starts) == 2
        assert len(run_completes) == 2
        assert len(benchmark_done) == 1


@pytest.mark.asyncio
async def test_benchmark_with_cancellation(tmp_repo, sample_config_dir, sample_task_yaml):
    """Test that cancellation stops after current run."""
    config = ConfigProfile.from_dir(sample_config_dir)
    config2_dir = tmp_repo / "configs" / "advanced"
    config2_dir.mkdir(parents=True)
    (config2_dir / "CLAUDE.md").write_text("# Advanced\n")
    config2 = ConfigProfile.from_dir(config2_dir)
    task = TaskDefinition.from_yaml(sample_task_yaml)

    runner = BenchmarkRunner(
        repo_root=tmp_repo,
        configs=[config, config2],
        tasks=[task],
    )

    mock_result = ExecutionResult(
        duration_ms=3000,
        duration_api_ms=2500,
        total_cost_usd=0.03,
        num_turns=2,
        session_id="cancel-test",
        is_error=False,
    )

    async def cancel_after_first(task, working_dir, on_event=None):
        runner.cancel()
        return mock_result

    # Mock worktree manager methods
    runner.worktree_mgr.create_worktree = MagicMock(
        return_value=tmp_repo / "worktrees" / "baseline_hello-world"
    )
    runner.worktree_mgr.copy_config_files = MagicMock()
    runner.worktree_mgr.copy_setup_files = MagicMock()
    runner.worktree_mgr.commit_setup = MagicMock(return_value="setup1")
    runner.worktree_mgr.commit_result = MagicMock(return_value="result1")
    runner.worktree_mgr.get_diff = MagicMock(return_value="diff content")
    runner.worktree_mgr.cleanup_all = MagicMock()

    with patch("cccb.runner.execute_task", side_effect=cancel_after_first), \
         patch("cccb.runner.run_checks", return_value=[]), \
         patch("cccb.runner.evaluate_run", new_callable=AsyncMock,
               return_value=({"quality": 5.0}, "ok")):

        async for event in runner.run():
            pass

        # Only 1 run should complete due to cancellation
        assert len(runner.results) == 1


@pytest.mark.asyncio
async def test_benchmark_event_callbacks(tmp_repo, sample_config_dir, sample_task_yaml):
    """Test that event callbacks are properly invoked."""
    config = ConfigProfile.from_dir(sample_config_dir)
    task = TaskDefinition.from_yaml(sample_task_yaml)

    runner = BenchmarkRunner(
        repo_root=tmp_repo,
        configs=[config],
        tasks=[task],
    )

    mock_result = ExecutionResult(
        duration_ms=2000,
        duration_api_ms=1500,
        total_cost_usd=0.02,
        num_turns=1,
        session_id="event-test",
        is_error=False,
    )

    # Mock worktree manager methods
    runner.worktree_mgr.create_worktree = MagicMock(
        return_value=tmp_repo / "worktrees" / "baseline_hello-world"
    )
    runner.worktree_mgr.copy_config_files = MagicMock()
    runner.worktree_mgr.copy_setup_files = MagicMock()
    runner.worktree_mgr.commit_setup = MagicMock(return_value="setup1")
    runner.worktree_mgr.commit_result = MagicMock(return_value="result1")
    runner.worktree_mgr.get_diff = MagicMock(return_value="diff content")
    runner.worktree_mgr.cleanup_all = MagicMock()

    with patch("cccb.runner.execute_task", return_value=mock_result), \
         patch("cccb.runner.run_checks", return_value=[]), \
         patch("cccb.runner.evaluate_run", new_callable=AsyncMock,
               return_value=({"quality": 8.0}, "good")):

        events_received = []
        callback_invoked = [0]

        def on_event(event):
            callback_invoked[0] += 1
            events_received.append(event)

        async for event in runner.run(on_event=on_event):
            pass

        # Verify callback was invoked for each event
        assert callback_invoked[0] > 0
        assert len(events_received) == callback_invoked[0]

        # Verify event types
        event_types = {e.type for e in events_received}
        assert "run_start" in event_types
        assert "run_complete" in event_types
        assert "benchmark_done" in event_types


@pytest.mark.asyncio
async def test_benchmark_report_winner_determination(tmp_repo, sample_config_dir, sample_task_yaml):
    """Test that the benchmark report correctly determines the winner."""
    config1 = ConfigProfile.from_dir(sample_config_dir)

    config2_dir = tmp_repo / "configs" / "advanced"
    config2_dir.mkdir(parents=True)
    (config2_dir / "CLAUDE.md").write_text("# Advanced Config\n")
    config2 = ConfigProfile.from_dir(config2_dir)

    task = TaskDefinition.from_yaml(sample_task_yaml)

    runner = BenchmarkRunner(
        repo_root=tmp_repo,
        configs=[config1, config2],
        tasks=[task],
    )

    # Mock results with different scores
    mock_result1 = ExecutionResult(
        duration_ms=3000,
        duration_api_ms=2500,
        total_cost_usd=0.03,
        num_turns=2,
        session_id="test-1",
        is_error=False,
    )

    mock_result2 = ExecutionResult(
        duration_ms=2000,
        duration_api_ms=1500,
        total_cost_usd=0.02,
        num_turns=2,
        session_id="test-2",
        is_error=False,
    )

    call_count = [0]

    async def mock_execute(task, working_dir, on_event=None):
        call_count[0] += 1
        return mock_result1 if call_count[0] == 1 else mock_result2

    # Mock worktree manager
    runner.worktree_mgr.create_worktree = MagicMock(
        side_effect=[
            tmp_repo / "worktrees" / "config1_hello-world",
            tmp_repo / "worktrees" / "config2_hello-world",
        ]
    )
    runner.worktree_mgr.copy_config_files = MagicMock()
    runner.worktree_mgr.copy_setup_files = MagicMock()
    runner.worktree_mgr.commit_setup = MagicMock(side_effect=["setup1", "setup2"])
    runner.worktree_mgr.commit_result = MagicMock(side_effect=["result1", "result2"])
    runner.worktree_mgr.get_diff = MagicMock(return_value="diff content")
    runner.worktree_mgr.cleanup_all = MagicMock()

    with patch("cccb.runner.execute_task", side_effect=mock_execute), \
         patch("cccb.runner.run_checks", return_value=[]), \
         patch("cccb.runner.evaluate_run", new_callable=AsyncMock) as mock_judge:

        # Give config2 higher scores so it should win
        mock_judge.side_effect = [
            ({"quality": 6.0, "correctness": 7.0}, "average"),
            ({"quality": 9.0, "correctness": 9.5}, "excellent"),
        ]

        async for event in runner.run():
            pass

        report = runner.build_report(summary="Test")

        # Config2 should be the winner due to higher judge scores
        assert report.winner is not None
        assert report.winner.name == "advanced"
