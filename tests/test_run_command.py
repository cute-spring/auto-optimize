from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import yaml

from auto_optimize.cli import main

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_DIR = ROOT / "examples" / "faq_retrieval"
SOURCE_WORKSPACE = EXAMPLE_DIR / "workspace"
SOURCE_CONTRACT = EXAMPLE_DIR / "optimization.contract.yaml"


def _run(cmd: list[str], cwd: Path) -> str:
    completed = subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True)
    return completed.stdout.strip()


def _init_git_repo(workspace: Path) -> None:
    _run(["git", "init"], cwd=workspace)
    _run(["git", "config", "user.name", "Auto Optimize Test"], cwd=workspace)
    _run(["git", "config", "user.email", "auto-optimize@example.com"], cwd=workspace)
    _run(["git", "add", "."], cwd=workspace)
    _run(["git", "commit", "-m", "initial"], cwd=workspace)


def _init_git_remote(tmp_path: Path, workspace: Path) -> Path:
    remote_path = tmp_path / "remote.git"
    _run(["git", "init", "--bare", str(remote_path)], cwd=tmp_path)
    _run(["git", "remote", "add", "origin", str(remote_path)], cwd=workspace)
    return remote_path


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


def _materialize_contract(tmp_path: Path, mutate=None) -> Path:
    workspace_copy = tmp_path / "workspace"
    shutil.copytree(SOURCE_WORKSPACE, workspace_copy)
    _reset_workspace_fixture(workspace_copy)

    with SOURCE_CONTRACT.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    data["workspace"]["path"] = "workspace"
    if mutate:
        mutate(data, workspace_copy)

    contract_path = tmp_path / "optimization.contract.yaml"
    contract_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return contract_path


