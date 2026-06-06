from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
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


@dataclass(slots=True)
class GitRunContext:
    enabled: bool
    initial_state: dict[str, object] | None
    branch_created: bool = False
    working_branch: str | None = None
    commits: list[str] | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "initial_state": self.initial_state,
            "branch_created": self.branch_created,
            "working_branch": self.working_branch,
            "commits": list(self.commits or []),
        }


@dataclass(slots=True)
class GitOperationError(Exception):
    code: str
    message: str
    hint: str | None = None

    def __str__(self) -> str:
        return self.message


def is_git_available() -> bool:
    return shutil.which("git") is not None


def _run_git(workspace_path: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(workspace_path), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def _require_git_success(workspace_path: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    completed = _run_git(workspace_path, args)
    if completed.returncode == 0:
        return completed

    hint = completed.stderr.strip() or completed.stdout.strip() or None
    raise GitOperationError(
        code="git_command_failed",
        message=f"Git command failed: git {' '.join(args)}",
        hint=hint,
    )


def _slugify_branch_component(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "optimization"


def generate_branch_name(prefix: str, label: str) -> str:
    normalized_prefix = prefix if prefix.endswith("/") else f"{prefix}/"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{normalized_prefix}{_slugify_branch_component(label)}-{timestamp}"


def create_branch(workspace_path: Path, branch_name: str) -> str:
    _require_git_success(workspace_path, ["switch", "-c", branch_name])
    return branch_name


def commit_files(workspace_path: Path, files: list[str], message: str) -> str:
    if not files:
        raise GitOperationError(
            code="git_commit_missing_files",
            message="Cannot create a Git commit without any tracked file changes.",
        )

    _require_git_success(workspace_path, ["add", "--", *files])
    commit_result = _require_git_success(workspace_path, ["commit", "-m", message])
    head = _require_git_success(workspace_path, ["rev-parse", "HEAD"]).stdout.strip()
    if not head:
        hint = commit_result.stderr.strip() or commit_result.stdout.strip() or None
        raise GitOperationError(
            code="git_commit_missing_head",
            message="Git commit completed but HEAD could not be resolved.",
            hint=hint,
        )
    return head


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

    repo_check = _run_git(workspace_path, ["rev-parse", "--is-inside-work-tree"])
    if repo_check.returncode != 0 or repo_check.stdout.strip() != "true":
        return GitRepoState(
            git_available=True,
            is_repo=False,
            branch=None,
            head=None,
            worktree_clean=None,
            status_porcelain=None,
        )

    branch_result = _run_git(workspace_path, ["branch", "--show-current"])
    head_result = _run_git(workspace_path, ["rev-parse", "HEAD"])
    status_result = _run_git(workspace_path, ["status", "--porcelain"])

    status_porcelain = status_result.stdout.strip()
    return GitRepoState(
        git_available=True,
        is_repo=True,
        branch=branch_result.stdout.strip() or None,
        head=head_result.stdout.strip() if head_result.returncode == 0 else None,
        worktree_clean=(status_porcelain == ""),
        status_porcelain=status_porcelain,
    )
