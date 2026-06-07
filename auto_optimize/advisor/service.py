from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from auto_optimize.builder.service import (
    SCENARIO_REQUIRED_FILES,
    SCENARIO_TO_PROFILE,
    build_contract_payload,
    detect_editable_scope,
    detect_eval_command,
    detect_protected_scope,
    infer_scenario,
    load_benchmark_manifest,
    write_yaml_file,
)


@dataclass(frozen=True, slots=True)
class AdvisorResult:
    draft_contract_path: Path
    readiness_report_path: Path
    readiness_report: dict[str, Any]


def _build_draft_contract(
    workspace: Path,
    scenario: str,
    benchmark_key: str | None,
    benchmark_manifest: dict[str, Any] | None,
) -> dict[str, Any]:
    payload = build_contract_payload(
        workspace=workspace,
        scenario=scenario,
        metric_profile=SCENARIO_TO_PROFILE[scenario],
        output_path=workspace / "auto_optimize_outputs" / "optimization.contract.draft.yaml",
        benchmark_key=benchmark_key,
        benchmark_manifest=benchmark_manifest,
    )
    payload["scenario"]["name"] = payload["scenario"].get("name") or f"Advisor Draft - {workspace.name}"
    payload["version_control"]["enabled"] = False
    payload["version_control"]["create_branch"] = False
    payload["version_control"]["commit_accepted_changes"] = False
    if benchmark_manifest is not None:
        payload.setdefault("advisor_context", {})
        payload["advisor_context"]["benchmark_manifest"] = benchmark_manifest
    return payload


def _build_readiness_report(
    workspace: Path,
    scenario: str,
    metric_profile: str,
    draft_contract_path: Path,
    benchmark_key: str | None,
    benchmark_manifest: dict[str, Any] | None,
) -> dict[str, Any]:
    required_files = SCENARIO_REQUIRED_FILES[scenario]
    existing_files = [path for path in required_files if (workspace / path).exists()]
    missing_files = [path for path in required_files if not (workspace / path).exists()]
    detected_eval_command = detect_eval_command(workspace, scenario)
    editable_scope = detect_editable_scope(workspace, scenario)

    ready_for_validate = len(editable_scope) > 0 and len(missing_files) == 0
    ready_for_run = ready_for_validate and (
        (workspace / detected_eval_command.split()[1]).exists() if len(detected_eval_command.split()) > 1 else False
    )

    next_actions: list[str] = []
    if missing_files:
        next_actions.extend([f"Create or restore missing required file: {path}" for path in missing_files])
    else:
        next_actions.append(f"Validate the generated draft contract: python -m auto_optimize.cli validate {draft_contract_path}")
        next_actions.append(f"Run the draft contract after validation: python -m auto_optimize.cli run {draft_contract_path}")

    return {
        "status": "ready" if ready_for_run else "needs_attention",
        "scenario_type": scenario,
        "recommended_metric_profile": metric_profile,
        "metric_template_path": f"examples/metric_templates/{metric_profile}.yaml",
        "workspace_path": str(workspace),
        "draft_contract_path": str(draft_contract_path),
        "benchmark_key": benchmark_key,
        "benchmark_manifest": benchmark_manifest,
        "required_files": required_files,
        "existing_files": existing_files,
        "missing_files": missing_files,
        "editable_scope_detected": editable_scope,
        "protected_scope_detected": detect_protected_scope(workspace),
        "evaluation_command_detected": detected_eval_command,
        "ready_for_validate": ready_for_validate,
        "ready_for_run": ready_for_run,
        "next_actions": next_actions,
    }


def run_advisor(workspace_arg: str | Path, scenario: str | None = None) -> AdvisorResult:
    workspace = Path(workspace_arg).resolve()
    if not workspace.exists() or not workspace.is_dir():
        raise ValueError(f"Workspace does not exist or is not a directory: {workspace}")

    benchmark_manifest = load_benchmark_manifest(workspace)
    benchmark_key = None if benchmark_manifest is None else benchmark_manifest.get("dataset_key")
    resolved_scenario = infer_scenario(workspace, scenario, benchmark_manifest)
    metric_profile = SCENARIO_TO_PROFILE[resolved_scenario]

    output_dir = workspace / "auto_optimize_outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    draft_contract_path = output_dir / "optimization.contract.draft.yaml"
    readiness_report_path = output_dir / "readiness_report.json"

    draft_contract = _build_draft_contract(workspace, resolved_scenario, benchmark_key, benchmark_manifest)
    write_yaml_file(draft_contract_path, draft_contract)

    readiness_report = _build_readiness_report(
        workspace=workspace,
        scenario=resolved_scenario,
        metric_profile=metric_profile,
        draft_contract_path=draft_contract_path,
        benchmark_key=benchmark_key,
        benchmark_manifest=benchmark_manifest,
    )
    readiness_report_path.write_text(
        json.dumps(readiness_report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return AdvisorResult(
        draft_contract_path=draft_contract_path,
        readiness_report_path=readiness_report_path,
        readiness_report=readiness_report,
    )