def _write_key_value_eval_script(workspace: Path) -> None:
    (workspace / "eval" / "run_eval.py").write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "from __future__ import annotations",
                "",
                'print("top1_accuracy: 0.901")',
                'print("hit_at_3: 0.962")',
                'print("recall_at_10: 0.983")',
                'print("mrr: 0.782")',
                'print("hard_negative_error_rate: 0.046")',
                'print("embed_query_latency_p95_ms: 42")',
                'print("rerank_latency_p95_ms: 97")',
                'print("index_size_mb: 385")',
                'print("all_tests_pass: true")',
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_declaration(path: Path, lines: list[str]) -> Path:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_run_command_writes_baseline_artifacts(tmp_path: Path) -> None:
    contract_path = _materialize_contract(tmp_path)

    exit_code = main(["run", str(contract_path)])

    assert exit_code == 0

    output_dir = tmp_path / "workspace" / "auto_optimize_outputs"
    run_summary_path = output_dir / "run_summary.json"
    jsonl_path = output_dir / "experiment_log.jsonl"
    csv_path = output_dir / "experiment_log.csv"
    history_path = output_dir / "run_history.jsonl"
    best_run_path = output_dir / "best_run_snapshot.json"
    md_report_path = output_dir / "optimization_report.md"
    validation_report_path = output_dir / "contract_validation_report.md"
    pareto_frontier_path = output_dir / "pareto_frontier.json"
    pareto_snapshot_dir = output_dir / "pareto_frontier_snapshots"

    assert run_summary_path.exists()
    assert jsonl_path.exists()
    assert csv_path.exists()
    assert history_path.exists()
    assert best_run_path.exists()
    assert md_report_path.exists()
    assert validation_report_path.exists()
    assert pareto_frontier_path.exists()
    assert pareto_snapshot_dir.exists()

    summary = json.loads(run_summary_path.read_text(encoding="utf-8"))
    assert summary["status"] == "completed"
    assert summary["baseline_metrics"]["top1_accuracy"] == 0.892
    assert summary["best_metrics"]["top1_accuracy"] == 0.909
    assert summary["final_workspace_metrics"]["top1_accuracy"] == 0.909
    assert summary["constraints_satisfied"] is True
    assert summary["pareto_enabled"] is True
    assert len(summary["pareto_frontier"]) >= 1
    assert summary["experiments_run"] == 10
    assert summary["accepted_experiments"] == 4
    assert summary["rejected_experiments"] == 6
    assert summary["failed_evaluations"] == 0
    assert summary["memory"]["total_runs"] == 1
    assert summary["memory"]["current_run_is_historical_best"] is True
    assert len(summary["accepted_candidates"]) == 4
    assert summary["asset_context"]["declaration_input"]["present"] is False
    assert summary["asset_context"]["generated_contract"]["present"] is True
    assert summary["asset_context"]["generated_contract"]["scenario_type"] == "faq_retrieval"
    assert summary["asset_context"]["generated_adapters"]["count"] == 0
    assert summary["adapter_provenance"] == []
    assert summary["risk_flags"] == []
    assert summary["decision_rationale_summary"]["accepted_reason_count"] >= 1
    assert summary["decision_rationale_summary"]["rejected_reason_count"] >= 1
    assert summary["decision_rationale_summary"]["failed_evaluation_count"] == 0

    records = [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    history_records = [json.loads(line) for line in history_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    best_run = json.loads(best_run_path.read_text(encoding="utf-8"))
    assert len(records) == 11
    assert len(history_records) == 1
    assert best_run["best_primary_metric"] == 0.909
    assert records[0]["experiment_id"] == "baseline"
    assert records[0]["decision"] == "baseline"
    assert any(record["decision"] == "accepted" for record in records[1:])
    assert any(record["rollback_performed"] for record in records[1:])
    assert (pareto_snapshot_dir / "baseline" / "configs" / "retrieval.yaml").exists()

    report_text = md_report_path.read_text(encoding="utf-8")
    assert "Baseline Metrics" in report_text
    assert "Best Metrics" in report_text
    assert "Accepted Experiments" in report_text
    assert "Asset Provenance" in report_text
    assert "Adapter Provenance" in report_text
    assert "Risk Flags" in report_text
    assert "Decision Rationale Summary" in report_text
    assert "Pareto Frontier" in report_text
    assert "Experiment Memory" in report_text
    assert "top1_accuracy" in report_text

    retrieval_config = yaml.safe_load((tmp_path / "workspace" / "configs" / "retrieval.yaml").read_text(encoding="utf-8"))
    reranker_config = yaml.safe_load((tmp_path / "workspace" / "configs" / "reranker.yaml").read_text(encoding="utf-8"))
    embedding_config = yaml.safe_load(
        (tmp_path / "workspace" / "configs" / "embedding_strategy.yaml").read_text(encoding="utf-8")
    )

    assert retrieval_config["retrieval"]["top_k"] == 20
    assert retrieval_config["retrieval"]["threshold"] == 0.78
    assert reranker_config["enabled"] is True
    assert embedding_config["embedding"]["faq_template"] == "question_title_answer_bilingual"
    assert embedding_config["embedding"]["query_template"] == "bilingual_expansion"
    assert embedding_config["embedding"]["multilingual_normalization"] is True


def test_run_command_records_rejected_points_in_pareto_frontier(tmp_path: Path) -> None:
    contract_path = _materialize_contract(tmp_path)

    exit_code = main(["run", str(contract_path)])

    assert exit_code == 0

    output_dir = tmp_path / "workspace" / "auto_optimize_outputs"
    summary = json.loads((output_dir / "run_summary.json").read_text(encoding="utf-8"))
    pareto_snapshot_dir = output_dir / "pareto_frontier_snapshots"

    assert any(entry["decision"] == "rejected" for entry in summary["pareto_frontier"])
    rejected_entry = next(entry for entry in summary["pareto_frontier"] if entry["decision"] == "rejected")
    assert (pareto_snapshot_dir / rejected_entry["experiment_id"] / "metadata.json").exists()


def test_run_command_supports_pareto_frontier_decision_mode(tmp_path: Path) -> None:
    def mutate(data, workspace):
        data["decision_policy"]["mode"] = "pareto_frontier"

    contract_path = _materialize_contract(tmp_path, mutate=mutate)

    exit_code = main(["run", str(contract_path)])

    assert exit_code == 0

    output_dir = tmp_path / "workspace" / "auto_optimize_outputs"
    summary = json.loads((output_dir / "run_summary.json").read_text(encoding="utf-8"))

    assert summary["accepted_experiments"] >= 4
    assert summary["final_workspace_metrics"] != summary["baseline_metrics"]
    assert any(candidate["primary_metric_improvement"] < 0 for candidate in summary["accepted_candidates"])


def test_run_command_fails_when_validation_fails(tmp_path: Path, capsys) -> None:
    def mutate(data, workspace):
        data["metrics"]["primary"]["name"] = "missing_metric"

    contract_path = _materialize_contract(tmp_path, mutate=mutate)

    exit_code = main(["run", str(contract_path)])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Contract validation failed before run:" in captured.out
    assert "Hint:" in captured.out
    assert "Next step: run `python -m auto_optimize.cli validate" in captured.out


def test_run_command_prints_remediation_for_invalid_declaration(tmp_path: Path, capsys) -> None:
    declaration_path = _write_declaration(
        tmp_path / "broken.declaration.yaml",
        [
            "objective: {}",
            "variables: []",
            "evaluation:",
            '  command: "python eval/run_eval.py --json"',
            "comparison:",
            "  direction: maximize",
            "safety:",
            "  editable: []",
        ],
    )

    exit_code = main(["run", str(declaration_path)])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Declaration validation failed." in captured.out
    assert "objective.description" in captured.out
    assert "Next step: fix the declaration fields above, then rerun `run`" in captured.out


def test_run_command_accepts_generated_parser_declaration_path(tmp_path: Path, capsys) -> None:
    workspace = tmp_path / "workspace"
    shutil.copytree(SOURCE_WORKSPACE, workspace)
    _write_key_value_eval_script(workspace)
    declaration_path = _write_declaration(
        tmp_path / "generated-parser.declaration.yaml",
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
            "    values: [10, 20]",
            "evaluation:",
            '  command: "python eval/run_eval.py"',
            "  metrics_source: generated_parser",
            "  parser_template: key_value_lines",
            "comparison:",
            "  primary_metric: top1_accuracy",
            "  direction: maximize",
            "constraints:",
            "  all_tests_pass:",
            "    required: true",
            "safety:",
            "  editable:",
            "    - configs/retrieval.yaml",
            "  protected:",
            "    - eval/",
            "adapter_generation:",
            "  allowed: true",
            "budget:",
            "  max_experiments: 2",
        ],
    )

    exit_code = main(["run", str(declaration_path)])
    captured = capsys.readouterr()

    assert exit_code == 0
    summary = json.loads((workspace / "auto_optimize_outputs" / "run_summary.json").read_text(encoding="utf-8"))
    report = (workspace / "auto_optimize_outputs" / "optimization_report.md").read_text(encoding="utf-8")

    assert f"Source declaration: {declaration_path.resolve()}" in captured.out
    assert "Generated contract:" in captured.out
    assert summary["execution_mode"] == "declaration_native"
    assert summary["asset_context"]["generated_contract"]["execution_mode"] == "declaration_native"
    assert summary["asset_context"]["declaration_input"]["path"] == str(declaration_path.resolve())
    assert summary["generated_adapters"][0]["kind"] == "metrics_parser"
    assert "Execution mode: `declaration_native`" in report


def test_run_command_accepts_env_var_declaration_path(tmp_path: Path) -> None:
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
                "print(json.dumps({",
                '    "top1_accuracy": 0.910 if mode == "turbo" else 0.870,',
                '    "all_tests_pass": True,',
                "} ))".replace("} )", "})"),
                "",
            ]
        ),
        encoding="utf-8",
    )
    declaration_path = _write_declaration(
        tmp_path / "env-var.declaration.yaml",
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
            "  all_tests_pass:",
            "    required: true",
            "safety:",
            "  editable:",
            "    - env:AUTO_OPT_MODE",
            "  protected:",
            "    - eval/",
            "budget:",
            "  max_experiments: 2",
        ],
    )
    original_value = os.environ.pop("AUTO_OPT_MODE", None)

    try:
        assert main(["run", str(declaration_path)]) == 0
        summary = json.loads((workspace / "auto_optimize_outputs" / "run_summary.json").read_text(encoding="utf-8"))
        assert summary["execution_mode"] == "declaration_native"
        assert summary["best_metrics"]["top1_accuracy"] == 0.91
    finally:
        if original_value is None:
            os.environ.pop("AUTO_OPT_MODE", None)
        else:
            os.environ["AUTO_OPT_MODE"] = original_value


