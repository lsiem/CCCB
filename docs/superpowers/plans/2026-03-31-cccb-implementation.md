# CCCB Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a TUI-based Python tool that benchmarks Claude Code configurations against each other using YAML-defined tasks, hybrid evaluation (auto-checks + LLM-as-Judge), and git worktree isolation.

**Architecture:** Monolithic Textual app with 4 screens (Config Select → Task Select → Running → Results). Core engine modules (isolation, executor, checker, judge, scorer) are orchestrated by a runner. Claude Code is invoked via the official `claude-agent-sdk` Python package. Each benchmark run creates isolated git worktrees per config×task combination.

**Tech Stack:** Python 3.10+, Textual (TUI), claude-agent-sdk (Claude Code), PyYAML, Git (worktrees via subprocess)

**Spec:** `docs/superpowers/specs/2026-03-30-cccb-design.md`

---

## Chunk 1: Project Setup & Data Models

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `cccb/__init__.py`
- Create: `cccb/__main__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "cccb"
version = "0.1.0"
description = "Claude Code Config Benchmark — TUI tool to compare Claude Code configurations"
requires-python = ">=3.11"
dependencies = [
    "textual>=1.0.0",
    "pyyaml>=6.0",
    "claude-agent-sdk>=0.1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-asyncio>=0.23",
    "pytest-cov>=4.0",
]

[project.scripts]
cccb = "cccb.__main__:main"
```

- [ ] **Step 2: Create cccb/__init__.py**

```python
"""CCCB — Claude Code Config Benchmark."""
```

- [ ] **Step 3: Create cccb/__main__.py**

```python
"""Entry point: python -m cccb."""


def main() -> None:
    from cccb.app import CCCBApp

    app = CCCBApp()
    app.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Create tests/__init__.py and tests/conftest.py**

```python
# tests/__init__.py — empty

# tests/conftest.py
import pytest
from pathlib import Path

@pytest.fixture
def tmp_repo(tmp_path: Path) -> Path:
    """Create a minimal git repo for testing."""
    import subprocess
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=tmp_path, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path, check=True, capture_output=True,
    )
    readme = tmp_path / "README.md"
    readme.write_text("# Test Repo\n")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=tmp_path, check=True, capture_output=True,
    )
    return tmp_path


@pytest.fixture
def sample_task_yaml(tmp_path: Path) -> Path:
    """Create a minimal task YAML for testing."""
    task_dir = tmp_path / "tasks" / "codegen"
    task_dir.mkdir(parents=True)
    task_file = task_dir / "hello-world.yaml"
    task_file.write_text(
        'name: "Hello World"\n'
        'category: "codegen"\n'
        'description: "Create a hello world script"\n'
        'prompt: "Create a Python file hello.py that prints Hello World"\n'
        "setup_files: []\n"
        "checks:\n"
        '  - type: "file_exists"\n'
        '    path: "hello.py"\n'
        '  - type: "command"\n'
        '    run: "python hello.py"\n'
        "    expect_exit_code: 0\n"
        "judge:\n"
        "  criteria:\n"
        '    - "Korrektheit: Gibt das Script Hello World aus?"\n'
        '  scale: "1-10"\n'
        "claude_settings:\n"
        "  max_turns: 5\n"
    )
    return task_file


@pytest.fixture
def sample_config_dir(tmp_path: Path) -> Path:
    """Create a minimal config directory for testing."""
    config_dir = tmp_path / "configs" / "baseline"
    config_dir.mkdir(parents=True)
    (config_dir / "CLAUDE.md").write_text("# Baseline Config\nDu bist ein hilfreicher Assistent.\n")
    return config_dir
```

- [ ] **Step 5: Install dev dependencies and verify**

Run: `cd /path/to/cccb && pip install -e ".[dev]" --break-system-packages`
Expected: Successful install

- [ ] **Step 6: Run empty test suite**

Run: `pytest tests/ -v`
Expected: "no tests ran" or 0 collected, exit code 5 (no tests)

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml cccb/__init__.py cccb/__main__.py tests/__init__.py tests/conftest.py
git commit -m "feat: project scaffolding with pyproject.toml and test fixtures"
```

---

### Task 2: Data Models

**Files:**
- Create: `cccb/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write tests for models**

```python
# tests/test_models.py
"""Tests for CCCB data models."""
import pytest
from pathlib import Path


def test_check_command():
    from cccb.models import Check
    c = Check(type="command", run="pytest -v", path=None, expect_exit_code=0)
    assert c.type == "command"
    assert c.run == "pytest -v"
    assert c.expect_exit_code == 0


def test_check_file_exists():
    from cccb.models import Check
    c = Check(type="file_exists", run=None, path="main.py", expect_exit_code=0)
    assert c.type == "file_exists"
    assert c.path == "main.py"


def test_claude_settings_defaults():
    from cccb.models import ClaudeSettings
    s = ClaudeSettings(max_turns=10)
    assert s.max_turns == 10
    assert s.allowed_tools is None
    assert s.timeout == 300  # default


def test_task_definition_from_yaml(sample_task_yaml: Path):
    from cccb.models import TaskDefinition
    task = TaskDefinition.from_yaml(sample_task_yaml)
    assert task.name == "Hello World"
    assert task.category == "codegen"
    assert len(task.checks) == 2
    assert task.checks[0].type == "file_exists"
    assert task.checks[1].type == "command"
    assert task.claude_settings.max_turns == 5


def test_task_definition_from_yaml_missing_file():
    from cccb.models import TaskDefinition
    with pytest.raises(FileNotFoundError):
        TaskDefinition.from_yaml(Path("/nonexistent/task.yaml"))


def test_task_definition_from_yaml_invalid():
    from cccb.models import TaskDefinition
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as f:
        f.write("not: valid: yaml: [")
    with pytest.raises(Exception):
        TaskDefinition.from_yaml(Path(f.name))


def test_config_profile_from_dir(sample_config_dir: Path):
    from cccb.models import ConfigProfile
    config = ConfigProfile.from_dir(sample_config_dir)
    assert config.name == "baseline"
    assert config.path == sample_config_dir
    assert "Baseline Config" in config.description


def test_config_profile_from_dir_missing_claude_md(tmp_path: Path):
    from cccb.models import ConfigProfile
    empty_dir = tmp_path / "empty-config"
    empty_dir.mkdir()
    with pytest.raises(ValueError, match="CLAUDE.md"):
        ConfigProfile.from_dir(empty_dir)


def test_config_profile_from_dir_with_config_yaml(sample_config_dir: Path):
    from cccb.models import ConfigProfile
    (sample_config_dir / "config.yaml").write_text(
        'name: "My Baseline"\ndescription: "A custom description"\n'
    )
    config = ConfigProfile.from_dir(sample_config_dir)
    assert config.name == "My Baseline"
    assert config.description == "A custom description"


def test_run_result_creation():
    from cccb.models import RunResult, ConfigProfile, TaskDefinition, CheckResult, Check
    # Minimal creation test — just ensure all fields are accepted
    result = RunResult(
        config=None,  # type: ignore
        task=None,  # type: ignore
        duration_ms=5000,
        duration_api_ms=4000,
        total_cost_usd=0.05,
        num_turns=3,
        session_id="test-session",
        checks_passed=2,
        checks_total=3,
        check_details=[],
        judge_scores={"quality": 7.5},
        judge_average=7.5,
        total_score=0.0,
        worktree_path=".cccb-bench/baseline/hello",
        branch_name="bench/baseline/hello",
        commit_hash="abc123",
    )
    assert result.duration_ms == 5000
    assert result.total_cost_usd == 0.05


