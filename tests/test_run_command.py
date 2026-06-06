from __future__ import annotations

import json
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

    assert run_summary_path.exists()
    assert jsonl_path.exists()
    assert csv_path.exists()
    assert history_path.exists()
    assert best_run_path.exists()
    assert md_report_path.exists()
    assert validation_report_path.exists()

    summary = json.loads(run_summary_path.read_text(encoding="utf-8"))
    assert summary["status"] == "completed"
    assert summary["baseline_metrics"]["top1_accuracy"] == 0.892
    assert summary["best_metrics"]["top1_accuracy"] == 0.909
    assert summary["constraints_satisfied"] is True
    assert summary["experiments_run"] == 10
    assert summary["accepted_experiments"] == 4
    assert summary["rejected_experiments"] == 6
    assert summary["failed_evaluations"] == 0
    assert summary["memory"]["total_runs"] == 1
    assert summary["memory"]["current_run_is_historical_best"] is True
    assert len(summary["accepted_candidates"]) == 4

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

    report_text = md_report_path.read_text(encoding="utf-8")
    assert "Baseline Metrics" in report_text
    assert "Best Metrics" in report_text
    assert "Accepted Experiments" in report_text
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


def test_run_command_fails_when_validation_fails(tmp_path: Path) -> None:
    def mutate(data, workspace):
        data["metrics"]["primary"]["name"] = "missing_metric"

    contract_path = _materialize_contract(tmp_path, mutate=mutate)

    exit_code = main(["run", str(contract_path)])

    assert exit_code == 1


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


def test_report_command_regenerates_markdown_report(tmp_path: Path) -> None:
    contract_path = _materialize_contract(tmp_path)

    assert main(["run", str(contract_path)]) == 0

    output_dir = tmp_path / "workspace" / "auto_optimize_outputs"
    report_path = output_dir / "optimization_report.md"
    report_path.unlink()

    exit_code = main(["report", str(output_dir / "experiment_log.jsonl")])

    assert exit_code == 0
    regenerated = report_path.read_text(encoding="utf-8")
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
