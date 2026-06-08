from __future__ import annotations

import csv
import json
import subprocess
from io import StringIO
from dataclasses import dataclass
from typing import Any

from auto_optimize.runner.generated_adapters import (
    GeneratedAdapterRecord,
    generated_adapter_execution_phase,
    execute_generated_adapter,
)
from auto_optimize.shared.paths import resolve_workspace_relative
from auto_optimize.shared.schemas import OptimizationContract


@dataclass(slots=True)
class EvaluationExecutionError(Exception):
    code: str
    message: str
    hint: str | None = None

    def __str__(self) -> str:
        return self.message


@dataclass(slots=True)
class EvaluationOutcome:
    metrics: dict[str, Any]
    generated_adapters: list[GeneratedAdapterRecord]


def _coerce_metric_value(raw: str) -> Any:
    value = raw.strip()
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value


def _parse_csv_summary_metrics(raw_output: str) -> dict[str, Any]:
    reader = csv.DictReader(StringIO(raw_output))
    if not reader.fieldnames:
        raise EvaluationExecutionError(
            code="invalid_evaluation_output",
            message="CSV summary output must include a header row with metric names.",
        )

    rows = [row for row in reader if any((value or "").strip() for value in row.values())]
    if not rows:
        raise EvaluationExecutionError(
            code="invalid_evaluation_output",
            message="CSV summary output must include at least one non-empty data row.",
        )

    summary_row = rows[-1]
    metrics: dict[str, Any] = {}
    for key, value in summary_row.items():
        if key is None:
            continue
        normalized_key = key.strip()
        if not normalized_key:
            continue
        metrics[normalized_key] = _coerce_metric_value(value or "")
    return metrics


def execute_evaluation_with_details(contract: OptimizationContract) -> EvaluationOutcome:
    if contract.evaluation.adapter and generated_adapter_execution_phase(contract.evaluation.adapter) == "pre_command":
        adapter_result = execute_generated_adapter(contract, "", contract.evaluation.adapter)
        return EvaluationOutcome(
            metrics=adapter_result.metrics,
            generated_adapters=adapter_result.generated_adapters,
        )

    output_file = None
    if contract.evaluation.output_file:
        output_file = resolve_workspace_relative(contract.workspace_path, contract.evaluation.output_file)
        if output_file.exists():
            output_file.unlink()

    try:
        completed = subprocess.run(
            contract.evaluation.command,
            cwd=contract.workspace_path,
            shell=True,
            text=True,
            capture_output=True,
            timeout=contract.evaluation.timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise EvaluationExecutionError(
            code="evaluation_timeout",
            message=f"Evaluation command exceeded timeout of {contract.evaluation.timeout_seconds} seconds.",
        ) from exc

    if completed.returncode != 0:
        raise EvaluationExecutionError(
            code="evaluation_command_failed",
            message="Evaluation command failed during execution.",
            hint=completed.stderr.strip() or completed.stdout.strip() or "No output captured.",
        )

    raw_output = completed.stdout.strip()
    if output_file is not None:
        if not output_file.exists():
            raise EvaluationExecutionError(
                code="missing_evaluation_output_file",
                message=f"Evaluation output file '{contract.evaluation.output_file}' was not created.",
            )
        raw_output = output_file.read_text(encoding="utf-8").strip()

    if contract.evaluation.adapter:
        adapter_result = execute_generated_adapter(contract, raw_output, contract.evaluation.adapter)
        return EvaluationOutcome(
            metrics=adapter_result.metrics,
            generated_adapters=adapter_result.generated_adapters,
        )

    if contract.evaluation.output_format == "csv_with_summary":
        metrics = _parse_csv_summary_metrics(raw_output)
    else:
        try:
            metrics = json.loads(raw_output)
        except json.JSONDecodeError as exc:
            raise EvaluationExecutionError(
                code="invalid_evaluation_output",
                message=f"Evaluation output is not valid JSON: {exc}",
            ) from exc

        if not isinstance(metrics, dict):
            raise EvaluationExecutionError(
                code="invalid_evaluation_shape",
                message="Evaluation output JSON must be an object.",
            )

    return EvaluationOutcome(metrics=metrics, generated_adapters=[])


def execute_evaluation(contract: OptimizationContract) -> dict[str, Any]:
    return execute_evaluation_with_details(contract).metrics
