from __future__ import annotations

import shlex

from auto_optimize.shared.paths import to_posix_relative


def infer_eval_paths(command: str) -> set[str]:
    inferred: set[str] = set()
    for token in shlex.split(command):
        normalized = to_posix_relative(token)
        if normalized == ".":
            continue
        if normalized.startswith("-"):
            continue
        if any(normalized.endswith(ext) for ext in (".py", ".sh", ".js")):
            inferred.add(normalized)
        if normalized.startswith("eval/"):
            inferred.add("eval/")
    return inferred
