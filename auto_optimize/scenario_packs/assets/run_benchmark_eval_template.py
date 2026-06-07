#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

import yaml

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]


def _load_yaml(relative_path: str) -> dict:
    path = WORKSPACE_ROOT / relative_path
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _load_json(relative_path: str, default):
    path = WORKSPACE_ROOT / relative_path
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(relative_path: str) -> list[dict]:
    path = WORKSPACE_ROOT / relative_path
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return numerator / (left_norm * right_norm)


def _load_provider_config() -> dict:
    provider = _load_yaml("configs/provider.yaml").get("provider", {})
    if not provider:
        return {
            "mode": "sample",
            "allow_fallback_to_sample": True,
            "model_name": None,
        }
    return provider


def _resolve_sentence_transformer_model_name(provider: dict, embedding_model_name: str | None) -> str:
    if provider.get("model_name"):
        return str(provider["model_name"])
    alias_map = {
        "gte-base-en": "thenlper/gte-base",
        "bge-base-en-v1.5": "BAAI/bge-base-en-v1.5",
        "e5-base-v2": "intfloat/e5-base-v2",
        "gte-multilingual-base": "Alibaba-NLP/gte-multilingual-base",
        "bge-large-zh-v1.5": "BAAI/bge-large-zh-v1.5",
        "qwen3-embedding-4b": "Alibaba-NLP/gte-multilingual-base",
    }
    if embedding_model_name and embedding_model_name in alias_map:
        return alias_map[embedding_model_name]
    return "sentence-transformers/all-MiniLM-L6-v2"


def _resolve_cross_encoder_model_name(provider: dict, reranker_model_name: str | None) -> str:
    if provider.get("model_name"):
        return str(provider["model_name"])
    alias_map = {
        "gte-reranker-modernbert-base": "cross-encoder/ms-marco-MiniLM-L-6-v2",
        "bge-reranker-v2-m3": "BAAI/bge-reranker-v2-m3",
        "qwen3-reranker-4b": "cross-encoder/ms-marco-MiniLM-L-12-v2",
    }
    if reranker_model_name and reranker_model_name in alias_map:
        return alias_map[reranker_model_name]
    return "cross-encoder/ms-marco-MiniLM-L-6-v2"


def _tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    current: list[str] = []
    for char in text.lower():
        if char.isascii() and char.isalnum():
            current.append(char)
            continue
        if current:
            tokens.append("".join(current))
            current = []
        if "\u4e00" <= char <= "\u9fff":
            tokens.append(char)
    if current:
        tokens.append("".join(current))
    return tokens


def _document_text(document: dict) -> str:
    return " ".join(str(document.get(field, "")) for field in ("title", "text", "question", "answer")).strip()


def _token_overlap_score(query_tokens: list[str], document_tokens: list[str]) -> float:
    query_set = set(query_tokens)
    if not query_set:
        return 0.0
    overlap = sum(1 for token in document_tokens if token in query_set)
    normalization = math.sqrt(max(len(document_tokens), 1))
    return overlap / normalization


def _compute_rankings(query_tokens_by_id: dict[str, list[str]], corpus: list[dict], model_quality_bonus: float = 0.0) -> dict[str, list[str]]:
    corpus_tokens = {doc["id"]: _tokenize(_document_text(doc)) for doc in corpus}
    ranked: dict[str, list[str]] = {}
    for query_id, query_tokens in query_tokens_by_id.items():
        scored = []
        for document in corpus:
            score = _token_overlap_score(query_tokens, corpus_tokens[document["id"]]) + model_quality_bonus
            scored.append((score, document["id"]))
        scored.sort(key=lambda item: (-item[0], item[1]))
        ranked[query_id] = [doc_id for _, doc_id in scored]
    return ranked


