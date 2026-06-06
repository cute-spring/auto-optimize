# Benchmark Contract Templates

These templates are intentionally not tied to checked-in corpora. They are starting points for materializing a real benchmark workspace after you download or sample a public dataset.

Included templates:

- `embedding_accuracy_en_scifact.contract.yaml`
- `embedding_accuracy_zh_duretrieval.contract.yaml`
- `reranking_zh_cmedqa.contract.yaml`

Each benchmark contract is aligned with one reusable metric profile:

- embedding benchmarks -> `examples/metric_templates/embedding_metrics.yaml`
- reranking benchmarks -> `examples/metric_templates/reranking_metrics.yaml`

Typical workflow:

1. download a public dataset into a local workspace
2. adapt the contract paths to match your local files
3. plug in your evaluation command
4. validate the contract
5. run optimization later when the Runner is implemented

## Materialized Workspaces

The repo now includes a workspace materializer that turns these templates into runnable benchmark workspaces with:

- a generated `optimization.contract.yaml`
- benchmark-specific config files
- `data/benchmark_manifest.json`
- a deterministic MVP eval adapter at `workspace/eval/run_benchmark_eval.py`

Example:

```bash
python scripts/materialize_benchmark_workspace.py \
  --dataset beir_scifact \
  --output-dir materialized_benchmarks

python -m auto_optimize.cli validate \
  materialized_benchmarks/beir_scifact/optimization.contract.yaml

python -m auto_optimize.cli run \
  materialized_benchmarks/beir_scifact/optimization.contract.yaml
```

If you already downloaded or sampled a dataset locally, you can record that path in the materialized workspace:

```bash
python scripts/materialize_benchmark_workspace.py \
  --dataset cmedqa_reranking \
  --output-dir materialized_benchmarks \
  --dataset-dir /path/to/local/dataset
```

You can also generate a materialized workspace directly from the downloader flow:

```bash
python scripts/download_benchmark_dataset.py \
  --dataset du_retrieval \
  --manifest-only \
  --materialize-workspace \
  --workspace-dir materialized_benchmarks
```
