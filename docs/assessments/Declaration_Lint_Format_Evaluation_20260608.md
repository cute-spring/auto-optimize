# Declaration Lint And Format Evaluation

Date: 2026-06-08

## Question

Should AutoOptimize add dedicated `declaration lint` and `declaration format` commands in the current slice?

## Current State

The current declaration workflow already has:

- YAML loading
- structural validation
- executable-slice validation through `declare` and `validate`
- actionable remediation messages for common declaration failures

## Assessment

Adding dedicated lint/format commands right now would provide limited incremental value.

Why:

1. declaration schema is still evolving
2. current failures are already surfaced through `declare`
3. formatting can currently rely on normal YAML editor tooling
4. a new command pair would add CLI surface area before there is a strong workflow need

## Decision

Do not introduce dedicated `declaration lint` or `declaration format` commands in the current slice.

Keep the current workflow:

1. author declaration YAML
2. run `declare`
3. run `validate`
4. fix issues using the reported remediation hints

## Revisit Criteria

Revisit lint/format commands when one of these becomes true:

1. the declaration schema stabilizes enough to justify a dedicated style contract
2. multiple teams start hand-authoring declarations at scale
3. declaration-specific hygiene checks go beyond what `declare` and `validate` already express

## Outcome For Checklist

Checklist item "评估是否需要 declaration lint / format 命令" is complete with a defer decision for the current slice.
