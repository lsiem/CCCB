"""Tests for benchmark runner orchestration."""
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cccb.executor import ExecutionResult
from cccb.models import Check, CheckResult, ConfigProfile, RunResult, TaskDefinition
from cccb.runner import BenchmarkRunner, RunEvent, task_slug


class TestTaskSlug:
    """Tests for task_slug function."""

    def test_simple_lowercase(self):
        """Test slug with simple lowercase name."""
        result = task_slug("hello world")
        assert result == "hello-world"

    def test_with_special_chars(self):
        """Test slug removes special characters."""
        result = task_slug("create REST API!")
        assert result == "create-rest-api"

    def test_with_german_chars(self):
        """Test slug preserves German characters."""
        result = task_slug("REST API erstellen")
        assert result == "rest-api-erstellen"

    def test_with_umlauts(self):
        """Test slug preserves umlauts."""
        result = task_slug("Überprüfung äöü")
        assert result == "überprüfung-äöü"

    def test_multiple_spaces(self):
        """Test slug collapses multiple spaces."""
        result = task_slug("hello   world  test")
        assert result == "hello-world-test"

    def test_leading_trailing_spaces(self):
        """Test slug strips leading/trailing spaces."""
        result = task_slug("  hello world  ")
        assert result == "hello-world"

    def test_leading_trailing_hyphens(self):
        """Test slug strips leading/trailing hyphens."""
        result = task_slug("-hello-world-")
        assert result == "hello-world"

    def test_mixed_case(self):
        """Test slug converts to lowercase."""
        result = task_slug("Hello WORLD Test")
        assert result == "hello-world-test"

    def test_numbers_preserved(self):
        """Test slug preserves numbers."""
        result = task_slug("Task 123 v2")
        assert result == "task-123-v2"

    def test_empty_string(self):
        """Test slug with empty string."""
        result = task_slug("")
        assert result == ""

    def test_only_special_chars(self):
        """Test slug with only special characters."""
        result = task_slug("!@#$%^&*()")
        assert result == ""


