from __future__ import annotations

import json
import shutil
from pathlib import Path

import yaml

from auto_optimize.cli import main
from auto_optimize.contract.loader import load_contract
from auto_optimize.contract.validator import validate_contract
from auto_optimize.declaration.converter import declaration_to_contract_data
from auto_optimize.declaration.loader import DeclarationValidationError, load_declaration

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_DIR = ROOT / "examples" / "faq_retrieval"
SOURCE_WORKSPACE = EXAMPLE_DIR / "workspace"


def test_load_declaration_parses_minimal_fields(tmp_path: Path) -> None:
    declaration_path = tmp_path / "optimization.declaration.yaml"
    declaration_path.write_text(
        "\n".join(
            [
                "objective:",
                '  description: "Tune a generic config."',
                "variables:",
                "  - name: top_k",
                "    kind: yaml_path",
                "    target: configs/retrieval.yaml",
                "    path: retrieval.top_k",
                "    values: [5, 10, 20]",
                "evaluation:",
                '  command: "python eval/run_eval.py --json"',
                "  metrics_source: stdout_json",
                "comparison:",
                "  primary_metric: top1_accuracy",
                "  direction: maximize",
                "safety:",
                "  editable:",
                "    - configs/retrieval.yaml",
                "  protected:",
                "    - eval/",
                "",
            ]
        ),
        encoding="utf-8",
    )

    declaration = load_declaration(declaration_path)

    assert declaration.objective.description == "Tune a generic config."
    assert declaration.workspace.path == "."
    assert declaration.workspace_path == tmp_path.resolve()
    assert declaration.variables[0].name == "top_k"
    assert declaration.evaluation.metrics_source == "stdout_json"


def test_load_declaration_missing_required_fields_fails(tmp_path: Path) -> None:
    declaration_path = tmp_path / "broken.declaration.yaml"
    declaration_path.write_text(
        "\n".join(
            [
                "objective: {}",
                "variables: []",
                "evaluation:",
                '  command: "python eval/run_eval.py --json"',
                "comparison:",
                "  direction: maximize",
                "safety:",
                "  editable: []",
                "",
            ]
        ),
        encoding="utf-8",
    )

    try:
        load_declaration(declaration_path)
    except DeclarationValidationError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected declaration validation to fail.")

    assert "objective.description" in message
    assert "evaluation.metrics_source" in message
    assert "comparison.primary_metric" in message
    assert "Declaration must include at least one variable." in message


