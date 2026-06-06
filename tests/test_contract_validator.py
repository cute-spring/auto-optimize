from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from auto_optimize.contract.loader import load_contract
from auto_optimize.contract.validator import validate_contract, write_validation_report

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_DIR = ROOT / "examples" / "faq_retrieval"
SOURCE_WORKSPACE = EXAMPLE_DIR / "workspace"
SOURCE_CONTRACT = EXAMPLE_DIR / "optimization.contract.yaml"


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
    result = validate_contract(contract)
    return contract, result


def test_validate_example_contract_passes_and_writes_report(tmp_path: Path) -> None:
    contract, result = _validate(tmp_path)

    assert result.valid
    assert result.baseline_metrics is not None

    report_path = write_validation_report(contract, result)
    assert report_path.exists()
    assert "Status: PASSED" in report_path.read_text(encoding="utf-8")


def test_missing_workspace_fails(tmp_path: Path) -> None:
    contract, result = _validate(
        tmp_path,
        mutate=lambda data, workspace: data["workspace"].update({"path": "does-not-exist"}),
    )

    assert not result.valid
    assert any(issue.code == "missing_workspace" for issue in result.issues)


def test_missing_primary_metric_fails(tmp_path: Path) -> None:
    _, result = _validate(
        tmp_path,
        mutate=lambda data, workspace: data["metrics"]["primary"].update({"name": "precision_at_1"}),
    )

    assert not result.valid
    assert any(issue.code == "missing_primary_metric" for issue in result.issues)


def test_editable_protected_conflict_fails(tmp_path: Path) -> None:
    _, result = _validate(
        tmp_path,
        mutate=lambda data, workspace: data["protected_scope"].append("configs/retrieval.yaml"),
    )

    assert not result.valid
    assert any(issue.code == "scope_conflict" for issue in result.issues)


def test_invalid_mapping_file_fails(tmp_path: Path) -> None:
    def mutate(data, workspace):
        data["search_space"]["top_k"]["mapping"]["file"] = "configs/missing.yaml"

    _, result = _validate(tmp_path, mutate=mutate)

    assert not result.valid
    assert any(issue.code == "missing_mapping_file" for issue in result.issues)


def test_invalid_yaml_path_fails(tmp_path: Path) -> None:
    def mutate(data, workspace):
        data["search_space"]["top_k"]["mapping"]["path"] = "retrieval.missing"

    _, result = _validate(tmp_path, mutate=mutate)

    assert not result.valid
    assert any(issue.code == "missing_mapping_path" for issue in result.issues)


def test_empty_search_space_fails(tmp_path: Path) -> None:
    _, result = _validate(tmp_path, mutate=lambda data, workspace: data.update({"search_space": {}}))

    assert not result.valid
    assert any(issue.code == "empty_search_space" for issue in result.issues)


def test_eval_scope_violation_fails(tmp_path: Path) -> None:
    _, result = _validate(
        tmp_path,
        mutate=lambda data, workspace: data["editable_scope"].append("eval/run_eval.py"),
    )

    assert not result.valid
    assert any(issue.code == "eval_integrity_violation" for issue in result.issues)


def test_commit_requires_version_control(tmp_path: Path) -> None:
    def mutate(data, workspace):
        data["version_control"]["enabled"] = False
        data["version_control"]["commit_accepted_changes"] = True

    _, result = _validate(tmp_path, mutate=mutate)

    assert not result.valid
    assert any(issue.code == "commit_requires_version_control" for issue in result.issues)
