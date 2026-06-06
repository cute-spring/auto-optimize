from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from auto_optimize.contract.validator import validate_contract, write_validation_report
from auto_optimize.memory.store import update_memory_store
from auto_optimize.reporting.report_generator import (
    generate_html_report,
    generate_markdown_report,
    write_csv,
    write_jsonl,
)
from auto_optimize.runner.decision import constraints_satisfied, decide_candidate, evaluate_constraints
from auto_optimize.runner.evaluator import EvaluationExecutionError, execute_evaluation
from auto_optimize.runner.modifier import apply_parameter_value
from auto_optimize.runner.planner import generate_one_variable_candidates
from auto_optimize.runner.rollback import rollback_change
from auto_optimize.shared.git import GitOperationError, GitRunContext, commit_files, create_branch, generate_branch_name, inspect_git_repo
from auto_optimize.shared.paths import resolve_workspace_relative
from auto_optimize.shared.schemas import OptimizationContract


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _baseline_log_entry(contract: OptimizationContract, metrics: dict[str, Any], git_state: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "experiment_id": "baseline",
        "timestamp": _timestamp(),
        "scenario_type": contract.scenario.type,
        "hypothesis": "Baseline evaluation before optimization.",
        "candidate": {},
        "changes": [],
        "metrics_before": {},
        "metrics_after": metrics,
        "decision": "baseline",
        "reason": "Baseline evaluation before candidate loop.",
        "constraints_satisfied": constraints_satisfied(contract.constraints, metrics),
        "rollback_performed": False,
        "git": git_state or {"enabled": False},
        "tags": ["baseline", "mvp"],
    }


def _candidate_log_entry(
    contract: OptimizationContract,
    experiment_id: str,
    parameter: str,
    candidate_value: Any,
    change: dict[str, Any],
    metrics_before: dict[str, Any],
    metrics_after: dict[str, Any],
    decision: str,
    reason: str,
    rollback_performed: bool,
    git_state: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "experiment_id": experiment_id,
        "timestamp": _timestamp(),
        "scenario_type": contract.scenario.type,
        "hypothesis": f"Changing {parameter} may improve the primary metric.",
        "candidate": {parameter: candidate_value},
        "changes": [change],
        "metrics_before": metrics_before,
        "metrics_after": metrics_after,
        "decision": decision,
        "reason": reason,
        "constraints_satisfied": constraints_satisfied(contract.constraints, metrics_after),
        "rollback_performed": rollback_performed,
        "git": git_state or {"enabled": False},
        "tags": [parameter, decision],
    }


def _prepare_git_run(contract: OptimizationContract, initial_git_state: dict[str, Any] | None) -> GitRunContext:
    if not contract.version_control.enabled:
        return GitRunContext(enabled=False, initial_state=initial_git_state, commits=[])

    current_state = inspect_git_repo(contract.workspace_path).as_dict()
    context = GitRunContext(
        enabled=True,
        initial_state=initial_git_state or current_state,
        working_branch=current_state.get("branch"),
        commits=[],
    )
    if not contract.version_control.create_branch:
        return context

    label = contract.scenario.name or contract.scenario.type
    branch_name = generate_branch_name(contract.version_control.branch_prefix, label)
    context.working_branch = create_branch(contract.workspace_path, branch_name)
    context.branch_created = True
    return context


def _build_commit_message(
    contract: OptimizationContract,
    experiment_id: str,
    parameter: str,
    candidate_value: Any,
    previous_metrics: dict[str, Any],
    candidate_metrics: dict[str, Any],
) -> str:
    primary_metric = contract.metrics.primary.name
    before = previous_metrics[primary_metric]
    after = candidate_metrics[primary_metric]
    summary = f"{parameter}={candidate_value} ({primary_metric} {before} -> {after})"
    template = contract.version_control.commit_message_template or "auto-optimize: {experiment_id} {summary}"
    return template.format(
        experiment_id=experiment_id,
        parameter=parameter,
        candidate_value=candidate_value,
        metric_name=primary_metric,
        metric_before=before,
        metric_after=after,
        summary=summary,
    ).strip()


