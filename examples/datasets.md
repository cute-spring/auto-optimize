# Public Benchmark Datasets

This is a reference document only.

Public datasets are not the product direction of AutoOptimize. They can help test example declarations and regression fixtures, but the skill should primarily operate from user-declared objectives, variables, evaluation methods, metrics, and safety boundaries.

This document records public datasets that were considered as optional reference fixtures for retrieval-like examples:

- embedding accuracy
- retrieval accuracy
- reranking quality
- latency / speed
- embedding or index size

Important:

- Accuracy and ranking quality come from labeled public datasets.
- Latency, throughput, model size, and index size are measured locally on top of those datasets.
- Large datasets should usually be sampled into smaller local benchmark subsets before becoming default fixtures.

## Optional Reference Fixtures

### 1. BEIR SciFact

- Best for: lightweight English retrieval regression checks
- Why it fits:
  - small enough for local smoke tests
  - standard `corpus / queries / qrels` retrieval shape
  - easy to use as a stable reference fixture
- Good metrics:
  - `nDCG@10`
  - `Recall@10`
  - `MRR`
- Suggested use:
  - first English retrieval reference fixture
  - embedding quality regression after model or template changes

Source:
- [BEIR datasets wiki](https://github.com/beir-cellar/beir/wiki/Datasets-available)

### 2. DuRetrieval

- Best for: Chinese retrieval quality and latency
- Why it fits:
  - public Chinese web-search retrieval benchmark
  - moderate size for local experiments
  - much closer to product-like Chinese query retrieval than toy FAQ fixtures
- Good metrics:
  - `nDCG@10`
  - `Recall@10`
  - `latency_ms`
  - `index_size_mb`
- Suggested use:
  - Chinese embedding retrieval reference fixture

Source:
- [mteb/DuRetrieval](https://huggingface.co/datasets/mteb/DuRetrieval)

### 3. CMedQAv2-reranking

- Best for: Chinese FAQ-like or QA-style reranking
- Why it fits:
  - query + candidate list + labels structure is close to FAQ reranking
  - small enough to prototype locally
  - useful even outside the medical domain because the evaluation shape matches user question to candidate answer ranking
- Good metrics:
  - `MRR`
  - `nDCG@10`
  - `rerank_latency_ms`
  - `top_k_hit_rate`
- Suggested use:
  - default Chinese reranking benchmark
  - analyze whether reranking materially improves top-1 quality after retrieval

Source:
- [mteb/CMedQAv2-reranking](https://huggingface.co/datasets/mteb/CMedQAv2-reranking)

## Strong Secondary Choices

### 4. T2Reranking

- Best for: larger-scale Chinese reranking analysis
- Why it fits:
  - Chinese passage ranking benchmark
  - more suitable than tiny toy datasets when comparing rerankers seriously
- Suggested use:
  - second-stage reranker benchmark after CMedQAv2

Source:
- [mteb/T2Reranking](https://huggingface.co/datasets/mteb/T2Reranking)

### 5. MIRACL

- Best for: multilingual retrieval, especially Chinese and English side-by-side
- Why it fits:
  - 18-language retrieval benchmark
  - good for testing multilingual embedding models
- Tradeoff:
  - large
  - not ideal as a default local fixture
- Suggested use:
  - sampled multilingual benchmark
  - performance and index-size stress testing

Sources:
- [MIRACL GitHub](https://github.com/project-miracl/miracl)
- [mteb/MIRACLRetrieval](https://huggingface.co/datasets/mteb/MIRACLRetrieval)

### 6. MS MARCO Passage Ranking

- Best for: English reranking quality analysis
- Why it fits:
  - standard passage reranking benchmark
  - directly matches "retrieve candidates then rerank" architecture
- Tradeoff:
  - large
  - non-commercial research terms apply
- Suggested use:
  - heavyweight English reranking benchmark
  - not a default repo fixture

Sources:
- [MS MARCO datasets](https://microsoft.github.io/msmarco/Datasets.html)
- [MSMARCO Passage Ranking](https://microsoft.github.io/MSMARCO-Passage-Ranking/)

## How To Use Them In AutoOptimize

### Embedding Accuracy

Recommended datasets:

- English: `SciFact`
- Chinese: `DuRetrieval`
- Multilingual: `MIRACL`

Recommended metrics:

- `nDCG@10`
- `Recall@10`
- `MRR`

### Reranking Capability

Recommended datasets:

- Chinese FAQ-like: `CMedQAv2-reranking`
- Chinese larger-scale: `T2Reranking`
- English larger-scale: `MS MARCO Passage Ranking`

Recommended metrics:

- `MRR`
- `nDCG@10`
- `top1_accuracy`
- `rerank_gain_over_retrieval`

### Performance And Speed

Use the same public dataset with a fixed local sample.

Recommended metrics:

- `embed_query_latency_ms`
- `embed_doc_latency_ms`
- `retrieve_latency_ms`
- `rerank_latency_ms`
- `queries_per_second`

### Embedding / Index Size

Use the same corpus and compare:

- `embedding_dimension`
- `embedding_bytes_per_doc`
- `index_size_mb`
- `model_disk_size_mb`

## Suggested Repo Strategy

Use three levels of benchmark weight:

1. `default-local`
   - SciFact
   - DuRetrieval
   - CMedQAv2-reranking
2. `extended-local`
   - T2Reranking
   - sampled MIRACL zh/en
3. `heavyweight`
   - full MIRACL slices
   - MS MARCO reranking

This keeps the repo practical while still giving the skill a credible path toward real retrieval and reranking evaluation.
