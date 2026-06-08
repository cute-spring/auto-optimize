from __future__ import annotations

import json
import shutil
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from auto_optimize.contract.validator import validate_contract, write_validation_report
from auto_optimize.memory.store import update_memory_store
from auto_optimize.reporting.report_generator import (
    generate_html_report,
    generate_markdown_report,
    write_csv,
    write_jsonl,
)
from auto_optimize.runner.decision import (
    constraints_satisfied,
    decide_candidate,
    dominates,
    evaluate_constraints,
    is_non_dominated,
    tracked_metric_definitions,
)
from auto_optimize.runner.evaluator import EvaluationExecutionError, execute_evaluation_with_details
from auto_optimize.runner.modifier import apply_candidate_changes
from auto_optimize.runner.planner import Candidate, generate_candidates
from auto_optimize.runner.rollback import rollback_change
from auto_optimize.shared.git import (
    GitOperationError,
    GitRunContext,
    commit_files,
    create_branch,
    create_pull_request,
    generate_branch_name,
    inspect_git_repo,
    push_branch,
)
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


def _pareto_entry(
    experiment_id: str,
    decision: str,
    metrics: dict[str, Any],
    candidate: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    return {
        "experiment_id": experiment_id,
        "decision": decision,
        "candidate": candidate,
        "metrics": metrics,
        "reason": reason,
    }


def _update_pareto_frontier(
    frontier: list[dict[str, Any]],
    entry: dict[str, Any],
    metric_definitions: list[Any],
) -> list[dict[str, Any]]:
    candidate_metrics = entry["metrics"]
    if any(dominates(existing["metrics"], candidate_metrics, metric_definitions) for existing in frontier):
        return frontier

    survivors = [
        existing
        for existing in frontier
        if not dominates(candidate_metrics, existing["metrics"], metric_definitions)
    ]
    survivors.append(entry)
    return survivors


def _capture_editable_file_snapshot(contract: OptimizationContract) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    for relative_path in contract.editable_scope:
        if relative_path.startswith("env:"):
            continue
        target_path = resolve_workspace_relative(contract.workspace_path, relative_path)
        if target_path.exists() and target_path.is_file():
            snapshot[relative_path] = target_path.read_text(encoding="utf-8")
    return snapshot


def _persist_pareto_snapshots(
    frontier: list[dict[str, Any]],
    snapshot_store: dict[str, dict[str, Any]],
    snapshot_dir: Path,
) -> None:
    if snapshot_dir.exists():
        shutil.rmtree(snapshot_dir)
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    frontier_ids = {entry["experiment_id"] for entry in frontier}
    for entry in frontier:
        snapshot_payload = snapshot_store.get(entry["experiment_id"])
        if snapshot_payload is None:
            continue

        point_dir = snapshot_dir / entry["experiment_id"]
        point_dir.mkdir(parents=True, exist_ok=True)
        (point_dir / "metadata.json").write_text(
            json.dumps(
                {
                    "experiment_id": entry["experiment_id"],
                    "decision": entry["decision"],
                    "candidate": entry["candidate"],
                    "metrics": entry["metrics"],
                    "reason": entry["reason"],
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

        for relative_path, content in snapshot_payload["editable_files"].items():
            target_path = point_dir / relative_path
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(content, encoding="utf-8")


def _candidate_log_entry(
    contract: OptimizationContract,
    experiment_id: str,
    candidate: Candidate,
    changes: list[dict[str, Any]],
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
        "hypothesis": f"Changing {candidate.parameter} may improve the primary metric.",
        "candidate": candidate.candidate_values,
        "parameters": candidate.parameters,
        "changes": changes,
        "metrics_before": metrics_before,
        "metrics_after": metrics_after,
        "decision": decision,
        "reason": reason,
        "constraints_satisfied": constraints_satisfied(contract.constraints, metrics_after),
        "rollback_performed": rollback_performed,
        "git": git_state or {"enabled": False},
        "tags": [*candidate.parameters, decision],
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
    candidate: Candidate,
    previous_metrics: dict[str, Any],
    candidate_metrics: dict[str, Any],
) -> str:
    primary_metric = contract.metrics.primary.name
    before = previous_metrics[primary_metric]
    after = candidate_metrics[primary_metric]
    summary = f"{candidate.parameter}={candidate.value} ({primary_metric} {before} -> {after})"
    template = contract.version_control.commit_message_template or "auto-optimize: {experiment_id} {summary}"
    return template.format(
        experiment_id=experiment_id,
        parameter=candidate.parameter,
        candidate_value=candidate.value,
        metric_name=primary_metric,
        metric_before=before,
        metric_after=after,
        summary=summary,
    ).strip()


def _load_workspace_benchmark_context(workspace_path: Path) -> dict[str, Any] | None:
    manifest_path = workspace_path / "data" / "benchmark_manifest.json"
    if not manifest_path.exists():
        return None

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    provider_path = workspace_path / "configs" / "provider.yaml"
    provider_mode = None
    provider_model_name = None
    if provider_path.exists():
        provider_payload = yaml.safe_load(provider_path.read_text(encoding="utf-8")) or {}
        provider = provider_payload.get("provider", {})
        provider_mode = provider.get("mode")
        provider_model_name = provider.get("model_name")

    return {
        "dataset_key": manifest.get("dataset_key"),
        "scenario_family": manifest.get("scenario_family"),
        "data_source": manifest.get("data_source"),
        "dataset_available_locally": manifest.get("dataset_available_locally"),
        "source_root": manifest.get("source_root"),
        "provider_mode": provider_mode,
        "provider_model_name": provider_model_name,
    }


def _build_asset_context(
    contract: OptimizationContract,
    generated_adapters: list[dict[str, Any]],
    execution_mode: str,
) -> dict[str, Any]:
    raw_contract = yaml.safe_load(contract.contract_path.read_text(encoding="utf-8")) or {}
    declaration_context = raw_contract.get("declaration_context", {})
    source_declaration = declaration_context.get("source_declaration")

    return {
        "declaration_input": {
            "path": source_declaration,
            "present": bool(source_declaration),
        },
        "generated_contract": {
            "path": str(contract.contract_path),
            "present": True,
            "scenario_type": contract.scenario.type,
            "execution_mode": execution_mode,
        },
        "generated_adapters": {
            "count": len(generated_adapters),
            "paths": [adapter["generated_path"] for adapter in generated_adapters],
        },
    }


def _build_adapter_provenance(contract: OptimizationContract, generated_adapters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    raw_contract = yaml.safe_load(contract.contract_path.read_text(encoding="utf-8")) or {}
    declaration_context = raw_contract.get("declaration_context", {})
    declaration_evaluation = declaration_context.get("evaluation", {})
    evaluation_adapter = raw_contract.get("evaluation", {}).get("adapter", {})

    provenance: list[dict[str, Any]] = []
    for adapter in generated_adapters:
        generated_path = adapter.get("generated_path")
        output_dir = None
        if isinstance(generated_path, str) and generated_path:
            output_dir = str(Path(generated_path).parent)

        provenance.append(
            {
                "kind": adapter.get("kind"),
                "template": adapter.get("template"),
                "generated_path": generated_path,
                "output_dir": output_dir or evaluation_adapter.get("output_dir"),
                "purpose": adapter.get("purpose"),
                "declaration_source": adapter.get("declaration_source"),
                "risk_flags": list(adapter.get("risk_flags", [])),
                "execution_phase": adapter.get("execution_phase"),
                "expected_input": adapter.get("expected_input"),
                "failure_mode": adapter.get("failure_mode"),
                "remediation_hint": adapter.get("remediation_hint"),
                "trigger": {
                    "evaluation_adapter_kind": evaluation_adapter.get("kind"),
                    "evaluation_adapter_template": evaluation_adapter.get("template"),
                    "metrics_source": declaration_evaluation.get("metrics_source"),
                    "parser_template": declaration_evaluation.get("parser_template"),
                },
            }
        )
    return provenance


def _build_risk_flags(
    contract: OptimizationContract,
    generated_adapters: list[dict[str, Any]],
    adapter_provenance: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    raw_contract = yaml.safe_load(contract.contract_path.read_text(encoding="utf-8")) or {}
    builder_context = raw_contract.get("builder_context", {})
    reference_fixture_context = builder_context.get("reference_fixture_context")

    risk_reason_map = {
        "generated_code": "This run generated executable helper code during evaluation.",
        "metrics_parsing": "This run depends on generated parsing logic to convert raw output into metrics.",
    }

    risk_flags: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    if generated_adapters:
        key = ("external_eval_command", "evaluation.command")
        seen.add(key)
        risk_flags.append(
            {
                "flag": "external_eval_command",
                "source": "evaluation.command",
                "reason": "This run executes a workspace evaluation command and trusts its output contract.",
            }
        )

    if reference_fixture_context:
        key = ("reference_fixture_context", "builder_context.reference_fixture_context")
        seen.add(key)
        risk_flags.append(
            {
                "flag": "reference_fixture_context",
                "source": "builder_context.reference_fixture_context",
                "reason": "This run uses scenario/template assets as reference fixtures rather than user-authored declarations alone.",
            }
        )

    for entry in adapter_provenance:
        source = entry.get("generated_path") or entry.get("kind") or "generated_adapter"
        for flag in entry.get("risk_flags", []):
            key = (str(flag), str(source))
            if key in seen:
                continue
            seen.add(key)
            risk_flags.append(
                {
                    "flag": flag,
                    "source": source,
                    "reason": risk_reason_map.get(
                        str(flag),
                        f"This run reported risk flag `{flag}` for a generated adapter artifact.",
                    ),
                }
            )

    return risk_flags


def _summarize_reason_counts(records: list[dict[str, Any]], decision: str) -> list[dict[str, Any]]:
    counter = Counter(
        str(record.get("reason", "")).strip()
        for record in records
        if record.get("decision") == decision and str(record.get("reason", "")).strip()
    )
    return [
        {"reason": reason, "count": count}
        for reason, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    ]


def _build_decision_rationale_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    experiment_records = [record for record in records if record.get("decision") != "baseline"]
    accepted_reasons = _summarize_reason_counts(experiment_records, "accepted")
    rejected_reasons = _summarize_reason_counts(experiment_records, "rejected")

    def _count_matching(pattern: str) -> int:
        lowered = pattern.lower()
        return sum(1 for record in experiment_records if lowered in str(record.get("reason", "")).lower())

    return {
        "accepted_reason_count": len(accepted_reasons),
        "rejected_reason_count": len(rejected_reasons),
        "accepted_reasons": accepted_reasons,
        "rejected_reasons": rejected_reasons,
        "top_accept_reasons": accepted_reasons[:3],
        "top_reject_reasons": rejected_reasons[:3],
        "failed_evaluation_count": _count_matching("evaluation command failed during execution"),
        "constraint_violation_count": _count_matching("violated one or more constraints"),
        "below_threshold_count": _count_matching("below threshold"),
        "non_improving_primary_metric_count": _count_matching("did not improve"),
        "pareto_accept_count": _count_matching("added to pareto frontier"),
        "pareto_reject_count": _count_matching("dominated by the current pareto frontier"),
    }


def _push_remote_artifacts(contract: OptimizationContract, git_context: GitRunContext, accepted_experiments: int) -> None:
    if not contract.version_control.enabled or not contract.version_control.push_remote or accepted_experiments == 0:
        return
    if not git_context.working_branch:
        raise RuntimeError("Cannot push remote branch: working branch is unknown.")

    try:
        git_context.pushed_remote_branch = push_branch(
            contract.workspace_path,
            contract.version_control.remote_name,
            git_context.working_branch,
        )
    except GitOperationError as exc:
        raise RuntimeError(exc.message if exc.hint is None else f"{exc.message}\n{exc.hint}") from exc

    if not contract.version_control.create_pull_request:
        return

    base_branch = None if git_context.initial_state is None else git_context.initial_state.get("branch")
    if not isinstance(base_branch, str) or not base_branch:
        raise RuntimeError("Cannot create a pull request because the base branch could not be determined.")

    title = f"AutoOptimize: {contract.scenario.name or contract.scenario.type}"
    body = (
        f"Auto-generated optimization results for `{contract.scenario.type}`.\n\n"
        f"- Branch: `{git_context.working_branch}`\n"
        f"- Accepted experiments: `{accepted_experiments}`\n"
    )
    try:
        git_context.pull_request_url = create_pull_request(
            contract.workspace_path,
            base_branch=base_branch,
            head_branch=git_context.working_branch,
            title=title,
            body=body,
            draft=contract.version_control.pull_request_draft,
        )
    except GitOperationError as exc:
        raise RuntimeError(exc.message if exc.hint is None else f"{exc.message}\n{exc.hint}") from exc


def run_contract(contract: OptimizationContract, execution_mode: str = "contract") -> dict[str, Any]:
    validation_result = validate_contract(contract)
    validation_report_path = write_validation_report(contract, validation_result)
    if not validation_result.valid or validation_result.baseline_metrics is None:
        messages: list[str] = []
        for issue in validation_result.issues:
            detail = f"[{issue.severity}] {issue.code}: {issue.message}"
            if issue.field:
                detail += f" Field: {issue.field}."
            if issue.hint:
                detail += f" Hint: {issue.hint}"
            messages.append(detail)
        raise RuntimeError("Contract validation failed before run:\n" + "\n".join(messages))

    git_context = _prepare_git_run(contract, validation_result.git_state)

    output_dir = resolve_workspace_relative(contract.workspace_path, contract.report.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    baseline_metrics = validation_result.baseline_metrics
    current_workspace_metrics = dict(baseline_metrics)
    best_primary_metrics = dict(baseline_metrics)
    constraint_checks = evaluate_constraints(contract.constraints, baseline_metrics)
    records = [_baseline_log_entry(contract, baseline_metrics, git_context.as_dict())]
    pareto_metric_definitions = tracked_metric_definitions(contract)
    pareto_frontier = (
        [
            _pareto_entry(
                experiment_id="baseline",
                decision="baseline",
                metrics=baseline_metrics,
                candidate={},
                reason="Baseline evaluation before candidate loop.",
            )
        ]
        if contract.pareto.enabled
        else []
    )
    pareto_snapshot_store = (
        {
            "baseline": {
                "editable_files": _capture_editable_file_snapshot(contract),
            }
        }
        if contract.pareto.enabled
        else {}
    )

    candidates = generate_candidates(contract)
    max_experiments = contract.run_policy.max_experiments
    no_improvement_rounds = 0
    accepted_experiments = 0
    rejected_experiments = 0
    failed_evaluations = 0
    accepted_candidates: list[dict[str, Any]] = []

    for index, candidate in enumerate(candidates[:max_experiments], start=1):
        previous_workspace_metrics = dict(current_workspace_metrics)
        previous_best_primary_metrics = dict(best_primary_metrics)
        changes, snapshots = apply_candidate_changes(contract, candidate.changes)
        rollback_performed = False

        try:
            outcome = execute_evaluation_with_details(contract)
            candidate_metrics = outcome.metrics
        except EvaluationExecutionError as exc:
            rollback_change(contract, snapshots)
            rollback_performed = True
            failed_evaluations += 1
            rejected_experiments += 1
            no_improvement_rounds += 1

            reason = exc.message if exc.hint is None else f"{exc.message} Hint: {exc.hint}"
            records.append(
                _candidate_log_entry(
                    contract=contract,
                    experiment_id=f"exp_{index:04d}",
                    candidate=candidate,
                    changes=[asdict(change) for change in changes],
                    metrics_before=previous_workspace_metrics,
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

        if contract.decision_policy.mode == "pareto_frontier":
            if not constraints_satisfied(contract.constraints, candidate_metrics):
                decision, reason = "rejected", "Candidate violated one or more constraints."
            else:
                frontier_metrics = [entry["metrics"] for entry in pareto_frontier]
                if is_non_dominated(frontier_metrics, candidate_metrics, pareto_metric_definitions):
                    decision, reason = "accepted", "Candidate added to Pareto frontier."
                else:
                    decision, reason = "rejected", "Candidate is dominated by the current Pareto frontier."
        else:
            decision, reason = decide_candidate(contract, baseline_metrics, best_primary_metrics, candidate_metrics)
        if contract.pareto.enabled and constraints_satisfied(contract.constraints, candidate_metrics):
            candidate_experiment_id = f"exp_{index:04d}"
            pareto_frontier = _update_pareto_frontier(
                pareto_frontier,
                _pareto_entry(
                    experiment_id=candidate_experiment_id,
                    decision=decision,
                    metrics=candidate_metrics,
                    candidate=candidate.candidate_values,
                    reason=reason,
                ),
                pareto_metric_definitions,
            )
            frontier_ids = {entry["experiment_id"] for entry in pareto_frontier}
            if candidate_experiment_id in frontier_ids:
                pareto_snapshot_store[candidate_experiment_id] = {
                    "editable_files": _capture_editable_file_snapshot(contract),
                }
            for experiment_id in list(pareto_snapshot_store):
                if experiment_id not in frontier_ids:
                    del pareto_snapshot_store[experiment_id]

        if decision == "accepted":
            if contract.version_control.enabled and contract.version_control.commit_accepted_changes:
                experiment_id = f"exp_{index:04d}"
                try:
                    commit_head = commit_files(
                        contract.workspace_path,
                        sorted({change.file for change in changes}),
                        _build_commit_message(
                            contract=contract,
                            experiment_id=experiment_id,
                            candidate=candidate,
                            previous_metrics=previous_workspace_metrics,
                            candidate_metrics=candidate_metrics,
                        ),
                    )
                except GitOperationError as exc:
                    rollback_change(contract, snapshots)
                    raise RuntimeError(
                        exc.message if exc.hint is None else f"{exc.message}\n{exc.hint}"
                    ) from exc
                git_context.commits.append(commit_head)

            current_workspace_metrics = dict(candidate_metrics)
            if dominates(
                {contract.metrics.primary.name: candidate_metrics[contract.metrics.primary.name]},
                {contract.metrics.primary.name: best_primary_metrics[contract.metrics.primary.name]},
                [contract.metrics.primary],
            ):
                best_primary_metrics = dict(candidate_metrics)
            accepted_experiments += 1
            no_improvement_rounds = 0
            accepted_candidates.append(
                {
                    "experiment_id": f"exp_{index:04d}",
                    "parameter": candidate.parameter,
                    "value": candidate.value,
                    "parameters": candidate.parameters,
                    "candidate": candidate.candidate_values,
                    "primary_metric_before": previous_workspace_metrics[contract.metrics.primary.name],
                    "primary_metric_after": candidate_metrics[contract.metrics.primary.name],
                    "primary_metric_improvement": (
                        candidate_metrics[contract.metrics.primary.name]
                        - previous_workspace_metrics[contract.metrics.primary.name]
                        if contract.metrics.primary.direction == "maximize"
                        else previous_workspace_metrics[contract.metrics.primary.name]
                        - candidate_metrics[contract.metrics.primary.name]
                    ),
                    "changes": [asdict(change) for change in changes],
                }
            )
        else:
            rollback_change(contract, snapshots)
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
                candidate=candidate,
                changes=[asdict(change) for change in changes],
                metrics_before=previous_workspace_metrics,
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
    pareto_frontier_path = output_dir / "pareto_frontier.json"
    pareto_snapshot_dir = output_dir / "pareto_frontier_snapshots"

    artifact_map = {
        "validation_report": str(validation_report_path),
        "experiment_log_jsonl": str(experiment_log_path),
        "experiment_log_csv": str(experiment_csv_path),
        "run_summary": str(run_summary_path),
        "optimization_report_md": str(report_md_path),
    }
    if contract.pareto.enabled:
        artifact_map["pareto_frontier"] = str(pareto_frontier_path)
        artifact_map["pareto_frontier_snapshots"] = str(pareto_snapshot_dir)
    if "html" in contract.report.formats:
        artifact_map["optimization_report_html"] = str(report_html_path)

    _push_remote_artifacts(contract, git_context, accepted_experiments)
    adapter_provenance = _build_adapter_provenance(contract, validation_result.generated_adapters)
    risk_flags = _build_risk_flags(contract, validation_result.generated_adapters, adapter_provenance)
    decision_rationale_summary = _build_decision_rationale_summary(records)

    summary = {
        "status": "completed",
        "mode": "run",
        "execution_mode": execution_mode,
        "scenario_type": contract.scenario.type,
        "scenario_name": contract.scenario.name,
        "search_strategy": contract.run_policy.search_strategy,
        "contract_path": str(contract.contract_path),
        "workspace_path": str(contract.workspace_path),
        "timestamp": _timestamp(),
        "experiments_run": len(records) - 1,
        "accepted_experiments": accepted_experiments,
        "rejected_experiments": rejected_experiments,
        "failed_evaluations": failed_evaluations,
        "baseline_metrics": baseline_metrics,
        "best_metrics": best_primary_metrics,
        "final_workspace_metrics": current_workspace_metrics,
        "primary_metric": {
            "name": contract.metrics.primary.name,
            "direction": contract.metrics.primary.direction,
        },
        "accepted_candidates": accepted_candidates,
        "constraints_satisfied": all(check.passed for check in constraint_checks),
        "constraint_checks": [asdict(check) for check in constraint_checks],
        "generated_adapters": validation_result.generated_adapters,
        "asset_context": _build_asset_context(contract, validation_result.generated_adapters, execution_mode),
        "adapter_provenance": adapter_provenance,
        "risk_flags": risk_flags,
        "decision_rationale_summary": decision_rationale_summary,
        "pareto_enabled": contract.pareto.enabled,
        "pareto_profiles": contract.pareto.profiles,
        "pareto_frontier": pareto_frontier,
        "benchmark_context": _load_workspace_benchmark_context(contract.workspace_path),
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
            f"This MVP run executes the `{contract.run_policy.search_strategy}` search strategy.",
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
    if contract.pareto.enabled:
        pareto_frontier_path.write_text(json.dumps(pareto_frontier, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        _persist_pareto_snapshots(pareto_frontier, pareto_snapshot_store, pareto_snapshot_dir)
    run_summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    markdown_report = generate_markdown_report(summary, baseline_metrics)
    report_md_path.write_text(markdown_report, encoding="utf-8")
    if "html" in contract.report.formats:
        report_html_path.write_text(generate_html_report(markdown_report), encoding="utf-8")

    return summary
