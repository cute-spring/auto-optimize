# Walkthrough: FAQ Example

Use this walkthrough when you want the easiest possible first success.

## What You Need

- the repository checked out locally
- Python environment with the project dependencies installed
- no external model provider or API credentials

## What You Will Run

```bash
python -m auto_optimize.cli advisor --workspace examples/faq_retrieval/workspace
python -m auto_optimize.cli validate examples/faq_retrieval/optimization.contract.yaml
python -m auto_optimize.cli run examples/faq_retrieval/optimization.contract.yaml
python -m auto_optimize.cli report examples/faq_retrieval/workspace/auto_optimize_outputs
```

## What This Example Is

The FAQ example is a deterministic local fixture. It is designed to validate the AutoOptimize workflow itself:

- contract loading
- readiness inspection
- validation
- bounded search
- rollback and reporting

It does not call a remote embedding or reranking API.

## What To Inspect

After `advisor`:

- [optimization.contract.draft.yaml](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/examples/faq_retrieval/workspace/auto_optimize_outputs/optimization.contract.draft.yaml:1)
- [readiness_report.json](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/examples/faq_retrieval/workspace/auto_optimize_outputs/readiness_report.json:1)

After `validate`:

- [contract_validation_report.md](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/examples/faq_retrieval/workspace/auto_optimize_outputs/contract_validation_report.md:1)

After `run`:

- [run_summary.json](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/examples/faq_retrieval/workspace/auto_optimize_outputs/run_summary.json:1)
- [optimization_report.md](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/examples/faq_retrieval/workspace/auto_optimize_outputs/optimization_report.md:1)
- [experiment_log.jsonl](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/examples/faq_retrieval/workspace/auto_optimize_outputs/experiment_log.jsonl:1)

## How To Know You Succeeded

You are done when:

- `advisor` reports a draft contract and readiness report path
- `validate` passes
- `run` finishes and prints artifact paths
- the report shows both baseline metrics and experiment outcomes

## What This Teaches You

This walkthrough gives you the shortest full path through the product:

- how a workspace is inspected
- what a contract looks like
- what validation protects
- what run artifacts look like

After this, the next natural step is either:

- a benchmark workspace via [walkthrough-benchmark.md](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/docs/walkthrough-benchmark.md:1)
- your own eval integration via [walkthrough-custom-eval.md](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/docs/walkthrough-custom-eval.md:1)
