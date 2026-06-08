from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


def _load_signals(signals_path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(signals_path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"Status audit signals must be a mapping: {signals_path}")
    return payload


def _checklist_progress(checklist_path: Path) -> dict[str, Any]:
    text = checklist_path.read_text(encoding="utf-8")
    checked = len(re.findall(r"^- \[x\]", text, flags=re.MULTILINE))
    unchecked = len(re.findall(r"^- \[ \]", text, flags=re.MULTILINE))
    total = checked + unchecked
    completion_ratio = 1.0 if total == 0 else checked / total
    return {
        "checked_items": checked,
        "unchecked_items": unchecked,
        "total_items": total,
        "completion_ratio": completion_ratio,
        "completion_percent": round(completion_ratio * 100, 1),
    }


def _stage_rows(stages: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for stage_key, payload in stages.items():
        if not isinstance(payload, dict):
            continue
        expected = int(payload.get("expected_items", 0))
        completed = int(payload.get("completed_items", 0))
        ratio = 1.0 if expected == 0 else completed / expected
        rows.append(
            {
                "key": stage_key,
                "label": payload.get("label", stage_key),
                "status": payload.get("status", "unknown"),
                "expected_items": expected,
                "completed_items": completed,
                "completion_percent": round(ratio * 100, 1),
                "evidence": list(payload.get("evidence", [])),
            }
        )
    return rows


def build_status_snapshot(signals_path: Path) -> dict[str, Any]:
    signals = _load_signals(signals_path)
    checklist_path = Path(signals["source_checklist"]).resolve()
    progress = _checklist_progress(checklist_path)
    stages = _stage_rows(signals.get("stages", {}))
    global_signals = dict(signals.get("global_signals", {}))

    return {
        "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "mode": "status-audit",
        "signals_path": str(signals_path.resolve()),
        "source_checklist": str(checklist_path),
        "last_refreshed": str(signals.get("last_refreshed")) if signals.get("last_refreshed") is not None else None,
        "goal_status": signals.get("goal_status", "unspecified"),
        "current_focus": signals.get("current_focus", "unspecified"),
        "last_full_test_at": str(signals.get("last_full_test_at")) if signals.get("last_full_test_at") is not None else None,
        "recommended_next_step": signals.get("recommended_next_step"),
        "strategic_gaps": list(signals.get("strategic_gaps", [])),
        "global_signals": global_signals,
        "checklist_progress": progress,
        "stages": stages,
        "historical_snapshots": [
            "/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/docs/assessments/Project_Status_Snapshot_20260607.md",
        ],
    }


def render_status_snapshot_markdown(snapshot: dict[str, Any]) -> str:
    progress = snapshot["checklist_progress"]
    lines = [
        "# AutoOptimize Progress Snapshot",
        "",
        f"- Generated at: {snapshot['generated_at']}",
        f"- Mode: `{snapshot['mode']}`",
        f"- Signals source: `{snapshot['signals_path']}`",
        f"- Source checklist: `{snapshot['source_checklist']}`",
        f"- Goal status: `{snapshot['goal_status']}`",
        f"- Current focus: `{snapshot['current_focus']}`",
    ]
    if snapshot.get("last_full_test_at"):
        lines.append(f"- Last full test refresh: `{snapshot['last_full_test_at']}`")
    if snapshot["global_signals"].get("full_pytest_result"):
        lines.append(f"- Full pytest result: `{snapshot['global_signals']['full_pytest_result']}`")

    lines.extend(
        [
            "",
            "## Overall Progress",
            "",
            f"- Overall completion: **{progress['completion_percent']}%**",
            f"- Tasks: `{progress['checked_items']}/{progress['total_items']}` completed",
            f"- Remaining unchecked tasks: `{progress['unchecked_items']}`",
            "",
            "## Stage Status",
            "",
        ]
    )
    for stage in snapshot["stages"]:
        lines.append(
            f"- `{stage['label']}`: `{stage['status']}` "
            f"({stage['completed_items']}/{stage['expected_items']}, {stage['completion_percent']}%)"
        )

    lines.extend(["", "## Global Signals", ""])
    for key, value in sorted(snapshot["global_signals"].items()):
        lines.append(f"- `{key}`: `{value}`")

    lines.extend(["", "## Strategic Gaps", ""])
    if not snapshot["strategic_gaps"]:
        lines.append("- None recorded.")
    else:
        for gap in snapshot["strategic_gaps"]:
            lines.append(f"- {gap}")

    lines.extend(["", "## Recommended Next Milestone", ""])
    if snapshot.get("recommended_next_step"):
        lines.append(f"- {snapshot['recommended_next_step']}")
    else:
        lines.append("- No recommended next step recorded.")

    lines.extend(["", "## Evidence Links", ""])
    for stage in snapshot["stages"]:
        lines.append(f"- `{stage['label']}` evidence:")
        for evidence in stage["evidence"]:
            lines.append(f"  - `{evidence}`")

    lines.extend(["", "## Historical Notes", ""])
    lines.append(
        "- `Project_Status_Snapshot_20260607.md` should be treated as a historical baseline, not the current source of truth."
    )
    lines.append("")
    return "\n".join(lines)


def default_status_snapshot_path(repo_root: Path) -> Path:
    date_suffix = datetime.utcnow().strftime("%Y%m%d")
    return repo_root / "docs" / "assessments" / f"Project_Status_Snapshot_{date_suffix}.md"


def write_status_snapshot(signals_path: Path, output_path: Path | None = None) -> tuple[dict[str, Any], Path, Path]:
    snapshot = build_status_snapshot(signals_path)
    resolved_output_path = (output_path or default_status_snapshot_path(signals_path.resolve().parents[2])).resolve()
    resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
    json_path = resolved_output_path.with_suffix(".json")

    resolved_output_path.write_text(render_status_snapshot_markdown(snapshot), encoding="utf-8")
    json_path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return snapshot, resolved_output_path, json_path
