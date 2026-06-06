from __future__ import annotations

import json
import subprocess
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


def execute_evaluation(contract: OptimizationContract) -> dict[str, Any]:
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

    return metrics
