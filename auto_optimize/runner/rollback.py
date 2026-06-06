from __future__ import annotations

from auto_optimize.runner.modifier import FileSnapshot, restore_snapshot
from auto_optimize.shared.schemas import OptimizationContract


def rollback_change(contract: OptimizationContract, snapshot: FileSnapshot) -> None:
    restore_snapshot(contract, snapshot)
