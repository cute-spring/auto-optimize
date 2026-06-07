from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True, slots=True)
class BenchmarkMaterializationResult:
    dataset_key: str
    contract_path: Path
    workspace_path: Path
    manifest_path: Path


@dataclass(frozen=True, slots=True)
class BenchmarkSpec:
    dataset_key: str
    template_name: str
    scenario_family: str
    workspace_dir_name: str
    retrieval_defaults: dict[str, Any]
    extra_config_files: dict[str, dict[str, Any]]
    eval_command: str = "python eval/run_benchmark_eval.py --json"


BENCHMARK_SPECS: dict[str, BenchmarkSpec] = {
    "beir_scifact": BenchmarkSpec(
        dataset_key="beir_scifact",
        template_name="embedding_accuracy_en_scifact.contract.yaml",
        scenario_family="retrieval_embedding",
        workspace_dir_name="scifact_benchmark",
        retrieval_defaults={"retrieval": {"top_k": 10}},
        extra_config_files={
            "configs/embedding.yaml": {
                "embedding": {
                    "model_name": "gte-base-en",
                    "query_instruction_mode": "none",
                }
            },
            "configs/provider.yaml": {
                "provider": {
                    "mode": "sample",
                    "model_name": None,
                    "allow_fallback_to_sample": True,
                }
            },
        },
    ),
    "du_retrieval": BenchmarkSpec(
        dataset_key="du_retrieval",
        template_name="embedding_accuracy_zh_duretrieval.contract.yaml",
        scenario_family="retrieval_embedding",
        workspace_dir_name="duretrieval_benchmark",
        retrieval_defaults={"retrieval": {"top_k": 10}},
        extra_config_files={
            "configs/embedding.yaml": {
                "embedding": {
                    "model_name": "gte-multilingual-base",
                }
            },
            "configs/provider.yaml": {
                "provider": {
                    "mode": "sample",
                    "model_name": None,
                    "allow_fallback_to_sample": True,
                }
            },
            "configs/query_processing.yaml": {
                "query": {
                    "template": "raw_query",
                    "multilingual_normalization": False,
                }
            },
        },
    ),
    "cmedqa_reranking": BenchmarkSpec(
        dataset_key="cmedqa_reranking",
        template_name="reranking_zh_cmedqa.contract.yaml",
        scenario_family="reranking",
        workspace_dir_name="cmedqa_reranking_benchmark",
        retrieval_defaults={"retrieval": {"initial_top_k": 100}},
        extra_config_files={
            "configs/provider.yaml": {
                "provider": {
                    "mode": "sample",
                    "model_name": None,
                    "allow_fallback_to_sample": True,
                }
            },
            "configs/reranker.yaml": {
                "reranker": {
                    "model_name": "gte-reranker-modernbert-base",
                    "top_n": 50,
                }
            },
            "configs/query_processing.yaml": {
                "query": {
                    "template": "raw_query",
                }
            },
        },
    ),
}