def run_contract(contract: OptimizationContract) -> dict[str, Any]:
    validation_result = validate_contract(contract)
    validation_report_path = write_validation_report(contract, validation_result)
    if not validation_result.valid or validation_result.baseline_metrics is None:
        messages = [f"[{issue.severity}] {issue.code}: {issue.message}" for issue in validation_result.issues]
        raise RuntimeError("Contract validation failed before run:\n" + "\n".join(messages))

    git_context = _prepare_git_run(contract, validation_result.git_state)

    output_dir = resolve_workspace_relative(contract.workspace_path, contract.report.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    baseline_metrics = validation_result.baseline_metrics
    current_best_metrics = dict(baseline_metrics)
    constraint_checks = evaluate_constraints(contract.constraints, baseline_metrics)
    records = [_baseline_log_entry(contract, baseline_metrics, git_context.as_dict())]

    candidates = generate_one_variable_candidates(contract)
    max_experiments = contract.run_policy.max_experiments
    no_improvement_rounds = 0
    accepted_experiments = 0
    rejected_experiments = 0
    failed_evaluations = 0
    accepted_candidates: list[dict[str, Any]] = []

    for index, candidate in enumerate(candidates[:max_experiments], start=1):
        previous_best_metrics = dict(current_best_metrics)
        change, snapshot = apply_parameter_value(contract, candidate.parameter, candidate.mapping, candidate.value)
        rollback_performed = False

        try:
            candidate_metrics = execute_evaluation(contract)
        except EvaluationExecutionError as exc:
            rollback_change(contract, snapshot)
            rollback_performed = True
            failed_evaluations += 1
            rejected_experiments += 1
            no_improvement_rounds += 1

            reason = exc.message if exc.hint is None else f"{exc.message} Hint: {exc.hint}"
            records.append(
                _candidate_log_entry(
                    contract=contract,
                    experiment_id=f"exp_{index:04d}",
                    parameter=candidate.parameter,
                    candidate_value=candidate.value,
                    change=asdict(change),
                    metrics_before=previous_best_metrics,
                    metrics_after={},
                    decision="rejected",
                    reason=reason,
                    rollback_performed=rollback_performed,
                    git_state=validation_result.git_state,
                )
            )

            if failed_evaluations >= contract.run_policy.max_failed_evaluations:
                break
            if no_improvement_rounds >= contract.run_policy.stop_if_no_improvement_rounds:
                break
            continue

        decision, reason = decide_candidate(contract, baseline_metrics, current_best_metrics, candidate_metrics)

        if decision == "accepted":
            if contract.version_control.enabled and contract.version_control.commit_accepted_changes:
                experiment_id = f"exp_{index:04d}"
                try:
                    commit_head = commit_files(
                        contract.workspace_path,
                        [change.file],
                        _build_commit_message(
                            contract=contract,
                            experiment_id=experiment_id,
                            parameter=candidate.parameter,
                            candidate_value=candidate.value,
                            previous_metrics=previous_best_metrics,
                            candidate_metrics=candidate_metrics,
                        ),
                    )
                except GitOperationError as exc:
                    rollback_change(contract, snapshot)
                    raise RuntimeError(
                        exc.message if exc.hint is None else f"{exc.message}\n{exc.hint}"
                    ) from exc
                git_context.commits.append(commit_head)

            current_best_metrics = dict(candidate_metrics)
            accepted_experiments += 1
            no_improvement_rounds = 0
            accepted_candidates.append(
                {
                    "experiment_id": f"exp_{index:04d}",
                    "parameter": candidate.parameter,
                    "value": candidate.value,
                    "primary_metric_before": previous_best_metrics[contract.metrics.primary.name],
                    "primary_metric_after": candidate_metrics[contract.metrics.primary.name],
                    "primary_metric_improvement": (
                        candidate_metrics[contract.metrics.primary.name]
                        - previous_best_metrics[contract.metrics.primary.name]
                        if contract.metrics.primary.direction == "maximize"
                        else previous_best_metrics[contract.metrics.primary.name]
                        - candidate_metrics[contract.metrics.primary.name]
                    ),
                    "change": asdict(change),
                }
            )
        else:
            rollback_change(contract, snapshot)
            rollback_performed = True
            rejected_experiments += 1
            no_improvement_rounds += 1

        candidate_git_state = git_context.as_dict()
        if contract.version_control.enabled:
            candidate_git_state["repo_state"] = inspect_git_repo(contract.workspace_path).as_dict()

        records.append(
            _candidate_log_entry(
                contract=contract,
                experiment_id=f"exp_{index:04d}",
                parameter=candidate.parameter,
                candidate_value=candidate.value,
                change=asdict(change),
                metrics_before=previous_best_metrics,
                metrics_after=candidate_metrics,
                decision=decision,
                reason=reason,
                rollback_performed=rollback_performed,
                git_state=candidate_git_state,
            )
        )

        if no_improvement_rounds >= contract.run_policy.stop_if_no_improvement_rounds:
            break

    experiment_log_path = output_dir / "experiment_log.jsonl"
    experiment_csv_path = output_dir / "experiment_log.csv"
    run_summary_path = output_dir / "run_summary.json"
    report_md_path = output_dir / "optimization_report.md"
    report_html_path = output_dir / "optimization_report.html"

    artifact_map = {
        "validation_report": str(validation_report_path),
        "experiment_log_jsonl": str(experiment_log_path),
        "experiment_log_csv": str(experiment_csv_path),
        "run_summary": str(run_summary_path),
        "optimization_report_md": str(report_md_path),
    }
    if "html" in contract.report.formats:
        artifact_map["optimization_report_html"] = str(report_html_path)

    summary = {
        "status": "completed",
        "mode": "run",
        "scenario_type": contract.scenario.type,
        "scenario_name": contract.scenario.name,
        "contract_path": str(contract.contract_path),
        "workspace_path": str(contract.workspace_path),
        "timestamp": _timestamp(),
        "experiments_run": len(records) - 1,
        "accepted_experiments": accepted_experiments,
        "rejected_experiments": rejected_experiments,
        "failed_evaluations": failed_evaluations,
        "baseline_metrics": baseline_metrics,
        "best_metrics": current_best_metrics,
        "primary_metric": {
            "name": contract.metrics.primary.name,
            "direction": contract.metrics.primary.direction,
        },
        "accepted_candidates": accepted_candidates,
        "constraints_satisfied": all(check.passed for check in constraint_checks),
        "constraint_checks": [asdict(check) for check in constraint_checks],
        "git": (
            {
                **git_context.as_dict(),
                "final_state": inspect_git_repo(contract.workspace_path).as_dict(),
            }
            if contract.version_control.enabled
            else {"enabled": False}
        ),
        "artifacts": artifact_map,
        "notes": [
            "This MVP run executes one-variable-at-a-time candidate changes.",
            "Rejected candidates are restored from file snapshots in this phase.",
            "When version_control is enabled, this MVP can branch and commit accepted changes, but still uses file-snapshot rollback for rejected candidates.",
        ],
    }

    memory_snapshot = update_memory_store(output_dir, summary, contract.metrics.primary)
    artifact_map["run_history_jsonl"] = str(memory_snapshot.history_path)
    artifact_map["best_run_snapshot"] = str(memory_snapshot.best_run_path)
    summary["memory"] = memory_snapshot.as_dict()

    write_jsonl(experiment_log_path, records)
    write_csv(experiment_csv_path, records)
    run_summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    markdown_report = generate_markdown_report(summary, baseline_metrics)
    report_md_path.write_text(markdown_report, encoding="utf-8")
    if "html" in contract.report.formats:
        report_html_path.write_text(generate_html_report(markdown_report), encoding="utf-8")

    return summary
