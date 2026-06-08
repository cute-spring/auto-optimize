from __future__ import annotations

import csv
import json
import subprocess
import sys
from io import StringIO
from dataclasses import dataclass
from typing import Any

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
class GeneratedAdapterRecord:
    kind: str
    template: str
    generated_path: str
    purpose: str
    declaration_source: str | None
    risk_flags: list[str]
    execution_mode: str = "subprocess"


@dataclass(slots=True)
class EvaluationOutcome:
    metrics: dict[str, Any]
    generated_adapters: list[GeneratedAdapterRecord]


_KEY_VALUE_LINES_ADAPTER_TEMPLATE = """#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


def _parse_value(raw: str):
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


def main() -> int:
    raw_path = Path(sys.argv[1])
    metrics = {}
    for line in raw_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            raise ValueError(f"Invalid metrics line: {stripped}")
        key, raw_value = stripped.split(":", 1)
        metrics[key.strip()] = _parse_value(raw_value)
    print(json.dumps(metrics))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""


def _generated_adapter_dir(contract: OptimizationContract, output_dir: str) -> Path:
    return resolve_workspace_relative(contract.workspace_path, output_dir)


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


def _ensure_generated_adapter(contract: OptimizationContract, adapter_config: dict[str, Any]) -> Path:
    template = adapter_config.get("template")
    if template != "key_value_lines":
        raise EvaluationExecutionError(
            code="unsupported_generated_adapter_template",
            message=f"Unsupported generated adapter template: {template}",
        )

    adapter_dir = _generated_adapter_dir(contract, adapter_config["output_dir"])
    adapter_dir.mkdir(parents=True, exist_ok=True)
    adapter_path = adapter_dir / f"{adapter_config['kind']}_{template}.py"
    if not adapter_path.exists():
        adapter_path.write_text(_KEY_VALUE_LINES_ADAPTER_TEMPLATE, encoding="utf-8")
    return adapter_path


def _run_generated_metrics_parser(
    contract: OptimizationContract,
    raw_output: str,
    adapter_config: dict[str, Any],
) -> EvaluationOutcome:
    adapter_path = _ensure_generated_adapter(contract, adapter_config)
    raw_metrics_path = adapter_path.parent / "latest_metrics_input.txt"
    raw_metrics_path.write_text(raw_output + "\n", encoding="utf-8")

    completed = subprocess.run(
        [sys.executable, str(adapter_path), str(raw_metrics_path)],
        cwd=contract.workspace_path,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise EvaluationExecutionError(
            code="generated_adapter_failed",
            message="Generated metrics parser failed during execution.",
            hint=completed.stderr.strip() or completed.stdout.strip() or "No output captured.",
        )

    try:
        metrics = json.loads(completed.stdout.strip())
    except json.JSONDecodeError as exc:
        raise EvaluationExecutionError(
            code="generated_adapter_invalid_output",
            message=f"Generated metrics parser did not emit valid JSON: {exc}",
        ) from exc

    if not isinstance(metrics, dict):
        raise EvaluationExecutionError(
            code="generated_adapter_invalid_shape",
            message="Generated metrics parser output must be a JSON object.",
        )

    return EvaluationOutcome(
        metrics=metrics,
        generated_adapters=[
            GeneratedAdapterRecord(
                kind=str(adapter_config["kind"]),
                template=str(adapter_config["template"]),
                generated_path=str(adapter_path),
                purpose=str(adapter_config.get("purpose", "Parse evaluation output into metrics.")),
                declaration_source=adapter_config.get("declaration_source"),
                risk_flags=list(adapter_config.get("risk_flags", [])),
            )
        ],
    )


def execute_evaluation_with_details(contract: OptimizationContract) -> EvaluationOutcome:
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
        return _run_generated_metrics_parser(contract, raw_output, contract.evaluation.adapter)

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
