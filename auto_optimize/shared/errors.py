from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ValidationIssue:
    severity: str
    code: str
    message: str
    field: str | None = None
    hint: str | None = None


@dataclass(slots=True)
class ValidationResult:
    issues: list[ValidationIssue] = field(default_factory=list)
    baseline_metrics: dict[str, Any] | None = None
    git_state: dict[str, Any] | None = None

    @property
    def valid(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    def add_issue(
        self,
        severity: str,
        code: str,
        message: str,
        field: str | None = None,
        hint: str | None = None,
    ) -> None:
        self.issues.append(
            ValidationIssue(
                severity=severity,
                code=code,
                message=message,
                field=field,
                hint=hint,
            )
        )
