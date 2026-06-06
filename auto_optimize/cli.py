from __future__ import annotations

import argparse
from pathlib import Path

from auto_optimize.contract.loader import load_contract
from auto_optimize.contract.validator import validate_contract, write_validation_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="auto-optimize")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="Validate an optimization contract")
    validate_parser.add_argument("contract", help="Path to optimization.contract.yaml")

    advisor_parser = subparsers.add_parser("advisor", help="Advisor mode (stub)")
    advisor_parser.add_argument("--workspace", required=False)
    advisor_parser.add_argument("--scenario", required=False)

    run_parser = subparsers.add_parser("run", help="Run mode (stub)")
    run_parser.add_argument("contract", nargs="?")

    report_parser = subparsers.add_parser("report", help="Report mode (stub)")
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


def cmd_stub(command_name: str) -> int:
    raise SystemExit(f"{command_name} mode is not implemented yet in this MVP slice.")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "validate":
        return cmd_validate(args.contract)
    if args.command == "advisor":
        return cmd_stub("advisor")
    if args.command == "run":
        return cmd_stub("run")
    if args.command == "report":
        return cmd_stub("report")
    raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