def test_benchmark_report_winner():
    from cccb.models import BenchmarkReport
    report = BenchmarkReport(
        configs=[],
        tasks=[],
        results=[],
        winner=None,  # type: ignore
        summary="Test summary",
    )
    assert report.summary == "Test summary"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'cccb.models'`

- [ ] **Step 3: Implement models.py**

```python
# cccb/models.py
"""Data models for CCCB benchmark definitions and results."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class SetupFile:
    """A file to copy into the working directory before a benchmark run."""

    source: str  # Path relative to task directory
    target: str  # Target path in test project


@dataclass
class Check:
    """An automated check to run after a benchmark task completes."""

    type: str  # "command" | "file_exists"
    run: str | None = None  # Shell command (for type=command)
    path: str | None = None  # File path (for type=file_exists)
    expect_exit_code: int = 0  # Expected exit code (for type=command)


@dataclass
class JudgeCriteria:
    """Criteria for LLM-as-Judge evaluation."""

    criteria: list[str]  # List of evaluation criteria
    scale: str = "1-10"  # Rating scale


@dataclass
class ClaudeSettings:
    """Settings for Claude Code invocation."""

    max_turns: int = 10  # Max agentic turns
    allowed_tools: list[str] | None = None  # Allowed tools (optional)
    timeout: int = 300  # Timeout in seconds


@dataclass
class TaskDefinition:
    """A benchmark task loaded from a YAML file."""

    name: str
    category: str  # "codegen" | "debugging" | "refactoring"
    description: str
    prompt: str
    setup_files: list[SetupFile]
    checks: list[Check]
    judge: JudgeCriteria
    claude_settings: ClaudeSettings

    @classmethod
    def from_yaml(cls, path: Path) -> TaskDefinition:
        """Load a TaskDefinition from a YAML file."""
        if not path.exists():
            raise FileNotFoundError(f"Task file not found: {path}")

        with open(path) as f:
            data = yaml.safe_load(f)

        setup_files = [
            SetupFile(source=sf["source"], target=sf["target"])
            for sf in (data.get("setup_files") or [])
        ]

        checks = [
            Check(
                type=c["type"],
                run=c.get("run"),
                path=c.get("path"),
                expect_exit_code=c.get("expect_exit_code", 0),
            )
            for c in (data.get("checks") or [])
        ]

        judge_data = data.get("judge", {})
        judge = JudgeCriteria(
            criteria=judge_data.get("criteria", []),
            scale=judge_data.get("scale", "1-10"),
        )

        cs_data = data.get("claude_settings", {})
        claude_settings = ClaudeSettings(
            max_turns=cs_data.get("max_turns", 10),
            allowed_tools=cs_data.get("allowed_tools"),
            timeout=cs_data.get("timeout", 300),
        )

        return cls(
            name=data["name"],
            category=data["category"],
            description=data["description"],
            prompt=data["prompt"],
            setup_files=setup_files,
            checks=checks,
            judge=judge,
            claude_settings=claude_settings,
        )


@dataclass
class ConfigProfile:
    """A Claude Code configuration — a directory with CLAUDE.md and optional extras."""

    name: str
    path: Path
    description: str

    @classmethod
    def from_dir(cls, path: Path) -> ConfigProfile:
        """Load a ConfigProfile from a directory.

        Validation: Directory MUST contain a non-empty CLAUDE.md.
        Optional: config.yaml for name/description overrides.
        """
        claude_md = path / "CLAUDE.md"
        if not claude_md.exists() or claude_md.stat().st_size == 0:
            raise ValueError(
                f"Config directory must contain a non-empty CLAUDE.md: {path}"
            )

        # Defaults
        name = path.name
        description = claude_md.read_text().strip().split("\n")[0]

        # Override from config.yaml if present
        config_yaml = path / "config.yaml"
        if config_yaml.exists():
            with open(config_yaml) as f:
                config_data = yaml.safe_load(f) or {}
            name = config_data.get("name", name)
            description = config_data.get("description", description)

        return cls(name=name, path=path, description=description)


@dataclass
class CheckResult:
    """Result of a single automated check."""

    check: Check
    passed: bool
    output: str  # Stdout/stderr from the check command


@dataclass
class RunResult:
    """Result of a single benchmark run (one config x one task)."""

    config: ConfigProfile
    task: TaskDefinition
    # From Claude Agent SDK:
    duration_ms: int
    duration_api_ms: int
    total_cost_usd: float
    num_turns: int
    session_id: str
    # Automated checks:
    checks_passed: int
    checks_total: int
    check_details: list[CheckResult]
    # LLM-as-Judge:
    judge_scores: dict[str, float]  # criterion -> 1-10
    judge_average: float
    # Aggregated:
    total_score: float
    # Git reference:
    worktree_path: str
    branch_name: str
    commit_hash: str


@dataclass
class BenchmarkReport:
    """Overall result of a benchmark run."""

    configs: list[ConfigProfile]
    tasks: list[TaskDefinition]
    results: list[RunResult]
    winner: ConfigProfile | None
    summary: str  # LLM-generated improvement suggestions
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_models.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add cccb/models.py tests/test_models.py
git commit -m "feat: data models with YAML loading and validation"
```

---

## Chunk 2: Git Worktree Isolation

### Task 3: isolation.py — Worktree Management

**Files:**
- Create: `cccb/isolation.py`
- Create: `tests/test_isolation.py`

- [ ] **Step 1: Write tests for worktree isolation**

```python
# tests/test_isolation.py
"""Tests for git worktree isolation."""
import pytest
import subprocess
from pathlib import Path
from cccb.isolation import WorktreeManager


class TestWorktreeManager:
    def test_init(self, tmp_repo: Path):
        mgr = WorktreeManager(tmp_repo)
        assert mgr.repo_root == tmp_repo
        assert mgr.bench_dir == tmp_repo / ".cccb-bench"

    def test_create_worktree(self, tmp_repo: Path):
        mgr = WorktreeManager(tmp_repo)
        wt_path = mgr.create_worktree("baseline", "hello-world")
        assert wt_path.exists()
        assert (wt_path / "README.md").exists()  # from initial commit
        assert wt_path == tmp_repo / ".cccb-bench" / "baseline" / "hello-world"

    def test_create_worktree_branch_name(self, tmp_repo: Path):
        mgr = WorktreeManager(tmp_repo)
        mgr.create_worktree("baseline", "hello-world")
        # Check branch was created
        result = subprocess.run(
            ["git", "branch", "--list", "bench/baseline/hello-world"],
            cwd=tmp_repo, capture_output=True, text=True,
        )
        assert "bench/baseline/hello-world" in result.stdout

    def test_create_worktree_collision_suffix(self, tmp_repo: Path):
        mgr = WorktreeManager(tmp_repo)
        mgr.create_worktree("baseline", "hello-world")
        # Creating again should use suffix
        wt_path2 = mgr.create_worktree("baseline", "hello-world")
        assert "hello-world-2" in str(wt_path2)

    def test_copy_config_files(self, tmp_repo: Path, sample_config_dir: Path):
        mgr = WorktreeManager(tmp_repo)
        wt_path = mgr.create_worktree("baseline", "test-task")
        mgr.copy_config_files(wt_path, sample_config_dir)
        assert (wt_path / "CLAUDE.md").exists()
        assert "Baseline Config" in (wt_path / "CLAUDE.md").read_text()

    def test_copy_setup_files(self, tmp_repo: Path):
        from cccb.models import SetupFile
        mgr = WorktreeManager(tmp_repo)
        wt_path = mgr.create_worktree("baseline", "test-task")
        # Create a fixture file
        fixture_dir = tmp_repo / "fixtures"
        fixture_dir.mkdir()
        (fixture_dir / "requirements.txt").write_text("fastapi\n")
        setup_files = [SetupFile(source=str(fixture_dir / "requirements.txt"), target="requirements.txt")]
        mgr.copy_setup_files(wt_path, setup_files)
        assert (wt_path / "requirements.txt").exists()

    def test_commit_setup(self, tmp_repo: Path, sample_config_dir: Path):
        mgr = WorktreeManager(tmp_repo)
        wt_path = mgr.create_worktree("baseline", "test-task")
        mgr.copy_config_files(wt_path, sample_config_dir)
        commit_hash = mgr.commit_setup(wt_path, "baseline", "test-task")
        assert len(commit_hash) == 40  # full SHA

    def test_commit_result(self, tmp_repo: Path, sample_config_dir: Path):
        mgr = WorktreeManager(tmp_repo)
        wt_path = mgr.create_worktree("baseline", "test-task")
        mgr.copy_config_files(wt_path, sample_config_dir)
        mgr.commit_setup(wt_path, "baseline", "test-task")
        # Simulate Claude output
        (wt_path / "main.py").write_text("print('hello')\n")
        commit_hash = mgr.commit_result(wt_path, "baseline", "test-task", score=7.5)
        assert len(commit_hash) == 40

    def test_commit_result_timeout_marker(self, tmp_repo: Path, sample_config_dir: Path):
        mgr = WorktreeManager(tmp_repo)
        wt_path = mgr.create_worktree("baseline", "test-task")
        mgr.copy_config_files(wt_path, sample_config_dir)
        mgr.commit_setup(wt_path, "baseline", "test-task")
        (wt_path / "partial.py").write_text("# partial\n")
        commit_hash = mgr.commit_result(
            wt_path, "baseline", "test-task", score=0.0, timeout=True,
        )
        # Verify commit message contains [TIMEOUT]
        log = subprocess.run(
            ["git", "log", "-1", "--format=%s", commit_hash],
            cwd=wt_path, capture_output=True, text=True,
        )
        assert "[TIMEOUT]" in log.stdout

    def test_get_diff(self, tmp_repo: Path, sample_config_dir: Path):
        mgr = WorktreeManager(tmp_repo)
        wt_path = mgr.create_worktree("baseline", "test-task")
        mgr.copy_config_files(wt_path, sample_config_dir)
        setup_hash = mgr.commit_setup(wt_path, "baseline", "test-task")
        (wt_path / "main.py").write_text("print('hello')\n")
        result_hash = mgr.commit_result(wt_path, "baseline", "test-task", score=7.5)
        diff = mgr.get_diff(wt_path, setup_hash, result_hash)
        assert "main.py" in diff
        assert "hello" in diff

    def test_cleanup(self, tmp_repo: Path):
        mgr = WorktreeManager(tmp_repo)
        mgr.create_worktree("baseline", "task1")
        mgr.create_worktree("baseline", "task2")
        assert (tmp_repo / ".cccb-bench").exists()
        mgr.cleanup_all()
        # Worktrees should be removed
        assert not (tmp_repo / ".cccb-bench" / "baseline" / "task1").exists()

    def test_path_traversal_rejected(self, tmp_repo: Path):
        mgr = WorktreeManager(tmp_repo)
        wt_path = mgr.create_worktree("baseline", "test-task")
        from cccb.models import SetupFile
        bad_files = [SetupFile(source="/etc/passwd", target="../../../etc/evil")]
        with pytest.raises(ValueError, match="[Pp]ath [Tt]raversal"):
            mgr.copy_setup_files(wt_path, bad_files)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_isolation.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'cccb.isolation'`

- [ ] **Step 3: Implement isolation.py**

```python
# cccb/isolation.py
"""Git worktree isolation for benchmark runs."""
from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

from cccb.models import SetupFile

logger = logging.getLogger(__name__)

MAX_COLLISION_RETRIES = 5


class WorktreeManager:
    """Manages git worktrees for isolated benchmark runs."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.bench_dir = repo_root / ".cccb-bench"

    def create_worktree(self, config_name: str, task_slug: str) -> Path:
        """Create an isolated git worktree for a benchmark run.

        Returns the worktree path.
        Handles name collisions with -2, -3, ... suffixes.
        """
        base_name = task_slug
        for attempt in range(1, MAX_COLLISION_RETRIES + 1):
            suffix = f"-{attempt}" if attempt > 1 else ""
            name = f"{base_name}{suffix}"
            wt_path = self.bench_dir / config_name / name
            branch_name = f"bench/{config_name}/{name}"

            if wt_path.exists():
                continue

            try:
                wt_path.parent.mkdir(parents=True, exist_ok=True)
                subprocess.run(
                    ["git", "worktree", "add", str(wt_path), "-b", branch_name, "HEAD"],
                    cwd=self.repo_root,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                logger.info("Created worktree: %s (branch: %s)", wt_path, branch_name)
                return wt_path
            except subprocess.CalledProcessError:
                # Branch might already exist — try next suffix
                continue

        raise RuntimeError(
            f"Could not create worktree for {config_name}/{task_slug} "
            f"after {MAX_COLLISION_RETRIES} attempts"
        )

    def copy_config_files(self, wt_path: Path, config_dir: Path) -> None:
        """Copy configuration files (CLAUDE.md, .claude/) into the worktree."""
        # Copy CLAUDE.md
        claude_md = config_dir / "CLAUDE.md"
        if claude_md.exists():
            shutil.copy2(claude_md, wt_path / "CLAUDE.md")

        # Copy .claude/ directory if present
        claude_dir = config_dir / ".claude"
        if claude_dir.exists() and claude_dir.is_dir():
            dest = wt_path / ".claude"
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(claude_dir, dest)

    def copy_setup_files(self, wt_path: Path, setup_files: list[SetupFile]) -> None:
        """Copy task setup files into the worktree.

        Validates paths to prevent path traversal attacks.
        Setup files do NOT overwrite CLAUDE.md.
        """
        for sf in setup_files:
            target = (wt_path / sf.target).resolve()
            # Security: target must be under worktree root
            if not str(target).startswith(str(wt_path.resolve())):
                raise ValueError(
                    f"Path traversal detected: {sf.target} resolves outside worktree"
                )
            # Don't overwrite CLAUDE.md
            if target.name == "CLAUDE.md" and target.parent == wt_path:
                logger.warning("Setup file would overwrite CLAUDE.md — skipping: %s", sf.target)
                continue

            target.parent.mkdir(parents=True, exist_ok=True)
            source = Path(sf.source)
            if source.exists():
                shutil.copy2(source, target)
            else:
                logger.warning("Setup file not found: %s", sf.source)

    def commit_setup(self, wt_path: Path, config_name: str, task_slug: str) -> str:
        """Stage all files in worktree and commit as setup. Returns commit hash."""
        subprocess.run(
            ["git", "add", "-A"],
            cwd=wt_path, check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", f"Setup: {config_name} x {task_slug}", "--allow-empty"],
            cwd=wt_path, check=True, capture_output=True,
        )
        return self._get_head_hash(wt_path)

    def commit_result(
        self,
        wt_path: Path,
        config_name: str,
        task_slug: str,
        score: float,
        timeout: bool = False,
        error: bool = False,
    ) -> str:
        """Stage all files and commit as result. Returns commit hash."""
        markers = []
        if timeout:
            markers.append("[TIMEOUT]")
        if error:
            markers.append("[ERROR]")
        marker_str = " ".join(markers)
        msg = f"Result: {config_name} x {task_slug} [score: {score:.1f}]"
        if marker_str:
            msg += f" {marker_str}"

        subprocess.run(
            ["git", "add", "-A"],
            cwd=wt_path, check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", msg, "--allow-empty"],
            cwd=wt_path, check=True, capture_output=True,
        )
        return self._get_head_hash(wt_path)

    def get_diff(self, wt_path: Path, setup_hash: str, result_hash: str, max_bytes: int = 50_000) -> str:
        """Get the git diff between setup and result commits.

        Truncates if diff exceeds max_bytes.
        """
        result = subprocess.run(
            ["git", "diff", f"{setup_hash}..{result_hash}"],
            cwd=wt_path, capture_output=True, text=True,
        )
        diff = result.stdout
        if len(diff.encode()) > max_bytes:
            truncated = diff.encode()[:max_bytes].decode(errors="replace")
            return truncated + "\n\n[DIFF TRUNCATED — exceeded 50KB]"
        return diff

    def cleanup_all(self) -> None:
        """Remove all benchmark worktrees and their branches."""
        if not self.bench_dir.exists():
            return

        # List and remove worktrees
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            cwd=self.repo_root, capture_output=True, text=True,
        )
        for line in result.stdout.splitlines():
            if line.startswith("worktree ") and ".cccb-bench" in line:
                wt_path = line.split("worktree ", 1)[1]
                subprocess.run(
                    ["git", "worktree", "remove", "--force", wt_path],
                    cwd=self.repo_root, capture_output=True,
                )

        # Prune stale worktree references
        subprocess.run(
            ["git", "worktree", "prune"],
            cwd=self.repo_root, capture_output=True,
        )

        # Delete bench/* branches
        result = subprocess.run(
            ["git", "branch", "--list", "bench/*"],
            cwd=self.repo_root, capture_output=True, text=True,
        )
        for line in result.stdout.splitlines():
            branch = line.strip()
            if branch:
                subprocess.run(
                    ["git", "branch", "-D", branch],
                    cwd=self.repo_root, capture_output=True,
                )

        # Remove bench directory
        if self.bench_dir.exists():
            shutil.rmtree(self.bench_dir, ignore_errors=True)

    def _get_head_hash(self, wt_path: Path) -> str:
        """Get the current HEAD commit hash in a worktree."""
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=wt_path, capture_output=True, text=True, check=True,
        )
        return result.stdout.strip()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_isolation.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add cccb/isolation.py tests/test_isolation.py
