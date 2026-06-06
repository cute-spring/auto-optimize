from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from auto_optimize.safety.scope_guard import is_editable, is_protected
from auto_optimize.shared.paths import resolve_workspace_relative, to_posix_relative
from auto_optimize.shared.schemas import OptimizationContract, SearchSpaceMapping


@dataclass(slots=True)
class ChangeRecord:
    parameter: str
    file: str
    path: str
    before: Any
    after: Any


@dataclass(slots=True)
class FileSnapshot:
    file: str
    content: str


def _load_document(path: Path, mapping_type: str) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        if mapping_type == "yaml_path":
            return yaml.safe_load(handle)
        if mapping_type == "json_path":
            return json.load(handle)
    raise ValueError(f"Unsupported mapping type: {mapping_type}")


def _dump_document(path: Path, mapping_type: str, document: Any) -> None:
    with path.open("w", encoding="utf-8") as handle:
        if mapping_type == "yaml_path":
            yaml.safe_dump(document, handle, sort_keys=False, allow_unicode=True)
            return
        if mapping_type == "json_path":
            json.dump(document, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            return
    raise ValueError(f"Unsupported mapping type: {mapping_type}")


def _get_nested_value(document: Any, dotted_path: str) -> Any:
    current = document
    for part in dotted_path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
            continue
        raise KeyError(f"Path '{dotted_path}' does not exist.")
    return current


def _set_nested_value(document: Any, dotted_path: str, value: Any) -> Any:
    current = document
    parts = dotted_path.split(".")
    for part in parts[:-1]:
        if isinstance(current, dict) and part in current:
            current = current[part]
            continue
        raise KeyError(f"Path '{dotted_path}' does not exist.")
    leaf = parts[-1]
    if not isinstance(current, dict) or leaf not in current:
        raise KeyError(f"Path '{dotted_path}' does not exist.")
    before = current[leaf]
    current[leaf] = value
    return before


def read_current_value(contract: OptimizationContract, mapping: SearchSpaceMapping) -> Any:
    target_path = resolve_workspace_relative(contract.workspace_path, mapping.file)
    document = _load_document(target_path, mapping.type)
    return _get_nested_value(document, mapping.path)


def apply_parameter_value(
    contract: OptimizationContract,
    parameter_name: str,
    mapping: SearchSpaceMapping,
    new_value: Any,
) -> tuple[ChangeRecord, FileSnapshot]:
    relative_file = to_posix_relative(mapping.file)
    if not is_editable(relative_file, contract.editable_scope):
        raise ValueError(f"Cannot edit '{mapping.file}': outside editable_scope.")
    if is_protected(relative_file, contract.protected_scope):
        raise ValueError(f"Cannot edit '{mapping.file}': file is protected.")

    target_path = resolve_workspace_relative(contract.workspace_path, mapping.file)
    original_content = target_path.read_text(encoding="utf-8")
    document = _load_document(target_path, mapping.type)
    before = _set_nested_value(document, mapping.path, new_value)
    _dump_document(target_path, mapping.type, document)

    change = ChangeRecord(
        parameter=parameter_name,
        file=mapping.file,
        path=mapping.path,
        before=before,
        after=new_value,
    )
    snapshot = FileSnapshot(file=mapping.file, content=original_content)
    return change, snapshot


def restore_snapshot(contract: OptimizationContract, snapshot: FileSnapshot) -> None:
    target_path = resolve_workspace_relative(contract.workspace_path, snapshot.file)
    target_path.write_text(snapshot.content, encoding="utf-8")
