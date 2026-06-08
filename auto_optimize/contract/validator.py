from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
from typing import Any

import yaml

from auto_optimize.runner.generated_adapters import generated_adapter_spec
from auto_optimize.runner.evaluator import EvaluationExecutionError, execute_evaluation_with_details
from auto_optimize.safety.budget_guard import validate_run_policy
from auto_optimize.safety.eval_integrity_guard import infer_eval_paths
from auto_optimize.safety.scope_guard import find_scope_conflicts, is_editable, is_protected
from auto_optimize.safety.secret_guard import validate_secret_scope
from auto_optimize.shared.errors import ValidationResult
from auto_optimize.shared.git import inspect_git_repo, is_gh_available, is_git_available, list_remotes
from auto_optimize.shared.paths import resolve_workspace_relative, to_posix_relative
from auto_optimize.shared.schemas import OptimizationContract, SearchSpaceParameter

SUPPORTED_EVALUATION_OUTPUT_FORMATS = {"json", "csv_with_summary"}


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
    if mapping.type not in {"yaml_path", "json_path", "env_var", "cli_arg"}:
        result.add_issue(
            "error",
            "unsupported_mapping_type",
            f"Search space parameter '{name}' uses unsupported mapping type '{mapping.type}'.",
            field=f"search_space.{name}.mapping.type",
            hint="Use `yaml_path`, `json_path`, `env_var`, or `cli_arg` so AutoOptimize knows how to mutate the target.",
        )
        return

    if mapping.type == "env_var":
        env_name = mapping.file.strip()
        env_scope = f"env:{env_name}"
        if not env_name:
            result.add_issue(
                "error",
                "missing_env_var_name",
                f"Search space parameter '{name}' must declare a non-empty env var target.",
                field=f"search_space.{name}.mapping.file",
                hint="Use `mapping.file` to declare the environment variable name, for example `FEATURE_FLAG`.",
            )
            return
        if mapping.path not in (None, ""):
            result.add_issue(
                "error",
                "env_var_path_not_supported",
                f"Search space parameter '{name}' uses env_var and must not declare mapping.path.",
                field=f"search_space.{name}.mapping.path",
                hint="Remove `mapping.path` for `env_var` parameters. The environment variable name belongs in `mapping.file`.",
            )
        if not is_editable(env_scope, contract.editable_scope):
            result.add_issue(
                "error",
                "env_var_not_editable",
                f"Search space parameter '{name}' points to env var '{env_name}', which is outside editable_scope.",
                field=f"search_space.{name}.mapping.file",
                hint=f"Add `env:{env_name}` to `editable_scope` so AutoOptimize may modify this environment variable.",
            )
        if is_protected(env_scope, contract.protected_scope):
            result.add_issue(
                "error",
                "env_var_protected",
                f"Search space parameter '{name}' points to protected env var '{env_name}'.",
                field=f"search_space.{name}.mapping.file",
                hint="Environment variables cannot be both editable and protected.",
            )
        return

    if mapping.type == "cli_arg":
        argument_name = mapping.file.strip()
        argument_scope = f"cmd_arg:{argument_name}"
        if not argument_name:
            result.add_issue(
                "error",
                "missing_cli_arg_name",
                f"Search space parameter '{name}' must declare a non-empty cli arg target.",
                field=f"search_space.{name}.mapping.file",
                hint="Use `mapping.file` to declare the CLI argument name, for example `--mode`.",
            )
            return
        if not argument_name.startswith("-"):
            result.add_issue(
                "error",
                "invalid_cli_arg_name",
                f"Search space parameter '{name}' must target a flag-style CLI argument such as `--mode`.",
                field=f"search_space.{name}.mapping.file",
                hint="Use a dash-prefixed flag name for `cli_arg`, for example `--temperature`.",
            )
        if mapping.path not in (None, ""):
            result.add_issue(
                "error",
                "cli_arg_path_not_supported",
                f"Search space parameter '{name}' uses cli_arg and must not declare mapping.path.",
                field=f"search_space.{name}.mapping.path",
                hint="Remove `mapping.path` for `cli_arg` parameters. The argument flag belongs in `mapping.file`.",
            )
        if not is_editable(argument_scope, contract.editable_scope):
            result.add_issue(
                "error",
                "cli_arg_not_editable",
                f"Search space parameter '{name}' points to cli arg '{argument_name}', which is outside editable_scope.",
                field=f"search_space.{name}.mapping.file",
                hint=f"Add `cmd_arg:{argument_name}` to `editable_scope` so AutoOptimize may modify this CLI argument.",
            )
        if is_protected(argument_scope, contract.protected_scope):
            result.add_issue(
                "error",
                "cli_arg_protected",
                f"Search space parameter '{name}' points to protected cli arg '{argument_name}'.",
                field=f"search_space.{name}.mapping.file",
                hint="CLI arguments cannot be both editable and protected.",
            )
        return

    if not mapping.path:
        result.add_issue(
            "error",
            "missing_mapping_path",
            f"Search space parameter '{name}' must declare a dotted mapping path.",
            field=f"search_space.{name}.mapping.path",
            hint="Provide the dotted path to the YAML or JSON field that AutoOptimize should mutate.",
        )
        return

    relative_file = to_posix_relative(mapping.file)
    mapping_path = resolve_workspace_relative(contract.workspace_path, mapping.file)
    if not mapping_path.exists():
        result.add_issue(
            "error",
            "missing_mapping_file",
            f"Search space parameter '{name}' points to missing file '{mapping.file}'.",
            field=f"search_space.{name}.mapping.file",
            hint="Point this parameter at a real editable config file inside the workspace.",
        )
        return

    if not is_editable(relative_file, contract.editable_scope):
        result.add_issue(
            "error",
            "mapping_not_editable",
            f"Search space parameter '{name}' points to '{mapping.file}', which is outside editable_scope.",
            field=f"search_space.{name}.mapping.file",
            hint="Add the file to `editable_scope` or move the parameter to a file AutoOptimize is allowed to edit.",
        )
    if is_protected(relative_file, contract.protected_scope):
        result.add_issue(
            "error",
            "mapping_protected",
            f"Search space parameter '{name}' points to protected file '{mapping.file}'.",
            field=f"search_space.{name}.mapping.file",
            hint="Search parameters cannot write into protected files. Move this parameter into an editable config file.",
        )

    document = _load_structured_file(mapping_path, mapping.type)
    if not mapping.create_if_missing and not _path_exists_in_mapping(document, mapping.path):
        result.add_issue(
            "error",
            "missing_mapping_path",
            f"Search space parameter '{name}' points to missing path '{mapping.path}' in '{mapping.file}'.",
            field=f"search_space.{name}.mapping.path",
            hint="Fix the dotted path or set `create_if_missing: true` if the key should be created during mutation.",
        )


