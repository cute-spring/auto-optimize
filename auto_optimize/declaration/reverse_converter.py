from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from auto_optimize.contract.explainer import load_raw_contract_data
from auto_optimize.shared.paths import to_posix_relative
from auto_optimize.shared.schemas import OptimizationContract

DEFAULT_DECISION_RULE = "constrained_primary_metric"


def _rebase_workspace_path(contract: OptimizationContract, output_path: Path) -> str:
    if contract.workspace_path is None:
        raise ValueError("Contract workspace path could not be resolved.")

    try:
        relative_path = os.path.relpath(contract.workspace_path, output_path.parent)
    except ValueError:
        return contract.workspace_path.as_posix()
    return to_posix_relative(relative_path)


def _derive_objective_description(contract: OptimizationContract, raw_data: dict[str, Any]) -> str:
    declaration_context = raw_data.get("declaration_context", {})
    declaration_objective = declaration_context.get("objective", {})
    description = declaration_objective.get("description")
    if isinstance(description, str) and description.strip():
        return description.strip()
    if contract.scenario.name:
        return contract.scenario.name
    return contract.scenario.type


def _derive_variables(contract: OptimizationContract) -> list[dict[str, Any]]:
    variables: list[dict[str, Any]] = []
    for name, parameter in contract.search_space.items():
        mapping = parameter.mapping
        variable: dict[str, Any] = {
            "name": name,
            "kind": mapping.type,
            "target": mapping.file,
            "values": list(parameter.values),
        }
        if mapping.path is not None:
            variable["path"] = mapping.path
        if mapping.create_if_missing:
            variable["create_if_missing"] = True
        variables.append(variable)
    return variables


def _derive_evaluation(contract: OptimizationContract, raw_data: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None]:
    declaration_context = raw_data.get("declaration_context", {})
    declaration_evaluation = declaration_context.get("evaluation", {})
    adapter_config = contract.evaluation.adapter

    evaluation: dict[str, Any] = {
        "command": contract.evaluation.command,
        "timeout_seconds": contract.evaluation.timeout_seconds,
    }
    adapter_generation: dict[str, Any] | None = None

    if adapter_config:
        evaluation["metrics_source"] = "generated_parser"
        if adapter_config.get("template"):
            evaluation["parser_template"] = adapter_config["template"]
        adapter_generation = {
            "allowed": True,
            "allowed_kinds": [adapter_config["kind"]] if adapter_config.get("kind") else [],
            "output_dir": adapter_config.get("output_dir", "auto_optimize_outputs/generated_adapters"),
        }
    elif contract.evaluation.output_format == "csv_with_summary":
        evaluation["metrics_source"] = "csv_with_summary"
        if contract.evaluation.output_file:
            evaluation["metrics_path"] = contract.evaluation.output_file
    elif contract.evaluation.output_file:
        evaluation["metrics_source"] = "metrics_json"
        evaluation["metrics_path"] = contract.evaluation.output_file
    else:
        evaluation["metrics_source"] = "stdout_json"

    repetitions = declaration_evaluation.get("repetitions")
    if repetitions not in (None, 1):
        evaluation["repetitions"] = repetitions
    prepared_inputs = declaration_evaluation.get("prepared_inputs")
    if isinstance(prepared_inputs, list) and prepared_inputs:
        evaluation["prepared_inputs"] = prepared_inputs

    return evaluation, adapter_generation


def _derive_comparison(contract: OptimizationContract) -> dict[str, Any]:
    comparison: dict[str, Any] = {
        "primary_metric": contract.metrics.primary.name,
        "direction": contract.metrics.primary.direction,
    }
    if contract.decision_policy.min_primary_improvement:
        comparison["min_improvement"] = contract.decision_policy.min_primary_improvement
    if contract.decision_policy.mode != DEFAULT_DECISION_RULE:
        comparison["decision_rule"] = contract.decision_policy.mode
    if contract.metrics.secondary:
        comparison["secondary_metrics"] = [
            {
                "name": metric.name,
                "direction": metric.direction,
            }
            for metric in contract.metrics.secondary
        ]
    return comparison


