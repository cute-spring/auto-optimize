# Contract Metric Profiles

This document defines optional reference metric profiles for AutoOptimize contracts.

These profiles are examples of comparison-rule bundles. They should not force user projects into FAQ, embedding, or reranking categories.

Related YAML snippets live in:

- `examples/metric_templates/faq_metrics.yaml`
- `examples/metric_templates/embedding_metrics.yaml`
- `examples/metric_templates/reranking_metrics.yaml`

## 1. FAQ Metrics

Use when:

- the task is FAQ retrieval
- the system tries to return the best answer in the first slot
- confusing near-duplicate candidates are common

Recommended emphasis:

- `top1_accuracy`
- `hit_at_3`
- `recall_at_10`
- `hard_negative_error_rate`
- latency small enough for interactive UX

Best fit:

- help center search
- support assistant retrieval
- bilingual FAQ retrieval

## 2. Embedding Metrics

Use when:

- the main variable is embedding model, embedding prompt, or embedding preprocessing
- the system is still evaluating retrieval-stage quality before reranking
- vector size and indexing cost matter

Recommended emphasis:

- `ndcg_at_10`
- `recall_at_10`
- `recall_at_50`
- `mrr`
- `embed_query_latency_p95_ms`
- `index_size_mb`

Best fit:

- benchmark comparison across embedding models
- query-template experiments
- multilingual normalization experiments

## 3. Reranking Metrics

Use when:

- retrieval already produces a candidate set
- the optimization target is a reranker
- the business question is whether the extra latency is worth it

Recommended emphasis:

- `mrr`
- `top1_accuracy`
- `rerank_gain_over_retrieval`
- `recovered_at_1_from_top10`
- `rerank_latency_p95_ms`

Best fit:

- FAQ reranking
- retrieval candidate rescoring
- comparing cross-encoder or instruction rerankers

## Suggested Default Choice

- Use `faq_metrics.yaml` for user-facing FAQ answer selection.
- Use `embedding_metrics.yaml` for retrieval or embedding benchmarking.
- Use `reranking_metrics.yaml` when there is already an initial retrieval stage and you want to optimize the reranker separately.