git commit -m "feat: git worktree isolation for benchmark runs"
```

---

## Chunk 3: Checker & Scorer

### Task 4: checker.py — Automated Checks

**Files:**
- Create: `cccb/checker.py`
- Create: `tests/test_checker.py`

- [ ] **Step 1: Write tests for checker**

```python
# tests/test_checker.py
"""Tests for automated checks."""
import pytest
from pathlib import Path
from cccb.checker import run_checks
from cccb.models import Check, CheckResult


class TestRunChecks:
    def test_file_exists_pass(self, tmp_path: Path):
        (tmp_path / "main.py").write_text("print('hi')\n")
        checks = [Check(type="file_exists", path="main.py")]
        results = run_checks(checks, cwd=tmp_path)
        assert len(results) == 1
        assert results[0].passed is True

    def test_file_exists_fail(self, tmp_path: Path):
        checks = [Check(type="file_exists", path="missing.py")]
        results = run_checks(checks, cwd=tmp_path)
        assert len(results) == 1
        assert results[0].passed is False

    def test_command_pass(self, tmp_path: Path):
        (tmp_path / "hello.py").write_text("print('hello')\n")
        checks = [Check(type="command", run="python hello.py", expect_exit_code=0)]
        results = run_checks(checks, cwd=tmp_path)
        assert results[0].passed is True
        assert "hello" in results[0].output

    def test_command_fail_exit_code(self, tmp_path: Path):
        checks = [Check(type="command", run="python -c 'raise SystemExit(1)'", expect_exit_code=0)]
        results = run_checks(checks, cwd=tmp_path)
        assert results[0].passed is False

    def test_command_expected_nonzero(self, tmp_path: Path):
        checks = [Check(type="command", run="python -c 'raise SystemExit(1)'", expect_exit_code=1)]
        results = run_checks(checks, cwd=tmp_path)
        assert results[0].passed is True

    def test_multiple_checks(self, tmp_path: Path):
        (tmp_path / "main.py").write_text("print('ok')\n")
        checks = [
            Check(type="file_exists", path="main.py"),
            Check(type="command", run="python main.py", expect_exit_code=0),
            Check(type="file_exists", path="missing.py"),
        ]
        results = run_checks(checks, cwd=tmp_path)
        assert results[0].passed is True
        assert results[1].passed is True
        assert results[2].passed is False

    def test_command_timeout(self, tmp_path: Path):
        checks = [Check(type="command", run="sleep 60", expect_exit_code=0)]
        results = run_checks(checks, cwd=tmp_path, timeout=1)
        assert results[0].passed is False
        assert "timeout" in results[0].output.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_checker.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement checker.py**

```python
# cccb/checker.py
"""Automated checks for benchmark task results."""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from cccb.models import Check, CheckResult

logger = logging.getLogger(__name__)

DEFAULT_CHECK_TIMEOUT = 60  # seconds


def run_checks(
    checks: list[Check],
    cwd: Path,
    timeout: int = DEFAULT_CHECK_TIMEOUT,
) -> list[CheckResult]:
    """Run all checks and return results.

    Each check runs independently — a failing check does not stop subsequent checks.
    """
    results: list[CheckResult] = []
    for check in checks:
        if check.type == "file_exists":
            result = _check_file_exists(check, cwd)
        elif check.type == "command":
            result = _check_command(check, cwd, timeout)
        else:
            result = CheckResult(
                check=check, passed=False, output=f"Unknown check type: {check.type}"
            )
        results.append(result)
    return results


def _check_file_exists(check: Check, cwd: Path) -> CheckResult:
    """Check if a file exists at the given path."""
    target = cwd / check.path
    exists = target.exists()
    return CheckResult(
        check=check,
        passed=exists,
        output=f"File {'exists' if exists else 'not found'}: {check.path}",
    )


def _check_command(check: Check, cwd: Path, timeout: int) -> CheckResult:
    """Run a shell command and check the exit code."""
    try:
        result = subprocess.run(
            check.run,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        passed = result.returncode == check.expect_exit_code
        output = result.stdout + result.stderr
        return CheckResult(check=check, passed=passed, output=output[:2000])
    except subprocess.TimeoutExpired:
        return CheckResult(
            check=check,
            passed=False,
            output=f"Timeout after {timeout}s: {check.run}",
        )
    except Exception as e:
        return CheckResult(check=check, passed=False, output=f"Error: {e}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_checker.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add cccb/checker.py tests/test_checker.py
git commit -m "feat: automated check runner (file_exists + command checks)"
```

---

### Task 5: scorer.py — Score Calculation

**Files:**
- Create: `cccb/scorer.py`
- Create: `tests/test_scorer.py`

- [ ] **Step 1: Write tests for scorer**

```python
# tests/test_scorer.py
"""Tests for score calculation."""
import pytest
from cccb.scorer import calculate_check_score, calculate_efficiency, calculate_total_score, calculate_config_average


class TestCheckScore:
    def test_all_passed(self):
        assert calculate_check_score(5, 5) == 10.0

    def test_none_passed(self):
        assert calculate_check_score(0, 5) == 0.0

    def test_partial(self):
        assert calculate_check_score(3, 5) == 6.0

    def test_zero_checks(self):
        assert calculate_check_score(0, 0) == 0.0


class TestEfficiency:
    def test_best_rank(self):
        # Best in both cost and time → 10
        score = calculate_efficiency(cost_rank=1, time_rank=1, n_configs=3)
        assert score == 10.0

    def test_worst_rank(self):
        # Worst in both → 1
        score = calculate_efficiency(cost_rank=3, time_rank=3, n_configs=3)
        assert score == 1.0

    def test_single_config(self):
        score = calculate_efficiency(cost_rank=1, time_rank=1, n_configs=1)
        assert score == 5.0  # neutral

    def test_timeout(self):
        score = calculate_efficiency(cost_rank=1, time_rank=1, n_configs=3, timeout=True)
        assert score == 1.0


class TestTotalScore:
    def test_default_weights(self):
        score = calculate_total_score(
            check_score=10.0, judge_score=10.0, efficiency=10.0,
        )
        assert score == 10.0

    def test_mixed(self):
        score = calculate_total_score(
            check_score=8.0, judge_score=6.0, efficiency=4.0,
        )
        # 8*0.4 + 6*0.4 + 4*0.2 = 3.2 + 2.4 + 0.8 = 6.4
        assert abs(score - 6.4) < 0.01

    def test_custom_weights(self):
        score = calculate_total_score(
            check_score=10.0, judge_score=0.0, efficiency=0.0,
            weights=(1.0, 0.0, 0.0),
        )
        assert score == 10.0


class TestConfigAverage:
    def test_average(self):
        avg = calculate_config_average([7.0, 8.0, 9.0])
        assert abs(avg - 8.0) < 0.01

    def test_single(self):
        avg = calculate_config_average([5.5])
        assert avg == 5.5

    def test_empty(self):
        avg = calculate_config_average([])
        assert avg == 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_scorer.py -v`
Expected: FAIL

- [ ] **Step 3: Implement scorer.py**

```python
# cccb/scorer.py
"""Score calculation and aggregation for benchmark results."""
from __future__ import annotations

DEFAULT_WEIGHTS = (0.4, 0.4, 0.2)  # check, judge, efficiency


def calculate_check_score(checks_passed: int, checks_total: int) -> float:
    """Calculate check score on a 0-10 scale.

    Returns 0.0 if there are no checks.
    """
    if checks_total == 0:
        return 0.0
    return (checks_passed / checks_total) * 10


def calculate_efficiency(
    cost_rank: int,
    time_rank: int,
    n_configs: int,
    timeout: bool = False,
) -> float:
    """Calculate efficiency score on a 1-10 scale.

    Based on rank among configs for cost and time.
    Returns 5.0 (neutral) if only 1 config.
    Returns 1.0 (worst) on timeout.
    """
    if timeout:
        return 1.0
    if n_configs <= 1:
        return 5.0
    return 10 - ((cost_rank + time_rank - 2) / (2 * (n_configs - 1))) * 9


def calculate_total_score(
    check_score: float,
    judge_score: float,
    efficiency: float,
    weights: tuple[float, float, float] = DEFAULT_WEIGHTS,
) -> float:
    """Calculate weighted total score."""
    w_check, w_judge, w_eff = weights
    return (check_score * w_check) + (judge_score * w_judge) + (efficiency * w_eff)


def calculate_config_average(scores: list[float]) -> float:
    """Calculate average score for a config across all tasks."""
    if not scores:
        return 0.0
    return sum(scores) / len(scores)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_scorer.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add cccb/scorer.py tests/test_scorer.py
git commit -m "feat: score calculation (check, efficiency, total, average)"
```

---

## Chunk 4: Executor & Judge (Claude Agent SDK)

### Task 6: executor.py — Claude Code Invocation

**Files:**
- Create: `cccb/executor.py`
- Create: `tests/test_executor.py`

- [ ] **Step 1: Write tests for executor**

These tests mock the claude-agent-sdk to avoid real API calls.

```python
# tests/test_executor.py
"""Tests for Claude Code executor via Agent SDK."""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path
from cccb.executor import execute_task, ExecutionResult
from cccb.models import TaskDefinition, ClaudeSettings, JudgeCriteria


@pytest.fixture
def minimal_task() -> TaskDefinition:
    return TaskDefinition(
        name="Test Task",
        category="codegen",
        description="A test task",
        prompt="Create hello.py",
        setup_files=[],
        checks=[],
        judge=JudgeCriteria(criteria=["quality"], scale="1-10"),
        claude_settings=ClaudeSettings(max_turns=5, timeout=10),
    )


class TestExecuteTask:
    @pytest.mark.asyncio
    async def test_successful_execution(self, minimal_task, tmp_path):
        """Test that execute_task returns an ExecutionResult on success."""
        mock_messages = [
            MagicMock(type="assistant", content=[]),
            MagicMock(type="result", duration_ms=5000, duration_api_ms=4000,
                      cost_usd=0.05, num_turns=3, session_id="sess-123",
                      is_error=False, subtype="success"),
        ]

        async def mock_query(**kwargs):
            for msg in mock_messages:
                yield msg

        with patch("cccb.executor.sdk_query", side_effect=mock_query):
            result = await execute_task(minimal_task, tmp_path)

        assert isinstance(result, ExecutionResult)
        assert result.duration_ms == 5000
        assert result.total_cost_usd == 0.05
        assert result.is_error is False

    @pytest.mark.asyncio
    async def test_timeout_handling(self, minimal_task, tmp_path):
        """Test that timeouts are caught and produce a result."""
        async def mock_query(**kwargs):
            await asyncio.sleep(100)  # Will be cancelled by timeout
            yield MagicMock()  # Never reached

        with patch("cccb.executor.sdk_query", side_effect=mock_query):
            result = await execute_task(minimal_task, tmp_path)

        assert result.timed_out is True
        assert result.is_error is True

    @pytest.mark.asyncio
    async def test_process_error_handling(self, minimal_task, tmp_path):
        """Test that ProcessError is caught."""
        from cccb.executor import ProcessError as MockPE

        async def mock_query(**kwargs):
            raise MockPE(1)
            yield  # Make it a generator

        with patch("cccb.executor.sdk_query", side_effect=mock_query):
            result = await execute_task(minimal_task, tmp_path)

        assert result.is_error is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_executor.py -v`
