from __future__ import annotations

import argparse
import json
from pathlib import Path

from auto_optimize.advisor.service import run_advisor
from auto_optimize.builder.service import build_contract, list_available_templates
from auto_optimize.contract.explainer import expanded_contract_data, load_raw_contract_data, write_contract_explanation
from auto_optimize.contract.loader import load_contract
from auto_optimize.contract.validator import validate_contract, write_validation_report
from auto_optimize.declaration import load_declaration, write_contract_from_declaration, write_declaration_from_contract
from auto_optimize.declaration.loader import DeclarationValidationError
from auto_optimize.governance import write_status_snapshot
from auto_optimize.reporting.report_generator import generate_html_report, generate_markdown_report, load_summary_for_report
from auto_optimize.runner.orchestrator import run_contract


def _is_declaration_path(path: Path) -> bool:
    return path.name.endswith(".declaration.yaml")


def _default_run_contract_path(declaration) -> Path:
    return declaration.workspace_path / "auto_optimize_outputs" / "optimization.contract.generated.yaml"


def _print_readiness_summary(readiness_report: dict[str, object]) -> None:
    scores = readiness_report.get("readiness_scores", {})
    if isinstance(scores, dict) and scores:
        print(
            "Readiness scores: "
            f"authoring={scores.get('authoring_completeness')}, "
            f"execution={scores.get('execution_readiness')}, "
            f"safety={scores.get('safety_readiness')}"
        )

    autofill_applied = readiness_report.get("autofill_applied", [])
    if isinstance(autofill_applied, list):
        print(f"Autofill applied: {len(autofill_applied)}")

    manual_decisions = readiness_report.get("manual_decisions_required", [])
    if isinstance(manual_decisions, list):
        print(f"Manual decisions required: {len(manual_decisions)}")

    declaration_gaps = readiness_report.get("declaration_gaps", [])
    if isinstance(declaration_gaps, list) and declaration_gaps:
        print("Top declaration gaps:")
        for gap in declaration_gaps[:3]:
            if not isinstance(gap, dict):
                continue
            detail = f"- [{gap.get('severity', 'unknown')}] {gap.get('id')}: {gap.get('message')}"
            remediation = gap.get("remediation")
            if remediation:
                detail += f" Remediation: {remediation}"
            print(detail)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="auto-optimize")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="Validate an optimization contract")
    validate_parser.add_argument("contract", help="Path to optimization.contract.yaml")

    advisor_parser = subparsers.add_parser("advisor", help="Generate a draft contract and readiness report for a workspace")
    advisor_parser.add_argument("--workspace", required=True)
    advisor_parser.add_argument("--scenario", required=False)
    advisor_parser.add_argument("--style", choices=["minimal", "expanded"], default="minimal")

    build_parser = subparsers.add_parser("build", help="Build a contract from a scenario template and metric profile")
    build_parser.add_argument("--workspace", required=True)
    build_parser.add_argument("--scenario", required=False)
    build_parser.add_argument("--metric-profile", required=False)
    build_parser.add_argument("--benchmark-key", required=False)
    build_parser.add_argument("--output", required=False)
    build_parser.add_argument("--style", choices=["minimal", "expanded"], default="expanded")

    guided_parser = subparsers.add_parser("guided", help="Run advisor and build a ready-to-edit generated contract")
    guided_parser.add_argument("--workspace", required=True)
    guided_parser.add_argument("--scenario", required=False)
    guided_parser.add_argument("--metric-profile", required=False)
    guided_parser.add_argument("--output", required=False)
    guided_parser.add_argument("--style", choices=["minimal", "expanded"], default="minimal")

    template_parser = subparsers.add_parser("template", help="List available scenario templates and metric profiles")
    template_parser.add_argument("--json", action="store_true")

    explain_parser = subparsers.add_parser("explain-contract", help="Write a human-readable explanation of a contract")
    explain_parser.add_argument("contract", help="Path to optimization.contract.yaml")
    explain_parser.add_argument("--output", required=False)
    explain_parser.add_argument("--json", action="store_true")

    declare_parser = subparsers.add_parser("declare", help="Convert a declaration YAML into an executable contract")
    declare_parser.add_argument("declaration", help="Path to optimization.declaration.yaml")
    declare_parser.add_argument("--output", required=False, help="Path to write the generated optimization.contract.yaml")

    derive_parser = subparsers.add_parser("derive-declaration", help="Derive a declaration YAML from an existing contract")
    derive_parser.add_argument("contract", help="Path to optimization.contract.yaml")
    derive_parser.add_argument("--output", required=False, help="Path to write the generated optimization.declaration.yaml")

    run_parser = subparsers.add_parser("run", help="Run an optimization contract or declaration")
    run_parser.add_argument("contract", nargs="?", help="Path to optimization.contract.yaml or optimization.declaration.yaml")

    status_audit_parser = subparsers.add_parser("status-audit", help="Generate a current project status snapshot from governance signals")
    status_audit_parser.add_argument("--output", required=False, help="Path to write the generated status snapshot Markdown file")

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
        detail = f"- [{issue.severity}] {issue.code}: {issue.message}"
        if issue.field:
            detail += f" Field: {issue.field}."
        if issue.hint:
            detail += f" Hint: {issue.hint}"
        print(detail)
    return 1


