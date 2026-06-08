from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations, product
from typing import Any

from auto_optimize.runner.modifier import CandidateChange, read_current_value
from auto_optimize.shared.schemas import OptimizationContract, SearchSpaceParameter


@dataclass(slots=True)
class Candidate:
    changes: list[CandidateChange]

    @property
    def fingerprint(self) -> str:
        return "||".join(
            f"{change.parameter}::{change.value}::{change.mapping.file}::{change.mapping.path or ''}"
            for change in self.changes
        )

    @property
    def parameter(self) -> str:
        return self.parameters[0] if len(self.changes) == 1 else ", ".join(self.parameters)

    @property
    def value(self) -> Any:
        if len(self.changes) == 1:
            return self.changes[0].value
        return self.candidate_values

    @property
    def parameters(self) -> list[str]:
        return [change.parameter for change in self.changes]

    @property
    def candidate_values(self) -> dict[str, Any]:
        return {change.parameter: change.value for change in self.changes}

    @property
    def is_pairwise(self) -> bool:
        return len(self.changes) == 2


def _parameter_state(contract: OptimizationContract) -> list[tuple[str, SearchSpaceParameter, Any]]:
    states: list[tuple[str, SearchSpaceParameter, Any]] = []
    for parameter_name, parameter in contract.search_space.items():
        current_value = read_current_value(contract, parameter.mapping)
        states.append((parameter_name, parameter, current_value))
    return states


def generate_one_variable_candidates(contract: OptimizationContract) -> list[Candidate]:
    candidates: list[Candidate] = []
    seen: set[str] = set()

    for parameter_name, parameter, current_value in _parameter_state(contract):
        for value in parameter.values:
            if value == current_value:
                continue
            candidate = Candidate(
                changes=[
                    CandidateChange(
                        parameter=parameter_name,
                        value=value,
                        mapping=parameter.mapping,
                        current_value=current_value,
                    )
                ]
            )
            if candidate.fingerprint in seen:
                continue
            seen.add(candidate.fingerprint)
            candidates.append(candidate)
    return candidates


def generate_pairwise_candidates(contract: OptimizationContract, max_candidates: int | None = None) -> list[Candidate]:
    states = _parameter_state(contract)
    candidates: list[Candidate] = []
    seen: set[str] = set()

    for (left_name, left_parameter, left_current), (right_name, right_parameter, right_current) in combinations(states, 2):
        left_values = [value for value in left_parameter.values if value != left_current]
        right_values = [value for value in right_parameter.values if value != right_current]

        for left_value, right_value in product(left_values, right_values):
            candidate = Candidate(
                changes=[
                    CandidateChange(
                        parameter=left_name,
                        value=left_value,
                        mapping=left_parameter.mapping,
                        current_value=left_current,
                    ),
                    CandidateChange(
                        parameter=right_name,
                        value=right_value,
                        mapping=right_parameter.mapping,
                        current_value=right_current,
                    ),
                ]
            )
            if candidate.fingerprint in seen:
                continue
            seen.add(candidate.fingerprint)
            candidates.append(candidate)
            if max_candidates is not None and len(candidates) >= max_candidates:
                return candidates
    return candidates


def generate_candidates(contract: OptimizationContract) -> list[Candidate]:
    strategy = contract.run_policy.search_strategy
    if strategy == "one_variable":
        return generate_one_variable_candidates(contract)
    if strategy == "pairwise":
        return generate_pairwise_candidates(contract, contract.run_policy.max_pairwise_candidates)
    if strategy == "one_variable_then_pairwise":
        one_variable = generate_one_variable_candidates(contract)
        pairwise = generate_pairwise_candidates(contract, contract.run_policy.max_pairwise_candidates)
        seen = {candidate.fingerprint for candidate in one_variable}
        for candidate in pairwise:
            if candidate.fingerprint not in seen:
                one_variable.append(candidate)
        return one_variable
    raise ValueError(f"Unsupported search strategy: {strategy}")
