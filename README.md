# AutoOptimize

AutoOptimize is a contract-driven optimization skill suite MVP. The current implementation includes safe contract loading and validation, a bounded search optimization loop with one-variable and pairwise strategies, Markdown/JSONL reporting, and optional local Git branching plus accepted-change commits.

## Start Here

If you are new to the project, use this order:

1. [Quickstart](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/docs/quickstart.md:1)
2. [Command Guide](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/docs/command-guide.md:1)
3. [FAQ Walkthrough](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/docs/walkthrough-faq.md:1)
4. [Examples Index](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/examples/README.md:1)

## Available Commands

```bash
python -m auto_optimize.cli validate examples/faq_retrieval/optimization.contract.yaml
python -m auto_optimize.cli advisor --help
python -m auto_optimize.cli build --help
python -m auto_optimize.cli guided --help
python -m auto_optimize.cli template --json
python -m auto_optimize.cli run --help
python -m auto_optimize.cli report --help
python scripts/download_benchmark_dataset.py --list
python scripts/materialize_benchmark_workspace.py --help
python scripts/export_benchmark_dataset.py --help
```

## Current Scope

- `advisor`: implemented for draft contract and readiness report generation
- `build`: implemented for composing a generated contract from scenario templates and metric profiles
- `guided`: implemented as advisor plus generated-contract workflow for beginners
- `template`: implemented for listing available scenarios, metric profiles, and benchmark datasets
- `validate`: implemented
- Git-aware contract validation: implemented
- `run`: implemented as a validation-first MVP loop with bounded one-variable or pairwise candidates and experiment memory
- `report`: implemented for regenerating reports from run artifacts
- local branch creation, accepted-change commits, and optional remote push / PR handoff: implemented when enabled in the contract

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
- validating remote Git prerequisites such as remotes and GitHub CLI when enabled

Current run mode covers:

- baseline evaluation plus candidate evaluation
- configurable `search_strategy` with `one_variable`, `pairwise`, and `one_variable_then_pairwise`
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

Current build and guided modes cover:

- generated contract composition from scenario templates plus metric profiles
- automatic workspace-relative `workspace.path` resolution
- metric profile stamping through `builder_context`
- a beginner-friendly `guided` path that produces readiness plus a generated contract in one pass

## Development

```bash
pytest
```

## Benchmark Planning Assets

- Quickstart: `docs/quickstart.md`
- Command guide: `docs/command-guide.md`
- FAQ walkthrough: `docs/walkthrough-faq.md`
- Benchmark walkthrough: `docs/walkthrough-benchmark.md`
- Custom eval walkthrough: `docs/walkthrough-custom-eval.md`
- Architecture overview: `docs/architecture-overview.md`
- Skill improvement roadmap: `docs/skill-improvement-roadmap.md`
- Examples index: `examples/README.md`
- Public dataset analysis: `examples/datasets.md`
- Benchmark contract templates: `examples/benchmarks/`
- Benchmark workspace materializer: `scripts/materialize_benchmark_workspace.py`
- Metric templates: `examples/metric_templates/`
- Dataset downloader scaffold: `scripts/download_benchmark_dataset.py`
- Dataset export bridge: `scripts/export_benchmark_dataset.py`
- Metric reference: `docs/benchmark-metrics.md`
- Contract metric profiles: `docs/contract-metric-profiles.md`

The benchmark templates are designed for:

- embedding quality
- retrieval latency
- reranking quality
- embedding / index size tracking

Materialized benchmark workspaces now include sample corpus/query/qrels assets plus a data-driven evaluation harness, so they can be validated and run end to end without external model dependencies.
They also support optional provider-backed execution paths for real local embedding or reranking models with safe fallback to sample mode.
For supported Hugging Face MTEB datasets, the download/export path now handles multi-config layouts and produces a normalized `auto_optimize_export/` directory that the materializer can ingest directly.