def cmd_run(contract_arg: str) -> int:
    if not contract_arg:
        print("run mode requires a contract or declaration path.")
        return 1

    input_path = Path(contract_arg).resolve()
    execution_mode = "contract"
    contract_path = input_path

    try:
        if _is_declaration_path(input_path):
            declaration = load_declaration(input_path)
            contract_path = write_contract_from_declaration(declaration, _default_run_contract_path(declaration))
            execution_mode = "declaration_native"
        contract = load_contract(contract_path)
    except DeclarationValidationError as exc:
        print("Declaration validation failed.")
        for issue in exc.issues:
            print(f"- {issue}")
        print("Next step: fix the declaration fields above, then rerun `run` with the declaration path.")
        return 1
    except ValueError as exc:
        print(str(exc))
        print("Next step: adjust the declaration to use only executable variable kinds, metrics sources, and required companion fields in this slice.")
        return 1

    try:
        summary = run_contract(contract, execution_mode=execution_mode)
    except RuntimeError as exc:
        print(str(exc))
        if str(exc).startswith("Contract validation failed before run:"):
            print(f"Next step: run `python -m auto_optimize.cli validate {contract_path}` and fix the reported fields before retrying.")
        return 1

    if execution_mode == "declaration_native":
        print(f"Source declaration: {input_path}")
        print(f"Generated contract: {contract_path}")
    print(f"Run summary: {summary['artifacts']['run_summary']}")
    print(f"Experiment log: {summary['artifacts']['experiment_log_jsonl']}")
    print(f"Markdown report: {summary['artifacts']['optimization_report_md']}")
    print("Optimization run completed.")
    return 0


def cmd_advisor(workspace_arg: str, scenario_arg: str | None, style_arg: str) -> int:
    try:
        result = run_advisor(workspace_arg, scenario=scenario_arg, contract_style=style_arg)
    except ValueError as exc:
        print(str(exc))
        return 1

    print(f"Draft declaration: {result.draft_declaration_path}")
    print(f"Normalized declaration: {result.normalized_declaration_path}")
    print(f"Draft contract: {result.draft_contract_path}")
    print(f"Readiness report: {result.readiness_report_path}")
    print(f"Readiness status: {result.readiness_report['status']}")
    print(f"Recommended contract style: {result.readiness_report['recommended_contract_style']}")
    _print_readiness_summary(result.readiness_report)
    return 0


def cmd_build(
    workspace_arg: str,
    scenario_arg: str | None,
    metric_profile_arg: str | None,
    benchmark_key_arg: str | None,
    output_arg: str | None,
    style_arg: str,
) -> int:
    try:
        result = build_contract(
            workspace_arg=workspace_arg,
            scenario=scenario_arg,
            metric_profile=metric_profile_arg,
            benchmark_key=benchmark_key_arg,
            output_path=output_arg,
            contract_style=style_arg,
        )
    except ValueError as exc:
        print(str(exc))
        return 1

    print(f"Generated contract: {result.contract_path}")
    print(f"Scenario: {result.scenario}")
    print(f"Metric profile: {result.metric_profile}")
    print(f"Contract style: {result.contract_style}")
    if result.benchmark_key:
        print(f"Benchmark key: {result.benchmark_key}")
    return 0


def cmd_guided(
    workspace_arg: str,
    scenario_arg: str | None,
    metric_profile_arg: str | None,
    output_arg: str | None,
    style_arg: str,
) -> int:
    try:
        advisor_result = run_advisor(workspace_arg, scenario=scenario_arg, contract_style=style_arg)
        declaration = load_declaration(advisor_result.normalized_declaration_path)
        resolved_output_arg = output_arg
        if resolved_output_arg is None:
            resolved_output_arg = str(Path(workspace_arg).resolve() / "auto_optimize_outputs" / "optimization.contract.generated.yaml")
        contract_path = write_contract_from_declaration(declaration, resolved_output_arg)
    except ValueError as exc:
        print(str(exc))
        return 1

    if metric_profile_arg is not None:
        print("Note: --metric-profile is ignored in declaration-first guided mode.")

    print(f"Readiness report: {advisor_result.readiness_report_path}")
    print(f"Draft declaration: {advisor_result.draft_declaration_path}")
    print(f"Normalized declaration: {advisor_result.normalized_declaration_path}")
    print(f"Generated contract: {contract_path}")
    print("Scenario: generic_declaration")
    print(f"Contract style: {style_arg}")
    _print_readiness_summary(advisor_result.readiness_report)
    print("Next step: validate the generated contract before run mode.")
    return 0


