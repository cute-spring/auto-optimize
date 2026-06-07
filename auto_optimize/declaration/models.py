from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class DeclarationWorkspace:
    path: str = "."


@dataclass(slots=True)
class ObjectiveDeclaration:
    description: str


@dataclass(slots=True)
class VariableDeclaration:
    name: str
    kind: str
    target: str
    values: list[Any]
    path: str | None = None
    create_if_missing: bool = False


@dataclass(slots=True)
class EvaluationDeclaration:
    command: str
    metrics_source: str
    timeout_seconds: int = 600
    metrics_path: str | None = None
    parser_template: str | None = None
    repetitions: int = 1
    prepared_inputs: list[str] = field(default_factory=list)


@dataclass(slots=True)
class MetricDeclaration:
    name: str
    direction: str


@dataclass(slots=True)
class ComparisonDeclaration:
    primary_metric: str
    direction: str
    min_improvement: float | None = None
    decision_rule: str | None = None
    secondary_metrics: list[MetricDeclaration] = field(default_factory=list)


@dataclass(slots=True)
class SafetyDeclaration:
    editable: list[str]
    protected: list[str] = field(default_factory=list)
    secrets: list[str] = field(default_factory=list)
    requires_confirmation: list[str] = field(default_factory=list)


@dataclass(slots=True)
class BudgetDeclaration:
    max_experiments: int | None = None
    stop_if_no_improvement_rounds: int | None = None
    search_strategy: str | None = None
    max_pairwise_candidates: int | None = None
    random_seed: int | None = None
    dry_run: bool | None = None
    max_runtime_minutes: int | None = None
    max_cost_usd: float | None = None
    max_failed_evaluations: int | None = None


@dataclass(slots=True)
class AlgorithmDeclaration:
    provided_by_user: bool = False
    command: str | None = None


@dataclass(slots=True)
class AdapterGenerationDeclaration:
    allowed: bool = False
    allowed_kinds: list[str] = field(default_factory=list)
    output_dir: str = "auto_optimize_outputs/generated_adapters"


@dataclass(slots=True)
class OptimizationDeclaration:
    objective: ObjectiveDeclaration
    variables: list[VariableDeclaration]
    evaluation: EvaluationDeclaration
    comparison: ComparisonDeclaration
    safety: SafetyDeclaration
    workspace: DeclarationWorkspace = field(default_factory=DeclarationWorkspace)
    constraints: dict[str, dict[str, Any]] = field(default_factory=dict)
    budget: BudgetDeclaration | None = None
    algorithm: AlgorithmDeclaration | None = None
    adapter_generation: AdapterGenerationDeclaration | None = None
    schema_version: str = "0.1"
    declaration_path: Path | None = None
    declaration_dir: Path | None = None
    workspace_path: Path | None = None
