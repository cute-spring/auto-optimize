# Walkthrough: Benchmark Workspace

Use this walkthrough when you want to run AutoOptimize against a retrieval or reranking benchmark workspace.

## What You Need

- the repository checked out locally
- Python environment with the project dependencies installed
- one of the supported benchmark keys:
  - `beir_scifact`
  - `du_retrieval`
  - `cmedqa_reranking`

## Fastest Path

Materialize a runnable benchmark workspace from the built-in assets:

```bash
python scripts/materialize_benchmark_workspace.py \
  --dataset beir_scifact \
  --output-dir materialized_benchmarks

python -m auto_optimize.cli validate \
  materialized_benchmarks/beir_scifact/optimization.contract.yaml

python -m auto_optimize.cli run \
  materialized_benchmarks/beir_scifact/optimization.contract.yaml
```

## What This Produces

The materializer creates:

- a generated `optimization.contract.yaml`
- `workspace/configs/*`
- `workspace/data/benchmark_manifest.json`
- `workspace/eval/run_benchmark_eval.py`
- sample or copied benchmark data under `workspace/data/`

## Optional Local Dataset Path

If you already have local data in a supported normalized layout, materialize from that directory:

```bash
python scripts/materialize_benchmark_workspace.py \
  --dataset du_retrieval \
  --output-dir materialized_benchmarks \
  --dataset-dir /path/to/local/dataset
```

If your data is a Hugging Face `save_to_disk()` directory, export it first:

```bash
python scripts/export_benchmark_dataset.py \
  --dataset du_retrieval \
  --dataset-dir /path/to/hf_saved_dataset
```

## What To Inspect

After materialization:

- `workspace/data/benchmark_manifest.json`
- `workspace/eval/run_benchmark_eval.py`
- the generated benchmark contract

After validation and run:

- `workspace/auto_optimize_outputs/contract_validation_report.md`
- `workspace/auto_optimize_outputs/run_summary.json`
- `workspace/auto_optimize_outputs/optimization_report.md`

## Provider Modes

Benchmark workspaces support provider configuration in `workspace/configs/provider.yaml`.

- `sample`
  - default
  - local sample harness
- `sentence_transformers`
  - local embedding model execution
- `cross_encoder`
  - local reranking model execution for reranking benchmarks

The default onboarding path uses `sample`, because it is the easiest way to validate the workflow end to end.

## How To Know You Succeeded

You are done when:

- the workspace materializes successfully
- `validate` passes on the generated contract
- `run` finishes and produces report artifacts under `workspace/auto_optimize_outputs/`

For more background on benchmark assets, see [examples/benchmarks/README.md](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/examples/benchmarks/README.md:1).