def cmd_template(json_output: bool) -> int:
    payload = list_available_templates()
    if json_output:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    print("Available reference fixtures:")
    for scenario in payload["reference_fixtures"]:
        print(f"- {scenario} -> default metric profile: {payload['default_metric_profiles'][scenario]}")
    print("Available metric profiles:")
    for profile in payload["metric_profiles"]:
        print(f"- {profile}")
    print("Available benchmark datasets:")
    for dataset in payload["benchmark_datasets"]:
        print(f"- {dataset}")
    return 0


def cmd_explain_contract(contract_arg: str, output_arg: str | None, json_output: bool) -> int:
    contract_path = Path(contract_arg).resolve()
    raw_data = load_raw_contract_data(contract_path)
    contract = load_contract(contract_path)

    if json_output:
        print(json.dumps(expanded_contract_data(contract), indent=2, ensure_ascii=False))
        return 0

    report_path = write_contract_explanation(contract, raw_data, output_path=output_arg)
    print(f"Contract explanation: {report_path}")
    return 0


def cmd_declare(declaration_arg: str, output_arg: str | None) -> int:
    declaration_path = Path(declaration_arg).resolve()
    try:
        declaration = load_declaration(declaration_path)
        contract_path = write_contract_from_declaration(declaration, output_arg)
    except DeclarationValidationError as exc:
        print("Declaration validation failed.")
        for issue in exc.issues:
            print(f"- {issue}")
        print("Next step: fix the declaration fields above, then rerun `declare`.")
        return 1
    except ValueError as exc:
        print(str(exc))
        print("Next step: adjust the declaration to use only executable variable kinds, metrics sources, and required companion fields in this slice.")
        return 1

    print(f"Generated contract: {contract_path}")
    print(f"Source declaration: {declaration_path}")
    print(f"Resolved workspace: {declaration.workspace_path}")
    print("Next step: validate the generated contract before run mode.")
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


def cmd_status_audit(output_arg: str | None) -> int:
    signals_path = Path(__file__).resolve().parents[1] / "docs" / "release_readiness_gate" / "status_audit_signals.yaml"
    snapshot, markdown_path, json_path = write_status_snapshot(
        signals_path=signals_path,
        output_path=None if output_arg is None else Path(output_arg).resolve(),
    )

    print(f"Status snapshot: {markdown_path}")
    print(f"Status snapshot JSON: {json_path}")
    print(f"Overall completion: {snapshot['checklist_progress']['completion_percent']}%")
    print(f"Recommended next step: {snapshot.get('recommended_next_step')}")
    return 0


def cmd_derive_declaration(contract_arg: str, output_arg: str | None) -> int:
    contract_path = Path(contract_arg).resolve()
    contract = load_contract(contract_path)
    try:
        declaration_path = write_declaration_from_contract(contract, output_arg)
    except ValueError as exc:
        print(str(exc))
        return 1

    print(f"Generated declaration: {declaration_path}")
    print(f"Source contract: {contract_path}")
    print("Note: contract-only sections such as version_control, pareto, and report stay in the contract layer.")
    print("Next step: review the derived declaration, then use `declare` to regenerate an executable contract when needed.")
    return 0


def cmd_stub(command_name: str) -> int:
    raise SystemExit(f"{command_name} mode is not implemented yet in this MVP slice.")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "validate":
        return cmd_validate(args.contract)
    if args.command == "advisor":
        return cmd_advisor(args.workspace, args.scenario, args.style)
    if args.command == "build":
        return cmd_build(args.workspace, args.scenario, args.metric_profile, args.benchmark_key, args.output, args.style)
    if args.command == "guided":
        return cmd_guided(args.workspace, args.scenario, args.metric_profile, args.output, args.style)
    if args.command == "template":
        return cmd_template(args.json)
    if args.command == "explain-contract":
        return cmd_explain_contract(args.contract, args.output, args.json)
    if args.command == "declare":
        return cmd_declare(args.declaration, args.output)
    if args.command == "derive-declaration":
        return cmd_derive_declaration(args.contract, args.output)
    if args.command == "run":
        return cmd_run(args.contract)
    if args.command == "status-audit":
        return cmd_status_audit(args.output)
    if args.command == "report":
        return cmd_report(args.experiment_log)
    raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
