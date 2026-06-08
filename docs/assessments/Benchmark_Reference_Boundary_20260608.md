# Benchmark And Reference Boundary

Date: 2026-06-08

## Goal

Clarify the boundary between benchmark/reference assets and the generic declaration-driven flow.

## Decision

Benchmark and FAQ-style assets remain in the repository as:

- reference fixtures
- regression coverage inputs
- example authoring material

They are not the required product entry point.

## Generic Flow Owns

The generic flow is responsible for:

1. declaration authoring
2. declaration-to-contract conversion
3. validation
4. generated adapter execution
5. optimization run orchestration
6. reporting and provenance

These behaviors must continue to work even when no built-in scenario fixture matches the user's project.

## Reference Assets Own

Reference assets are still useful for:

1. end-to-end regression tests
2. example declarations and contracts
3. benchmark-shaped evaluation demonstrations
4. fixture-backed smoke coverage for common workflow shapes

## Required Product Boundary

Reference assets may:

- provide default examples
- seed fixture context in `advisor` / `builder`
- help explain likely metric/eval patterns

Reference assets must not:

- become mandatory scenario classification for the main user path
- block declaration-first usage when no scenario matches
- define the only supported workflow vocabulary

## Current Repository Outcome

The repository now reflects this boundary in three places:

1. `guided` and `advisor` are declaration-first
2. reference fixture context is explicitly labeled as compatibility/reference context
3. docs describe FAQ and benchmark material as examples rather than required project shapes

## Follow-Up Rule

Future benchmark/reference additions should justify themselves as either:

- regression fixtures
- example walkthroughs
- optional migration helpers

They should not expand a static scenario catalog as the primary architecture.