def _validate_version_control(contract: OptimizationContract, result: ValidationResult) -> None:
    version_control = contract.version_control

    if version_control.create_pull_request and not version_control.push_remote:
        result.add_issue(
            "error",
            "create_pr_requires_push_remote",
            "version_control.create_pull_request requires version_control.push_remote=true.",
            field="version_control.create_pull_request",
            hint="Enable `version_control.push_remote` before asking AutoOptimize to open a pull request.",
        )
    if version_control.create_pull_request and not version_control.create_branch:
        result.add_issue(
            "error",
            "create_pr_requires_branch",
            "version_control.create_pull_request requires version_control.create_branch=true.",
            field="version_control.create_pull_request",
            hint="Enable `version_control.create_branch` so the pull request has a dedicated branch to open from.",
        )
    if version_control.commit_accepted_changes and not version_control.enabled:
        result.add_issue(
            "error",
            "commit_requires_version_control",
            "version_control.commit_accepted_changes requires version_control.enabled=true.",
            field="version_control.commit_accepted_changes",
            hint="Either disable accepted-change commits or enable the version-control integration for this contract.",
        )
    if not version_control.enabled:
        return

    if not is_git_available():
        result.add_issue(
            "error",
            "git_not_available",
            "Git executable is required when version_control.enabled is true, but it is not available.",
            field="version_control.enabled",
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
                field="version_control.remote_name",
                hint="Use an existing remote name such as `origin`, or update the repository remotes before running.",
            )

    if version_control.create_pull_request and not is_gh_available():
        result.add_issue(
            "error",
            "gh_not_available",
            "GitHub CLI is required when version_control.create_pull_request=true, but `gh` is not available.",
            field="version_control.create_pull_request",
            hint="Install and authenticate `gh`, or disable pull request creation for this run.",
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
            field="metrics.primary.name",
            hint="Make sure your evaluation command emits this metric name exactly, or change the contract to match the eval output.",
        )

    required_constraint_metrics = set(contract.constraints.keys())
    for metric_name in required_constraint_metrics:
        if metric_name not in metrics:
            result.add_issue(
                "error",
                "missing_constraint_metric",
                f"Constraint metric '{metric_name}' is missing from baseline evaluation output.",
                field=f"constraints.{metric_name}",
                hint="Emit this metric from the evaluation command or remove the constraint from the contract.",
            )

    result.baseline_metrics = metrics


