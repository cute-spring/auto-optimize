from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import yaml

from auto_optimize.safety.scope_guard import is_editable, is_protected
from auto_optimize.shared.paths import resolve_workspace_relative, to_posix_relative
from auto_optimize.shared.schemas import OptimizationContract, SearchSpaceMapping


@dataclass(slots=True)
class CandidateChange:
    parameter: str
    value: Any
    mapping: SearchSpaceMapping
    current_value: Any


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
    change = CandidateChange(
        parameter=parameter_name,
        value=new_value,
        mapping=mapping,
        current_value=read_current_value(contract, mapping),
    )
    changes, snapshots = apply_candidate_changes(contract, [change])
    return changes[0], snapshots[0]


def apply_candidate_changes(
    contract: OptimizationContract,
    candidate_changes: Sequence[CandidateChange],
) -> tuple[list[ChangeRecord], list[FileSnapshot]]:
    if not candidate_changes:
        return [], []

    grouped_changes: dict[str, list[CandidateChange]] = {}
    for change in candidate_changes:
        grouped_changes.setdefault(to_posix_relative(change.mapping.file), []).append(change)

    change_records: list[ChangeRecord] = []
    snapshots: list[FileSnapshot] = []

    for relative_file, file_changes in grouped_changes.items():
        if not is_editable(relative_file, contract.editable_scope):
            raise ValueError(f"Cannot edit '{relative_file}': outside editable_scope.")
        if is_protected(relative_file, contract.protected_scope):
            raise ValueError(f"Cannot edit '{relative_file}': file is protected.")

        target_path = resolve_workspace_relative(contract.workspace_path, relative_file)
        original_content = target_path.read_text(encoding="utf-8")
        mapping_type = file_changes[0].mapping.type
        document = _load_document(target_path, mapping_type)

        for candidate_change in file_changes:
            before = _set_nested_value(document, candidate_change.mapping.path, candidate_change.value)
            change_records.append(
                ChangeRecord(
                    parameter=candidate_change.parameter,
                    file=candidate_change.mapping.file,
                    path=candidate_change.mapping.path,
                    before=before,
                    after=candidate_change.value,
                )
            )

        _dump_document(target_path, mapping_type, document)
        snapshots.append(FileSnapshot(file=relative_file, content=original_content))

    return change_records, snapshots


def restore_snapshots(contract: OptimizationContract, snapshots: Sequence[FileSnapshot]) -> None:
    for snapshot in snapshots:
        restore_snapshot(contract, snapshot)
def restore_snapshot(contract: OptimizationContract, snapshot: FileSnapshot) -> None:
    target_path = resolve_workspace_relative(contract.workspace_path, snapshot.file)
    target_path.write_text(snapshot.content, encoding="utf-8")
