from __future__ import annotations

import json
from pathlib import Path

from auto_optimize.cli import main


def test_status_audit_command_generates_current_snapshot(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "Project_Status_Snapshot_test.md"

    exit_code = main(["status-audit", "--output", str(output_path)])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert output_path.exists()
    assert output_path.with_suffix(".json").exists()
    assert "Status snapshot:" in captured.out
    assert "Overall completion:" in captured.out

    report = output_path.read_text(encoding="utf-8")
    payload = json.loads(output_path.with_suffix(".json").read_text(encoding="utf-8"))

    assert "## Overall Progress" in report
    assert "## Stage Status" in report
    assert "## Strategic Gaps" in report
    assert "## Recommended Next Milestone" in report
    assert "95 passed" in report
    assert payload["global_signals"]["full_pytest_result"] == "95 passed"
    assert payload["checklist_progress"]["unchecked_items"] == 0
    assert payload["current_focus"]
    assert payload["recommended_next_step"]
