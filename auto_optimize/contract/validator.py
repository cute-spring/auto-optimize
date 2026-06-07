from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from auto_optimize.runner.evaluator import EvaluationExecutionError, execute_evaluation
from auto_optimize.safety.budget_guard import validate_run_policy
from auto_optimize.safety.eval_integrity_guard import infer_eval_paths
from auto_optimize.safety.scope_guard import find_scope_conflicts, is_editable, is_protected
from auto_optimize.safety.secret_guard import validate_secret_scope
from auto_optimize.shared.errors import ValidationResult
from auto_optimize.shared.git import inspect_git_repo, is_gh_available, is_git_available, list_remotes
from auto_optimize.shared.paths import resolve_workspace_relative, to_posix_relative
from auto_optimize.shared.schemas import OptimizationContract, SearchSpaceParameter


def _load_structured_file(path: Path, mapping_type: str) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        if mapping_type == "yaml_path":
            return yaml.safe_load(handle)
        if mapping_type == "json_path":
            return json.load(handle)
    raise ValueError(f"Unsupported mapping type: {mapping_type}")


def _path_exists_in_mapping(document: Any, dotted_path: str) -> bool:
    current = document
    for part in dotted_path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
            continue
        return False
    return True


def _validate_search_parameter(
    name: str,
    parameter: SearchSpaceParameter,
    contract: OptimizationContract,
    result: ValidationResult,
) -> None:
    if not parameter.values:
        result.add_issue("error", "empty_parameter_values", f"Search space parameter '{name}' has no values.")
        return

    mapping = parameter.mapping
    if mapping.type not in {"yaml_path", "json_path"}:
        result.add_issue(
            "error",
            "unsupported_mapping_type",
            f"Search space parameter '{name}' uses unsupported mapping type '{mapping.type}'.",
        )
        return

    relative_file = to_posix_relative(mapping.file)
    mapping_path = resolve_workspace_relative(contract.workspace_path, mapping.file)
    if not mapping_path.exists():
        result.add_issue(
            "error",
            "missing_mapping_file",
            f"Search space parameter '{name}' points to missing file '{mapping.file}'.",
        )
        return

    if not is_editable(relative_file, contract.editable_scope):
        result.add_issue(
            "error",
            "mapping_not_editable",
            f"Search space parameter '{name}' points to '{mapping.file}', which is outside editable_scope.",
        )
    if is_protected(relative_file, contract.protected_scope):
        result.add_issue(
            "error",
            "mapping_protected",
            f"Search space parameter '{name}' points to protected file '{mapping.file}'.",
        )

    document = _load_structured_file(mapping_path, mapping.type)
    if not mapping.create_if_missing and not _path_exists_in_mapping(document, mapping.path):
        result.add_issue(
            "error",
            "missing_mapping_path",
            f"Search space parameter '{name}' points to missing path '{mapping.path}' in '{mapping.file}'.",
        )


def _validate_version_control(contract: OptimizationContract, result: ValidationResult) -> None:
    version_control = contract.version_control

    if version_control.create_pull_request and not version_control.push_remote:
        result.add_issue(
            "error",
            "create_pr_requires_push_remote",
            "version_control.create_pull_request requires version_control.push_remote=true.",
        )
    if version_control.create_pull_request and not version_control.create_branch:
        result.add_issue(
            "error",
            "create_pr_requires_branch",
            "version_control.create_pull_request requires version_control.create_branch=true.",
        )
    if version_control.commit_accepted_changes and not version_control.enabled:
        result.add_issue(
            "error",
            "commit_requires_version_control",
            "version_control.commit_accepted_changes requires version_control.enabled=true.",
        )
    if not version_control.enabled:
        return

    if not is_git_available():
        result.add_issue(
            "error",
            "git_not_available",
            "Git executable is required when version_control.enabled is true, but it is not available.",
        )
        return

    git_state = inspect_git_repo(contract.workspace_path)
    result.git_state = git_state.as_dict()

    if not git_state.is_repo:
        result.add_issue(
            "error",
            "workspace_not_git_repo",
            "version_control.enabled is true, but workspace is not inside a Git work tree.",
            hint="Disable version_control or get user approval before initializing Git.",
        )
        return

    if version_control.require_clean_worktree and not git_state.worktree_clean:
        result.add_issue(
            "error",
            "dirty_worktree",
            "Git worktree must be clean because version_control.require_clean_worktree is true.",
            hint="Commit, stash, or discard local changes before running optimization.",
        )
    elif not version_control.require_clean_worktree and not git_state.worktree_clean:
        result.add_issue(
            "warning",
            "dirty_worktree_allowed",
            "Git worktree is dirty. MVP validation records this, but future runner logic must avoid unrelated rollback.",
        )

    if not version_control.create_branch and git_state.branch in {"main", "master"}:
        result.add_issue(
            "warning",
            "protected_branch_execution",
            "Contract disables optimization branch creation while targeting a protected default branch.",
        )

    if version_control.push_remote or version_control.create_pull_request:
        remotes = list_remotes(contract.workspace_path)
        if version_control.remote_name not in remotes:
            result.add_issue(
                "error",
                "missing_git_remote",
                f"Configured Git remote '{version_control.remote_name}' does not exist in the workspace repository.",
            )

    if version_control.create_pull_request and not is_gh_available():
        result.add_issue(
            "error",
            "gh_not_available",
            "GitHub CLI is required when version_control.create_pull_request=true, but `gh` is not available.",
        )


