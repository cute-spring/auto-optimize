from __future__ import annotations

import json
import os
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from auto_optimize.builder.service import (
    SCENARIO_REQUIRED_FILES,
    SCENARIO_TO_PROFILE,
    build_contract_payload,
    detect_protected_scope,
    infer_scenario,
    load_benchmark_manifest,
    resolve_reference_fixture_context,
    write_yaml_file,
)
from auto_optimize.shared.schemas import DecisionPolicy, RunPolicy
from auto_optimize.shared.paths import to_posix_relative

_DECLARATION_EDITABLE_CANDIDATES = [
    "configs/retrieval.yaml",
    "configs/reranker.yaml",
    "configs/embedding_strategy.yaml",
    "configs/embedding.yaml",
    "configs/query_processing.yaml",
]
_METRICS_JSON_CANDIDATES = [
    "reports/metrics.json",
    "metrics.json",
]
_CSV_SUMMARY_CANDIDATES = [
    "reports/summary.csv",
    "summary.csv",
]


@dataclass(frozen=True, slots=True)
class AdvisorResult:
    draft_declaration_path: Path
    normalized_declaration_path: Path
    draft_contract_path: Path
    readiness_report_path: Path
    readiness_report: dict[str, Any]


def _build_draft_contract(
    workspace: Path,
    scenario: str,
    benchmark_key: str | None,
    benchmark_manifest: dict[str, Any] | None,
    contract_style: str,
) -> dict[str, Any]:
    payload = build_contract_payload(
        workspace=workspace,
        scenario=scenario,
        metric_profile=SCENARIO_TO_PROFILE[scenario],
        output_path=workspace / "auto_optimize_outputs" / "optimization.contract.draft.yaml",
        benchmark_key=benchmark_key,
        benchmark_manifest=benchmark_manifest,
        contract_style=contract_style,
    )
    payload["scenario"]["name"] = payload["scenario"].get("name") or f"Advisor Draft - {workspace.name}"
    if "version_control" in payload:
        payload["version_control"]["enabled"] = False
        payload["version_control"]["create_branch"] = False
        payload["version_control"]["commit_accepted_changes"] = False
    payload.setdefault("advisor_context", {})
    payload["advisor_context"]["contract_style"] = contract_style
    if benchmark_manifest is not None:
        payload["advisor_context"]["benchmark_manifest"] = benchmark_manifest
    return payload


def _workspace_reference(workspace: Path, output_path: Path) -> str:
    relative = os.path.relpath(workspace, start=output_path.parent)
    return to_posix_relative(relative)


