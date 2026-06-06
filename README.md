# AutoOptimize

AutoOptimize is a contract-driven optimization skill suite MVP. The current implementation focuses on safe contract loading and validation, including v0.2 Git-aware safety checks, before experiment runner logic is introduced.

## Available Commands

```bash
python -m auto_optimize.cli validate examples/faq_retrieval/optimization.contract.yaml
python -m auto_optimize.cli advisor --help
python -m auto_optimize.cli run --help
python -m auto_optimize.cli report --help
```

## Current Scope

- `validate`: implemented
- Git-aware contract validation: implemented
- `advisor`: stubbed for future work
- `run`: stubbed for future work
- `report`: stubbed for future work

## Validation Outputs

The validator writes a Markdown report to the contract workspace output directory, typically:

```text
<workspace>/auto_optimize_outputs/contract_validation_report.md
```

Current validation covers:

- workspace and scope checks
- protected evaluation path checks
- baseline evaluation JSON parsing
- run budget checks
- Git repository presence when enabled
- clean worktree enforcement
- blocking unsupported remote Git operations in MVP

## Development

```bash
pytest
```
