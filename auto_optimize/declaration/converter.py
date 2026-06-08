from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from auto_optimize.declaration.models import BudgetDeclaration, OptimizationDeclaration
from auto_optimize.shared.paths import to_posix_relative

SUPPORTED_VARIABLE_KINDS = {"yaml_path", "json_path", "env_var", "cli_arg"}
SUPPORTED_METRICS_SOURCES = {"stdout_json", "metrics_json", "csv_with_summary", "generated_parser"}
SUPPORTED_DIRECTIONS = {"maximize", "minimize"}
DEFAULT_DECISION_RULE = "constrained_primary_metric"
SUPPORTED_PARSER_TEMPLATES = {"key_value_lines"}


def _ensure_supported_declaration(declaration: OptimizationDeclaration) -> None:
    unsupported_variable_kinds = sorted(
        {variable.kind for variable in declaration.variables if variable.kind not in SUPPORTED_VARIABLE_KINDS}
    )
    if unsupported_variable_kinds:
        raise ValueError(
            "This declaration uses variable kinds that are not executable in the current slice: "
            f"{unsupported_variable_kinds}. Use `yaml_path`, `json_path`, `env_var`, or `cli_arg` for now."
        )

    if declaration.evaluation.metrics_source not in SUPPORTED_METRICS_SOURCES:
        raise ValueError(
            "This declaration uses an evaluation metrics source that is not executable in the current slice: "
            f"`{declaration.evaluation.metrics_source}`. Use `stdout_json`, `metrics_json`, `csv_with_summary`, or `generated_parser` for now."
        )

    directions = {declaration.comparison.direction}
    directions.update(metric.direction for metric in declaration.comparison.secondary_metrics)
    unsupported_directions = sorted(direction for direction in directions if direction not in SUPPORTED_DIRECTIONS)
    if unsupported_directions:
        raise ValueError(
            "Comparison directions must be one of "
            f"{sorted(SUPPORTED_DIRECTIONS)}. Found: {unsupported_directions}."
        )

    if declaration.evaluation.metrics_source == "metrics_json" and not declaration.evaluation.metrics_path:
        raise ValueError(
            "`evaluation.metrics_path` is required when `evaluation.metrics_source` is `metrics_json`."
        )
    if declaration.evaluation.metrics_source == "csv_with_summary" and not declaration.evaluation.metrics_path:
        raise ValueError(
            "`evaluation.metrics_path` is required when `evaluation.metrics_source` is `csv_with_summary`."
        )
    if declaration.evaluation.metrics_source == "generated_parser":
        if declaration.adapter_generation is None or not declaration.adapter_generation.allowed:
            raise ValueError(
                "`adapter_generation.allowed: true` is required when `evaluation.metrics_source` is `generated_parser`."
            )
        if declaration.evaluation.parser_template not in SUPPORTED_PARSER_TEMPLATES:
            raise ValueError(
                "This declaration uses an unsupported parser template for `generated_parser`: "
                f"`{declaration.evaluation.parser_template}`. Use one of {sorted(SUPPORTED_PARSER_TEMPLATES)}."
            )


def _rebase_workspace_path(declaration: OptimizationDeclaration, output_path: Path) -> str:
    if declaration.workspace_path is None:
        raise ValueError("Declaration workspace path could not be resolved.")

    try:
        relative_path = os.path.relpath(declaration.workspace_path, output_path.parent)
    except ValueError:
        return declaration.workspace_path.as_posix()
    return to_posix_relative(relative_path)


def _budget_to_run_policy(budget: BudgetDeclaration | None) -> dict[str, Any]:
    if budget is None:
        return {}

    run_policy: dict[str, Any] = {}
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
        value = getattr(budget, field_name)
        if value is not None:
            run_policy[field_name] = value
    return run_policy


