from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from auto_optimize.scenario_packs.benchmark_materializer import materialize_benchmark_workspace


DATASETS = {
    "beir_scifact": {
        "category": "retrieval",
        "language": "en",
        "download_mode": "manual",
        "source": "https://github.com/beir-cellar/beir/wiki/Datasets-available",
        "note": "Use BEIR tooling to download the SciFact dataset into a local benchmark workspace.",
    },
    "du_retrieval": {
        "category": "retrieval",
        "language": "zh",
        "download_mode": "huggingface",
        "hf_id": "mteb/DuRetrieval",
        "note": "Recommended default Chinese retrieval benchmark.",
    },
    "cmedqa_reranking": {
        "category": "reranking",
        "language": "zh",
        "download_mode": "huggingface",
        "hf_id": "mteb/CMedQAv2-reranking",
        "note": "Recommended default Chinese FAQ-like reranking benchmark.",
    },
    "t2_reranking": {
        "category": "reranking",
        "language": "zh",
        "download_mode": "huggingface",
        "hf_id": "mteb/T2Reranking",
        "note": "Stronger Chinese reranking benchmark for extended local evaluation.",
    },
    "miracl_retrieval": {
        "category": "retrieval",
        "language": "multilingual",
        "download_mode": "manual",
        "source": "https://github.com/project-miracl/miracl",
        "note": "Large multilingual retrieval benchmark; usually sample zh/en slices locally.",
    },
    "msmarco_passage_reranking": {
        "category": "reranking",
        "language": "en",
        "download_mode": "manual",
        "source": "https://microsoft.github.io/msmarco/Datasets.html",
        "note": "Heavyweight English reranking benchmark with non-commercial research terms.",
    },
}


def _require_datasets():
    try:
        from datasets import load_dataset  # type: ignore
    except ImportError as exc:  # pragma: no cover - exercised through CLI behavior
        raise SystemExit(
            "The 'datasets' package is required for Hugging Face downloads. "
            "Install it first, for example: pip install datasets"
        ) from exc
    return load_dataset


def list_datasets() -> int:
    for key, meta in DATASETS.items():
        print(f"{key}: {meta['category']} / {meta['language']} / {meta['download_mode']}")
    return 0


def write_manifest(dataset_key: str, output_dir: Path) -> int:
    meta = DATASETS[dataset_key]
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / f"{dataset_key}.manifest.json"
    manifest_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote manifest: {manifest_path}")
    return 0


def download_dataset(dataset_key: str, output_dir: Path) -> int:
    meta = DATASETS[dataset_key]
    output_dir.mkdir(parents=True, exist_ok=True)

    if meta["download_mode"] == "manual":
        print(f"{dataset_key} requires manual download or external tooling.")
        print(f"Source: {meta['source']}")
        print(meta["note"])
        return 0

    load_dataset = _require_datasets()
    target_dir = output_dir / dataset_key
    target_dir.mkdir(parents=True, exist_ok=True)
    dataset = load_dataset(meta["hf_id"])
    dataset.save_to_disk(str(target_dir))
    print(f"Downloaded {dataset_key} to {target_dir}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Download or inspect public benchmark datasets for AutoOptimize.")
    parser.add_argument("--list", action="store_true", help="List supported benchmark datasets.")
    parser.add_argument("--dataset", choices=sorted(DATASETS.keys()), help="Dataset key to download or inspect.")
    parser.add_argument(
        "--output-dir",
        default="downloads/benchmarks",
        help="Output directory for dataset downloads or manifests.",
    )
    parser.add_argument(
        "--manifest-only",
        action="store_true",
        help="Write a local manifest instead of downloading the dataset.",
    )
    parser.add_argument(
        "--materialize-workspace",
        action="store_true",
        help="Generate a runnable benchmark workspace after downloading or writing the manifest.",
    )
    parser.add_argument(
        "--workspace-dir",
        default="materialized_benchmarks",
        help="Parent directory for generated benchmark workspaces when --materialize-workspace is used.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list:
        return list_datasets()
    if not args.dataset:
        parser.error("--dataset is required unless --list is used.")

    output_dir = Path(args.output_dir).resolve()
    dataset_path = output_dir / args.dataset
    if args.manifest_only:
        exit_code = write_manifest(args.dataset, output_dir)
        dataset_dir = None
    else:
        exit_code = download_dataset(args.dataset, output_dir)
        dataset_dir = dataset_path if dataset_path.exists() else None

    if exit_code != 0:
        return exit_code

    if args.materialize_workspace:
        result = materialize_benchmark_workspace(
            dataset_key=args.dataset,
            output_dir=Path(args.workspace_dir).resolve(),
            dataset_dir=dataset_dir,
        )
        print(f"Materialized contract: {result.contract_path}")
        print(f"Materialized workspace: {result.workspace_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
