# AutoOptimize

AutoOptimize is a contract-driven optimization skill suite MVP. The current implementation includes safe contract loading and validation, a one-variable-at-a-time optimization loop, Markdown/JSONL reporting, and optional local Git branching plus accepted-change commits.

## Available Commands

```bash
python -m auto_optimize.cli validate examples/faq_retrieval/optimization.contract.yaml
python -m auto_optimize.cli advisor --help
python -m auto_optimize.cli run --help
python -m auto_optimize.cli report --help
python scripts/download_benchmark_dataset.py --list
python scripts/materialize_benchmark_workspace.py --help
```

## Current Scope

- `advisor`: implemented for draft contract and readiness report generation
- `validate`: implemented
- Git-aware contract validation: implemented
- `run`: implemented as a validation-first MVP loop with one-variable-at-a-time candidates and experiment memory
- `report`: implemented for regenerating reports from run artifacts
- local branch creation and accepted-change commits: implemented when enabled in the contract

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

Current run mode covers:

- baseline evaluation plus candidate evaluation
- YAML/JSON parameter mutation within `editable_scope`
- accept or reject decisions using the configured primary metric and constraints
- file-snapshot rollback for rejected candidates
- experiment logs in JSONL and CSV plus Markdown summary reports
- run history and best-run memory snapshots
- optional local Git branch creation and commit of accepted changes

Current advisor mode covers:

- workspace inspection for FAQ and materialized benchmark scenarios
- draft contract generation at `auto_optimize_outputs/optimization.contract.draft.yaml`
- readiness report generation at `auto_optimize_outputs/readiness_report.json`
- metric profile recommendation based on scenario type

## Development

```bash
pytest
```

## Benchmark Planning Assets

- Architecture overview: `docs/architecture-overview.md`
- Public dataset analysis: `examples/datasets.md`
- Benchmark contract templates: `examples/benchmarks/`
- Benchmark workspace materializer: `scripts/materialize_benchmark_workspace.py`
- Metric templates: `examples/metric_templates/`
- Dataset downloader scaffold: `scripts/download_benchmark_dataset.py`
- Metric reference: `docs/benchmark-metrics.md`
- Contract metric profiles: `docs/contract-metric-profiles.md`

The benchmark templates are designed for:

- embedding quality
- retrieval latency
- reranking quality
- embedding / index size tracking
