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


def test_build_command_generates_valid_contract_from_template(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    shutil.copytree(SOURCE_WORKSPACE, workspace)
    _reset_workspace_fixture(workspace)

    output_path = workspace / "contracts" / "generated.contract.yaml"
    exit_code = main(
        [
            "build",
            "--workspace",
            str(workspace),
            "--scenario",
            "faq_retrieval",
            "--metric-profile",
            "faq_metrics",
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 0
    assert output_path.exists()

    payload = yaml.safe_load(output_path.read_text(encoding="utf-8"))
    assert payload["workspace"]["path"] == ".."
    assert payload["builder_context"]["metric_profile"] == "faq_metrics"
    assert payload["builder_context"]["reference_fixture_context"]["fixture_kind"] == "faq_reference_fixture"
    assert payload["builder_context"]["reference_fixture_context"]["contract_template_path"] == (
        "examples/faq_retrieval/optimization.contract.yaml"
    )
    assert payload["builder_context"]["reference_fixture_context"]["metric_template_path"] == (
        "examples/metric_templates/faq_metrics.yaml"
    )

    contract = load_contract(output_path)
    result = validate_contract(contract)
    assert result.valid


def test_build_command_supports_minimal_style(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    shutil.copytree(SOURCE_WORKSPACE, workspace)
    _reset_workspace_fixture(workspace)

    output_path = workspace / "contracts" / "generated-minimal.contract.yaml"
    exit_code = main(
        [
            "build",
            "--workspace",
            str(workspace),
            "--scenario",
            "faq_retrieval",
            "--metric-profile",
            "faq_metrics",
            "--style",
            "minimal",
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 0
    payload = yaml.safe_load(output_path.read_text(encoding="utf-8"))
    assert "constraints" not in payload
    assert "run_policy" not in payload
    assert payload["builder_context"]["contract_style"] == "minimal"

    contract = load_contract(output_path)
    result = validate_contract(contract)
    assert result.valid


def test_guided_command_generates_contract_and_readiness_for_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    shutil.copytree(SOURCE_WORKSPACE, workspace)
    _reset_workspace_fixture(workspace)

    exit_code = main(["guided", "--workspace", str(workspace)])

    assert exit_code == 0

    readiness_path = workspace / "auto_optimize_outputs" / "readiness_report.json"
    generated_contract_path = workspace / "auto_optimize_outputs" / "optimization.contract.generated.yaml"
    assert readiness_path.exists()
    assert generated_contract_path.exists()

    readiness = json.loads(readiness_path.read_text(encoding="utf-8"))
    assert readiness["status"] == "ready"

    payload = yaml.safe_load(generated_contract_path.read_text(encoding="utf-8"))
    assert payload["scenario"]["type"] == "generic_declaration"
    assert payload["declaration_context"]["source_declaration"].endswith("optimization.declaration.normalized.yaml")

    contract = load_contract(generated_contract_path)
    result = validate_contract(contract)
    assert result.valid


def test_guided_command_defaults_to_minimal_style(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    shutil.copytree(SOURCE_WORKSPACE, workspace)
    _reset_workspace_fixture(workspace)

    exit_code = main(["guided", "--workspace", str(workspace)])

    assert exit_code == 0

    generated_contract_path = workspace / "auto_optimize_outputs" / "optimization.contract.generated.yaml"
    payload = yaml.safe_load(generated_contract_path.read_text(encoding="utf-8"))
    readiness = json.loads((workspace / "auto_optimize_outputs" / "readiness_report.json").read_text(encoding="utf-8"))

    assert payload["scenario"]["type"] == "generic_declaration"
    assert payload["constraints"] == {}
    assert "builder_context" not in payload
    assert readiness["recommended_contract_style"] == "minimal"
    assert readiness["normalized_declaration_path"].endswith("optimization.declaration.normalized.yaml")


def test_guided_command_prints_readiness_scores_and_gap_summary(tmp_path: Path, capsys) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "configs").mkdir(parents=True, exist_ok=True)
    (workspace / "eval").mkdir(parents=True, exist_ok=True)
    (workspace / "configs" / "retrieval.yaml").write_text("retrieval:\n  top_k: 10\n", encoding="utf-8")

    exit_code = main(["guided", "--workspace", str(workspace), "--scenario", "faq_retrieval"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Readiness scores:" in captured.out
    assert "Autofill applied:" in captured.out
    assert "Manual decisions required:" in captured.out
    assert "Top declaration gaps:" in captured.out
    assert "missing_evaluation_script" in captured.out


def test_guided_command_uses_declaration_first_even_with_metric_profile_override(tmp_path: Path, capsys) -> None:
    workspace = tmp_path / "workspace"
    shutil.copytree(SOURCE_WORKSPACE, workspace)
    _reset_workspace_fixture(workspace)

    exit_code = main(["guided", "--workspace", str(workspace), "--metric-profile", "faq_metrics"])

    assert exit_code == 0

    generated_contract_path = workspace / "auto_optimize_outputs" / "optimization.contract.generated.yaml"
    payload = yaml.safe_load(generated_contract_path.read_text(encoding="utf-8"))
    captured = capsys.readouterr()

    assert payload["scenario"]["type"] == "generic_declaration"
    assert "ignored in declaration-first guided mode" in captured.out


def test_guided_command_infers_benchmark_workspace_and_preserves_reference_fixture_context(tmp_path: Path) -> None:
    materialized = materialize_benchmark_workspace("du_retrieval", tmp_path)

    exit_code = main(["guided", "--workspace", str(materialized.workspace_path)])

    assert exit_code == 0

    generated_contract_path = materialized.workspace_path / "auto_optimize_outputs" / "optimization.contract.generated.yaml"
    readiness_path = materialized.workspace_path / "auto_optimize_outputs" / "readiness_report.json"
    payload = yaml.safe_load(generated_contract_path.read_text(encoding="utf-8"))
    readiness = json.loads(readiness_path.read_text(encoding="utf-8"))

    assert payload["scenario"]["type"] == "generic_declaration"
    assert payload["declaration_context"]["source_declaration"].endswith("optimization.declaration.normalized.yaml")
    assert readiness["reference_fixture_context"]["fixture_kind"] == "benchmark_reference_fixture"
    assert readiness["reference_fixture_context"]["benchmark_key"] == "du_retrieval"

    contract = load_contract(generated_contract_path)
    result = validate_contract(contract)
    assert result.valid


def test_guided_command_supports_custom_output_path_with_declaration_first_contract(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    shutil.copytree(SOURCE_WORKSPACE, workspace)
    _reset_workspace_fixture(workspace)

    output_path = workspace / "contracts" / "guided.contract.yaml"
    exit_code = main(["guided", "--workspace", str(workspace), "--output", str(output_path)])

    assert exit_code == 0
    assert output_path.exists()

    payload = yaml.safe_load(output_path.read_text(encoding="utf-8"))
    assert payload["scenario"]["type"] == "generic_declaration"
    assert payload["declaration_context"]["source_declaration"].endswith("optimization.declaration.normalized.yaml")

    contract = load_contract(output_path)
    result = validate_contract(contract)
    assert result.valid


def test_advisor_expanded_style_is_recorded_in_readiness_report(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    shutil.copytree(SOURCE_WORKSPACE, workspace)
    _reset_workspace_fixture(workspace)

    exit_code = main(["advisor", "--workspace", str(workspace), "--style", "expanded"])

    assert exit_code == 0

    readiness = json.loads((workspace / "auto_optimize_outputs" / "readiness_report.json").read_text(encoding="utf-8"))
    draft = yaml.safe_load((workspace / "auto_optimize_outputs" / "optimization.contract.draft.yaml").read_text(encoding="utf-8"))

    assert readiness["recommended_contract_style"] == "expanded"
    assert readiness["reference_fixture_context"]["fixture_kind"] == "faq_reference_fixture"
    assert draft["builder_context"]["contract_style"] == "expanded"
    assert "constraints" in draft


def test_template_command_lists_available_scenarios_profiles_and_benchmarks(capsys) -> None:
    exit_code = main(["template", "--json"])

    assert exit_code == 0

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert "faq_retrieval" in payload["scenarios"]
    assert "faq_retrieval" in payload["reference_fixtures"]
    assert "faq_metrics" in payload["metric_profiles"]
    assert "du_retrieval" in payload["benchmark_datasets"]
