from __future__ import annotations

import json
import shutil
from pathlib import Path

import yaml

from auto_optimize.cli import main
from auto_optimize.contract.loader import load_contract
from auto_optimize.contract.validator import validate_contract

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

    contract = load_contract(generated_contract_path)
    result = validate_contract(contract)
    assert result.valid


def test_template_command_lists_available_scenarios_profiles_and_benchmarks(capsys) -> None:
    exit_code = main(["template", "--json"])

    assert exit_code == 0

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert "faq_retrieval" in payload["scenarios"]
    assert "faq_metrics" in payload["metric_profiles"]
    assert "du_retrieval" in payload["benchmark_datasets"]
