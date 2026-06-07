# Walkthrough: Custom Evaluation Declaration

This walkthrough shows the intended generic path.

The user should not have to reshape their project into a fixed FAQ, embedding, reranking, or benchmark scenario. The user should declare how their own evaluation works.

## What To Declare

At minimum:

- objective
- editable variables
- protected files and data
- evaluation command
- metrics source
- primary comparison rule
- constraints

Example:

```yaml
objective:
  description: "Improve generated answer quality while keeping test runtime under 5 minutes."

variables:
  - name: prompt_style
    kind: yaml_path
    target: configs/prompt.yaml
    path: prompt.style
    values: [baseline, concise, evidence_first]

evaluation:
  command: "python eval/run_eval.py --json"
  metrics_source: stdout_json

comparison:
  primary_metric: quality_score
  direction: maximize

constraints:
  runtime_seconds:
    max: 300

safety:
  editable:
    - configs/prompt.yaml
  protected:
    - eval/
    - data/
```

See [declaration-protocol.md](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/docs/declaration-protocol.md:1).

## Current Executable Form

Today, run mode still consumes an executable contract.

Use:

```bash
python -m auto_optimize.cli explain-contract examples/contracts/minimal_custom_eval.contract.yaml
python -m auto_optimize.cli validate examples/contracts/minimal_custom_eval.contract.yaml
```

Then adapt the contract fields to your project:

- `workspace.path`
- `editable_scope`
- `search_space`
- `evaluation.command`
- `metrics.primary`
- `constraints`
- `protected_scope`

## Dynamic Adapter Direction

The intended future flow is:

1. User declares the evaluation command and metrics source.
2. AutoOptimize validates the declaration.
3. If needed, AutoOptimize generates a temporary parser or wrapper under `auto_optimize_outputs/generated_adapters/`.
4. The generated code is recorded in the report.
5. The generic runner executes the normalized contract.

Existing fixed example layouts are only references.
