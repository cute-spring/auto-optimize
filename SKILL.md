---
name: auto-optimize
description: A generic declaration-driven optimization skill. Use it when a user can declare what may change, how evaluation runs, how metrics are compared, and which safety boundaries apply; AutoOptimize validates the declaration, optionally generates scoped helper code, runs bounded experiments, rolls back rejected changes, and reports the result.
---

# AutoOptimize Skill

## Direction

AutoOptimize is a generic optimization skill.

It must not become a large static catalog of hardcoded scenarios, datasets, providers, or benchmark workflows. Existing FAQ, embedding, reranking, benchmark, provider, and metric-profile assets are examples and regression fixtures only.

The core user input is a declaration:

- objective
- editable variables
- protected scope
- evaluation command
- metrics source
- comparison rule
- constraints
- budget
- optional user-provided algorithm
- optional permission for generated adapters

## When To Use

Use this skill when the user wants to improve a project component through controlled experiments backed by measurable evaluation results and explicit safety boundaries.

The target can be any domain as long as the user can declare what changes and how it is measured.

## When Not To Use

- Do not use this skill for arbitrary code rewriting with no evaluation loop.
- Do not use this skill when the user cannot define any measurable evaluation method.
- Do not force the user into FAQ, embedding, reranking, benchmark, or provider-specific shapes.
- Do not expand static scenario support as the primary path.

## Modes

- Advisor Mode: inspect the workspace and help turn the user's stated goal into a declaration.
- Guided Mode: collect missing declaration fields and produce an executable contract.
- Expert Mode: load a complete contract or declaration and run after validation.
- Reference Mode: use existing examples only as reference declarations or regression fixtures.

## Required Declaration

At minimum, capture:

- what the user wants to optimize
- what variables may change
- what files, data, commands, and secrets are protected
- how evaluation runs
- how metrics are extracted
- what counts as improvement
- what constraints must not regress

## Dynamic Adapter Generation

When the user has supplied enough declaration data but no ready adapter, AutoOptimize may generate scoped temporary code for:

- evaluation wrappers
- metric parsers
- config mutators
- environment patchers
- result comparators

Generated code must be written under the run output directory, recorded in reports, and kept inside the declared safety boundaries.

Ask before generating or running code that edits project source, uses credentials, calls paid services, or performs materially risky operations.

## Safety Rules

- Never modify files outside declared editable scope.
- Never modify files in protected scope.
- Never modify evaluation scripts, test data, golden data, or secrets unless the user explicitly declares them editable.
- Never access or print secrets.
- Validate before run mode.
- Prefer a clean Git worktree when Git integration is enabled.
- Require user approval before destructive actions, Git initialization, disabling clean-worktree requirements, or enabling high-risk generated code.

## Recommended Workflow

1. Capture or load the user's declaration.
2. Validate safety boundaries and evaluation readiness.
3. Generate temporary adapters only when useful and allowed.
4. Convert the declaration into an executable contract.
5. Run baseline evaluation.
6. Try bounded candidate changes.
7. Compare metrics using declared rules.
8. Accept, reject, roll back, and report.

## CLI

```bash
python -m auto_optimize.cli declare ./optimization.declaration.yaml --output ./optimization.contract.yaml
python -m auto_optimize.cli derive-declaration ./optimization.contract.yaml --output ./optimization.declaration.yaml
python -m auto_optimize.cli advisor --workspace ./project
python -m auto_optimize.cli guided --workspace ./project --style minimal
python -m auto_optimize.cli explain-contract optimization.contract.yaml
python -m auto_optimize.cli validate optimization.contract.yaml
python -m auto_optimize.cli run optimization.contract.yaml
python -m auto_optimize.cli report auto_optimize_outputs
```

The current CLI still executes contracts, but declarations are now the primary authoring path and existing contracts can be converted back into declarations for migration.

## Output Files

- `auto_optimize_outputs/contract_validation_report.md`
- `auto_optimize_outputs/optimization.contract.draft.yaml`
- `auto_optimize_outputs/optimization.contract.generated.yaml`
- `auto_optimize_outputs/readiness_report.json`
- `auto_optimize_outputs/generated_adapters/` when dynamic adapters are generated
- `auto_optimize_outputs/experiment_log.jsonl`
- `auto_optimize_outputs/experiment_log.csv`
- `auto_optimize_outputs/run_summary.json`
- `auto_optimize_outputs/optimization_report.md`
- `auto_optimize_outputs/run_history.jsonl`
- `auto_optimize_outputs/best_run_snapshot.json`

## Stop Conditions

- Stop if validation fails.
- Stop if the declaration or contract violates safety boundaries.
- Stop and ask the user before destructive, irreversible, credentialed, paid, or approval-gated actions.
