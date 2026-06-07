# Command Guide

Use this page when you know what stage you are in, but are not sure which command to run next.

## Start Here

- Use `advisor` when you have a workspace and want AutoOptimize to inspect it.
- Use `guided` when you want a beginner-friendly path that produces both readiness output and a generated contract.
- Use `build` when you already know the scenario and want a generated contract from templates.
- Use `template` when you want to see available scenarios, metric profiles, and benchmark datasets.
- Use `validate` before `run`.
- Use `run` when the contract is ready and you want AutoOptimize to execute the bounded optimization loop.
- Use `report` when you want to regenerate a Markdown report from previous run artifacts.

## Commands

### `advisor`

When to use it:

- you have a workspace but not a contract yet
- you want AutoOptimize to inspect files and suggest the next action

Typical command:

```bash
python -m auto_optimize.cli advisor --workspace examples/faq_retrieval/workspace
```

Outputs:

- `optimization.contract.draft.yaml`
- `readiness_report.json`

### `guided`

When to use it:

- you want the easiest onboarding path
- you want readiness inspection plus a generated contract in one pass

Typical command:

```bash
python -m auto_optimize.cli guided --workspace examples/faq_retrieval/workspace
```

Outputs:

- `readiness_report.json`
- `optimization.contract.generated.yaml`

### `build`

When to use it:

- you want a generated contract from a known scenario template
- you want to pick a metric profile explicitly

Typical command:

```bash
python -m auto_optimize.cli build \
  --workspace examples/faq_retrieval/workspace \
  --scenario faq_retrieval \
  --metric-profile faq_metrics
```

Output:

- `optimization.contract.generated.yaml`

### `template`

When to use it:

- you want to discover supported scenarios and profiles

Typical command:

```bash
python -m auto_optimize.cli template --json
```

### `validate`

When to use it:

- you have a contract and want to check workspace safety and eval readiness before running optimization

Typical command:

```bash
python -m auto_optimize.cli validate examples/faq_retrieval/optimization.contract.yaml
```

Output:

- `contract_validation_report.md`

### `run`

When to use it:

- the contract validates successfully
- you want AutoOptimize to execute baseline plus candidate evaluations

Typical command:

```bash
python -m auto_optimize.cli run examples/faq_retrieval/optimization.contract.yaml
```

Outputs:

- `experiment_log.jsonl`
- `run_summary.json`
- `optimization_report.md`
- `run_history.jsonl`
- `best_run_snapshot.json`

### `report`

When to use it:

- you already have run artifacts and want to rebuild the Markdown report

Typical command:

```bash
python -m auto_optimize.cli report examples/faq_retrieval/workspace/auto_optimize_outputs
```

## Common Flows

First run with a checked-in example:

```bash
python -m auto_optimize.cli advisor --workspace examples/faq_retrieval/workspace
python -m auto_optimize.cli validate examples/faq_retrieval/optimization.contract.yaml
python -m auto_optimize.cli run examples/faq_retrieval/optimization.contract.yaml
```

Beginner path for your own compatible workspace:

```bash
python -m auto_optimize.cli guided --workspace /path/to/workspace
python -m auto_optimize.cli validate /path/to/workspace/auto_optimize_outputs/optimization.contract.generated.yaml
python -m auto_optimize.cli run /path/to/workspace/auto_optimize_outputs/optimization.contract.generated.yaml
```
