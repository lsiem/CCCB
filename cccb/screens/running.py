"""Running screen showing benchmark progress."""
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    Header,
    Button,
    ProgressBar,
    Label,
    RichLog,
    Static,
)
from textual.worker import Worker
from rich.text import Text
import asyncio

from cccb.runner import RunEvent
from cccb.screens.results import ResultsScreen


class CostTicker(Static):
    """Widget showing accumulated cost."""

    DEFAULT_CSS = """
    CostTicker {
        width: 1fr;
        height: 1;
        content-align: right middle;
    }
    """

    def __init__(self, cost: float = 0.0, **kwargs) -> None:
        """Initialize cost ticker."""
        super().__init__(**kwargs)
        self.cost = cost

    def render(self) -> str:
        """Render the cost."""
        return f"Kosten: ${self.cost:.3f}"

    def update_cost(self, amount: float) -> None:
        """Update and display the cost."""
        self.cost = amount
        self.update(self.render())


class RunningScreen(Screen):
    """Screen showing benchmark progress and results."""

    def __init__(self) -> None:
        """Initialize the running screen."""
        super().__init__()
        self.total_cost = 0.0
        self.current_run = 0
        self.total_runs = 0

    def compose(self) -> ComposeResult:
        """Compose the screen widgets."""
        yield Label("CCCB - Benchmark wird ausgefuehrt", id="header")
        
        with Vertical(classes="progress-section"):
            yield Label("Fortschritt:", id="progress_label")
            yield ProgressBar(id="progress_bar", total=100)
            yield Label("", id="current_run_label")
            yield CostTicker(id="cost_ticker")
        
        yield RichLog(id="run_log", classes="run-log")
        
        yield Button("Abbrechen", id="cancel_btn")

    def on_mount(self) -> None:
        """Start the benchmark worker."""
        self.run_worker(self._run_benchmark())

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "cancel_btn":
            if self.app.runner:
                self.app.runner.cancel()

    async def _run_benchmark(self) -> None:
        """Run the benchmark and handle events."""
        if not self.app.runner:
            self.app.pop_screen()
            return
        
        log = self.query_one("#run_log", RichLog)
        progress = self.query_one("#progress_bar", ProgressBar)
        cost_ticker = self.query_one("#cost_ticker", CostTicker)
        current_label = self.query_one("#current_run_label", Label)
        
        try:
            async for event in self.app.runner.run():
                if event.type == "run_start":
                    self.total_runs = event.total_runs
                    progress.total = event.total_runs
                    self.current_run = event.run_index
                    current_label.update(f"Config: {event.config_name} x Task: {event.task_name}")
                
                elif event.type == "run_complete":
                    if event.result:
                        status = "✓" if event.result.total_score >= 7.0 else "✗"
                        duration_s = event.result.duration_ms / 1000
                        cost_str = f"${event.result.total_cost_usd:.4f}"
                        checks_str = f"{event.result.checks_passed}/{event.result.checks_total}"
                        
                        msg = f"{status} {event.config_name} x {event.task_name}: {duration_s:.1f}s, {cost_str}, {checks_str}"
                        log.write(Text(msg))
                        
                        self.total_cost += event.result.total_cost_usd
                        cost_ticker.update_cost(self.total_cost)
                    
                    progress.update(completed=event.run_index)
                
                elif event.type == "run_error":
                    msg = f"✗ ERROR: {event.config_name} x {event.task_name}: {event.error}"
                    log.write(Text(msg, style="red"))
                    progress.update(completed=event.run_index)
                
                elif event.type == "benchmark_done":
                    # Push results screen
                    self.app.push_screen(ResultsScreen())
                    return
        
        except Exception as e:
            log.write(Text(f"ERROR: {str(e)}", style="red"))
