from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class DatasetExportResult:
    dataset_key: str
    source_dir: Path
    export_dir: Path
    manifest_path: Path


HF_MULTI_CONFIG_EXPORTS: dict[str, dict[str, list[str] | list[str]]] = {
    "du_retrieval": {
        "required_configs": ["corpus", "queries", "default"],
        "optional_configs": [],
    },
    "cmedqa_reranking": {
        "required_configs": ["corpus", "queries", "default", "top_ranked"],
        "optional_configs": [],
    },
    "t2_reranking": {
        "required_configs": ["corpus", "queries", "default", "top_ranked"],
        "optional_configs": [],
    },
}


def _require_datasets():
    try:
        from datasets import Dataset, DatasetDict, load_from_disk  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "The 'datasets' package is required to export normalized benchmark data from a saved Hugging Face dataset."
        ) from exc
    return Dataset, DatasetDict, load_from_disk


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _pick(row: dict[str, Any], aliases: list[str], *, required: bool = True, default: Any = None) -> Any:
    for alias in aliases:
        if alias in row and row[alias] is not None:
            return row[alias]
    if required:
        raise KeyError(f"Missing required fields {aliases} in row keys {sorted(row)}")
    return default


def _listify_terms(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        return [term for term in value.split() if term]
    return [str(value)]


def _rows_from_split(dataset_dict: Any, split_name: str) -> list[dict[str, Any]]:
    if split_name not in dataset_dict:
        return []
    return [dict(row) for row in dataset_dict[split_name]]


def _rows_from_loaded_dataset(loaded: Any) -> list[dict[str, Any]]:
    try:
        split_names = list(loaded.keys())
    except Exception:
        return [dict(row) for row in loaded]
    if not split_names:
        return []
    first_split = split_names[0]
    return [dict(row) for row in loaded[first_split]]


def _normalize_corpus_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        normalized.append(
            {
                "id": str(_pick(row, ["id", "doc_id", "corpus_id", "_id"])),
                "title": str(_pick(row, ["title", "heading", "name"], required=False, default="")),
                "text": str(_pick(row, ["text", "contents", "body", "document", "answer"], required=False, default="")),
                "question": str(_pick(row, ["question"], required=False, default="")),
                "answer": str(_pick(row, ["answer"], required=False, default="")),
            }
        )
    return normalized


def _normalize_query_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        normalized.append(
            {
                "id": str(_pick(row, ["id", "query_id", "qid", "_id"])),
                "text": str(_pick(row, ["text", "query", "question"])),
            }
        )
    return normalized


def _normalize_qrels(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    qrels: dict[str, dict[str, int]] = {}
    for row in rows:
        query_id = str(_pick(row, ["query_id", "qid", "query-id", "id"]))
        doc_id = str(_pick(row, ["doc_id", "corpus_id", "corpus-id", "docid", "pid"]))
        score = int(_pick(row, ["score", "relevance", "label"], required=False, default=1))
        qrels.setdefault(query_id, {})[doc_id] = score
    return qrels


def _normalize_candidates(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        query_id = str(_pick(row, ["query_id", "qid", "query-id", "id"]))
        doc_id = str(_pick(row, ["doc_id", "corpus_id", "corpus-id", "docid", "pid"]))
        baseline_score = float(_pick(row, ["baseline_score", "score", "retrieval_score"], required=False, default=0.0))
        rank = int(_pick(row, ["rank"], required=False, default=0))
        grouped.setdefault(query_id, []).append(
            {
                "doc_id": doc_id,
                "baseline_score": baseline_score,
                "rank": rank,
            }
        )
    for query_id, items in grouped.items():
        grouped[query_id] = sorted(items, key=lambda item: (item["rank"], -item["baseline_score"], item["doc_id"]))
    return grouped


def _normalize_top_ranked(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        query_id = str(_pick(row, ["query-id", "query_id", "qid", "id"]))
        doc_ids = _pick(row, ["corpus-ids", "doc_ids", "corpus_ids"])
        candidate_rows: list[dict[str, Any]] = []
        for index, doc_id in enumerate(doc_ids, start=1):
            candidate_rows.append(
                {
                    "doc_id": str(doc_id),
                    "baseline_score": float(max(len(doc_ids) - index, 0)),
                    "rank": index,
                }
            )
        grouped[query_id] = candidate_rows
    return grouped


def _normalize_query_expansions(rows: list[dict[str, Any]]) -> dict[str, dict[str, list[str]]]:
    grouped: dict[str, dict[str, list[str]]] = {}
    for row in rows:
        query_id = str(_pick(row, ["query_id", "qid", "query-id", "id"]))
        mode = str(_pick(row, ["mode", "template"], required=False, default="default"))
        terms = _listify_terms(_pick(row, ["terms", "tokens", "expansion_terms", "expansion"], required=False, default=[]))
        grouped.setdefault(query_id, {})[mode] = terms
    return grouped


def _summarize_export(files_written: list[str], corpus_rows: list[dict[str, Any]], query_rows: list[dict[str, Any]], qrels: dict[str, dict[str, int]], candidates: dict[str, list[dict[str, Any]]] | None) -> dict[str, Any]:
    return {
        "files_written": files_written,
        "corpus_rows": len(corpus_rows),
        "query_rows": len(query_rows),
        "qrels_queries": len(qrels),
        "candidate_queries": None if candidates is None else len(candidates),
    }


def _load_hf_multi_config_rows(dataset_key: str, dataset_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    _, _, load_from_disk = _require_datasets()
    config_spec = HF_MULTI_CONFIG_EXPORTS[dataset_key]
    required_configs = config_spec["required_configs"]

    missing = [config_name for config_name in required_configs if not (dataset_dir / config_name).exists()]
    if missing:
        raise ValueError(
            f"Could not export dataset: expected saved Hugging Face config directories {required_configs} under {dataset_dir}, missing {missing}."
        )

    corpus_rows = _rows_from_loaded_dataset(load_from_disk(str(dataset_dir / "corpus")))
    query_rows = _rows_from_loaded_dataset(load_from_disk(str(dataset_dir / "queries")))
    qrels_rows = _rows_from_loaded_dataset(load_from_disk(str(dataset_dir / "default")))
    top_ranked_rows = (
        _rows_from_loaded_dataset(load_from_disk(str(dataset_dir / "top_ranked")))
        if (dataset_dir / "top_ranked").exists()
        else []
    )
    query_expansion_rows = (
        _rows_from_loaded_dataset(load_from_disk(str(dataset_dir / "query_expansions")))
        if (dataset_dir / "query_expansions").exists()
        else []
    )
    return corpus_rows, query_rows, qrels_rows, top_ranked_rows, query_expansion_rows


def export_dataset_from_disk(dataset_key: str, dataset_dir: Path, export_dir: Path | None = None) -> DatasetExportResult:
    _, DatasetDict, load_from_disk = _require_datasets()

    dataset_dir = dataset_dir.resolve()
    export_root = (export_dir or dataset_dir / "auto_optimize_export").resolve()
    export_root.mkdir(parents=True, exist_ok=True)

    if dataset_key in HF_MULTI_CONFIG_EXPORTS and all((dataset_dir / config_name).exists() for config_name in HF_MULTI_CONFIG_EXPORTS[dataset_key]["required_configs"]):
        corpus_source_rows, query_source_rows, qrels_source_rows, top_ranked_rows, query_expansion_rows = _load_hf_multi_config_rows(
            dataset_key,
            dataset_dir,
        )
        corpus_rows = _normalize_corpus_rows(corpus_source_rows)
        query_rows = _normalize_query_rows(query_source_rows)
        qrels = _normalize_qrels(qrels_source_rows)
        candidates = _normalize_top_ranked(top_ranked_rows) if top_ranked_rows else None
        query_expansions = _normalize_query_expansions(query_expansion_rows) if query_expansion_rows else None
    else:
        loaded = load_from_disk(str(dataset_dir))
        if not isinstance(loaded, DatasetDict):
            raise ValueError(f"Expected a DatasetDict at {dataset_dir}, but found {type(loaded).__name__}.")

        corpus_rows = _normalize_corpus_rows(_rows_from_split(loaded, "corpus"))
        query_rows = _normalize_query_rows(_rows_from_split(loaded, "queries"))
        qrels = _normalize_qrels(_rows_from_split(loaded, "qrels"))
        candidates_rows = _rows_from_split(loaded, "candidates")
        query_expansion_rows = _rows_from_split(loaded, "query_expansions")

        if not corpus_rows or not query_rows or not qrels:
            raise ValueError(
                "Could not export dataset: expected dataset splits `corpus`, `queries`, and `qrels` with supported columns."
            )
        candidates = _normalize_candidates(candidates_rows) if candidates_rows else None
        query_expansions = _normalize_query_expansions(query_expansion_rows) if query_expansion_rows else None

    if not corpus_rows or not query_rows or not qrels:
        raise ValueError(
            "Could not export dataset: missing normalized corpus, queries, or qrels after schema adaptation."
        )

    files_written = ["corpus.jsonl", "queries.jsonl", "qrels.json"]
    _write_jsonl(export_root / "corpus.jsonl", corpus_rows)
    _write_jsonl(export_root / "queries.jsonl", query_rows)
    _write_json(export_root / "qrels.json", qrels)

    if candidates is not None:
        _write_json(export_root / "candidates.json", candidates)
        files_written.append("candidates.json")
    if query_expansions is not None:
        _write_json(export_root / "query_expansions.json", query_expansions)
        files_written.append("query_expansions.json")

    manifest_path = export_root / "auto_optimize_export_manifest.json"
    _write_json(
        manifest_path,
        {
            "dataset_key": dataset_key,
            "source_dir": str(dataset_dir),
            "export_dir": str(export_root),
            "summary": _summarize_export(files_written, corpus_rows, query_rows, qrels, candidates),
        },
    )
    return DatasetExportResult(
        dataset_key=dataset_key,
        source_dir=dataset_dir,
        export_dir=export_root,
        manifest_path=manifest_path,
    )
