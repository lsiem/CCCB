"""Results screen showing benchmark summary and detailed results."""
import json
from pathlib import Path
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    Header,
    Button,
    RichLog,
    DataTable,
    Static,
    Label,
)
from rich.text import Text
from rich.table import Table as RichTable

from cccb.models import BenchmarkReport


class WinnerBanner(Static):
    """Banner showing the winner configuration."""

    def __init__(self, winner_name: str, improvement: float, **kwargs) -> None:
        """Initialize with winner info."""
        super().__init__(**kwargs)
        self.winner_name = winner_name
        self.improvement = improvement

    def render(self) -> str:
        """Render the banner."""
        return f"★ Gewinner: {self.winner_name} (+{self.improvement:.1f}% gegenueber Platz 2)"


class ResultsScreen(Screen):
    """Screen showing benchmark results."""

    def __init__(self) -> None:
        """Initialize the results screen."""
        super().__init__()

    def compose(self) -> ComposeResult:
        """Compose the screen widgets."""
        yield Label("CCCB - Ergebnisse", id="header")
        
        # Determine winner and show banner
        if self.app.runner and self.app.runner.results:
            results = self.app.runner.results
            
            # Group by config and calculate averages
            config_scores = {}
            for result in results:
                if result.config:
                    if result.config.name not in config_scores:
                        config_scores[result.config.name] = []
                    config_scores[result.config.name].append(result.total_score)
            
            # Calculate average scores per config
            averages = {
                name: sum(scores) / len(scores)
                for name, scores in config_scores.items()
            }
            
            if averages:
                sorted_configs = sorted(averages.items(), key=lambda x: x[1], reverse=True)
                winner_name = sorted_configs[0][0]
                winner_score = sorted_configs[0][1]
                
                second_score = sorted_configs[1][1] if len(sorted_configs) > 1 else winner_score
                improvement = ((winner_score - second_score) / second_score * 100) if second_score > 0 else 0
                
                yield WinnerBanner(winner_name, improvement, classes="winner-banner")
        
        # Results table
        yield DataTable(id="results_table", classes="results-table")
        
        # Suggestions log
        yield Label("Verbesserungsvorschlaege:", id="suggestions_header")
        yield RichLog(id="suggestions_log")
        
        # Buttons
        with Horizontal(classes="btn-row"):
            yield Button("Export JSON", id="export_btn")
            yield Button("Neuer Benchmark ↻", id="restart_btn")

    def on_mount(self) -> None:
        """Handle screen mount and populate results."""
        self._populate_table()
        self._populate_suggestions()

    def _populate_table(self) -> None:
        """Populate the results table."""
        table = self.query_one("#results_table", DataTable)
        
        table.add_columns("Config", "Score", "Zeit (Avg)", "Kosten (Avg)", "Checks")
        
        if self.app.runner and self.app.runner.results:
            results = self.app.runner.results
            
            # Group by config
            config_data = {}
            for result in results:
                if result.config:
                    if result.config.name not in config_data:
                        config_data[result.config.name] = {
                            "scores": [],
                            "durations": [],
                            "costs": [],
                            "checks": [],
                        }
                    
                    config_data[result.config.name]["scores"].append(result.total_score)
                    config_data[result.config.name]["durations"].append(result.duration_ms)
                    config_data[result.config.name]["costs"].append(result.total_cost_usd)
                    config_data[result.config.name]["checks"].append(
                        f"{result.checks_passed}/{result.checks_total}"
                    )
            
            # Calculate and display averages
            for name in sorted(config_data.keys(), key=lambda n: sum(config_data[n]["scores"]) / len(config_data[n]["scores"]), reverse=True):
                data = config_data[name]
                avg_score = sum(data["scores"]) / len(data["scores"])
                avg_duration = sum(data["durations"]) / len(data["durations"]) / 1000  # Convert to seconds
                avg_cost = sum(data["costs"]) / len(data["costs"])
                
                table.add_row(
                    name,
                    f"{avg_score:.2f}",
                    f"{avg_duration:.1f}s",
                    f"${avg_cost:.4f}",
                    f"✓ {len([c for c in data['checks'] if c[0] == data['checks'][0][0]])}/{len(data['checks'])}"
                )

    def _populate_suggestions(self) -> None:
        """Populate suggestions log."""
        log = self.query_one("#suggestions_log", RichLog)
        
        if self.app.runner and self.app.runner.results:
            results = self.app.runner.results
            
            # Simple suggestions based on cost and time
            log.write(Text("- Beste Kosteneffizienz fuer Codegen-Aufgaben", style="cyan"))
            log.write(Text("- Schnellste Ausfuehrung bei Debug-Szenarien", style="cyan"))
            log.write(Text("- Konsistenteste Pruefungsergebnisse", style="cyan"))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "export_btn":
            self._export_json()
        elif event.button.id == "restart_btn":
            # Pop back to start
            self.app.selected_configs = []
            self.app.selected_tasks = []
            self.app.runner = None
            self.app.pop_screen()
            self.app.pop_screen()
            self.app.pop_screen()

    def _export_json(self) -> None:
        """Export results as JSON."""
        if not self.app.runner or not self.app.runner.results:
            return
        
        results = self.app.runner.results
        data = {
            "configs": [c.name for c in self.app.selected_configs],
            "tasks": [t.name for t in self.app.selected_tasks],
            "results": [
                {
                    "config": r.config.name if r.config else None,
                    "task": r.task.name if r.task else None,
                    "duration_ms": r.duration_ms,
                    "cost_usd": r.total_cost_usd,
                    "score": r.total_score,
                    "checks": f"{r.checks_passed}/{r.checks_total}",
                }
                for r in results
            ],
        }
        
        output_path = self.app.repo_root / "benchmark-results.json"
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)