def test_declaration_to_contract_maps_generic_fields(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    declaration_path = tmp_path / "generic.declaration.yaml"
    declaration_path.write_text(
        "\n".join(
            [
                "workspace:",
                "  path: workspace",
                "objective:",
                '  description: "Improve config quality."',
                "variables:",
                "  - name: top_k",
                "    kind: yaml_path",
                "    target: configs/retrieval.yaml",
                "    path: retrieval.top_k",
                "    values: [5, 10, 20]",
                "  - name: thresholds",
                "    kind: json_path",
                "    target: configs/thresholds.json",
                "    path: retrieval.threshold",
                "    values: [0.7, 0.8]",
                "    create_if_missing: true",
                "evaluation:",
                '  command: "python eval/run_eval.py --json"',
                "  metrics_source: metrics_json",
                "  metrics_path: reports/metrics.json",
                "  timeout_seconds: 45",
                "comparison:",
                "  primary_metric: top1_accuracy",
                "  direction: maximize",
                "  min_improvement: 0.01",
                "  decision_rule: constrained_primary_metric",
                "  secondary_metrics:",
                "    - name: latency_ms",
                "      direction: minimize",
                "constraints:",
                "  latency_ms:",
                "    max: 200",
                "safety:",
                "  editable:",
                "    - configs/retrieval.yaml",
                "    - configs/thresholds.json",
                "  protected:",
                "    - eval/",
                "  secrets:",
                "    - .env",
                "budget:",
                "  max_experiments: 5",
                "  search_strategy: pairwise",
                "",
            ]
        ),
        encoding="utf-8",
    )

    declaration = load_declaration(declaration_path)
    contract_data = declaration_to_contract_data(declaration, tmp_path / "generated.contract.yaml")

    assert contract_data["scenario"]["type"] == "generic_declaration"
    assert contract_data["workspace"]["path"] == "workspace"
    assert contract_data["editable_scope"] == ["configs/retrieval.yaml", "configs/thresholds.json"]
    assert contract_data["protected_scope"] == ["eval/", ".env"]
    assert contract_data["search_space"]["top_k"]["mapping"]["type"] == "yaml_path"
    assert contract_data["search_space"]["thresholds"]["mapping"]["create_if_missing"] is True
    assert contract_data["evaluation"]["output_file"] == "reports/metrics.json"
    assert contract_data["metrics"]["primary"]["name"] == "top1_accuracy"
    assert contract_data["metrics"]["secondary"][0]["name"] == "latency_ms"
    assert contract_data["constraints"]["latency_ms"]["max"] == 200
    assert contract_data["run_policy"]["max_experiments"] == 5
    assert contract_data["run_policy"]["search_strategy"] == "pairwise"


def test_generated_contract_from_example_declaration_validates() -> None:
    declaration_path = ROOT / "examples" / "declarations" / "generic_config_optimization.declaration.yaml"
    declaration = load_declaration(declaration_path)
    contract_data = declaration_to_contract_data(declaration, ROOT / "tmp.generated.contract.yaml")

    contract_path = ROOT / "tmp.generated.contract.yaml"
    try:
        contract_path.write_text(yaml.safe_dump(contract_data, sort_keys=False), encoding="utf-8")
        contract = load_contract(contract_path)
        result = validate_contract(contract)
    finally:
        if contract_path.exists():
            contract_path.unlink()

    assert result.valid


def test_declare_command_writes_valid_contract(tmp_path: Path) -> None:
    declaration_path = ROOT / "examples" / "declarations" / "generic_config_optimization.declaration.yaml"
    output_path = tmp_path / "declared.contract.yaml"

    exit_code = main(["declare", str(declaration_path), "--output", str(output_path)])

    assert exit_code == 0
    assert output_path.exists()

    contract = load_contract(output_path)
    result = validate_contract(contract)
    assert result.valid


def test_generated_parser_declaration_runs_through_declare_validate_and_run(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    shutil.copytree(SOURCE_WORKSPACE, workspace)
    (workspace / "eval" / "run_eval.py").write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "from __future__ import annotations",
                "",
                'print("top1_accuracy: 0.901")',
                'print("latency_ms: 123")',
                'print("all_tests_pass: true")',
                "",
            ]
        ),
        encoding="utf-8",
    )

    declaration_path = tmp_path / "generated-parser.declaration.yaml"
    declaration_path.write_text(
        "\n".join(
            [
                "workspace:",
                "  path: workspace",
                "objective:",
                '  description: "Parse metrics from plain text output."',
                "variables:",
                "  - name: top_k",
                "    kind: yaml_path",
                "    target: configs/retrieval.yaml",
                "    path: retrieval.top_k",
                "    values: [5, 10]",
                "evaluation:",
                '  command: "python eval/run_eval.py"',
                "  metrics_source: generated_parser",
                "  parser_template: key_value_lines",
                "comparison:",
                "  primary_metric: top1_accuracy",
                "  direction: maximize",
                "constraints:",
                "  latency_ms:",
                "    max: 200",
                "  all_tests_pass:",
                "    required: true",
                "safety:",
                "  editable:",
                "    - configs/retrieval.yaml",
                "  protected:",
                "    - eval/",
                "    - data/",
                "adapter_generation:",
                "  allowed: true",
                "",
            ]
        ),
        encoding="utf-8",
    )

    contract_path = tmp_path / "generated-parser.contract.yaml"

    assert main(["declare", str(declaration_path), "--output", str(contract_path)]) == 0
    assert main(["validate", str(contract_path)]) == 0
    assert main(["run", str(contract_path)]) == 0

    summary = json.loads((workspace / "auto_optimize_outputs" / "run_summary.json").read_text(encoding="utf-8"))
    report = (workspace / "auto_optimize_outputs" / "optimization_report.md").read_text(encoding="utf-8")
    generated_dir = workspace / "auto_optimize_outputs" / "generated_adapters"

    assert summary["generated_adapters"]
    assert summary["generated_adapters"][0]["kind"] == "metrics_parser"
    assert generated_dir.exists()
    assert any(path.name == "metrics_parser_key_value_lines.py" for path in generated_dir.iterdir())
    assert "Generated Adapters" in report
