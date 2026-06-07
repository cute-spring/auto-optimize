from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from auto_optimize.scenario_packs.benchmark_materializer import BENCHMARK_SPECS
from auto_optimize.shared.paths import to_posix_relative


@dataclass(frozen=True, slots=True)
class BuildResult:
    contract_path: Path
    scenario: str
    metric_profile: str
    benchmark_key: str | None
    contract_payload: dict[str, Any]


_REPO_ROOT = Path(__file__).resolve().parents[2]

SCENARIO_TO_PROFILE = {
    "faq_retrieval": "faq_metrics",
    "retrieval_embedding_benchmark": "embedding_metrics",
    "reranking_benchmark": "reranking_metrics",
}

SCENARIO_REQUIRED_FILES = {
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


def load_yaml_file(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def write_yaml_file(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")


def load_benchmark_manifest(workspace: Path) -> dict[str, Any] | None:
    manifest_path = workspace / "data" / "benchmark_manifest.json"
    if not manifest_path.exists():
        return None
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def infer_scenario(workspace: Path, scenario: str | None, benchmark_manifest: dict[str, Any] | None) -> str:
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


def detect_eval_command(workspace: Path, scenario: str) -> str:
    if (workspace / "eval" / "run_eval.py").exists():
        return "python eval/run_eval.py --json"
    if (workspace / "eval" / "run_benchmark_eval.py").exists():
        return "python eval/run_benchmark_eval.py --json"
    if scenario == "faq_retrieval":
        return "python eval/run_eval.py --json"
    return "python eval/run_benchmark_eval.py --json"


def detect_editable_scope(workspace: Path, scenario: str) -> list[str]:
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


def detect_protected_scope(workspace: Path) -> list[str]:
    protected = ["data/", "eval/"]
    optional = [".env", "secrets/", "benchmark/"]
    for entry in optional:
        if (workspace / entry.rstrip("/")).exists():
            protected.append(entry)
    return protected


def load_template_payload(scenario: str, benchmark_key: str | None) -> dict[str, Any]:
    if scenario == "faq_retrieval":
        template_path = _REPO_ROOT / "examples" / "faq_retrieval" / "optimization.contract.yaml"
        return load_yaml_file(template_path)

    if benchmark_key and benchmark_key in BENCHMARK_SPECS:
        template_name = BENCHMARK_SPECS[benchmark_key].template_name
        template_path = _REPO_ROOT / "examples" / "benchmarks" / template_name
        return load_yaml_file(template_path)

    if scenario == "retrieval_embedding_benchmark":
        template_path = _REPO_ROOT / "examples" / "benchmarks" / "embedding_accuracy_en_scifact.contract.yaml"
        return load_yaml_file(template_path)

    if scenario == "reranking_benchmark":
        template_path = _REPO_ROOT / "examples" / "benchmarks" / "reranking_zh_cmedqa.contract.yaml"
        return load_yaml_file(template_path)

    raise ValueError(f"Unsupported scenario template: {scenario}")


def load_metric_profile(metric_profile: str) -> dict[str, Any]:
    template_path = _REPO_ROOT / "examples" / "metric_templates" / f"{metric_profile}.yaml"
    if not template_path.exists():
        raise ValueError(f"Unknown metric profile: {metric_profile}")
    return load_yaml_file(template_path)


def list_available_templates() -> dict[str, Any]:
    return {
        "scenarios": sorted(SCENARIO_TO_PROFILE),
        "metric_profiles": sorted(path.stem for path in (_REPO_ROOT / "examples" / "metric_templates").glob("*.yaml")),
        "benchmark_datasets": sorted(BENCHMARK_SPECS),
        "default_metric_profiles": SCENARIO_TO_PROFILE,
    }


def _workspace_reference(workspace: Path, output_path: Path) -> str:
    relative = os.path.relpath(workspace, start=output_path.parent)
    return to_posix_relative(relative)


def build_contract_payload(
    workspace: Path,
    scenario: str,
    metric_profile: str,
    output_path: Path,
    benchmark_key: str | None = None,
    benchmark_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = load_template_payload(scenario, benchmark_key)
    metric_sections = load_metric_profile(metric_profile)

    payload["workspace"]["path"] = _workspace_reference(workspace, output_path)
    payload["scenario"]["type"] = scenario
    payload["scenario"]["name"] = payload["scenario"].get("name") or f"Built Contract - {workspace.name}"
    payload["editable_scope"] = detect_editable_scope(workspace, scenario)
    payload["protected_scope"] = detect_protected_scope(workspace)
    payload["evaluation"]["command"] = detect_eval_command(workspace, scenario)

    for key in ("metrics", "constraints", "decision_policy", "pareto", "report"):
        if key in metric_sections:
            payload[key] = metric_sections[key]

    payload.setdefault("builder_context", {})
    payload["builder_context"]["metric_profile"] = metric_profile
    if benchmark_key is not None:
        payload["builder_context"]["benchmark_key"] = benchmark_key
    if benchmark_manifest is not None:
        payload["builder_context"]["benchmark_manifest"] = benchmark_manifest
    return payload


def build_contract(
    workspace_arg: str | Path,
    scenario: str | None = None,
    metric_profile: str | None = None,
    output_path: str | Path | None = None,
    benchmark_key: str | None = None,
) -> BuildResult:
    workspace = Path(workspace_arg).resolve()
    if not workspace.exists() or not workspace.is_dir():
        raise ValueError(f"Workspace does not exist or is not a directory: {workspace}")

    benchmark_manifest = load_benchmark_manifest(workspace)
    resolved_benchmark_key = benchmark_key or (None if benchmark_manifest is None else benchmark_manifest.get("dataset_key"))
    resolved_scenario = infer_scenario(workspace, scenario, benchmark_manifest)
    resolved_metric_profile = metric_profile or SCENARIO_TO_PROFILE[resolved_scenario]

    if output_path is None:
        contract_path = workspace / "auto_optimize_outputs" / "optimization.contract.generated.yaml"
    else:
        contract_path = Path(output_path).resolve()

    contract_payload = build_contract_payload(
        workspace=workspace,
        scenario=resolved_scenario,
        metric_profile=resolved_metric_profile,
        output_path=contract_path,
        benchmark_key=resolved_benchmark_key,
        benchmark_manifest=benchmark_manifest,
    )
    write_yaml_file(contract_path, contract_payload)

    return BuildResult(
        contract_path=contract_path,
        scenario=resolved_scenario,
        metric_profile=resolved_metric_profile,
        benchmark_key=resolved_benchmark_key,
        contract_payload=contract_payload,
    )
