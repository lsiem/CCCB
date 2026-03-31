# CCCB — Claude Code Config Benchmark

## Design Specification

**Datum:** 2026-03-30
**Autor:** Lasse Siemoneit + Claude
**Status:** Draft

---

## 1. Übersicht

CCCB ist ein TUI-basiertes Python-Tool, das Claude Code Konfigurationen gegeneinander benchmarkt. Der User wählt Konfigurationsverzeichnisse und YAML-definierte Aufgaben aus, das Tool führt alle Kombinationen sequentiell durch und zeigt am Ende eine Vergleichstabelle mit Scores und Verbesserungsvorschlägen.

**Ziel:** Herausfinden, welche Kombination aus CLAUDE.md, Projektregeln, MCP-Servern und Skills die besten Ergebnisse liefert — gemessen an Qualität, Geschwindigkeit und Token-Effizienz.

## 2. Kernentscheidungen

| Entscheidung | Gewählt | Alternativen verworfen |
|---|---|---|
| Vergleichsmodus | Konfigurationen gegeneinander (A/B/C) | Einzelbewertung, Turnier-Stil |
| Durchlauf-Modus | Sequentiell (alle Kombinationen) | Turnier (Kopf-an-Kopf) |
| Aufgaben-Definition | YAML-Dateien (erweiterbar) | Fest eingebaut, Hybrid |
| Bewertung | Hybrid: Auto-Checks + LLM-as-Judge | Nur regelbasiert, nur LLM |
| Konfigurations-Format | Verzeichnis-basiert | Overlay-basiert |
| Isolation | Git Worktrees (isolierte Arbeitsverzeichnisse, shared .git) | Branches, Temporäre Verzeichnisse |
| Wiederholungen | Einzeldurchlauf (manuell wiederholbar) | Konfigurierbare n-Wiederholungen |
| Claude Code Aufruf | Claude Agent SDK für Python (`claude-agent-sdk`) — async `query()` mit `ClaudeAgentOptions` | Raw subprocess, API direkt |
| Architektur | Monolithische Textual-App | CLI+TUI getrennt, Plugin-Architektur |
| UI-Sprache | Deutsch | Englisch, Gemischt |

## 3. Tech-Stack

- **Python 3.11+** — Hauptsprache (benötigt `asyncio.timeout()`)
- **Textual** — TUI-Framework (Screens mit `push_screen`/`pop_screen`, Widgets, CSS-Styling, `@work(exclusive=True)`-Workers)
- **PyYAML** — Aufgaben-Definitionen parsen
- **claude-agent-sdk** (`pip install claude-agent-sdk`) — Offizielles Python SDK für Claude Code, wraps CLI mit async `query()` Generator, `ClaudeAgentOptions`, strukturiertem Message-Streaming, Error-Handling (`CLINotFoundError`, `ProcessError`, `CLIJSONDecodeError`). Bundled Claude Code CLI automatisch.
- **Git** — via subprocess für Isolation (**Worktrees**: `git worktree add`, shared `.git` Objekt-Speicher, echte Verzeichnis-Isolation)
- **Keine Datenbank** — Ergebnisse leben im Git-Repo und als JSON

**Sprachkonvention:** Code und Bezeichner in Englisch, TUI-Oberfläche und Docs in Deutsch. Kommentare im Code auf Englisch.

## 4. Projektstruktur

```
cccb/
├── __main__.py          # Entry point: python -m cccb
├── app.py               # Textual App (Screens, Navigation)
├── models.py            # Datenmodelle (Task, Config, Result, Metrics)
├── runner.py            # Benchmark-Engine (Orchestrierung der Durchläufe)
├── executor.py          # Claude Code Aufrufe via claude-agent-sdk
├── isolation.py         # Git Worktree Isolation (worktree add/remove, diff)
├── checker.py           # Automatische Checks (exit codes, file exists, lint)
├── judge.py             # LLM-as-Judge Bewertung via Claude CLI
├── scorer.py            # Score-Berechnung & Aggregation
├── screens/
│   ├── config_select.py # Screen: Konfigurationen auswählen
│   ├── task_select.py   # Screen: Aufgaben auswählen
│   ├── running.py       # Screen: Live-Ansicht während Benchmark
│   └── results.py       # Screen: Ergebnis-Dashboard & Vergleich
├── widgets/
│   ├── metric_card.py   # Widget: einzelne Metrik-Anzeige
│   ├── comparison.py    # Widget: Vergleichstabelle
│   └── detail_view.py   # Widget: Detail-Ansicht eines Durchlaufs
└── tasks/               # Mitgelieferte Beispiel-Aufgaben
    ├── codegen/
    ├── debugging/
    └── refactoring/
```