def _compute_rankings_with_sentence_transformers(
    queries: list[dict],
    corpus: list[dict],
    provider: dict,
    embedding_model_name: str | None,
) -> tuple[dict[str, list[str]], dict[str, float]]:
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
    except ImportError as exc:
        raise RuntimeError("sentence-transformers is not installed for provider.mode=sentence_transformers") from exc

    model_name = _resolve_sentence_transformer_model_name(provider, embedding_model_name)
    start = time.perf_counter()
    model = SentenceTransformer(model_name)
    model_load_ms = (time.perf_counter() - start) * 1000.0

    doc_texts = [_document_text(doc) for doc in corpus]
    query_texts = [query["text"] for query in queries]

    start = time.perf_counter()
    doc_embeddings = model.encode(doc_texts, normalize_embeddings=True)
    doc_latency_ms = ((time.perf_counter() - start) * 1000.0) / max(len(doc_texts), 1)

    start = time.perf_counter()
    query_embeddings = model.encode(query_texts, normalize_embeddings=True)
    query_latency_ms = ((time.perf_counter() - start) * 1000.0) / max(len(query_texts), 1)

    ranked: dict[str, list[str]] = {}
    for query, query_vector in zip(queries, query_embeddings):
        scored = []
        for document, doc_vector in zip(corpus, doc_embeddings):
            scored.append((_cosine_similarity(query_vector.tolist(), doc_vector.tolist()), document["id"]))
        scored.sort(key=lambda item: (-item[0], item[1]))
        ranked[query["id"]] = [doc_id for _, doc_id in scored]

    embedding_dimension = int(len(doc_embeddings[0])) if len(doc_embeddings) > 0 else 0
    metrics = {
        "provider_query_latency_ms": query_latency_ms,
        "provider_doc_latency_ms": doc_latency_ms,
        "provider_model_load_ms": model_load_ms,
        "provider_embedding_dimension": embedding_dimension,
    }
    return ranked, metrics


def _recall_at_k(ranked: list[str], relevant: dict[str, int], k: int) -> float:
    if not relevant:
        return 0.0
    retrieved = sum(1 for doc_id in ranked[:k] if doc_id in relevant)
    return retrieved / len(relevant)


def _mrr(ranked: list[str], relevant: dict[str, int]) -> float:
    for index, doc_id in enumerate(ranked, start=1):
        if doc_id in relevant:
            return 1.0 / index
    return 0.0


def _dcg(ranked: list[str], relevant: dict[str, int], k: int) -> float:
    total = 0.0
    for index, doc_id in enumerate(ranked[:k], start=1):
        rel = relevant.get(doc_id, 0)
        if rel > 0:
            total += rel / math.log2(index + 1)
    return total


def _ndcg_at_k(ranked: list[str], relevant: dict[str, int], k: int) -> float:
    actual = _dcg(ranked, relevant, k)
    ideal = _dcg([doc_id for doc_id, _ in sorted(relevant.items(), key=lambda item: -item[1])], relevant, k)
    if ideal == 0:
        return 0.0
    return actual / ideal


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _round_metrics(metrics: dict) -> dict:
    rounded = {}
    for key, value in metrics.items():
        if isinstance(value, float):
            rounded[key] = round(value, 3)
        else:
            rounded[key] = value
    return rounded


def _clamp_metric(value: float) -> float:
    return max(0.0, min(1.0, value))


def _apply_quality_adjustments(metrics: dict, adjustments: dict[str, float]) -> None:
    for key, delta in adjustments.items():
        metrics[key] = _clamp_metric(metrics[key] + delta)


def _query_tokens_by_mode(queries: list[dict], mode: str, expansions: dict[str, dict[str, list[str]]]) -> dict[str, list[str]]:
    tokens: dict[str, list[str]] = {}
    for query in queries:
        query_id = query["id"]
        query_tokens = _tokenize(query["text"])
        query_tokens.extend(expansions.get(query_id, {}).get(mode, []))
        tokens[query_id] = query_tokens
    return tokens


def _query_text_by_mode(query: dict, mode: str, expansions: dict[str, dict[str, list[str]]]) -> str:
    query_id = query["id"]
    terms = expansions.get(query_id, {}).get(mode, [])
    suffix = f" {' '.join(terms)}" if terms else ""
    return f"{query['text']}{suffix}".strip()


def _sample_rerank(
    corpus: dict[str, dict],
    initial_ranking: list[dict],
    query_tokens: list[str],
    top_n: int,
) -> list[str]:
    reranked_head = []
    for item in initial_ranking[:top_n]:
        doc = corpus[item["doc_id"]]
        score = item["baseline_score"] + _token_overlap_score(query_tokens, _tokenize(_document_text(doc)))
        reranked_head.append((score, item["doc_id"]))
    reranked_head.sort(key=lambda pair: (-pair[0], pair[1]))
    return [doc_id for _, doc_id in reranked_head] + [item["doc_id"] for item in initial_ranking[top_n:]]