Expected: FAIL

- [ ] **Step 3: Implement executor.py**

```python
# cccb/executor.py
"""Claude Code invocation via the official claude-agent-sdk."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncIterator

from cccb.models import TaskDefinition

logger = logging.getLogger(__name__)

# Import SDK — we alias to allow easy mocking in tests
try:
    from claude_agent_sdk import (
        query as sdk_query,
        ClaudeAgentOptions,
        AssistantMessage,
        ToolUseBlock,
        TextBlock,
        CLINotFoundError,
        ProcessError,
        CLIJSONDecodeError,
    )
except ImportError:
    # Stub for testing without SDK installed
    sdk_query = None  # type: ignore
    ClaudeAgentOptions = None  # type: ignore
    AssistantMessage = type("AssistantMessage", (), {})  # type: ignore
    ToolUseBlock = type("ToolUseBlock", (), {})  # type: ignore
    TextBlock = type("TextBlock", (), {})  # type: ignore
    CLINotFoundError = type("CLINotFoundError", (Exception,), {})  # type: ignore
    ProcessError = type("ProcessError", (Exception,), {"__init__": lambda self, code: setattr(self, "exit_code", code) or Exception.__init__(self)})  # type: ignore
    CLIJSONDecodeError = type("CLIJSONDecodeError", (Exception,), {})  # type: ignore


@dataclass
class ExecutionResult:
    """Result from a Claude Code execution."""

    duration_ms: int = 0
    duration_api_ms: int = 0
    total_cost_usd: float = 0.0
    num_turns: int = 0
    session_id: str = ""
    is_error: bool = False
    timed_out: bool = False
    tool_uses: list[str] = field(default_factory=list)


@dataclass
class ExecutionEvent:
    """A streaming event during execution, for TUI updates."""

    type: str  # "tool_use" | "text" | "progress"
    detail: str = ""


async def execute_task(
    task: TaskDefinition,
    working_dir: Path,
    on_event: callable | None = None,
) -> ExecutionResult:
    """Execute a benchmark task via Claude Agent SDK.

    Args:
        task: The task definition to execute.
        working_dir: Git worktree directory to run in.
        on_event: Optional callback for streaming events.

    Returns:
        ExecutionResult with metrics and status.
    """
    if sdk_query is None:
        raise RuntimeError(
            "claude-agent-sdk not installed. Run: pip install claude-agent-sdk"
        )

    options = ClaudeAgentOptions(
        allowed_tools=task.claude_settings.allowed_tools or ["Read", "Write", "Edit", "Bash"],
        permission_mode="dangerouslySkipPermissions",
        max_turns=task.claude_settings.max_turns,
        cwd=str(working_dir),
    )

    result = ExecutionResult()
    timeout_seconds = task.claude_settings.timeout or 300

    try:
        async with asyncio.timeout(timeout_seconds):
            async for message in sdk_query(prompt=task.prompt, options=options):
                # Track tool usage for monitoring
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, ToolUseBlock):
                            result.tool_uses.append(block.name)
                            if on_event:
                                on_event(ExecutionEvent(type="tool_use", detail=block.name))
                        elif isinstance(block, TextBlock):
                            if on_event:
                                on_event(ExecutionEvent(type="text", detail=block.text[:100]))

                # Extract metrics from result message
                if hasattr(message, "duration_ms"):
                    result.duration_ms = getattr(message, "duration_ms", 0)
                    result.duration_api_ms = getattr(message, "duration_api_ms", 0)
                    result.total_cost_usd = getattr(message, "cost_usd", 0.0)
                    result.num_turns = getattr(message, "num_turns", 0)
                    result.session_id = getattr(message, "session_id", "")
                    result.is_error = getattr(message, "is_error", False)

    except TimeoutError:
        logger.warning("Task timed out after %ds: %s", timeout_seconds, task.name)
        result.timed_out = True
        result.is_error = True
    except CLINotFoundError:
        raise RuntimeError(
            "Claude Code CLI not found. Install: pip install --force-reinstall claude-agent-sdk"
        )
    except ProcessError as e:
        logger.error("Process error (exit %d): %s", e.exit_code, task.name)
        result.is_error = True
    except CLIJSONDecodeError as e:
        logger.error("JSON decode error: %s", e)
        result.is_error = True

    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_executor.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add cccb/executor.py tests/test_executor.py
git commit -m "feat: Claude Code executor via claude-agent-sdk"
```

---

### Task 7: judge.py — LLM-as-Judge

**Files:**
- Create: `cccb/judge.py`
- Create: `tests/test_judge.py`

- [ ] **Step 1: Write tests for judge**

```python
# tests/test_judge.py
"""Tests for LLM-as-Judge evaluation."""
import pytest
import json
from unittest.mock import patch, MagicMock
from pathlib import Path
from cccb.judge import build_judge_prompt, parse_judge_response, evaluate_run
from cccb.models import TaskDefinition, JudgeCriteria, ClaudeSettings


@pytest.fixture
def codegen_task() -> TaskDefinition:
    return TaskDefinition(
        name="REST API",
        category="codegen",
        description="Create a REST API",
        prompt="Create a FastAPI REST API",
        setup_files=[],
        checks=[],
        judge=JudgeCriteria(
            criteria=["Korrektheit", "Code-Struktur", "Vollstaendigkeit"],
            scale="1-10",
        ),
        claude_settings=ClaudeSettings(max_turns=10),
    )


class TestBuildJudgePrompt:
    def test_contains_task_info(self, codegen_task):
        prompt = build_judge_prompt(codegen_task, "diff --git a/main.py b/main.py\n+print('hi')")
        assert "REST API" in prompt
        assert "FastAPI" in prompt
        assert "Korrektheit" in prompt
        assert "Code-Struktur" in prompt
        assert "diff --git" in prompt

    def test_contains_anchors(self, codegen_task):
        prompt = build_judge_prompt(codegen_task, "some diff")
        assert "1-2:" in prompt
        assert "9-10:" in prompt

    def test_truncated_diff(self, codegen_task):
        huge_diff = "x" * 60_000
        prompt = build_judge_prompt(codegen_task, huge_diff)
        assert "[DIFF TRUNCATED" in prompt

    def test_empty_diff(self, codegen_task):
        prompt = build_judge_prompt(codegen_task, "")
        assert "Kein Code" in prompt or "leer" in prompt.lower()


class TestParseJudgeResponse:
    def test_valid_json(self):
        response = json.dumps({
            "scores": {"Korrektheit": 8, "Code-Struktur": 7},
            "reasoning": "Good implementation",
        })
        scores, reasoning = parse_judge_response(response)
        assert scores == {"Korrektheit": 8.0, "Code-Struktur": 7.0}
        assert reasoning == "Good implementation"

    def test_invalid_json(self):
        with pytest.raises(ValueError):
            parse_judge_response("not json at all")

    def test_missing_scores(self):
        response = json.dumps({"reasoning": "test"})
        with pytest.raises(ValueError, match="scores"):
            parse_judge_response(response)

    def test_score_clamping(self):
        """Scores outside 1-10 should be clamped."""
        response = json.dumps({
            "scores": {"quality": 15, "style": -1},
            "reasoning": "test",
        })
        scores, _ = parse_judge_response(response)
        assert scores["quality"] == 10.0
        assert scores["style"] == 1.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_judge.py -v`
Expected: FAIL

- [ ] **Step 3: Implement judge.py**

```python
# cccb/judge.py
"""LLM-as-Judge evaluation via Claude Agent SDK."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from cccb.models import TaskDefinition

logger = logging.getLogger(__name__)

MAX_DIFF_CHARS = 50_000

JUDGE_TEMPLATE = """Du bewertest Code, der von einem KI-Coding-Assistenten generiert wurde.

## Aufgabe
{description}

## Prompt an den Assistenten
{prompt}

## Generierter Code (git diff vom Setup zum Ergebnis)
{diff_section}

## Bewertungskriterien
{criteria_list}

## Bewertungsanker
- 1-2: Voellig unbrauchbar, grundlegend falsch
- 3-4: Ansatz erkennbar, aber wesentliche Maengel
- 5-6: Funktioniert grundsaetzlich, erfuellt Anforderungen teilweise
- 7-8: Gute Qualitaet, erfuellt alle Anforderungen solide
- 9-10: Exzellent, uebertrifft Erwartungen in Eleganz/Effizienz

Bewerte jedes Kriterium einzeln auf der Skala 1-10.
Antworte als JSON mit "scores" (Objekt: Kriterium -> Zahl) und "reasoning" (String)."""

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "scores": {
            "type": "object",
            "description": "Bewertung pro Kriterium (1-10)",
            "additionalProperties": {"type": "number", "minimum": 1, "maximum": 10},
        },
        "reasoning": {
            "type": "string",
            "description": "Kurze Begruendung der Bewertung",
        },
    },
    "required": ["scores", "reasoning"],
}


def build_judge_prompt(task: TaskDefinition, git_diff: str) -> str:
    """Build the judge prompt from task and diff."""
    if not git_diff.strip():
        diff_section = "[Kein Code generiert — der Diff ist leer.]"
    elif len(git_diff) > MAX_DIFF_CHARS:
        diff_section = git_diff[:MAX_DIFF_CHARS] + "\n\n[DIFF TRUNCATED — exceeded 50KB]"
    else:
        diff_section = git_diff

    criteria_list = "\n".join(f"- {c}" for c in task.judge.criteria)

    return JUDGE_TEMPLATE.format(
        description=task.description,
        prompt=task.prompt,
        diff_section=diff_section,
        criteria_list=criteria_list,
    )


def parse_judge_response(response_text: str) -> tuple[dict[str, float], str]:
    """Parse the judge's JSON response.

    Returns (scores_dict, reasoning_string).
    Clamps scores to 1-10 range.
    """
    try:
        data = json.loads(response_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Judge response is not valid JSON: {e}")

    if "scores" not in data:
        raise ValueError("Judge response missing 'scores' field")

    scores: dict[str, float] = {}
    for key, value in data["scores"].items():
        clamped = max(1.0, min(10.0, float(value)))
        scores[key] = clamped

    reasoning = data.get("reasoning", "")
    return scores, reasoning


async def evaluate_run(
    task: TaskDefinition,
    git_diff: str,
    working_dir: Path,
) -> tuple[dict[str, float], str]:
    """Run LLM-as-Judge evaluation and return (scores, reasoning).

    Uses Claude Agent SDK with max_turns=1 and no tools.
    """
    try:
        from claude_agent_sdk import query as sdk_query, ClaudeAgentOptions, AssistantMessage, TextBlock
    except ImportError:
        raise RuntimeError("claude-agent-sdk not installed")

    judge_prompt = build_judge_prompt(task, git_diff)

    options = ClaudeAgentOptions(
        permission_mode="dangerouslySkipPermissions",
        max_turns=1,
        cwd=str(working_dir),
        allowed_tools=[],
    )

    response_text = ""
    async for message in sdk_query(prompt=judge_prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    response_text += block.text

    if not response_text:
        raise ValueError("Judge returned empty response")

    return parse_judge_response(response_text)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_judge.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add cccb/judge.py tests/test_judge.py
git commit -m "feat: LLM-as-Judge evaluation with prompt builder and response parser"
```

