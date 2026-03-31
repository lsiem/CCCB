# CCCB — Claude Code Config Benchmark

TUI-basiertes Benchmarking-Tool zum Vergleich von Claude Code Konfigurationen (CLAUDE.md, Projektregeln, MCP-Server, Skills).

## Features

- **Konfigurationsvergleich**: Teste verschiedene CLAUDE.md / `.claude/`-Setups gegeneinander
- **YAML-definierte Aufgaben**: Codegen, Debugging, Refactoring mit automatischen Checks
- **Hybrid-Bewertung**: Automatische Checks (pytest, file_exists) + LLM-as-Judge
- **Score-System**: Gewichteter Score aus Check-Ergebnis (40%), Judge-Bewertung (40%), Effizienz (20%)
- **Git Worktree Isolation**: Jeder Benchmark-Durchlauf in isoliertem Worktree
- **Textual TUI**: Interaktive Oberfläche mit Config-Auswahl → Task-Auswahl → Fortschritt → Ergebnisse

## Voraussetzungen

- Python 3.11+
- Git-Repository mit mindestens einem Commit
- Claude Code CLI installiert (`claude-agent-sdk`)

## Installation

```bash
pip install -e ".[dev]"
```

## Verwendung

```bash
# Im Projektverzeichnis mit tasks/ und Konfigurationen:
python -m cccb

# Oder mit explizitem Repo-Pfad:
cccb --repo /pfad/zum/projekt
```

### Konfigurationen vorbereiten

Jede Konfiguration ist ein Verzeichnis mit mindestens einer `CLAUDE.md`:

```
configs/
  minimal/
    CLAUDE.md
  full/
    CLAUDE.md
    .claude/
      settings.json
    config.yaml        # Optional: name, description
```

### Benchmark-Aufgaben

Aufgaben werden als YAML-Dateien in `tasks/` definiert:

```yaml
name: REST API erstellen
category: codegen
description: Implementiere eine FastAPI REST API
prompt: |
  Erstelle eine FastAPI-Anwendung mit CRUD-Endpoints...

checks:
  - type: file_exists
    path: main.py
  - type: command
    run: python -m pytest tests/ -v

judge:
  criteria:
    - "Korrektheit: API-Endpoints funktionieren korrekt"
    - "Code-Struktur: Sauber und modular"
  scale: "1-10"

claude_settings:
  max_turns: 10
  timeout: 300
```

## Score-Berechnung

```
total_score = (check_score × 0.4) + (judge_score × 0.4) + (efficiency × 0.2)
```

- **check_score**: Anteil bestandener automatischer Checks (0–10)
- **judge_score**: LLM-as-Judge Bewertung (1–10)
- **efficiency**: Rang-basiert nach Kosten und Zeit (1–10)

## Entwicklung

```bash
# Tests ausführen
pytest tests/ -v

# Mit Coverage
pytest tests/ --cov=cccb --cov-report=term-missing
```

## Lizenz

ITSC GmbH - Interne Nutzung