def _build_draft_declaration(
    workspace: Path,
    draft_declaration_path: Path,
    draft_contract: dict[str, Any],
) -> dict[str, Any]:
    primary_metric = draft_contract["metrics"]["primary"]
    objective_description = (
        f"Improve {primary_metric['name']} for {workspace.name} while respecting declared safety boundaries."
    )

    variables = []
    for name, variable_data in draft_contract["search_space"].items():
        mapping = variable_data["mapping"]
        variable_declaration: dict[str, Any] = {
            "name": name,
            "kind": mapping["type"],
            "target": mapping["file"],
            "values": list(variable_data["values"]),
        }
        if mapping.get("path") is not None:
            variable_declaration["path"] = mapping["path"]
        if mapping.get("create_if_missing"):
            variable_declaration["create_if_missing"] = True
        variables.append(variable_declaration)

    metrics_source = "stdout_json"
    metrics_path = None
    for candidate in _CSV_SUMMARY_CANDIDATES:
        if (workspace / candidate).exists():
            metrics_source = "csv_with_summary"
            metrics_path = candidate
            break
    if metrics_path is None:
        for candidate in _METRICS_JSON_CANDIDATES:
            if (workspace / candidate).exists():
                metrics_source = "metrics_json"
                metrics_path = candidate
                break

    declaration: dict[str, Any] = {
        "schema_version": "0.1",
        "workspace": {
            "path": _workspace_reference(workspace, draft_declaration_path),
        },
        "objective": {
            "description": objective_description,
        },
        "variables": variables,
        "evaluation": {
            "command": draft_contract["evaluation"]["command"],
            "metrics_source": metrics_source,
        },
        "comparison": {
            "primary_metric": primary_metric["name"],
            "direction": primary_metric["direction"],
        },
        "safety": {
            "editable": list(draft_contract["editable_scope"]),
            "protected": list(draft_contract.get("protected_scope") or detect_protected_scope(workspace)),
        },
        "adapter_generation": {
            "allowed": False,
        },
    }
    if metrics_path is not None:
        declaration["evaluation"]["metrics_path"] = metrics_path

    secondary_metrics = [
        {
            "name": metric["name"],
            "direction": metric["direction"],
        }
        for metric in draft_contract.get("metrics", {}).get("secondary", [])
    ]
    if secondary_metrics:
        declaration["comparison"]["secondary_metrics"] = secondary_metrics

    decision_policy = draft_contract.get("decision_policy", {})
    if decision_policy.get("min_primary_improvement") is not None:
        declaration["comparison"]["min_improvement"] = decision_policy["min_primary_improvement"]
    if decision_policy.get("mode"):
        declaration["comparison"]["decision_rule"] = decision_policy["mode"]

    constraints = draft_contract.get("constraints")
    if constraints:
        declaration["constraints"] = constraints

    run_policy = draft_contract.get("run_policy")
    if run_policy:
        declaration["budget"] = {
            key: value
            for key, value in run_policy.items()
            if key
            in {
                "max_experiments",
                "stop_if_no_improvement_rounds",
                "search_strategy",
                "max_pairwise_candidates",
                "random_seed",
                "dry_run",
                "max_runtime_minutes",
                "max_cost_usd",
                "max_failed_evaluations",
            }
        }

    return declaration


