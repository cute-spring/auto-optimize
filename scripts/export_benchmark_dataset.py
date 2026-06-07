from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from auto_optimize.scenario_packs.benchmark_materializer import BENCHMARK_SPECS
from auto_optimize.scenario_packs.dataset_export import export_dataset_from_disk


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export a saved Hugging Face benchmark dataset into AutoOptimize's normalized local layout.")
    parser.add_argument("--dataset", choices=sorted(BENCHMARK_SPECS.keys()), required=True)
    parser.add_argument("--dataset-dir", required=True, help="Path to a local dataset saved with datasets.save_to_disk().")
    parser.add_argument(
        "--output-dir",
        help="Optional export directory. Defaults to <dataset-dir>/auto_optimize_export.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    export_result = export_dataset_from_disk(
        dataset_key=args.dataset,
        dataset_dir=Path(args.dataset_dir).resolve(),
        export_dir=None if args.output_dir is None else Path(args.output_dir).resolve(),
    )
    print(f"Export dir: {export_result.export_dir}")
    print(f"Export manifest: {export_result.manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