---

## Chunk 5: Runner (Orchestration)

### Task 8: runner.py — Benchmark Engine

**Files:**
- Create: `cccb/runner.py`
- Create: `tests/test_runner.py`

- [ ] **Step 1: Write tests for runner**

```python
# tests/test_runner.py
"""Tests for the benchmark runner orchestration."""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
from cccb.runner import BenchmarkRunner, RunEvent
from cccb.models import (
    TaskDefinition, ConfigProfile, ClaudeSettings,
    JudgeCriteria, RunResult,
)


@pytest.fixture
def mock_task() -> TaskDefinition:
    return TaskDefinition(
        name="Hello World",
        category="codegen",
        description="Create hello.py",
        prompt="Create hello.py",
        setup_files=[],
        checks=[],
        judge=JudgeCriteria(criteria=["quality"], scale="1-10"),
        claude_settings=ClaudeSettings(max_turns=5, timeout=10),
    )


@pytest.fixture
def mock_config(sample_config_dir) -> ConfigProfile:
    return ConfigProfile(name="baseline", path=sample_config_dir, description="Test config")


class TestBenchmarkRunner:
    def test_build_matrix(self, mock_task, mock_config):
        runner = BenchmarkRunner(
            repo_root=Path("/tmp/test"),
            configs=[mock_config],
            tasks=[mock_task],
        )
        matrix = runner.build_matrix()
        assert len(matrix) == 1
        assert matrix[0] == (mock_config, mock_task)

    def test_build_matrix_multiple(self, mock_task, mock_config):
        config2 = ConfigProfile(name="advanced", path=mock_config.path, description="Advanced")
        runner = BenchmarkRunner(
            repo_root=Path("/tmp/test"),
            configs=[mock_config, config2],
            tasks=[mock_task, mock_task],
        )
        matrix = runner.build_matrix()
        assert len(matrix) == 4  # 2 configs x 2 tasks

    def test_task_slug(self):
        from cccb.runner import task_slug
        assert task_slug("REST API erstellen") == "rest-api-erstellen"
        assert task_slug("Memory Leak finden!") == "memory-leak-finden"

    @pytest.mark.asyncio
    async def test_run_single_mocked(self, mock_task, mock_config, tmp_repo):
        """Test a single run with all components mocked."""
        from cccb.executor import ExecutionResult

        runner = BenchmarkRunner(
            repo_root=tmp_repo,
            configs=[mock_config],
            tasks=[mock_task],
        )

        mock_exec_result = ExecutionResult(
            duration_ms=5000, duration_api_ms=4000,
            total_cost_usd=0.05, num_turns=3,
            session_id="test-sess", is_error=False,
        )

        with patch("cccb.runner.execute_task", new_callable=AsyncMock, return_value=mock_exec_result), \
             patch("cccb.runner.run_checks", return_value=[]), \
             patch("cccb.runner.evaluate_run", new_callable=AsyncMock, return_value=({"quality": 8.0}, "Good")):

            events = []
            async for event in runner.run(on_event=lambda e: events.append(e)):
                pass

            assert len(runner.results) == 1
            result = runner.results[0]
            assert result.total_cost_usd == 0.05
            assert result.judge_average == 8.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_runner.py -v`
Expected: FAIL

- [ ] **Step 3: Implement runner.py**

```python
# cccb/runner.py
"""Benchmark engine — orchestrates config x task runs."""
from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator, Callable

from cccb.models import (
    ConfigProfile, TaskDefinition, RunResult,
    CheckResult, BenchmarkReport,
)
from cccb.isolation import WorktreeManager
from cccb.executor import execute_task, ExecutionResult
from cccb.checker import run_checks
from cccb.judge import evaluate_run
from cccb.scorer import (
    calculate_check_score, calculate_efficiency,
    calculate_total_score, calculate_config_average,
)

logger = logging.getLogger(__name__)


def task_slug(name: str) -> str:
    """Convert a task name to a filesystem-safe slug."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9äöüß\s-]", "", slug)
    slug = re.sub(r"[\s]+", "-", slug)
    return slug.strip("-")


@dataclass
class RunEvent:
    """Event emitted during benchmark execution for TUI updates."""

    type: str  # "run_start" | "run_complete" | "run_error" | "benchmark_done"
    config_name: str = ""
    task_name: str = ""
    run_index: int = 0
    total_runs: int = 0
    result: RunResult | None = None
    error: str = ""


class BenchmarkRunner:
    """Orchestrates benchmark runs for all config x task combinations."""

    def __init__(
        self,
        repo_root: Path,
        configs: list[ConfigProfile],
        tasks: list[TaskDefinition],
    ) -> None:
        self.repo_root = repo_root
        self.configs = configs
        self.tasks = tasks
        self.results: list[RunResult] = []
        self.worktree_mgr = WorktreeManager(repo_root)
        self._cancelled = False

    def build_matrix(self) -> list[tuple[ConfigProfile, TaskDefinition]]:
        """Generate all config x task combinations."""
        return [
            (config, task)
            for config in self.configs
            for task in self.tasks
        ]

    def cancel(self) -> None:
        """Signal cancellation — current run finishes, then stop."""
        self._cancelled = True

    async def run(
        self,
        on_event: Callable[[RunEvent], None] | None = None,
    ) -> AsyncIterator[RunEvent]:
        """Run all benchmark combinations sequentially.

        Yields RunEvent for each step, suitable for TUI progress updates.
        """
        matrix = self.build_matrix()
        total = len(matrix)

        # Cleanup old worktrees
        self.worktree_mgr.cleanup_all()

        for idx, (config, task) in enumerate(matrix):
            if self._cancelled:
                break

            slug = task_slug(task.name)
            event = RunEvent(
                type="run_start",
                config_name=config.name,
                task_name=task.name,
                run_index=idx + 1,
                total_runs=total,
            )
            if on_event:
                on_event(event)
            yield event

            try:
                result = await self._run_single(config, task, slug)
                self.results.append(result)

                event = RunEvent(
                    type="run_complete",
                    config_name=config.name,
                    task_name=task.name,
                    run_index=idx + 1,
                    total_runs=total,
                    result=result,
                )
            except Exception as e:
                logger.error("Run failed: %s x %s: %s", config.name, task.name, e)
                event = RunEvent(
                    type="run_error",
                    config_name=config.name,
                    task_name=task.name,
                    run_index=idx + 1,
                    total_runs=total,
                    error=str(e),
                )

            if on_event:
                on_event(event)
            yield event

        # Calculate efficiency ranks per task
        self._calculate_efficiency_scores()

        yield RunEvent(type="benchmark_done", total_runs=total)

    async def _run_single(
        self,
        config: ConfigProfile,
        task: TaskDefinition,
        slug: str,
    ) -> RunResult:
        """Execute a single config x task combination."""
        # 1. Create worktree
        wt_path = self.worktree_mgr.create_worktree(config.name, slug)

        # 2. Copy config + setup files
        self.worktree_mgr.copy_config_files(wt_path, config.path)
        self.worktree_mgr.copy_setup_files(wt_path, task.setup_files)
        setup_hash = self.worktree_mgr.commit_setup(wt_path, config.name, slug)

        # 3. Execute Claude Code
        exec_result = await execute_task(task, wt_path)

        # 4. Run automated checks
        check_results = run_checks(task.checks, cwd=wt_path)
        checks_passed = sum(1 for cr in check_results if cr.passed)

        # 5. Commit result
        result_hash = self.worktree_mgr.commit_result(
            wt_path, config.name, slug,
            score=0.0,  # Placeholder, updated after scoring
            timeout=exec_result.timed_out,
            error=exec_result.is_error,
        )

        # 6. Run LLM-as-Judge
        git_diff = self.worktree_mgr.get_diff(wt_path, setup_hash, result_hash)
        try:
            judge_scores, _reasoning = await evaluate_run(task, git_diff, wt_path)
        except Exception as e:
            logger.error("Judge failed for %s x %s: %s", config.name, task.name, e)
            judge_scores = {c: 1.0 for c in task.judge.criteria}

        judge_average = sum(judge_scores.values()) / max(len(judge_scores), 1)

        # 7. Calculate scores
        check_score = calculate_check_score(checks_passed, len(task.checks))
        total_score = calculate_total_score(
            check_score=check_score,
            judge_score=judge_average,
            efficiency=5.0,  # Placeholder — updated in _calculate_efficiency_scores
        )

        return RunResult(
            config=config,
            task=task,
            duration_ms=exec_result.duration_ms,
            duration_api_ms=exec_result.duration_api_ms,
            total_cost_usd=exec_result.total_cost_usd,
            num_turns=exec_result.num_turns,
            session_id=exec_result.session_id,
            checks_passed=checks_passed,
            checks_total=len(task.checks),
            check_details=check_results,
            judge_scores=judge_scores,
            judge_average=judge_average,
            total_score=total_score,
            worktree_path=str(wt_path.relative_to(self.repo_root)),
            branch_name=f"bench/{config.name}/{slug}",
            commit_hash=result_hash,
        )

    def _calculate_efficiency_scores(self) -> None:
        """Recalculate efficiency and total scores using ranking per task."""
        # Group results by task
        by_task: dict[str, list[RunResult]] = {}
        for r in self.results:
            by_task.setdefault(r.task.name, []).append(r)

        n_configs = len(self.configs)

        for task_name, task_results in by_task.items():
            # Rank by cost (ascending)
            sorted_by_cost = sorted(task_results, key=lambda r: r.total_cost_usd)
            cost_ranks = {id(r): i + 1 for i, r in enumerate(sorted_by_cost)}

            # Rank by time (ascending)
            sorted_by_time = sorted(task_results, key=lambda r: r.duration_ms)
            time_ranks = {id(r): i + 1 for i, r in enumerate(sorted_by_time)}

            for r in task_results:
                efficiency = calculate_efficiency(
                    cost_rank=cost_ranks[id(r)],
                    time_rank=time_ranks[id(r)],
                    n_configs=n_configs,
                    timeout=r.duration_ms == 0 and r.checks_passed == 0,
                )
                check_score = calculate_check_score(r.checks_passed, r.checks_total)
                r.total_score = calculate_total_score(
                    check_score=check_score,
                    judge_score=r.judge_average,
                    efficiency=efficiency,
                )

    def build_report(self, summary: str = "") -> BenchmarkReport:
        """Build the final benchmark report."""
        if not self.results:
            return BenchmarkReport(
                configs=self.configs,
                tasks=self.tasks,
                results=[],
                winner=None,
                summary=summary,
            )

        # Find winner: config with highest average score
        config_scores: dict[str, list[float]] = {}
        for r in self.results:
            config_scores.setdefault(r.config.name, []).append(r.total_score)

        config_averages = {
            name: calculate_config_average(scores)
            for name, scores in config_scores.items()
        }
        winner_name = max(config_averages, key=config_averages.get)
        winner = next(c for c in self.configs if c.name == winner_name)

        return BenchmarkReport(
            configs=self.configs,
            tasks=self.tasks,
            results=self.results,
            winner=winner,
            summary=summary,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_runner.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add cccb/runner.py tests/test_runner.py
git commit -m "feat: benchmark runner with full orchestration pipeline"
```

---

## Chunk 6: TUI Screens

### Task 9: Textual App Shell & Config Select Screen

**Files:**
- Create: `cccb/app.py`
- Create: `cccb/screens/__init__.py`
- Create: `cccb/screens/config_select.py`
- Create: `cccb/cccb.tcss` (Textual CSS)
- Create: `tests/test_screens.py`

- [ ] **Step 1: Write tests for config select screen**

