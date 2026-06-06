from __future__ import annotations

import json
from pathlib import Path

from auto_optimize.cli import main
from auto_optimize.contract.loader import load_contract
from auto_optimize.contract.validator import validate_contract
from auto_optimize.scenario_packs.benchmark_materializer import materialize_benchmark_workspace


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