_EVAL_SCRIPT = """#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]


def _load_yaml(relative_path: str) -> dict:
    path = WORKSPACE_ROOT / relative_path
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _load_manifest() -> dict:
    path = WORKSPACE_ROOT / "data" / "benchmark_manifest.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _apply(metrics: dict, deltas: dict) -> None:
    for key, value in deltas.items():
        metrics[key] += value


def _round_metrics(metrics: dict) -> dict:
    rounded = {}
    for key, value in metrics.items():
        if isinstance(value, float):
            rounded[key] = round(value, 3)
        else:
            rounded[key] = value
    return rounded


def _evaluate_retrieval_embedding(dataset_key: str) -> dict:
    retrieval = _load_yaml("configs/retrieval.yaml").get("retrieval", {})
    embedding = _load_yaml("configs/embedding.yaml").get("embedding", {})
    query_config = _load_yaml("configs/query_processing.yaml").get("query", {})

    if dataset_key == "beir_scifact":
        metrics = {
            "ndcg_at_10": 0.632,
            "top1_accuracy": 0.54,
            "recall_at_10": 0.781,
            "recall_at_50": 0.913,
            "mrr": 0.601,
            "embed_query_latency_p95_ms": 28,
            "embed_doc_latency_ms": 3.4,
            "index_size_mb": 512,
            "embedding_dimension": 768,
        }
        model_adjustments = {
            "bge-base-en-v1.5": {"ndcg_at_10": 0.021, "top1_accuracy": 0.018, "recall_at_10": 0.013, "recall_at_50": 0.008, "mrr": 0.018, "embed_query_latency_p95_ms": 4, "index_size_mb": 64},
            "e5-base-v2": {"ndcg_at_10": 0.012, "top1_accuracy": 0.011, "recall_at_10": 0.008, "mrr": 0.01, "embed_query_latency_p95_ms": 2, "index_size_mb": 32},
            "gte-base-en": {},
        }
        instruction_adjustments = {
            "none": {},
            "retrieval_query_prefix": {"ndcg_at_10": 0.009, "top1_accuracy": 0.008, "recall_at_10": 0.006, "mrr": 0.008, "embed_query_latency_p95_ms": 1},
        }
        top_k_adjustments = {
            10: {},
            20: {"ndcg_at_10": 0.008, "top1_accuracy": 0.006, "recall_at_10": 0.01, "recall_at_50": 0.006, "mrr": 0.006, "embed_query_latency_p95_ms": 3},
            50: {"ndcg_at_10": 0.004, "top1_accuracy": 0.002, "recall_at_10": 0.016, "recall_at_50": 0.011, "mrr": 0.002, "embed_query_latency_p95_ms": 7},
        }
        _apply(metrics, model_adjustments.get(embedding.get("model_name", "gte-base-en"), {}))
        _apply(metrics, instruction_adjustments.get(embedding.get("query_instruction_mode", "none"), {}))
        _apply(metrics, top_k_adjustments.get(int(retrieval.get("top_k", 10)), {}))
    else:
        metrics = {
            "ndcg_at_10": 0.588,
            "top1_accuracy": 0.501,
            "recall_at_10": 0.744,
            "recall_at_50": 0.889,
            "mrr": 0.563,
            "embed_query_latency_p95_ms": 34,
            "embed_doc_latency_ms": 4.1,
            "index_size_mb": 768,
            "embedding_dimension": 1024,
        }
        model_adjustments = {
            "bge-large-zh-v1.5": {"ndcg_at_10": 0.023, "top1_accuracy": 0.019, "recall_at_10": 0.015, "recall_at_50": 0.009, "mrr": 0.017, "embed_query_latency_p95_ms": 5, "embed_doc_latency_ms": 0.5, "index_size_mb": 144},
            "gte-multilingual-base": {},
            "qwen3-embedding-4b": {"ndcg_at_10": 0.012, "top1_accuracy": 0.01, "recall_at_10": 0.008, "mrr": 0.009, "embed_query_latency_p95_ms": 11, "embed_doc_latency_ms": 1.2, "index_size_mb": 280, "embedding_dimension": 512},
        }
        query_adjustments = {
            "raw_query": {},
            "normalized_query": {"ndcg_at_10": 0.011, "top1_accuracy": 0.009, "recall_at_10": 0.007, "mrr": 0.008, "embed_query_latency_p95_ms": 1},
            "keyword_augmented_query": {"ndcg_at_10": 0.015, "top1_accuracy": 0.01, "recall_at_10": 0.012, "recall_at_50": 0.005, "mrr": 0.009, "embed_query_latency_p95_ms": 4},
        }
        top_k_adjustments = {
            10: {},
            20: {"ndcg_at_10": 0.009, "top1_accuracy": 0.006, "recall_at_10": 0.012, "recall_at_50": 0.007, "mrr": 0.006, "embed_query_latency_p95_ms": 3},
            50: {"ndcg_at_10": 0.005, "top1_accuracy": 0.002, "recall_at_10": 0.019, "recall_at_50": 0.012, "mrr": 0.003, "embed_query_latency_p95_ms": 8},
        }
        _apply(metrics, model_adjustments.get(embedding.get("model_name", "gte-multilingual-base"), {}))
        _apply(metrics, query_adjustments.get(query_config.get("template", "raw_query"), {}))
        _apply(metrics, top_k_adjustments.get(int(retrieval.get("top_k", 10)), {}))
        if bool(query_config.get("multilingual_normalization", False)):
            _apply(metrics, {"ndcg_at_10": 0.01, "top1_accuracy": 0.008, "recall_at_10": 0.006, "mrr": 0.008, "embed_query_latency_p95_ms": 2})

    metrics["embed_query_latency_p95_ms"] = int(metrics["embed_query_latency_p95_ms"])
    metrics["index_size_mb"] = int(metrics["index_size_mb"])
    metrics["embedding_dimension"] = int(metrics["embedding_dimension"])
    return _round_metrics(metrics)


def _evaluate_reranking() -> dict:
    retrieval = _load_yaml("configs/retrieval.yaml").get("retrieval", {})
    reranker = _load_yaml("configs/reranker.yaml").get("reranker", {})
    query_config = _load_yaml("configs/query_processing.yaml").get("query", {})

    metrics = {
        "mrr": 0.673,
        "top1_accuracy": 0.59,
        "ndcg_at_10": 0.701,
        "rerank_gain_over_retrieval": 0.081,
        "recovered_at_1_from_top10": 0.16,
        "candidate_depth_sensitivity": 0.84,
        "rerank_latency_p95_ms": 118,
        "latency_per_candidate_ms": 1.8,
    }
    model_adjustments = {
        "bge-reranker-v2-m3": {"mrr": 0.022, "top1_accuracy": 0.018, "ndcg_at_10": 0.017, "rerank_gain_over_retrieval": 0.014, "recovered_at_1_from_top10": 0.028, "candidate_depth_sensitivity": 0.01, "rerank_latency_p95_ms": 14, "latency_per_candidate_ms": 0.2},
        "qwen3-reranker-4b": {"mrr": 0.017, "top1_accuracy": 0.014, "ndcg_at_10": 0.013, "rerank_gain_over_retrieval": 0.01, "recovered_at_1_from_top10": 0.02, "candidate_depth_sensitivity": 0.008, "rerank_latency_p95_ms": 26, "latency_per_candidate_ms": 0.35},
        "gte-reranker-modernbert-base": {},
    }
    top_n_adjustments = {
        20: {"mrr": -0.012, "top1_accuracy": -0.009, "ndcg_at_10": -0.01, "rerank_gain_over_retrieval": -0.011, "recovered_at_1_from_top10": -0.02, "candidate_depth_sensitivity": -0.018, "rerank_latency_p95_ms": -26, "latency_per_candidate_ms": -0.3},
        50: {},
        100: {"mrr": 0.009, "top1_accuracy": 0.005, "ndcg_at_10": 0.007, "rerank_gain_over_retrieval": 0.006, "recovered_at_1_from_top10": 0.013, "candidate_depth_sensitivity": 0.016, "rerank_latency_p95_ms": 34, "latency_per_candidate_ms": 0.45},
    }
    query_adjustments = {
        "raw_query": {},
        "normalized_query": {"mrr": 0.012, "top1_accuracy": 0.009, "ndcg_at_10": 0.01, "rerank_gain_over_retrieval": 0.007, "recovered_at_1_from_top10": 0.014, "candidate_depth_sensitivity": 0.009, "rerank_latency_p95_ms": 2},
        "faq_style_query": {"mrr": 0.016, "top1_accuracy": 0.011, "ndcg_at_10": 0.012, "rerank_gain_over_retrieval": 0.009, "recovered_at_1_from_top10": 0.018, "candidate_depth_sensitivity": 0.012, "rerank_latency_p95_ms": 5},
    }
    initial_top_k_adjustments = {
        50: {"mrr": -0.013, "top1_accuracy": -0.01, "ndcg_at_10": -0.012, "rerank_gain_over_retrieval": -0.015, "recovered_at_1_from_top10": -0.021, "candidate_depth_sensitivity": -0.019},
        100: {},
        200: {"mrr": 0.008, "top1_accuracy": 0.005, "ndcg_at_10": 0.006, "rerank_gain_over_retrieval": 0.01, "recovered_at_1_from_top10": 0.017, "candidate_depth_sensitivity": 0.018, "rerank_latency_p95_ms": 9},
    }

    _apply(metrics, model_adjustments.get(reranker.get("model_name", "gte-reranker-modernbert-base"), {}))
    _apply(metrics, top_n_adjustments.get(int(reranker.get("top_n", 50)), {}))
    _apply(metrics, query_adjustments.get(query_config.get("template", "raw_query"), {}))
    _apply(metrics, initial_top_k_adjustments.get(int(retrieval.get("initial_top_k", 100)), {}))
    metrics["rerank_latency_p95_ms"] = int(metrics["rerank_latency_p95_ms"])
    return _round_metrics(metrics)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if not args.json:
        return 1

    manifest = _load_manifest()
    scenario_family = manifest["scenario_family"]
    if scenario_family == "retrieval_embedding":
        payload = _evaluate_retrieval_embedding(manifest["dataset_key"])
    elif scenario_family == "reranking":
        payload = _evaluate_reranking()
    else:
        raise SystemExit(f"Unsupported scenario_family: {scenario_family}")

    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _asset_dir() -> Path:
    return _repo_root() / "auto_optimize" / "scenario_packs" / "assets"


def _template_path(template_name: str) -> Path:
    return _repo_root() / "examples" / "benchmarks" / template_name


def _copy_sample_data(spec: BenchmarkSpec, workspace_path: Path) -> None:
    sample_root = _asset_dir() / "benchmark_samples" / spec.dataset_key
    if not sample_root.exists():
        return
    target_root = workspace_path / "data"
    target_root.mkdir(parents=True, exist_ok=True)
    for source in sample_root.rglob("*"):
        if not source.is_file():
            continue
        relative = source.relative_to(sample_root)
        destination = target_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)


def _supported_dataset_files(spec: BenchmarkSpec) -> tuple[list[str], list[str]]:
    if spec.scenario_family == "retrieval_embedding":
        return (
            ["corpus.jsonl", "queries.jsonl", "qrels.json"],
            ["query_expansions.json"],
        )
    if spec.scenario_family == "reranking":
        return (
            ["corpus.jsonl", "queries.jsonl", "qrels.json", "candidates.json"],
            ["query_expansions.json"],
        )
    raise ValueError(f"Unsupported scenario family: {spec.scenario_family}")


def _resolve_dataset_payload_root(dataset_dir: Path) -> Path:
    export_dir = dataset_dir / "auto_optimize_export"
    if export_dir.exists() and export_dir.is_dir():
        return export_dir
    data_dir = dataset_dir / "data"
    if data_dir.exists() and data_dir.is_dir():
        return data_dir
    return dataset_dir


def _copy_local_dataset_files(spec: BenchmarkSpec, dataset_dir: Path, workspace_path: Path) -> dict[str, Any]:
    source_root = _resolve_dataset_payload_root(dataset_dir)
    required_files, optional_files = _supported_dataset_files(spec)
    available_required = [name for name in required_files if (source_root / name).exists()]
    if len(available_required) != len(required_files):
        return {
            "used": False,
            "source_root": str(source_root),
            "missing_required_files": [name for name in required_files if name not in available_required],
            "copied_files": [],
        }

    copied_files: list[str] = []
    target_root = workspace_path / "data"
    target_root.mkdir(parents=True, exist_ok=True)
    for name in required_files + optional_files:
        source = source_root / name
        if not source.exists():
            continue
        destination = target_root / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        copied_files.append(name)

    return {
        "used": True,
        "source_root": str(source_root),
        "missing_required_files": [],
        "copied_files": copied_files,
    }


def _count_jsonl_rows(path: Path) -> int | None:
    if not path.exists():
        return None
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def _count_json_entries(path: Path) -> int | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return len(payload)
    if isinstance(payload, list):
        return len(payload)
    return None


def _summarize_materialized_data(workspace_path: Path) -> dict[str, int | None]:
    data_root = workspace_path / "data"
    return {
        "corpus_rows": _count_jsonl_rows(data_root / "corpus.jsonl"),
        "query_rows": _count_jsonl_rows(data_root / "queries.jsonl"),
        "qrels_queries": _count_json_entries(data_root / "qrels.json"),
        "candidate_queries": _count_json_entries(data_root / "candidates.json"),
    }


def _write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")


def _load_template(spec: BenchmarkSpec) -> dict[str, Any]:
    return yaml.safe_load(_template_path(spec.template_name).read_text(encoding="utf-8"))


def _build_manifest(
    spec: BenchmarkSpec,
    dataset_dir: Path | None,
    sample_limit: int | None,
    data_source: str,
    copied_files: list[str],
    source_root: str | None,
    missing_required_files: list[str],
    data_summary: dict[str, int | None],
) -> dict[str, Any]:
    return {
        "dataset_key": spec.dataset_key,
        "scenario_family": spec.scenario_family,
        "dataset_dir": None if dataset_dir is None else str(dataset_dir),
        "dataset_available_locally": dataset_dir is not None,
        "sample_limit": sample_limit,
        "data_source": data_source,
        "source_root": source_root,
        "copied_files": copied_files,
        "missing_required_files": missing_required_files,
        "data_summary": data_summary,
        "note": "This workspace was materialized for AutoOptimize benchmark validation and MVP run flows.",
    }


def _apply_contract_defaults(contract_data: dict[str, Any], spec: BenchmarkSpec) -> dict[str, Any]:
    contract_data["workspace"]["path"] = "workspace"
    contract_data["evaluation"]["command"] = spec.eval_command
    contract_data["version_control"]["enabled"] = False
    contract_data["version_control"]["create_branch"] = False
    contract_data["version_control"]["commit_accepted_changes"] = False
    return contract_data


def materialize_benchmark_workspace(
    dataset_key: str,
    output_dir: Path,
    dataset_dir: Path | None = None,
    sample_limit: int | None = None,
) -> BenchmarkMaterializationResult:
    spec = BENCHMARK_SPECS[dataset_key]
    root_dir = output_dir.resolve() / dataset_key
    workspace_path = root_dir / "workspace"
    workspace_path.mkdir(parents=True, exist_ok=True)

    for relative_path, payload in spec.extra_config_files.items():
        _write_yaml(workspace_path / relative_path, payload)
    _write_yaml(workspace_path / "configs" / "retrieval.yaml", spec.retrieval_defaults)

    local_copy_result = {
        "used": False,
        "source_root": None,
        "missing_required_files": [],
        "copied_files": [],
    }
    if dataset_dir is not None and dataset_dir.exists():
        local_copy_result = _copy_local_dataset_files(spec, dataset_dir, workspace_path)
    if not local_copy_result["used"]:
        _copy_sample_data(spec, workspace_path)

    manifest_path = workspace_path / "data" / "benchmark_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(
            _build_manifest(
                spec,
                dataset_dir,
                sample_limit,
                data_source="local_dataset_dir" if local_copy_result["used"] else "sample_assets",
                copied_files=local_copy_result["copied_files"],
                source_root=local_copy_result["source_root"],
                missing_required_files=local_copy_result["missing_required_files"],
                data_summary=_summarize_materialized_data(workspace_path),
            ),
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    eval_path = workspace_path / "eval" / "run_benchmark_eval.py"
    eval_path.parent.mkdir(parents=True, exist_ok=True)
    eval_path.write_text((_asset_dir() / "run_benchmark_eval_template.py").read_text(encoding="utf-8"), encoding="utf-8")

    readme_path = root_dir / "README.md"
    readme_path.write_text(
        "\n".join(
            [
                f"# {dataset_key}",
                "",
                "Materialized benchmark workspace for AutoOptimize.",
                "",
                f"- Contract: `./optimization.contract.yaml`",
                f"- Workspace: `./workspace`",
                f"- Dataset manifest: `./workspace/data/benchmark_manifest.json`",
                "",
                "Typical commands:",
                "",
                "```bash",
                "python -m auto_optimize.cli validate optimization.contract.yaml",
                "python -m auto_optimize.cli run optimization.contract.yaml",
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )

    contract_data = _apply_contract_defaults(_load_template(spec), spec)
    contract_path = root_dir / "optimization.contract.yaml"
    contract_path.write_text(yaml.safe_dump(contract_data, sort_keys=False, allow_unicode=True), encoding="utf-8")

    return BenchmarkMaterializationResult(
        dataset_key=dataset_key,
        contract_path=contract_path,
        workspace_path=workspace_path,
        manifest_path=manifest_path,
    )