def _validate_evaluation_metrics(
    contract: OptimizationContract,
    metrics: dict[str, Any],
    result: ValidationResult,
) -> None:
    primary_metric = contract.metrics.primary.name
    if primary_metric not in metrics:
        result.add_issue(
            "error",
            "missing_primary_metric",
            f"Primary metric '{primary_metric}' is missing from baseline evaluation output.",
        )

    required_constraint_metrics = set(contract.constraints.keys())
    for metric_name in required_constraint_metrics:
        if metric_name not in metrics:
            result.add_issue(
                "error",
                "missing_constraint_metric",
                f"Constraint metric '{metric_name}' is missing from baseline evaluation output.",
            )

    result.baseline_metrics = metrics


def _run_baseline_evaluation(contract: OptimizationContract, result: ValidationResult) -> None:
    try:
        metrics = execute_evaluation(contract)
    except EvaluationExecutionError as exc:
        result.add_issue("error", exc.code, exc.message, hint=exc.hint)
        return

    _validate_evaluation_metrics(contract, metrics, result)


def validate_contract(contract: OptimizationContract) -> ValidationResult:
    result = ValidationResult()

    if contract.workspace_path is None:
        result.add_issue("error", "missing_workspace_path", "Workspace path could not be resolved.")
        return result

    if not contract.workspace_path.exists():
        result.add_issue("error", "missing_workspace", f"Workspace path does not exist: {contract.workspace_path}")
        return result

    if not contract.workspace_path.is_dir():
        result.add_issue("error", "workspace_not_directory", "Workspace path must be a directory.")
        return result

    if not contract.editable_scope:
        result.add_issue("error", "empty_editable_scope", "editable_scope must not be empty.")

    conflicts = find_scope_conflicts(contract.editable_scope, contract.protected_scope)
    for editable, protected in conflicts:
        result.add_issue(
            "error",
            "scope_conflict",
            f"Editable scope '{editable}' conflicts with protected scope '{protected}'.",
        )

    validate_secret_scope(contract.editable_scope, result)
    validate_run_policy(contract.run_policy, result)
    _validate_version_control(contract, result)

    if not contract.search_space:
        result.add_issue("error", "empty_search_space", "search_space must not be empty.")
    else:
        for name, parameter in contract.search_space.items():
            _validate_search_parameter(name, parameter, contract, result)

    for inferred_path in infer_eval_paths(contract.evaluation.command):
        if is_editable(inferred_path, contract.editable_scope):
            result.add_issue(
                "error",
                "eval_integrity_violation",
                f"Editable scope must not include evaluation path '{inferred_path}'.",
            )
        if not is_protected(inferred_path, contract.protected_scope):
            result.add_issue(
                "error",
                "eval_path_not_protected",
                f"Evaluation path '{inferred_path}' must be protected and is not covered by protected_scope.",
            )

    if result.valid:
        _run_baseline_evaluation(contract, result)

    return result


def write_validation_report(contract: OptimizationContract, result: ValidationResult) -> Path:
    output_dir = resolve_workspace_relative(contract.workspace_path, contract.report.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "contract_validation_report.md"

    lines = [
        "# Contract Validation Report",
        "",
        f"- Contract: `{contract.contract_path}`",
        f"- Workspace: `{contract.workspace_path}`",
        f"- Status: {'PASSED' if result.valid else 'FAILED'}",
        f"- Schema version: `{contract.schema_version}`",
        "",
        "## Summary",
        "",
        f"- Issues: {len(result.issues)}",
        f"- Baseline metrics captured: {'yes' if result.baseline_metrics else 'no'}",
        f"- Git checks captured: {'yes' if result.git_state else 'no'}",
        "",
    ]

    if result.git_state:
        lines.extend(["## Git Validation", ""])
        for key, value in result.git_state.items():
            lines.append(f"- `{key}`: `{value}`")
        lines.append("")

    if result.baseline_metrics:
        lines.extend(["## Baseline Metrics", ""])
        for key, value in sorted(result.baseline_metrics.items()):
            lines.append(f"- `{key}`: `{value}`")
        lines.append("")

    lines.extend(["## Issues", ""])
    if not result.issues:
        lines.append("- No validation issues found.")
    else:
        for issue in result.issues:
            detail = f"- [{issue.severity}] `{issue.code}`: {issue.message}"
            if issue.hint:
                detail += f" Hint: {issue.hint}"
            lines.append(detail)
    lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path
