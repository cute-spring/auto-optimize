from __future__ import annotations

from auto_optimize.shared.errors import ValidationResult
from auto_optimize.shared.schemas import RunPolicy


def validate_run_policy(run_policy: RunPolicy, result: ValidationResult) -> None:
    if run_policy.max_experiments <= 0:
        result.add_issue("error", "invalid_run_budget", "run_policy.max_experiments must be greater than 0.")
    if run_policy.stop_if_no_improvement_rounds < 0:
        result.add_issue(
            "error",
            "invalid_stop_threshold",
            "run_policy.stop_if_no_improvement_rounds cannot be negative.",
        )
    if run_policy.max_runtime_minutes is not None and run_policy.max_runtime_minutes <= 0:
        result.add_issue(
            "error",
            "invalid_runtime_budget",
            "run_policy.max_runtime_minutes must be greater than 0 when provided.",
        )
    if run_policy.max_cost_usd is not None and run_policy.max_cost_usd <= 0:
        result.add_issue(
            "error",
            "invalid_cost_budget",
            "run_policy.max_cost_usd must be greater than 0 when provided.",
        )
