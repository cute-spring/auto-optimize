from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from auto_optimize.scenario_packs.benchmark_materializer import BENCHMARK_SPECS


@dataclass(frozen=True, slots=True)
class AdvisorResult:
    draft_contract_path: Path
    readiness_report_path: Path
    readiness_report: dict[str, Any]


_REPO_ROOT = Path(__file__).resolve().parents[2]

_SCENARIO_TO_PROFILE = {
    "faq_retrieval": "faq_metrics",
    "retrieval_embedding_benchmark": "embedding_metrics",
    "reranking_benchmark": "reranking_metrics",
}

_SCENARIO_REQUIRED_FILES = {
    "faq_retrieval": [
        "configs/retrieval.yaml",
        "configs/reranker.yaml",
        "configs/embedding_strategy.yaml",
        "eval/run_eval.py",
    ],
    "retrieval_embedding_benchmark": [
        "configs/retrieval.yaml",
        "configs/embedding.yaml",
        "eval/run_benchmark_eval.py",
        "data/benchmark_manifest.json",
    ],
    "reranking_benchmark": [
        "configs/retrieval.yaml",
        "configs/reranker.yaml",
        "configs/query_processing.yaml",
        "eval/run_benchmark_eval.py",
        "data/benchmark_manifest.json",
    ],
}


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")


def _load_template_payload(workspace: Path, scenario: str, benchmark_key: str | None) -> dict[str, Any]:
    if scenario == "faq_retrieval":
        template_path = _REPO_ROOT / "examples" / "faq_retrieval" / "optimization.contract.yaml"
        return _load_yaml(template_path)

    if benchmark_key and benchmark_key in BENCHMARK_SPECS:
        template_name = BENCHMARK_SPECS[benchmark_key].template_name
        template_path = _REPO_ROOT / "examples" / "benchmarks" / template_name
        return _load_yaml(template_path)

    if scenario == "retrieval_embedding_benchmark":
        template_path = _REPO_ROOT / "examples" / "benchmarks" / "embedding_accuracy_en_scifact.contract.yaml"
        return _load_yaml(template_path)

    if scenario == "reranking_benchmark":
        template_path = _REPO_ROOT / "examples" / "benchmarks" / "reranking_zh_cmedqa.contract.yaml"
        return _load_yaml(template_path)

    raise ValueError(f"Unsupported advisor scenario: {scenario}")


def _load_benchmark_manifest(workspace: Path) -> dict[str, Any] | None:
    manifest_path = workspace / "data" / "benchmark_manifest.json"
    if not manifest_path.exists():
        return None
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _infer_scenario(workspace: Path, scenario: str | None, benchmark_manifest: dict[str, Any] | None) -> str:
    if scenario:
        return scenario

    if benchmark_manifest is not None:
        family = benchmark_manifest.get("scenario_family")
        if family == "retrieval_embedding":
            return "retrieval_embedding_benchmark"
        if family == "reranking":
            return "reranking_benchmark"

    if (workspace / "eval" / "run_eval.py").exists():
        return "faq_retrieval"
    if (workspace / "configs" / "embedding.yaml").exists():
        return "retrieval_embedding_benchmark"
    if (workspace / "configs" / "reranker.yaml").exists():
        return "reranking_benchmark"
    raise ValueError("Could not infer scenario. Pass --scenario explicitly.")


def _detect_eval_command(workspace: Path, scenario: str) -> str:
    if (workspace / "eval" / "run_eval.py").exists():
        return "python eval/run_eval.py --json"
    if (workspace / "eval" / "run_benchmark_eval.py").exists():
        return "python eval/run_benchmark_eval.py --json"
    if scenario == "faq_retrieval":
        return "python eval/run_eval.py --json"
    return "python eval/run_benchmark_eval.py --json"


def _detect_editable_scope(workspace: Path, scenario: str) -> list[str]:
    if scenario == "faq_retrieval":
        candidates = [
            "configs/retrieval.yaml",
            "configs/reranker.yaml",
            "configs/embedding_strategy.yaml",
        ]
    elif scenario == "retrieval_embedding_benchmark":
        candidates = [
            "configs/embedding.yaml",
            "configs/retrieval.yaml",
            "configs/query_processing.yaml",
        ]
    else:
        candidates = [
            "configs/retrieval.yaml",
            "configs/reranker.yaml",
            "configs/query_processing.yaml",
        ]
    return [candidate for candidate in candidates if (workspace / candidate).exists()]


def _detect_protected_scope(workspace: Path) -> list[str]:
    protected = ["data/", "eval/"]
    optional = [".env", "secrets/", "benchmark/"]
    for entry in optional:
        if (workspace / entry.rstrip("/")).exists():
            protected.append(entry)
    return protected


