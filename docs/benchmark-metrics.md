# Benchmark Metrics

This document is an optional metric reference for retrieval-like examples.

It should not be read as the core direction of AutoOptimize. The core direction is generic declaration-driven optimization.

This document defines useful metrics when evaluating:

- embedding quality
- retrieval quality
- reranking quality
- latency and throughput
- model and index size
- stability and robustness

The goal is not to maximize one score in isolation. The goal is to compare tradeoffs clearly and make optimization decisions that still hold under realistic workload and data variation.

## 1. Principles

- Prefer metrics that reflect actual user experience, not only benchmark convention.
- Separate retrieval-stage metrics from reranking-stage metrics.
- Track both average quality and tail latency.
- Always evaluate quality together with size or speed cost.
- Add robustness checks so a model does not look good only on clean benchmark phrasing.

## 2. Embedding And Retrieval Metrics

These metrics answer:

- did we retrieve the right document?
- how high did the right document rank?
- how much quality do we get for the latency and index size we pay?

### Core Quality Metrics

- `top1_accuracy`
  - Whether the correct result is ranked first.
  - Very important for FAQ and support retrieval.

- `hit_at_1`
  - Equivalent to top-1 success for candidate retrieval.
  - Good for dashboards and product-facing reporting.

- `hit_at_3`
  - Whether at least one relevant result appears in the top 3.
  - Useful when the UI shows multiple results.

- `hit_at_10`
  - Whether at least one relevant result appears in the top 10.
  - Useful when reranking is applied after initial retrieval.

- `recall_at_10`
  - Fraction of relevant documents retrieved in the top 10.
  - Good for measuring retrieval ceiling before reranking.

- `recall_at_50`
  - Good for evaluating whether retrieval is strong enough to feed a reranker.

- `recall_at_100`
  - Especially useful when reranking over a larger candidate pool.

- `mrr`
  - Mean Reciprocal Rank.
  - Good when one highly relevant answer matters most.

- `ndcg_at_10`
  - Normalized Discounted Cumulative Gain at 10.
  - Better than plain recall when multiple relevant answers exist or graded relevance is available.

### Retrieval-Specific Diagnostic Metrics

- `retrieval_ceiling_at_10`
  - Equivalent to whether the relevant item is even available to later ranking stages.

- `retrieval_ceiling_at_50`
  - Critical for reranking pipeline design.

- `hard_negative_error_rate`
  - Fraction of cases where a confusing but wrong candidate outranks the true answer.
  - Very important for FAQ, support, policy, and product-doc retrieval.

- `category_breakdown`
  - Per-category performance, such as billing, refund, password reset, SSO, invoice.
  - Prevents average metrics from hiding weak business-critical slices.

## 3. Reranking Metrics

These metrics answer:

- did reranking improve final answer quality?
- how much did it help over raw retrieval?
- is the gain worth the extra latency and cost?

### Core Reranking Metrics

- `top1_accuracy`
  - Final top-1 quality after reranking.

- `mrr`
  - Standard reranking metric, especially when there is one main relevant answer.

- `ndcg_at_10`
  - Useful when candidate lists contain multiple relevant items.

- `rerank_gain_over_retrieval`
  - Improvement of final ranking metric relative to the pre-rerank baseline.
  - Example:
    - `mrr_after - mrr_before`
    - `top1_accuracy_after - top1_accuracy_before`

- `swap_success_rate`
  - Frequency with which reranking correctly promotes a previously lower-ranked relevant candidate above an irrelevant one.

- `recovered_at_1_from_top10`
  - When the correct answer was already in the top 10 retrieved candidates, how often did reranking move it to rank 1?

- `recovered_at_1_from_top50`
  - Same idea for a larger candidate pool.

### Reranking Pipeline Metrics

- `candidate_depth_sensitivity`
  - Compare reranking quality over top 20, top 50, and top 100 candidates.

- `rerank_failure_on_retrieval_success`
  - Cases where retrieval found the right answer, but reranking made the final answer worse.

- `rerank_gain_per_ms`
  - Improvement in quality divided by rerank latency.
  - Useful for cost-benefit decisions.

## 4. Latency And Throughput Metrics

These metrics answer:

- how fast is each pipeline stage?
- how stable is latency, not just average speed?

### Embedding Latency

- `embed_query_latency_ms`
  - Mean query embedding latency.

- `embed_query_latency_p50_ms`
- `embed_query_latency_p95_ms`
- `embed_query_latency_p99_ms`
  - Tail latency matters for real product experience.

- `embed_doc_latency_ms`
  - Mean document embedding latency during indexing or refresh.

