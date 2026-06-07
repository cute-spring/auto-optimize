# Command Guide

This guide describes the current CLI while keeping the project direction clear: declarations are the user-facing goal, contracts are the current executable form.

## Start Here

- Use `declare` to convert a declaration YAML into the current executable contract format.
- Use `advisor` to inspect a workspace and draft an executable contract from available clues.
- Use `guided` to collect missing fields and generate a contract.
- Use `explain-contract` to understand what a contract will do.
- Use `validate` before any run.
- Use `run` when the executable contract is ready.
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

### `guided`

Use it when:

- you want a generated contract from a workspace
- you want a smaller authoring-oriented contract with `--style minimal`

```bash
python -m auto_optimize.cli guided --workspace /path/to/workspace --style minimal
```

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

- validation passes
- the editable variables and evaluation method are correct

```bash
python -m auto_optimize.cli run optimization.contract.yaml
```

### `report`

Use it when:

- you have prior run artifacts and want to rebuild the Markdown report

```bash
python -m auto_optimize.cli report auto_optimize_outputs
```

### `template`

Use it only for reference assets:

```bash
python -m auto_optimize.cli template --json
```

Templates and reference scenarios are examples, not the target architecture.

## Current Transitional Flow

```bash
python -m auto_optimize.cli declare /path/to/optimization.declaration.yaml --output /path/to/optimization.contract.yaml
python -m auto_optimize.cli explain-contract /path/to/optimization.contract.yaml
python -m auto_optimize.cli validate /path/to/optimization.contract.yaml
python -m auto_optimize.cli run /path/to/optimization.contract.yaml
```
