# Declaration Protocol

This document defines the user-facing protocol AutoOptimize should optimize around.

The declaration is intentionally smaller and more natural than the full executable contract. It captures what the user knows. AutoOptimize can then validate it, fill safe defaults, generate temporary adapter code when needed, and convert it into an executable contract.

## Minimal Declaration

```yaml
workspace:
  path: "."

objective:
  description: "Improve answer quality while keeping latency under 200 ms."

variables:
  - name: top_k
    kind: yaml_path
    target: configs/retrieval.yaml
    path: retrieval.top_k
    values: [5, 10, 20]

evaluation:
  command: "python eval/run_eval.py --json"
  metrics_source: stdout_json

comparison:
  primary_metric: top1_accuracy
  direction: maximize

constraints:
  latency_ms:
    max: 200

safety:
  editable:
    - configs/retrieval.yaml
  protected:
    - eval/
    - data/
```

## Required Sections

### `objective`

What the user wants to improve.

Fields:

- `description`: human-readable goal

### `workspace`

Where AutoOptimize should treat as the optimization workspace.

Fields:

- `path`: optional, relative to the declaration file. Defaults to `.`.

### `variables`

What AutoOptimize may change.

Each variable should declare:

- `name`
- `kind`
- `target`
- `path` or equivalent mutation location
- `values` or generation rule

Supported initial variable kinds:

- `yaml_path`
- `json_path`
- `env_var`
- `cli_arg`
- `generated_adapter`

Current executable slice:

- `yaml_path`
- `json_path`

The other kinds remain future declaration targets until dynamic adapter generation is implemented.

### `evaluation`

How to measure the current candidate.

Fields:

- `command`: command to run from the workspace root
- `metrics_source`: how metrics are extracted
- `timeout_seconds`: optional
- `repetitions`: optional stability-check count

Supported initial metric sources:

- `stdout_json`
- `metrics_json`
- `csv_with_summary`
- `generated_parser`

Current executable slice:

- `stdout_json`
- `metrics_json`
- `generated_parser`

When `metrics_source: metrics_json` is used, also declare `metrics_path`.
When `metrics_source: generated_parser` is used, also declare `parser_template` and enable `adapter_generation.allowed: true`.

Supported executable parser templates in this slice:

- `key_value_lines`

Example:

```yaml
evaluation:
  command: "python eval/run_eval.py"
  metrics_source: generated_parser
  parser_template: key_value_lines

adapter_generation:
  allowed: true
```

### `comparison`

How to decide whether the candidate improved.

Fields:

- `primary_metric`
- `direction`
- `min_improvement`: optional
- `decision_rule`: optional

### `constraints`

Metrics or conditions that must not be violated.

Examples:

- latency max
- cost max
- size max
- tests pass required

### `safety`

What can and cannot be touched.

Fields:

- `editable`
- `protected`
- `requires_confirmation`: optional list of higher-risk actions

## Optional Sections

### `algorithm`

Use this when the user already has a fixed method or search algorithm.

```yaml
algorithm:
  provided_by_user: true
  command: "python tools/propose_candidate.py --json"
```

If this is present, AutoOptimize should respect it before choosing its own search strategy.

### `adapter_generation`

Use this when AutoOptimize may generate helper code.

```yaml
adapter_generation:
  allowed: true
  allowed_kinds:
    - metrics_parser
    - eval_wrapper
    - config_mutator
  output_dir: auto_optimize_outputs/generated_adapters
```

### `budget`

Use this to limit execution.

```yaml
budget:
  max_experiments: 10
  max_runtime_minutes: 30
  max_failed_evaluations: 3
```

## Conversion To Contract

The declaration should be converted into the executable contract only after:

- required fields are present
- editable and protected scopes do not conflict
- evaluation can be smoke-tested or validated
- generated adapter permissions are known
- comparison rules are unambiguous

The existing `optimization.contract.yaml` format can remain the lower-level execution format. The declaration is the user-facing interface.

## Implemented Command

The first executable declaration slice is now available:

```bash
python -m auto_optimize.cli declare path/to/optimization.declaration.yaml --output path/to/optimization.contract.yaml
python -m auto_optimize.cli explain-contract path/to/optimization.contract.yaml
python -m auto_optimize.cli validate path/to/optimization.contract.yaml
```

Reference example:

```bash
python -m auto_optimize.cli declare examples/declarations/generic_config_optimization.declaration.yaml --output /tmp/auto-optimize-declared.contract.yaml
```
