from __future__ import annotations

import json
from pathlib import Path

from auto_optimize.scenario_packs.dataset_export import export_dataset_from_disk


def _require_datasets():
    from datasets import Dataset, DatasetDict  # type: ignore

    return Dataset, DatasetDict


def test_export_retrieval_dataset_from_saved_hf_layout(tmp_path: Path) -> None:
    Dataset, DatasetDict = _require_datasets()

    dataset = DatasetDict(
        {
            "corpus": Dataset.from_dict(
                {
                    "id": ["d1", "d2"],
                    "title": ["Reset password", "Invoices"],
                    "text": ["How to reset password", "How to download invoices"],
                }
            ),
            "queries": Dataset.from_dict(
                {
                    "id": ["q1"],
                    "text": ["reset password"],
                }
            ),
            "qrels": Dataset.from_dict(
                {
                    "query_id": ["q1"],
                    "doc_id": ["d1"],
                    "score": [1],
                }
            ),
        }
    )
    source_dir = tmp_path / "hf_saved"
    dataset.save_to_disk(str(source_dir))

    result = export_dataset_from_disk("du_retrieval", source_dir)

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    corpus_rows = (result.export_dir / "corpus.jsonl").read_text(encoding="utf-8").splitlines()
    qrels = json.loads((result.export_dir / "qrels.json").read_text(encoding="utf-8"))

    assert manifest["dataset_key"] == "du_retrieval"
    assert manifest["summary"]["files_written"] == ["corpus.jsonl", "queries.jsonl", "qrels.json"]
    assert len(corpus_rows) == 2
    assert qrels == {"q1": {"d1": 1}}


def test_export_reranking_dataset_from_saved_hf_layout(tmp_path: Path) -> None:
    Dataset, DatasetDict = _require_datasets()

    dataset = DatasetDict(
        {
            "corpus": Dataset.from_dict(
                {
                    "id": ["d1", "d2"],
                    "question": ["Reset password", "Invoice"],
                    "answer": ["Use forgot password", "Open billing page"],
                }
            ),
            "queries": Dataset.from_dict(
                {
                    "id": ["q1"],
                    "query": ["password reset"],
                }
            ),
            "qrels": Dataset.from_dict(
                {
                    "qid": ["q1"],
                    "corpus_id": ["d1"],
                    "relevance": [1],
                }
            ),
            "candidates": Dataset.from_dict(
                {
                    "query_id": ["q1", "q1"],
                    "doc_id": ["d2", "d1"],
                    "baseline_score": [0.2, 0.1],
                    "rank": [1, 2],
                }
            ),
        }
    )
    source_dir = tmp_path / "hf_saved_rerank"
    dataset.save_to_disk(str(source_dir))

    result = export_dataset_from_disk("cmedqa_reranking", source_dir)

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    candidates = json.loads((result.export_dir / "candidates.json").read_text(encoding="utf-8"))

    assert manifest["summary"]["candidate_queries"] == 1
    assert candidates["q1"][0]["doc_id"] == "d2"


def test_export_multiconfig_mteb_style_layout(tmp_path: Path) -> None:
    Dataset, DatasetDict = _require_datasets()

    source_dir = tmp_path / "mteb_saved"
    DatasetDict(
        {
            "dev": Dataset.from_dict(
                {
                    "_id": ["d1", "d2"],
                    "text": ["Reset password help", "Invoice download help"],
                    "title": ["Reset", "Invoice"],
                }
            )
        }
    ).save_to_disk(str(source_dir / "corpus"))
    DatasetDict(
        {
            "dev": Dataset.from_dict(
                {
                    "_id": ["q1"],
                    "text": ["reset password"],
                }
            )
        }
    ).save_to_disk(str(source_dir / "queries"))
    DatasetDict(
        {
            "dev": Dataset.from_dict(
                {
                    "query-id": ["q1"],
                    "corpus-id": ["d1"],
                    "score": [1],
                }
            )
        }
    ).save_to_disk(str(source_dir / "default"))

    result = export_dataset_from_disk("du_retrieval", source_dir)

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    corpus_rows = [json.loads(line) for line in (result.export_dir / "corpus.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    qrels = json.loads((result.export_dir / "qrels.json").read_text(encoding="utf-8"))

    assert manifest["summary"]["corpus_rows"] == 2
    assert corpus_rows[0]["id"] == "d1"
    assert qrels == {"q1": {"d1": 1}}


def test_export_multiconfig_reranking_top_ranked_layout(tmp_path: Path) -> None:
    Dataset, DatasetDict = _require_datasets()

    source_dir = tmp_path / "mteb_rerank_saved"
    DatasetDict(
        {
            "test": Dataset.from_dict(
                {
                    "_id": ["d1", "d2"],
                    "text": ["Reset password help", "Invoice download help"],
                    "title": ["Reset", "Invoice"],
                }
            )
        }
    ).save_to_disk(str(source_dir / "corpus"))
    DatasetDict(
        {
            "test": Dataset.from_dict(
                {
                    "_id": ["q1"],
                    "text": ["reset password"],
                }
            )
        }
    ).save_to_disk(str(source_dir / "queries"))
    DatasetDict(
        {
            "test": Dataset.from_dict(
                {
                    "query-id": ["q1"],
                    "corpus-id": ["d1"],
                    "score": [1],
                }
            )
        }
    ).save_to_disk(str(source_dir / "default"))
    DatasetDict(
        {
            "test": Dataset.from_dict(
                {
                    "query-id": ["q1"],
                    "corpus-ids": [["d2", "d1"]],
                }
            )
        }
    ).save_to_disk(str(source_dir / "top_ranked"))

    result = export_dataset_from_disk("cmedqa_reranking", source_dir)

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    candidates = json.loads((result.export_dir / "candidates.json").read_text(encoding="utf-8"))

    assert manifest["summary"]["candidate_queries"] == 1
    assert candidates["q1"][0]["doc_id"] == "d2"
    assert candidates["q1"][0]["rank"] == 1
