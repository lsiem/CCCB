"""Tests for git worktree isolation module."""
import pytest
from pathlib import Path
from cccb.isolation import WorktreeManager
from cccb.models import SetupFile


class TestCreateWorktree:
    """Test worktree creation."""

    def test_create_worktree_basic(self, tmp_repo: Path) -> None:
        """Test basic worktree creation."""
        manager = WorktreeManager(tmp_repo)
        wt_path = manager.create_worktree("baseline", "hello-world")
        
        assert wt_path.exists()
        assert ".cccb-bench" in str(wt_path)
        assert "baseline" in str(wt_path)
        assert "hello-world" in str(wt_path)

    def test_create_worktree_creates_branch(self, tmp_repo: Path) -> None:
        """Test that worktree creation creates a branch."""
        manager = WorktreeManager(tmp_repo)
        wt_path = manager.create_worktree("baseline", "hello-world")
        
        # Check that branch exists
        import subprocess
        result = subprocess.run(
            ["git", "branch", "-l", "bench/baseline/hello-world"],
            cwd=tmp_repo,
            capture_output=True,
            text=True,
            check=True
        )
        assert "bench/baseline/hello-world" in result.stdout

    def test_create_worktree_collision_handling(self, tmp_repo: Path) -> None:
        """Test collision handling with suffix."""
        manager = WorktreeManager(tmp_repo)
        
        # Create first worktree
        wt1 = manager.create_worktree("baseline", "task")
        assert wt1.exists()
        
        # Create second worktree with same config/task - should get suffix
        wt2 = manager.create_worktree("baseline", "task")
        assert wt2.exists()
        assert wt1 != wt2
        assert "-2" in str(wt2)