def test_run_command_accepts_cli_arg_declaration_path(tmp_path: Path) -> None:
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
                "print(json.dumps({",
                '    "top1_accuracy": 0.910 if args.mode == "turbo" else 0.870,',
                '    "all_tests_pass": True,',
                "} ))".replace("} )", "})"),
                "",
            ]
        ),
        encoding="utf-8",
    )
    declaration_path = _write_declaration(
        tmp_path / "cli-arg.declaration.yaml",
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
            "  all_tests_pass:",
            "    required: true",
            "safety:",
            "  editable:",
            "    - cmd_arg:--mode",
            "  protected:",
            "    - eval/",
            "budget:",
            "  max_experiments: 2",
        ],
    )

    assert main(["run", str(declaration_path)]) == 0
    summary = json.loads((workspace / "auto_optimize_outputs" / "run_summary.json").read_text(encoding="utf-8"))

    assert summary["execution_mode"] == "declaration_native"
    assert summary["best_metrics"]["top1_accuracy"] == 0.91
    assert summary["accepted_candidates"][0]["changes"][0]["file"] == "cmd_arg:--mode"


def test_run_command_accepts_csv_summary_declaration_path(tmp_path: Path) -> None:
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
                'summary_path.write_text("top1_accuracy,all_tests_pass\\n" + ("0.910,true\\n" if top_k == 20 else "0.870,true\\n"), encoding="utf-8")',
                "",
            ]
        ),
        encoding="utf-8",
    )
    declaration_path = _write_declaration(
        tmp_path / "csv-summary.declaration.yaml",
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
            "  all_tests_pass:",
            "    required: true",
            "safety:",
            "  editable:",
            "    - configs/retrieval.yaml",
            "  protected:",
            "    - eval/",
            "budget:",
            "  max_experiments: 2",
        ],
    )

    assert main(["run", str(declaration_path)]) == 0
    summary = json.loads((workspace / "auto_optimize_outputs" / "run_summary.json").read_text(encoding="utf-8"))

    assert summary["execution_mode"] == "declaration_native"
    assert summary["best_metrics"]["top1_accuracy"] == 0.91