def _build_normalized_declaration(
    draft_declaration: dict[str, Any],
    workspace: Path,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    normalized = json.loads(json.dumps(draft_declaration))
    autofill_applied: list[dict[str, str]] = []

    evaluation = normalized.setdefault("evaluation", {})
    if "timeout_seconds" not in evaluation:
        evaluation["timeout_seconds"] = 600
        autofill_applied.append(
            {
                "field": "evaluation.timeout_seconds",
                "reason": "Filled with the current executable default timeout so the declaration stays explicit.",
            }
        )
    if "repetitions" not in evaluation:
        evaluation["repetitions"] = 1
        autofill_applied.append(
            {
                "field": "evaluation.repetitions",
                "reason": "Filled with the current single-run default for declaration-first evaluation.",
            }
        )
    if "prepared_inputs" not in evaluation:
        evaluation["prepared_inputs"] = []
        autofill_applied.append(
            {
                "field": "evaluation.prepared_inputs",
                "reason": "Normalized to an explicit empty list so future prepared inputs are diffable.",
            }
        )

    comparison = normalized.setdefault("comparison", {})
    if "decision_rule" not in comparison:
        comparison["decision_rule"] = DecisionPolicy().mode
        autofill_applied.append(
            {
                "field": "comparison.decision_rule",
                "reason": "Filled with the current contract decision default.",
            }
        )
    if "min_improvement" not in comparison:
        comparison["min_improvement"] = DecisionPolicy().min_primary_improvement
        autofill_applied.append(
            {
                "field": "comparison.min_improvement",
                "reason": "Filled with the current no-threshold default so the rule is explicit.",
            }
        )

    safety = normalized.setdefault("safety", {})
    if not safety.get("protected"):
        safety["protected"] = detect_protected_scope(workspace)
        autofill_applied.append(
            {
                "field": "safety.protected",
                "reason": "Filled from the current workspace safety heuristic.",
            }
        )

    adapter_generation = normalized.setdefault("adapter_generation", {})
    if "allowed" not in adapter_generation:
        adapter_generation["allowed"] = False
        autofill_applied.append(
            {
                "field": "adapter_generation.allowed",
                "reason": "Defaulted to `false` until the declaration explicitly requests generated helper code.",
            }
        )
    if "allowed_kinds" not in adapter_generation:
        adapter_generation["allowed_kinds"] = []
        autofill_applied.append(
            {
                "field": "adapter_generation.allowed_kinds",
                "reason": "Normalized to an explicit empty list for future adapter-policy diffs.",
            }
        )

    if "budget" not in normalized:
        defaults = RunPolicy()
        normalized["budget"] = {
            "max_experiments": defaults.max_experiments,
            "stop_if_no_improvement_rounds": defaults.stop_if_no_improvement_rounds,
            "search_strategy": defaults.search_strategy,
            "max_pairwise_candidates": defaults.max_pairwise_candidates,
            "random_seed": defaults.random_seed,
            "dry_run": defaults.dry_run,
            "max_failed_evaluations": defaults.max_failed_evaluations,
        }
        autofill_applied.append(
            {
                "field": "budget",
                "reason": "Filled with conservative executable defaults so the normalized declaration is self-contained.",
            }
        )

    return normalized, autofill_applied


def _extract_command_file(command: str) -> str | None:
    parts = shlex.split(command)
    if len(parts) < 2:
        return None
    candidate = parts[1].strip()
    if not candidate or candidate.startswith("-"):
        return None
    return candidate


def _detect_declaration_editable_scope(workspace: Path) -> list[str]:
    return [path for path in _DECLARATION_EDITABLE_CANDIDATES if (workspace / path).exists()]


def _declaration_required_files(workspace: Path, draft_declaration: dict[str, Any]) -> tuple[list[str], list[str]]:
    required_files = list(draft_declaration["safety"]["editable"])

    evaluation_command = draft_declaration["evaluation"]["command"]
    command_file = _extract_command_file(evaluation_command)
    if command_file is not None and command_file not in required_files:
        required_files.append(command_file)

    metrics_path = draft_declaration["evaluation"].get("metrics_path")
    if metrics_path and metrics_path not in required_files:
        required_files.append(metrics_path)

    existing_files = [path for path in required_files if (workspace / path).exists()]
    missing_files = [path for path in required_files if not (workspace / path).exists()]
    return required_files, existing_files, missing_files


def _build_declaration_gaps(
    draft_declaration: dict[str, Any],
    declaration_missing_files: list[str],
    editable_scope: list[str],
    command_file: str | None,
) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []

    variables = draft_declaration.get("variables", [])
    if not variables:
        gaps.append(
            {
                "id": "missing_editable_variables",
                "severity": "high",
                "message": "No declaration variables were drafted yet.",
                "remediation": "Add at least one editable variable before declaration-first execution.",
            }
        )

    if not editable_scope:
        gaps.append(
            {
                "id": "missing_editable_scope",
                "severity": "high",
                "message": "No editable files were detected in the workspace.",
                "remediation": "Declare at least one editable target or restore the expected config files.",
            }
        )

    if not draft_declaration.get("evaluation", {}).get("command"):
        gaps.append(
            {
                "id": "missing_evaluation_command",
                "severity": "high",
                "message": "No evaluation command was detected for the draft declaration.",
                "remediation": "Add a runnable evaluation command before validation or run.",
            }
        )

    if command_file is not None and command_file in declaration_missing_files:
        gaps.append(
            {
                "id": "missing_evaluation_script",
                "severity": "high",
                "message": f"The evaluation command references a missing file: {command_file}.",
                "remediation": f"Create or restore `{command_file}` before declaration-first execution.",
            }
        )

    missing_editable_files = [
        path
        for path in declaration_missing_files
        if path in draft_declaration.get("safety", {}).get("editable", [])
    ]
    if missing_editable_files:
        gaps.append(
            {
                "id": "missing_editable_files",
                "severity": "medium",
                "message": "Some declared editable files are missing from the workspace.",
                "remediation": "Create or restore the missing editable files before validation.",
                "files": missing_editable_files,
            }
        )

    if not draft_declaration.get("safety", {}).get("protected"):
        gaps.append(
            {
                "id": "missing_protected_scope",
                "severity": "medium",
                "message": "No protected scope was detected for the declaration draft.",
                "remediation": "Add protected files, directories, or secrets before execution.",
            }
        )

    if not draft_declaration.get("constraints"):
        gaps.append(
            {
                "id": "missing_constraints_review",
                "severity": "low",
                "message": "No explicit constraints were drafted yet.",
                "remediation": "Review whether safety or quality constraints should be added before longer runs.",
            }
        )

    gaps.append(
        {
            "id": "review_draft_declaration",
            "severity": "low",
            "message": "The draft declaration should still be reviewed before longer or higher-risk runs.",
            "remediation": "Confirm the objective wording, variable values, and safety scope before relying on this draft as the long-term source of truth.",
        }
    )

    return gaps


def _score_fraction(completed: int, total: int) -> float:
    if total <= 0:
        return 100.0
    return round((completed / total) * 100, 1)


def _build_readiness_scores(
    draft_declaration: dict[str, Any],
    declaration_missing_files: list[str],
    ready_for_validate: bool,
    ready_for_run: bool,
) -> dict[str, float]:
    sections = [
        bool(draft_declaration.get("objective", {}).get("description")),
        bool(draft_declaration.get("variables")),
        bool(draft_declaration.get("evaluation", {}).get("command")),
        bool(draft_declaration.get("evaluation", {}).get("metrics_source")),
        bool(draft_declaration.get("comparison", {}).get("primary_metric")),
        bool(draft_declaration.get("safety", {}).get("editable")),
        bool(draft_declaration.get("safety", {}).get("protected")),
    ]
    authoring_completeness = _score_fraction(sum(1 for item in sections if item), len(sections))

    execution_checks = [
        ready_for_validate,
        ready_for_run,
        not declaration_missing_files,
        bool(draft_declaration.get("variables")),
        bool(draft_declaration.get("evaluation", {}).get("command")),
    ]
    execution_readiness = _score_fraction(sum(1 for item in execution_checks if item), len(execution_checks))

    safety_checks = [
        bool(draft_declaration.get("safety", {}).get("editable")),
        bool(draft_declaration.get("safety", {}).get("protected")),
        not any(path.startswith("eval/") for path in draft_declaration.get("safety", {}).get("editable", [])),
    ]
    safety_readiness = _score_fraction(sum(1 for item in safety_checks if item), len(safety_checks))

    return {
        "authoring_completeness": authoring_completeness,
        "execution_readiness": execution_readiness,
        "safety_readiness": safety_readiness,
    }


def _build_autofill_applied(
    draft_declaration: dict[str, Any],
    normalized_autofill_applied: list[dict[str, str]],
    scenario: str,
    metric_profile: str,
) -> list[dict[str, str]]:
    autofill_entries = [
        {
            "field": "objective.description",
            "reason": f"Drafted from the inferred primary metric and workspace name for scenario `{scenario}`.",
        },
        {
            "field": "evaluation.metrics_source",
            "reason": f"Inferred as `{draft_declaration['evaluation']['metrics_source']}` from the current workspace and evaluation shape.",
        },
        {
            "field": "comparison.metric_profile_hint",
            "reason": f"Reference fixture context suggested metric profile `{metric_profile}`.",
        },
    ]
    if draft_declaration.get("evaluation", {}).get("metrics_path"):
        autofill_entries.append(
            {
                "field": "evaluation.metrics_path",
                "reason": f"Inferred metrics artifact path `{draft_declaration['evaluation']['metrics_path']}` from the workspace.",
            }
        )
    autofill_entries.extend(normalized_autofill_applied)
    return autofill_entries


def _build_manual_decisions_required(
    draft_declaration: dict[str, Any],
    declaration_missing_files: list[str],
) -> list[str]:
    decisions = [
        "Review whether the drafted objective description matches the real optimization goal.",
        "Review the generated variable values and remove any that should not be searched automatically.",
    ]
    if not draft_declaration.get("constraints"):
        decisions.append("Decide whether additional constraints are needed before larger or riskier runs.")
    if declaration_missing_files:
        decisions.append("Resolve missing workspace files before trusting declaration-first execution readiness.")
    return decisions


def _build_readiness_report(
    workspace: Path,
    draft_declaration: dict[str, Any],
    draft_declaration_path: Path,
    normalized_declaration_path: Path,
    draft_contract_path: Path,
    scenario: str,
    metric_profile: str,
    benchmark_key: str | None,
    benchmark_manifest: dict[str, Any] | None,
    contract_style: str,
    normalized_autofill_applied: list[dict[str, str]],
) -> dict[str, Any]:
    editable_scope = _detect_declaration_editable_scope(workspace)
    declaration_required_files, declaration_existing_files, declaration_missing_files = _declaration_required_files(
        workspace,
        draft_declaration,
    )
    template_required_files = SCENARIO_REQUIRED_FILES[scenario]
    required_files = list(dict.fromkeys(declaration_required_files + template_required_files))
    existing_files = [path for path in required_files if (workspace / path).exists()]
    missing_files = [path for path in required_files if not (workspace / path).exists()]
    detected_eval_command = draft_declaration["evaluation"]["command"]

    ready_for_validate = len(editable_scope) > 0 and len(missing_files) == 0
    command_file = _extract_command_file(detected_eval_command)
    ready_for_run = ready_for_validate and (command_file is None or (workspace / command_file).exists())
    declaration_gaps = _build_declaration_gaps(
        draft_declaration=draft_declaration,
        declaration_missing_files=declaration_missing_files,
        editable_scope=editable_scope,
        command_file=command_file,
    )
    readiness_scores = _build_readiness_scores(
        draft_declaration=draft_declaration,
        declaration_missing_files=declaration_missing_files,
        ready_for_validate=ready_for_validate,
        ready_for_run=ready_for_run,
    )
    autofill_applied = _build_autofill_applied(
        draft_declaration=draft_declaration,
        normalized_autofill_applied=normalized_autofill_applied,
        scenario=scenario,
        metric_profile=metric_profile,
    )
    manual_decisions_required = _build_manual_decisions_required(
        draft_declaration=draft_declaration,
        declaration_missing_files=declaration_missing_files,
    )

    next_actions: list[str] = []
    declaration_first_next_actions: list[str] = []
    declared_contract_path = workspace / "auto_optimize_outputs" / "optimization.contract.generated.yaml"
    if missing_files:
        next_actions.extend([f"Create or restore missing required file: {path}" for path in missing_files])
        declaration_first_next_actions.extend(
            [f"Create or restore missing required file before declaration-first flow: {path}" for path in missing_files]
        )
    else:
        next_actions.append(f"Validate the generated draft contract: python -m auto_optimize.cli validate {draft_contract_path}")
        next_actions.append(
            f"Explain the generated draft contract: python -m auto_optimize.cli explain-contract {draft_contract_path}"
        )
        next_actions.append(f"Run the draft contract after validation: python -m auto_optimize.cli run {draft_contract_path}")
        declaration_first_next_actions.append(
            "Generate an executable contract from the draft declaration: "
            f"python -m auto_optimize.cli declare {normalized_declaration_path} --output {declared_contract_path}"
        )
        declaration_first_next_actions.append(
            f"Explain the declaration-generated contract: python -m auto_optimize.cli explain-contract {declared_contract_path}"
        )
        declaration_first_next_actions.append(
            f"Validate the declaration-generated contract: python -m auto_optimize.cli validate {declared_contract_path}"
        )

    return {
        "status": "ready" if ready_for_run else "needs_attention",
        "scenario_type": scenario,
        "recommended_metric_profile": metric_profile,
        "recommended_contract_style": contract_style,
        "metric_template_path": f"examples/metric_templates/{metric_profile}.yaml",
        "workspace_path": str(workspace),
        "draft_declaration_path": str(draft_declaration_path),
        "normalized_declaration_path": str(normalized_declaration_path),
        "draft_contract_path": str(draft_contract_path),
        "benchmark_key": benchmark_key,
        "benchmark_manifest": benchmark_manifest,
        "declaration_required_files": declaration_required_files,
        "declaration_existing_files": declaration_existing_files,
        "declaration_missing_files": declaration_missing_files,
        "required_files": required_files,
        "existing_files": existing_files,
        "missing_files": missing_files,
        "editable_scope_detected": editable_scope,
        "protected_scope_detected": detect_protected_scope(workspace),
        "evaluation_command_detected": detected_eval_command,
        "ready_for_validate": ready_for_validate,
        "ready_for_run": ready_for_run,
        "declaration_gaps": declaration_gaps,
        "readiness_scores": readiness_scores,
        "autofill_applied": autofill_applied,
        "manual_decisions_required": manual_decisions_required,
        "next_actions": next_actions,
        "declaration_first_next_actions": declaration_first_next_actions,
        "template_context": {
            "scenario_type": scenario,
            "recommended_metric_profile": metric_profile,
            "required_files": template_required_files,
            "benchmark_key": benchmark_key,
            "benchmark_manifest": benchmark_manifest,
        },
        "reference_fixture_context": resolve_reference_fixture_context(scenario, benchmark_key, metric_profile),
    }


def run_advisor(
    workspace_arg: str | Path,
    scenario: str | None = None,
    contract_style: str = "minimal",
) -> AdvisorResult:
    workspace = Path(workspace_arg).resolve()
    if not workspace.exists() or not workspace.is_dir():
        raise ValueError(f"Workspace does not exist or is not a directory: {workspace}")
    if contract_style not in {"minimal", "expanded"}:
        raise ValueError(f"Unsupported contract style: {contract_style}")

    benchmark_manifest = load_benchmark_manifest(workspace)
    benchmark_key = None if benchmark_manifest is None else benchmark_manifest.get("dataset_key")
    resolved_scenario = infer_scenario(workspace, scenario, benchmark_manifest)
    metric_profile = SCENARIO_TO_PROFILE[resolved_scenario]

    output_dir = workspace / "auto_optimize_outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    draft_declaration_path = output_dir / "optimization.declaration.draft.yaml"
    normalized_declaration_path = output_dir / "optimization.declaration.normalized.yaml"
    draft_contract_path = output_dir / "optimization.contract.draft.yaml"
    readiness_report_path = output_dir / "readiness_report.json"

    draft_contract = _build_draft_contract(
        workspace,
        resolved_scenario,
        benchmark_key,
        benchmark_manifest,
        contract_style,
    )
    draft_declaration = _build_draft_declaration(
        workspace=workspace,
        draft_declaration_path=draft_declaration_path,
        draft_contract=draft_contract,
    )
    normalized_declaration, normalized_autofill_applied = _build_normalized_declaration(
        draft_declaration=draft_declaration,
        workspace=workspace,
    )
    write_yaml_file(draft_declaration_path, draft_declaration)
    write_yaml_file(normalized_declaration_path, normalized_declaration)
    write_yaml_file(draft_contract_path, draft_contract)

    readiness_report = _build_readiness_report(
        workspace=workspace,
        draft_declaration=draft_declaration,
        draft_declaration_path=draft_declaration_path,
        normalized_declaration_path=normalized_declaration_path,
        draft_contract_path=draft_contract_path,
        scenario=resolved_scenario,
        metric_profile=metric_profile,
        benchmark_key=benchmark_key,
        benchmark_manifest=benchmark_manifest,
        contract_style=contract_style,
        normalized_autofill_applied=normalized_autofill_applied,
    )
    readiness_report_path.write_text(
        json.dumps(readiness_report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return AdvisorResult(
        draft_declaration_path=draft_declaration_path,
        normalized_declaration_path=normalized_declaration_path,
        draft_contract_path=draft_contract_path,
        readiness_report_path=readiness_report_path,
        readiness_report=readiness_report,
    )
