"""Benchmark runner orchestration engine."""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncIterator, Callable, Optional

from cccb.checker import run_checks
from cccb.executor import execute_task
from cccb.isolation import WorktreeManager
from cccb.judge import evaluate_run
from cccb.models import ConfigProfile, RunResult, TaskDefinition, BenchmarkReport
from cccb.scorer import (
    calculate_check_score,
    calculate_efficiency,
    calculate_total_score,
    calculate_config_average,
)

logger = logging.getLogger(__name__)


def task_slug(name: str) -> str:
    """Convert task name to filesystem-safe slug.

    Args:
        name: Task name, may contain special characters

    Returns:
        Filesystem-safe slug suitable for directory names
    """
    slug = name.lower().strip()
    # Keep German characters, remove other special chars
    slug = re.sub(r"[^a-z0-9äöüß\s-]", "", slug)
    # Replace whitespace with hyphens
    slug = re.sub(r"[\s]+", "-", slug)
    return slug.strip("-")


@dataclass
class RunEvent:
    """Event emitted during benchmark run."""
    type: str  # "run_start" | "run_complete" | "run_error" | "benchmark_done"
    config_name: str = ""
    task_name: str = ""
    run_index: int = 0
    total_runs: int = 0
    result: Optional[RunResult] = None
    error: str = ""


