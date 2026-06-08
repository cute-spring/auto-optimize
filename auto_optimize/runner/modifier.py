from __future__ import annotations

import json
import os
import shlex
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
    content: str | None
    target_type: str = "file"
    existed: bool = True


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


def _env_scope_entry(env_name: str) -> str:
    return f"env:{env_name}"


def _cli_arg_scope_entry(argument_name: str) -> str:
    return f"cmd_arg:{argument_name}"


def _read_cli_arg_value(command: str, argument_name: str) -> Any:
    tokens = shlex.split(command)
    for index, token in enumerate(tokens):
        if token == argument_name:
            if index + 1 >= len(tokens) or tokens[index + 1].startswith("-"):
                return True
            return tokens[index + 1]
        if token.startswith(f"{argument_name}="):
            return token.split("=", 1)[1]
    return None


def _set_cli_arg_value(command: str, argument_name: str, value: Any) -> str:
    tokens = shlex.split(command)
    rendered_value = str(value)
    updated_tokens: list[str] = []
    skip_next = False
    replaced = False

    for index, token in enumerate(tokens):
        if skip_next:
            skip_next = False
            continue
        if token == argument_name:
            updated_tokens.extend([argument_name, rendered_value])
            replaced = True
            if index + 1 < len(tokens) and not tokens[index + 1].startswith("-"):
                skip_next = True
            continue
        if token.startswith(f"{argument_name}="):
            updated_tokens.append(f"{argument_name}={rendered_value}")
            replaced = True
            continue
        updated_tokens.append(token)

    if not replaced:
        updated_tokens.extend([argument_name, rendered_value])
    return shlex.join(updated_tokens)


def read_current_value(contract: OptimizationContract, mapping: SearchSpaceMapping) -> Any:
    if mapping.type == "env_var":
        return None if not mapping.file else os.environ.get(mapping.file)
    if mapping.type == "cli_arg":
        return _read_cli_arg_value(contract.evaluation.command, mapping.file)
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
        if change.mapping.type == "env_var":
            grouped_changes.setdefault(_env_scope_entry(change.mapping.file), []).append(change)
        elif change.mapping.type == "cli_arg":
            grouped_changes.setdefault(_cli_arg_scope_entry(change.mapping.file), []).append(change)
        else:
            grouped_changes.setdefault(to_posix_relative(change.mapping.file), []).append(change)

    change_records: list[ChangeRecord] = []
    snapshots: list[FileSnapshot] = []

    for relative_file, file_changes in grouped_changes.items():
        if not is_editable(relative_file, contract.editable_scope):
            raise ValueError(f"Cannot edit '{relative_file}': outside editable_scope.")
        if is_protected(relative_file, contract.protected_scope):
            raise ValueError(f"Cannot edit '{relative_file}': file is protected.")

        if file_changes[0].mapping.type == "env_var":
            env_name = file_changes[0].mapping.file
            original_exists = env_name in os.environ
            original_value = os.environ.get(env_name)
            for candidate_change in file_changes:
                before = os.environ.get(env_name)
                os.environ[env_name] = str(candidate_change.value)
                change_records.append(
                    ChangeRecord(
                        parameter=candidate_change.parameter,
                        file=_env_scope_entry(env_name),
                        path="<env>",
                        before=before,
                        after=str(candidate_change.value),
                    )
                )

            snapshots.append(
                FileSnapshot(
                    file=_env_scope_entry(env_name),
                    content=original_value,
                    target_type="env_var",
                    existed=original_exists,
                )
            )
            continue

        if file_changes[0].mapping.type == "cli_arg":
            argument_name = file_changes[0].mapping.file
            original_command = contract.evaluation.command
            for candidate_change in file_changes:
                before = _read_cli_arg_value(contract.evaluation.command, argument_name)
                contract.evaluation.command = _set_cli_arg_value(
                    contract.evaluation.command,
                    argument_name,
                    candidate_change.value,
                )
                change_records.append(
                    ChangeRecord(
                        parameter=candidate_change.parameter,
                        file=_cli_arg_scope_entry(argument_name),
                        path="<cli_arg>",
                        before=before,
                        after=str(candidate_change.value),
                    )
                )

            snapshots.append(
                FileSnapshot(
                    file=_cli_arg_scope_entry(argument_name),
                    content=original_command,
                    target_type="cli_arg",
                )
            )
            continue

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
    if snapshot.target_type == "env_var":
        env_name = snapshot.file.removeprefix("env:")
        if snapshot.existed:
            os.environ[env_name] = snapshot.content or ""
        else:
            os.environ.pop(env_name, None)
        return
    if snapshot.target_type == "cli_arg":
        contract.evaluation.command = snapshot.content or ""
        return
    target_path = resolve_workspace_relative(contract.workspace_path, snapshot.file)
    target_path.write_text(snapshot.content or "", encoding="utf-8")
