# AutoOptimize

AutoOptimize is a generic, declaration-driven optimization skill.

It is designed for user projects where the user can declare the goal, editable variables, protected boundaries, evaluation method, metrics, and comparison rule. AutoOptimize should then validate the declaration, generate temporary helper code when useful, run bounded experiments, compare results, roll back rejected changes, and produce an auditable report.

It is not intended to become a large static catalog of hardcoded scenarios, datasets, providers, or benchmark adapters. Existing FAQ, embedding, reranking, and benchmark assets are reference examples and regression fixtures.

## Start Here

Read these first:

1. [Generic Skill Direction](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/docs/generic-skill-direction.md:1)
2. [Declaration Protocol](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/docs/declaration-protocol.md:1)
3. [Quickstart](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/docs/quickstart.md:1)
4. [Command Guide](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/docs/command-guide.md:1)
5. [Architecture Overview](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/docs/architecture-overview.md:1)

## Core Workflow

1. Declare the optimization objective.
2. Declare editable variables and protected scope.
3. Declare how evaluation runs and where metrics come from.
4. Declare how to compare improvement and regressions.
5. Validate the declaration or generated contract.
6. Run bounded experiments.
7. Inspect the report and decide whether to adopt the result.

## Current Commands

```bash
python -m auto_optimize.cli declare examples/declarations/generic_config_optimization.declaration.yaml --output /tmp/auto-optimize-declared.contract.yaml
python -m auto_optimize.cli advisor --help
python -m auto_optimize.cli guided --help
python -m auto_optimize.cli build --help
python -m auto_optimize.cli explain-contract /tmp/auto-optimize-declared.contract.yaml
python -m auto_optimize.cli validate /tmp/auto-optimize-declared.contract.yaml
python -m auto_optimize.cli run /tmp/auto-optimize-declared.contract.yaml
python -m auto_optimize.cli report examples/faq_retrieval/workspace/auto_optimize_outputs
```

The current CLI still uses `optimization.contract.yaml` as the executable form, but declarations can now generate that executable contract directly. Dynamic adapter generation is still future work.

## Current Implementation

Implemented foundations:

- contract loading and validation
- editable and protected scope checks
- evaluation execution
- YAML and JSON path mutation
- bounded candidate search
- accept/reject decisions
- rollback for rejected candidates
- JSONL/CSV/Markdown reporting
- experiment memory
- optional Git checks, branch creation, commits, push, and PR handoff when explicitly enabled
- contract explanation and minimal/expanded generated contract styles

Important limitation:

- `advisor`, `build`, and `guided` still contain scenario-oriented logic today. That should be treated as transitional support, not the product direction.

## Reference Assets

These are examples, not the core product direction:

- [examples/faq_retrieval/](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/examples/faq_retrieval/README.md:1): local reference declaration and regression fixture.
- [examples/benchmarks/](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/examples/benchmarks/README.md:1): reference benchmark-shaped declarations.
- [examples/metric_templates/](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/examples/metric_templates/README.md:1): optional comparison-rule examples.
- [examples/datasets.md](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/examples/datasets.md:1): background reference only.

Do not treat these assets as required shapes for user projects.

## Development

```bash
pytest
```
