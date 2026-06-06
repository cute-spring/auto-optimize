from __future__ import annotations

from pathlib import PurePosixPath

from auto_optimize.shared.paths import to_posix_relative


def normalize_scope_entry(entry: str) -> str:
    normalized = to_posix_relative(entry)
    if entry.endswith("/") and not normalized.endswith("/"):
        return f"{normalized}/"
    return normalized


def scope_entry_matches(scope_entry: str, relative_path: str) -> bool:
    normalized_entry = normalize_scope_entry(scope_entry)
    normalized_path = to_posix_relative(relative_path)

    if normalized_entry == ".":
        return normalized_path == "."
    if normalized_entry.endswith("/"):
        return normalized_path == normalized_entry[:-1] or normalized_path.startswith(normalized_entry)
    return normalized_path == normalized_entry


def find_scope_conflicts(editable_scope: list[str], protected_scope: list[str]) -> list[tuple[str, str]]:
    conflicts: list[tuple[str, str]] = []
    for editable in editable_scope:
        for protected in protected_scope:
            if scope_entry_matches(protected, editable) or scope_entry_matches(editable, protected):
                conflicts.append((editable, protected))
    return conflicts


def is_editable(relative_path: str, editable_scope: list[str]) -> bool:
    return any(scope_entry_matches(entry, relative_path) for entry in editable_scope)


def is_protected(relative_path: str, protected_scope: list[str]) -> bool:
    return any(scope_entry_matches(entry, relative_path) for entry in protected_scope)


def path_depth(relative_path: str) -> int:
    path = PurePosixPath(to_posix_relative(relative_path))
    return len(path.parts)