def _rerank_with_cross_encoder(
    queries: list[dict],
    corpus: dict[str, dict],
    candidates: dict[str, list[dict]],
    provider: dict,
    reranker_model_name: str | None,
    mode: str,
    expansions: dict[str, dict[str, list[str]]],
    top_n: int,
    initial_top_k: int,
) -> tuple[dict[str, list[str]], dict[str, float]]:
    try:
        from sentence_transformers import CrossEncoder  # type: ignore
    except ImportError as exc:
        raise RuntimeError("sentence-transformers is not installed for provider.mode=cross_encoder") from exc

    model_name = _resolve_cross_encoder_model_name(provider, reranker_model_name)
    start = time.perf_counter()
    model = CrossEncoder(model_name)
    model_load_ms = (time.perf_counter() - start) * 1000.0

    reranked: dict[str, list[str]] = {}
    per_query_latencies: list[float] = []
    pairs_scored = 0

    for query in queries:
        query_id = query["id"]
        initial_ranking = candidates[query_id][:initial_top_k]
        query_text = _query_text_by_mode(query, mode, expansions)
        pairs = []
        doc_ids = []
        for item in initial_ranking[:top_n]:
            doc = corpus[item["doc_id"]]
            pairs.append((query_text, _document_text(doc)))
            doc_ids.append(item["doc_id"])

        start = time.perf_counter()
        scores = model.predict(pairs)
        per_query_latencies.append((time.perf_counter() - start) * 1000.0)
        pairs_scored += len(pairs)

        reranked_head = list(zip(scores.tolist(), doc_ids))
        reranked_head.sort(key=lambda pair: (-pair[0], pair[1]))
        reranked[query_id] = [doc_id for _, doc_id in reranked_head] + [item["doc_id"] for item in initial_ranking[top_n:]]

    latency_ms = max(per_query_latencies) if per_query_latencies else 0.0
    metrics = {
        "provider_rerank_latency_ms": latency_ms,
        "provider_model_load_ms": model_load_ms,
        "provider_pairs_scored": float(pairs_scored),
        "provider_latency_per_candidate_ms": (latency_ms / max(top_n, 1)) if top_n else 0.0,
    }
    return reranked, metrics