def _validate_evaluation_adapter(contract: OptimizationContract, result: ValidationResult) -> None:
    adapter = contract.evaluation.adapter
    if not adapter:
        return

    spec = generated_adapter_spec(adapter)
    kind = adapter.get("kind")
    template = adapter.get("template")
    output_dir = adapter.get("output_dir")
    risk_flags = adapter.get("risk_flags", [])

    if spec is None:
        result.add_issue(
            "error",
            "unsupported_generated_adapter",
            f"Unsupported generated adapter `{kind}` with template `{template}`.",
            field="evaluation.adapter",
            hint="Use the built-in `metrics_parser/key_value_lines` or `eval_wrapper/last_json_line` adapters for this slice.",
        )
        return

    for field_name in spec.required_fields:
        value = adapter.get(field_name)
        if field_name == "risk_flags":
            continue
        if not isinstance(value, str) or not value.strip():
            result.add_issue(
                "error",
                "missing_generated_adapter_field",
                f"Generated adapter `{kind}/{template}` requires a non-empty `{field_name}` field.",
                field=f"evaluation.adapter.{field_name}",
                hint=f"Populate `evaluation.adapter.{field_name}` for `{kind}/{template}`.",
            )

    if not isinstance(output_dir, str) or not output_dir.strip():
        result.add_issue(
            "error",
            "missing_generated_adapter_output_dir",
            "Generated adapter config must declare a non-empty output_dir.",
            field="evaluation.adapter.output_dir",
        )

    if not isinstance(risk_flags, list) or any(not isinstance(item, str) for item in risk_flags):
        result.add_issue(
            "error",
            "invalid_generated_adapter_risk_flags",
            "Generated adapter risk_flags must be a list of strings.",
            field="evaluation.adapter.risk_flags",
        )
    else:
        missing_flags = [flag for flag in spec.required_risk_flags if flag not in risk_flags]
        if missing_flags:
            result.add_issue(
                "error",
                "missing_generated_adapter_risk_flag",
                f"Generated adapter `{kind}/{template}` is missing required risk flags: {missing_flags}.",
                field="evaluation.adapter.risk_flags",
                hint=f"Include the required risk flags for `{kind}/{template}`: {list(spec.required_risk_flags)}.",
            )
        unsupported_flags = [flag for flag in risk_flags if flag not in spec.allowed_risk_flags]
        if unsupported_flags:
            result.add_issue(
                "error",
                "unsupported_generated_adapter_risk_flag",
                f"Generated adapter `{kind}/{template}` declares unsupported risk flags: {unsupported_flags}.",
                field="evaluation.adapter.risk_flags",
                hint=f"Use only the supported risk flags for `{kind}/{template}`: {list(spec.allowed_risk_flags)}.",
            )

    if contract.contract_path and contract.contract_path.exists():
        raw_contract = yaml.safe_load(contract.contract_path.read_text(encoding="utf-8")) or {}
        declaration_adapter_generation = raw_contract.get("declaration_context", {}).get("adapter_generation", {})
        if declaration_adapter_generation:
            if not declaration_adapter_generation.get("allowed", False):
                result.add_issue(
                    "error",
                    "generated_adapter_not_allowed_by_declaration",
                    f"Generated adapter `{kind}/{template}` is present, but declaration_context.adapter_generation.allowed is false.",
                    field="declaration_context.adapter_generation.allowed",
                    hint="Set `adapter_generation.allowed: true` in the declaration before generating this adapter path.",
                )
            allowed_kinds = declaration_adapter_generation.get("allowed_kinds", [])
            if allowed_kinds and spec.declaration_allowed_kind not in allowed_kinds:
                result.add_issue(
                    "error",
                    "generated_adapter_kind_not_allowed",
                    f"Generated adapter `{kind}/{template}` is not listed in declaration_context.adapter_generation.allowed_kinds.",
                    field="declaration_context.adapter_generation.allowed_kinds",
                    hint=f"Include `{spec.declaration_allowed_kind}` in `adapter_generation.allowed_kinds` for this declaration-driven adapter path.",
                )


def _validate_evaluation_config(contract: OptimizationContract, result: ValidationResult) -> None:
    output_format = contract.evaluation.output_format
    if output_format not in SUPPORTED_EVALUATION_OUTPUT_FORMATS:
        result.add_issue(
            "error",
            "unsupported_evaluation_output_format",
            f"Unsupported evaluation.output_format `{output_format}`.",
            field="evaluation.output_format",
            hint="Use `json` for JSON metrics or `csv_with_summary` for a summary CSV artifact.",
        )
        return

    if output_format == "csv_with_summary" and not contract.evaluation.output_file:
        result.add_issue(
            "error",
            "missing_csv_summary_output_file",
            "evaluation.output_file is required when evaluation.output_format is `csv_with_summary`.",
            field="evaluation.output_file",
            hint="Point `evaluation.output_file` at the CSV artifact containing the summary metrics row.",
        )


