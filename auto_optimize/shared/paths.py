from __future__ import annotations

from pathlib import Path, PurePosixPath


def resolve_contract_relative(base_dir: Path, raw_path: str) -> Path:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return candidate.resolve()
    return (base_dir / candidate).resolve()


def resolve_workspace_relative(workspace_dir: Path, raw_path: str) -> Path:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return candidate.resolve()
    return (workspace_dir / candidate).resolve()


def to_posix_relative(path: str) -> str:
    value = path.replace("\\", "/")
    pure = PurePosixPath(value)
    normalized_parts = [part for part in pure.parts if part not in ("", ".")]
    normalized = PurePosixPath(*normalized_parts).as_posix() if normalized_parts else "."
    return normalized.rstrip("/") if normalized != "." else normalized