class BenchmarkRunner:
    """Orchestrates benchmark runs across configs and tasks."""

    def __init__(
        self,
        repo_root: Path,
        configs: list[ConfigProfile],
        tasks: list[TaskDefinition],
    ):
        """Initialize the benchmark runner.

        Args:
            repo_root: Root path of the git repository
            configs: List of configuration profiles
            tasks: List of task definitions
        """
        self.repo_root = Path(repo_root)
        self.configs = configs
        self.tasks = tasks
        self.results: list[RunResult] = []
        self.worktree_mgr = WorktreeManager(repo_root)
        self._cancelled = False

    def build_matrix(self) -> list[tuple[ConfigProfile, TaskDefinition]]:
        """Build the config x task matrix.

        Returns:
            List of (config, task) tuples for all combinations
        """
        return [(config, task) for config in self.configs for task in self.tasks]

    def cancel(self) -> None:
        """Request cancellation of the benchmark run."""
        self._cancelled = True

    async def run(
        self,
        on_event: Optional[Callable[[RunEvent], None]] = None,
    ) -> AsyncIterator[RunEvent]:
        """Execute the benchmark across all configs and tasks.

        Args:
            on_event: Optional callback for run events

        Yields:
            RunEvent for each run phase
        """
        matrix = self.build_matrix()
        total = len(matrix)
        self.worktree_mgr.cleanup_all()

        for idx, (config, task) in enumerate(matrix):
            if self._cancelled:
                break

            slug = task_slug(task.name)

            # Emit run_start
            event = RunEvent(
                type="run_start",
                config_name=config.name,
                task_name=task.name,
                run_index=idx + 1,
                total_runs=total,
            )
            if on_event:
                on_event(event)
            yield event

            try:
                result = await self._run_single(config, task, slug)
                self.results.append(result)
                event = RunEvent(
                    type="run_complete",
                    config_name=config.name,
                    task_name=task.name,
                    run_index=idx + 1,
                    total_runs=total,
                    result=result,
                )
            except Exception as e:
                event = RunEvent(
                    type="run_error",
                    config_name=config.name,
                    task_name=task.name,
                    run_index=idx + 1,
                    total_runs=total,
                    error=str(e),
                )
                logger.exception(f"Error running {config.name} x {task.name}")

            if on_event:
                on_event(event)
            yield event

        # Calculate efficiency scores after all runs complete
        self._calculate_efficiency_scores()

        # Emit benchmark complete
        event = RunEvent(type="benchmark_done", total_runs=total)
        if on_event:
            on_event(event)
        yield event

    async def _run_single(
        self,
        config: ConfigProfile,
        task: TaskDefinition,
        slug: str,
    ) -> RunResult:
        """Run a single config x task combination.

        Args:
            config: Configuration to run
            task: Task to run
            slug: Filesystem slug for the task

        Returns:
            RunResult with metrics and scores
        """
        logger.info(f"Starting run: {config.name} x {task.name}")

        # 1. Create worktree
        wt_path = self.worktree_mgr.create_worktree(config.name, slug)
        logger.debug(f"Created worktree at {wt_path}")

        # 2. Copy config and setup files
        self.worktree_mgr.copy_config_files(wt_path, config.path)
        self.worktree_mgr.copy_setup_files(wt_path, task.setup_files)
        logger.debug(f"Copied config and setup files")

        # 3. Commit setup state
        setup_hash = self.worktree_mgr.commit_setup(wt_path, config.name, slug)
        logger.debug(f"Setup commit hash: {setup_hash}")

        # 4. Execute Claude Code
        exec_result = await execute_task(task, wt_path)
        logger.info(
            f"Execution complete: {exec_result.num_turns} turns, "
            f"${exec_result.total_cost_usd:.4f}, {exec_result.duration_ms}ms"
        )

        # 5. Run checks
        check_results = run_checks(task.checks, wt_path)
        checks_passed = sum(1 for cr in check_results if cr.passed)
        checks_total = len(check_results)
        logger.info(f"Checks: {checks_passed}/{checks_total} passed")

        # 6. Commit result state
        # Calculate a preliminary score for the commit message
        check_score = calculate_check_score(checks_passed, checks_total)
        result_hash = self.worktree_mgr.commit_result(
            wt_path,
            config.name,
            slug,
            check_score,
            timeout=exec_result.timed_out,
            error=exec_result.is_error,
        )
        logger.debug(f"Result commit hash: {result_hash}")

        # 7. Get diff and run judge
        git_diff = self.worktree_mgr.get_diff(wt_path, setup_hash, result_hash)
        judge_scores, judge_reasoning = await evaluate_run(task, git_diff, str(wt_path))

        # Calculate judge average
        judge_values = list(judge_scores.values()) if judge_scores else [5.0]
        judge_average = sum(judge_values) / len(judge_values) if judge_values else 5.0
        logger.info(f"Judge scores: {judge_scores}, average: {judge_average:.2f}")

        # 8. Calculate scores
        check_score = calculate_check_score(checks_passed, checks_total)
        # Note: efficiency is calculated later after all runs complete
        efficiency = 5.0  # Placeholder, will be recalculated
        total_score = calculate_total_score(check_score, judge_average, efficiency)

        # 9. Return RunResult
        result = RunResult(
            config=config,
            task=task,
            duration_ms=exec_result.duration_ms,
            duration_api_ms=exec_result.duration_api_ms,
            total_cost_usd=exec_result.total_cost_usd,
            num_turns=exec_result.num_turns,
            session_id=exec_result.session_id,
            checks_passed=checks_passed,
            checks_total=checks_total,
            check_details=check_results,
            judge_scores=judge_scores,
            judge_average=judge_average,
            total_score=total_score,
            timed_out=exec_result.timed_out,
            is_error=exec_result.is_error,
            worktree_path=str(wt_path),
            branch_name=f"bench/{config.name}/{slug}",
            commit_hash=result_hash,
        )

        logger.info(f"Run complete: total_score={result.total_score:.2f}")
        return result

    def _calculate_efficiency_scores(self) -> None:
        """Recalculate efficiency scores for all runs.

        Groups results by task, ranks by cost and time, and updates total scores.
        """
        if not self.results:
            return

        # Group results by task
        results_by_task: dict[str, list[RunResult]] = {}
        for result in self.results:
            task_name = result.task.name if result.task else "unknown"
            if task_name not in results_by_task:
                results_by_task[task_name] = []
            results_by_task[task_name].append(result)

        # Recalculate efficiency for each task
        for task_name, task_results in results_by_task.items():
            n_configs = len(task_results)

            # Rank by cost and time using indices
            cost_ranked = sorted(
                enumerate(task_results),
                key=lambda x: x[1].total_cost_usd,
            )
            time_ranked = sorted(
                enumerate(task_results),
                key=lambda x: x[1].duration_ms,
            )

            # Create index-based rank maps
            cost_rank_map = {idx: rank + 1 for rank, (idx, _) in enumerate(cost_ranked)}
            time_rank_map = {idx: rank + 1 for rank, (idx, _) in enumerate(time_ranked)}

            # Update efficiency and total score for each result
            for idx, result in enumerate(task_results):
                cost_rank = cost_rank_map[idx]
                time_rank = time_rank_map[idx]
                timeout = result.timed_out

                efficiency = calculate_efficiency(
                    cost_rank,
                    time_rank,
                    n_configs,
                    timeout=timeout,
                )

                # Recalculate total score with efficiency
                check_score = calculate_check_score(
                    result.checks_passed,
                    result.checks_total,
                )
                total_score = calculate_total_score(
                    check_score,
                    result.judge_average,
                    efficiency,
                )

                # Update result in place
                result.total_score = total_score

                logger.debug(
                    f"Updated {result.config.name} x {task_name}: "
                    f"cost_rank={cost_rank}, time_rank={time_rank}, "
                    f"efficiency={efficiency:.2f}, total_score={total_score:.2f}"
                )

    def build_report(self, summary: str = "") -> BenchmarkReport:
        """Build a comprehensive benchmark report.

        Args:
            summary: Optional summary text

        Returns:
            BenchmarkReport with results and winner
        """
        # Find winner: highest average score per config
        config_scores: dict[str, list[float]] = {}
        for result in self.results:
            config_name = result.config.name if result.config else "unknown"
            if config_name not in config_scores:
                config_scores[config_name] = []
            config_scores[config_name].append(result.total_score)

        winner = None
        best_avg = -1.0
        for config in self.configs:
            if config.name in config_scores:
                avg_score = calculate_config_average(config_scores[config.name])
                if avg_score > best_avg:
                    best_avg = avg_score
                    winner = config

        return BenchmarkReport(
            configs=self.configs,
            tasks=self.tasks,
            results=self.results,
            winner=winner,
            summary=summary,
        )
