# Walkthrough: Custom Eval Integration

Use this walkthrough when you want to adapt AutoOptimize to your own evaluation logic.

## Current MVP Shape

Today, the easiest custom path is to follow the FAQ-style workspace layout and replace the example config files and eval logic with your own:

```text
your_workspace/
  configs/
    retrieval.yaml
    reranker.yaml
    embedding_strategy.yaml
  eval/
    run_eval.py
  data/
    ...
```

This is the smoothest onboarding path because `advisor`, `guided`, and `build` already recognize that shape.

## What You Need

- one workspace directory with config files you are comfortable letting AutoOptimize edit
- one evaluation command that can run from the workspace root
- one primary metric that your eval returns consistently

## Recommended First Pass

1. Copy the FAQ workspace shape.
2. Replace the config contents with your own knobs.
3. Replace `eval/run_eval.py` with your own evaluation logic.
4. Keep your mutable config files in `configs/`.
5. Keep your eval code and datasets in protected paths such as `eval/` and `data/`.

## Commands

Inspect and generate onboarding artifacts:

```bash
python -m auto_optimize.cli advisor --workspace /path/to/your_workspace --scenario faq_retrieval
python -m auto_optimize.cli guided --workspace /path/to/your_workspace --scenario faq_retrieval
```

Then validate and run the generated contract:

```bash
python -m auto_optimize.cli validate /path/to/your_workspace/auto_optimize_outputs/optimization.contract.generated.yaml
python -m auto_optimize.cli run /path/to/your_workspace/auto_optimize_outputs/optimization.contract.generated.yaml
```

## What Your Eval Must Do

At minimum, your evaluation command should:

- run successfully from the workspace root
- emit the contract's primary metric
- emit any metrics referenced by constraints
- avoid mutating protected files

In the current MVP, the cleanest path is to keep the eval command as:

```bash
python eval/run_eval.py --json
```

and return structured metrics from that script.

## What To Inspect

- `auto_optimize_outputs/readiness_report.json`
- `auto_optimize_outputs/optimization.contract.generated.yaml`
- `auto_optimize_outputs/contract_validation_report.md`

Validation is the point where most integration issues should surface:

- missing editable files
- eval path not protected
- primary metric missing
- search space mapping path missing

## Honest Boundaries

This custom-eval path is usable today, but it is still MVP-shaped:

- generic arbitrary workspace inference is not complete yet
- the easiest path is still to follow the recognized FAQ-style layout
- a more explicit eval protocol and smoke-eval command are planned next

If your workspace does not fit the recognized patterns, start from a generated contract and edit it manually before validation.
