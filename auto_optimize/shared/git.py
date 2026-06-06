from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class GitRepoState:
    git_available: bool
    is_repo: bool
    branch: str | None
    head: str | None
    worktree_clean: bool | None
    status_porcelain: str | None

    def as_dict(self) -> dict[str, object]:
        return {
            "git_available": self.git_available,
            "is_repo": self.is_repo,
            "branch": self.branch,
            "head": self.head,
            "worktree_clean": self.worktree_clean,
            "status_porcelain": self.status_porcelain,
        }


def is_git_available() -> bool:
    return shutil.which("git") is not None


def inspect_git_repo(workspace_path: Path) -> GitRepoState:
    if not is_git_available():
        return GitRepoState(
            git_available=False,
            is_repo=False,
            branch=None,
            head=None,
            worktree_clean=None,
            status_porcelain=None,
        )

    repo_check = subprocess.run(
        ["git", "-C", str(workspace_path), "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
        check=False,
    )
    if repo_check.returncode != 0 or repo_check.stdout.strip() != "true":
        return GitRepoState(
            git_available=True,
            is_repo=False,
            branch=None,
            head=None,
            worktree_clean=None,
            status_porcelain=None,
        )

    branch_result = subprocess.run(
        ["git", "-C", str(workspace_path), "branch", "--show-current"],
        capture_output=True,
        text=True,
        check=False,
    )
    head_result = subprocess.run(
        ["git", "-C", str(workspace_path), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    status_result = subprocess.run(
        ["git", "-C", str(workspace_path), "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=False,
    )

    status_porcelain = status_result.stdout.strip()
    return GitRepoState(
        git_available=True,
        is_repo=True,
        branch=branch_result.stdout.strip() or None,
        head=head_result.stdout.strip() if head_result.returncode == 0 else None,
        worktree_clean=(status_porcelain == ""),
        status_porcelain=status_porcelain,
    )