def _run_baseline_evaluation(contract: OptimizationContract, result: ValidationResult) -> None:
    try:
        outcome = execute_evaluation_with_details(contract)
    except EvaluationExecutionError as exc:
        result.add_issue("error", exc.code, exc.message, hint=exc.hint)
        return

    result.generated_adapters = [asdict(adapter) for adapter in outcome.generated_adapters]
    _validate_evaluation_metrics(contract, outcome.metrics, result)


def validate_contract(contract: OptimizationContract) -> ValidationResult:
    result = ValidationResult()

    if contract.workspace_path is None:
        result.add_issue("error", "missing_workspace_path", "Workspace path could not be resolved.")
        return result

    if not contract.workspace_path.exists():
        result.add_issue(
            "error",
            "missing_workspace",
            f"Workspace path does not exist: {contract.workspace_path}",
            field="workspace.path",
            hint="Set `workspace.path` relative to the contract file so it points at a real workspace directory.",
        )
        return result

    if not contract.workspace_path.is_dir():
        result.add_issue(
            "error",
            "workspace_not_directory",
            "Workspace path must be a directory.",
            field="workspace.path",
            hint="Point `workspace.path` at the workspace directory rather than a file.",
        )
        return result

    if not contract.editable_scope:
        result.add_issue(
            "error",
            "empty_editable_scope",
            "editable_scope must not be empty.",
            field="editable_scope",
            hint="List at least one config file that AutoOptimize is allowed to modify.",
        )

    conflicts = find_scope_conflicts(contract.editable_scope, contract.protected_scope)
    for editable, protected in conflicts:
        result.add_issue(
            "error",
            "scope_conflict",
            f"Editable scope '{editable}' conflicts with protected scope '{protected}'.",
            field="editable_scope",
            hint="A file cannot be both editable and protected. Remove it from one of the two scopes.",
        )

    validate_secret_scope(contract.editable_scope, result)
    validate_run_policy(contract.run_policy, result)
    _validate_version_control(contract, result)

    if not contract.search_space:
        result.add_issue(
            "error",
            "empty_search_space",
            "search_space must not be empty.",
            field="search_space",
            hint="Declare at least one tunable parameter with a target file, dotted path, and candidate values.",
        )
    else:
        for name, parameter in contract.search_space.items():
            _validate_search_parameter(name, parameter, contract, result)

    if contract.version_control.commit_accepted_changes and any(
        parameter.mapping.type == "cli_arg" for parameter in contract.search_space.values()
    ):
        result.add_issue(
            "error",
            "cli_arg_commit_not_supported",
            "version_control.commit_accepted_changes is not supported for cli_arg search parameters in this slice.",
            field="version_control.commit_accepted_changes",
            hint="Disable accepted-change commits for cli_arg runs, or use file-backed parameters so accepted state can be committed.",
        )

    for inferred_path in infer_eval_paths(contract.evaluation.command):
        if is_editable(inferred_path, contract.editable_scope):
            result.add_issue(
                "error",
                "eval_integrity_violation",
                f"Editable scope must not include evaluation path '{inferred_path}'.",
                field="editable_scope",
                hint="Keep evaluation code under protected paths such as `eval/` so optimization cannot rewrite the scorer.",
            )
        if not is_protected(inferred_path, contract.protected_scope):
            result.add_issue(
                "error",
                "eval_path_not_protected",
                f"Evaluation path '{inferred_path}' must be protected and is not covered by protected_scope.",
                field="protected_scope",
                hint="Add the evaluation path or its parent directory, usually `eval/`, to `protected_scope`.",
            )

    _validate_evaluation_adapter(contract, result)
    _validate_evaluation_config(contract, result)

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

    if result.generated_adapters:
        lines.extend(["## Generated Adapters", ""])
        for adapter in result.generated_adapters:
            lines.append(
                f"- `{adapter['kind']}` via `{adapter['template']}` at `{adapter['generated_path']}` "
                f"for `{adapter['purpose']}`. Risk flags: `{adapter['risk_flags']}`"
            )
        lines.append("")

    lines.extend(["## Issues", ""])
    if not result.issues:
        lines.append("- No validation issues found.")
    else:
        for issue in result.issues:
            detail = f"- [{issue.severity}] `{issue.code}`: {issue.message}"
            if issue.field:
                detail += f" Field: `{issue.field}`."
            if issue.hint:
                detail += f" Hint: {issue.hint}"
            lines.append(detail)
    lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path
