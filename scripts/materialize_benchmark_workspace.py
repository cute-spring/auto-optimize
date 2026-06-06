from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from auto_optimize.scenario_packs.benchmark_materializer import BENCHMARK_SPECS, materialize_benchmark_workspace


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Materialize a runnable benchmark workspace for AutoOptimize.")
    parser.add_argument("--dataset", choices=sorted(BENCHMARK_SPECS.keys()), required=True)
    parser.add_argument("--output-dir", default="materialized_benchmarks", help="Parent directory for generated benchmark workspaces.")
    parser.add_argument("--dataset-dir", help="Optional local dataset directory to record in the workspace manifest.")
    parser.add_argument("--sample-limit", type=int, help="Optional sample limit recorded in the workspace manifest.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    dataset_dir = None if args.dataset_dir is None else Path(args.dataset_dir).resolve()
    result = materialize_benchmark_workspace(
        dataset_key=args.dataset,
        output_dir=Path(args.output_dir).resolve(),
        dataset_dir=dataset_dir,
        sample_limit=args.sample_limit,
    )

    print(f"Contract: {result.contract_path}")
    print(f"Workspace: {result.workspace_path}")
    print(f"Manifest: {result.manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