## 5. Datenmodelle

### 5.1 TaskDefinition

Repräsentiert eine Benchmark-Aufgabe, geladen aus einer YAML-Datei.

```python
@dataclass
class SetupFile:
    source: str   # Pfad relativ zum Task-Verzeichnis
    target: str   # Zielpfad im Testprojekt

@dataclass
class Check:
    type: str              # "command" | "file_exists"
    run: str | None        # Shell-Kommando (bei type=command)
    path: str | None       # Dateipfad (bei type=file_exists)
    expect_exit_code: int  # Erwarteter Exit-Code (bei type=command)

@dataclass
class JudgeCriteria:
    criteria: list[str]    # Liste der Bewertungskriterien
    scale: str             # z.B. "1-10"

@dataclass
class ClaudeSettings:
    max_turns: int                    # Max. Agentic-Turns
    allowed_tools: list[str] | None   # Erlaubte Tools (optional)
    timeout: int | None               # Timeout in Sekunden (Default: 300)

@dataclass
class TaskDefinition:
    name: str
    category: str          # "codegen" | "debugging" | "refactoring"
    description: str
    prompt: str
    setup_files: list[SetupFile]
    checks: list[Check]
    judge: JudgeCriteria
    claude_settings: ClaudeSettings
```

### 5.2 ConfigProfile

Repräsentiert eine Claude Code Konfiguration — ein Verzeichnis mit CLAUDE.md und optional weiteren Dateien.

```python
@dataclass
class ConfigProfile:
    name: str
    path: Path             # Verzeichnis mit CLAUDE.md, .claude/, etc.
    description: str       # Aus optionaler config.yaml im Verzeichnis

# Validierung: Ein gültiges Config-Verzeichnis MUSS eine nicht-leere CLAUDE.md enthalten.
# Optional: .claude/ Verzeichnis, config.yaml (für name/description).
# Wenn config.yaml fehlt: name = Verzeichnisname, description = erste Zeile der CLAUDE.md.
```

### 5.3 RunResult

Ergebnis eines einzelnen Durchlaufs (eine Konfiguration × eine Aufgabe).

```python
@dataclass
class CheckResult:
    check: Check
    passed: bool
    output: str            # Stdout/Stderr des Check-Kommandos

@dataclass
class RunResult:
    config: ConfigProfile
    task: TaskDefinition
    # Automatisch aus Claude CLI JSON:
    duration_ms: int
    duration_api_ms: int     # Claude CLI Feldname: duration_api_ms
    total_cost_usd: float
    num_turns: int
    session_id: str
    # Automatische Checks:
    checks_passed: int
    checks_total: int
    check_details: list[CheckResult]
    # LLM-as-Judge:
    judge_scores: dict[str, float]   # Kriterium → 1-10
    judge_average: float
    # Aggregiert:
    total_score: float
    # Git-Referenz:
    worktree_path: str     # .cccb-bench/<config>/<task>/
    branch_name: str
    commit_hash: str
```

### 5.4 BenchmarkReport

Gesamtergebnis eines Benchmark-Laufs.

```python
@dataclass
class BenchmarkReport:
    configs: list[ConfigProfile]
    tasks: list[TaskDefinition]
    results: list[RunResult]
    winner: ConfigProfile
    summary: str           # LLM-generierte Verbesserungsvorschläge
```

## 6. Aufgaben-Format (YAML)

Jede Aufgabe ist eine YAML-Datei im `tasks/`-Verzeichnis.

