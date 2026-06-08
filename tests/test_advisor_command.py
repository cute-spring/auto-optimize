from __future__ import annotations

import json
import shutil
from pathlib import Path

import yaml

from auto_optimize.cli import main
from auto_optimize.contract.loader import load_contract
from auto_optimize.contract.validator import validate_contract
from auto_optimize.declaration.loader import load_declaration
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
    declaration_path = output_dir / "optimization.declaration.draft.yaml"
    normalized_declaration_path = output_dir / "optimization.declaration.normalized.yaml"
    draft_path = output_dir / "optimization.contract.draft.yaml"
    readiness_path = output_dir / "readiness_report.json"
    assert declaration_path.exists()
    assert normalized_declaration_path.exists()
    assert draft_path.exists()
    assert readiness_path.exists()

    readiness = json.loads(readiness_path.read_text(encoding="utf-8"))
    assert readiness["status"] == "ready"
    assert readiness["recommended_metric_profile"] == "faq_metrics"
    assert readiness["ready_for_run"] is True
    assert readiness["draft_declaration_path"] == str(declaration_path)
    assert readiness["normalized_declaration_path"] == str(normalized_declaration_path)
    assert readiness["declaration_first_next_actions"]
    assert readiness["declaration_gaps"]
    assert {gap["id"] for gap in readiness["declaration_gaps"]} >= {"review_draft_declaration"}
    assert readiness["readiness_scores"]["authoring_completeness"] == 100.0
    assert readiness["readiness_scores"]["execution_readiness"] == 100.0
    assert readiness["autofill_applied"]
    assert readiness["manual_decisions_required"]
    assert readiness["template_context"]["scenario_type"] == "faq_retrieval"
    assert readiness["reference_fixture_context"]["fixture_kind"] == "faq_reference_fixture"
    assert readiness["required_files"] == [
        "configs/retrieval.yaml",
        "configs/reranker.yaml",
        "configs/embedding_strategy.yaml",
        "eval/run_eval.py",
    ]

    declaration = load_declaration(declaration_path)
    normalized_declaration = load_declaration(normalized_declaration_path)
    assert declaration.objective.description.startswith("Improve top1_accuracy")
    assert declaration.workspace.path == ".."
    assert normalized_declaration.evaluation.timeout_seconds == 600
    assert normalized_declaration.comparison.decision_rule == "constrained_primary_metric"
    assert normalized_declaration.budget is not None
    assert normalized_declaration.budget.max_experiments == 10

    declared_contract_path = output_dir / "optimization.contract.generated.yaml"
    assert main(["declare", str(normalized_declaration_path), "--output", str(declared_contract_path)]) == 0

    contract = load_contract(draft_path)
    result = validate_contract(contract)
    assert result.valid
    assert result.baseline_metrics is not None

    declared_contract = load_contract(declared_contract_path)
    declared_result = validate_contract(declared_contract)
    assert declared_result.valid
    assert declared_contract.scenario.type == "generic_declaration"


def test_advisor_infers_benchmark_scenario_and_generates_valid_draft(tmp_path: Path) -> None:
    materialized = materialize_benchmark_workspace("du_retrieval", tmp_path)

    exit_code = main(["advisor", "--workspace", str(materialized.workspace_path)])

    assert exit_code == 0

    draft_path = materialized.workspace_path / "auto_optimize_outputs" / "optimization.contract.draft.yaml"
    readiness_path = materialized.workspace_path / "auto_optimize_outputs" / "readiness_report.json"
    readiness = json.loads(readiness_path.read_text(encoding="utf-8"))
    draft = yaml.safe_load(draft_path.read_text(encoding="utf-8"))
    declaration = yaml.safe_load(
        (materialized.workspace_path / "auto_optimize_outputs" / "optimization.declaration.draft.yaml").read_text(
            encoding="utf-8"
        )
    )
    normalized_declaration = yaml.safe_load(
        (materialized.workspace_path / "auto_optimize_outputs" / "optimization.declaration.normalized.yaml").read_text(
            encoding="utf-8"
        )
    )

    assert readiness["recommended_metric_profile"] == "embedding_metrics"
    assert readiness["benchmark_key"] == "du_retrieval"
    assert draft["workspace"]["path"] == ".."
    assert declaration["workspace"]["path"] == ".."
    assert normalized_declaration["evaluation"]["timeout_seconds"] == 600
    assert declaration["comparison"]["primary_metric"] == draft["metrics"]["primary"]["name"]
    assert readiness["readiness_scores"]["authoring_completeness"] == 100.0
    assert readiness["manual_decisions_required"]
    assert readiness["template_context"]["benchmark_key"] == "du_retrieval"
    assert readiness["reference_fixture_context"]["fixture_kind"] == "benchmark_reference_fixture"
    assert "eval/run_benchmark_eval.py" in readiness["required_files"]

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
    assert readiness["draft_declaration_path"].endswith("optimization.declaration.draft.yaml")
    assert readiness["normalized_declaration_path"].endswith("optimization.declaration.normalized.yaml")
    assert readiness["declaration_first_next_actions"]
    assert readiness["readiness_scores"]["execution_readiness"] < 100.0
    assert {gap["id"] for gap in readiness["declaration_gaps"]} >= {"missing_evaluation_script"}


def test_advisor_autofills_metrics_artifact_defaults_from_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    shutil.copytree(SOURCE_WORKSPACE, workspace)
    _reset_workspace_fixture(workspace)
    (workspace / "reports").mkdir(parents=True, exist_ok=True)
    (workspace / "reports" / "summary.csv").write_text("top1_accuracy,all_tests_pass\n0.91,true\n", encoding="utf-8")

    exit_code = main(["advisor", "--workspace", str(workspace), "--scenario", "faq_retrieval"])

    assert exit_code == 0

    normalized = yaml.safe_load(
        (workspace / "auto_optimize_outputs" / "optimization.declaration.normalized.yaml").read_text(encoding="utf-8")
    )
    readiness = json.loads((workspace / "auto_optimize_outputs" / "readiness_report.json").read_text(encoding="utf-8"))

    assert normalized["evaluation"]["metrics_source"] == "csv_with_summary"
    assert normalized["evaluation"]["metrics_path"] == "reports/summary.csv"
    assert any(entry["field"] == "evaluation.metrics_path" for entry in readiness["autofill_applied"])
