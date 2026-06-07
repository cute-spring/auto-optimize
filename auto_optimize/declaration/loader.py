from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from auto_optimize.declaration.models import (
    AdapterGenerationDeclaration,
    AlgorithmDeclaration,
    BudgetDeclaration,
    ComparisonDeclaration,
    DeclarationWorkspace,
    EvaluationDeclaration,
    MetricDeclaration,
    ObjectiveDeclaration,
    OptimizationDeclaration,
    SafetyDeclaration,
    VariableDeclaration,
)
from auto_optimize.shared.paths import resolve_contract_relative


class DeclarationValidationError(ValueError):
    def __init__(self, issues: list[str]) -> None:
        self.issues = issues
        super().__init__("\n".join(issues))


def _require_mapping(data: dict[str, Any], key: str, issues: list[str]) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        issues.append(f"Missing or invalid `{key}` section.")
        return {}
    return value


def _require_string(data: dict[str, Any], key: str, issues: list[str], field_name: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        issues.append(f"Missing required `{field_name}` string.")
        return ""
    return value.strip()


def _optional_string(data: dict[str, Any], key: str, issues: list[str], field_name: str) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        issues.append(f"Invalid `{field_name}` string.")
        return None
    return value.strip()


def _require_list(data: dict[str, Any], key: str, issues: list[str], field_name: str) -> list[Any]:
    value = data.get(key)
    if not isinstance(value, list):
        issues.append(f"Missing or invalid `{field_name}` list.")
        return []
    return value


def _string_list(value: Any, issues: list[str], field_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        issues.append(f"Invalid `{field_name}` list.")
        return []
    return [item.strip() for item in value]


def _optional_int(data: dict[str, Any], key: str, issues: list[str], field_name: str) -> int | None:
    value = data.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        issues.append(f"Invalid `{field_name}` integer.")
        return None
    return value


def _optional_float(data: dict[str, Any], key: str, issues: list[str], field_name: str) -> float | None:
    value = data.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        issues.append(f"Invalid `{field_name}` number.")
        return None
    return float(value)


def _optional_bool(data: dict[str, Any], key: str, issues: list[str], field_name: str) -> bool | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, bool):
        issues.append(f"Invalid `{field_name}` boolean.")
        return None
    return value


def _load_variable(raw_variable: Any, index: int, issues: list[str]) -> VariableDeclaration | None:
    field_prefix = f"variables[{index}]"
    if not isinstance(raw_variable, dict):
        issues.append(f"Invalid `{field_prefix}` item.")
        return None

    name = _require_string(raw_variable, "name", issues, f"{field_prefix}.name")
    kind = _require_string(raw_variable, "kind", issues, f"{field_prefix}.kind")
    target = _require_string(raw_variable, "target", issues, f"{field_prefix}.target")
    path = _optional_string(raw_variable, "path", issues, f"{field_prefix}.path")
    values = _require_list(raw_variable, "values", issues, f"{field_prefix}.values")

    create_if_missing = raw_variable.get("create_if_missing", False)
    if not isinstance(create_if_missing, bool):
        issues.append(f"Invalid `{field_prefix}.create_if_missing` boolean.")
        create_if_missing = False

    return VariableDeclaration(
        name=name,
        kind=kind,
        target=target,
        path=path,
        values=list(values),
        create_if_missing=create_if_missing,
    )


def _load_secondary_metrics(raw_metrics: Any, issues: list[str]) -> list[MetricDeclaration]:
    if raw_metrics is None:
        return []
    if not isinstance(raw_metrics, list):
        issues.append("Invalid `comparison.secondary_metrics` list.")
        return []

    metrics: list[MetricDeclaration] = []
    for index, raw_metric in enumerate(raw_metrics):
        field_prefix = f"comparison.secondary_metrics[{index}]"
        if not isinstance(raw_metric, dict):
            issues.append(f"Invalid `{field_prefix}` item.")
            continue
        name = _require_string(raw_metric, "name", issues, f"{field_prefix}.name")
        direction = _require_string(raw_metric, "direction", issues, f"{field_prefix}.direction")
        metrics.append(MetricDeclaration(name=name, direction=direction))
    return metrics


def load_declaration(declaration_path: str | Path) -> OptimizationDeclaration:
    resolved_path = Path(declaration_path).resolve()
    with resolved_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    if not isinstance(data, dict):
        raise DeclarationValidationError(["Declaration file must contain a top-level mapping."])

    issues: list[str] = []

    objective_data = _require_mapping(data, "objective", issues)
    evaluation_data = _require_mapping(data, "evaluation", issues)
    comparison_data = _require_mapping(data, "comparison", issues)
    safety_data = _require_mapping(data, "safety", issues)
    workspace_data = data.get("workspace", {})
    if workspace_data is None:
        workspace_data = {}
    if not isinstance(workspace_data, dict):
        issues.append("Invalid `workspace` section.")
        workspace_data = {}

    objective = ObjectiveDeclaration(
        description=_require_string(objective_data, "description", issues, "objective.description"),
    )

    variables: list[VariableDeclaration] = []
    raw_variables = _require_list(data, "variables", issues, "variables")
    for index, raw_variable in enumerate(raw_variables):
        variable = _load_variable(raw_variable, index, issues)
        if variable is not None:
            variables.append(variable)
    if not variables:
        issues.append("Declaration must include at least one variable.")

    evaluation = EvaluationDeclaration(
        command=_require_string(evaluation_data, "command", issues, "evaluation.command"),
        metrics_source=_require_string(evaluation_data, "metrics_source", issues, "evaluation.metrics_source"),
        timeout_seconds=_optional_int(
            evaluation_data,
            "timeout_seconds",
            issues,
            "evaluation.timeout_seconds",
        )
        or 600,
        metrics_path=(
            _optional_string(evaluation_data, "metrics_path", issues, "evaluation.metrics_path")
            or _optional_string(evaluation_data, "output_file", issues, "evaluation.output_file")
        ),
        parser_template=_optional_string(
            evaluation_data,
            "parser_template",
            issues,
            "evaluation.parser_template",
        ),
        repetitions=_optional_int(evaluation_data, "repetitions", issues, "evaluation.repetitions") or 1,
        prepared_inputs=_string_list(
            evaluation_data.get("prepared_inputs"),
            issues,
            "evaluation.prepared_inputs",
        ),
    )

    comparison = ComparisonDeclaration(
        primary_metric=_require_string(
            comparison_data,
            "primary_metric",
            issues,
            "comparison.primary_metric",
        ),
        direction=_require_string(comparison_data, "direction", issues, "comparison.direction"),
        min_improvement=_optional_float(
            comparison_data,
            "min_improvement",
            issues,
            "comparison.min_improvement",
        ),
        decision_rule=_optional_string(
            comparison_data,
            "decision_rule",
            issues,
            "comparison.decision_rule",
        ),
        secondary_metrics=_load_secondary_metrics(comparison_data.get("secondary_metrics"), issues),
    )

    safety = SafetyDeclaration(
        editable=_string_list(safety_data.get("editable"), issues, "safety.editable"),
        protected=_string_list(safety_data.get("protected"), issues, "safety.protected"),
        secrets=_string_list(safety_data.get("secrets"), issues, "safety.secrets"),
        requires_confirmation=_string_list(
            safety_data.get("requires_confirmation"),
            issues,
            "safety.requires_confirmation",
        ),
    )
    if not safety.editable:
        issues.append("Declaration must include at least one editable path in `safety.editable`.")

    constraints = data.get("constraints", {})
    if constraints is None:
        constraints = {}
    if not isinstance(constraints, dict):
        issues.append("Invalid `constraints` mapping.")
        constraints = {}

    budget = None
    raw_budget = data.get("budget")
    if raw_budget is not None:
        if not isinstance(raw_budget, dict):
            issues.append("Invalid `budget` section.")
        else:
            budget = BudgetDeclaration(
                max_experiments=_optional_int(raw_budget, "max_experiments", issues, "budget.max_experiments"),
                stop_if_no_improvement_rounds=_optional_int(
                    raw_budget,
                    "stop_if_no_improvement_rounds",
                    issues,
                    "budget.stop_if_no_improvement_rounds",
                ),
                search_strategy=_optional_string(raw_budget, "search_strategy", issues, "budget.search_strategy"),
                max_pairwise_candidates=_optional_int(
                    raw_budget,
                    "max_pairwise_candidates",
                    issues,
                    "budget.max_pairwise_candidates",
                ),
                random_seed=_optional_int(raw_budget, "random_seed", issues, "budget.random_seed"),
                dry_run=_optional_bool(raw_budget, "dry_run", issues, "budget.dry_run"),
                max_runtime_minutes=_optional_int(
                    raw_budget,
                    "max_runtime_minutes",
                    issues,
                    "budget.max_runtime_minutes",
                ),
                max_cost_usd=_optional_float(raw_budget, "max_cost_usd", issues, "budget.max_cost_usd"),
                max_failed_evaluations=_optional_int(
                    raw_budget,
                    "max_failed_evaluations",
                    issues,
                    "budget.max_failed_evaluations",
                ),
            )

    algorithm = None
    raw_algorithm = data.get("algorithm")
    if raw_algorithm is not None:
        if not isinstance(raw_algorithm, dict):
            issues.append("Invalid `algorithm` section.")
        else:
            algorithm = AlgorithmDeclaration(
                provided_by_user=bool(raw_algorithm.get("provided_by_user", False)),
                command=_optional_string(raw_algorithm, "command", issues, "algorithm.command"),
            )
            if algorithm.provided_by_user and not algorithm.command:
                issues.append("`algorithm.command` is required when `algorithm.provided_by_user` is true.")

    adapter_generation = None
    raw_adapter_generation = data.get("adapter_generation")
    if raw_adapter_generation is not None:
        if not isinstance(raw_adapter_generation, dict):
            issues.append("Invalid `adapter_generation` section.")
        else:
            allowed = _optional_bool(
                raw_adapter_generation,
                "allowed",
                issues,
                "adapter_generation.allowed",
            )
            adapter_generation = AdapterGenerationDeclaration(
                allowed=allowed if allowed is not None else False,
                allowed_kinds=_string_list(
                    raw_adapter_generation.get("allowed_kinds"),
                    issues,
                    "adapter_generation.allowed_kinds",
                ),
                output_dir=(
                    _optional_string(
                        raw_adapter_generation,
                        "output_dir",
                        issues,
                        "adapter_generation.output_dir",
                    )
                    or "auto_optimize_outputs/generated_adapters"
                ),
            )

    workspace = DeclarationWorkspace(
        path=_optional_string(workspace_data, "path", issues, "workspace.path") or ".",
    )

    if issues:
        raise DeclarationValidationError(issues)

    declaration = OptimizationDeclaration(
        schema_version=str(data.get("schema_version", "0.1")),
        workspace=workspace,
        objective=objective,
        variables=variables,
        evaluation=evaluation,
        comparison=comparison,
        constraints=dict(constraints),
        safety=safety,
        budget=budget,
        algorithm=algorithm,
        adapter_generation=adapter_generation,
    )
    declaration.declaration_path = resolved_path
    declaration.declaration_dir = resolved_path.parent
    declaration.workspace_path = resolve_contract_relative(declaration.declaration_dir, declaration.workspace.path)
    return declaration