```python
# tests/test_screens.py
"""Tests for TUI screens using Textual's async test API."""
import pytest
from pathlib import Path
from textual.app import App
from cccb.screens.config_select import ConfigSelectScreen
from cccb.models import ConfigProfile


class ConfigSelectTestApp(App):
    """Test wrapper app."""
    def on_mount(self):
        self.push_screen(ConfigSelectScreen())


class TestConfigSelectScreen:
    @pytest.mark.asyncio
    async def test_screen_mounts(self):
        app = ConfigSelectTestApp()
        async with app.run_test() as pilot:
            assert app.screen.__class__.__name__ == "ConfigSelectScreen"

    @pytest.mark.asyncio
    async def test_minimum_two_configs_required(self):
        app = ConfigSelectTestApp()
        async with app.run_test() as pilot:
            screen = app.screen
            # "Weiter" button should be disabled with < 2 selections
            weiter = screen.query_one("#btn-next", expect_type=None)
            if weiter:
                assert weiter.disabled is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_screens.py -v`
Expected: FAIL

- [ ] **Step 3: Create Textual CSS file**

```css
/* cccb/cccb.tcss */
Screen {
    background: $surface;
}

#header {
    dock: top;
    height: 3;
    content-align: center middle;
    background: $primary;
    color: $text;
    text-style: bold;
}

#footer {
    dock: bottom;
    height: 3;
    background: $primary-background;
}

.config-list {
    height: 1fr;
    border: solid $primary;
    padding: 1;
}

.config-preview {
    height: 1fr;
    border: solid $secondary;
    padding: 1;
}

.task-filter {
    height: 3;
    layout: horizontal;
}

.task-filter Button {
    margin: 0 1;
}

.progress-section {
    height: auto;
    padding: 1;
}

.run-log {
    height: 1fr;
    border: solid $primary;
    padding: 1;
}

.results-table {
    height: 1fr;
}

.winner-banner {
    height: 3;
    content-align: center middle;
    background: $success;
    color: $text;
    text-style: bold;
}

.btn-row {
    height: 3;
    layout: horizontal;
    align: center middle;
}

.btn-row Button {
    margin: 0 2;
}
```

- [ ] **Step 4: Create app.py shell**

```python
# cccb/app.py
"""CCCB Textual TUI application."""
from __future__ import annotations

from pathlib import Path
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer

from cccb.screens.config_select import ConfigSelectScreen


class CCCBApp(App):
    """Claude Code Config Benchmark — TUI Application."""

    CSS_PATH = "cccb.tcss"  # Textual resolves relative to the module's directory
    TITLE = "CCCB Benchmark"
    BINDINGS = [
        ("q", "quit", "Beenden"),
    ]

    def __init__(self, repo_root: Path | None = None) -> None:
        super().__init__()
        self.repo_root = repo_root or Path.cwd()
        self.selected_configs: list = []
        self.selected_tasks: list = []

    def on_mount(self) -> None:
        self.push_screen(ConfigSelectScreen())
```

- [ ] **Step 5: Create screens/__init__.py**

```python
# cccb/screens/__init__.py
"""TUI screens for CCCB benchmark workflow."""
__all__ = ["ConfigSelectScreen", "TaskSelectScreen", "RunningScreen", "ResultsScreen"]
```

- [ ] **Step 6: Implement ConfigSelectScreen**

```python
# cccb/screens/config_select.py
"""Screen: Select configuration directories to benchmark."""
from __future__ import annotations

from pathlib import Path
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import (
    Static, Button, DirectoryTree, ListView, ListItem, Label,
    TextArea,
)
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive

from cccb.models import ConfigProfile


class ConfigSelectScreen(Screen):
    """Select configuration directories to benchmark against each other."""

    TITLE = "Konfigurationen auswaehlen"

    selected_configs: reactive[list[ConfigProfile]] = reactive(list, init=False)

    def compose(self) -> ComposeResult:
        yield Static("CCCB Benchmark — Konfigurationen", id="header")
        with Horizontal():
            with Vertical(classes="config-list"):
                yield Static("Verzeichnisse auswaehlen:")
                yield ListView(id="config-listview")
                yield Button("Verzeichnis hinzufuegen...", id="btn-add", variant="default")
            with Vertical(classes="config-preview"):
                yield Static("CLAUDE.md Preview:")
                yield TextArea(read_only=True, id="preview-area")
        with Horizontal(classes="btn-row"):
            yield Static(id="selection-count")
            yield Button("Weiter →", id="btn-next", variant="primary", disabled=True)

    def on_mount(self) -> None:
        self.selected_configs = []
        self._update_count()

    def _update_count(self) -> None:
        count = len(self.selected_configs)
        label = self.query_one("#selection-count", Static)
        label.update(f"{count} von min. 2 ausgewaehlt")
        btn = self.query_one("#btn-next", Button)
        btn.disabled = count < 2

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-next":
            from cccb.screens.task_select import TaskSelectScreen
            self.app.push_screen(TaskSelectScreen())
        elif event.button.id == "btn-add":
            # Placeholder for directory picker
            pass

    def add_config(self, path: Path) -> None:
        """Add a config directory to the selection."""
        try:
            config = ConfigProfile.from_dir(path)
        except ValueError as e:
            self.notify(str(e), severity="error")
            return

        self.selected_configs.append(config)
        listview = self.query_one("#config-listview", ListView)
        listview.append(ListItem(Label(f"[bold]{config.name}[/] — {config.description}")))
        self._update_count()
```

- [ ] **Step 7: Run tests**

Run: `pytest tests/test_screens.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add cccb/app.py cccb/cccb.tcss cccb/screens/__init__.py cccb/screens/config_select.py tests/test_screens.py
git commit -m "feat: Textual app shell and Config Select screen"
```

---

### Task 10: Task Select Screen

**Files:**
- Create: `cccb/screens/task_select.py`

- [ ] **Step 1: Implement TaskSelectScreen**

```python
# cccb/screens/task_select.py
"""Screen: Select benchmark tasks to run."""
from __future__ import annotations

from pathlib import Path
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, Button, ListView, ListItem, Label, Checkbox
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive

from cccb.models import TaskDefinition


class TaskSelectScreen(Screen):
    """Select tasks and categories to include in the benchmark."""

    TITLE = "Aufgaben auswaehlen"

    selected_tasks: reactive[list[TaskDefinition]] = reactive(list, init=False)
    all_tasks: reactive[list[TaskDefinition]] = reactive(list, init=False)
    active_filter: reactive[str] = reactive("all")

    def compose(self) -> ComposeResult:
        yield Static("CCCB Benchmark — Aufgaben", id="header")
        with Horizontal(classes="task-filter"):
            yield Button("Alle", id="filter-all", variant="primary")
            yield Button("Codegen", id="filter-codegen")
            yield Button("Debugging", id="filter-debugging")
            yield Button("Refactoring", id="filter-refactoring")
        with Vertical(classes="config-list"):
            yield ListView(id="task-listview")
        with Horizontal(classes="btn-row"):
            yield Static(id="run-count")
            yield Button("← Zurueck", id="btn-back")
            yield Button("Start ▶", id="btn-start", variant="success", disabled=True)

    def on_mount(self) -> None:
        self.selected_tasks = []
        self._load_tasks()
        self._update_count()

    def _load_tasks(self) -> None:
        """Load all YAML task files from the tasks/ directory."""
        tasks_dir = Path.cwd() / "tasks"
        if not tasks_dir.exists():
            self.notify("Kein tasks/ Verzeichnis gefunden", severity="warning")
            return

        self.all_tasks = []
        for yaml_file in sorted(tasks_dir.rglob("*.yaml")):
            try:
                task = TaskDefinition.from_yaml(yaml_file)
                self.all_tasks.append(task)
            except Exception as e:
                self.notify(f"Fehler: {yaml_file.name}: {e}", severity="warning")

        self._refresh_list()

    def _refresh_list(self) -> None:
        """Refresh the task list based on active filter."""
        listview = self.query_one("#task-listview", ListView)
        listview.clear()

        for task in self.all_tasks:
            if self.active_filter != "all" and task.category != self.active_filter:
                continue
            cat_label = {"codegen": "codegen", "debugging": "debug", "refactoring": "refactor"}.get(
                task.category, task.category
            )
            listview.append(
                ListItem(Label(f"[{cat_label}] {task.name} — {task.description[:60]}"))
            )

    def _update_count(self) -> None:
        n_tasks = len(self.selected_tasks)
        n_configs = len(getattr(self.app, "selected_configs", []))
        total = n_tasks * n_configs
        label = self.query_one("#run-count", Static)
        label.update(f"{n_tasks} Aufgaben x {n_configs} Configs = {total} Durchlaeufe")
        btn = self.query_one("#btn-start", Button)
        btn.disabled = n_tasks == 0

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-back":
            self.app.pop_screen()
        elif event.button.id == "btn-start":
            from cccb.screens.running import RunningScreen
            self.app.push_screen(RunningScreen())
        elif event.button.id and event.button.id.startswith("filter-"):
            category = event.button.id.replace("filter-", "")
            self.active_filter = category
            self._refresh_list()
```

- [ ] **Step 2: Commit**

```bash
git add cccb/screens/task_select.py
git commit -m "feat: Task Select screen with category filtering"
```

---

### Task 11: Running Screen

**Files:**
- Create: `cccb/screens/running.py`

- [ ] **Step 1: Implement RunningScreen**

```python
# cccb/screens/running.py
"""Screen: Live benchmark progress display."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import (
    Static, Button, ProgressBar, ListView, ListItem, Label, RichLog,
)
from textual.containers import Vertical, Horizontal
from textual.worker import Worker, work
from textual.message import Message

from cccb.runner import BenchmarkRunner, RunEvent


class RunCompleted(Message):
    """Posted when a single run completes."""

    def __init__(self, event: RunEvent) -> None:
        super().__init__()
        self.event = event


class RunningScreen(Screen):
    """Live progress during benchmark execution."""

    TITLE = "Benchmark laeuft..."

    def compose(self) -> ComposeResult:
        yield Static("CCCB Benchmark — Laeuft...", id="header")
        with Vertical(classes="progress-section"):
            yield Static("Initialisiere...", id="current-run")
            yield ProgressBar(total=100, show_eta=True, id="main-progress")
            yield Static("Kosten: $0.00", id="cost-ticker")
        with Vertical(classes="run-log"):
            yield Static("Abgeschlossene Durchlaeufe:")
            yield RichLog(id="run-log", highlight=True, markup=True)
        with Horizontal(classes="btn-row"):
            yield Button("Abbrechen ✕", id="btn-cancel", variant="error")

    def on_mount(self) -> None:
        self._run_benchmark()

    @work(exclusive=True)
    async def _run_benchmark(self) -> None:
        """Run the benchmark in a background worker."""
        runner: BenchmarkRunner = getattr(self.app, "runner", None)
        if runner is None:
            self.notify("Kein Benchmark konfiguriert", severity="error")
            return

        total_cost = 0.0

        async for event in runner.run():
            if event.type == "run_start":
                self.call_from_thread(self._update_current, event)
            elif event.type == "run_complete":
                if event.result:
                    total_cost += event.result.total_cost_usd
                self.call_from_thread(self._log_result, event, total_cost)
            elif event.type == "run_error":
                self.call_from_thread(self._log_error, event)
            elif event.type == "benchmark_done":
                self.call_from_thread(self._finish)

    def _update_current(self, event: RunEvent) -> None:
        label = self.query_one("#current-run", Static)
        label.update(
            f"Durchlauf {event.run_index}/{event.total_runs}: "
            f"{event.config_name} x {event.task_name}"
        )
        progress = self.query_one("#main-progress", ProgressBar)
        progress.update(total=event.total_runs, progress=event.run_index - 1)

    def _log_result(self, event: RunEvent, total_cost: float) -> None:
        log = self.query_one("#run-log", RichLog)
        r = event.result
        if r:
            log.write(
                f"[green]✓[/] {event.config_name} x {event.task_name} "
                f"({r.duration_ms / 1000:.1f}s, ${r.total_cost_usd:.3f}, "
                f"{r.checks_passed}/{r.checks_total} Checks)"
            )
        progress = self.query_one("#main-progress", ProgressBar)
        progress.update(progress=event.run_index)
        cost_label = self.query_one("#cost-ticker", Static)
        cost_label.update(f"Kosten: ${total_cost:.3f}")

    def _log_error(self, event: RunEvent) -> None:
        log = self.query_one("#run-log", RichLog)
        log.write(f"[red]✗[/] {event.config_name} x {event.task_name}: {event.error}")

    def _finish(self) -> None:
        from cccb.screens.results import ResultsScreen
        self.app.push_screen(ResultsScreen())

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            runner = getattr(self.app, "runner", None)
            if runner:
                runner.cancel()
            self.notify("Benchmark wird nach aktuellem Durchlauf gestoppt...")
```

