#!/usr/bin/env python3
"""Generate SVG screenshots of CCCB TUI screens for docs (run from repo root, venv active)."""

from __future__ import annotations

import asyncio
from pathlib import Path

from textual.css.query import NoMatches
from textual.widgets import Input

from cccb.app import CCCBApp
from cccb.models import (
    Check,
    CheckResult,
    ConfigProfile,
    RunResult,
    TaskDefinition,
)
from cccb.runner import RunEvent
from cccb.screens.results import ResultsScreen
from cccb.screens.running import RunningScreen


REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "docs" / "images"
FIXTURE_ALPHA = REPO_ROOT / "docs" / "images" / "fixtures" / "config-alpha"
FIXTURE_BETA = REPO_ROOT / "docs" / "images" / "fixtures" / "config-beta"
TERM_SIZE = (118, 32)


async def _wait_for_config_input(app: CCCBApp, pilot) -> Input:
    """query_one on the active screen — app.query_one targets the default screen."""
    for _ in range(80):
        await pilot.pause(0.05)
        try:
            return app.screen.query_one("#config_path_input", Input)
        except NoMatches:
            continue
    raise RuntimeError("Config screen did not mount in time")


def _configs() -> tuple[ConfigProfile, ConfigProfile]:
    return (
        ConfigProfile.from_dir(FIXTURE_ALPHA),
        ConfigProfile.from_dir(FIXTURE_BETA),
    )


def _sample_task() -> TaskDefinition:
    yaml_path = REPO_ROOT / "tasks" / "codegen" / "cli-parser.yaml"
    return TaskDefinition.from_yaml(yaml_path)


def _fake_run_result(
    config: ConfigProfile,
    task: TaskDefinition,
    *,
    score: float,
    duration_ms: int,
    cost: float,
    checks_ok: int,
    checks_total: int,
) -> RunResult:
    dummy_check = Check(type="command", run="true", expect_exit_code=0)
    return RunResult(
        config=config,
        task=task,
        duration_ms=duration_ms,
        duration_api_ms=int(duration_ms * 0.85),
        total_cost_usd=cost,
        num_turns=12,
        session_id="screenshot-session",
        checks_passed=checks_ok,
        checks_total=checks_total,
        check_details=[
            CheckResult(check=dummy_check, passed=True, output=""),
        ],
        judge_scores={"qualitaet": score},
        judge_average=score,
        total_score=score,
        worktree_path=str(REPO_ROOT / ".cccb-bench"),
        branch_name="bench-main",
        commit_hash="abc1234",
    )


class PausingStubRunner:
    """Yields run_start, blocks until resume() so a screenshot can be taken."""

    def __init__(self, configs: list[ConfigProfile], task: TaskDefinition) -> None:
        self.configs = configs
        self.task = task
        self.results: list[RunResult] = []
        self._resume = asyncio.Event()
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True
        self._resume.set()

    def resume_after_screenshot(self) -> None:
        self._resume.set()

    async def run(self):
        total = len(self.configs) * 1
        idx = 0
        for config in self.configs:
            if self._cancelled:
                break
            idx += 1
            yield RunEvent(
                type="run_start",
                config_name=config.name,
                task_name=self.task.name,
                run_index=idx,
                total_runs=total,
            )
            await self._resume.wait()
            if self._cancelled:
                break
            result = _fake_run_result(
                config,
                self.task,
                score=7.5 if "Alpha" in config.name else 8.1,
                duration_ms=145000 if "Alpha" in config.name else 98000,
                cost=0.31 if "Alpha" in config.name else 0.24,
                checks_ok=4,
                checks_total=4,
            )
            self.results.append(result)
            yield RunEvent(
                type="run_complete",
                config_name=config.name,
                task_name=self.task.name,
                run_index=idx,
                total_runs=total,
                result=result,
            )
        if not self._cancelled:
            yield RunEvent(type="benchmark_done")


class FakeResultsRunner:
    """Pre-filled results for the results screen only."""

    def __init__(self, results: list[RunResult]) -> None:
        self.results = results


class SnapRunningApp(CCCBApp):
    def on_mount(self) -> None:
        c1, c2 = _configs()
        task = _sample_task()
        self.selected_configs = [c1, c2]
        self.selected_tasks = [task]
        self.runner = PausingStubRunner([c1, c2], task)
        self.push_screen(RunningScreen())


class SnapResultsApp(CCCBApp):
    def on_mount(self) -> None:
        c1, c2 = _configs()
        task = _sample_task()
        self.selected_configs = [c1, c2]
        self.selected_tasks = [task]
        self.runner = FakeResultsRunner(
            [
                _fake_run_result(
                    c1,
                    task,
                    score=7.40,
                    duration_ms=152000,
                    cost=0.3291,
                    checks_ok=4,
                    checks_total=4,
                ),
                _fake_run_result(
                    c2,
                    task,
                    score=8.15,
                    duration_ms=101200,
                    cost=0.2388,
                    checks_ok=4,
                    checks_total=4,
                ),
            ]
        )
        self.push_screen(ResultsScreen())


async def capture_config_select() -> None:
    app = CCCBApp(repo_root=REPO_ROOT)
    async with app.run_test(size=TERM_SIZE) as pilot:
        alpha, beta = _configs()
        for path in (alpha.path, beta.path):
            inp = await _wait_for_config_input(app, pilot)
            inp.value = str(path)
            await pilot.click("#add_config_btn")
            await pilot.pause(0.08)
        app.save_screenshot(
            filename="tui-config-select.svg",
            path=str(OUT_DIR),
        )


async def capture_task_select() -> None:
    app = CCCBApp(repo_root=REPO_ROOT)
    async with app.run_test(size=TERM_SIZE) as pilot:
        alpha, beta = _configs()
        for path in (alpha.path, beta.path):
            inp = await _wait_for_config_input(app, pilot)
            inp.value = str(path)
            await pilot.click("#add_config_btn")
            await pilot.pause(0.06)
        await pilot.click("#next_btn")
        await pilot.pause(0.2)
        app.save_screenshot(
            filename="tui-task-select.svg",
            path=str(OUT_DIR),
        )


async def capture_running() -> None:
    app = SnapRunningApp(repo_root=REPO_ROOT)
    async with app.run_test(size=TERM_SIZE) as pilot:
        await pilot.pause(0.35)
        runner = app.runner
        assert isinstance(runner, PausingStubRunner)
        app.save_screenshot(
            filename="tui-running.svg",
            path=str(OUT_DIR),
        )
        runner.resume_after_screenshot()
        await pilot.pause(0.15)


async def capture_results() -> None:
    app = SnapResultsApp(repo_root=REPO_ROOT)
    async with app.run_test(size=TERM_SIZE) as pilot:
        await pilot.pause(0.25)
        app.save_screenshot(
            filename="tui-results.svg",
            path=str(OUT_DIR),
        )


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    asyncio.run(capture_config_select())
    asyncio.run(capture_task_select())
    asyncio.run(capture_running())
    asyncio.run(capture_results())
    print(f"Wrote SVGs under {OUT_DIR}")


if __name__ == "__main__":
    main()
