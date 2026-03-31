import os

import pytest
from pathlib import Path


def _git_env(home: Path) -> dict[str, str]:
    """Isolate git from the developer machine (HOME, no system config)."""
    return {
        **os.environ,
        "HOME": str(home),
        "GIT_CONFIG_NOSYSTEM": "1",
    }


@pytest.fixture
def tmp_repo(tmp_path: Path) -> Path:
    """Create a minimal git repo for testing."""
    import subprocess

    home = tmp_path / ".git_test_home"
    home.mkdir()
    (home / ".gitconfig").write_text(
        "[user]\n\temail = test@test.com\n\tname = Test User\n",
        encoding="utf-8",
    )
    env = _git_env(home)

    init = subprocess.run(
        ["git", "init", "-b", "main", str(tmp_path)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if init.returncode != 0:
        pytest.fail(f"git init failed: {init.stderr or init.stdout}")

    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        env=env,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        env=env,
    )
    readme = tmp_path / "README.md"
    readme.write_text("# Test Repo\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", "-A"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        env=env,
    )
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        env=env,
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
    (config_dir / "CLAUDE.md").write_text(
        "# Baseline Config\nDu bist ein hilfreicher Assistent.\n",
        encoding="utf-8",
    )
    return config_dir
