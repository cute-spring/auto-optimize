# Benchmark Reference Assets

These assets are references and regression fixtures. They are not the core AutoOptimize direction.

The core direction is generic declaration-driven optimization. Benchmark utilities remain useful as examples of complex declarations involving data files, candidate sets, metrics, and adapters.

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
- sample benchmark data such as `corpus.jsonl`, `queries.jsonl`, `qrels.json`, and optional candidate/expansion files
- a data-driven MVP eval adapter at `workspace/eval/run_benchmark_eval.py`

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

When `--dataset-dir` contains a supported exported layout, the materializer will copy those files into `workspace/data/` instead of using the built-in sample assets.

Supported local layout:

- retrieval benchmarks:
  - `corpus.jsonl`
  - `queries.jsonl`
  - `qrels.json`
  - optional: `query_expansions.json`
- reranking benchmarks:
  - `corpus.jsonl`
  - `queries.jsonl`
  - `qrels.json`
  - `candidates.json`
  - optional: `query_expansions.json`

These files can live directly under `dataset_dir/` or `dataset_dir/data/`.

If the local directory does not match this exported layout, the workspace still materializes successfully and falls back to the checked-in sample assets. The manifest records which source was used.

If your local dataset is stored as a Hugging Face `save_to_disk()` directory, export it first:

```bash
python scripts/export_benchmark_dataset.py \
  --dataset du_retrieval \
  --dataset-dir /path/to/hf_saved_dataset
```

This writes `/path/to/hf_saved_dataset/auto_optimize_export/`, and the materializer will automatically prefer that normalized export when you pass `--dataset-dir /path/to/hf_saved_dataset`.

For MTEB-style Hugging Face datasets such as `DuRetrieval` and `CMedQAv2-reranking`, the downloader now fetches the required configs separately and then writes this normalized export automatically.

The current MVP adapter uses the materialized sample data to compute retrieval or reranking metrics from rankings and qrels. It is intended as a realistic harness scaffold for AutoOptimize flow validation before wiring in full external-model execution.

## Provider Modes

Materialized retrieval benchmarks now include `workspace/configs/provider.yaml`.

- `mode: sample`
  - default
  - uses the built-in data-driven harness with local sample corpus/query/qrels
- `mode: sentence_transformers`
  - optional
  - attempts to load a local `sentence-transformers` model and compute ranking scores from real embeddings
  - if `allow_fallback_to_sample: true`, the harness falls back to sample mode when the dependency or model is unavailable
- `mode: cross_encoder`
  - optional for reranking benchmarks
  - attempts to load a local `sentence-transformers` `CrossEncoder` model and score candidate query-document pairs
  - if `allow_fallback_to_sample: true`, the harness falls back to sample reranking when the dependency or model is unavailable

Example:

```yaml
provider:
  mode: sentence_transformers
  model_name: sentence-transformers/all-MiniLM-L6-v2
  allow_fallback_to_sample: true
```

For reranking benchmarks:

```yaml
provider:
  mode: cross_encoder
  model_name: cross-encoder/ms-marco-MiniLM-L-6-v2
  allow_fallback_to_sample: true
```

You can also generate a materialized workspace directly from the downloader flow:

```bash
python scripts/download_benchmark_dataset.py \
  --dataset du_retrieval \
  --manifest-only \
  --materialize-workspace \
  --workspace-dir materialized_benchmarks
```
