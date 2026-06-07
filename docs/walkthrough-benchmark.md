# Walkthrough: Benchmark Reference Assets

Benchmark assets are reference examples only.

They are useful for testing the current runner and showing a more complex evaluation declaration, but they are not the product direction. AutoOptimize should not require user projects to be benchmark-shaped.

## What This Reference Demonstrates

- protected data and eval files
- generated workspaces
- metric extraction from an evaluation command
- reference provider-style adapters
- run artifacts and reports

## Current Reference Flow

```bash
python scripts/materialize_benchmark_workspace.py \
  --dataset beir_scifact \
  --output-dir materialized_benchmarks

python -m auto_optimize.cli validate \
  materialized_benchmarks/beir_scifact/optimization.contract.yaml

python -m auto_optimize.cli run \
  materialized_benchmarks/beir_scifact/optimization.contract.yaml
```

## Direction Boundary

Do not treat this as the required path for users.

The generic path should be:

1. user declares their own data, evaluation command, metrics, and constraints
2. AutoOptimize generates or selects temporary adapters if needed
3. runner executes the generic loop

The benchmark utilities may remain as fixtures and examples for complex declarations.
