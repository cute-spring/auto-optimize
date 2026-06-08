from __future__ import annotations

from pathlib import Path

import yaml

from auto_optimize.contract.loader import load_contract
from auto_optimize.runner.generated_adapters import (
    generated_adapter_execution_phase,
    materialize_generated_adapter,
    registered_generated_adapters,
)


def test_generated_adapter_registry_lists_metrics_parser() -> None:
    assert ("metrics_parser", "key_value_lines") in registered_generated_adapters()
    assert ("eval_wrapper", "last_json_line") in registered_generated_adapters()
    assert generated_adapter_execution_phase({"kind": "metrics_parser", "template": "key_value_lines"}) == "post_output"
    assert generated_adapter_execution_phase({"kind": "eval_wrapper", "template": "last_json_line"}) == "pre_command"


def test_materialize_generated_metrics_parser_writes_adapter_file(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    contract_path = tmp_path / "contract.yaml"
    contract_path.write_text(
        yaml.safe_dump(
            {
                "schema_version": "0.2",
                "scenario": {"type": "generic_declaration", "name": "Adapter registry test"},
                "workspace": {"path": "workspace"},
                "editable_scope": ["configs/retrieval.yaml"],
                "protected_scope": ["eval/"],
                "search_space": {
                    "top_k": {
                        "values": [10, 20],
                        "mapping": {
                            "type": "yaml_path",
                            "file": "configs/retrieval.yaml",
                            "path": "retrieval.top_k",
                        },
                    }
                },
                "evaluation": {
                    "command": "python eval/run_eval.py",
                    "adapter": {
                        "kind": "metrics_parser",
                        "template": "key_value_lines",
                        "output_dir": "auto_optimize_outputs/generated_adapters",
                        "purpose": "Parse key/value lines into JSON metrics.",
                        "risk_flags": ["generated_code", "metrics_parsing"],
                    },
                },
                "metrics": {
                    "primary": {"name": "top1_accuracy", "direction": "maximize"},
                    "secondary": [],
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    contract = load_contract(contract_path)
    adapter_path = materialize_generated_adapter(contract, contract.evaluation.adapter or {})

    assert adapter_path.exists()
    assert adapter_path.name == "metrics_parser_key_value_lines.py"
    assert "json" in adapter_path.read_text(encoding="utf-8")


def test_materialize_generated_eval_wrapper_writes_adapter_file(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    contract_path = tmp_path / "contract.yaml"
    contract_path.write_text(
        yaml.safe_dump(
            {
                "schema_version": "0.2",
                "scenario": {"type": "generic_declaration", "name": "Eval wrapper registry test"},
                "workspace": {"path": "workspace"},
                "editable_scope": ["configs/retrieval.yaml"],
                "protected_scope": ["eval/"],
                "search_space": {
                    "top_k": {
                        "values": [10, 20],
                        "mapping": {
                            "type": "yaml_path",
                            "file": "configs/retrieval.yaml",
                            "path": "retrieval.top_k",
                        },
                    }
                },
                "evaluation": {
                    "command": "python eval/run_eval.py",
                    "adapter": {
                        "kind": "eval_wrapper",
                        "template": "last_json_line",
                        "output_dir": "auto_optimize_outputs/generated_adapters",
                        "purpose": "Normalize noisy stdout into JSON metrics.",
                        "risk_flags": ["generated_code", "external_eval_command"],
                    },
                },
                "metrics": {
                    "primary": {"name": "top1_accuracy", "direction": "maximize"},
                    "secondary": [],
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    contract = load_contract(contract_path)
    adapter_path = materialize_generated_adapter(contract, contract.evaluation.adapter or {})

    assert adapter_path.exists()
    assert adapter_path.name == "eval_wrapper_last_json_line.py"
    assert "subprocess" in adapter_path.read_text(encoding="utf-8")
