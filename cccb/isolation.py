"""Git worktree-based isolation for benchmark runs."""
from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from cccb.models import SetupFile

logger = logging.getLogger(__name__)


class WorktreeManager:
    """Manages git worktrees for isolated benchmark runs."""

    def __init__(self, repo_root: Path) -> None:
        """Initialize WorktreeManager.
        
        Args:
            repo_root: Root path of the git repository.
        """
        self.repo_root = Path(repo_root)
        self.bench_dir = self.repo_root / ".cccb-bench"

    def create_worktree(self, config_name: str, task_slug: str) -> Path:
        """Create a new git worktree for a benchmark run.
        
        Args:
            config_name: Name of the configuration.
            task_slug: Slug identifier for the task.
            
        Returns:
            Path to the created worktree.
            
        Raises:
            RuntimeError: If unable to create worktree after max attempts.
        """
        # Ensure bench directory exists
        self.bench_dir.mkdir(parents=True, exist_ok=True)
        
        config_dir = self.bench_dir / config_name
        config_dir.mkdir(parents=True, exist_ok=True)
        
        base_wt_path = config_dir / task_slug
        branch_name = f"bench/{config_name}/{task_slug}"
        
        # Try to create worktree, with suffix for collisions
        for attempt in range(1, 6):
            if attempt == 1:
                wt_path = base_wt_path
                current_branch = branch_name
            else:
                wt_path = config_dir / f"{task_slug}-{attempt}"
                current_branch = f"{branch_name}-{attempt}"
            
            if wt_path.exists():
                logger.debug(f"Worktree path exists, trying suffix: {wt_path}")
                continue
            
            try:
                subprocess.run(
                    ["git", "worktree", "add", str(wt_path), "-b", current_branch, "HEAD"],
                    cwd=self.repo_root,
                    check=True,
                    capture_output=True,
                    text=True
                )
                logger.info(f"Created worktree at {wt_path} with branch {current_branch}")
                return wt_path
            except subprocess.CalledProcessError as e:
                logger.debug(f"Attempt {attempt} failed: {e.stderr}")
                continue
        
        raise RuntimeError(
            f"Failed to create worktree for {config_name}/{task_slug} after 5 attempts"
        )

    def copy_config_files(self, wt_path: Path, config_dir: Path) -> None:
        """Copy configuration files to worktree.
        
        Args:
            wt_path: Path to the worktree.
            config_dir: Path to the configuration directory.
        """
        wt_path = Path(wt_path)
        config_dir = Path(config_dir)
        
        # Copy CLAUDE.md
        claude_md = config_dir / "CLAUDE.md"
        if claude_md.exists():
            shutil.copy2(claude_md, wt_path / "CLAUDE.md")
            logger.debug(f"Copied CLAUDE.md to {wt_path}")
        
        # Copy .claude directory
        claude_dir = config_dir / ".claude"
        if claude_dir.exists():
            target_claude_dir = wt_path / ".claude"
            if target_claude_dir.exists():
                shutil.rmtree(target_claude_dir)
            shutil.copytree(claude_dir, target_claude_dir)
            logger.debug(f"Copied .claude directory to {wt_path}")

    def copy_setup_files(self, wt_path: Path, setup_files: list[SetupFile]) -> None:
        """Copy setup files to worktree.
        
        Args:
            wt_path: Path to the worktree.
            setup_files: List of SetupFile objects to copy.
            
        Raises:
            ValueError: If target path traverses outside worktree or would overwrite CLAUDE.md.
        """
        wt_path = Path(wt_path).resolve()
        
        for setup_file in setup_files:
            source_path = Path(setup_file.source)
            target_path = (wt_path / setup_file.target).resolve()
            
            # Security: prevent path traversal
            try:
                target_path.relative_to(wt_path)
            except ValueError:
                raise ValueError(
                    f"Setup file target '{setup_file.target}' traverses outside worktree"
                )
            
            # Security: prevent overwriting CLAUDE.md
            if target_path.name == "CLAUDE.md" or target_path == wt_path / "CLAUDE.md":
                logger.warning(f"Skipping setup file '{setup_file.target}' (would overwrite CLAUDE.md)")
                continue
            
            # Copy the file
            if not source_path.exists():
                logger.warning(f"Setup file source not found: {source_path}")
                continue
            
            # Create parent directories
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            if source_path.is_dir():
                if target_path.exists():
                    shutil.rmtree(target_path)
                shutil.copytree(source_path, target_path)
            else:
                shutil.copy2(source_path, target_path)
            
            logger.debug(f"Copied setup file {setup_file.source} to {setup_file.target}")

    def commit_setup(self, wt_path: Path, config_name: str, task_slug: str) -> str:
        """Commit setup state in worktree.
        
        Args:
            wt_path: Path to the worktree.
            config_name: Name of the configuration.
            task_slug: Slug identifier for the task.
            
        Returns:
            40-character commit hash.
        """
        wt_path = Path(wt_path)
        
        # Stage all files
        subprocess.run(
            ["git", "add", "-A"],
            cwd=wt_path,
            check=True,
            capture_output=True,
            text=True
        )
        
        # Commit
        commit_msg = f"Setup: {config_name} x {task_slug}"
        result = subprocess.run(
            ["git", "commit", "-m", commit_msg],
            cwd=wt_path,
            check=True,
            capture_output=True,
            text=True
        )
        
        # Get commit hash
        commit_hash = self._get_head_hash(wt_path)
        logger.info(f"Committed setup with hash {commit_hash}")
        return commit_hash

    def commit_result(
        self,
        wt_path: Path,
        config_name: str,
        task_slug: str,
        score: float,
        timeout: bool = False,
        error: bool = False
    ) -> str:
        """Commit result state in worktree.
        
        Args:
            wt_path: Path to the worktree.
            config_name: Name of the configuration.
            task_slug: Slug identifier for the task.
            score: Numeric score for the run.
            timeout: Whether the run timed out.
            error: Whether the run errored.
            
        Returns:
            40-character commit hash.
        """
        wt_path = Path(wt_path)
        
        # Build commit message with markers
        markers = []
        if timeout:
            markers.append("[TIMEOUT]")
        if error:
            markers.append("[ERROR]")
        
        marker_str = " ".join(markers)
        if marker_str:
            commit_msg = f"Result: {config_name} x {task_slug} - {score:.2f} {marker_str}"
        else:
            commit_msg = f"Result: {config_name} x {task_slug} - {score:.2f}"
        
        # Stage all files
        subprocess.run(
            ["git", "add", "-A"],
            cwd=wt_path,
            check=True,
            capture_output=True,
            text=True
        )
        
        # Commit
        subprocess.run(
            ["git", "commit", "-m", commit_msg],
            cwd=wt_path,
            check=True,
            capture_output=True,
            text=True
        )
        
        # Get commit hash
        commit_hash = self._get_head_hash(wt_path)
        logger.info(f"Committed result with hash {commit_hash}")
        return commit_hash

    def get_diff(self, wt_path: Path, setup_hash: str, result_hash: str, max_bytes: int = 50000) -> str:
        """Get diff between setup and result commits.
        
        Args:
            wt_path: Path to the worktree.
            setup_hash: Commit hash of setup.
            result_hash: Commit hash of result.
            max_bytes: Maximum bytes to return before truncating.
            
        Returns:
            Diff output, truncated if necessary.
        """
        wt_path = Path(wt_path)
        
        result = subprocess.run(
            ["git", "diff", f"{setup_hash}..{result_hash}"],
            cwd=wt_path,
            check=True,
            capture_output=True,
            text=True
        )
        
        diff_output = result.stdout
        if len(diff_output) > max_bytes:
            diff_output = diff_output[:max_bytes] + f"\n\n... (truncated, was {len(result.stdout)} bytes)"
        
        return diff_output

    def cleanup_all(self) -> None:
        """Remove all worktrees and clean up bench directory."""
        if not self.bench_dir.exists():
            logger.debug("Bench directory does not exist")
            return
        
        # Remove all worktrees
        worktrees_to_remove = []
        result = subprocess.run(
            ["git", "worktree", "list"],
            cwd=self.repo_root,
            check=True,
            capture_output=True,
            text=True
        )
        
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue
            parts = line.split()
            wt_path = parts[0]
            if ".cccb-bench" in wt_path:
                worktrees_to_remove.append(wt_path)
        
        # Remove each worktree
        for wt_path in worktrees_to_remove:
            try:
                subprocess.run(
                    ["git", "worktree", "remove", wt_path],
                    cwd=self.repo_root,
                    check=True,
                    capture_output=True,
                    text=True
                )
                logger.info(f"Removed worktree {wt_path}")
            except subprocess.CalledProcessError as e:
                logger.warning(f"Failed to remove worktree {wt_path}: {e.stderr}")
        
        # Prune worktree refs
        try:
            subprocess.run(
                ["git", "worktree", "prune"],
                cwd=self.repo_root,
                check=True,
                capture_output=True,
                text=True
            )
            logger.info("Pruned worktree refs")
        except subprocess.CalledProcessError as e:
            logger.warning(f"Failed to prune worktree refs: {e.stderr}")
        
        # Delete bench/* branches
        try:
            result = subprocess.run(
                ["git", "branch", "-l", "bench/*"],
                cwd=self.repo_root,
                check=True,
                capture_output=True,
                text=True
            )
            
            for branch in result.stdout.strip().split('\n'):
                if branch:
                    branch = branch.strip()
                    try:
                        subprocess.run(
                            ["git", "branch", "-D", branch],
                            cwd=self.repo_root,
                            check=True,
                            capture_output=True,
                            text=True
                        )
                        logger.info(f"Deleted branch {branch}")
                    except subprocess.CalledProcessError as e:
                        logger.warning(f"Failed to delete branch {branch}: {e.stderr}")
        except subprocess.CalledProcessError as e:
            logger.warning(f"Failed to list branches: {e.stderr}")
        
        # Remove bench directory
        if self.bench_dir.exists():
            shutil.rmtree(self.bench_dir)
            logger.info(f"Removed bench directory {self.bench_dir}")

    def _get_head_hash(self, wt_path: Path) -> str:
        """Get the current HEAD commit hash.
        
        Args:
            wt_path: Path to the worktree.
            
        Returns:
            40-character commit hash.
        """
        wt_path = Path(wt_path)
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=wt_path,
            check=True,
            capture_output=True,
            text=True
        )
        return result.stdout.strip()
