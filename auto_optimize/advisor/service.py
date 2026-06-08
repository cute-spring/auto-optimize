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
from auto_optimize.shared.paths import to_posix_relative

_DECLARATION_EDITABLE_CANDIDATES = [
    "configs/retrieval.yaml",
    "configs/reranker.yaml",
    "configs/embedding_strategy.yaml",
    "configs/embedding.yaml",
    "configs/query_processing.yaml",
]


@dataclass(frozen=True, slots=True)
class AdvisorResult:
    draft_declaration_path: Path
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
            "metrics_source": "stdout_json",
        },
        "comparison": {
            "primary_metric": primary_metric["name"],
            "direction": primary_metric["direction"],
        },
        "safety": {
            "editable": list(draft_contract["editable_scope"]),
            "protected": list(draft_contract.get("protected_scope", [])),
        },
        "adapter_generation": {
            "allowed": False,
        },
    }

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


def _build_readiness_report(
    workspace: Path,
    draft_declaration: dict[str, Any],
    draft_declaration_path: Path,
    draft_contract_path: Path,
    scenario: str,
    metric_profile: str,
    benchmark_key: str | None,
    benchmark_manifest: dict[str, Any] | None,
    contract_style: str,
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
            f"python -m auto_optimize.cli declare {draft_declaration_path} --output {declared_contract_path}"
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
    write_yaml_file(draft_declaration_path, draft_declaration)
    write_yaml_file(draft_contract_path, draft_contract)

    readiness_report = _build_readiness_report(
        workspace=workspace,
        draft_declaration=draft_declaration,
        draft_declaration_path=draft_declaration_path,
        draft_contract_path=draft_contract_path,
        scenario=resolved_scenario,
        metric_profile=metric_profile,
        benchmark_key=benchmark_key,
        benchmark_manifest=benchmark_manifest,
        contract_style=contract_style,
    )
    readiness_report_path.write_text(
        json.dumps(readiness_report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return AdvisorResult(
        draft_declaration_path=draft_declaration_path,
        draft_contract_path=draft_contract_path,
        readiness_report_path=readiness_report_path,
        readiness_report=readiness_report,
    )
