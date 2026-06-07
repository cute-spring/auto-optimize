from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import yaml

from auto_optimize.contract.loader import load_contract
from auto_optimize.contract.validator import validate_contract

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_DIR = ROOT / "examples" / "faq_retrieval"
SOURCE_WORKSPACE = EXAMPLE_DIR / "workspace"
SOURCE_CONTRACT = EXAMPLE_DIR / "optimization.contract.yaml"


def _run(cmd: list[str], cwd: Path) -> None:
    subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True)


def _init_git_repo(workspace: Path) -> None:
    _run(["git", "init"], cwd=workspace)
    _run(["git", "config", "user.name", "Auto Optimize Test"], cwd=workspace)
    _run(["git", "config", "user.email", "auto-optimize@example.com"], cwd=workspace)
    _run(["git", "add", "."], cwd=workspace)
    _run(["git", "commit", "-m", "initial"], cwd=workspace)


def _materialize_contract(tmp_path: Path, mutate=None) -> Path:
    workspace_copy = tmp_path / "workspace"
    shutil.copytree(SOURCE_WORKSPACE, workspace_copy)

    with SOURCE_CONTRACT.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    data["workspace"]["path"] = "workspace"
    if mutate:
        mutate(data, workspace_copy)

    contract_path = tmp_path / "optimization.contract.yaml"
    contract_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return contract_path


def _validate(tmp_path: Path, mutate=None):
    contract_path = _materialize_contract(tmp_path, mutate=mutate)
    contract = load_contract(contract_path)
    return validate_contract(contract)


def test_git_enabled_passes_with_clean_worktree(tmp_path: Path) -> None:
    def mutate(data, workspace):
        _init_git_repo(workspace)
        data["version_control"]["enabled"] = True
        data["version_control"]["require_clean_worktree"] = True

    result = _validate(tmp_path, mutate=mutate)

    assert result.valid
    assert result.git_state is not None
    assert result.git_state["is_repo"] is True
    assert result.git_state["worktree_clean"] is True


def test_dirty_worktree_blocks_validation_when_required(tmp_path: Path) -> None:
    def mutate(data, workspace):
        _init_git_repo(workspace)
        data["version_control"]["enabled"] = True
        data["version_control"]["require_clean_worktree"] = True
        retrieval_file = workspace / "configs" / "retrieval.yaml"
        retrieval_file.write_text("retrieval:\n  top_k: 11\n  threshold: 0.82\n", encoding="utf-8")

    result = _validate(tmp_path, mutate=mutate)

    assert not result.valid
    assert any(issue.code == "dirty_worktree" for issue in result.issues)


def test_remote_git_operations_are_blocked_in_mvp(tmp_path: Path) -> None:
    def mutate(data, workspace):
        _init_git_repo(workspace)
        data["version_control"]["enabled"] = True
        data["version_control"]["push_remote"] = True
        data["version_control"]["remote_name"] = "origin"

    result = _validate(tmp_path, mutate=mutate)

    assert not result.valid
    assert any(issue.code == "missing_git_remote" for issue in result.issues)


def test_pull_request_requires_push_remote_and_branch(tmp_path: Path) -> None:
    def mutate(data, workspace):
        _init_git_repo(workspace)
        data["version_control"]["enabled"] = True
        data["version_control"]["create_pull_request"] = True
        data["version_control"]["push_remote"] = False
        data["version_control"]["create_branch"] = False

    result = _validate(tmp_path, mutate=mutate)

    assert not result.valid
    assert any(issue.code == "create_pr_requires_push_remote" for issue in result.issues)
    assert any(issue.code == "create_pr_requires_branch" for issue in result.issues)
