from __future__ import annotations

from auto_optimize.shared.schemas import OptimizationContract

DEFAULT_PROTECTED_SCOPE = [
    ".env",
    "secrets/",
    "eval/",
    "test_data/",
    "benchmark/",
    "production_config/",
]


def apply_contract_defaults(contract: OptimizationContract) -> OptimizationContract:
    merged_protected = list(contract.protected_scope)
    for entry in DEFAULT_PROTECTED_SCOPE:
        if entry not in merged_protected:
            merged_protected.append(entry)
    contract.protected_scope = merged_protected

    if not contract.report.output_dir:
        contract.report.output_dir = "auto_optimize_outputs"
    if not contract.run_policy.max_experiments:
        contract.run_policy.max_experiments = 10
    if not contract.pareto.profiles:
        contract.pareto.profiles = [
            "accuracy_first",
            "balanced",
            "latency_first",
            "cost_first",
        ]
    if not contract.version_control.branch_prefix:
        contract.version_control.branch_prefix = "auto-optimize/"
    return contract
