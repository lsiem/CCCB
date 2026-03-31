"""Entry point: python -m cccb."""
import sys
from pathlib import Path


def main() -> None:
    """Launch the CCCB Benchmark TUI."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="cccb",
        description="CCCB — Claude Code Config Benchmark",
    )
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path.cwd(),
        help="Pfad zum Git-Repository (Standard: aktuelles Verzeichnis)",
    )
    args = parser.parse_args()

    repo_root = args.repo.resolve()

    # Validate prerequisites
    if not repo_root.is_dir():
        print(f"Fehler: Verzeichnis existiert nicht: {repo_root}", file=sys.stderr)
        sys.exit(1)

    git_dir = repo_root / ".git"
    if not git_dir.exists():
        print(
            f"Fehler: Kein Git-Repository gefunden in {repo_root}\n"
            "CCCB benoetigt ein Git-Repository fuer Worktree-Isolation.\n"
            "Initialisiere mit: git init && git add . && git commit -m 'init'",
            file=sys.stderr,
        )
        sys.exit(1)

    tasks_dir = repo_root / "tasks"
    if not tasks_dir.exists():
        print(
            f"Hinweis: Kein 'tasks/' Verzeichnis in {repo_root}\n"
            "Benchmark-Aufgaben werden aus tasks/*.yaml geladen.",
            file=sys.stderr,
        )

    from cccb.app import CCCBApp

    app = CCCBApp(repo_root=repo_root)
    app.run()


if __name__ == "__main__":
    main()
