from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class ScenarioConfig:
    type: str
    name: str | None = None


@dataclass(slots=True)
class WorkspaceConfig:
    path: str


@dataclass(slots=True)
class SearchSpaceMapping:
    type: str
    file: str
    path: str
    create_if_missing: bool = False


@dataclass(slots=True)
class SearchSpaceParameter:
    values: list[Any]
    mapping: SearchSpaceMapping


@dataclass(slots=True)
class EvaluationConfig:
    command: str
    output_format: str = "json"
    timeout_seconds: int = 600
    output_file: str | None = None


@dataclass(slots=True)
class MetricDefinition:
    name: str
    direction: str


@dataclass(slots=True)
class MetricsConfig:
    primary: MetricDefinition
    secondary: list[MetricDefinition] = field(default_factory=list)


@dataclass(slots=True)
class DecisionPolicy:
    mode: str = "constrained_primary_metric"
    min_primary_improvement: float = 0.0


@dataclass(slots=True)
class ParetoConfig:
    enabled: bool = False
    profiles: list[str] = field(default_factory=list)


@dataclass(slots=True)
class RunPolicy:
    max_experiments: int = 10
    stop_if_no_improvement_rounds: int = 3
    search_strategy: str = "one_variable"
    max_pairwise_candidates: int = 12
    random_seed: int = 42
    dry_run: bool = False
    max_runtime_minutes: int | None = None
    max_cost_usd: float | None = None
    max_failed_evaluations: int = 3


@dataclass(slots=True)
class VersionControlConfig:
    enabled: bool = False
    require_clean_worktree: bool = True
    create_branch: bool = True
    commit_accepted_changes: bool = False
    rollback_rejected_changes: bool = True
    branch_prefix: str = "auto-optimize/"
    remote_name: str = "origin"
    push_remote: bool = False
    create_pull_request: bool = False
    pull_request_draft: bool = True
    commit_message_template: str | None = None


@dataclass(slots=True)
class ReportConfig:
    formats: list[str] = field(default_factory=lambda: ["markdown"])
    output_dir: str = "auto_optimize_outputs"


@dataclass(slots=True)
class OptimizationContract:
    schema_version: str
    scenario: ScenarioConfig
    workspace: WorkspaceConfig
    editable_scope: list[str]
    protected_scope: list[str]
    search_space: dict[str, SearchSpaceParameter]
    evaluation: EvaluationConfig
    metrics: MetricsConfig
    constraints: dict[str, dict[str, Any]] = field(default_factory=dict)
    decision_policy: DecisionPolicy = field(default_factory=DecisionPolicy)
    pareto: ParetoConfig = field(default_factory=ParetoConfig)
    run_policy: RunPolicy = field(default_factory=RunPolicy)
    version_control: VersionControlConfig = field(default_factory=VersionControlConfig)
    report: ReportConfig = field(default_factory=ReportConfig)
    contract_path: Path | None = None
    contract_dir: Path | None = None
    workspace_path: Path | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OptimizationContract":
        scenario = ScenarioConfig(**data["scenario"])
        workspace = WorkspaceConfig(**data["workspace"])

        search_space = {
            key: SearchSpaceParameter(
                values=value.get("values", []),
                mapping=SearchSpaceMapping(**value["mapping"]),
            )
            for key, value in data.get("search_space", {}).items()
        }

        metrics_dict = data["metrics"]
        metrics = MetricsConfig(
            primary=MetricDefinition(**metrics_dict["primary"]),
            secondary=[MetricDefinition(**item) for item in metrics_dict.get("secondary", [])],
        )

        evaluation = EvaluationConfig(**data["evaluation"])
        decision_policy = DecisionPolicy(**data.get("decision_policy", {}))
        pareto = ParetoConfig(**data.get("pareto", {}))
        run_policy = RunPolicy(**data.get("run_policy", {}))
        version_control = VersionControlConfig(**data.get("version_control", {}))
        report = ReportConfig(**data.get("report", {}))

        return cls(
            schema_version=str(data.get("schema_version", "0.2")),
            scenario=scenario,
            workspace=workspace,
            editable_scope=list(data.get("editable_scope", [])),
            protected_scope=list(data.get("protected_scope", [])),
            search_space=search_space,
            evaluation=evaluation,
            metrics=metrics,
            constraints=dict(data.get("constraints", {})),
            decision_policy=decision_policy,
            pareto=pareto,
            run_policy=run_policy,
            version_control=version_control,
            report=report,
        )
