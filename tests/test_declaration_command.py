from __future__ import annotations

import json
import os
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


def test_declare_command_prints_remediation_for_invalid_declaration(tmp_path: Path, capsys) -> None:
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

    exit_code = main(["declare", str(declaration_path)])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Declaration validation failed." in captured.out
    assert "objective.description" in captured.out
    assert "Next step: fix the declaration fields above" in captured.out


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


def test_declaration_to_contract_maps_env_var_variable(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    declaration_path = tmp_path / "env-var.declaration.yaml"
    declaration_path.write_text(
        "\n".join(
            [
                "workspace:",
                "  path: workspace",
                "objective:",
                '  description: "Tune an env-driven runtime flag."',
                "variables:",
                "  - name: mode",
                "    kind: env_var",
                "    target: AUTO_OPT_MODE",
                '    values: ["baseline", "turbo"]',
                "evaluation:",
                '  command: "python eval/run_eval.py --json"',
                "  metrics_source: stdout_json",
                "comparison:",
                "  primary_metric: top1_accuracy",
                "  direction: maximize",
                "safety:",
                "  editable:",
                "    - env:AUTO_OPT_MODE",
                "  protected:",
                "    - eval/",
                "",
            ]
        ),
        encoding="utf-8",
    )

    declaration = load_declaration(declaration_path)
    contract_data = declaration_to_contract_data(declaration, tmp_path / "generated.contract.yaml")

    assert contract_data["search_space"]["mode"]["mapping"]["type"] == "env_var"
    assert contract_data["search_space"]["mode"]["mapping"]["file"] == "AUTO_OPT_MODE"
    assert "path" not in contract_data["search_space"]["mode"]["mapping"]
    assert contract_data["editable_scope"] == ["env:AUTO_OPT_MODE"]


def test_declaration_to_contract_maps_cli_arg_variable(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    declaration_path = tmp_path / "cli-arg.declaration.yaml"
    declaration_path.write_text(
        "\n".join(
            [
                "workspace:",
                "  path: workspace",
                "objective:",
                '  description: "Tune a CLI-driven runtime mode."',
                "variables:",
                "  - name: mode",
                "    kind: cli_arg",
                "    target: --mode",
                '    values: ["baseline", "turbo"]',
                "evaluation:",
                '  command: "python eval/run_eval.py --json"',
                "  metrics_source: stdout_json",
                "comparison:",
                "  primary_metric: top1_accuracy",
                "  direction: maximize",
                "safety:",
                "  editable:",
                "    - cmd_arg:--mode",
                "  protected:",
                "    - eval/",
                "",
            ]
        ),
        encoding="utf-8",
    )

    declaration = load_declaration(declaration_path)
    contract_data = declaration_to_contract_data(declaration, tmp_path / "generated.contract.yaml")

    assert contract_data["search_space"]["mode"]["mapping"]["type"] == "cli_arg"
    assert contract_data["search_space"]["mode"]["mapping"]["file"] == "--mode"
    assert "path" not in contract_data["search_space"]["mode"]["mapping"]
    assert contract_data["editable_scope"] == ["cmd_arg:--mode"]


def test_declaration_to_contract_maps_csv_with_summary_evaluation(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    declaration_path = tmp_path / "csv-summary.declaration.yaml"
    declaration_path.write_text(
        "\n".join(
            [
                "workspace:",
                "  path: workspace",
                "objective:",
                '  description: "Parse CSV summary metrics."',
                "variables:",
                "  - name: top_k",
                "    kind: yaml_path",
                "    target: configs/retrieval.yaml",
                "    path: retrieval.top_k",
                "    values: [5, 10]",
                "evaluation:",
                '  command: "python eval/run_eval.py"',
                "  metrics_source: csv_with_summary",
                "  metrics_path: reports/summary.csv",
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
    contract_data = declaration_to_contract_data(declaration, tmp_path / "generated.contract.yaml")

    assert contract_data["evaluation"]["output_format"] == "csv_with_summary"
    assert contract_data["evaluation"]["output_file"] == "reports/summary.csv"


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
    assert summary["asset_context"]["declaration_input"]["present"] is True
    assert summary["asset_context"]["declaration_input"]["path"] == str(declaration_path.resolve())
    assert summary["asset_context"]["generated_contract"]["scenario_type"] == "generic_declaration"
    assert len(summary["adapter_provenance"]) == 1
    assert summary["adapter_provenance"][0]["declaration_source"] == str(declaration_path.resolve())
    assert summary["decision_rationale_summary"]["accepted_reason_count"] >= 1
    assert {entry["flag"] for entry in summary["risk_flags"]} >= {
        "generated_code",
        "metrics_parsing",
        "external_eval_command",
    }
    assert summary["generated_adapters"][0]["kind"] == "metrics_parser"
    assert generated_dir.exists()
    assert any(path.name == "metrics_parser_key_value_lines.py" for path in generated_dir.iterdir())
    assert "Asset Provenance" in report
    assert "Adapter Provenance" in report
    assert "Risk Flags" in report
    assert "Decision Rationale Summary" in report
    assert "Generated Adapters" in report


def test_env_var_declaration_runs_through_declare_validate_and_run(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    shutil.copytree(SOURCE_WORKSPACE, workspace)
    (workspace / "eval" / "run_eval.py").write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "from __future__ import annotations",
                "",
                "import json",
                "import os",
                "",
                'mode = os.environ.get("AUTO_OPT_MODE", "baseline")',
                "metrics = {",
                '    "top1_accuracy": 0.910 if mode == "turbo" else 0.870,',
                '    "latency_ms": 120 if mode == "turbo" else 140,',
                '    "all_tests_pass": True,',
                "}",
                "print(json.dumps(metrics))",
                "",
            ]
        ),
        encoding="utf-8",
    )

    declaration_path = tmp_path / "env-var.declaration.yaml"
    declaration_path.write_text(
        "\n".join(
            [
                "workspace:",
                "  path: workspace",
                "objective:",
                '  description: "Tune env-var based evaluation behavior."',
                "variables:",
                "  - name: mode",
                "    kind: env_var",
                "    target: AUTO_OPT_MODE",
                '    values: ["baseline", "turbo"]',
                "evaluation:",
                '  command: "python eval/run_eval.py --json"',
                "  metrics_source: stdout_json",
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
                "    - env:AUTO_OPT_MODE",
                "  protected:",
                "    - eval/",
                "    - data/",
                "budget:",
                "  max_experiments: 2",
                "",
            ]
        ),
        encoding="utf-8",
    )

    contract_path = tmp_path / "env-var.contract.yaml"
    original_value = os.environ.pop("AUTO_OPT_MODE", None)

    try:
        assert main(["declare", str(declaration_path), "--output", str(contract_path)]) == 0
        assert main(["validate", str(contract_path)]) == 0
        assert main(["run", str(contract_path)]) == 0

        summary = json.loads((workspace / "auto_optimize_outputs" / "run_summary.json").read_text(encoding="utf-8"))
        report = (workspace / "auto_optimize_outputs" / "optimization_report.md").read_text(encoding="utf-8")

        assert summary["best_metrics"]["top1_accuracy"] == 0.91
        assert summary["accepted_experiments"] >= 1
        assert summary["asset_context"]["declaration_input"]["path"] == str(declaration_path.resolve())
        assert summary["risk_flags"] == []
        assert summary["adapter_provenance"] == []
        assert "Decision Rationale Summary" in report
    finally:
        if original_value is None:
            os.environ.pop("AUTO_OPT_MODE", None)


def test_cli_arg_declaration_runs_through_declare_validate_and_run(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    shutil.copytree(SOURCE_WORKSPACE, workspace)
    (workspace / "eval" / "run_eval.py").write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "from __future__ import annotations",
                "",
                "import argparse",
                "import json",
                "",
                "parser = argparse.ArgumentParser()",
                'parser.add_argument("--json", action="store_true")',
                'parser.add_argument("--mode", default="baseline")',
                "args = parser.parse_args()",
                "metrics = {",
                '    "top1_accuracy": 0.910 if args.mode == "turbo" else 0.870,',
                '    "latency_ms": 120 if args.mode == "turbo" else 140,',
                '    "all_tests_pass": True,',
                "}",
                "print(json.dumps(metrics))",
                "",
            ]
        ),
        encoding="utf-8",
    )

    declaration_path = tmp_path / "cli-arg.declaration.yaml"
    declaration_path.write_text(
        "\n".join(
            [
                "workspace:",
                "  path: workspace",
                "objective:",
                '  description: "Tune CLI-driven evaluation behavior."',
                "variables:",
                "  - name: mode",
                "    kind: cli_arg",
                "    target: --mode",
                '    values: ["baseline", "turbo"]',
                "evaluation:",
                '  command: "python eval/run_eval.py --json"',
                "  metrics_source: stdout_json",
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
                "    - cmd_arg:--mode",
                "  protected:",
                "    - eval/",
                "    - data/",
                "budget:",
                "  max_experiments: 2",
                "",
            ]
        ),
        encoding="utf-8",
    )

    contract_path = tmp_path / "cli-arg.contract.yaml"

    assert main(["declare", str(declaration_path), "--output", str(contract_path)]) == 0
    assert main(["validate", str(contract_path)]) == 0
    assert main(["run", str(contract_path)]) == 0

    summary = json.loads((workspace / "auto_optimize_outputs" / "run_summary.json").read_text(encoding="utf-8"))
    report = (workspace / "auto_optimize_outputs" / "optimization_report.md").read_text(encoding="utf-8")

    assert summary["best_metrics"]["top1_accuracy"] == 0.91
    assert summary["accepted_experiments"] >= 1
    assert summary["asset_context"]["declaration_input"]["path"] == str(declaration_path.resolve())
    assert summary["accepted_candidates"][0]["changes"][0]["file"] == "cmd_arg:--mode"
    assert summary["accepted_candidates"][0]["changes"][0]["path"] == "<cli_arg>"
    assert summary["risk_flags"] == []
    assert summary["adapter_provenance"] == []
    assert "Decision Rationale Summary" in report


def test_csv_summary_declaration_runs_through_declare_validate_and_run(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    shutil.copytree(SOURCE_WORKSPACE, workspace)
    (workspace / "eval" / "run_eval.py").write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "from __future__ import annotations",
                "",
                "from pathlib import Path",
                "import yaml",
                "",
                'retrieval = yaml.safe_load(Path("configs/retrieval.yaml").read_text(encoding="utf-8"))["retrieval"]',
                'top_k = retrieval["top_k"]',
                'summary_path = Path("reports/summary.csv")',
                "summary_path.parent.mkdir(parents=True, exist_ok=True)",
                'summary_path.write_text("top1_accuracy,latency_ms,all_tests_pass\\n" + ("0.910,120,true\\n" if top_k == 20 else "0.870,140,true\\n"), encoding="utf-8")',
                "",
            ]
        ),
        encoding="utf-8",
    )

    declaration_path = tmp_path / "csv-summary.declaration.yaml"
    declaration_path.write_text(
        "\n".join(
            [
                "workspace:",
                "  path: workspace",
                "objective:",
                '  description: "Tune config with CSV summary metrics."',
                "variables:",
                "  - name: top_k",
                "    kind: yaml_path",
                "    target: configs/retrieval.yaml",
                "    path: retrieval.top_k",
                "    values: [10, 20]",
                "evaluation:",
                '  command: "python eval/run_eval.py"',
                "  metrics_source: csv_with_summary",
                "  metrics_path: reports/summary.csv",
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
                "budget:",
                "  max_experiments: 2",
                "",
            ]
        ),
        encoding="utf-8",
    )

    contract_path = tmp_path / "csv-summary.contract.yaml"

    assert main(["declare", str(declaration_path), "--output", str(contract_path)]) == 0
    assert main(["validate", str(contract_path)]) == 0
    assert main(["run", str(contract_path)]) == 0

    summary = json.loads((workspace / "auto_optimize_outputs" / "run_summary.json").read_text(encoding="utf-8"))
    report = (workspace / "auto_optimize_outputs" / "optimization_report.md").read_text(encoding="utf-8")

    assert summary["best_metrics"]["top1_accuracy"] == 0.91
    assert summary["accepted_experiments"] >= 1
    assert summary["asset_context"]["declaration_input"]["path"] == str(declaration_path.resolve())
    assert summary["risk_flags"] == []
    assert summary["adapter_provenance"] == []
    assert "Decision Rationale Summary" in report
