# Contract Metric Templates

These files are reusable YAML snippets for the metric-related parts of an AutoOptimize contract.

They are designed to be copied into the following contract sections:

- `metrics`
- `constraints`
- `decision_policy`
- `pareto`
- `report`

Current recommended profiles:

- `faq_metrics.yaml`
- `embedding_metrics.yaml`
- `reranking_metrics.yaml`

## How To Use

1. choose the profile closest to your evaluation goal
2. copy the YAML blocks into your contract
3. adjust thresholds such as latency or size to match your environment
4. keep the metric names aligned with your evaluation command output

## When To Use Each

- `faq_metrics.yaml`
  - support FAQ retrieval
  - user question to FAQ answer selection
  - first-result quality matters most

- `embedding_metrics.yaml`
  - embedding or retrieval benchmark
  - vector quality vs latency vs index size tradeoff

- `reranking_metrics.yaml`
  - retrieve-then-rerank pipelines
  - compare reranker quality, gain, and latency