```yaml
name: "REST API erstellen"
category: "codegen"
description: "Erstelle eine vollständige REST API mit FastAPI inkl. CRUD-Endpunkte, Validierung und Error Handling"

prompt: |
  Erstelle eine REST API mit FastAPI für eine Aufgabenverwaltung (Todo-App).
  Anforderungen:
  - CRUD-Endpunkte (GET, POST, PUT, DELETE) für /todos
  - Pydantic-Modelle für Request/Response Validierung
  - Proper Error Handling (404, 422)
  - In-Memory Storage (kein DB nötig)
  - Schreibe Tests mit pytest und httpx

setup_files:
  - source: "fixtures/rest-api/requirements.txt"
    target: "requirements.txt"

checks:
  - type: "command"
    run: "pip install -r requirements.txt --break-system-packages -q"
    expect_exit_code: 0
  - type: "file_exists"
    path: "main.py"
  - type: "command"
    run: "python -m py_compile main.py"
    expect_exit_code: 0
  - type: "command"
    run: "python -m pytest tests/ -v"
    expect_exit_code: 0

judge:
  criteria:
    - "Korrektheit: Funktionieren alle CRUD-Endpunkte wie spezifiziert?"
    - "Validierung: Werden ungültige Eingaben sauber abgefangen?"
    - "Code-Struktur: Ist der Code gut organisiert und idiomatisch?"
    - "Vollständigkeit: Sind alle Anforderungen umgesetzt inkl. Tests?"
  scale: "1-10"

claude_settings:
  max_turns: 15
  allowed_tools:
    - "Edit"
    - "Write"
    - "Bash(python *)"
    - "Bash(pip *)"
    - "Bash(pytest *)"
```

Aufgaben sollen bewusst auch sehr anspruchsvolle Szenarien abdecken — komplexe Refactorings, subtile Bugs, Multi-File Code-Generierung — um Konfigurationsunterschiede deutlich sichtbar zu machen.

## 7. TUI-Flow & Screens

Der User durchläuft vier Screens:

### 7.1 Config Select Screen

- Dateisystem-Browser oder Pfadeingabe für Konfigurationsverzeichnisse
- Checkbox-Liste der gefundenen Konfigurationen
- Preview: zeigt CLAUDE.md-Inhalt und enthaltene Dateien
- Mindestens 2 Konfigurationen müssen ausgewählt werden
- Button: "Weiter →"

### 7.2 Task Select Screen

- Lädt alle YAML-Dateien aus dem Tasks-Verzeichnis
- Filter-Buttons nach Kategorie (codegen, debugging, refactoring)
- Checkbox-Liste mit Aufgabenname und Beschreibung
- Anzeige: "X Aufgaben × Y Configs = Z Durchläufe"
- Buttons: "← Zurück", "Start ▶"

### 7.3 Running Screen

- Gesamtfortschrittsbalken (X von Z Durchläufen)
- Aktuelle Kombination: Config-Name × Task-Name
- Liste der abgeschlossenen Durchläufe mit Kurzinfos (Dauer, Kosten, Checks)
- Laufender Kosten-Ticker
- Abbrechen-Button (stoppt nach aktuellem Durchlauf, zeigt bisherige Ergebnisse)
- Verwendet genau einen Textual `@work(exclusive=True)`-Worker für sequentielle, nicht-blockierende Ausführung
- Worker postet `RunCompleted`-Messages an die TUI für Live-Updates
- Bei Worker-Exception: Fehlermeldung in der TUI, Benchmark wird gestoppt, bisherige Ergebnisse bleiben erhalten

### 7.4 Results Screen

- Vergleichstabelle (DataTable): Config | Score | Zeit | Kosten | Checks bestanden
- Gewinner-Markierung (höchster Durchschnittsscore)
- Delta-Anzeige: "+25% Score, -26% Kosten"
- Verbesserungsvorschläge (LLM-generiert)
- Detail-Ansicht pro Durchlauf (aufklappbar)
- Export-Button (JSON-Report)
- Button: "Neuer Benchmark ↻"

## 8. Benchmark-Engine Flow

```
1. Runner liest ausgewählte Configs + Tasks
2. Erzeugt Matrix: [(config_a, task_1), (config_a, task_2), ..., (config_n, task_m)]
3. Für jede Kombination:
   a) isolation.py: Git Worktree erstellen (.cccb-bench/<config>/<task>/)
   b) isolation.py: Config-Dateien + Task-Setup-Dateien in Worktree kopieren
   c) executor.py: Claude Code via Agent SDK aufrufen:
      async for message in query(
          prompt=task.prompt,
          options=ClaudeAgentOptions(
              allowed_tools=task.allowed_tools,
              permission_mode="dangerouslySkipPermissions",
              max_turns=task.max_turns,
              cwd=worktree_path,
          )
      )
   d) SDK-Messages streamen → Echtzeit-Updates an TUI, Metriken sammeln
   e) checker.py: Automatische Checks im Worktree ausführen (pytest, compile, file_exists)
   f) judge.py: LLM-as-Judge via Agent SDK (separater query()-Aufruf mit
      strukturierter 1-10 Bewertung pro Kriterium)
   g) scorer.py: Alles aggregieren → Gesamtscore
   h) isolation.py: Git-Commit im Worktree mit Ergebnis-Metadaten
4. Ergebnis-Objekte an Results-Screen übergeben
```