def _derive_safety(contract: OptimizationContract, raw_data: dict[str, Any]) -> dict[str, Any]:
    declaration_context = raw_data.get("declaration_context", {})
    declaration_safety = declaration_context.get("safety", {})
    safety: dict[str, Any] = {
        "editable": list(raw_data.get("editable_scope", contract.editable_scope)),
        "protected": list(raw_data.get("protected_scope", contract.protected_scope)),
    }
    requires_confirmation = declaration_safety.get("requires_confirmation")
    if isinstance(requires_confirmation, list) and requires_confirmation:
        safety["requires_confirmation"] = list(requires_confirmation)
    return safety


def _derive_budget(raw_data: dict[str, Any]) -> dict[str, Any] | None:
    raw_run_policy = raw_data.get("run_policy")
    if not isinstance(raw_run_policy, dict):
        return None

    budget: dict[str, Any] = {}
    for field_name in (
        "max_experiments",
        "stop_if_no_improvement_rounds",
        "search_strategy",
        "max_pairwise_candidates",
        "random_seed",
        "dry_run",
        "max_runtime_minutes",
        "max_cost_usd",
        "max_failed_evaluations",
    ):
        if field_name in raw_run_policy:
            budget[field_name] = raw_run_policy[field_name]
    return budget or None


def _derive_algorithm(raw_data: dict[str, Any]) -> dict[str, Any] | None:
    declaration_context = raw_data.get("declaration_context", {})
    algorithm = declaration_context.get("algorithm")
    if not isinstance(algorithm, dict):
        return None

    result: dict[str, Any] = {
        "provided_by_user": bool(algorithm.get("provided_by_user", False)),
    }
    command = algorithm.get("command")
    if isinstance(command, str) and command.strip():
        result["command"] = command.strip()
    return result


def contract_to_declaration_data(
    contract: OptimizationContract,
    raw_data: dict[str, Any],
    output_path: str | Path,
) -> dict[str, Any]:
    resolved_output_path = Path(output_path).resolve()
    evaluation, adapter_generation = _derive_evaluation(contract, raw_data)

    declaration_data: dict[str, Any] = {
        "schema_version": "0.1",
        "workspace": {
            "path": _rebase_workspace_path(contract, resolved_output_path),
        },
        "objective": {
            "description": _derive_objective_description(contract, raw_data),
        },
        "variables": _derive_variables(contract),
        "evaluation": evaluation,
        "comparison": _derive_comparison(contract),
        "constraints": dict(contract.constraints),
        "safety": _derive_safety(contract, raw_data),
    }

    budget = _derive_budget(raw_data)
    if budget:
        declaration_data["budget"] = budget

    algorithm = _derive_algorithm(raw_data)
    if algorithm:
        declaration_data["algorithm"] = algorithm

    if adapter_generation:
        declaration_data["adapter_generation"] = adapter_generation

    return declaration_data


def _default_output_path(contract_path: Path) -> Path:
    if contract_path.name.endswith(".contract.generated.yaml"):
        target_name = contract_path.name.replace(".contract.generated.yaml", ".derived.declaration.yaml")
    elif contract_path.name.endswith(".contract.yaml"):
        target_name = contract_path.name.replace(".contract.yaml", ".derived.declaration.yaml")
    else:
        target_name = contract_path.stem + ".derived.declaration.yaml"
    return contract_path.with_name(target_name)


def write_declaration_from_contract(
    contract: OptimizationContract,
    output_path: str | Path | None = None,
) -> Path:
    if contract.contract_path is None:
        raise ValueError("Contract path is required before deriving a declaration.")

    resolved_output_path = _default_output_path(contract.contract_path) if output_path is None else Path(output_path).resolve()
    raw_data = load_raw_contract_data(contract.contract_path)
    declaration_data = contract_to_declaration_data(contract, raw_data, resolved_output_path)
    resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_output_path.write_text(
        yaml.safe_dump(declaration_data, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )
    return resolved_output_path