class TestBenchmarkRunner:
    """Tests for BenchmarkRunner class."""

    @pytest.fixture
    def runner_setup(self, tmp_repo: Path, sample_task_yaml: Path, sample_config_dir: Path):
        """Set up a runner with sample task and config."""
        task = TaskDefinition.from_yaml(sample_task_yaml)
        config = ConfigProfile.from_dir(sample_config_dir)
        runner = BenchmarkRunner(tmp_repo, [config], [task])
        return runner, task, config, tmp_repo

    def test_build_matrix_single_config_task(self, runner_setup):
        """Test matrix with 1 config and 1 task."""
        runner, task, config, _ = runner_setup
        matrix = runner.build_matrix()
        assert len(matrix) == 1
        assert matrix[0] == (config, task)

    def test_build_matrix_multiple_configs_tasks(self, tmp_repo: Path):
        """Test matrix with multiple configs and tasks."""
        # Create 2 configs and 2 tasks
        configs = [
            ConfigProfile(
                name="config1",
                path=tmp_repo / "configs" / "config1",
                description="Config 1",
            ),
            ConfigProfile(
                name="config2",
                path=tmp_repo / "configs" / "config2",
                description="Config 2",
            ),
        ]
        tasks = [
            TaskDefinition(
                name="task1",
                category="cat",
                description="Task 1",
                prompt="Do task 1",
            ),
            TaskDefinition(
                name="task2",
                category="cat",
                description="Task 2",
                prompt="Do task 2",
            ),
        ]

        runner = BenchmarkRunner(tmp_repo, configs, tasks)
        matrix = runner.build_matrix()
        assert len(matrix) == 4
        assert (configs[0], tasks[0]) in matrix
        assert (configs[0], tasks[1]) in matrix
        assert (configs[1], tasks[0]) in matrix
        assert (configs[1], tasks[1]) in matrix

    def test_cancel_flag(self, runner_setup):
        """Test cancellation flag."""
        runner, _, _, _ = runner_setup
        assert runner._cancelled is False
        runner.cancel()
        assert runner._cancelled is True

    @pytest.mark.asyncio
    async def test_run_single_mocked(self, runner_setup):
        """Test _run_single with mocked dependencies."""
        runner, task, config, _ = runner_setup

        # Mock the worktree manager methods
        wt_path = Path("/fake/worktree")
        runner.worktree_mgr.create_worktree = MagicMock(return_value=wt_path)
        runner.worktree_mgr.copy_config_files = MagicMock()
        runner.worktree_mgr.copy_setup_files = MagicMock()
        runner.worktree_mgr.commit_setup = MagicMock(return_value="setup123")
        runner.worktree_mgr.commit_result = MagicMock(return_value="result456")
        runner.worktree_mgr.get_diff = MagicMock(return_value="diff content")

        # Mock execute_task
        exec_result = ExecutionResult(
            duration_ms=1000,
            duration_api_ms=500,
            total_cost_usd=0.05,
            num_turns=3,
            session_id="test-session",
            is_error=False,
            timed_out=False,
        )

        with patch("cccb.runner.execute_task", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = exec_result

            # Mock run_checks
            check_result = CheckResult(
                check=Check(type="file_exists", path="test.py"),
                passed=True,
                output="File found",
            )
            with patch("cccb.runner.run_checks", return_value=[check_result]):
                # Mock evaluate_run
                judge_scores = {"correctness": 8.5, "quality": 7.5}
                with patch(
                    "cccb.runner.evaluate_run", new_callable=AsyncMock
                ) as mock_judge:
                    mock_judge.return_value = (judge_scores, "Good solution")

                    result = await runner._run_single(config, task, "test-task")

                    # Verify result fields
                    assert isinstance(result, RunResult)
                    assert result.config == config
                    assert result.task == task
                    assert result.duration_ms == 1000
                    assert result.duration_api_ms == 500
                    assert result.total_cost_usd == 0.05
                    assert result.num_turns == 3
                    assert result.session_id == "test-session"
                    assert result.checks_passed == 1
                    assert result.checks_total == 1
                    assert result.judge_scores == judge_scores
                    assert result.judge_average == 8.0
                    assert result.commit_hash == "result456"
                    assert result.worktree_path == str(wt_path)

    @pytest.mark.asyncio
    async def test_run_emits_events(self, runner_setup):
        """Test that run() emits correct events."""
        runner, task, config, _ = runner_setup

        # Mock all dependencies
        wt_path = Path("/fake/worktree")
        runner.worktree_mgr.cleanup_all = MagicMock()
        runner.worktree_mgr.create_worktree = MagicMock(return_value=wt_path)
        runner.worktree_mgr.copy_config_files = MagicMock()
        runner.worktree_mgr.copy_setup_files = MagicMock()
        runner.worktree_mgr.commit_setup = MagicMock(return_value="setup123")
        runner.worktree_mgr.commit_result = MagicMock(return_value="result456")
        runner.worktree_mgr.get_diff = MagicMock(return_value="diff")

        exec_result = ExecutionResult(
            duration_ms=100,
            duration_api_ms=50,
            total_cost_usd=0.01,
            num_turns=1,
            session_id="test",
        )

        with patch("cccb.runner.execute_task", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = exec_result

            with patch("cccb.runner.run_checks", return_value=[]):
                with patch(
                    "cccb.runner.evaluate_run", new_callable=AsyncMock
                ) as mock_judge:
                    mock_judge.return_value = ({}, "")

                    events = []
                    async for event in runner.run(on_event=events.append):
                        pass

                    # Should have: run_start, run_complete, benchmark_done
                    assert len(events) >= 3
                    assert events[0].type == "run_start"
                    assert events[1].type == "run_complete"
                    assert events[-1].type == "benchmark_done"

    @pytest.mark.asyncio
    async def test_run_cancellation(self, tmp_repo: Path):
        """Test that cancellation stops iteration."""
        configs = [
            ConfigProfile(
                name="c1",
                path=tmp_repo / "configs" / "c1",
                description="Config 1",
            ),
            ConfigProfile(
                name="c2",
                path=tmp_repo / "configs" / "c2",
                description="Config 2",
            ),
        ]
        tasks = [
            TaskDefinition(
                name="t1",
                category="cat",
                description="Task 1",
                prompt="Task 1",
            ),
            TaskDefinition(
                name="t2",
                category="cat",
                description="Task 2",
                prompt="Task 2",
            ),
        ]

        runner = BenchmarkRunner(tmp_repo, configs, tasks)
        runner.worktree_mgr.cleanup_all = MagicMock()

        # Mock dependencies
        wt_path = Path("/fake/worktree")
        runner.worktree_mgr.create_worktree = MagicMock(return_value=wt_path)
        runner.worktree_mgr.copy_config_files = MagicMock()
        runner.worktree_mgr.copy_setup_files = MagicMock()
        runner.worktree_mgr.commit_setup = MagicMock(return_value="s")
        runner.worktree_mgr.commit_result = MagicMock(return_value="r")
        runner.worktree_mgr.get_diff = MagicMock(return_value="")

        exec_result = ExecutionResult(
            duration_ms=100,
            duration_api_ms=50,
            total_cost_usd=0.01,
            num_turns=1,
            session_id="test",
        )

        with patch("cccb.runner.execute_task", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = exec_result

            with patch("cccb.runner.run_checks", return_value=[]):
                with patch(
                    "cccb.runner.evaluate_run", new_callable=AsyncMock
                ) as mock_judge:
                    mock_judge.return_value = ({}, "")

                    count = 0
                    async for event in runner.run():
                        count += 1
                        if count == 2:  # After first run_start
                            runner.cancel()

                    # Should have stopped early
                    assert len(runner.results) <= 1

    def test_calculate_efficiency_scores(self, tmp_repo: Path):
        """Test efficiency score calculation."""
        config1 = ConfigProfile(
            name="config1",
            path=tmp_repo / "c1",
            description="Config 1",
        )
        config2 = ConfigProfile(
            name="config2",
            path=tmp_repo / "c2",
            description="Config 2",
        )
        task = TaskDefinition(
            name="task",
            category="cat",
            description="Task",
            prompt="Task",
        )

        runner = BenchmarkRunner(tmp_repo, [config1, config2], [task])

        # Create two results with different costs and times
        result1 = RunResult(
            config=config1,
            task=task,
            duration_ms=1000,
            duration_api_ms=500,
            total_cost_usd=0.10,
            num_turns=3,
            session_id="s1",
            checks_passed=1,
            checks_total=1,
            check_details=[],
            judge_scores={"q": 8.0},
            judge_average=8.0,
            total_score=7.0,
            worktree_path="/tmp/w1",
            branch_name="b1",
            commit_hash="h1",
        )
        result2 = RunResult(
            config=config2,
            task=task,
            duration_ms=2000,  # Slower
            duration_api_ms=1000,
            total_cost_usd=0.05,  # Cheaper
            num_turns=5,
            session_id="s2",
            checks_passed=1,
            checks_total=1,
            check_details=[],
            judge_scores={"q": 7.0},
            judge_average=7.0,
            total_score=6.0,
            worktree_path="/tmp/w2",
            branch_name="b2",
            commit_hash="h2",
        )

        runner.results = [result1, result2]
        runner._calculate_efficiency_scores()

        # result1 should have better efficiency (cheapest AND fastest)
        # result2 should have worse efficiency (slower AND more expensive)
        assert result1.total_score > result2.total_score

    def test_build_report_finds_winner(self, tmp_repo: Path):
        """Test that build_report correctly identifies winner."""
        config1 = ConfigProfile(
            name="config1",
            path=tmp_repo / "c1",
            description="Config 1",
        )
        config2 = ConfigProfile(
            name="config2",
            path=tmp_repo / "c2",
            description="Config 2",
        )
        task = TaskDefinition(
            name="task",
            category="cat",
            description="Task",
            prompt="Task",
        )

        runner = BenchmarkRunner(tmp_repo, [config1, config2], [task])

        # Create results where config1 has higher score
        result1 = RunResult(
            config=config1,
            task=task,
            duration_ms=1000,
            duration_api_ms=500,
            total_cost_usd=0.05,
            num_turns=3,
            session_id="s1",
            checks_passed=1,
            checks_total=1,
            check_details=[],
            judge_scores={},
            judge_average=9.0,
            total_score=9.0,
            worktree_path="/tmp/w1",
            branch_name="b1",
            commit_hash="h1",
        )
        result2 = RunResult(
            config=config2,
            task=task,
            duration_ms=1000,
            duration_api_ms=500,
            total_cost_usd=0.05,
            num_turns=3,
            session_id="s2",
            checks_passed=1,
            checks_total=1,
            check_details=[],
            judge_scores={},
            judge_average=6.0,
            total_score=6.0,
            worktree_path="/tmp/w2",
            branch_name="b2",
            commit_hash="h2",
        )

        runner.results = [result1, result2]

        report = runner.build_report(summary="Test summary")

        assert report.winner == config1
        assert report.configs == [config1, config2]
        assert report.tasks == [task]
        assert len(report.results) == 2
        assert report.summary == "Test summary"

    def test_build_report_no_results(self, tmp_repo: Path):
        """Test build_report with no results."""
        config = ConfigProfile(
            name="config",
            path=tmp_repo / "c",
            description="Config",
        )
        task = TaskDefinition(
            name="task",
            category="cat",
            description="Task",
            prompt="Task",
        )

        runner = BenchmarkRunner(tmp_repo, [config], [task])
        report = runner.build_report()

        assert report.winner is None
        assert len(report.results) == 0

    @pytest.mark.asyncio
    async def test_run_with_error_continues(self, tmp_repo: Path):
        """Test that errors in one run don't stop the benchmark."""
        config1 = ConfigProfile(
            name="c1",
            path=tmp_repo / "c1",
            description="Config 1",
        )
        config2 = ConfigProfile(
            name="c2",
            path=tmp_repo / "c2",
            description="Config 2",
        )
        task = TaskDefinition(
            name="t",
            category="cat",
            description="Task",
            prompt="Task",
        )

        runner = BenchmarkRunner(tmp_repo, [config1, config2], [task])
        runner.worktree_mgr.cleanup_all = MagicMock()

        wt_path = Path("/fake/worktree")
        runner.worktree_mgr.create_worktree = MagicMock(return_value=wt_path)
        runner.worktree_mgr.copy_config_files = MagicMock()
        runner.worktree_mgr.copy_setup_files = MagicMock()
        runner.worktree_mgr.commit_setup = MagicMock(return_value="s")
        runner.worktree_mgr.commit_result = MagicMock(return_value="r")
        runner.worktree_mgr.get_diff = MagicMock(return_value="")

        # Make first run fail
        with patch("cccb.runner.execute_task", new_callable=AsyncMock) as mock_exec:
            mock_exec.side_effect = RuntimeError("Fake error")

            with patch("cccb.runner.run_checks", return_value=[]):
                with patch(
                    "cccb.runner.evaluate_run", new_callable=AsyncMock
                ) as mock_judge:
                    mock_judge.return_value = ({}, "")

                    events = []
                    async for event in runner.run(on_event=events.append):
                        pass

                    # Should have error event
                    error_events = [e for e in events if e.type == "run_error"]
                    assert len(error_events) >= 1
