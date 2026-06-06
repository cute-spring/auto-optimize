from __future__ import annotations

import json
import shutil
from pathlib import Path

import yaml

from auto_optimize.cli import main
from auto_optimize.contract.loader import load_contract
from auto_optimize.contract.validator import validate_contract
from auto_optimize.scenario_packs.benchmark_materializer import materialize_benchmark_workspace

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_DIR = ROOT / "examples" / "faq_retrieval"
SOURCE_WORKSPACE = EXAMPLE_DIR / "workspace"


def _reset_workspace_fixture(workspace: Path) -> None:
    output_dir = workspace / "auto_optimize_outputs"
    if output_dir.exists():
        shutil.rmtree(output_dir)

    (workspace / "configs" / "retrieval.yaml").write_text(
        "retrieval:\n  top_k: 10\n  threshold: 0.82\n",
        encoding="utf-8",
    )
    (workspace / "configs" / "reranker.yaml").write_text("enabled: true\n", encoding="utf-8")
    (workspace / "configs" / "embedding_strategy.yaml").write_text(
        "\n".join(
            [
                "embedding:",
                "  faq_template: question_with_answer",
                "  query_template: normalized_query",
                "  multilingual_normalization: true",
                "  language_hint_mode: auto",
                "  faq_text_fields:",
                "    - title",
                "    - question",
                "    - answer",
                "  query_processing_steps:",
                "    - trim",
                "    - lowercase_ascii",
                "    - preserve_chinese",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_advisor_generates_valid_faq_draft_and_readiness_report(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    shutil.copytree(SOURCE_WORKSPACE, workspace)
    _reset_workspace_fixture(workspace)

    exit_code = main(["advisor", "--workspace", str(workspace), "--scenario", "faq_retrieval"])

    assert exit_code == 0

    output_dir = workspace / "auto_optimize_outputs"
    draft_path = output_dir / "optimization.contract.draft.yaml"
    readiness_path = output_dir / "readiness_report.json"
    assert draft_path.exists()
    assert readiness_path.exists()

    readiness = json.loads(readiness_path.read_text(encoding="utf-8"))
    assert readiness["status"] == "ready"
    assert readiness["recommended_metric_profile"] == "faq_metrics"
    assert readiness["ready_for_run"] is True

    contract = load_contract(draft_path)
    result = validate_contract(contract)
    assert result.valid
    assert result.baseline_metrics is not None


def test_advisor_infers_benchmark_scenario_and_generates_valid_draft(tmp_path: Path) -> None:
    materialized = materialize_benchmark_workspace("du_retrieval", tmp_path)

    exit_code = main(["advisor", "--workspace", str(materialized.workspace_path)])

    assert exit_code == 0

    draft_path = materialized.workspace_path / "auto_optimize_outputs" / "optimization.contract.draft.yaml"
    readiness_path = materialized.workspace_path / "auto_optimize_outputs" / "readiness_report.json"
    readiness = json.loads(readiness_path.read_text(encoding="utf-8"))
    draft = yaml.safe_load(draft_path.read_text(encoding="utf-8"))

    assert readiness["recommended_metric_profile"] == "embedding_metrics"
    assert readiness["benchmark_key"] == "du_retrieval"
    assert draft["workspace"]["path"] == ".."

    contract = load_contract(draft_path)
    result = validate_contract(contract)
    assert result.valid


def test_advisor_flags_missing_files_in_readiness_report(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "configs").mkdir(parents=True, exist_ok=True)
    (workspace / "eval").mkdir(parents=True, exist_ok=True)
    (workspace / "configs" / "retrieval.yaml").write_text("retrieval:\n  top_k: 10\n", encoding="utf-8")

    exit_code = main(["advisor", "--workspace", str(workspace), "--scenario", "faq_retrieval"])

    assert exit_code == 0
    readiness_path = workspace / "auto_optimize_outputs" / "readiness_report.json"
    readiness = json.loads(readiness_path.read_text(encoding="utf-8"))

    assert readiness["status"] == "needs_attention"
    assert readiness["ready_for_run"] is False
    assert "configs/reranker.yaml" in readiness["missing_files"]
    assert "eval/run_eval.py" in readiness["missing_files"]
