from __future__ import annotations

import json
from pathlib import Path

from auto_optimize.cli import main
from auto_optimize.contract.loader import load_contract
from auto_optimize.contract.validator import validate_contract
from auto_optimize.scenario_packs.benchmark_materializer import materialize_benchmark_workspace
from auto_optimize.scenario_packs.dataset_export import export_dataset_from_disk


def test_materialize_scifact_workspace_validates_and_runs(tmp_path: Path) -> None:
    result = materialize_benchmark_workspace("beir_scifact", tmp_path)

    contract = load_contract(result.contract_path)
    validation = validate_contract(contract)
    assert validation.valid
    assert validation.baseline_metrics is not None

    exit_code = main(["run", str(result.contract_path)])
    assert exit_code == 0

    output_dir = result.workspace_path / "auto_optimize_outputs"
    summary = json.loads((output_dir / "run_summary.json").read_text(encoding="utf-8"))
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))

    assert summary["scenario_type"] == "retrieval_embedding_benchmark"
    assert summary["accepted_experiments"] >= 1
    assert summary["memory"]["total_runs"] == 1
    assert summary["benchmark_context"]["dataset_key"] == "beir_scifact"
    assert summary["benchmark_context"]["data_source"] == "sample_assets"
    assert summary["benchmark_context"]["provider_mode"] == "sample"
    assert manifest["dataset_key"] == "beir_scifact"
    assert manifest["dataset_available_locally"] is False


def test_materialize_duretrieval_workspace_validates(tmp_path: Path) -> None:
    result = materialize_benchmark_workspace("du_retrieval", tmp_path, sample_limit=500)

    contract = load_contract(result.contract_path)
    validation = validate_contract(contract)
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))

    assert validation.valid
    assert validation.baseline_metrics is not None
    assert manifest["sample_limit"] == 500
    assert contract.evaluation.command == "python eval/run_benchmark_eval.py --json"
    assert contract.version_control.enabled is False
    assert (result.workspace_path / "configs" / "provider.yaml").exists()


def test_materialize_cmedqa_workspace_validates_and_runs(tmp_path: Path) -> None:
    dataset_dir = tmp_path / "mock_dataset"
    dataset_dir.mkdir(parents=True, exist_ok=True)

    result = materialize_benchmark_workspace("cmedqa_reranking", tmp_path, dataset_dir=dataset_dir)

    contract = load_contract(result.contract_path)
    validation = validate_contract(contract)
    assert validation.valid
    assert validation.baseline_metrics is not None

    exit_code = main(["run", str(result.contract_path)])
    assert exit_code == 0

    output_dir = result.workspace_path / "auto_optimize_outputs"
    summary = json.loads((output_dir / "run_summary.json").read_text(encoding="utf-8"))
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))

    assert summary["scenario_type"] == "reranking_benchmark"
    assert summary["accepted_experiments"] >= 1
    assert summary["best_metrics"]["mrr"] >= summary["baseline_metrics"]["mrr"]
    assert manifest["dataset_available_locally"] is True
    assert manifest["data_source"] == "sample_assets"


def test_materialize_workspace_prefers_supported_local_dataset_layout(tmp_path: Path) -> None:
    dataset_dir = tmp_path / "local_dataset"
    dataset_dir.mkdir(parents=True, exist_ok=True)
    (dataset_dir / "corpus.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"id": "d1", "title": "Reset password", "text": "How to reset password"}),
                json.dumps({"id": "d2", "title": "Invoice", "text": "Download invoice"}),
                "",
            ]
        ),
        encoding="utf-8",
    )
    (dataset_dir / "queries.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"id": "q1", "text": "reset password"}),
                "",
            ]
        ),
        encoding="utf-8",
    )
    (dataset_dir / "qrels.json").write_text(
        json.dumps({"q1": {"d1": 1}}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    result = materialize_benchmark_workspace("du_retrieval", tmp_path, dataset_dir=dataset_dir)
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    copied_corpus = (result.workspace_path / "data" / "corpus.jsonl").read_text(encoding="utf-8")

    assert manifest["data_source"] == "local_dataset_dir"
    assert manifest["copied_files"] == ["corpus.jsonl", "queries.jsonl", "qrels.json"]
    assert manifest["missing_required_files"] == []
    assert manifest["data_summary"]["corpus_rows"] == 2
    assert manifest["data_summary"]["query_rows"] == 1
    assert '"id": "d1"' in copied_corpus


def test_materialize_workspace_prefers_auto_optimize_export_inside_saved_dataset_root(tmp_path: Path) -> None:
    from datasets import Dataset, DatasetDict  # type: ignore

    dataset_root = tmp_path / "saved_dataset"
    DatasetDict({"dev": Dataset.from_dict({"_id": ["d1"], "text": ["reset help"], "title": ["Reset"]})}).save_to_disk(
        str(dataset_root / "corpus")
    )
    DatasetDict({"dev": Dataset.from_dict({"_id": ["q1"], "text": ["reset password"]})}).save_to_disk(
        str(dataset_root / "queries")
    )
    DatasetDict({"dev": Dataset.from_dict({"query-id": ["q1"], "corpus-id": ["d1"], "score": [1]})}).save_to_disk(
        str(dataset_root / "default")
    )
    export_dataset_from_disk("du_retrieval", dataset_root)

    result = materialize_benchmark_workspace("du_retrieval", tmp_path, dataset_dir=dataset_root)
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))

    assert manifest["data_source"] == "local_dataset_dir"
    assert manifest["source_root"].endswith("auto_optimize_export")
    assert manifest["data_summary"]["corpus_rows"] == 1


def test_sentence_transformers_provider_can_fallback_to_sample_mode(tmp_path: Path) -> None:
    result = materialize_benchmark_workspace("beir_scifact", tmp_path)
    provider_path = result.workspace_path / "configs" / "provider.yaml"
    provider_path.write_text(
        "\n".join(
            [
                "provider:",
                "  mode: sentence_transformers",
                "  model_name: sentence-transformers/all-MiniLM-L6-v2",
                "  allow_fallback_to_sample: true",
                "",
            ]
        ),
        encoding="utf-8",
    )

    exit_code = main(["run", str(result.contract_path)])
    assert exit_code == 0

    summary = json.loads((result.workspace_path / "auto_optimize_outputs" / "run_summary.json").read_text(encoding="utf-8"))
    assert summary["scenario_type"] == "retrieval_embedding_benchmark"
    assert summary["experiments_run"] >= 1


def test_cross_encoder_provider_can_fallback_to_sample_mode(tmp_path: Path) -> None:
    result = materialize_benchmark_workspace("cmedqa_reranking", tmp_path)
    provider_path = result.workspace_path / "configs" / "provider.yaml"
    provider_path.write_text(
        "\n".join(
            [
                "provider:",
                "  mode: cross_encoder",
                "  model_name: invalid/cross-encoder-model",
                "  allow_fallback_to_sample: true",
                "",
            ]
        ),
        encoding="utf-8",
    )

    exit_code = main(["run", str(result.contract_path)])
    assert exit_code == 0

    summary = json.loads((result.workspace_path / "auto_optimize_outputs" / "run_summary.json").read_text(encoding="utf-8"))
    assert summary["scenario_type"] == "reranking_benchmark"
    assert summary["experiments_run"] >= 1
