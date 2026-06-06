from __future__ import annotations

from pathlib import Path

import yaml

from auto_optimize.contract.defaults import apply_contract_defaults
from auto_optimize.shared.paths import resolve_contract_relative
from auto_optimize.shared.schemas import OptimizationContract


def load_contract(contract_path: str | Path) -> OptimizationContract:
    resolved_contract_path = Path(contract_path).resolve()
    with resolved_contract_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    contract = OptimizationContract.from_dict(data)
    contract.contract_path = resolved_contract_path
    contract.contract_dir = resolved_contract_path.parent
    contract.workspace_path = resolve_contract_relative(contract.contract_dir, contract.workspace.path)
    return apply_contract_defaults(contract)
