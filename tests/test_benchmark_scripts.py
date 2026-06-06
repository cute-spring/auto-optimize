from __future__ import annotations

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
