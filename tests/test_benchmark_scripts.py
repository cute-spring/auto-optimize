from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_download_script_can_materialize_workspace_from_manifest(tmp_path: Path) -> None:
    downloads_dir = tmp_path / "downloads"
    workspace_dir = tmp_path / "materialized"

    completed = subprocess.run(
        [
            "python",
            "scripts/download_benchmark_dataset.py",
            "--dataset",
            "du_retrieval",
            "--manifest-only",
            "--output-dir",
            str(downloads_dir),
            "--materialize-workspace",
            "--workspace-dir",
            str(workspace_dir),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert (downloads_dir / "du_retrieval.manifest.json").exists()
    assert (workspace_dir / "du_retrieval" / "optimization.contract.yaml").exists()
    assert (workspace_dir / "du_retrieval" / "workspace" / "data" / "benchmark_manifest.json").exists()


def test_export_script_generates_normalized_layout_from_saved_hf_dataset(tmp_path: Path) -> None:
    from datasets import Dataset, DatasetDict  # type: ignore

    raw_dir = tmp_path / "hf_saved"
    dataset = DatasetDict(
        {
            "corpus": Dataset.from_dict({"id": ["d1"], "title": ["Reset"], "text": ["Reset password help"]}),
            "queries": Dataset.from_dict({"id": ["q1"], "text": ["reset password"]}),
            "qrels": Dataset.from_dict({"query_id": ["q1"], "doc_id": ["d1"], "score": [1]}),
        }
    )
    dataset.save_to_disk(str(raw_dir))

    completed = subprocess.run(
        [
            "python",
            "scripts/export_benchmark_dataset.py",
            "--dataset",
            "du_retrieval",
            "--dataset-dir",
            str(raw_dir),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    export_dir = raw_dir / "auto_optimize_export"
    assert (export_dir / "corpus.jsonl").exists()
    assert (export_dir / "queries.jsonl").exists()
    assert (export_dir / "qrels.json").exists()
    manifest = json.loads((export_dir / "auto_optimize_export_manifest.json").read_text(encoding="utf-8"))
    assert manifest["dataset_key"] == "du_retrieval"