### 8.1 executor.py — Claude Code Aufruf via Agent SDK

Verwendet das offizielle `claude-agent-sdk` Python-Paket statt raw subprocess. Die `query()`-Funktion liefert einen async Iterator von Messages.

```python
from claude_agent_sdk import (
    query, ClaudeAgentOptions,
    AssistantMessage, ToolUseBlock, ToolResultBlock, TextBlock,
    CLINotFoundError, ProcessError, CLIJSONDecodeError,
)
import asyncio

async def execute_task(task: TaskDefinition, working_dir: Path) -> dict:
    """Führt eine Benchmark-Aufgabe via Claude Agent SDK aus."""
    options = ClaudeAgentOptions(
        allowed_tools=task.claude_settings.allowed_tools or ["Read", "Write", "Edit", "Bash"],
        permission_mode="dangerouslySkipPermissions",
        max_turns=task.claude_settings.max_turns,
        cwd=str(working_dir),
    )

    messages = []
    try:
        async for message in query(prompt=task.prompt, options=options):
            messages.append(message)
            # Echtzeit-Monitoring: Tool-Nutzung tracken
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, ToolUseBlock):
                        yield {"event": "tool_use", "tool": block.name}
    except CLINotFoundError:
        raise RuntimeError("Claude Code CLI nicht gefunden. pip install --force-reinstall claude-agent-sdk")
    except ProcessError as e:
        yield {"event": "error", "exit_code": e.exit_code}
    except CLIJSONDecodeError as e:
        yield {"event": "parse_error", "line": e.line}
    except asyncio.TimeoutError:
        # Timeout-Handling: partielle Ergebnisse bleiben erhalten
        yield {"event": "timeout"}

    # Ergebnis extrahieren aus dem letzten ResultMessage
    # Die SDK liefert strukturierte Messages inkl. Kosten/Dauer/Turns
```

**Timeout-Handling:** `asyncio.timeout(task.claude_settings.timeout or 300)` wrapping den `async for`-Loop. Bei Timeout bleiben partielle Dateien im Worktree erhalten und Checks laufen trotzdem.

Das Working Directory (Worktree) enthält die CLAUDE.md und `.claude/`-Ordner aus dem Konfigurationsverzeichnis, plus die Setup-Dateien aus der Aufgabe.

**SDK Message Types** (Referenz: claude-agent-sdk Docs):
- `AssistantMessage` — enthält `TextBlock`, `ToolUseBlock` Content-Blöcke
- `ToolResultBlock` — Ergebnis einer Tool-Ausführung (`tool_use_id`, `content`, `is_error`)
- `SystemMessage` (subtype `init`) — enthält `slash_commands` und Session-Info

**Metriken-Extraktion:** Das SDK liefert `total_cost_usd`, `duration_ms`, `duration_api_ms`, `num_turns`, `session_id` als Teil der Stream-Metadaten. Bei `ProcessError` (is_error): Kosten und Dauer werden trotzdem erfasst, check_score = 0, Judge wird aufgerufen.

### 8.2 judge.py — LLM-as-Judge

Separater Claude Code Aufruf mit `--json-schema` für strukturierte Bewertung:

```python
from claude_agent_sdk import query, ClaudeAgentOptions

schema = {
    "type": "object",
    "properties": {
        "scores": {
            "type": "object",
            "description": "Bewertung pro Kriterium (1-10)",
            "additionalProperties": {"type": "number", "minimum": 1, "maximum": 10}
        },
        "reasoning": {
            "type": "string",
            "description": "Kurze Begründung der Bewertung"
        }
    },
    "required": ["scores", "reasoning"]
}

# Judge-Aufruf via Agent SDK — max_turns=1, keine Tools nötig
options = ClaudeAgentOptions(
    permission_mode="dangerouslySkipPermissions",
    max_turns=1,
    cwd=str(working_dir),
    allowed_tools=[],  # Judge braucht keine Tools
    # json_schema wird als CLI-Argument durchgereicht
)

async for message in query(prompt=judge_prompt, options=options):
    # Strukturiertes JSON-Ergebnis parsen
    ...
```

