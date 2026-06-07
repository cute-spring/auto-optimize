from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

import yaml

from auto_optimize.shared.paths import resolve_workspace_relative
from auto_optimize.shared.schemas import OptimizationContract


TOP_LEVEL_DEFAULT_SECTIONS = {
    "decision_policy": "Defaults were applied because `decision_policy` was omitted.",
    "pareto": "Defaults were applied because `pareto` was omitted.",
    "run_policy": "Defaults were applied because `run_policy` was omitted.",
    "version_control": "Defaults were applied because `version_control` was omitted.",
    "report": "Defaults were applied because `report` was omitted.",
}


def load_raw_contract_data(contract_path: str | Path) -> dict[str, Any]:
    resolved_path = Path(contract_path).resolve()
    with resolved_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _stringify_value(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value)


def _collect_defaults(raw_data: dict[str, Any], contract: OptimizationContract) -> list[str]:
    defaults: list[str] = []

    for section_name, description in TOP_LEVEL_DEFAULT_SECTIONS.items():
        if section_name not in raw_data:
            defaults.append(description)

    evaluation_defaults: list[str] = []
    raw_evaluation = raw_data.get("evaluation", {})
    if "output_format" not in raw_evaluation:
        evaluation_defaults.append("`evaluation.output_format=json`")
    if "timeout_seconds" not in raw_evaluation:
        evaluation_defaults.append(f"`evaluation.timeout_seconds={contract.evaluation.timeout_seconds}`")
    if evaluation_defaults:
        defaults.append("Evaluation defaults: " + ", ".join(evaluation_defaults))

    protected_defaults = [
        entry for entry in contract.protected_scope if entry not in raw_data.get("protected_scope", [])
    ]
    if protected_defaults:
        defaults.append("Protected scope defaults added: " + ", ".join(f"`{entry}`" for entry in protected_defaults))

    raw_run_policy = raw_data.get("run_policy", {})
    run_policy_defaults: list[str] = []
    for field_name in (
        "max_experiments",
        "stop_if_no_improvement_rounds",
        "search_strategy",
        "max_pairwise_candidates",
        "random_seed",
        "dry_run",
        "max_failed_evaluations",
    ):
        if "run_policy" not in raw_data or field_name not in raw_run_policy:
            run_policy_defaults.append(f"`run_policy.{field_name}={getattr(contract.run_policy, field_name)}`")
    if run_policy_defaults:
        defaults.append("Run policy defaults: " + ", ".join(run_policy_defaults))

    raw_report = raw_data.get("report", {})
    report_defaults: list[str] = []
    if "formats" not in raw_report:
        report_defaults.append("`report.formats=markdown`")
    if "output_dir" not in raw_report:
        report_defaults.append(f"`report.output_dir={contract.report.output_dir}`")
    if report_defaults:
        defaults.append("Report defaults: " + ", ".join(report_defaults))

    return defaults


def explain_contract_markdown(contract: OptimizationContract, raw_data: dict[str, Any]) -> str:
    resolved_workspace = contract.workspace_path or resolve_workspace_relative(contract.contract_dir, contract.workspace.path)
    lines = [
        "# Contract Explanation",
        "",
        "## Overview",
        "",
        f"- Contract: `{contract.contract_path}`",
        f"- Scenario type: `{contract.scenario.type}`",
        f"- Scenario name: `{contract.scenario.name or '(not set)'}`",
        f"- Workspace path: `{contract.workspace.path}`",
        f"- Resolved workspace: `{resolved_workspace}`",
        f"- Evaluation command: `{contract.evaluation.command}`",
        "",
        "## Why These Sections Matter",
        "",
        "- `workspace`: tells AutoOptimize which directory to treat as the optimization target.",
        "- `editable_scope`: lists the files AutoOptimize is allowed to modify.",
        "- `protected_scope`: lists files or directories AutoOptimize must never edit.",
        "- `search_space`: defines which parameters can change, where they live, and which values are allowed.",
        "- `metrics`: tells AutoOptimize how to score results and what counts as improvement.",
        "",
        "## Editable Scope",
        "",
    ]

    if contract.editable_scope:
        for entry in contract.editable_scope:
            lines.append(f"- `{entry}`")
    else:
        lines.append("- No editable files are declared.")

    lines.extend(["", "## Protected Scope", ""])
    for entry in contract.protected_scope:
        lines.append(f"- `{entry}`")

    lines.extend(["", "## Search Parameters", ""])
    if not contract.search_space:
        lines.append("- No search parameters are declared.")
    else:
        for name, parameter in contract.search_space.items():
            sample_values = ", ".join(repr(value) for value in parameter.values[:4])
            value_suffix = "" if len(parameter.values) <= 4 else ", ..."
            lines.append(
                f"- `{name}` -> `{parameter.mapping.file}` at `{parameter.mapping.path}` "
                f"with {len(parameter.values)} value(s): {sample_values}{value_suffix}"
            )

    lines.extend(["", "## Metrics", ""])
    lines.append(f"- Primary: `{contract.metrics.primary.name}` ({contract.metrics.primary.direction})")
    if contract.metrics.secondary:
        for metric in contract.metrics.secondary:
            lines.append(f"- Secondary: `{metric.name}` ({metric.direction})")
    else:
        lines.append("- No secondary metrics declared.")

    lines.extend(["", "## Constraints", ""])
    if contract.constraints:
        for metric_name, rule in contract.constraints.items():
            lines.append(f"- `{metric_name}`: `{_stringify_value(rule)}`")
    else:
        lines.append("- No explicit constraints declared.")

    lines.extend(["", "## Defaults Applied", ""])
    applied_defaults = _collect_defaults(raw_data, contract)
    if applied_defaults:
        for entry in applied_defaults:
            lines.append(f"- {entry}")
    else:
        lines.append("- No implicit defaults were detected; the contract already declares the relevant sections.")

    lines.extend(
        [
            "",
            "## Next Step",
            "",
            f"- Validate this contract: `python -m auto_optimize.cli validate {contract.contract_path}`",
            "- Review the validation report before running optimization.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_contract_explanation(
    contract: OptimizationContract,
    raw_data: dict[str, Any],
    output_path: str | Path | None = None,
) -> Path:
    if output_path is None:
        target_path = resolve_workspace_relative(contract.workspace_path, contract.report.output_dir) / "contract_explanation.md"
    else:
        target_path = Path(output_path).resolve()

    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(explain_contract_markdown(contract, raw_data), encoding="utf-8")
    return target_path


def expanded_contract_data(contract: OptimizationContract) -> dict[str, Any]:
    payload = asdict(contract)
    payload.pop("contract_path", None)
    payload.pop("contract_dir", None)
    payload.pop("workspace_path", None)
    return payload