- `queries_per_second`
- `docs_per_second`

### Retrieval Latency

- `retrieve_latency_ms`
- `retrieve_latency_p50_ms`
- `retrieve_latency_p95_ms`
- `retrieve_latency_p99_ms`

### Reranking Latency

- `rerank_latency_ms`
- `rerank_latency_p50_ms`
- `rerank_latency_p95_ms`
- `rerank_latency_p99_ms`

- `latency_per_candidate_ms`
  - Useful when comparing rerankers with different top-k sizes.

- `top_k_scaling_curve`
  - Measure latency at top 20, top 50, top 100, and top 200 candidates.
  - This reveals whether a reranker is practical at production candidate depth.

## 5. Size, Memory, And Cost Metrics

These metrics answer:

- what is the resource cost of better quality?
- how much storage and memory does the system require?

### Embedding And Model Size

- `embedding_dimension`
- `embedding_bytes_per_doc`
- `model_disk_size_mb`
- `embedding_cache_size_mb`

### Index Size

- `index_size_mb`
- `index_size_per_100k_docs_mb`

### Runtime Memory

- `cpu_mem_peak_mb`
- `gpu_mem_peak_mb`
- `ram_peak_mb`

### Cost

- `cost_per_1k_queries`
- `cost_per_1k_reranks`
- `cost_per_correct_top1_gain`
  - Useful when comparing more expensive rerankers.

## 6. Stability And Robustness Metrics

These metrics answer:

- does the system hold up under messy, real-world queries?
- is it stable across runs and query variants?

### Query Robustness

- `typo_robustness`
  - Performance on typo, OCR-like, or colloquial queries.

- `paraphrase_robustness`
  - Performance when the same intent is expressed differently.

- `multilingual_robustness`
  - Performance on mixed Chinese-English or cross-lingual phrasing.

- `length_sensitivity`
  - Compare very short, normal, and verbose queries.

### Template And Config Stability

- `template_sensitivity`
  - How much quality changes when FAQ embedding text composition changes.

- `query_processing_sensitivity`
  - How much results change under normalization, keyword expansion, or bilingual expansion.

- `run_to_run_variance`
  - Variation across repeated runs of the same setup.

### ANN Or Indexing Robustness

- `ann_recall_loss`
  - Difference between approximate nearest-neighbor retrieval and exact retrieval.
  - Important when choosing practical vector index settings.

## 7. Recommended Metric Sets

### Minimal Retrieval Set

Use this when starting with embedding retrieval optimization:

- `top1_accuracy`
- `recall_at_10`
- `recall_at_50`
- `mrr`
- `ndcg_at_10`
- `embed_query_latency_p95_ms`
- `index_size_mb`

### Minimal Reranking Set

Use this when starting with reranking optimization:

- `top1_accuracy`
- `mrr`
- `ndcg_at_10`
- `rerank_gain_over_retrieval`
- `rerank_latency_p95_ms`

### FAQ / Support Retrieval Set

Recommended for FAQ-like systems:

- `top1_accuracy`
- `hit_at_3`
- `recall_at_10`
- `recovered_at_1_from_top10`
- `hard_negative_error_rate`
- `embed_query_latency_p95_ms`
- `rerank_latency_p95_ms`
- `index_size_mb`

### Efficiency-Focused Set

Use this when the optimization target is speed or cost:

- `top1_accuracy`
- `ndcg_at_10`
- `embed_query_latency_p95_ms`
- `retrieve_latency_p95_ms`
- `rerank_latency_p95_ms`
- `queries_per_second`
- `index_size_mb`
- `cost_per_1k_queries`

## 8. How These Metrics Map To AutoOptimize

### Embedding Optimization

Prioritize:

- `recall_at_k`
- `mrr`
- `ndcg_at_10`
- `embed_query_latency_p95_ms`
- `index_size_mb`

### Reranking Optimization

Prioritize:

- `top1_accuracy`
- `mrr`
- `rerank_gain_over_retrieval`
- `recovered_at_1_from_top10`
- `rerank_latency_p95_ms`

### Production Readiness

Before calling a configuration production-ready, include:

- one quality metric
- one retrieval ceiling metric
- one tail-latency metric
- one size or cost metric
- one robustness slice

## 9. Practical Notes

- Do not rely on a single score.
- For reranking, always report both pre-rerank and post-rerank quality.
- For embedding, always report both quality and index size.
- For latency, always prefer p95 over mean when making product decisions.
- For multilingual systems, always break out Chinese, English, and mixed-language queries separately.
