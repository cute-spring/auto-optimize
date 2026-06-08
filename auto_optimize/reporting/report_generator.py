from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any


def _metric_delta(direction: str, baseline: Any, best: Any) -> float | None:
    if not isinstance(baseline, (int, float)) or not isinstance(best, (int, float)):
        return None
    if direction == "maximize":
        return best - baseline
    if direction == "minimize":
        return baseline - best
    return None


def _format_delta(delta: float | None) -> str:
    if delta is None:
        return "n/a"
    return f"{delta:+.6f}"


def generate_markdown_report(summary: dict[str, Any], baseline_metrics: dict[str, Any]) -> str:
    primary_name = summary["primary_metric"]["name"]
    primary_direction = summary["primary_metric"]["direction"]
    primary_baseline = summary["baseline_metrics"][primary_name]
    primary_best = summary["best_metrics"][primary_name]
    primary_delta = _metric_delta(primary_direction, primary_baseline, primary_best)

    lines = [
        "# Optimization Report",
        "",
        "## Executive Summary",
        "",
        f"- Scenario: `{summary['scenario_type']}`",
        f"- Mode: `{summary['mode']}`",
        f"- Status: `{summary['status']}`",
        f"- Experiments run: `{summary['experiments_run']}`",
        f"- Accepted experiments: `{summary.get('accepted_experiments', 0)}`",
        f"- Rejected experiments: `{summary.get('rejected_experiments', 0)}`",
        f"- Failed evaluations: `{summary.get('failed_evaluations', 0)}`",
        f"- Constraints satisfied: `{summary['constraints_satisfied']}`",
        f"- Primary metric: `{primary_name}` ({primary_direction})",
        f"- Baseline primary metric: `{primary_baseline}`",
        f"- Best primary metric: `{primary_best}`",
        f"- Primary metric delta: `{_format_delta(primary_delta)}`",
        "",
        "## Baseline Metrics",
        "",
    ]
    for key, value in sorted(baseline_metrics.items()):
        lines.append(f"- `{key}`: `{value}`")

    if summary.get("best_metrics"):
        lines.extend(["", "## Best Metrics", ""])
        for key, value in sorted(summary["best_metrics"].items()):
            lines.append(f"- `{key}`: `{value}`")

    final_workspace_metrics = summary.get("final_workspace_metrics")
    if final_workspace_metrics:
        lines.extend(["", "## Final Workspace Metrics", ""])
        for key, value in sorted(final_workspace_metrics.items()):
            lines.append(f"- `{key}`: `{value}`")

    lines.extend(["", "## Baseline vs Best", ""])
    for key, best_value in sorted(summary["best_metrics"].items()):
        baseline_value = summary["baseline_metrics"].get(key)
        direction = "maximize"
        if key == primary_name:
            direction = primary_direction
        delta = _metric_delta(direction, baseline_value, best_value)
        lines.append(
            f"- `{key}`: baseline `{baseline_value}` -> best `{best_value}` (delta `{_format_delta(delta)}`)"
        )

    accepted_candidates = summary.get("accepted_candidates", [])
    lines.extend(["", "## Accepted Experiments", ""])
    if not accepted_candidates:
        lines.append("- No accepted candidates in this run.")
    else:
        for candidate in accepted_candidates:
            candidate_label = candidate.get("parameter") or ", ".join(candidate.get("parameters", []))
            candidate_value = candidate.get("value", candidate.get("candidate"))
            lines.append(
                "- "
                f"`{candidate['experiment_id']}` changed `{candidate_label}` to `{candidate_value}` "
                f"and moved `{primary_name}` from `{candidate['primary_metric_before']}` to "
                f"`{candidate['primary_metric_after']}` (delta `{_format_delta(candidate['primary_metric_improvement'])}`)."
            )

    generated_adapters = summary.get("generated_adapters", [])
    asset_context = summary.get("asset_context", {})
    adapter_provenance = summary.get("adapter_provenance", [])
    risk_flags = summary.get("risk_flags", [])
    decision_rationale_summary = summary.get("decision_rationale_summary", {})
    declaration_input = asset_context.get("declaration_input", {})
    generated_contract = asset_context.get("generated_contract", {})
    generated_adapter_assets = asset_context.get("generated_adapters", {})

    lines.extend(["", "## Asset Provenance", ""])
    if declaration_input.get("present"):
        lines.append(f"- Declaration input: `{declaration_input.get('path')}`")
    else:
        lines.append("- Declaration input: `none recorded for this run`")
    if generated_contract.get("present"):
        lines.append(f"- Generated contract: `{generated_contract.get('path')}`")
        lines.append(f"- Generated contract scenario: `{generated_contract.get('scenario_type')}`")
        if generated_contract.get("execution_mode"):
            lines.append(f"- Execution mode: `{generated_contract.get('execution_mode')}`")
    else:
        lines.append("- Generated contract: `none recorded`")
    lines.append(f"- Generated adapters count: `{generated_adapter_assets.get('count', 0)}`")
    for path in generated_adapter_assets.get("paths", []):
        lines.append(f"- Generated adapter artifact: `{path}`")

    lines.extend(["", "## Generated Adapters", ""])
    if not generated_adapters:
        lines.append("- No generated adapters were used in this run.")
    else:
        for adapter in generated_adapters:
            lines.append(
                "- "
                f"`{adapter['kind']}` via `{adapter['template']}` generated `{adapter['generated_path']}` "
                f"for `{adapter['purpose']}` with risk flags `{adapter['risk_flags']}`."
            )
            if adapter.get("failure_mode"):
                lines.append(f"- Failure mode: {adapter['failure_mode']}")
            if adapter.get("remediation_hint"):
                lines.append(f"- Remediation: {adapter['remediation_hint']}")

    lines.extend(["", "## Adapter Provenance", ""])
    if not adapter_provenance:
        lines.append("- No adapter provenance records were produced in this run.")
    else:
        for adapter in adapter_provenance:
            lines.append(
                "- "
                f"`{adapter['kind']}` via `{adapter['template']}` came from "
                f"`{adapter['declaration_source'] or 'no declaration source recorded'}` "
                f"and wrote `{adapter['generated_path']}` under `{adapter['output_dir']}`."
            )
            lines.append(
                "- "
                f"Execution phase `{adapter.get('execution_phase')}` expects `{adapter.get('expected_input')}`."
            )
            lines.append(
                "- "
                f"Failure mode: {adapter.get('failure_mode')} Remediation: {adapter.get('remediation_hint')}"
            )
            trigger = adapter.get("trigger", {})
            lines.append(
                "- "
                f"Trigger: metrics_source `{trigger.get('metrics_source')}`, "
                f"parser_template `{trigger.get('parser_template')}`, "
                f"evaluation adapter `{trigger.get('evaluation_adapter_kind')}` / `{trigger.get('evaluation_adapter_template')}`."
            )

    lines.extend(["", "## Risk Flags", ""])
    if not risk_flags:
        lines.append("- No explicit risk flags were recorded in this run.")
    else:
        for entry in risk_flags:
            lines.append(
                f"- `{entry['flag']}` from `{entry['source']}`: {entry['reason']}"
            )

    lines.extend(["", "## Decision Rationale Summary", ""])
    if not decision_rationale_summary:
        lines.append("- No decision rationale summary was recorded in this run.")
    else:
        lines.append(
            f"- Accepted reason variants: `{decision_rationale_summary.get('accepted_reason_count', 0)}`"
        )
        lines.append(
            f"- Rejected reason variants: `{decision_rationale_summary.get('rejected_reason_count', 0)}`"
        )
        lines.append(
            f"- Failed evaluation rejections: `{decision_rationale_summary.get('failed_evaluation_count', 0)}`"
        )
        lines.append(
            f"- Constraint violation rejections: `{decision_rationale_summary.get('constraint_violation_count', 0)}`"
        )
        lines.append(
            f"- Below-threshold rejections: `{decision_rationale_summary.get('below_threshold_count', 0)}`"
        )
        lines.append(
            f"- Non-improving rejections: `{decision_rationale_summary.get('non_improving_primary_metric_count', 0)}`"
        )
        lines.append(
            f"- Pareto accepts: `{decision_rationale_summary.get('pareto_accept_count', 0)}`"
        )
        lines.append(
            f"- Pareto rejects: `{decision_rationale_summary.get('pareto_reject_count', 0)}`"
        )

        top_accept_reasons = decision_rationale_summary.get("top_accept_reasons", [])
        if top_accept_reasons:
            lines.append("- Top accept reasons:")
            for entry in top_accept_reasons:
                lines.append(f"  - `{entry['reason']}` x `{entry['count']}`")

        top_reject_reasons = decision_rationale_summary.get("top_reject_reasons", [])
        if top_reject_reasons:
            lines.append("- Top reject reasons:")
            for entry in top_reject_reasons:
                lines.append(f"  - `{entry['reason']}` x `{entry['count']}`")

    benchmark_context = summary.get("benchmark_context")
    if benchmark_context:
        lines.extend(["", "## Benchmark Context", ""])
        for key in (
            "dataset_key",
            "scenario_family",
            "data_source",
            "dataset_available_locally",
            "source_root",
            "provider_mode",
            "provider_model_name",
        ):
            lines.append(f"- `{key}`: `{benchmark_context.get(key)}`")

    pareto_frontier = summary.get("pareto_frontier", [])
    if summary.get("pareto_enabled"):
        lines.extend(["", "## Pareto Frontier", ""])
        lines.append(f"- Enabled: `{summary.get('pareto_enabled')}`")
        lines.append(f"- Profiles: `{summary.get('pareto_profiles', [])}`")
        lines.append(f"- Frontier points: `{len(pareto_frontier)}`")
        for entry in pareto_frontier:
            lines.append(
                "- "
                f"`{entry['experiment_id']}` decision `{entry['decision']}` "
                f"candidate `{entry['candidate']}` "
                f"primary `{entry['metrics'].get(primary_name)}`"
            )

    memory = summary.get("memory")
    if memory:
        lines.extend(["", "## Experiment Memory", ""])
        lines.append(f"- Historical runs recorded: `{memory['total_runs']}`")
        lines.append(f"- Current run is historical best: `{memory['current_run_is_historical_best']}`")
        lines.append(f"- Historical best timestamp: `{memory['best_run_timestamp']}`")
        lines.append(f"- Historical best primary metric: `{memory['best_primary_metric']}`")
        lines.append(f"- Historical best improvement: `{memory['best_primary_improvement']}`")

    lines.extend(
        [
            "",
            "## Notes",
            "",
            f"- This MVP run evaluates the baseline, applies the `{summary.get('search_strategy', 'one_variable')}` candidate strategy, records decisions, and updates experiment memory.",
            "- Rejected candidates are rolled back with file snapshots. Accepted candidates may also be committed through the Git layer when enabled.",
            "",
            "## Output Artifacts",
            "",
        ]
    )
    for label, path in summary["artifacts"].items():
        lines.append(f"- `{label}`: `{path}`")
    lines.append("")
    return "\n".join(lines)


def generate_html_report(markdown_report: str) -> str:
    escaped = html.escape(markdown_report)
    return (
        "<html><head><meta charset='utf-8'><title>Optimization Report</title></head>"
        "<body><pre>"
        f"{escaped}"
        "</pre></body></html>"
    )


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    lines = [json.dumps(record, ensure_ascii=False) for record in records]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_csv(path: Path, records: list[dict[str, Any]]) -> None:
    if not records:
        path.write_text("", encoding="utf-8")
        return

    ordered_keys: list[str] = []
    for record in records:
        for key in record:
            if key not in ordered_keys:
                ordered_keys.append(key)

    rows = [",".join(ordered_keys)]
    for record in records:
        row = []
        for key in ordered_keys:
            value = record.get(key, "")
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False)
            cell = str(value).replace('"', '""')
            row.append(f'"{cell}"')
        rows.append(",".join(row))
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def load_summary_for_report(target: Path) -> tuple[dict[str, Any], Path]:
    if target.is_dir():
        summary_path = target / "run_summary.json"
    elif target.name == "run_summary.json":
        summary_path = target
    else:
        summary_path = target.parent / "run_summary.json"

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    return summary, summary_path.parent