- [ ] **Step 2: Commit**

```bash
git add cccb/screens/running.py
git commit -m "feat: Running screen with live progress and cost ticker"
```

---

### Task 12: Results Screen

**Files:**
- Create: `cccb/screens/results.py`

- [ ] **Step 1: Implement ResultsScreen**

```python
# cccb/screens/results.py
"""Screen: Benchmark results dashboard with comparison table."""
from __future__ import annotations

import json
from pathlib import Path

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import (
    Static, Button, DataTable, RichLog,
)
from textual.containers import Vertical, Horizontal

from cccb.models import BenchmarkReport
from cccb.scorer import calculate_config_average


class ResultsScreen(Screen):
    """Display benchmark results with comparison table and recommendations."""

    TITLE = "Ergebnisse"

    def compose(self) -> ComposeResult:
        yield Static("CCCB Benchmark — Ergebnisse", id="header")
        yield Static("", id="winner-banner", classes="winner-banner")
        yield DataTable(id="results-table", classes="results-table")
        with Vertical():
            yield Static("Verbesserungsvorschlaege:")
            yield RichLog(id="suggestions-log", highlight=True, markup=True)
        with Horizontal(classes="btn-row"):
            yield Button("Details", id="btn-details")
            yield Button("Export JSON", id="btn-export", variant="primary")
            yield Button("Neuer Benchmark ↻", id="btn-restart", variant="success")

    def on_mount(self) -> None:
        report: BenchmarkReport = getattr(self.app, "report", None)
        if report is None:
            self.notify("Keine Ergebnisse vorhanden", severity="error")
            return

        self._populate_table(report)
        self._show_winner(report)
        self._show_suggestions(report)

    def _populate_table(self, report: BenchmarkReport) -> None:
        table = self.query_one("#results-table", DataTable)
        table.add_columns("Config", "Score", "Zeit (Avg)", "Kosten (Avg)", "Checks")

        # Group results by config
        by_config: dict[str, list] = {}
        for r in report.results:
            by_config.setdefault(r.config.name, []).append(r)

        for config_name, results in sorted(by_config.items()):
            avg_score = calculate_config_average([r.total_score for r in results])
            avg_time = sum(r.duration_ms for r in results) / len(results) / 1000
            avg_cost = sum(r.total_cost_usd for r in results) / len(results)
            total_checks = sum(r.checks_passed for r in results)
            total_possible = sum(r.checks_total for r in results)

            is_winner = report.winner and report.winner.name == config_name
            prefix = "★ " if is_winner else "  "

            table.add_row(
                f"{prefix}{config_name}",
                f"{avg_score:.1f}",
                f"{avg_time:.1f}s",
                f"${avg_cost:.3f}",
                f"{total_checks}/{total_possible}",
            )

    def _show_winner(self, report: BenchmarkReport) -> None:
        banner = self.query_one("#winner-banner", Static)
        if report.winner:
            # Calculate deltas vs second place
            by_config: dict[str, list] = {}
            for r in report.results:
                by_config.setdefault(r.config.name, []).append(r)

            averages = {
                name: calculate_config_average([r.total_score for r in results])
                for name, results in by_config.items()
            }
            sorted_avgs = sorted(averages.items(), key=lambda x: x[1], reverse=True)

            if len(sorted_avgs) >= 2:
                winner_avg = sorted_avgs[0][1]
                second_avg = sorted_avgs[1][1]
                delta_pct = ((winner_avg - second_avg) / max(second_avg, 0.01)) * 100
                banner.update(
                    f"★ Gewinner: {report.winner.name} "
                    f"(+{delta_pct:.0f}% gegenueber {sorted_avgs[1][0]})"
                )
            else:
                banner.update(f"★ Gewinner: {report.winner.name}")
        else:
            banner.update("Keine Ergebnisse")

    def _show_suggestions(self, report: BenchmarkReport) -> None:
        log = self.query_one("#suggestions-log", RichLog)
        if report.summary:
            log.write(report.summary)
        else:
            log.write("[dim]Keine Verbesserungsvorschlaege verfuegbar.[/]")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-export":
            self._export_json()
        elif event.button.id == "btn-restart":
            # Pop all screens back to start
            while len(self.app.screen_stack) > 1:
                self.app.pop_screen()
        elif event.button.id == "btn-details":
            pass  # TODO: detail view

    def _export_json(self) -> None:
        """Export benchmark results as JSON."""
        report: BenchmarkReport = getattr(self.app, "report", None)
        if not report:
            return

        export_data = {
            "configs": [{"name": c.name, "path": str(c.path)} for c in report.configs],
            "tasks": [{"name": t.name, "category": t.category} for t in report.tasks],
            "results": [
                {
                    "config": r.config.name,
                    "task": r.task.name,
                    "total_score": r.total_score,
                    "duration_ms": r.duration_ms,
                    "total_cost_usd": r.total_cost_usd,
                    "checks_passed": r.checks_passed,
                    "checks_total": r.checks_total,
                    "judge_scores": r.judge_scores,
                    "judge_average": r.judge_average,
                }
                for r in report.results
            ],
            "winner": report.winner.name if report.winner else None,
            "summary": report.summary,
        }

        export_path = Path.cwd() / "benchmark-results.json"
        export_path.write_text(json.dumps(export_data, indent=2, ensure_ascii=False))
        self.notify(f"Exportiert: {export_path}")
```

- [ ] **Step 2: Commit**

```bash
git add cccb/screens/results.py
git commit -m "feat: Results screen with comparison table, winner banner, and JSON export"
```

---

## Chunk 7: Sample Tasks & Integration

### Task 13: Sample Task Definitions

**Files:**
- Create: `tasks/codegen/rest-api.yaml`
- Create: `tasks/codegen/cli-parser.yaml`
- Create: `tasks/debugging/memory-leak.yaml`
- Create: `tasks/debugging/race-condition.yaml`
- Create: `tasks/refactoring/extract-class.yaml`
- Create: `tasks/refactoring/async-migration.yaml`

- [ ] **Step 1: Create codegen tasks**

```yaml
# tasks/codegen/rest-api.yaml
name: "REST API erstellen"
category: "codegen"
description: "Erstelle eine vollstaendige REST API mit FastAPI inkl. CRUD-Endpunkte, Validierung und Error Handling"

prompt: |
  Erstelle eine REST API mit FastAPI fuer eine Aufgabenverwaltung (Todo-App).
  Anforderungen:
  - CRUD-Endpunkte (GET, POST, PUT, DELETE) fuer /todos
  - Pydantic-Modelle fuer Request/Response Validierung
  - Proper Error Handling (404, 422)
  - In-Memory Storage (kein DB noetig)
  - Schreibe Tests mit pytest und httpx

setup_files: []

checks:
  - type: "file_exists"
    path: "main.py"
  - type: "command"
    run: "python -m py_compile main.py"
    expect_exit_code: 0
  - type: "command"
    run: "python -m pytest tests/ -v --tb=short"
    expect_exit_code: 0

judge:
  criteria:
    - "Korrektheit: Funktionieren alle CRUD-Endpunkte wie spezifiziert?"
    - "Validierung: Werden ungueltige Eingaben sauber abgefangen?"
    - "Code-Struktur: Ist der Code gut organisiert und idiomatisch?"
    - "Vollstaendigkeit: Sind alle Anforderungen umgesetzt inkl. Tests?"
  scale: "1-10"

claude_settings:
  max_turns: 15
  allowed_tools:
    - "Edit"
    - "Write"
    - "Bash"
```

```yaml
# tasks/codegen/cli-parser.yaml
name: "CLI-Tool mit Click"
category: "codegen"
description: "Erstelle ein CLI-Tool mit Click fuer Datei-Operationen (suchen, ersetzen, zaehlen)"

prompt: |
  Erstelle ein CLI-Tool mit dem Click-Framework fuer Textdatei-Operationen.
  Anforderungen:
  - Unterkommandos: search, replace, count
  - search: Sucht ein Pattern in einer Datei, gibt Zeilennummern aus
  - replace: Ersetzt ein Pattern in einer Datei (mit --dry-run Option)
  - count: Zaehlt Zeilen, Woerter, Zeichen
  - Proper Error Handling (Datei nicht gefunden, etc.)
  - Hilfetexte fuer alle Kommandos und Optionen
  - Schreibe Tests mit pytest und click.testing.CliRunner

setup_files: []

checks:
  - type: "file_exists"
    path: "cli.py"
  - type: "command"
    run: "python -m py_compile cli.py"
    expect_exit_code: 0
  - type: "command"
    run: "python cli.py --help"
    expect_exit_code: 0
  - type: "command"
    run: "python -m pytest tests/ -v --tb=short"
    expect_exit_code: 0

judge:
  criteria:
    - "CLI-Design: Sind Kommandos und Optionen intuitiv und gut dokumentiert?"
    - "Korrektheit: Funktionieren alle Unterkommandos mit Edge Cases?"
    - "Error Handling: Werden fehlerhafte Eingaben sauber behandelt?"
    - "Testabdeckung: Decken die Tests alle Kommandos und Fehlerfaelle ab?"
  scale: "1-10"

claude_settings:
  max_turns: 15
  allowed_tools:
    - "Edit"
    - "Write"
    - "Bash"
```

- [ ] **Step 2: Create debugging tasks**

```yaml
# tasks/debugging/memory-leak.yaml
name: "Memory Leak finden"
category: "debugging"
description: "Finde und behebe einen Memory Leak in einer Python-Anwendung mit wachsendem Cache"

prompt: |
  Die Datei server.py hat einen Memory Leak. Der Server verarbeitet Anfragen
  und cached Ergebnisse, aber der Cache waechst unbegrenzt.

  1. Analysiere server.py und finde den Memory Leak
  2. Erklaere das Problem
  3. Behebe den Bug (z.B. LRU-Cache, TTL, max_size)
  4. Schreibe einen Test der beweist dass der Leak behoben ist

setup_files:
  - source: "fixtures/memory-leak/server.py"
    target: "server.py"

checks:
  - type: "command"
    run: "python -m py_compile server.py"
    expect_exit_code: 0
  - type: "command"
    run: "python -m pytest test_server.py -v --tb=short"
    expect_exit_code: 0

judge:
  criteria:
    - "Diagnose: Wurde der Memory Leak korrekt identifiziert?"
    - "Fix-Qualitaet: Ist die Loesung robust und idiomatic?"
    - "Erklaerung: Ist die Analyse verstaendlich und korrekt?"
    - "Test: Beweist der Test effektiv dass der Leak behoben ist?"
  scale: "1-10"

claude_settings:
  max_turns: 10
  allowed_tools:
    - "Read"
    - "Edit"
    - "Write"
    - "Bash"
```

