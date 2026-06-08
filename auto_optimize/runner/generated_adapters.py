from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from auto_optimize.shared.paths import resolve_workspace_relative
from auto_optimize.shared.schemas import OptimizationContract


@dataclass(slots=True)
class GeneratedAdapterRecord:
    kind: str
    template: str
    generated_path: str
    purpose: str
    declaration_source: str | None
    risk_flags: list[str]
    execution_phase: str
    expected_input: str
    failure_mode: str
    remediation_hint: str
    execution_mode: str = "subprocess"


@dataclass(slots=True)
class GeneratedAdapterExecutionResult:
    metrics: dict[str, Any]
    generated_adapters: list[GeneratedAdapterRecord]


@dataclass(frozen=True, slots=True)
class GeneratedAdapterSpec:
    kind: str
    template: str
    execution_phase: str
    required_fields: tuple[str, ...]
    required_risk_flags: tuple[str, ...]
    allowed_risk_flags: tuple[str, ...]
    declaration_allowed_kind: str
    materialize: Callable[[OptimizationContract, dict[str, Any]], Path]
    execute: Callable[[OptimizationContract, str, dict[str, Any]], GeneratedAdapterExecutionResult]


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

_LAST_JSON_LINE_WRAPPER_TEMPLATE = """#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys


def _extract_metrics(stdout: str) -> dict:
    for line in reversed(stdout.splitlines()):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    raise ValueError("Could not find a JSON object on the last non-empty stdout lines.")


def main() -> int:
    command = sys.argv[1]
    completed = subprocess.run(command, shell=True, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        sys.stderr.write(completed.stderr or completed.stdout or "Wrapper captured no output.\\n")
        return completed.returncode
    metrics = _extract_metrics(completed.stdout)
    print(json.dumps(metrics))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""


def _generated_adapter_dir(contract: OptimizationContract, output_dir: str) -> Path:
    return resolve_workspace_relative(contract.workspace_path, output_dir)


def _ensure_metrics_parser_key_value_lines(contract: OptimizationContract, adapter_config: dict[str, Any]) -> Path:
    adapter_dir = _generated_adapter_dir(contract, adapter_config["output_dir"])
    adapter_dir.mkdir(parents=True, exist_ok=True)
    adapter_path = adapter_dir / f"{adapter_config['kind']}_{adapter_config['template']}.py"
    if not adapter_path.exists():
        adapter_path.write_text(_KEY_VALUE_LINES_ADAPTER_TEMPLATE, encoding="utf-8")
    return adapter_path


def _ensure_eval_wrapper_last_json_line(contract: OptimizationContract, adapter_config: dict[str, Any]) -> Path:
    adapter_dir = _generated_adapter_dir(contract, adapter_config["output_dir"])
    adapter_dir.mkdir(parents=True, exist_ok=True)
    adapter_path = adapter_dir / f"{adapter_config['kind']}_{adapter_config['template']}.py"
    if not adapter_path.exists():
        adapter_path.write_text(_LAST_JSON_LINE_WRAPPER_TEMPLATE, encoding="utf-8")
    return adapter_path


def _execute_metrics_parser_key_value_lines(
    contract: OptimizationContract,
    raw_output: str,
    adapter_config: dict[str, Any],
) -> GeneratedAdapterExecutionResult:
    from auto_optimize.runner.evaluator import EvaluationExecutionError

    adapter_path = _ensure_metrics_parser_key_value_lines(contract, adapter_config)
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

    return GeneratedAdapterExecutionResult(
        metrics=metrics,
        generated_adapters=[
            GeneratedAdapterRecord(
                kind=str(adapter_config["kind"]),
                template=str(adapter_config["template"]),
                generated_path=str(adapter_path),
                purpose=str(adapter_config.get("purpose", "Parse evaluation output into metrics.")),
                declaration_source=adapter_config.get("declaration_source"),
                risk_flags=list(adapter_config.get("risk_flags", [])),
                execution_phase="post_output",
                expected_input="Colon-delimited key/value lines from evaluation stdout or output file.",
                failure_mode="Fails when evaluation output cannot be parsed as stable `name: value` lines.",
                remediation_hint="Emit stable `name: value` lines or switch to a more appropriate adapter template.",
            )
        ],
    )


def _execute_eval_wrapper_last_json_line(
    contract: OptimizationContract,
    raw_output: str,
    adapter_config: dict[str, Any],
) -> GeneratedAdapterExecutionResult:
    from auto_optimize.runner.evaluator import EvaluationExecutionError

    del raw_output
    adapter_path = _ensure_eval_wrapper_last_json_line(contract, adapter_config)
    completed = subprocess.run(
        [sys.executable, str(adapter_path), contract.evaluation.command],
        cwd=contract.workspace_path,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise EvaluationExecutionError(
            code="generated_adapter_failed",
            message="Generated eval wrapper failed during execution.",
            hint=completed.stderr.strip() or completed.stdout.strip() or "No output captured.",
        )

    try:
        metrics = json.loads(completed.stdout.strip())
    except json.JSONDecodeError as exc:
        raise EvaluationExecutionError(
            code="generated_adapter_invalid_output",
            message=f"Generated eval wrapper did not emit valid JSON: {exc}",
        ) from exc

    if not isinstance(metrics, dict):
        raise EvaluationExecutionError(
            code="generated_adapter_invalid_shape",
            message="Generated eval wrapper output must be a JSON object.",
        )

    return GeneratedAdapterExecutionResult(
        metrics=metrics,
        generated_adapters=[
            GeneratedAdapterRecord(
                kind=str(adapter_config["kind"]),
                template=str(adapter_config["template"]),
                generated_path=str(adapter_path),
                purpose=str(adapter_config.get("purpose", "Normalize evaluation command output into a metrics JSON object.")),
                declaration_source=adapter_config.get("declaration_source"),
                risk_flags=list(adapter_config.get("risk_flags", [])),
                execution_phase="pre_command",
                expected_input="A wrapped evaluation command whose last non-empty stdout line is a JSON object.",
                failure_mode="Fails when the wrapped command exits non-zero or no JSON object can be recovered from the last stdout lines.",
                remediation_hint="Make the wrapped command end with a JSON metrics line or switch to a parser-based adapter path.",
            )
        ],
    )


_REGISTERED_SPECS: dict[tuple[str, str], GeneratedAdapterSpec] = {
    ("metrics_parser", "key_value_lines"): GeneratedAdapterSpec(
        kind="metrics_parser",
        template="key_value_lines",
        execution_phase="post_output",
        required_fields=("kind", "template", "output_dir", "purpose", "risk_flags"),
        required_risk_flags=("generated_code", "metrics_parsing"),
        allowed_risk_flags=("generated_code", "metrics_parsing"),
        declaration_allowed_kind="metrics_parser",
        materialize=_ensure_metrics_parser_key_value_lines,
        execute=_execute_metrics_parser_key_value_lines,
    ),
    ("eval_wrapper", "last_json_line"): GeneratedAdapterSpec(
        kind="eval_wrapper",
        template="last_json_line",
        execution_phase="pre_command",
        required_fields=("kind", "template", "output_dir", "purpose", "risk_flags"),
        required_risk_flags=("generated_code", "external_eval_command"),
        allowed_risk_flags=("generated_code", "external_eval_command"),
        declaration_allowed_kind="eval_wrapper",
        materialize=_ensure_eval_wrapper_last_json_line,
        execute=_execute_eval_wrapper_last_json_line,
    ),
}


def materialize_generated_adapter(contract: OptimizationContract, adapter_config: dict[str, Any]) -> Path:
    from auto_optimize.runner.evaluator import EvaluationExecutionError

    key = (str(adapter_config.get("kind")), str(adapter_config.get("template")))
    spec = _REGISTERED_SPECS.get(key)
    if spec is None:
        raise EvaluationExecutionError(
            code="unsupported_generated_adapter_template",
            message=f"Unsupported generated adapter `{key[0]}` with template `{key[1]}`.",
        )
    return spec.materialize(contract, adapter_config)


def execute_generated_adapter(
    contract: OptimizationContract,
    raw_output: str,
    adapter_config: dict[str, Any],
) -> GeneratedAdapterExecutionResult:
    from auto_optimize.runner.evaluator import EvaluationExecutionError

    key = (str(adapter_config.get("kind")), str(adapter_config.get("template")))
    spec = _REGISTERED_SPECS.get(key)
    if spec is None:
        raise EvaluationExecutionError(
            code="unsupported_generated_adapter_template",
            message=f"Unsupported generated adapter `{key[0]}` with template `{key[1]}`.",
        )
    return spec.execute(contract, raw_output, adapter_config)


def generated_adapter_execution_phase(adapter_config: dict[str, Any]) -> str:
    key = (str(adapter_config.get("kind")), str(adapter_config.get("template")))
    spec = _REGISTERED_SPECS.get(key)
    if spec is None:
        return "unknown"
    return spec.execution_phase


def registered_generated_adapters() -> list[tuple[str, str]]:
    return sorted(_REGISTERED_SPECS)


def generated_adapter_spec(adapter_config: dict[str, Any]) -> GeneratedAdapterSpec | None:
    key = (str(adapter_config.get("kind")), str(adapter_config.get("template")))
    return _REGISTERED_SPECS.get(key)
