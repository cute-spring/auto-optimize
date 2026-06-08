# Quickstart

AutoOptimize should start from a user declaration.

For now, the executable form is still `optimization.contract.yaml`, but the mental model is declaration first:

1. state the objective
2. declare editable variables
3. declare protected scope
4. declare evaluation
5. declare metrics and comparison
6. validate
7. run bounded experiments
8. inspect the report

## Minimal Declaration Shape

```yaml
objective:
  description: "Improve quality without increasing latency too much."

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

safety:
  editable:
    - configs/retrieval.yaml
  protected:
    - eval/
    - data/
```

See [declaration-protocol.md](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/docs/declaration-protocol.md:1) for the intended user-facing protocol.

## Current Executable Path

The declaration-first slice now supports a declaration-native run path:

```bash
python -m auto_optimize.cli run examples/declarations/generic_config_optimization.declaration.yaml
python -m auto_optimize.cli report examples/faq_retrieval/workspace/auto_optimize_outputs
```

If you want to inspect the generated contract explicitly before execution, keep the transitional contract-first path:

```bash
python -m auto_optimize.cli declare examples/declarations/generic_config_optimization.declaration.yaml --output /tmp/auto-optimize-declared.contract.yaml
python -m auto_optimize.cli explain-contract /tmp/auto-optimize-declared.contract.yaml
python -m auto_optimize.cli validate /tmp/auto-optimize-declared.contract.yaml
python -m auto_optimize.cli run /tmp/auto-optimize-declared.contract.yaml
```

## How To Tell It Worked

The workflow is successful when:

- validation passes
- run artifacts are written under `auto_optimize_outputs/`
- the report explains baseline metrics, candidate decisions, and final result

## Important Direction Note

The FAQ and benchmark examples are reference fixtures. They are not required project shapes. A user project should be supported by declarations, generated adapters, and generic execution, not by being forced into a fixed scenario.

For now, the executable slice directly supports declarations that mutate `yaml_path` and `json_path` variables and read metrics from `stdout_json` or `metrics_json`. Broader declaration forms remain planned work.
