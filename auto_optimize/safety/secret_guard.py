from __future__ import annotations

from auto_optimize.shared.errors import ValidationResult
from auto_optimize.shared.paths import to_posix_relative

SUSPICIOUS_SECRET_MARKERS = ("secret", "secrets", ".env", "credential", "token", "key")


def validate_secret_scope(editable_scope: list[str], result: ValidationResult) -> None:
    for entry in editable_scope:
        normalized = to_posix_relative(entry).lower()
        if any(marker in normalized for marker in SUSPICIOUS_SECRET_MARKERS):
            result.add_issue(
                "error",
                "secret_scope_violation",
                f"Editable scope entry '{entry}' looks like a secret path and must not be editable.",
            )
