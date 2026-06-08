# Generated Adapter Variable Evaluation

Date: 2026-06-08

## Question

Should AutoOptimize introduce a minimal executable `generated_adapter` variable kind inside declaration `variables` during the current Priority 4 slice?

## Current State

- Declaration execution already supports generated helper code for evaluation through `metrics_source: generated_parser`.
- Generated helper code is currently represented as evaluation-time adapter configuration, not as a search-space variable.
- The current executable variable kinds are:
  - `yaml_path`
  - `json_path`
  - `env_var`
  - `cli_arg`

Relevant implementation points:

- Declaration conversion only turns variables into value-mutation mappings and handles generated code under `evaluation.adapter`.
- Candidate planning assumes each parameter expands into a finite list of scalar candidate values.
- Candidate application and rollback assume one of three mutation targets:
  - structured file paths
  - environment variables
  - CLI arguments
- Git commit support stages changed files from recorded mutation targets, and `cli_arg` is already explicitly blocked from commit-backed accepted state because it is runtime-only.

## Assessment

Introducing `generated_adapter` as a search-space variable in the current runner shape would be a semantic mismatch.

Why:

1. Search-space variables currently mean "swap one value into an existing target".
2. Generated adapters mean "materialize a new executable artifact, wire it into evaluation, and track risk/provenance".
3. Those are different lifecycle models.

The current runner does not yet have a first-class abstraction for "artifact-producing candidate changes".

Missing pieces for a safe minimal executable version:

1. A candidate value schema that can describe generated code intent, not just scalar replacements.
2. A rollback model for generated artifacts and evaluation wiring changes together.
3. A commit model for accepted generated artifacts.
4. A safety model for editable/protected scope over generated output destinations.
5. Provenance and risk reporting at the candidate-change level, not only at the evaluation-adapter level.

## Decision

Do not introduce `generated_adapter` as an executable declaration variable kind in the current Priority 4 slice.

Keep generated code in the existing lane:

- declaration permission via `adapter_generation`
- runtime materialization via `evaluation.adapter`
- provenance/risk reporting via run summary and report

This preserves a coherent boundary:

- variables change values
- adapters change execution plumbing

## What To Do Instead

If a project needs generated helper code today:

1. Use normal variables for file/env/CLI tuning.
2. Use `metrics_source: generated_parser` when output parsing needs generated code.
3. Record adapter permissions through `adapter_generation`.

## Revisit Criteria

Revisit executable `generated_adapter` variables only after AutoOptimize has:

1. a generic artifact-producing candidate abstraction
2. explicit generated-artifact rollback and accepted-state semantics
3. commit/report support for generated artifacts as first-class candidate outputs

## Outcome For Checklist

Priority 4 item "评估是否引入 `generated_adapter` 变量类型的最小可执行版本" is complete with a defer decision for the current slice.
