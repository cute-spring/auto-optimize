from __future__ import annotations

from collections.abc import Sequence

from auto_optimize.runner.modifier import FileSnapshot, restore_snapshot, restore_snapshots
from auto_optimize.shared.schemas import OptimizationContract


def rollback_change(contract: OptimizationContract, snapshot: FileSnapshot | Sequence[FileSnapshot]) -> None:
    if isinstance(snapshot, FileSnapshot):
        restore_snapshot(contract, snapshot)
        return
    restore_snapshots(contract, snapshot)
