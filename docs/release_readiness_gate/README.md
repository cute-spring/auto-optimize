# Release Readiness Gate

This directory holds the governance artifacts that turn project progress into auditable release evidence.

## Files

- `release_readiness_template.md`: the gate template to fill before calling a slice release-ready
- `definition_of_done.md`: stage-level completion definitions
- `status_audit_signals.yaml`: machine-readable progress signals for status-audit automation

## Operating Rule

After every milestone-sized project push:

1. Update [AutoOptimize_Execution_Checklist_20260608.md](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/docs/plans/AutoOptimize_Execution_Checklist_20260608.md).
2. Refresh the relevant entries in `status_audit_signals.yaml`.
3. Regenerate the current status snapshot with `python -m auto_optimize.cli status-audit`.
4. If the slice is approaching release or handoff, instantiate `release_readiness_template.md` into a dated gate file in this directory.

This rule exists so release status does not depend on memory, chat history, or manual interpretation of scattered notes.
