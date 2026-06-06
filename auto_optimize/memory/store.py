from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from auto_optimize.shared.schemas import MetricDefinition


@dataclass(slots=True)
class MemorySnapshot:
    history_path: Path
    best_run_path: Path
    total_runs: int
    current_run_is_historical_best: bool
    best_run_timestamp: str | None
    best_primary_metric: Any
    best_primary_improvement: float | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "history_path": str(self.history_path),
            "best_run_path": str(self.best_run_path),
            "total_runs": self.total_runs,
            "current_run_is_historical_best": self.current_run_is_historical_best,
            "best_run_timestamp": self.best_run_timestamp,
            "best_primary_metric": self.best_primary_metric,
            "best_primary_improvement": self.best_primary_improvement,
        }


def _primary_metric_value(summary: dict[str, Any], definition: MetricDefinition) -> Any:
    return summary["best_metrics"][definition.name]


def _primary_metric_improvement(summary: dict[str, Any], definition: MetricDefinition) -> float:
    baseline = summary["baseline_metrics"][definition.name]
    best = summary["best_metrics"][definition.name]
    if definition.direction == "maximize":
        return best - baseline
    if definition.direction == "minimize":
        return baseline - best
    raise ValueError(f"Unsupported metric direction: {definition.direction}")


def _is_better(candidate: Any, incumbent: Any, definition: MetricDefinition) -> bool:
    if incumbent is None:
        return True
    if definition.direction == "maximize":
        return candidate > incumbent
    if definition.direction == "minimize":
        return candidate < incumbent
    raise ValueError(f"Unsupported metric direction: {definition.direction}")


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _build_run_record(summary: dict[str, Any], definition: MetricDefinition) -> dict[str, Any]:
    return {
        "timestamp": summary["timestamp"],
        "scenario_type": summary["scenario_type"],
        "scenario_name": summary["scenario_name"],
        "contract_path": summary["contract_path"],
        "workspace_path": summary["workspace_path"],
        "run_summary_path": summary["artifacts"]["run_summary"],
        "primary_metric_name": definition.name,
        "primary_metric_direction": definition.direction,
        "baseline_primary_metric": summary["baseline_metrics"][definition.name],
        "best_primary_metric": summary["best_metrics"][definition.name],
        "primary_metric_improvement": _primary_metric_improvement(summary, definition),
        "accepted_experiments": summary["accepted_experiments"],
        "rejected_experiments": summary["rejected_experiments"],
        "failed_evaluations": summary["failed_evaluations"],
    }


def update_memory_store(output_dir: Path, summary: dict[str, Any], definition: MetricDefinition) -> MemorySnapshot:
    history_path = output_dir / "run_history.jsonl"
    best_run_path = output_dir / "best_run_snapshot.json"

    current_record = _build_run_record(summary, definition)
    existing_best = _load_json(best_run_path)
    existing_best_metric = None if existing_best is None else existing_best.get("best_primary_metric")

    current_best_metric = _primary_metric_value(summary, definition)
    current_run_is_historical_best = _is_better(current_best_metric, existing_best_metric, definition)
    if current_run_is_historical_best:
        best_payload = {
            **current_record,
            "baseline_metrics": summary["baseline_metrics"],
            "best_metrics": summary["best_metrics"],
            "accepted_candidates": summary.get("accepted_candidates", []),
        }
        best_run_path.write_text(json.dumps(best_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        best_snapshot = best_payload
    else:
        best_snapshot = existing_best or current_record

    with history_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(current_record, ensure_ascii=False) + "\n")

    total_runs = sum(1 for line in history_path.read_text(encoding="utf-8").splitlines() if line.strip())
    best_primary_improvement = best_snapshot.get("primary_metric_improvement")

    return MemorySnapshot(
        history_path=history_path,
        best_run_path=best_run_path,
        total_runs=total_runs,
        current_run_is_historical_best=current_run_is_historical_best,
        best_run_timestamp=best_snapshot.get("timestamp"),
        best_primary_metric=best_snapshot.get("best_primary_metric"),
        best_primary_improvement=best_primary_improvement,
    )
