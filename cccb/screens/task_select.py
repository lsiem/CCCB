"""Task selection screen."""
from pathlib import Path
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    Header,
    Button,
    ListView,
    ListItem,
    Label,
    Static,
)

from cccb.models import TaskDefinition
from cccb.runner import BenchmarkRunner
from cccb.screens.running import RunningScreen


class TaskListItem(ListItem):
    """A list item for a task."""

    def __init__(self, task: TaskDefinition, selected: bool = False, **kwargs) -> None:
        """Initialize with a task definition."""
        super().__init__(**kwargs)
        self.task_def = task
        self.selected = selected

    def render(self) -> str:
        """Render the task with category tag and description."""
        prefix = "[bold][green]✓[/green][/bold] " if self.selected else "  "
        return f"{prefix}[{self.task_def.category}] {self.task_def.name}\n{self.task_def.description[:60]}"


class CounterLabel(Static):
    """Counter label for runs calculation."""

    def __init__(self, task_count: int, config_count: int, **kwargs) -> None:
        """Initialize with counts."""
        super().__init__(**kwargs)
        self.task_count = task_count
        self.config_count = config_count

    def render(self) -> str:
        """Render the counter."""
        runs = self.task_count * self.config_count
        return f"{self.task_count} Aufgaben × {self.config_count} Configs = {runs} Durchlaeufe"


class TaskSelectScreen(Screen):
    """Screen for selecting benchmark tasks."""

    def __init__(self) -> None:
        """Initialize the task selection screen."""
        super().__init__()
        self.tasks: list[TaskDefinition] = []
        self.selected_tasks: list[TaskDefinition] = []
        self.current_filter = "Alle"

    def _load_tasks(self) -> None:
        """Load tasks from YAML files."""
        tasks_dir = self.app.repo_root / "tasks"
        
        if not tasks_dir.exists():
            return
        
        # Load all YAML files recursively
        for yaml_file in tasks_dir.rglob("*.yaml"):
            try:
                task = TaskDefinition.from_yaml(yaml_file)
                self.tasks.append(task)
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Task-Datei konnte nicht geladen werden: {yaml_file}: {e}")

    def compose(self) -> ComposeResult:
        """Compose the screen widgets."""
        # Load tasks now that self.app is available
        self._load_tasks()

        yield Label("CCCB - Aufgaben auswaehlen", id="header")

        with Horizontal(classes="task-filter"):
            for category in ["Alle", "Codegen", "Debugging", "Refactoring"]:
                yield Button(
                    category,
                    id=f"filter_{category}",
                    variant="primary" if category == "Alle" else "default",
                )

        yield ListView(id="task_list")

        config_count = len(self.app.selected_configs)
        yield CounterLabel(len(self.tasks), config_count, id="counter")
        
        with Horizontal(classes="btn-row"):
            yield Button("← Zurueck", id="back_btn")
            yield Button("Start ▶", id="start_btn")

    def on_mount(self) -> None:
        """Handle screen mount."""
        self._populate_task_list()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id
        
        if button_id == "back_btn":
            self.app.pop_screen()
        elif button_id == "start_btn":
            self._start_benchmark()
        elif button_id and button_id.startswith("filter_"):
            category = button_id.replace("filter_", "")
            self._set_filter(category)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle task selection in list view."""
        item = event.list_view.children[event.cursor_line]
        if isinstance(item, TaskListItem):
            item.selected = not item.selected
            if item.selected:
                self.selected_tasks.append(item.task_def)
            else:
                self.selected_tasks.remove(item.task_def)
            
            # Refresh list
            self._populate_task_list()

    def _populate_task_list(self) -> None:
        """Populate the task list view with filtered tasks."""
        list_view = self.query_one("#task_list", ListView)
        list_view.clear()
        
        filtered = self.tasks
        if self.current_filter != "Alle":
            filtered = [t for t in self.tasks if t.category == self.current_filter]
        
        for task in filtered:
            selected = task in self.selected_tasks
            list_view.append(TaskListItem(task, selected=selected))

    def _set_filter(self, category: str) -> None:
        """Set the task filter."""
        self.current_filter = category
        
        # Update button states
        for cat in ["Alle", "Codegen", "Debugging", "Refactoring"]:
            btn = self.query_one(f"#filter_{cat}", Button)
            btn.variant = "primary" if cat == category else "default"
        
        # Refresh list
        self._populate_task_list()

    def _start_benchmark(self) -> None:
        """Start the benchmark run."""
        if not self.selected_tasks:
            return
        
        self.app.selected_tasks = self.selected_tasks
        
        # Create runner
        runner = BenchmarkRunner(
            repo_root=self.app.repo_root,
            configs=self.app.selected_configs,
            tasks=self.selected_tasks,
        )
        self.app.runner = runner
        
        # Push running screen
        self.app.push_screen(RunningScreen())