def _build_draft_contract(
    workspace: Path,
    scenario: str,
    benchmark_key: str | None,
    benchmark_manifest: dict[str, Any] | None,
) -> dict[str, Any]:
    payload = _load_template_payload(workspace, scenario, benchmark_key)
    payload["workspace"]["path"] = ".."
    payload["scenario"]["type"] = scenario
    payload["scenario"]["name"] = payload["scenario"].get("name") or f"Advisor Draft - {workspace.name}"
    payload["editable_scope"] = _detect_editable_scope(workspace, scenario)
    payload["protected_scope"] = _detect_protected_scope(workspace)
    payload["evaluation"]["command"] = _detect_eval_command(workspace, scenario)
    payload["version_control"]["enabled"] = False
    payload["version_control"]["create_branch"] = False
    payload["version_control"]["commit_accepted_changes"] = False

    if benchmark_manifest is not None:
        payload.setdefault("advisor_context", {})
        payload["advisor_context"]["benchmark_manifest"] = benchmark_manifest
    return payload


def _build_readiness_report(
    workspace: Path,
    scenario: str,
    metric_profile: str,
    draft_contract_path: Path,
    benchmark_key: str | None,
    benchmark_manifest: dict[str, Any] | None,
) -> dict[str, Any]:
    required_files = _SCENARIO_REQUIRED_FILES[scenario]
    existing_files = [path for path in required_files if (workspace / path).exists()]
    missing_files = [path for path in required_files if not (workspace / path).exists()]
    detected_eval_command = _detect_eval_command(workspace, scenario)
    editable_scope = _detect_editable_scope(workspace, scenario)

    ready_for_validate = len(editable_scope) > 0 and len(missing_files) == 0
    ready_for_run = ready_for_validate and (
        (workspace / detected_eval_command.split()[1]).exists() if len(detected_eval_command.split()) > 1 else False
    )

    next_actions: list[str] = []
    if missing_files:
        next_actions.extend([f"Create or restore missing required file: {path}" for path in missing_files])
    else:
        next_actions.append(f"Validate the generated draft contract: python -m auto_optimize.cli validate {draft_contract_path}")
        next_actions.append(f"Run the draft contract after validation: python -m auto_optimize.cli run {draft_contract_path}")

    return {
        "status": "ready" if ready_for_run else "needs_attention",
        "scenario_type": scenario,
        "recommended_metric_profile": metric_profile,
        "metric_template_path": f"examples/metric_templates/{metric_profile}.yaml",
        "workspace_path": str(workspace),
        "draft_contract_path": str(draft_contract_path),
        "benchmark_key": benchmark_key,
        "benchmark_manifest": benchmark_manifest,
        "required_files": required_files,
        "existing_files": existing_files,
        "missing_files": missing_files,
        "editable_scope_detected": editable_scope,
        "protected_scope_detected": _detect_protected_scope(workspace),
        "evaluation_command_detected": detected_eval_command,
        "ready_for_validate": ready_for_validate,
        "ready_for_run": ready_for_run,
        "next_actions": next_actions,
    }


def run_advisor(workspace_arg: str | Path, scenario: str | None = None) -> AdvisorResult:
    workspace = Path(workspace_arg).resolve()
    if not workspace.exists() or not workspace.is_dir():
        raise ValueError(f"Workspace does not exist or is not a directory: {workspace}")

    benchmark_manifest = _load_benchmark_manifest(workspace)
    benchmark_key = None if benchmark_manifest is None else benchmark_manifest.get("dataset_key")
    resolved_scenario = _infer_scenario(workspace, scenario, benchmark_manifest)
    metric_profile = _SCENARIO_TO_PROFILE[resolved_scenario]

    output_dir = workspace / "auto_optimize_outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    draft_contract_path = output_dir / "optimization.contract.draft.yaml"
    readiness_report_path = output_dir / "readiness_report.json"

    draft_contract = _build_draft_contract(workspace, resolved_scenario, benchmark_key, benchmark_manifest)
    _write_yaml(draft_contract_path, draft_contract)

    readiness_report = _build_readiness_report(
        workspace=workspace,
        scenario=resolved_scenario,
        metric_profile=metric_profile,
        draft_contract_path=draft_contract_path,
        benchmark_key=benchmark_key,
        benchmark_manifest=benchmark_manifest,
    )
    readiness_report_path.write_text(
        json.dumps(readiness_report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return AdvisorResult(
        draft_contract_path=draft_contract_path,
        readiness_report_path=readiness_report_path,
        readiness_report=readiness_report,
    )
