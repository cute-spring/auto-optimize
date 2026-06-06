from __future__ import annotations

import argparse
import json
from pathlib import Path

from auto_optimize.contract.loader import load_contract
from auto_optimize.contract.validator import validate_contract, write_validation_report
from auto_optimize.advisor.service import run_advisor
from auto_optimize.reporting.report_generator import generate_html_report, generate_markdown_report, load_summary_for_report
from auto_optimize.runner.orchestrator import run_contract


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="auto-optimize")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="Validate an optimization contract")
    validate_parser.add_argument("contract", help="Path to optimization.contract.yaml")

    advisor_parser = subparsers.add_parser("advisor", help="Generate a draft contract and readiness report for a workspace")
    advisor_parser.add_argument("--workspace", required=True)
    advisor_parser.add_argument("--scenario", required=False)

    run_parser = subparsers.add_parser("run", help="Run an optimization contract")
    run_parser.add_argument("contract", nargs="?")

    report_parser = subparsers.add_parser("report", help="Regenerate a report from an output directory or log path")
    report_parser.add_argument("experiment_log", nargs="?")

    return parser


def cmd_validate(contract_arg: str) -> int:
    contract_path = Path(contract_arg).resolve()
    contract = load_contract(contract_path)
    result = validate_contract(contract)
    report_path = write_validation_report(contract, result)

    print(f"Validation report: {report_path}")
    if result.valid:
        print("Contract validation passed.")
        return 0

    print("Contract validation failed.")
    for issue in result.issues:
        print(f"- [{issue.severity}] {issue.code}: {issue.message}")
    return 1


def cmd_run(contract_arg: str) -> int:
    contract_path = Path(contract_arg).resolve()
    contract = load_contract(contract_path)
    try:
        summary = run_contract(contract)
    except RuntimeError as exc:
        print(str(exc))
        return 1

    print(f"Run summary: {summary['artifacts']['run_summary']}")
    print(f"Experiment log: {summary['artifacts']['experiment_log_jsonl']}")
    print(f"Markdown report: {summary['artifacts']['optimization_report_md']}")
    print("Optimization run completed.")
    return 0


def cmd_advisor(workspace_arg: str, scenario_arg: str | None) -> int:
    try:
        result = run_advisor(workspace_arg, scenario=scenario_arg)
    except ValueError as exc:
        print(str(exc))
        return 1

    print(f"Draft contract: {result.draft_contract_path}")
    print(f"Readiness report: {result.readiness_report_path}")
    print(f"Readiness status: {result.readiness_report['status']}")
    return 0


def cmd_report(target_arg: str) -> int:
    target_path = Path(target_arg).resolve()
    try:
        summary, output_dir = load_summary_for_report(target_path)
    except FileNotFoundError:
        print(f"Could not find run_summary.json from: {target_path}")
        return 1

    markdown_report = generate_markdown_report(summary, summary["baseline_metrics"])
    report_md_path = output_dir / "optimization_report.md"
    report_md_path.write_text(markdown_report, encoding="utf-8")

    report_html_path = output_dir / "optimization_report.html"
    if "optimization_report_html" in summary.get("artifacts", {}):
        report_html_path.write_text(generate_html_report(markdown_report), encoding="utf-8")

    summary_path = output_dir / "run_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Markdown report: {report_md_path}")
    if report_html_path.exists():
        print(f"HTML report: {report_html_path}")
    return 0


def cmd_stub(command_name: str) -> int:
    raise SystemExit(f"{command_name} mode is not implemented yet in this MVP slice.")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "validate":
        return cmd_validate(args.contract)
    if args.command == "advisor":
        return cmd_advisor(args.workspace, args.scenario)
    if args.command == "run":
        return cmd_run(args.contract)
    if args.command == "report":
        return cmd_report(args.experiment_log)
    raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
