# Contract Fields

This is the practical field guide for the current executable contract.

Direction note: the user-facing interface should become declaration-first. These fields describe the current normalized execution format.

## Core Fields

### `schema_version`

What it means:

- the contract schema revision

Current value:

- `"0.2"`

### `scenario.type`

What it means:

- the workflow shape AutoOptimize expects

Current transitional scenario labels:

- `faq_retrieval`
- `retrieval_embedding_benchmark`
- `reranking_benchmark`

### `workspace.path`

What it means:

- the directory AutoOptimize will treat as the optimization workspace

Important:

- this path is resolved relative to the contract file

### `editable_scope`

What it means:

- the files AutoOptimize is allowed to modify

Good examples:

- `configs/retrieval.yaml`
- `configs/reranker.yaml`

### `protected_scope`

What it means:

- files or directories AutoOptimize must not edit

Typical examples:

- `eval/`
- `data/`
- `.env`
- `secrets/`

### `search_space`

What it means:

- the set of tunable parameters and where they live

Each parameter needs:

- `values`
- `mapping.type`
- `mapping.file`
- `mapping.path`

Supported mapping types:

- `yaml_path`
- `json_path`

### `evaluation.command`

What it means:

- the command used to score the current workspace configuration

Current onboarding recommendation:

- `python eval/run_eval.py --json`
- `python eval/run_benchmark_eval.py --json`

### `metrics.primary`

What it means:

- the metric AutoOptimize uses as the main optimization target

Directions:

- `maximize`
- `minimize`

## Optional But Important Fields

### `constraints`

What it means:

- limits the result must satisfy even if the primary metric improves

Typical examples:

- latency max
- size max
- cost max

### `decision_policy`

What it means:

- how AutoOptimize decides whether a candidate is acceptable

Current important modes:

- `constrained_primary_metric`
- `pareto_frontier`

### `run_policy`

What it means:

- controls search budget and candidate planning behavior

Useful fields:

- `max_experiments`
- `search_strategy`
- `stop_if_no_improvement_rounds`

### `version_control`

What it means:

- enables Git-aware execution, commits, branch creation, and optional push or PR flow

Keep it off for a first local run unless you want Git integration.

### `report`

What it means:

- controls output formats and artifact directory

Default output directory:

- `auto_optimize_outputs`

## Recommended Reading Order

If you are editing a contract for the first time, understand these sections in this order:

1. `workspace`
2. `editable_scope`
3. `protected_scope`
4. `search_space`
5. `evaluation`
6. `metrics`
7. `constraints`

## Helpful Companion Commands

- `python -m auto_optimize.cli explain-contract <contract>`
- `python -m auto_optimize.cli validate <contract>`