class TestCopyConfigFiles:
    """Test configuration file copying."""

    def test_copy_config_files_copies_claude_md(self, tmp_repo: Path, sample_config_dir: Path) -> None:
        """Test that CLAUDE.md is copied."""
        manager = WorktreeManager(tmp_repo)
        wt_path = manager.create_worktree("baseline", "task")
        
        manager.copy_config_files(wt_path, sample_config_dir)
        
        claude_md = wt_path / "CLAUDE.md"
        assert claude_md.exists()
        assert "Baseline Config" in claude_md.read_text()

    def test_copy_config_files_copies_claude_dir(self, tmp_repo: Path, tmp_path: Path) -> None:
        """Test that .claude directory is copied."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "CLAUDE.md").write_text("# Config\n")
        
        claude_dir = config_dir / ".claude"
        claude_dir.mkdir()
        (claude_dir / "settings.json").write_text('{"key": "value"}')
        
        manager = WorktreeManager(tmp_repo)
        wt_path = manager.create_worktree("baseline", "task")
        
        manager.copy_config_files(wt_path, config_dir)
        
        assert (wt_path / ".claude").exists()
        assert (wt_path / ".claude" / "settings.json").exists()


class TestCopySetupFiles:
    """Test setup file copying."""

    def test_copy_setup_files_basic(self, tmp_repo: Path, tmp_path: Path) -> None:
        """Test basic setup file copying."""
        # Create a source file
        source_file = tmp_path / "source.txt"
        source_file.write_text("test content")
        
        manager = WorktreeManager(tmp_repo)
        wt_path = manager.create_worktree("baseline", "task")
        
        setup_files = [SetupFile(source=str(source_file), target="test.txt")]
        manager.copy_setup_files(wt_path, setup_files)
        
        target_file = wt_path / "test.txt"
        assert target_file.exists()
        assert target_file.read_text() == "test content"

    def test_copy_setup_files_path_traversal_rejection(self, tmp_repo: Path, tmp_path: Path) -> None:
        """Test that path traversal is rejected."""
        source_file = tmp_path / "source.txt"
        source_file.write_text("test")
        
        manager = WorktreeManager(tmp_repo)
        wt_path = manager.create_worktree("baseline", "task")
        
        # Attempt path traversal
        setup_files = [SetupFile(source=str(source_file), target="../../etc/passwd")]
        
        with pytest.raises(ValueError, match="traverses outside worktree"):
            manager.copy_setup_files(wt_path, setup_files)

    def test_copy_setup_files_skips_claude_md(self, tmp_repo: Path, tmp_path: Path) -> None:
        """Test that CLAUDE.md overwrite is skipped."""
        source_file = tmp_path / "source.txt"
        source_file.write_text("bad content")
        
        manager = WorktreeManager(tmp_repo)
        wt_path = manager.create_worktree("baseline", "task")
        
        # Write original CLAUDE.md
        original_content = "original"
        (wt_path / "CLAUDE.md").write_text(original_content)
        
        # Try to overwrite CLAUDE.md
        setup_files = [SetupFile(source=str(source_file), target="CLAUDE.md")]
        manager.copy_setup_files(wt_path, setup_files)
        
        # Should still have original content
        assert (wt_path / "CLAUDE.md").read_text() == original_content


class TestCommitSetup:
    """Test setup commit functionality."""

    def test_commit_setup_returns_hash(self, tmp_repo: Path, sample_config_dir: Path) -> None:
        """Test that commit_setup returns a 40-char hash."""
        manager = WorktreeManager(tmp_repo)
        wt_path = manager.create_worktree("baseline", "task")
        manager.copy_config_files(wt_path, sample_config_dir)
        
        commit_hash = manager.commit_setup(wt_path, "baseline", "task")
        
        assert len(commit_hash) == 40
        assert all(c in "0123456789abcdef" for c in commit_hash)

    def test_commit_setup_creates_commit(self, tmp_repo: Path, sample_config_dir: Path) -> None:
        """Test that commit is created with correct message."""
        manager = WorktreeManager(tmp_repo)
        wt_path = manager.create_worktree("baseline", "task")
        manager.copy_config_files(wt_path, sample_config_dir)
        
        manager.commit_setup(wt_path, "baseline", "task")
        
        # Check commit message
        import subprocess
        result = subprocess.run(
            ["git", "log", "-1", "--format=%B"],
            cwd=wt_path,
            capture_output=True,
            text=True,
            check=True
        )
        assert "Setup: baseline x task" in result.stdout


class TestCommitResult:
    """Test result commit functionality."""

    def test_commit_result_basic(self, tmp_repo: Path, sample_config_dir: Path) -> None:
        """Test basic result commit."""
        manager = WorktreeManager(tmp_repo)
        wt_path = manager.create_worktree("baseline", "task")
        manager.copy_config_files(wt_path, sample_config_dir)
        
        commit_hash = manager.commit_result(wt_path, "baseline", "task", 85.5)
        
        assert len(commit_hash) == 40

    def test_commit_result_timeout_marker(self, tmp_repo: Path, sample_config_dir: Path) -> None:
        """Test that [TIMEOUT] marker is in commit message."""
        manager = WorktreeManager(tmp_repo)
        wt_path = manager.create_worktree("baseline", "task")
        manager.copy_config_files(wt_path, sample_config_dir)
        
        manager.commit_result(wt_path, "baseline", "task", 50.0, timeout=True)
        
        import subprocess
        result = subprocess.run(
            ["git", "log", "-1", "--format=%B"],
            cwd=wt_path,
            capture_output=True,
            text=True,
            check=True
        )
        assert "[TIMEOUT]" in result.stdout

    def test_commit_result_error_marker(self, tmp_repo: Path, sample_config_dir: Path) -> None:
        """Test that [ERROR] marker is in commit message."""
        manager = WorktreeManager(tmp_repo)
        wt_path = manager.create_worktree("baseline", "task")
        manager.copy_config_files(wt_path, sample_config_dir)
        
        manager.commit_result(wt_path, "baseline", "task", 0.0, error=True)
        
        import subprocess
        result = subprocess.run(
            ["git", "log", "-1", "--format=%B"],
            cwd=wt_path,
            capture_output=True,
            text=True,
            check=True
        )
        assert "[ERROR]" in result.stdout

    def test_commit_result_both_markers(self, tmp_repo: Path, sample_config_dir: Path) -> None:
        """Test that both [TIMEOUT] and [ERROR] markers are present."""
        manager = WorktreeManager(tmp_repo)
        wt_path = manager.create_worktree("baseline", "task")
        manager.copy_config_files(wt_path, sample_config_dir)
        
        manager.commit_result(wt_path, "baseline", "task", 0.0, timeout=True, error=True)
        
        import subprocess
        result = subprocess.run(
            ["git", "log", "-1", "--format=%B"],
            cwd=wt_path,
            capture_output=True,
            text=True,
            check=True
        )
        assert "[TIMEOUT]" in result.stdout
        assert "[ERROR]" in result.stdout


class TestGetDiff:
    """Test diff retrieval."""

    def test_get_diff_shows_changes(self, tmp_repo: Path, sample_config_dir: Path) -> None:
        """Test that get_diff shows file changes."""
        manager = WorktreeManager(tmp_repo)
        wt_path = manager.create_worktree("baseline", "task")
        manager.copy_config_files(wt_path, sample_config_dir)
        
        # First commit
        setup_hash = manager.commit_setup(wt_path, "baseline", "task")
        
        # Make a change
        (wt_path / "test.txt").write_text("new content")
        
        # Second commit
        import subprocess
        subprocess.run(
            ["git", "add", "-A"],
            cwd=wt_path,
            check=True,
            capture_output=True
        )
        subprocess.run(
            ["git", "commit", "-m", "test commit"],
            cwd=wt_path,
            check=True,
            capture_output=True
        )
        result_hash = manager._get_head_hash(wt_path)
        
        # Get diff
        diff = manager.get_diff(wt_path, setup_hash, result_hash)
        
        assert "test.txt" in diff

    def test_get_diff_truncates_large(self, tmp_repo: Path, sample_config_dir: Path) -> None:
        """Test that large diffs are truncated."""
        manager = WorktreeManager(tmp_repo)
        wt_path = manager.create_worktree("baseline", "task")
        manager.copy_config_files(wt_path, sample_config_dir)
        
        # First commit
        setup_hash = manager.commit_setup(wt_path, "baseline", "task")
        
        # Make a large change
        large_content = "x" * 100000
        (wt_path / "large.txt").write_text(large_content)
        
        # Second commit
        import subprocess
        subprocess.run(
            ["git", "add", "-A"],
            cwd=wt_path,
            check=True,
            capture_output=True
        )
        subprocess.run(
            ["git", "commit", "-m", "large commit"],
            cwd=wt_path,
            check=True,
            capture_output=True
        )
        result_hash = manager._get_head_hash(wt_path)
        
        # Get diff with small max_bytes
        diff = manager.get_diff(wt_path, setup_hash, result_hash, max_bytes=1000)
        
        assert len(diff) <= 1500  # Some margin for truncation message
        assert "truncated" in diff


class TestCleanupAll:
    """Test cleanup functionality."""

    def test_cleanup_all_removes_worktrees(self, tmp_repo: Path, sample_config_dir: Path) -> None:
        """Test that cleanup_all removes all worktrees."""
        manager = WorktreeManager(tmp_repo)
        wt_path = manager.create_worktree("baseline", "task")
        
        assert wt_path.exists()
        
        manager.cleanup_all()
        
        assert not wt_path.exists()

    def test_cleanup_all_removes_branches(self, tmp_repo: Path, sample_config_dir: Path) -> None:
        """Test that cleanup_all removes bench/* branches."""
        manager = WorktreeManager(tmp_repo)
        manager.create_worktree("baseline", "task")
        
        manager.cleanup_all()
        
        # Check that branch is gone
        import subprocess
        result = subprocess.run(
            ["git", "branch", "-l", "bench/*"],
            cwd=tmp_repo,
            capture_output=True,
            text=True,
            check=True
        )
        assert "bench/baseline/task" not in result.stdout

    def test_cleanup_all_removes_bench_dir(self, tmp_repo: Path, sample_config_dir: Path) -> None:
        """Test that cleanup_all removes .cccb-bench directory."""
        manager = WorktreeManager(tmp_repo)
        manager.create_worktree("baseline", "task")
        
        bench_dir = manager.bench_dir
        assert bench_dir.exists()
        
        manager.cleanup_all()
        
        assert not bench_dir.exists()

    def test_cleanup_all_is_idempotent(self, tmp_repo: Path) -> None:
        """Test that cleanup_all can be called multiple times."""
        manager = WorktreeManager(tmp_repo)
        
        # Call cleanup on empty bench_dir (doesn't exist yet)
        manager.cleanup_all()
        
        # Create a worktree
        manager.create_worktree("baseline", "task")
        
        # Cleanup
        manager.cleanup_all()
        
        # Cleanup again - should not raise
        manager.cleanup_all()
