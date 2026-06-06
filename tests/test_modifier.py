from __future__ import annotations

import json
import shutil
from pathlib import Path

import yaml

from auto_optimize.contract.loader import load_contract
from auto_optimize.runner.modifier import apply_parameter_value, restore_snapshot
from auto_optimize.shared.schemas import SearchSpaceMapping

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_DIR = ROOT / "examples" / "faq_retrieval"
SOURCE_WORKSPACE = EXAMPLE_DIR / "workspace"
SOURCE_CONTRACT = EXAMPLE_DIR / "optimization.contract.yaml"


def _reset_workspace_fixture(workspace: Path) -> None:
    output_dir = workspace / "auto_optimize_outputs"
    if output_dir.exists():
        shutil.rmtree(output_dir)

    (workspace / "configs" / "retrieval.yaml").write_text(
        "retrieval:\n  top_k: 10\n  threshold: 0.82\n",
        encoding="utf-8",
    )
    (workspace / "configs" / "embedding_strategy.yaml").write_text(
        "\n".join(
            [
                "embedding:",
                "  faq_template: question_with_answer",
                "  query_template: normalized_query",
                "  multilingual_normalization: true",
                "  language_hint_mode: auto",
                "  faq_text_fields:",
                "    - title",
                "    - question",
                "    - answer",
                "  query_processing_steps:",
                "    - trim",
                "    - lowercase_ascii",
                "    - preserve_chinese",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _materialize_contract(tmp_path: Path):
    workspace_copy = tmp_path / "workspace"
    shutil.copytree(SOURCE_WORKSPACE, workspace_copy)
    _reset_workspace_fixture(workspace_copy)

    data = yaml.safe_load(SOURCE_CONTRACT.read_text(encoding="utf-8"))
    data["workspace"]["path"] = "workspace"

    contract_path = tmp_path / "optimization.contract.yaml"
    contract_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return load_contract(contract_path)


def test_apply_parameter_value_updates_yaml_and_restores_snapshot(tmp_path: Path) -> None:
    contract = _materialize_contract(tmp_path)
    mapping = contract.search_space["top_k"].mapping

    change, snapshot = apply_parameter_value(contract, "top_k", mapping, 20)
    updated = yaml.safe_load((tmp_path / "workspace" / "configs" / "retrieval.yaml").read_text(encoding="utf-8"))

    assert change.before == 10
    assert change.after == 20
    assert updated["retrieval"]["top_k"] == 20

    restore_snapshot(contract, snapshot)
    restored = yaml.safe_load((tmp_path / "workspace" / "configs" / "retrieval.yaml").read_text(encoding="utf-8"))
    assert restored["retrieval"]["top_k"] == 10


def test_apply_parameter_value_updates_json_and_restores_snapshot(tmp_path: Path) -> None:
    contract = _materialize_contract(tmp_path)
    json_path = tmp_path / "workspace" / "configs" / "candidate.json"
    json_path.write_text(json.dumps({"candidate": {"temperature": 0.1}}, indent=2) + "\n", encoding="utf-8")
    contract.editable_scope.append("configs/candidate.json")

    mapping = SearchSpaceMapping(type="json_path", file="configs/candidate.json", path="candidate.temperature")

    change, snapshot = apply_parameter_value(contract, "temperature", mapping, 0.2)
    updated = json.loads(json_path.read_text(encoding="utf-8"))

    assert change.before == 0.1
    assert change.after == 0.2
    assert updated["candidate"]["temperature"] == 0.2

    restore_snapshot(contract, snapshot)
    restored = json.loads(json_path.read_text(encoding="utf-8"))
    assert restored["candidate"]["temperature"] == 0.1
