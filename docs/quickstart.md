# Quickstart

This is the shortest useful path through AutoOptimize:

1. inspect a workspace
2. generate or review a contract
3. validate it
4. run optimization
5. read the report

If you want the fastest first success, start with the checked-in FAQ example.

## Ten-Minute Path

Run these commands from the repository root:

```bash
python -m auto_optimize.cli advisor --workspace examples/faq_retrieval/workspace
python -m auto_optimize.cli validate examples/faq_retrieval/optimization.contract.yaml
python -m auto_optimize.cli run examples/faq_retrieval/optimization.contract.yaml
python -m auto_optimize.cli report examples/faq_retrieval/workspace/auto_optimize_outputs
```

## What Each Step Produces

`advisor`

- inspects the workspace
- writes `examples/faq_retrieval/workspace/auto_optimize_outputs/optimization.contract.draft.yaml`
- writes `examples/faq_retrieval/workspace/auto_optimize_outputs/readiness_report.json`

`validate`

- checks workspace, scope, evaluation command, search space, metrics, and Git settings
- writes `examples/faq_retrieval/workspace/auto_optimize_outputs/contract_validation_report.md`

`run`

- evaluates the baseline
- tries bounded candidate changes
- writes:
  - `experiment_log.jsonl`
  - `run_summary.json`
  - `optimization_report.md`
  - `run_history.jsonl`
  - `best_run_snapshot.json`

`report`

- regenerates `optimization_report.md` from a previous run summary

## How To Tell It Worked

The workflow is successful when:

- `validate` prints `Contract validation passed.`
- `run` prints paths for `run_summary.json`, `experiment_log.jsonl`, and `optimization_report.md`
- `optimization_report.md` exists under the workspace `auto_optimize_outputs/` directory

## Which Path Should You Start With

- Use [walkthrough-faq.md](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/docs/walkthrough-faq.md:1) if you want the easiest first run.
- Use [walkthrough-benchmark.md](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/docs/walkthrough-benchmark.md:1) if you want retrieval or reranking benchmark flow.
- Use [walkthrough-custom-eval.md](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/docs/walkthrough-custom-eval.md:1) if you want to adapt your own evaluation script.
- Use [command-guide.md](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/docs/command-guide.md:1) if you want to understand when to use each CLI command.
