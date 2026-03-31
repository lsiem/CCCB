"""Config selection screen."""
from pathlib import Path
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    Header,
    Button,
    Input,
    ListView,
    ListItem,
    Label,
    TextArea,
    Static,
)

from cccb.models import ConfigProfile
from cccb.screens.task_select import TaskSelectScreen


class ConfigListItem(ListItem):
    """A list item for a config."""

    def __init__(self, config: ConfigProfile, **kwargs) -> None:
        """Initialize with a config profile."""
        super().__init__(**kwargs)
        self.config = config

    def render(self) -> str:
        """Render the config name and description."""
        return f"[bold]{self.config.name}[/bold]\n{self.config.description[:60]}"


class ConfigSelectScreen(Screen):
    """Screen for selecting benchmark configurations."""

    def __init__(self) -> None:
        """Initialize the config selection screen."""
        super().__init__()
        self.configs: list[ConfigProfile] = []
        self.selected_config: ConfigProfile | None = None

    def compose(self) -> ComposeResult:
        """Compose the screen widgets."""
        yield Label("CCCB - Konfigurationen auswaehlen", id="header")
        
        with Horizontal():
            with Vertical(classes="config-input-section"):
                yield Label("Pfad zum Konfig-Verzeichnis:")
                yield Input(
                    placeholder="/path/to/config",
                    id="config_path_input",
                )
                yield Button("Hinzufuegen", id="add_config_btn")
            
            with Vertical(classes="config-list-section"):
                yield Label("Gewaehlte Konfigurationen:")
                yield ListView(id="config_list")
        
        yield Label("Konfig-Preview:", id="preview_header")
        yield TextArea(id="config_preview", read_only=True)
        
        with Horizontal(classes="btn-row"):
            yield Button("Weiter →", id="next_btn", disabled=True)

    def on_mount(self) -> None:
        """Handle screen mount."""
        self.app.selected_configs = []

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "add_config_btn":
            self._add_config()
        elif event.button.id == "next_btn":
            self._next()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission (Enter key)."""
        if event.input.id == "config_path_input":
            self._add_config()

    def _add_config(self) -> None:
        """Add a config from the input field."""
        input_widget = self.query_one("#config_path_input", Input)
        path_str = input_widget.value.strip()
        
        if not path_str:
            return
        
        try:
            path = Path(path_str).expanduser().resolve()
            config = ConfigProfile.from_dir(path)
            
            # Check if already added
            if any(c.name == config.name for c in self.configs):
                return
            
            self.configs.append(config)
            
            # Add to list view
            list_view = self.query_one("#config_list", ListView)
            list_view.append(ConfigListItem(config))
            
            # Clear input
            input_widget.value = ""
            
            # Update button state
            self._update_next_button()
        except FileNotFoundError:
            self.notify(f"Pfad nicht gefunden: {path_str}", severity="error")
        except ValueError as e:
            self.notify(str(e), severity="error")
        except Exception as e:
            self.notify(f"Fehler beim Laden: {e}", severity="error")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle config selection in list view."""
        item = event.list_view.children[event.cursor_line]
        if isinstance(item, ConfigListItem):
            self.selected_config = item.config
            self._update_preview()

    def _update_preview(self) -> None:
        """Update the preview area with selected config info."""
        preview = self.query_one("#config_preview", TextArea)
        
        if self.selected_config:
            preview.text = self.selected_config.description
        else:
            preview.text = ""

    def _update_next_button(self) -> None:
        """Enable next button if >= 2 configs selected."""
        next_btn = self.query_one("#next_btn", Button)
        next_btn.disabled = len(self.configs) < 2

    def _next(self) -> None:
        """Move to task selection screen."""
        self.app.selected_configs = self.configs
        self.app.push_screen(TaskSelectScreen())
