from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from auto_optimize.shared.schemas import MetricDefinition, OptimizationContract


@dataclass(slots=True)
class ConstraintCheck:
    metric_name: str
    passed: bool
    message: str


def evaluate_constraints(constraints: dict[str, dict[str, Any]], metrics: dict[str, Any]) -> list[ConstraintCheck]:
    checks: list[ConstraintCheck] = []
    for metric_name, rule in constraints.items():
        if metric_name not in metrics:
            checks.append(
                ConstraintCheck(
                    metric_name=metric_name,
                    passed=False,
                    message=f"Metric '{metric_name}' is missing from evaluation output.",
                )
            )
            continue

        value = metrics[metric_name]
        if "max" in rule:
            checks.append(
                ConstraintCheck(
                    metric_name=metric_name,
                    passed=value <= rule["max"],
                    message=f"{metric_name} <= {rule['max']} (actual: {value})",
                )
            )
            continue

        if "min" in rule:
            checks.append(
                ConstraintCheck(
                    metric_name=metric_name,
                    passed=value >= rule["min"],
                    message=f"{metric_name} >= {rule['min']} (actual: {value})",
                )
            )
            continue

        if "required" in rule:
            checks.append(
                ConstraintCheck(
                    metric_name=metric_name,
                    passed=bool(value) is bool(rule["required"]),
                    message=f"{metric_name} required={rule['required']} (actual: {value})",
                )
            )
            continue

        checks.append(
            ConstraintCheck(
                metric_name=metric_name,
                passed=True,
                message=f"No executable rule recognized for '{metric_name}'.",
            )
        )
    return checks


def constraints_satisfied(constraints: dict[str, dict[str, Any]], metrics: dict[str, Any]) -> bool:
    return all(check.passed for check in evaluate_constraints(constraints, metrics))


def metric_improvement(
    definition: MetricDefinition,
    before_metrics: dict[str, Any],
    after_metrics: dict[str, Any],
) -> float:
    before = before_metrics[definition.name]
    after = after_metrics[definition.name]
    if definition.direction == "maximize":
        return after - before
    if definition.direction == "minimize":
        return before - after
    raise ValueError(f"Unsupported metric direction: {definition.direction}")


def decide_candidate(
    contract: OptimizationContract,
    baseline_metrics: dict[str, Any],
    current_best_metrics: dict[str, Any],
    candidate_metrics: dict[str, Any],
) -> tuple[str, str]:
    policy = contract.decision_policy.mode
    primary_definition = contract.metrics.primary

    if policy == "primary_metric_only":
        improvement = metric_improvement(primary_definition, current_best_metrics, candidate_metrics)
        if improvement > 0:
            return "accepted", f"Primary metric improved by {improvement:.6f}."
        return "rejected", f"Primary metric did not improve (delta {improvement:.6f})."

    if policy == "constrained_primary_metric":
        checks = evaluate_constraints(contract.constraints, candidate_metrics)
        if not all(check.passed for check in checks):
            return "rejected", "Candidate violated one or more constraints."

        improvement = metric_improvement(primary_definition, current_best_metrics, candidate_metrics)
        min_improvement = contract.decision_policy.min_primary_improvement
        if improvement >= min_improvement:
            return "accepted", f"Primary metric improved by {improvement:.6f}."
        return "rejected", f"Primary metric improvement {improvement:.6f} is below threshold {min_improvement:.6f}."

    return "rejected", f"Decision policy '{policy}' is not implemented in this MVP."
