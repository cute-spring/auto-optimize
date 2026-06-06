---
name: auto-optimize
description: Diagnose optimization opportunities, build optimization contracts, run safe experiment loops, compare metrics, manage Git checkpoints, keep better changes, reject worse changes, and generate optimization reports for project components.
---

# AutoOptimize Skill

## When To Use

Use this skill when the user wants to improve a project component through controlled experiments backed by measurable evaluation results and explicit safety boundaries.

## When Not To Use

- Do not use this skill for arbitrary code rewriting with no evaluation loop.
- Do not use this skill when the user wants direct production deployment automation.
- Do not use this skill when there is no measurable evaluation command or optimization contract path.

## Modes

- Advisor Mode: read-only diagnosis and draft contract generation.
- Guided Mode: step-by-step contract collection for beginners.
- Template Mode: fill a scenario template and validate it.
- Expert Mode: load a complete `optimization.contract.yaml` and run directly after validation.

## Required Artifacts

- `optimization.contract.yaml`
- `experiment_log.jsonl` after run mode executes

## Safety Rules

- Never modify files outside `editable_scope`.
- Never modify files in `protected_scope`.
- Never modify evaluation scripts or golden datasets.
- Never access or print secrets.
- Require contract validation before run mode.
- Require clean Git worktree by default.
- Require user approval before Git initialization, disabling the clean worktree requirement, committing accepted changes unless enabled in the contract, or enabling code modification in a user project.

## Git Rules

- Use a new optimization branch when configured.
- Record Git state before the run and branch when configured.
- Commit accepted experiments only when configured.
- Roll back rejected experiments safely.
- Never push to remote or create pull requests in MVP.

## Recommended Workflow

1. If no contract exists, start with Advisor or Guided mode.
2. Generate or load `optimization.contract.yaml`.
3. Validate the contract.
4. Check Git state.
5. Run baseline evaluation.
6. Run controlled experiments.
7. Accept or reject changes.
8. Generate logs and reports.

## CLI

```bash
python -m auto_optimize.cli validate examples/faq_retrieval/optimization.contract.yaml
python -m auto_optimize.cli advisor --workspace ./project --scenario faq_retrieval
python -m auto_optimize.cli run optimization.contract.yaml
python -m auto_optimize.cli report auto_optimize_outputs/experiment_log.jsonl
```

## Output Files

- `auto_optimize_outputs/contract_validation_report.md`
- `auto_optimize_outputs/optimization.contract.draft.yaml`
- `auto_optimize_outputs/readiness_report.json`
- `auto_optimize_outputs/experiment_log.jsonl`
- `auto_optimize_outputs/experiment_log.csv`
- `auto_optimize_outputs/run_summary.json`
- `auto_optimize_outputs/optimization_report.md`
- `auto_optimize_outputs/run_history.jsonl`
- `auto_optimize_outputs/best_run_snapshot.json`

## Stop Conditions

- Stop if validation fails.
- Stop if the contract violates safety boundaries.
- Stop and ask the user before any destructive, irreversible, or approval-gated action.

## Human Approval Requirements

- initializing Git in a non-repo workspace
- committing accepted changes
- writing a generated contract into a user project root
- enabling code modification in a target workspace
- running beyond a safe experiment budget