**Judge-Prompt Template:**

```
Du bewertest Code, der von einem KI-Coding-Assistenten generiert wurde.

## Aufgabe
{task.description}

## Prompt an den Assistenten
{task.prompt}

## Generierter Code (git diff vom Setup zum Ergebnis)
{git_diff_output}

## Bewertungskriterien
{for criterion in task.judge.criteria}
- {criterion}
{endfor}

## Bewertungsanker
- 1-2: Völlig unbrauchbar, grundlegend falsch
- 3-4: Ansatz erkennbar, aber wesentliche Mängel
- 5-6: Funktioniert grundsätzlich, erfüllt Anforderungen teilweise
- 7-8: Gute Qualität, erfüllt alle Anforderungen solide
- 9-10: Exzellent, übertrifft Erwartungen in Eleganz/Effizienz

Bewerte jeden Kriterium einzeln auf der Skala 1-10.
```

Der `git_diff_output` wird erzeugt via `git diff <setup-commit>..<result-commit>` im Branch des jeweiligen Durchlaufs. Bei leerem Diff (kein Code generiert) oder Diff > 50KB wird der Diff gekürzt und der Judge entsprechend informiert.

### 8.3 isolation.py — Git Worktree Isolation

**Warum Worktrees statt Branches?**
- Echte Verzeichnis-Isolation: Jeder Durchlauf hat sein eigenes Dateisystem-Verzeichnis
- Kein Checkout-Racing: Hauptverzeichnis bleibt unberührt
- Shared `.git` Objekt-Speicher: Kein Kopier-Overhead
- Zukunftssicher: Parallele Durchläufe wären möglich ohne Git-Konflikte

**Voraussetzungen:**
- Gültiges Git-Repository mit mindestens einem Commit
- Gültiger HEAD auf master/main

**Cleanup vor Benchmark-Start:**
- Alle Worktrees unter `.cccb-bench/` werden entfernt (`git worktree remove --force`)
- Zugehörige Branches mit Prefix `bench/` werden gelöscht
- User wird gewarnt wenn Worktrees mit uncommitted changes existieren

```
Vor jedem Durchlauf:
  1. Worktree-Pfad bestimmen: .cccb-bench/<config-name>/<task-slug>/
  2. git worktree add .cccb-bench/<config>/<task> -b bench/<config>/<task> HEAD
     → Erstellt isoliertes Arbeitsverzeichnis + neuen Branch
     → Bei Namenskollision: Suffix -2, -3, ... (max 5 Versuche)
  3. Im Worktree-Verzeichnis:
     a) Konfigurationsdateien kopieren (CLAUDE.md, .claude/)
        → Task-Setup-Dateien überschreiben NICHT CLAUDE.md
        → Pfade werden validiert (kein Path Traversal, muss unter Worktree-Root liegen)
     b) git add -A && git commit -m "Setup: <config> x <task>"

Nach Claude Code Durchlauf (oder Timeout):
  4. Im Worktree-Verzeichnis:
     git add -A && git commit -m "Result: <config> x <task> [score: X.X]"
     → Bei Timeout: Commit-Message enthält [TIMEOUT]
     → Bei is_error: Commit-Message enthält [ERROR]

Nach Benchmark-Ende (optional):
  5. git worktree remove .cccb-bench/<config>/<task>
     → Oder: Worktrees erhalten für nachträgliche Inspektion
     → User kann git diff zwischen Worktree-Branches machen

Ergebnis: Jeder Durchlauf hat ein eigenes Verzeichnis + Branch mit Setup-Commit und Result-Commit.
Das Hauptverzeichnis wird nie verändert.
```

**Checks und Claude Code laufen im Worktree-Verzeichnis** (cwd = `.cccb-bench/<config>/<task>/`). Umgebungsvariablen werden vom System geerbt. Checks sollen relative Pfade verwenden.

## 9. Score-Berechnung

### 9.1 Pro Durchlauf