```yaml
# tasks/debugging/race-condition.yaml
name: "Race Condition beheben"
category: "debugging"
description: "Finde und behebe eine Race Condition in einem Multi-Threaded Counter"

prompt: |
  Die Datei counter.py implementiert einen Thread-sicheren Counter — aber er ist
  es nicht wirklich. Bei hoher Last gehen Inkremente verloren.

  1. Analysiere counter.py und finde die Race Condition
  2. Erklaere warum das Problem auftritt
  3. Behebe den Bug mit proper Synchronisation
  4. Schreibe einen Stresstest der beweist dass der Fix funktioniert

setup_files:
  - source: "fixtures/race-condition/counter.py"
    target: "counter.py"

checks:
  - type: "command"
    run: "python -m py_compile counter.py"
    expect_exit_code: 0
  - type: "command"
    run: "python -m pytest test_counter.py -v --tb=short"
    expect_exit_code: 0

judge:
  criteria:
    - "Diagnose: Wurde die Race Condition korrekt identifiziert?"
    - "Fix: Ist die Synchronisation korrekt und performant?"
    - "Erklaerung: Versteht man warum das Problem auftrat?"
    - "Stresstest: Ist der Test aussagekraeftig und reproduzierbar?"
  scale: "1-10"

claude_settings:
  max_turns: 10
  allowed_tools:
    - "Read"
    - "Edit"
    - "Write"
    - "Bash"
```

- [ ] **Step 3: Create refactoring tasks**

```yaml
# tasks/refactoring/extract-class.yaml
name: "God Object aufloesen"
category: "refactoring"
description: "Refactore eine 500-Zeilen God Class in separate, fokussierte Klassen"

prompt: |
  Die Datei app.py enthaelt eine monolithische AppManager-Klasse mit ~500 Zeilen,
  die User-Verwaltung, Email-Versand, Logging und Konfiguration in einer Klasse vereint.

  1. Analysiere die Verantwortlichkeiten
  2. Extrahiere mindestens 3 separate Klassen mit klaren Interfaces
  3. Stelle sicher dass die bestehende Funktionalitaet erhalten bleibt
  4. Schreibe Tests fuer die neuen Klassen

setup_files:
  - source: "fixtures/god-object/app.py"
    target: "app.py"
  - source: "fixtures/god-object/test_app.py"
    target: "test_app.py"

checks:
  - type: "command"
    run: "python -m py_compile app.py"
    expect_exit_code: 0
  - type: "command"
    run: "python -m pytest test_app.py -v --tb=short"
    expect_exit_code: 0
  - type: "command"
    run: "python -c \"import ast; tree = ast.parse(open('app.py').read()); classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]; assert len(classes) >= 3, f'Only {len(classes)} classes found'\""
    expect_exit_code: 0

judge:
  criteria:
    - "Separation of Concerns: Sind die Verantwortlichkeiten sauber getrennt?"
    - "Interface-Design: Sind die Klassen-Interfaces minimal und klar?"
    - "Backward Compatibility: Funktionieren bestehende Tests noch?"
    - "Code-Qualitaet: Ist der refactored Code besser lesbar und wartbar?"
  scale: "1-10"

claude_settings:
  max_turns: 20
  allowed_tools:
    - "Read"
    - "Edit"
    - "Write"
    - "Bash"
```

```yaml
# tasks/refactoring/async-migration.yaml
name: "Sync zu Async Migration"
category: "refactoring"
description: "Migriere synchrone HTTP-Aufrufe zu async/await mit aiohttp"

prompt: |
  Die Datei fetcher.py macht synchrone HTTP-Aufrufe mit requests.
  Migriere den Code zu async/await mit aiohttp:

  1. Ersetze requests durch aiohttp
  2. Mache alle fetch-Funktionen async
  3. Nutze asyncio.gather fuer parallele Aufrufe wo moeglich
  4. Behalte das Error Handling bei
  5. Aktualisiere die Tests

setup_files:
  - source: "fixtures/sync-to-async/fetcher.py"
    target: "fetcher.py"
  - source: "fixtures/sync-to-async/test_fetcher.py"
    target: "test_fetcher.py"

checks:
  - type: "command"
    run: "python -m py_compile fetcher.py"
    expect_exit_code: 0
  - type: "command"
    run: "python -c \"import ast; src = open('fetcher.py').read(); tree = ast.parse(src); asyncs = [n for n in ast.walk(tree) if isinstance(n, ast.AsyncFunctionDef)]; assert len(asyncs) >= 2, f'Only {len(asyncs)} async functions'\""
    expect_exit_code: 0
  - type: "command"
    run: "python -m pytest test_fetcher.py -v --tb=short"
    expect_exit_code: 0

judge:
  criteria:
    - "Async-Korrektheit: Sind alle I/O-Calls korrekt async?"
    - "Parallelisierung: Wird asyncio.gather sinnvoll eingesetzt?"
    - "Error Handling: Ist das Fehlerverhalten aequivalent zum Original?"
    - "Testqualitaet: Testen die Tests async-spezifische Szenarien?"
  scale: "1-10"

claude_settings:
  max_turns: 15
  allowed_tools:
    - "Read"
    - "Edit"
    - "Write"
    - "Bash"
```

- [ ] **Step 4: Create fixture directories (empty placeholders)**

```bash
mkdir -p tasks/codegen tasks/debugging tasks/refactoring
mkdir -p tasks/fixtures/memory-leak tasks/fixtures/race-condition
mkdir -p tasks/fixtures/god-object tasks/fixtures/sync-to-async
```

Note: Fixture source files (server.py, counter.py, app.py, fetcher.py) will be created during Task 14.

- [ ] **Step 5: Commit**

```bash
git add tasks/
git commit -m "feat: sample benchmark tasks (codegen, debugging, refactoring)"
```

---

### Task 14: Task Fixtures (Bug/Refactoring Source Files)

**Files:**
- Create: `tasks/fixtures/memory-leak/server.py`
- Create: `tasks/fixtures/race-condition/counter.py`
- Create: `tasks/fixtures/god-object/app.py`
- Create: `tasks/fixtures/god-object/test_app.py`
- Create: `tasks/fixtures/sync-to-async/fetcher.py`
- Create: `tasks/fixtures/sync-to-async/test_fetcher.py`

- [ ] **Step 1: Create memory leak fixture**

```python
# tasks/fixtures/memory-leak/server.py
"""A simple server with an unbounded cache — memory leak by design."""
import hashlib
import time


class RequestCache:
    """Caches processed results. BUG: never evicts entries."""

    def __init__(self):
        self._cache = {}
        self._access_times = {}

    def get(self, key: str):
        if key in self._cache:
            self._access_times[key] = time.time()
            return self._cache[key]
        return None

    def put(self, key: str, value):
        self._cache[key] = value
        self._access_times[key] = time.time()
        # BUG: no eviction, no max size, no TTL


class Server:
    def __init__(self):
        self.cache = RequestCache()
        self.request_count = 0

    def handle_request(self, data: str) -> str:
        """Process a request, caching the result."""
        self.request_count += 1
        key = hashlib.sha256(data.encode()).hexdigest()

        cached = self.cache.get(key)
        if cached is not None:
            return cached

        # Simulate expensive computation
        result = self._process(data)
        self.cache.put(key, result)
        return result

    def _process(self, data: str) -> str:
        """Simulate CPU-intensive processing."""
        return f"processed:{data}:{hashlib.md5(data.encode()).hexdigest()}"

    def get_cache_size(self) -> int:
        return len(self.cache._cache)
```

- [ ] **Step 2: Create race condition fixture**

```python
# tasks/fixtures/race-condition/counter.py
"""A counter that claims to be thread-safe but isn't."""
import threading
import time


class ThreadSafeCounter:
    """BUG: read-modify-write is not atomic despite the name."""

    def __init__(self):
        self._value = 0

    def increment(self):
        """Increment the counter by 1. BUG: not actually thread-safe."""
        current = self._value
        # Simulate some work between read and write
        time.sleep(0.0001)
        self._value = current + 1

    def decrement(self):
        current = self._value
        time.sleep(0.0001)
        self._value = current - 1

    @property
    def value(self) -> int:
        return self._value


def stress_test(counter: ThreadSafeCounter, n_threads: int = 10, n_ops: int = 100):
    """Run n_threads threads each incrementing n_ops times."""
    threads = []
    for _ in range(n_threads):
        t = threading.Thread(target=lambda: [counter.increment() for _ in range(n_ops)])
        threads.append(t)
        t.start()
    for t in threads:
        t.join()
    return counter.value  # Should be n_threads * n_ops but won't be
```

- [ ] **Step 3: Create god object fixture**

Create `tasks/fixtures/god-object/app.py` — a ~300 line monolithic class combining user management, email sending, logging, and configuration. And `tasks/fixtures/god-object/test_app.py` with basic integration tests.

(Implementation: a realistic AppManager class with mixed responsibilities to test the AI's refactoring ability.)

- [ ] **Step 4: Create sync-to-async fixture**

Create `tasks/fixtures/sync-to-async/fetcher.py` with synchronous HTTP fetching using requests, and `tasks/fixtures/sync-to-async/test_fetcher.py` with sync tests.

- [ ] **Step 5: Commit**

```bash
git add tasks/fixtures/
git commit -m "feat: task fixtures for debugging and refactoring benchmarks"
```

---

### Task 15: Integration Wiring & End-to-End Smoke Test

**Files:**
- Modify: `cccb/app.py` — wire screens together with data flow
- Modify: `cccb/screens/config_select.py` — pass data to app
- Create: `tests/test_integration.py`

- [ ] **Step 1: Write integration smoke test**

```python
# tests/test_integration.py
"""End-to-end integration test with mocked Claude SDK."""
import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock
from cccb.models import TaskDefinition, ConfigProfile
from cccb.runner import BenchmarkRunner
from cccb.executor import ExecutionResult


@pytest.mark.asyncio
async def test_full_benchmark_pipeline(tmp_repo, sample_config_dir, sample_task_yaml):
    """Test the full pipeline: config -> task -> run -> score."""
    config = ConfigProfile.from_dir(sample_config_dir)
    task = TaskDefinition.from_yaml(sample_task_yaml)

    runner = BenchmarkRunner(
        repo_root=tmp_repo,
        configs=[config],
        tasks=[task],
    )

    mock_result = ExecutionResult(
        duration_ms=3000, duration_api_ms=2500,
        total_cost_usd=0.03, num_turns=2,
        session_id="integ-test", is_error=False,
    )

    with patch("cccb.runner.execute_task", new_callable=AsyncMock, return_value=mock_result), \
         patch("cccb.runner.evaluate_run", new_callable=AsyncMock, return_value=({"quality": 7.0}, "ok")):

        events = []
        async for event in runner.run(on_event=lambda e: events.append(e)):
            events.append(event)

        assert len(runner.results) == 1
        report = runner.build_report(summary="Test summary")
        assert report.winner is not None
        assert report.winner.name == "baseline"
```

- [ ] **Step 2: Run integration test**

Run: `pytest tests/test_integration.py -v`
Expected: PASS

- [ ] **Step 3: Wire app.py data flow between screens**

Update `cccb/app.py` to store `selected_configs`, `selected_tasks`, `runner`, and `report` on the app instance, so screens can access them.

- [ ] **Step 4: Commit**

```bash
git add tests/test_integration.py cccb/app.py cccb/screens/config_select.py
git commit -m "feat: integration wiring and end-to-end smoke test"
```

---

### Task 16: Final Verification

- [ ] **Step 1: Run full test suite**

Run: `pytest tests/ -v --tb=short`
Expected: All PASS

- [ ] **Step 2: Run type checking (optional)**

Run: `python -m py_compile cccb/models.py cccb/isolation.py cccb/checker.py cccb/scorer.py cccb/executor.py cccb/judge.py cccb/runner.py cccb/app.py`
Expected: No errors

- [ ] **Step 3: Verify TUI launches**

Run: `python -m cccb`
Expected: Textual app starts, shows Config Select screen

- [ ] **Step 4: Commit final state**

```bash
git add -A
git commit -m "feat: CCCB v0.1.0 — complete TUI benchmark tool"
```
