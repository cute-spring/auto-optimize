# Examples

Examples are reference declarations, adapter examples, and regression fixtures.

They are not the product center and should not define the required shape of user projects. AutoOptimize should work from a user's declaration even when none of these examples match.

## How To Read This Directory

- `declarations/`: generic declaration-first examples that compile into executable contracts.
- `contracts/`: minimal executable contract examples that demonstrate the declaration shape.
- `faq_retrieval/`: small local fixture for validating the generic execution loop.
- `benchmarks/`: benchmark-shaped reference declarations and materializer utilities.
- `metric_templates/`: optional examples of comparison-rule bundles.
- `datasets.md`: background reference for benchmark examples only.

## Recommended Use

Use examples to learn:

- how to declare editable variables
- how to protect eval code and data
- how metrics are returned
- how reports and logs look

Do not use examples as evidence that user projects must be FAQ, embedding, reranking, or benchmark systems.

## Current Best Starting Point

Start with:

- [docs/generic-skill-direction.md](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/docs/generic-skill-direction.md:1)
- [docs/declaration-protocol.md](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/docs/declaration-protocol.md:1)
- [examples/declarations/generic_config_optimization.declaration.yaml](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/examples/declarations/generic_config_optimization.declaration.yaml:1)

Then use the FAQ fixture only to see the current runner operate end to end.