```
check_score  = (checks_passed / checks_total) * 10      # 0-10
               → Bei 0 Checks: check_score = 0 (nur Judge zählt, Gewichtung angepasst)

judge_score  = Durchschnitt der LLM-Judge-Scores          # 1-10
               → Explizit: sum(scores.values()) / len(scores)

effizienz    = Kombination aus Kosten- und Zeit-Effizienz  # 1-10
               Berechnung pro Task (nicht global):
               cost_rank = Rang der Config nach Kosten (günstigste = 1)
               time_rank = Rang der Config nach Zeit (schnellste = 1)
               effizienz = 10 - ((cost_rank + time_rank - 2) / (2 * (n_configs - 1))) * 9
               → Bei nur 1 Config: effizienz = 5 (neutral)
               → Bei Timeout: effizienz = 1 (schlechtester Wert)

total_score = (check_score * 0.4)
            + (judge_score * 0.4)
            + (effizienz   * 0.2)
```

**Gewichtung ist konfigurierbar** — die Defaults priorisieren Korrektheit und Qualität gleich, Effizienz als Bonus.

### 9.2 Pro Konfiguration

Durchschnitt über alle Aufgaben ergibt den Gesamt-Score der Konfiguration.

### 9.3 Gewinner & Verbesserungsvorschläge

Der Gewinner ist die Konfiguration mit dem höchsten Durchschnittsscore. Verbesserungsvorschläge werden via LLM generiert:

```
Prompt: "Du bist ein Claude Code Konfigurationsberater. Hier sind die
Benchmark-Ergebnisse: [alle RunResults als JSON]. Analysiere warum
{winner} besser abschneidet als die anderen Konfigurationen. Gib 3-5
konkrete, umsetzbare Verbesserungsvorschläge für die schwächeren
Konfigurationen."
```

## 10. Error Handling

### 10.1 Fehlertypen und Verhalten

| Fehler | Verhalten | Score-Auswirkung |
|---|---|---|
| **Claude Code Timeout** | `asyncio.timeout()` → Partielle Dateien bleiben im Worktree. Checks laufen trotzdem. Git-Commit mit `[TIMEOUT]`. | check_score normal, judge normal, effizienz = 1 |
| **Claude Code `ProcessError`** | SDK wirft `ProcessError(exit_code)`. Kosten/Dauer werden erfasst. Checks laufen (wahrscheinlich 0/n). Judge wird aufgerufen. | check_score normal (wahrscheinlich 0), judge normal |
| **`CLINotFoundError`** | Claude Code CLI nicht installiert. Benchmark wird komplett abgebrochen mit Installationshinweis. | Fatal — kein Benchmark möglich |
| **Git Worktree-Kollision** | Suffix -2, -3, ... (max 5 Versuche), dann Fatal Error für diesen Durchlauf | Durchlauf übersprungen |
| **YAML-Parsing-Fehler** | Task wird übersprungen mit Warnung in der TUI | Task nicht gewertet |
| **Netzwerk/API-Fehler** | Retry: 3 Versuche, Backoff 1s → 2s → 4s. Bedingung: Connection Refused, Timeout, HTTP 5xx | Nach 3 Fehlschlägen: Durchlauf als fehlgeschlagen (Score 0) |
| **Abbruch durch User** | Aktueller Durchlauf läuft zu Ende, dann Stop. Bisherige Ergebnisse werden angezeigt. | Nur abgeschlossene Durchläufe gewertet |

### 10.2 Logging

Alle Fehler werden nach `~/.cccb/logs/benchmark-<timestamp>.log` geschrieben. Inhalt: Fehlertyp, betroffene Config/Task, stderr-Auszug (erste 500 Zeichen), Zeitstempel. In der TUI erscheint eine Kurzwarnung mit Verweis auf die Log-Datei.

### 10.3 Config-Validierung

Beim Laden eines Config-Verzeichnisses wird geprüft:
- CLAUDE.md existiert und ist nicht leer
- Keine symbolischen Links außerhalb des Verzeichnisses
- Optional: .claude/settings.json ist valides JSON

## 11. Nicht im Scope (bewusst weggelassen)

- Parallele Durchläufe (MVP bleibt sequentiell, aber Worktree-Architektur ermöglicht spätere Parallelisierung ohne Umbau)
- Web-Frontend (TUI reicht)
- Datenbank (Git + JSON reichen)
- Plugin-System (interne Module reichen)
- Konfigurierbare Wiederholungen mit Statistik (kann manuell wiederholt werden)
- Automatisches Setup von MCP-Servern (User muss das selbst vorbereiten)
