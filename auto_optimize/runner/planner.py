from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from auto_optimize.runner.modifier import read_current_value
from auto_optimize.shared.schemas import OptimizationContract, SearchSpaceMapping


@dataclass(slots=True)
class Candidate:
    parameter: str
    value: Any
    mapping: SearchSpaceMapping
    current_value: Any

    @property
    def fingerprint(self) -> str:
        return f"{self.parameter}::{self.value}::{self.mapping.file}::{self.mapping.path}"


def generate_one_variable_candidates(contract: OptimizationContract) -> list[Candidate]:
    candidates: list[Candidate] = []
    seen: set[str] = set()

    for parameter_name, parameter in contract.search_space.items():
        current_value = read_current_value(contract, parameter.mapping)
        for value in parameter.values:
            if value == current_value:
                continue
            candidate = Candidate(
                parameter=parameter_name,
                value=value,
                mapping=parameter.mapping,
                current_value=current_value,
            )
            if candidate.fingerprint in seen:
                continue
            seen.add(candidate.fingerprint)
            candidates.append(candidate)
    return candidates
