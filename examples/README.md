# Examples

This directory is organized around the question: which starting point matches my scenario?

## Start With This

- Use `faq_retrieval/` if you want the easiest first success and a deterministic local workflow.
- Use `benchmarks/` if you want retrieval or reranking benchmark templates and materialized workspaces.
- Use `metric_templates/` if you want reusable metric and constraint profiles.
- Use `datasets.md` if you want background on public benchmark datasets and where they fit.

## Example Selection Guide

### `faq_retrieval/`

Choose this when:

- you are learning the product
- you want to validate the end-to-end flow quickly
- you want a local fixture that does not depend on external providers

Key files:

- `optimization.contract.yaml`
- `workspace/configs/`
- `workspace/eval/run_eval.py`

### `benchmarks/`

Choose this when:

- you want a benchmark-style retrieval or reranking workflow
- you want to materialize a runnable workspace from sample assets or local dataset files

Key files:

- benchmark contract templates
- `scripts/materialize_benchmark_workspace.py`
- materialized `workspace/eval/run_benchmark_eval.py`

### `metric_templates/`

Choose this when:

- you want recommended metrics, constraints, and decision policy defaults
- you are generating or reviewing a contract

Profiles:

- `faq_metrics.yaml`
- `embedding_metrics.yaml`
- `reranking_metrics.yaml`

## Recommended First Path

If you are new to AutoOptimize:

1. Start with `faq_retrieval/`.
2. Read [quickstart.md](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/docs/quickstart.md:1).
3. Run `advisor`, `validate`, and `run` on the FAQ example.
4. Move to `benchmarks/` or your own workspace after you understand the artifacts.