def _evaluate_retrieval_embedding(manifest: dict) -> dict:
    corpus = _load_jsonl("data/corpus.jsonl")
    queries = _load_jsonl("data/queries.jsonl")
    qrels = _load_json("data/qrels.json", {})
    expansions = _load_json("data/query_expansions.json", {})
    retrieval = _load_yaml("configs/retrieval.yaml").get("retrieval", {})
    embedding = _load_yaml("configs/embedding.yaml").get("embedding", {})
    query_config = _load_yaml("configs/query_processing.yaml").get("query", {})
    provider = _load_provider_config()

    dataset_key = manifest["dataset_key"]
    if dataset_key == "beir_scifact":
        mode = "retrieval_query_prefix" if embedding.get("query_instruction_mode") == "retrieval_query_prefix" else "default"
        model_name = embedding.get("model_name", "gte-base-en")
    else:
        mode = query_config.get("template", "raw_query")
        if query_config.get("multilingual_normalization"):
            mode = f"{mode}+multilingual"
        model_name = embedding.get("model_name", "gte-multilingual-base")

    model_quality_bonus = {
        "bge-base-en-v1.5": 0.015,
        "e5-base-v2": 0.008,
        "gte-base-en": 0.0,
        "bge-large-zh-v1.5": 0.018,
        "gte-multilingual-base": 0.0,
        "qwen3-embedding-4b": 0.01,
    }.get(model_name, 0.0)

    provider_metrics: dict[str, float] = {}
    if provider.get("mode") == "sentence_transformers":
        try:
            ranked, provider_metrics = _compute_rankings_with_sentence_transformers(queries, corpus, provider, model_name)
        except Exception:
            if not provider.get("allow_fallback_to_sample", True):
                raise
            ranked = _compute_rankings(_query_tokens_by_mode(queries, mode, expansions), corpus, model_quality_bonus=model_quality_bonus)
            provider_metrics["provider_fallback_used"] = 1.0
        else:
            provider_metrics["provider_fallback_used"] = 0.0
    else:
        ranked = _compute_rankings(_query_tokens_by_mode(queries, mode, expansions), corpus, model_quality_bonus=model_quality_bonus)
        provider_metrics["provider_fallback_used"] = 0.0
    top_k = int(retrieval.get("top_k", 10))
    recall_cutoff = min(50, max(top_k, 10))

    top1_values: list[float] = []
    recall10_values: list[float] = []
    recall50_values: list[float] = []
    mrr_values: list[float] = []
    ndcg_values: list[float] = []
    for query in queries:
        relevant = qrels.get(query["id"], {})
        ranking = ranked[query["id"]]
        top1_values.append(1.0 if ranking[:1] and ranking[0] in relevant else 0.0)
        recall10_values.append(_recall_at_k(ranking, relevant, min(10, top_k)))
        recall50_values.append(_recall_at_k(ranking, relevant, recall_cutoff))
        mrr_values.append(_mrr(ranking[:top_k], relevant))
        ndcg_values.append(_ndcg_at_k(ranking[:top_k], relevant, min(10, top_k)))

    metrics = {
        "ndcg_at_10": _mean(ndcg_values),
        "top1_accuracy": _mean(top1_values),
        "recall_at_10": _mean(recall10_values),
        "recall_at_50": _mean(recall50_values),
        "mrr": _mean(mrr_values),
    }

    if dataset_key == "beir_scifact":
        adjustment = {"ndcg_at_10": -0.055, "top1_accuracy": -0.08, "recall_at_10": -0.05, "recall_at_50": -0.03, "mrr": -0.06}
        _apply_quality_adjustments(metrics, adjustment)
        if model_name == "e5-base-v2":
            _apply_quality_adjustments(metrics, {"ndcg_at_10": 0.012, "top1_accuracy": 0.01, "recall_at_10": 0.008, "mrr": 0.01})
        if model_name == "bge-base-en-v1.5":
            _apply_quality_adjustments(metrics, {"ndcg_at_10": 0.028, "top1_accuracy": 0.024, "recall_at_10": 0.015, "recall_at_50": 0.01, "mrr": 0.02})
        if mode == "retrieval_query_prefix":
            _apply_quality_adjustments(metrics, {"ndcg_at_10": 0.03, "top1_accuracy": 0.028, "recall_at_10": 0.018, "mrr": 0.024})
    else:
        _apply_quality_adjustments(metrics, {"ndcg_at_10": -0.045, "top1_accuracy": -0.065, "recall_at_10": -0.045, "recall_at_50": -0.025, "mrr": -0.05})
        if model_name == "qwen3-embedding-4b":
            _apply_quality_adjustments(metrics, {"ndcg_at_10": 0.014, "top1_accuracy": 0.012, "recall_at_10": 0.01, "mrr": 0.01})
        if model_name == "bge-large-zh-v1.5":
            _apply_quality_adjustments(metrics, {"ndcg_at_10": 0.03, "top1_accuracy": 0.024, "recall_at_10": 0.018, "recall_at_50": 0.01, "mrr": 0.022})
        if mode.startswith("normalized_query"):
            _apply_quality_adjustments(metrics, {"ndcg_at_10": 0.022, "top1_accuracy": 0.016, "recall_at_10": 0.014, "mrr": 0.016})
        if mode.startswith("keyword_augmented_query"):
            _apply_quality_adjustments(metrics, {"ndcg_at_10": 0.036, "top1_accuracy": 0.025, "recall_at_10": 0.022, "recall_at_50": 0.01, "mrr": 0.024})
        if mode.endswith("+multilingual"):
            _apply_quality_adjustments(metrics, {"ndcg_at_10": 0.012, "top1_accuracy": 0.01, "recall_at_10": 0.008, "mrr": 0.01})

    if top_k == 20:
        _apply_quality_adjustments(metrics, {"ndcg_at_10": 0.01, "recall_at_10": 0.012, "recall_at_50": 0.008, "mrr": 0.006})
    elif top_k == 50:
        _apply_quality_adjustments(metrics, {"ndcg_at_10": 0.004, "recall_at_10": 0.018, "recall_at_50": 0.012, "mrr": 0.002})

    latency_base = 24 if dataset_key == "beir_scifact" else 32
    doc_latency_base = 3.0 if dataset_key == "beir_scifact" else 4.0
    index_base = 520 if dataset_key == "beir_scifact" else 760
    dimension_base = 768 if dataset_key == "beir_scifact" else 1024
    metrics["embed_query_latency_p95_ms"] = int(latency_base + (top_k // 10) * 2 + model_quality_bonus * 100)
    metrics["embed_doc_latency_ms"] = round(doc_latency_base + model_quality_bonus * 10, 3)
    metrics["index_size_mb"] = int(index_base + (0 if "gte" in model_name else 80 if "bge" in model_name else 160))
    metrics["embedding_dimension"] = int(dimension_base if "qwen3" not in model_name else 512)
    if provider.get("mode") == "sentence_transformers" and "provider_query_latency_ms" in provider_metrics:
        metrics["embed_query_latency_p95_ms"] = int(max(metrics["embed_query_latency_p95_ms"], round(provider_metrics["provider_query_latency_ms"])))
        metrics["embed_doc_latency_ms"] = round(max(metrics["embed_doc_latency_ms"], provider_metrics["provider_doc_latency_ms"]), 3)
        metrics["embedding_dimension"] = int(provider_metrics.get("provider_embedding_dimension", metrics["embedding_dimension"]))
    return _round_metrics(metrics)


def _evaluate_reranking(manifest: dict) -> dict:
    corpus = {doc["id"]: doc for doc in _load_jsonl("data/corpus.jsonl")}
    queries = _load_jsonl("data/queries.jsonl")
    qrels = _load_json("data/qrels.json", {})
    candidates = _load_json("data/candidates.json", {})
    expansions = _load_json("data/query_expansions.json", {})

    retrieval = _load_yaml("configs/retrieval.yaml").get("retrieval", {})
    reranker = _load_yaml("configs/reranker.yaml").get("reranker", {})
    query_config = _load_yaml("configs/query_processing.yaml").get("query", {})
    provider = _load_provider_config()

    mode = query_config.get("template", "raw_query")
    top_n = int(reranker.get("top_n", 50))
    initial_top_k = int(retrieval.get("initial_top_k", 100))
    provider_metrics: dict[str, float] = {}

    provider_reranked: dict[str, list[str]] | None = None
    if provider.get("mode") == "cross_encoder":
        try:
            provider_reranked, provider_metrics = _rerank_with_cross_encoder(
                queries=queries,
                corpus=corpus,
                candidates=candidates,
                provider=provider,
                reranker_model_name=reranker.get("model_name", "gte-reranker-modernbert-base"),
                mode=mode,
                expansions=expansions,
                top_n=top_n,
                initial_top_k=initial_top_k,
            )
        except Exception:
            if not provider.get("allow_fallback_to_sample", True):
                raise
            provider_metrics["provider_fallback_used"] = 1.0
        else:
            provider_metrics["provider_fallback_used"] = 0.0
    else:
        provider_metrics["provider_fallback_used"] = 0.0

    mrr_values: list[float] = []
    top1_values: list[float] = []
    ndcg_values: list[float] = []
    gain_values: list[float] = []
    recovered_values: list[float] = []
    depth_values: list[float] = []

    for query in queries:
        query_id = query["id"]
        query_tokens = _query_tokens_by_mode([query], mode, expansions)[query_id]
        initial_ranking = candidates[query_id][:initial_top_k]
        baseline_docs = [item["doc_id"] for item in initial_ranking]
        relevant = qrels.get(query_id, {})
        reranked = (
            provider_reranked[query_id]
            if provider_reranked is not None
            else _sample_rerank(corpus, initial_ranking, query_tokens, top_n)
        )

        baseline_mrr = _mrr(baseline_docs, relevant)
        reranked_mrr = _mrr(reranked, relevant)
        mrr_values.append(reranked_mrr)
        top1_values.append(1.0 if reranked[:1] and reranked[0] in relevant else 0.0)
        ndcg_values.append(_ndcg_at_k(reranked, relevant, 10))
        gain_values.append(reranked_mrr - baseline_mrr)
        recovered_values.append(1.0 if baseline_docs[:1] and baseline_docs[0] not in relevant and reranked[:1] and reranked[0] in relevant else 0.0)
        depth_values.append(1.0 if any(doc_id in relevant for doc_id in reranked[:top_n]) else 0.0)

    metrics = {
        "mrr": _mean(mrr_values),
        "top1_accuracy": _mean(top1_values),
        "ndcg_at_10": _mean(ndcg_values),
        "rerank_gain_over_retrieval": _mean(gain_values),
        "recovered_at_1_from_top10": _mean(recovered_values),
        "candidate_depth_sensitivity": _mean(depth_values),
        "rerank_latency_p95_ms": int(88 + top_n * 0.65),
        "latency_per_candidate_ms": round((88 + top_n * 0.65) / max(top_n, 1), 3),
    }

    _apply_quality_adjustments(metrics, {"mrr": -0.075, "top1_accuracy": -0.07, "ndcg_at_10": -0.06, "rerank_gain_over_retrieval": -0.04, "recovered_at_1_from_top10": -0.08, "candidate_depth_sensitivity": -0.06})
    if reranker.get("model_name") == "qwen3-reranker-4b":
        _apply_quality_adjustments(metrics, {"mrr": 0.016, "top1_accuracy": 0.012, "ndcg_at_10": 0.012, "rerank_gain_over_retrieval": 0.01, "recovered_at_1_from_top10": 0.014})
    if reranker.get("model_name") == "bge-reranker-v2-m3":
        _apply_quality_adjustments(metrics, {"mrr": 0.03, "top1_accuracy": 0.024, "ndcg_at_10": 0.02, "rerank_gain_over_retrieval": 0.018, "recovered_at_1_from_top10": 0.024, "candidate_depth_sensitivity": 0.014})
    if mode == "normalized_query":
        _apply_quality_adjustments(metrics, {"mrr": 0.026, "top1_accuracy": 0.02, "ndcg_at_10": 0.018, "rerank_gain_over_retrieval": 0.014, "recovered_at_1_from_top10": 0.018})
    if mode == "faq_style_query":
        _apply_quality_adjustments(metrics, {"mrr": 0.042, "top1_accuracy": 0.03, "ndcg_at_10": 0.024, "rerank_gain_over_retrieval": 0.02, "recovered_at_1_from_top10": 0.028, "candidate_depth_sensitivity": 0.018})
    if top_n == 20:
        _apply_quality_adjustments(metrics, {"mrr": -0.02, "top1_accuracy": -0.014, "ndcg_at_10": -0.012, "rerank_gain_over_retrieval": -0.01, "recovered_at_1_from_top10": -0.014})
    elif top_n == 100:
        _apply_quality_adjustments(metrics, {"mrr": 0.012, "top1_accuracy": 0.008, "ndcg_at_10": 0.008, "rerank_gain_over_retrieval": 0.01, "candidate_depth_sensitivity": 0.016})
    if initial_top_k == 50:
        _apply_quality_adjustments(metrics, {"mrr": -0.016, "top1_accuracy": -0.012, "ndcg_at_10": -0.012, "rerank_gain_over_retrieval": -0.012, "recovered_at_1_from_top10": -0.018, "candidate_depth_sensitivity": -0.016})
    elif initial_top_k == 200:
        _apply_quality_adjustments(metrics, {"mrr": 0.014, "top1_accuracy": 0.01, "ndcg_at_10": 0.01, "rerank_gain_over_retrieval": 0.014, "recovered_at_1_from_top10": 0.016, "candidate_depth_sensitivity": 0.02})

    if provider.get("mode") == "cross_encoder" and "provider_rerank_latency_ms" in provider_metrics:
        metrics["rerank_latency_p95_ms"] = int(max(metrics["rerank_latency_p95_ms"], round(provider_metrics["provider_rerank_latency_ms"])))
        metrics["latency_per_candidate_ms"] = round(
            max(metrics["latency_per_candidate_ms"], provider_metrics["provider_latency_per_candidate_ms"]),
            3,
        )
    metrics.update(provider_metrics)

    return _round_metrics(metrics)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if not args.json:
        return 1

    manifest = _load_json("data/benchmark_manifest.json", {})
    scenario_family = manifest["scenario_family"]
    if scenario_family == "retrieval_embedding":
        payload = _evaluate_retrieval_embedding(manifest)
    elif scenario_family == "reranking":
        payload = _evaluate_reranking(manifest)
    else:
        raise SystemExit(f"Unsupported scenario_family: {scenario_family}")

    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
