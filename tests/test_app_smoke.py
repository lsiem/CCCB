"""Smoke tests: CCCB Textual app mounts and basic navigation works."""

from pathlib import Path

import pytest
from textual.css.query import NoMatches
from textual.widgets import Button, Input

from cccb.app import CCCBApp
from cccb.screens.config_select import ConfigSelectScreen
from cccb.screens.task_select import TaskSelectScreen

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ALPHA = REPO_ROOT / "docs" / "images" / "fixtures" / "config-alpha"
FIXTURE_BETA = REPO_ROOT / "docs" / "images" / "fixtures" / "config-beta"


@pytest.mark.asyncio
async def test_app_mounts_config_select_screen() -> None:
    app = CCCBApp(repo_root=REPO_ROOT)
    async with app.run_test(size=(100, 30)) as pilot:
        for _ in range(60):
            await pilot.pause(0.05)
            if isinstance(app.screen, ConfigSelectScreen):
                break
        assert isinstance(app.screen, ConfigSelectScreen)
        inp = app.screen.query_one("#config_path_input", Input)
        assert inp is not None


@pytest.mark.asyncio
async def test_config_to_task_screen_with_fixture_configs() -> None:
    assert FIXTURE_ALPHA.is_dir() and FIXTURE_BETA.is_dir(), "fixture configs missing"

    app = CCCBApp(repo_root=REPO_ROOT)
    async with app.run_test(size=(120, 32)) as pilot:
        for _ in range(80):
            await pilot.pause(0.05)
            try:
                app.screen.query_one("#config_path_input", Input)
                break
            except NoMatches:
                continue
        else:
            pytest.fail("config screen did not mount")

        for path in (FIXTURE_ALPHA, FIXTURE_BETA):
            inp = app.screen.query_one("#config_path_input", Input)
            inp.value = str(path)
            await pilot.click("#add_config_btn")
            await pilot.pause(0.25)

        next_btn = app.screen.query_one("#next_btn", Button)
        assert not next_btn.disabled

        await pilot.click("#next_btn")
        await pilot.pause(0.35)

        assert isinstance(app.screen, TaskSelectScreen)
        assert len(app.screen.tasks) >= 1


@pytest.mark.asyncio
async def test_task_filter_codegen_shows_only_codegen_tasks() -> None:
    app = CCCBApp(repo_root=REPO_ROOT)
    async with app.run_test(size=(120, 32)) as pilot:
        for _ in range(80):
            await pilot.pause(0.05)
            try:
                app.screen.query_one("#config_path_input", Input)
                break
            except NoMatches:
                continue

        for path in (FIXTURE_ALPHA, FIXTURE_BETA):
            inp = app.screen.query_one("#config_path_input", Input)
            inp.value = str(path)
            await pilot.click("#add_config_btn")
            await pilot.pause(0.25)
        await pilot.click("#next_btn")
        await pilot.pause(0.35)

        screen = app.screen
        assert isinstance(screen, TaskSelectScreen)
        total = len(screen.tasks)
        assert total >= 1

        await pilot.click("#filter_codegen")
        await pilot.pause(0.2)

        list_view = screen.query_one("#task_list")
        codegen_count = sum(1 for t in screen.tasks if t.category.lower() == "codegen")
        assert codegen_count >= 1
        assert len(list_view.children) == codegen_count

        await pilot.click("#filter_all")
        await pilot.pause(0.1)
        assert len(screen.query_one("#task_list").children) == total
