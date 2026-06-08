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


def test_env_var_mapping_is_supported_when_scope_allows_it(tmp_path: Path) -> None:
    def mutate(data, workspace):
        data["editable_scope"] = ["env:AUTO_OPTIMIZE_MODE", "configs/retrieval.yaml", "configs/reranker.yaml"]
        data["search_space"] = {
            "mode": {
                "values": ["baseline", "fast"],
                "mapping": {
                    "type": "env_var",
                    "file": "AUTO_OPTIMIZE_MODE",
                },
            }
        }

    _, result = _validate(tmp_path, mutate=mutate)

    assert result.valid


def test_env_var_mapping_outside_editable_scope_fails(tmp_path: Path) -> None:
    def mutate(data, workspace):
        data["search_space"] = {
            "mode": {
                "values": ["baseline", "fast"],
                "mapping": {
                    "type": "env_var",
                    "file": "AUTO_OPTIMIZE_MODE",
                },
            }
        }

    _, result = _validate(tmp_path, mutate=mutate)

    assert not result.valid
    assert any(issue.code == "env_var_not_editable" for issue in result.issues)


def test_cli_arg_mapping_is_supported_when_scope_allows_it(tmp_path: Path) -> None:
    def mutate(data, workspace):
        data["editable_scope"] = ["cmd_arg:--mode", "configs/retrieval.yaml", "configs/reranker.yaml"]
        data["search_space"] = {
            "mode": {
                "values": ["baseline", "fast"],
                "mapping": {
                    "type": "cli_arg",
                    "file": "--mode",
                },
            }
        }

    _, result = _validate(tmp_path, mutate=mutate)

    assert result.valid


def test_cli_arg_mapping_outside_editable_scope_fails(tmp_path: Path) -> None:
    def mutate(data, workspace):
        data["search_space"] = {
            "mode": {
                "values": ["baseline", "fast"],
                "mapping": {
                    "type": "cli_arg",
                    "file": "--mode",
                },
            }
        }

    _, result = _validate(tmp_path, mutate=mutate)

    assert not result.valid
    assert any(issue.code == "cli_arg_not_editable" for issue in result.issues)


def test_cli_arg_commit_accepted_changes_is_not_supported(tmp_path: Path) -> None:
    def mutate(data, workspace):
        data["editable_scope"] = ["cmd_arg:--mode", "configs/retrieval.yaml", "configs/reranker.yaml"]
        data["search_space"] = {
            "mode": {
                "values": ["baseline", "fast"],
                "mapping": {
                    "type": "cli_arg",
                    "file": "--mode",
                },
            }
        }
        data["version_control"]["enabled"] = True
        data["version_control"]["require_clean_worktree"] = False
        data["version_control"]["create_branch"] = False
        data["version_control"]["commit_accepted_changes"] = True

    _, result = _validate(tmp_path, mutate=mutate)

    assert not result.valid
    assert any(issue.code == "cli_arg_commit_not_supported" for issue in result.issues)


def test_csv_summary_output_format_requires_output_file(tmp_path: Path) -> None:
    def mutate(data, workspace):
        data["evaluation"]["command"] = "python eval/run_eval.py"
        data["evaluation"]["output_format"] = "csv_with_summary"
        data["evaluation"].pop("output_file", None)

    _, result = _validate(tmp_path, mutate=mutate)

    assert not result.valid
    assert any(issue.code == "missing_csv_summary_output_file" for issue in result.issues)


def test_generated_adapter_requires_expected_risk_flags(tmp_path: Path) -> None:
    def mutate(data, workspace):
        data["evaluation"]["command"] = "python eval/run_eval.py"
        data["evaluation"]["adapter"] = {
            "kind": "metrics_parser",
            "template": "key_value_lines",
            "output_dir": "auto_optimize_outputs/generated_adapters",
            "purpose": "Parse key/value metrics into JSON.",
            "declaration_source": "tests.generated_parser",
            "risk_flags": ["generated_code"],
        }

    _, result = _validate(tmp_path, mutate=mutate)

    assert not result.valid
    assert any(issue.code == "missing_generated_adapter_risk_flag" for issue in result.issues)


def test_generated_adapter_kind_must_be_allowed_by_declaration_context(tmp_path: Path) -> None:
    def mutate(data, workspace):
        data["evaluation"]["command"] = "python eval/run_eval.py"
        data["evaluation"]["adapter"] = {
            "kind": "eval_wrapper",
            "template": "last_json_line",
            "output_dir": "auto_optimize_outputs/generated_adapters",
            "purpose": "Normalize noisy stdout into JSON metrics.",
            "declaration_source": "tests.eval_wrapper",
            "risk_flags": ["generated_code", "external_eval_command"],
        }
        data["declaration_context"] = {
            "adapter_generation": {
                "allowed": True,
                "allowed_kinds": ["metrics_parser"],
                "output_dir": "auto_optimize_outputs/generated_adapters",
            }
        }
        data["constraints"] = {"all_tests_pass": {"required": True}}
        data["metrics"]["secondary"] = []

    _, result = _validate(tmp_path, mutate=mutate)

    assert not result.valid
    assert any(issue.code == "generated_adapter_kind_not_allowed" for issue in result.issues)


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


def test_unsupported_search_strategy_fails(tmp_path: Path) -> None:
    def mutate(data, workspace):
        data["run_policy"]["search_strategy"] = "bayesian"

    _, result = _validate(tmp_path, mutate=mutate)

    assert not result.valid
    assert any(issue.code == "unsupported_search_strategy" for issue in result.issues)
