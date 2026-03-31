"""Automated check runner for validating task completion."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .models import Check, CheckResult


def run_checks(checks: list[Check], cwd: Path, timeout: int = 60) -> list[CheckResult]:
    """
    Run a list of checks in a working directory.

    Args:
        checks: List of Check objects to run
        cwd: Working directory where checks are executed
        timeout: Timeout in seconds for each check (default 60)

    Returns:
        List of CheckResult objects with pass/fail status and output
    """
    results = []

    for check in checks:
        if check.type == "file_exists":
            result = _check_file_exists(check, cwd)
        elif check.type == "command":
            result = _check_command(check, cwd, timeout)
        else:
            result = CheckResult(
                check=check,
                passed=False,
                output=f"Unknown check type: {check.type}"
            )

        results.append(result)

    return results


def _check_file_exists(check: Check, cwd: Path) -> CheckResult:
    """Check if a file exists."""
    if not check.path:
        return CheckResult(
            check=check,
            passed=False,
            output="No path specified in check"
        )

    file_path = cwd / check.path
    passed = file_path.exists()
    output = f"File {'found' if passed else 'not found'}: {check.path}"

    return CheckResult(
        check=check,
        passed=passed,
        output=output
    )


def _check_command(check: Check, cwd: Path, timeout: int) -> CheckResult:
    """Run a command and check the exit code."""
    if not check.run:
        return CheckResult(
            check=check,
            passed=False,
            output="No run command specified in check"
        )

    try:
        result = subprocess.run(
            check.run,
            cwd=cwd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )

        exit_code_matches = result.returncode == check.expect_exit_code
        output = result.stdout + result.stderr

        # Truncate output to 2000 characters
        if len(output) > 2000:
            output = output[:2000] + "\n... (truncated)"

        return CheckResult(
            check=check,
            passed=exit_code_matches,
            output=output if output else f"Exit code: {result.returncode} (expected {check.expect_exit_code})"
        )

    except subprocess.TimeoutExpired:
        return CheckResult(
            check=check,
            passed=False,
            output=f"Command timed out after {timeout}s"
        )
    except Exception as e:
        return CheckResult(
            check=check,
            passed=False,
            output=f"Error running command: {str(e)}"
        )
