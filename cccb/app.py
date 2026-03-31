"""Main CCCB TUI application."""

from pathlib import Path
from textual.app import App, ComposeResult
from textual.widgets import Header

from cccb.screens.config_select import ConfigSelectScreen


class CCCBApp(App):
    """CCCB Benchmark TUI application."""

    CSS_PATH = str(Path(__file__).resolve().parent / "cccb.tcss")
    TITLE = "CCCB Benchmark"
    BINDINGS = [("q", "quit", "Beenden")]

    def __init__(self, repo_root: Path | None = None):
        """Initialize the app.

        Args:
            repo_root: Root path of the git repository (defaults to cwd)
        """
        super().__init__()
        self.repo_root = repo_root or Path.cwd()
        self.selected_configs = []
        self.selected_tasks = []
        self.runner = None
        self.report = None

    def on_mount(self) -> None:
        """Initialize the app and push the first screen."""
        self.push_screen(ConfigSelectScreen())
