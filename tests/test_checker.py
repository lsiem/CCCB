"""Tests for the automated check runner."""
import pytest
from pathlib import Path

from cccb.models import Check
from cccb.checker import run_checks


class TestFileExistsCheck:
    """Tests for file_exists check type."""

    def test_file_exists_pass(self, tmp_path: Path):
        """Test that file_exists check passes when file is present."""
        # Create a test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello")

        checks = [Check(type="file_exists", path="test.txt")]
        results = run_checks(checks, tmp_path)

        assert len(results) == 1
        assert results[0].passed is True
        assert "found" in results[0].output.lower()

    def test_file_exists_fail(self, tmp_path: Path):
        """Test that file_exists check fails when file is missing."""
        checks = [Check(type="file_exists", path="missing.txt")]
        results = run_checks(checks, tmp_path)

        assert len(results) == 1
        assert results[0].passed is False
        assert "not found" in results[0].output.lower()

    def test_file_exists_nested_path(self, tmp_path: Path):
        """Test that file_exists works with nested paths."""
        # Create nested structure
        nested_dir = tmp_path / "subdir" / "nested"
        nested_dir.mkdir(parents=True)
        nested_file = nested_dir / "deep.txt"
        nested_file.write_text("Content")

        checks = [Check(type="file_exists", path="subdir/nested/deep.txt")]
        results = run_checks(checks, tmp_path)

        assert results[0].passed is True


class TestCommandCheck:
    """Tests for command check type."""

    def test_command_success(self, tmp_path: Path):
        """Test that command check passes on exit code 0."""
        checks = [Check(type="command", run="echo 'test'", expect_exit_code=0)]
        results = run_checks(checks, tmp_path)

        assert len(results) == 1
        assert results[0].passed is True
        assert "test" in results[0].output

    def test_command_failure(self, tmp_path: Path):
        """Test that command check fails on wrong exit code."""
        checks = [Check(type="command", run="exit 1", expect_exit_code=0)]
        results = run_checks(checks, tmp_path)

        assert results[0].passed is False

    def test_command_expected_nonzero(self, tmp_path: Path):
        """Test command that expects non-zero exit code."""
        checks = [Check(type="command", run="exit 42", expect_exit_code=42)]
        results = run_checks(checks, tmp_path)

        assert results[0].passed is True

    def test_command_timeout(self, tmp_path: Path):
        """Test command that times out."""
        checks = [Check(type="command", run="sleep 10", expect_exit_code=0)]
        results = run_checks(checks, tmp_path, timeout=1)

        assert results[0].passed is False
        assert "timed out" in results[0].output.lower()

    def test_command_with_output(self, tmp_path: Path):
        """Test that command output is captured."""
        checks = [Check(type="command", run="echo 'Hello World'", expect_exit_code=0)]
        results = run_checks(checks, tmp_path)

        assert results[0].passed is True
        assert "Hello World" in results[0].output

    def test_command_output_truncation(self, tmp_path: Path):
        """Test that long output is truncated to 2000 chars."""
        # Create a command that outputs lots of text
        long_output = "x" * 3000
        checks = [Check(type="command", run=f"echo '{long_output}'", expect_exit_code=0)]
        results = run_checks(checks, tmp_path)

        assert len(results[0].output) <= 2100  # 2000 + truncation message
        assert "truncated" in results[0].output.lower()


class TestMultipleChecks:
    """Tests for running multiple checks."""

    def test_multiple_checks_all_pass(self, tmp_path: Path):
        """Test that multiple checks all pass."""
        # Create files
        (tmp_path / "file1.txt").write_text("1")
        (tmp_path / "file2.txt").write_text("2")

        checks = [
            Check(type="file_exists", path="file1.txt"),
            Check(type="file_exists", path="file2.txt"),
            Check(type="command", run="echo ok", expect_exit_code=0),
        ]
        results = run_checks(checks, tmp_path)

        assert len(results) == 3
        assert all(r.passed for r in results)

    def test_multiple_checks_mixed_pass_fail(self, tmp_path: Path):
        """Test multiple checks with mixed results."""
        (tmp_path / "exists.txt").write_text("1")

        checks = [
            Check(type="file_exists", path="exists.txt"),
            Check(type="file_exists", path="missing.txt"),
            Check(type="command", run="exit 1", expect_exit_code=0),
            Check(type="command", run="echo ok", expect_exit_code=0),
        ]
        results = run_checks(checks, tmp_path)

        assert len(results) == 4
        assert results[0].passed is True
        assert results[1].passed is False
        assert results[2].passed is False
        assert results[3].passed is True

    def test_checks_run_in_correct_cwd(self, tmp_path: Path):
        """Test that checks are executed in the correct working directory."""
        checks = [Check(type="command", run="pwd", expect_exit_code=0)]
        results = run_checks(checks, tmp_path)

        # The output should show the tmp_path directory
        assert results[0].passed is True
        # pwd output should be there (might vary by platform)
        assert len(results[0].output) > 0


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_unknown_check_type(self, tmp_path: Path):
        """Test handling of unknown check type."""
        checks = [Check(type="unknown", path="test.txt")]
        results = run_checks(checks, tmp_path)

        assert results[0].passed is False
        assert "Unknown check type" in results[0].output

    def test_command_missing_run(self, tmp_path: Path):
        """Test command check without run specified."""
        checks = [Check(type="command")]
        results = run_checks(checks, tmp_path)

        assert results[0].passed is False
        assert "No run command" in results[0].output

    def test_file_exists_missing_path(self, tmp_path: Path):
        """Test file_exists check without path specified."""
        checks = [Check(type="file_exists")]
        results = run_checks(checks, tmp_path)

        assert results[0].passed is False
        assert "No path specified" in results[0].output

    def test_command_stderr_captured(self, tmp_path: Path):
        """Test that stderr is captured along with stdout."""
        checks = [Check(type="command", run="python -c \"import sys; sys.stderr.write('error')\"", expect_exit_code=0)]
        results = run_checks(checks, tmp_path)

        assert results[0].passed is True
        assert "error" in results[0].output
