# Generic Skill Improvement Roadmap

AutoOptimize is a generic, declaration-driven optimization skill.

The project direction is not to build a large catalog of hardcoded scenarios, datasets, providers, or benchmark adapters. Those assets may exist as examples, tests, and reference implementations, but they are not the product center.

The product center is a generic workflow:

1. The user declares the optimization goal.
2. The user declares what can change and what must not change.
3. The user declares how evaluation is run and how metrics are read.
4. The user declares what counts as improvement, regression, or constraint violation.
5. The skill validates the declaration, generates temporary adapters when useful, runs bounded experiments, compares results, rolls back rejected changes, and reports what happened.

## Guiding Principles

- Build for arbitrary user projects, not for a fixed set of scenarios.
- Prefer user declarations over static templates.
- Generate temporary adapter code when that lowers setup burden.
- Treat examples, benchmark fixtures, metric profiles, and provider demos as optional references.
- Keep safety boundaries explicit before mutation or generated code execution.
- Respect user-provided algorithms, test commands, and comparison rules before inventing replacements.
- Ask only when the user has not supplied a decision that materially changes behavior or risk.

## Milestone 1: Direction Realignment

### Goal

Make every public project document describe AutoOptimize as a generic declaration-driven skill.

### Scope

- Rewrite top-level positioning in `README.md` and `SKILL.md`.
- Replace static scenario-centric roadmap language.
- Reframe examples as reference declarations and regression fixtures.
- Make benchmark and dataset docs clearly secondary.
- Document the new declaration-first mental model.

### Acceptance Criteria

- No primary document presents FAQ, embedding, reranking, or public datasets as the product direction.
- Examples are described as optional reference cases.
- The main onboarding path starts from a user declaration, not from a fixed scenario catalog.

## Milestone 2: Declaration Protocol

### Goal

Define the minimal information a user must provide for a generic optimization task.

### Scope

- Define a declaration protocol with:
  - objective
  - editable variables
  - protected files and data
  - evaluation command
  - metric extraction rule
  - comparison rule
  - constraints
  - budget
  - optional user-provided algorithm
- Allow declarations to be authored as YAML, generated from guided conversation, or derived from an existing contract.
- Keep the protocol natural enough for users who do not know the internal contract schema.

### Acceptance Criteria

- A new user can describe a custom task without pretending it is FAQ, embedding, or reranking.
- The declaration can be converted into an executable contract.
- Existing examples can be re-expressed as reference declarations.

## Milestone 3: Dynamic Adapter Generation

### Goal

Let the skill generate run-specific helper code when the user has supplied enough declarations but not a ready-made adapter.

### Scope

- Generate temporary code for:
  - evaluation wrappers
  - metric parsers
  - config mutation helpers
  - environment patchers
  - result comparators
- Store generated code under the run output directory, not as permanent scenario code.
- Record generated code in reports so users can inspect what was run.
- Require confirmation for generated code that edits project code, uses credentials, calls paid services, or performs risky operations.

### Acceptance Criteria

- A user does not need to prebuild a full scenario-specific adapter for common cases.
- Generated code is auditable and scoped.
- Existing static adapters are treated as examples of what generated adapters may look like.

## Milestone 4: Generic Execution Loop

### Goal

Keep the runner generic and independent from any domain.

### Scope

- Run baseline evaluation.
- Generate candidates from declared variables.
- Mutate only declared editable targets.
- Execute the declared evaluation method or generated adapter.
- Parse metrics according to the declaration.
- Compare using the declared objective and constraints.
- Accept, reject, roll back, and report.

### Acceptance Criteria

- The runner does not need to know whether the target is FAQ, search, pricing, prompt tuning, config tuning, or another domain.
- Domain-specific behavior lives in user declarations or generated run adapters.

## Milestone 5: Usability And Trust

### Goal

Make the generic workflow easy to start and easy to trust.

### Scope

- Provide a declaration-first quickstart.
- Provide a guided declaration builder.
- Provide `explain` output that clarifies what will be changed, how evaluation runs, and how decisions are made.
- Improve validation messages with concrete remediation.
- Improve reports with generated-code summaries, metric comparisons, decision reasons, and risk flags.

### Acceptance Criteria

- A user can start from their own task statement.
- The skill can show exactly what it plans to mutate and execute.
- The report supports an adoption decision without requiring users to inspect raw logs.

## Non-Goals

- Do not expand public dataset support as a product goal.
- Do not build a provider catalog as a product goal.
- Do not hardcode more domain-specific scenario behavior as the primary path.
- Do not force user projects to match FAQ, embedding, reranking, or benchmark shapes.

## Existing Assets Repositioning

- FAQ example: reference declaration and local regression fixture.
- Benchmark examples: reference declarations for more complex evaluation shapes.
- Metric profiles: optional examples of comparison rules.
- Provider demos: optional examples of adapter behavior.
- Dataset scripts: optional reference utilities, not the generic skill core.

## Next Implementation Slice

The direction realignment docs are now in place. The next implementation slice should make the declaration-first layer executable:

- implement declaration-to-contract generation
- add validation for declaration fields before contract conversion
- introduce `auto_optimize_outputs/generated_adapters/` as the run-specific adapter location
- generate the first simple metrics parser adapter from a declaration
- record generated adapter paths and source summaries in reports