def test_run_command_rolls_back_failed_evaluation(tmp_path: Path) -> None:
    def mutate(data, workspace):
        data["evaluation"]["command"] = "python eval/run_eval.py --json --fail-on-top-k 20"
        data["run_policy"]["max_experiments"] = 2
        data["run_policy"]["max_failed_evaluations"] = 1

    contract_path = _materialize_contract(tmp_path, mutate=mutate)

    exit_code = main(["run", str(contract_path)])

    assert exit_code == 0

    output_dir = tmp_path / "workspace" / "auto_optimize_outputs"
    summary = json.loads((output_dir / "run_summary.json").read_text(encoding="utf-8"))
    records = [
        json.loads(line)
        for line in (output_dir / "experiment_log.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    retrieval_config = yaml.safe_load((tmp_path / "workspace" / "configs" / "retrieval.yaml").read_text(encoding="utf-8"))

    assert summary["accepted_experiments"] == 0
    assert summary["rejected_experiments"] == 2
    assert summary["failed_evaluations"] == 1
    assert summary["memory"]["total_runs"] == 1
    assert summary["decision_rationale_summary"]["failed_evaluation_count"] == 1
    assert any(
        "Evaluation command failed during execution." in entry["reason"]
        for entry in summary["decision_rationale_summary"]["top_reject_reasons"]
    )
    assert retrieval_config["retrieval"]["top_k"] == 10
    assert records[-1]["decision"] == "rejected"
    assert records[-1]["rollback_performed"] is True
    assert "Evaluation command failed during execution." in records[-1]["reason"]


def test_run_command_creates_branch_and_commits_accepted_changes(tmp_path: Path) -> None:
    def mutate(data, workspace):
        _init_git_repo(workspace)
        data["version_control"]["enabled"] = True
        data["version_control"]["require_clean_worktree"] = True
        data["version_control"]["create_branch"] = True
        data["version_control"]["commit_accepted_changes"] = True
        data["version_control"]["branch_prefix"] = "auto-optimize-test/"
        data["run_policy"]["max_experiments"] = 2

    contract_path = _materialize_contract(tmp_path, mutate=mutate)

    exit_code = main(["run", str(contract_path)])

    assert exit_code == 0

    workspace = tmp_path / "workspace"
    output_dir = workspace / "auto_optimize_outputs"
    summary = json.loads((output_dir / "run_summary.json").read_text(encoding="utf-8"))
    branch_name = _run(["git", "branch", "--show-current"], cwd=workspace)
    commit_subject = _run(["git", "log", "-1", "--pretty=%s"], cwd=workspace)
    commit_count = int(_run(["git", "rev-list", "--count", "HEAD"], cwd=workspace))
    retrieval_config = yaml.safe_load((workspace / "configs" / "retrieval.yaml").read_text(encoding="utf-8"))

    assert summary["accepted_experiments"] == 1
    assert summary["rejected_experiments"] == 1
    assert summary["git"]["enabled"] is True
    assert summary["git"]["branch_created"] is True
    assert summary["git"]["working_branch"].startswith("auto-optimize-test/")
    assert len(summary["git"]["commits"]) == 1
    assert branch_name.startswith("auto-optimize-test/")
    assert "auto-optimize: exp_0002" in commit_subject
    assert commit_count == 2
    assert retrieval_config["retrieval"]["top_k"] == 20


def test_run_command_generates_and_records_metrics_parser_adapter(tmp_path: Path) -> None:
    def mutate(data, workspace):
        _write_key_value_eval_script(workspace)
        data["evaluation"] = {
            "command": "python eval/run_eval.py",
            "timeout_seconds": 60,
            "adapter": {
                "kind": "metrics_parser",
                "template": "key_value_lines",
                "output_dir": "auto_optimize_outputs/generated_adapters",
                "purpose": "Parse key/value metrics into JSON.",
                "declaration_source": "tests.generated_parser",
                "risk_flags": ["generated_code", "metrics_parsing"],
            },
        }
        data["run_policy"]["max_experiments"] = 1

    contract_path = _materialize_contract(tmp_path, mutate=mutate)

    exit_code = main(["run", str(contract_path)])

    assert exit_code == 0

    output_dir = tmp_path / "workspace" / "auto_optimize_outputs"
    summary = json.loads((output_dir / "run_summary.json").read_text(encoding="utf-8"))
    validation_report = (output_dir / "contract_validation_report.md").read_text(encoding="utf-8")
    report = (output_dir / "optimization_report.md").read_text(encoding="utf-8")
    adapter_path = output_dir / "generated_adapters" / "metrics_parser_key_value_lines.py"

    assert adapter_path.exists()
    assert summary["generated_adapters"]
    assert summary["asset_context"]["generated_adapters"]["count"] == 1
    assert summary["asset_context"]["generated_adapters"]["paths"] == [str(adapter_path)]
    assert len(summary["adapter_provenance"]) == 1
    assert summary["adapter_provenance"][0]["declaration_source"] == "tests.generated_parser"
    assert summary["adapter_provenance"][0]["trigger"]["evaluation_adapter_kind"] == "metrics_parser"
    assert summary["adapter_provenance"][0]["execution_phase"] == "post_output"
    assert "name: value" in summary["adapter_provenance"][0]["failure_mode"]
    assert {entry["flag"] for entry in summary["risk_flags"]} >= {
        "generated_code",
        "metrics_parsing",
        "external_eval_command",
    }
    assert summary["generated_adapters"][0]["generated_path"] == str(adapter_path)
    assert "Generated Adapters" in validation_report
    assert "Asset Provenance" in report
    assert "Adapter Provenance" in report
    assert "Risk Flags" in report
    assert "Decision Rationale Summary" in report
    assert "Declaration input" in report
    assert "Generated contract" in report
    assert "Generated Adapters" in report
    assert "Failure mode:" in report
    assert summary["generated_adapters"][0]["kind"] == "metrics_parser"


def test_run_command_generates_and_records_eval_wrapper_adapter(tmp_path: Path) -> None:
    def mutate(data, workspace):
        (workspace / "eval" / "run_eval.py").write_text(
            "\n".join(
                [
                    "#!/usr/bin/env python3",
                    "from __future__ import annotations",
                    "",
                    "import json",
                    "",
                    'print(\"starting noisy benchmark run\")',
                    'print(json.dumps({\"top1_accuracy\": 0.904, \"all_tests_pass\": True}))',
                    "",
                ]
            ),
            encoding="utf-8",
        )
        data["evaluation"] = {
            "command": "python eval/run_eval.py",
            "timeout_seconds": 60,
            "adapter": {
                "kind": "eval_wrapper",
                "template": "last_json_line",
                "output_dir": "auto_optimize_outputs/generated_adapters",
                "purpose": "Normalize noisy stdout into JSON metrics.",
                "declaration_source": "tests.eval_wrapper",
                "risk_flags": ["generated_code", "external_eval_command"],
            },
        }
        data["metrics"]["secondary"] = []
        data["constraints"] = {"all_tests_pass": {"required": True}}
        data["run_policy"]["max_experiments"] = 1

    contract_path = _materialize_contract(tmp_path, mutate=mutate)

    exit_code = main(["run", str(contract_path)])

    assert exit_code == 0

    output_dir = tmp_path / "workspace" / "auto_optimize_outputs"
    summary = json.loads((output_dir / "run_summary.json").read_text(encoding="utf-8"))
    adapter_path = output_dir / "generated_adapters" / "eval_wrapper_last_json_line.py"

    assert adapter_path.exists()
    assert summary["generated_adapters"]
    assert summary["generated_adapters"][0]["kind"] == "eval_wrapper"
    assert summary["generated_adapters"][0]["generated_path"] == str(adapter_path)
    assert summary["asset_context"]["generated_adapters"]["count"] == 1
    assert summary["adapter_provenance"][0]["trigger"]["evaluation_adapter_kind"] == "eval_wrapper"
    assert summary["adapter_provenance"][0]["declaration_source"] == "tests.eval_wrapper"
    assert summary["adapter_provenance"][0]["execution_phase"] == "pre_command"
    assert "last stdout lines" in summary["adapter_provenance"][0]["failure_mode"]
    assert {entry["flag"] for entry in summary["risk_flags"]} >= {"generated_code", "external_eval_command"}


def test_run_command_supports_csv_summary_output_format(tmp_path: Path) -> None:
    def mutate(data, workspace):
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
        data["evaluation"] = {
            "command": "python eval/run_eval.py",
            "output_format": "csv_with_summary",
            "output_file": "reports/summary.csv",
            "timeout_seconds": 60,
        }
        data["constraints"] = {
            "latency_ms": {"max": 200},
            "all_tests_pass": {"required": True},
        }
        data["run_policy"]["max_experiments"] = 2

    contract_path = _materialize_contract(tmp_path, mutate=mutate)

    exit_code = main(["run", str(contract_path)])

    assert exit_code == 0

    output_dir = tmp_path / "workspace" / "auto_optimize_outputs"
    summary = json.loads((output_dir / "run_summary.json").read_text(encoding="utf-8"))
    report = (output_dir / "optimization_report.md").read_text(encoding="utf-8")

    assert summary["best_metrics"]["top1_accuracy"] == 0.91
    assert summary["accepted_experiments"] >= 1
    assert summary["risk_flags"] == []
    assert summary["adapter_provenance"] == []
    assert "Decision Rationale Summary" in report


def test_run_command_can_push_accepted_branch_to_remote(tmp_path: Path) -> None:
    def mutate(data, workspace):
        _init_git_repo(workspace)
        remote_path = _init_git_remote(tmp_path, workspace)
        data["version_control"]["enabled"] = True
        data["version_control"]["require_clean_worktree"] = True
        data["version_control"]["create_branch"] = True
        data["version_control"]["commit_accepted_changes"] = True
        data["version_control"]["push_remote"] = True
        data["version_control"]["remote_name"] = "origin"
        data["version_control"]["branch_prefix"] = "auto-optimize-test/"
        data["run_policy"]["max_experiments"] = 2
        data.setdefault("test_context", {})
        data["test_context"]["remote_path"] = str(remote_path)

    contract_path = _materialize_contract(tmp_path, mutate=mutate)

    exit_code = main(["run", str(contract_path)])

    assert exit_code == 0

    workspace = tmp_path / "workspace"
    output_dir = workspace / "auto_optimize_outputs"
    summary = json.loads((output_dir / "run_summary.json").read_text(encoding="utf-8"))
    remote_path = Path(yaml.safe_load(contract_path.read_text(encoding="utf-8"))["test_context"]["remote_path"])
    remote_branches = _run(["git", "--git-dir", str(remote_path), "branch", "--list"], cwd=workspace)

    assert summary["git"]["pushed_remote_branch"].startswith("origin/auto-optimize-test/")
    assert "auto-optimize-test/" in remote_branches


def test_run_command_can_create_pull_request_when_enabled(tmp_path: Path, monkeypatch) -> None:
    import auto_optimize.runner.orchestrator as orchestrator_module

    def mutate(data, workspace):
        _init_git_repo(workspace)
        _init_git_remote(tmp_path, workspace)
        data["version_control"]["enabled"] = True
        data["version_control"]["require_clean_worktree"] = True
        data["version_control"]["create_branch"] = True
        data["version_control"]["commit_accepted_changes"] = True
        data["version_control"]["push_remote"] = True
        data["version_control"]["create_pull_request"] = True
        data["version_control"]["remote_name"] = "origin"
        data["version_control"]["branch_prefix"] = "auto-optimize-test/"
        data["run_policy"]["max_experiments"] = 2

    monkeypatch.setattr(
        orchestrator_module,
        "create_pull_request",
        lambda workspace_path, base_branch, head_branch, title, body, draft: "https://example.test/pr/123",
    )

    contract_path = _materialize_contract(tmp_path, mutate=mutate)

    exit_code = main(["run", str(contract_path)])

    assert exit_code == 0

    summary = json.loads(((tmp_path / "workspace" / "auto_optimize_outputs") / "run_summary.json").read_text(encoding="utf-8"))
    assert summary["git"]["pull_request_url"] == "https://example.test/pr/123"


def test_run_command_supports_pairwise_search_strategy(tmp_path: Path) -> None:
    def mutate(data, workspace):
        data["run_policy"]["search_strategy"] = "pairwise"
        data["run_policy"]["max_pairwise_candidates"] = 3
        data["run_policy"]["max_experiments"] = 3
        data["run_policy"]["stop_if_no_improvement_rounds"] = 3

    contract_path = _materialize_contract(tmp_path, mutate=mutate)

    exit_code = main(["run", str(contract_path)])

    assert exit_code == 0

    output_dir = tmp_path / "workspace" / "auto_optimize_outputs"
    summary = json.loads((output_dir / "run_summary.json").read_text(encoding="utf-8"))
    records = [
        json.loads(line)
        for line in (output_dir / "experiment_log.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    retrieval_config = yaml.safe_load((tmp_path / "workspace" / "configs" / "retrieval.yaml").read_text(encoding="utf-8"))

    assert summary["search_strategy"] == "pairwise"
    assert summary["accepted_experiments"] == 1
    assert summary["rejected_experiments"] == 2
    assert summary["accepted_candidates"][0]["parameters"] == ["top_k", "threshold"]
    assert records[1]["parameters"] == ["top_k", "threshold"]
    assert len(records[1]["changes"]) == 2
    assert retrieval_config["retrieval"]["top_k"] == 20
    assert retrieval_config["retrieval"]["threshold"] == 0.78


def test_report_command_regenerates_markdown_report(tmp_path: Path) -> None:
    contract_path = _materialize_contract(tmp_path)

    assert main(["run", str(contract_path)]) == 0

    output_dir = tmp_path / "workspace" / "auto_optimize_outputs"
    report_path = output_dir / "optimization_report.md"
    report_path.unlink()

    exit_code = main(["report", str(output_dir / "experiment_log.jsonl")])

    assert exit_code == 0
    regenerated = report_path.read_text(encoding="utf-8")
    assert "Asset Provenance" in regenerated
    assert "Adapter Provenance" in regenerated
    assert "Risk Flags" in regenerated
    assert "Decision Rationale Summary" in regenerated
    assert "Baseline vs Best" in regenerated
    assert "Experiment Memory" in regenerated


def test_run_memory_history_accumulates_across_runs(tmp_path: Path) -> None:
    contract_path = _materialize_contract(tmp_path)

    assert main(["run", str(contract_path)]) == 0
    assert main(["run", str(contract_path)]) == 0

    output_dir = tmp_path / "workspace" / "auto_optimize_outputs"
    summary = json.loads((output_dir / "run_summary.json").read_text(encoding="utf-8"))
    history_records = [
        json.loads(line)
        for line in (output_dir / "run_history.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert len(history_records) == 2
    assert summary["memory"]["total_runs"] == 2
    assert summary["memory"]["best_primary_metric"] == 0.909
