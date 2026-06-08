# Definition Of Done

This file defines what each current project stage must prove before it is considered complete.

## Priority 1: Dynamic Adapter Minimal Loop

Done when:

- declaration can request at least one generated helper path
- generated adapter code is materialized under `auto_optimize_outputs/generated_adapters/`
- validation and run both recognize the adapter path
- run summary and report record generated adapter provenance
- end-to-end tests cover the adapter workflow

## Priority 2: Guided Path De-Scenarization

Done when:

- `advisor` emits a generic draft declaration
- `guided` defaults to declaration-first generation
- readiness reporting is declaration-first
- scenario assets are treated as reference fixtures, not the required entry point
- regression tests cover guided/advisor declaration-first paths

## Priority 3: Trust / Reporting

Done when:

- report distinguishes declaration input, generated contract, and generated adapters
- report includes adapter provenance and risk flags
- report includes decision rationale summary
- regenerate flow preserves the new report sections
- full tests remain green

## Priority 4: Declaration Execution Coverage

Done when:

- at least one file-backed variable kind works
- runtime-only variable kinds needed for common integrations are executable
- at least one non-JSON metrics source works
- declaration failure and remediation messages are actionable
- focused validation and run tests exist for each newly executable declaration slice

## Priority 5: Governance And Release Artifacts

Done when:

- release readiness artifacts live under `docs/release_readiness_gate/`
- there is a reusable gate template
- stage completion criteria are documented
- status-audit can read countable progress signals from a stable file
- milestone updates explicitly require checklist maintenance
