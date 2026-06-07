# Contract Authoring

This guide is for writing or editing the current executable AutoOptimize contract.

Direction note: the project should move toward a user-facing declaration protocol. The contract remains the current executable form, not the product's final mental model.

## The Smallest Useful Contract

A practical minimal contract needs these sections:

- `schema_version`
- `scenario`
- `workspace`
- `editable_scope`
- `search_space`
- `evaluation`
- `metrics`

Everything else can start from defaults or be added later.

See these starter files:

- [minimal_faq.contract.yaml](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/examples/contracts/minimal_faq.contract.yaml:1)
- [minimal_custom_eval.contract.yaml](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/examples/contracts/minimal_custom_eval.contract.yaml:1)

You can also choose between two generated contract styles:

- `minimal`
  - best when you want the easiest file to read and edit first
  - keeps only the essential sections
- `expanded`
  - best when you want the more operational contract shape up front
  - keeps sections such as constraints, run policy, version control, and report

## Write In This Order

### 1. Point at the workspace

`workspace.path` should point to the directory AutoOptimize will treat as the optimization target.

It is resolved relative to the contract file, not relative to the current shell directory.

### 2. Declare what can change

Put mutable config files in `editable_scope`.

Typical examples:

- `configs/retrieval.yaml`
- `configs/reranker.yaml`
- `configs/embedding.yaml`

If a file is not in `editable_scope`, AutoOptimize will refuse to mutate it.

### 3. Protect your evaluator and data

Keep scoring logic and datasets under protected paths such as:

- `eval/`
- `data/`
- `.env`
- `secrets/`

These paths belong in `protected_scope`.

### 4. Define the search space

Each search parameter needs:

- a name
- candidate values
- a mapping type
- a target file
- a dotted path inside that file

Example:

```yaml
search_space:
  top_k:
    values: [5, 10, 20]
    mapping:
      type: yaml_path
      file: "configs/retrieval.yaml"
      path: "retrieval.top_k"
```

### 5. Point at the evaluation command

The evaluation command should run from the workspace root and emit the metrics the contract expects.

Current executable-contract path:

```yaml
evaluation:
  command: "python eval/run_eval.py --json"
```

### 6. Choose metrics

At minimum, define:

- `metrics.primary.name`
- `metrics.primary.direction`

You can add `secondary` metrics later.

## Useful Commands While Authoring

Explain the contract in human-readable form:

```bash
python -m auto_optimize.cli explain-contract examples/contracts/minimal_faq.contract.yaml
```

Validate before any run:

```bash
python -m auto_optimize.cli validate examples/contracts/minimal_faq.contract.yaml
```

Generate a contract from a recognized workspace:

```bash
python -m auto_optimize.cli guided --workspace examples/faq_retrieval/workspace --style minimal
python -m auto_optimize.cli build --workspace examples/faq_retrieval/workspace --style expanded
```

## Common Authoring Mistakes

- `workspace.path` points to the wrong directory
- `editable_scope` is empty
- a search parameter points at a file not listed in `editable_scope`
- a search parameter path does not exist in the target YAML or JSON
- the eval command points at a file not protected by `protected_scope`
- the eval output does not contain the declared primary metric

## A Good First Workflow

1. Start from `guided` or one of the minimal examples.
2. Edit only `workspace`, `editable_scope`, `search_space`, `evaluation`, and `metrics`.
3. Run `explain-contract`.
4. Run `validate`.
5. Only run optimization after the validation report is clean.
