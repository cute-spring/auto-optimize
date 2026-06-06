#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]


def _load_yaml(relative_path: str) -> dict:
    path = WORKSPACE_ROOT / relative_path
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _round_metrics(metrics: dict[str, float | int | bool]) -> dict[str, float | int | bool]:
    rounded: dict[str, float | int | bool] = {}
    for key, value in metrics.items():
        if isinstance(value, float):
            rounded[key] = round(value, 3)
        else:
            rounded[key] = value
    return rounded


def _apply_adjustments(metrics: dict[str, float | int | bool], adjustments: dict[str, float | int]) -> None:
    for key, delta in adjustments.items():
        metrics[key] += delta


def _calculate_metrics() -> dict[str, float | int | bool]:
    retrieval = _load_yaml("configs/retrieval.yaml").get("retrieval", {})
    reranker = _load_yaml("configs/reranker.yaml")
    embedding = _load_yaml("configs/embedding_strategy.yaml").get("embedding", {})

    metrics: dict[str, float | int | bool] = {
        "top1_accuracy": 0.892,
        "hit_at_3": 0.961,
        "recall_at_10": 0.982,
        "mrr": 0.781,
        "hard_negative_error_rate": 0.047,
        "embed_query_latency_p95_ms": 42,
        "rerank_latency_p95_ms": 96,
        "index_size_mb": 384,
        "all_tests_pass": True,
    }

    top_k_adjustments = {
        5: {
            "top1_accuracy": -0.006,
            "hit_at_3": -0.005,
            "recall_at_10": -0.012,
            "mrr": -0.004,
            "embed_query_latency_p95_ms": -3,
            "rerank_latency_p95_ms": -8,
        },
        20: {
            "top1_accuracy": 0.004,
            "hit_at_3": 0.003,
            "recall_at_10": 0.006,
            "mrr": 0.002,
            "embed_query_latency_p95_ms": 4,
            "rerank_latency_p95_ms": 18,
        },
    }
    threshold_adjustments = {
        0.78: {
            "top1_accuracy": 0.003,
            "hit_at_3": 0.002,
            "recall_at_10": 0.001,
            "mrr": 0.003,
            "hard_negative_error_rate": -0.003,
        },
        0.86: {
            "top1_accuracy": -0.004,
            "recall_at_10": -0.006,
            "mrr": -0.003,
            "hard_negative_error_rate": 0.004,
        },
    }
    faq_template_adjustments = {
        "question_only": {
            "top1_accuracy": -0.01,
            "recall_at_10": -0.004,
            "index_size_mb": -48,
        },
        "question_title_answer_bilingual": {
            "top1_accuracy": 0.004,
            "hit_at_3": 0.003,
            "recall_at_10": 0.002,
            "mrr": 0.003,
            "embed_query_latency_p95_ms": 8,
            "index_size_mb": 96,
        },
    }
    query_template_adjustments = {
        "raw_query": {
            "top1_accuracy": -0.007,
            "mrr": -0.006,
            "embed_query_latency_p95_ms": -2,
        },
        "bilingual_expansion": {
            "top1_accuracy": 0.006,
            "hit_at_3": 0.002,
            "recall_at_10": 0.003,
            "mrr": 0.005,
            "embed_query_latency_p95_ms": 11,
            "index_size_mb": 20,
        },
    }

    top_k = retrieval.get("top_k", 10)
    threshold = round(float(retrieval.get("threshold", 0.82)), 2)
    reranker_enabled = bool(reranker.get("enabled", True))
    faq_template = embedding.get("faq_template", "question_with_answer")
    query_template = embedding.get("query_template", "normalized_query")
    multilingual_normalization = bool(embedding.get("multilingual_normalization", True))

    _apply_adjustments(metrics, top_k_adjustments.get(top_k, {}))
    _apply_adjustments(metrics, threshold_adjustments.get(threshold, {}))
    _apply_adjustments(metrics, faq_template_adjustments.get(faq_template, {}))
    _apply_adjustments(metrics, query_template_adjustments.get(query_template, {}))

    if not reranker_enabled:
        _apply_adjustments(
            metrics,
            {
                "top1_accuracy": -0.018,
                "hit_at_3": -0.012,
                "recall_at_10": -0.002,
                "mrr": -0.028,
                "hard_negative_error_rate": 0.01,
                "rerank_latency_p95_ms": -54,
                "index_size_mb": -12,
            },
        )

    if not multilingual_normalization:
        _apply_adjustments(
            metrics,
            {
                "top1_accuracy": -0.003,
                "hit_at_3": -0.001,
                "hard_negative_error_rate": 0.003,
                "embed_query_latency_p95_ms": -2,
            },
        )

    metrics["top1_accuracy"] = min(max(metrics["top1_accuracy"], 0.0), 0.999)
    metrics["hit_at_3"] = min(max(metrics["hit_at_3"], 0.0), 0.999)
    metrics["recall_at_10"] = min(max(metrics["recall_at_10"], 0.0), 0.999)
    metrics["mrr"] = min(max(metrics["mrr"], 0.0), 0.999)
    metrics["hard_negative_error_rate"] = min(max(metrics["hard_negative_error_rate"], 0.0), 0.999)
    metrics["embed_query_latency_p95_ms"] = int(metrics["embed_query_latency_p95_ms"])
    metrics["rerank_latency_p95_ms"] = int(metrics["rerank_latency_p95_ms"])
    metrics["index_size_mb"] = int(metrics["index_size_mb"])
    return _round_metrics(metrics)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--fail-on-top-k", type=int)
    args = parser.parse_args()

    if not args.json:
        return 1

    current_top_k = _load_yaml("configs/retrieval.yaml").get("retrieval", {}).get("top_k", 10)
    if args.fail_on_top_k is not None and current_top_k == args.fail_on_top_k:
        return 2

    payload = _calculate_metrics()
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