def declaration_to_contract_data(
    declaration: OptimizationDeclaration,
    output_path: str | Path,
) -> dict[str, Any]:
    resolved_output_path = Path(output_path).resolve()
    _ensure_supported_declaration(declaration)

    search_space = {}
    for variable in declaration.variables:
        mapping = {
            "type": variable.kind,
            "file": variable.target,
        }
        if variable.path is not None:
            mapping["path"] = variable.path
        if variable.create_if_missing:
            mapping["create_if_missing"] = True

        search_space[variable.name] = {
            "values": list(variable.values),
            "mapping": mapping,
        }

    protected_scope = declaration.safety.protected + declaration.safety.secrets
    seen_protected: set[str] = set()
    deduped_protected = []
    for entry in protected_scope:
        if entry not in seen_protected:
            deduped_protected.append(entry)
            seen_protected.add(entry)

    evaluation = {
        "command": declaration.evaluation.command,
        "output_format": "csv_with_summary" if declaration.evaluation.metrics_source == "csv_with_summary" else "json",
        "timeout_seconds": declaration.evaluation.timeout_seconds,
    }
    if declaration.evaluation.metrics_path:
        evaluation["output_file"] = declaration.evaluation.metrics_path
    if declaration.evaluation.metrics_source == "generated_parser":
        adapter_generation = declaration.adapter_generation
        evaluation["adapter"] = {
            "kind": "metrics_parser",
            "template": declaration.evaluation.parser_template,
            "output_dir": adapter_generation.output_dir if adapter_generation is not None else "auto_optimize_outputs/generated_adapters",
            "purpose": "Parse evaluation output into a metrics JSON object.",
            "declaration_source": str(declaration.declaration_path) if declaration.declaration_path else None,
            "risk_flags": ["generated_code", "metrics_parsing"],
        }

    contract_data: dict[str, Any] = {
        "schema_version": "0.2",
        "scenario": {
            "type": "generic_declaration",
            "name": declaration.objective.description,
        },
        "workspace": {
            "path": _rebase_workspace_path(declaration, resolved_output_path),
        },
        "editable_scope": list(declaration.safety.editable),
        "protected_scope": deduped_protected,
        "search_space": search_space,
        "evaluation": evaluation,
        "metrics": {
            "primary": {
                "name": declaration.comparison.primary_metric,
                "direction": declaration.comparison.direction,
            },
            "secondary": [
                {
                    "name": metric.name,
                    "direction": metric.direction,
                }
                for metric in declaration.comparison.secondary_metrics
            ],
        },
        "constraints": dict(declaration.constraints),
        "decision_policy": {
            "mode": declaration.comparison.decision_rule or DEFAULT_DECISION_RULE,
            "min_primary_improvement": declaration.comparison.min_improvement or 0.0,
        },
        "declaration_context": {
            "source_declaration": str(declaration.declaration_path) if declaration.declaration_path else None,
            "objective": {
                "description": declaration.objective.description,
            },
            "evaluation": {
                "metrics_source": declaration.evaluation.metrics_source,
                "parser_template": declaration.evaluation.parser_template,
                "prepared_inputs": list(declaration.evaluation.prepared_inputs),
                "repetitions": declaration.evaluation.repetitions,
            },
            "safety": {
                "requires_confirmation": list(declaration.safety.requires_confirmation),
            },
        },
    }

    run_policy = _budget_to_run_policy(declaration.budget)
    if run_policy:
        contract_data["run_policy"] = run_policy

    if declaration.algorithm is not None:
        contract_data["declaration_context"]["algorithm"] = {
            "provided_by_user": declaration.algorithm.provided_by_user,
            "command": declaration.algorithm.command,
        }
    if declaration.adapter_generation is not None:
        contract_data["declaration_context"]["adapter_generation"] = {
            "allowed": declaration.adapter_generation.allowed,
            "allowed_kinds": list(declaration.adapter_generation.allowed_kinds),
            "output_dir": declaration.adapter_generation.output_dir,
        }

    return contract_data


def _default_output_path(declaration_path: Path) -> Path:
    if declaration_path.name.endswith(".declaration.yaml"):
        target_name = declaration_path.name.replace(".declaration.yaml", ".contract.generated.yaml")
    else:
        target_name = declaration_path.stem + ".contract.generated.yaml"
    return declaration_path.with_name(target_name)


def write_contract_from_declaration(
    declaration: OptimizationDeclaration,
    output_path: str | Path | None = None,
) -> Path:
    if declaration.declaration_path is None:
        raise ValueError("Declaration path is required before writing a contract.")

    resolved_output_path = (
        _default_output_path(declaration.declaration_path)
        if output_path is None
        else Path(output_path).resolve()
    )
    contract_data = declaration_to_contract_data(declaration, resolved_output_path)
    resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_output_path.write_text(
        yaml.safe_dump(contract_data, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )
    return resolved_output_path
