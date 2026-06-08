# Command Guide

This guide describes the current CLI while keeping the project direction clear: declarations are the user-facing goal, and the contract remains the executable internal form.

## Start Here

- Use `declare` when you want to inspect or keep the generated executable contract explicitly.
- Use `derive-declaration` to migrate an existing contract back into a declaration.
- Use `advisor` to inspect a workspace and draft an executable contract from available clues.
- Use `guided` to collect missing fields and generate a contract.
- Use `explain-contract` to understand what a contract will do.
- Use `validate` before any run.
- Use `run` with either a declaration or a contract. When you pass a declaration, AutoOptimize generates a scoped contract automatically before execution.
- Use `status-audit` to regenerate the current project status snapshot from the checklist and governance signals.
- Use `report` to regenerate a Markdown report from run artifacts.
- Use `template` only for reference discovery. It is not the main product path.

## Commands

### `declare`

Use it when:

- you already know the objective, variables, safety boundaries, evaluation command, and comparison rule
- you want the current contract generated from that declaration

```bash
python -m auto_optimize.cli declare optimization.declaration.yaml --output optimization.contract.yaml
```

### `advisor`

Use it when:

- you have a workspace
- you want AutoOptimize to infer a starting point
- you understand that current inference is transitional and may still use reference scenarios

```bash
python -m auto_optimize.cli advisor --workspace /path/to/workspace
```

Current outputs include:

- `optimization.declaration.draft.yaml`
- `optimization.declaration.normalized.yaml`
- `optimization.contract.draft.yaml`
- `readiness_report.json`

### `derive-declaration`

Use it when:

- you already have an executable contract
- you want a declaration-first source file for migration, editing, or review

```bash
python -m auto_optimize.cli derive-declaration optimization.contract.yaml --output optimization.declaration.yaml
```

### `guided`

Use it when:

- you want a generated contract from a workspace
- you want a smaller authoring-oriented contract with `--style minimal`

```bash
python -m auto_optimize.cli guided --workspace /path/to/workspace --style minimal
```

In declaration-first mode, `guided` now builds the generated contract from the normalized declaration artifact rather than the raw draft.

### `explain-contract`

Use it when:

- you want to understand editable scope, protected scope, variables, metrics, and defaults

```bash
python -m auto_optimize.cli explain-contract optimization.contract.yaml
```

### `validate`

Use it when:

- you have an executable contract
- you want safety and evaluation readiness checks before mutation

```bash
python -m auto_optimize.cli validate optimization.contract.yaml
```

### `run`

Use it when:

- validation already passes for a contract path, or
- you want a declaration-native entry point and are ready for AutoOptimize to generate the contract automatically

```bash
python -m auto_optimize.cli run optimization.declaration.yaml
python -m auto_optimize.cli run optimization.contract.yaml
```

### `report`

Use it when:

- you have prior run artifacts and want to rebuild the Markdown report

```bash
python -m auto_optimize.cli report auto_optimize_outputs
```

### `status-audit`

Use it when:

- you want the current project progress snapshot regenerated from governance artifacts
- you want a machine-readable JSON snapshot alongside the Markdown summary

```bash
python -m auto_optimize.cli status-audit
python -m auto_optimize.cli status-audit --output /tmp/Project_Status_Snapshot.md
```

### `template`

Use it only for reference assets:

```bash
python -m auto_optimize.cli template --json
```

Templates and reference scenarios are examples, not the target architecture.

## Current Transitional Flow

```bash
python -m auto_optimize.cli run /path/to/optimization.declaration.yaml
python -m auto_optimize.cli declare /path/to/optimization.declaration.yaml --output /path/to/optimization.contract.yaml
python -m auto_optimize.cli explain-contract /path/to/optimization.contract.yaml
python -m auto_optimize.cli validate /path/to/optimization.contract.yaml
python -m auto_optimize.cli run /path/to/optimization.contract.yaml
python -m auto_optimize.cli derive-declaration /path/to/optimization.contract.yaml --output /path/to/optimization.declaration.yaml
```
