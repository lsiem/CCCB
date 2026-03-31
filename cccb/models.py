"""CCCB data models."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Any

import yaml


@dataclass
class SetupFile:
    """A setup file for a task."""
    source: str
    target: str


@dataclass
class Check:
    """A check to validate task completion."""
    type: str
    run: Optional[str] = None
    path: Optional[str] = None
    expect_exit_code: int = 0


@dataclass
class JudgeCriteria:
    """Judging criteria for a task."""
    criteria: list[str] = field(default_factory=list)
    scale: str = "1-10"


@dataclass
class ClaudeSettings:
    """Claude configuration for running a task."""
    max_turns: int
    allowed_tools: Optional[list[str]] = None
    timeout: int = 300


@dataclass
class TaskDefinition:
    """A task to benchmark."""
    name: str
    category: str
    description: str
    prompt: str
    setup_files: list[SetupFile] = field(default_factory=list)
    checks: list[Check] = field(default_factory=list)
    judge: Optional[JudgeCriteria] = None
    claude_settings: Optional[ClaudeSettings] = None

    @classmethod
    def from_yaml(cls, path: Path) -> TaskDefinition:
        """Load a task definition from YAML file."""
        if not path.exists():
            raise FileNotFoundError(f"Task file not found: {path}")

        with open(path) as f:
            data = yaml.safe_load(f)

        # Parse setup_files
        setup_files = []
        if "setup_files" in data and data["setup_files"]:
            for sf in data["setup_files"]:
                setup_files.append(SetupFile(source=sf["source"], target=sf["target"]))

        # Parse checks
        checks = []
        if "checks" in data and data["checks"]:
            for check in data["checks"]:
                checks.append(Check(
                    type=check["type"],
                    run=check.get("run"),
                    path=check.get("path"),
                    expect_exit_code=check.get("expect_exit_code", 0)
                ))

        # Parse judge criteria
        judge = None
        if "judge" in data and data["judge"]:
            judge_data = data["judge"]
            judge = JudgeCriteria(
                criteria=judge_data.get("criteria", []),
                scale=judge_data.get("scale", "1-10")
            )

        # Parse claude_settings
        claude_settings = None
        if "claude_settings" in data and data["claude_settings"]:
            cs = data["claude_settings"]
            claude_settings = ClaudeSettings(
                max_turns=cs.get("max_turns", 5),
                allowed_tools=cs.get("allowed_tools"),
                timeout=cs.get("timeout", 300)
            )

        return cls(
            name=data["name"],
            category=data["category"],
            description=data["description"],
            prompt=data["prompt"],
            setup_files=setup_files,
            checks=checks,
            judge=judge,
            claude_settings=claude_settings
        )


@dataclass
class ConfigProfile:
    """A Claude Code configuration profile."""
    name: str
    path: Path
    description: str

    @classmethod
    def from_dir(cls, path: Path) -> ConfigProfile:
        """Load a config profile from directory."""
        claude_md = path / "CLAUDE.md"
        if not claude_md.exists():
            raise ValueError(f"CLAUDE.md not found in {path}")

        # Read CLAUDE.md for description (first line after #)
        with open(claude_md) as f:
            content = f.read().strip()

        if not content:
            raise ValueError(f"CLAUDE.md is empty in {path}")

        description = content

        # Check for config.yaml overrides
        config_yaml = path / "config.yaml"
        name = path.name

        if config_yaml.exists():
            with open(config_yaml) as f:
                config_data = yaml.safe_load(f)

            if config_data:
                if "name" in config_data:
                    name = config_data["name"]
                if "description" in config_data:
                    description = config_data["description"]

        return cls(
            name=name,
            path=path,
            description=description
        )


@dataclass
class CheckResult:
    """Result of a single check."""
    check: Check
    passed: bool
    output: str = ""


@dataclass
class RunResult:
    """Result of running a task with a specific config."""
    config: Optional[ConfigProfile]
    task: Optional[TaskDefinition]
    duration_ms: int
    duration_api_ms: int
    total_cost_usd: float
    num_turns: int
    session_id: str
    checks_passed: int
    checks_total: int
    check_details: list[CheckResult]
    judge_scores: dict[str, float]
    judge_average: float
    total_score: float
    timed_out: bool = False
    is_error: bool = False
    worktree_path: str = ""
    branch_name: str = ""
    commit_hash: str = ""


@dataclass
class BenchmarkReport:
    """A benchmark report comparing multiple configs."""
    configs: list[ConfigProfile]
    tasks: list[TaskDefinition]
    results: list[RunResult]
    winner: Optional[ConfigProfile]
    summary: str
