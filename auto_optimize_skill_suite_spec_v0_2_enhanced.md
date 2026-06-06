# AutoOptimize Skill Suite — Codex Implementation Specification v0.2 Enhanced

> Version: v0.2  
> Target reader: Codex / coding agent  
> Purpose: Create a reusable, contract-driven AutoOptimize Skill Suite that can diagnose optimization opportunities, generate optimization contracts, run safe experiment loops, manage changes with Git, and produce clear human-readable reports.

---

## 0. What Changed in v0.2

This v0.2 enhanced specification extends v0.1 with stronger product and engineering boundaries.

Added or strengthened:

1. Skill Suite vs Platform boundary.
2. Advisor / Contract Builder / Runner / Reporter permission boundaries.
3. Light Advisor and Deep Advisor modes.
4. Guided Mode conversation and confirmation rules.
5. Template materialization rules.
6. Experiment Memory and long-term organizational learning design.
7. Pareto solution classification.
8. Default MVP safety policy.
9. Detailed Git / version control strategy.
10. Stronger non-goals and implementation constraints.

The core principle remains:

> All user paths should converge to `optimization.contract.yaml`, and all scenarios should run through the same safe Optimization Core.

---

## 1. Executive Summary

Create an **AutoOptimize Skill Suite** rather than one large monolithic skill.

The suite should help a user improve a project component by:

1. diagnosing what is worth optimizing;
2. helping the user build a safe `optimization.contract.yaml`;
3. validating the contract before any change is made;
4. running controlled experiments inside the allowed scope;
5. using Git checkpoints, branches, commits, and rollbacks to manage changes safely;
6. accepting better changes and rejecting worse changes;
7. logging all successful and failed attempts;
8. producing a final human-readable optimization report.

The conceptual inspiration is an AutoResearch-style loop:

```text
hypothesis
→ candidate change
→ apply candidate safely
→ run evaluation
→ compare metrics
→ accept / reject / keep as Pareto candidate
→ commit or rollback
→ record learning
→ repeat
→ report
```

However, this implementation should be enterprise-safe and scenario-agnostic.

The core must **not** hard-code FAQ, RAG, Prompt, Intent, Memory, or Code Performance logic. Scenario-specific differences should be isolated through:

```text
Scenario Contract
Scenario Template
Scenario Adapter
```

---

## 2. Skill Suite vs Platform Boundary

This project is still a **Skill Suite**, not a full platform.

### 2.1 It Is a Skill Suite

It should be installable and usable as a skill package with:

```text
SKILL.md
CLI commands
local contract files
local outputs
scenario templates
```

It should run locally or inside the agent's available execution environment.

### 2.2 It Is Not Yet a Platform

Do not implement the following in MVP:

```text
Web UI
multi-user login
team permissions
central experiment database
remote job queue
cloud scheduler
approval workflow UI
dashboard
CI/CD merge automation
remote PR creation
cost center integration
```

These may be future platform features.

### 2.3 Future Evolution

The intended evolution path is:

```text
v0.1 / v0.2:
  Local Skill Suite

Future:
  Optimization Framework Skill

Later:
  Optimization Platform
```

For now, keep the implementation local, contract-driven, file-based, testable, and safe.

---

## 3. Recommended Product Shape

Implement as a **Skill Suite** with one user-facing entry point and multiple internal modules.

```text
AutoOptimize Skill Suite
│
├── Shared Core
│   ├── Contract Schema
│   ├── Experiment Log Schema
│   ├── Metric Schema
│   ├── Scope Guard
│   ├── Safety Policy
│   └── Common Report Schema
│
├── Skills / Modules
│   ├── Advisor
│   ├── Contract Builder
│   ├── Runner
│   └── Reporter
│
└── Scenario Packs / Adapters
    ├── FAQ Retrieval
    ├── RAG Chunking
    ├── Prompt Optimization
    ├── Intent Classification
    ├── Memory Retrieval
    └── Code Performance
```

For MVP, implement this as **one skill package / one repository** with clear internal modules. Later, the modules can be split into separate skills if needed.

---

## 4. Skill Identity

Suggested skill directory name:

```text
auto-optimize-skill/
```

Suggested user-facing skill name:

```text
AutoOptimize
```

Suggested `SKILL.md` frontmatter:

```yaml
---
name: auto-optimize
description: Diagnose optimization opportunities, build optimization contracts, run safe experiment loops, compare metrics, manage Git checkpoints, keep better changes, reject worse changes, and generate optimization reports for project components such as RAG, FAQ retrieval, prompts, intent classification, memory retrieval, or performance tuning.
---
```

Important:

- Keep the `description` clear because it determines when Codex should trigger the skill.
- The skill should be invoked when the user says things like:
  - "optimize this project based on eval results"
  - "help me find better RAG parameters"
  - "run experiments to improve FAQ retrieval"
  - "generate an optimization contract"
  - "analyze past experiment logs and produce a report"
  - "advise which parameters I should tune"
  - "try different configs and commit the better one"
  - "use Git to manage accepted/rejected experiments"

---

## 5. Core Design Principle

The main design rule is:

> Keep the optimization engine generic. Put scenario-specific logic into `Scenario Contract`, `Scenario Template`, or `Scenario Adapter`.

The core should know how to:

```text
load contract
validate boundaries
check Git state
run baseline
propose or load experiments
apply candidate changes
run evaluation command
parse metrics
decide accept / reject / Pareto candidate
rollback or commit
record experiment log
maintain Pareto frontier
generate report
```

The core should **not** know hard-coded details like:

```text
chunk_size
top_k
embedding_template
FAQ threshold
intent threshold
prompt style
memory window size
```

Those belong to scenario packs or user-provided contracts.

---

## 6. Module Permission Boundaries

This is a critical safety requirement.

| Module | Read Project Files | Write Project Files | Run Evaluation Commands | Modify Git | Commit Changes |
|---|---:|---:|---:|---:|---:|
| Advisor | Yes | No by default | Optional read-only checks only | No | No |
| Contract Builder | Yes | Only draft contract with approval | No | No | No |
| Runner | Yes | Yes, only within `editable_scope` | Yes | Yes, if enabled | Yes, if enabled |
| Reporter | Reads logs/outputs | Only report files | No | No | No |

Rules:

1. Advisor must be read-only by default.
2. Contract Builder may write `optimization.contract.draft.yaml` only with user approval.
3. Runner is the only module allowed to modify project files.
4. Runner must obey `editable_scope`, `protected_scope`, and Git rules.
5. Reporter must not rerun experiments or modify source files.

---

## 7. Modes

The suite should support four modes.

---

### 7.1 Advisor Mode

Purpose:

> Read-only diagnosis before formal optimization.

Responsibilities:

- inspect user-provided description, project structure, config samples, or existing eval output;
- identify whether the project is ready for automatic optimization;
- recommend optimization opportunities;
- recommend metrics;
- recommend search space;
- generate a draft `optimization.contract.yaml`;
- warn about risks.

Default behavior:

```yaml
advisor_mode:
  read_only: true
  allow_file_modification: false
  allow_evaluation_run: optional
```

Advisor must not modify project files unless explicitly asked to save a draft contract.

Output examples:

```text
auto_optimize_outputs/optimization_advice.md
auto_optimize_outputs/optimization.contract.draft.yaml
auto_optimize_outputs/readiness_report.json
```

---

### 7.2 Advisor Depth Levels

Advisor Mode should support two conceptual depth levels.

#### 7.2.1 Light Advisor

Use when the user only provides a description.

Input examples:

```text
I want to improve RAG retrieval but don't know where to start.
What parameters should I tune for FAQ retrieval?
```

Light Advisor should provide:

```text
likely bottlenecks
recommended metrics
recommended parameters
recommended next steps
draft contract skeleton
```

It should not require reading files.

#### 7.2.2 Deep Advisor

Use when the user provides a workspace path, project structure, config files, or existing eval outputs.

Deep Advisor may inspect:

```text
config files
prompt files
evaluation script names
sample metric outputs
existing experiment logs
directory structure
```

Deep Advisor should produce:

```text
readiness score
detected gaps
optimization opportunity ranking
recommended search space
recommended protected scope
draft contract
risk warnings
```

Deep Advisor is still read-only unless explicitly asked to save draft files.

---

### 7.3 Guided Mode

Purpose:

> Help beginner users provide necessary information step by step.

Guided Mode should ask for required information in stages:

1. task type;
2. goal;
3. workspace path;
4. editable scope;
5. protected scope;
6. evaluation command;
7. primary metric;
8. constraints;
9. run budget;
10. report format.

Guided Mode should **not** ask all questions at once.

Rules:

1. Ask for one category of information at a time.
2. If the user is unsure, provide safe defaults.
3. Do not run optimization immediately.
4. Always generate a contract preview first.
5. Ask for user confirmation before running.
6. Save the generated contract only with user approval.

Example beginner defaults:

```yaml
guided_defaults:
  allow_config_changes: true
  allow_prompt_changes: true
  allow_code_changes: false
  allow_eval_changes: false
  require_contract_preview: true
  require_user_confirmation_before_run: true
  require_clean_worktree: true
```

---

### 7.4 Template Mode

Purpose:

> Let semi-expert users start from a scenario template.

Examples:

```text
Use FAQ Retrieval template.
Use RAG Chunking template.
Use Prompt Optimization template.
Use Intent Classification template.
```

Template Mode should:

1. load the selected scenario template;
2. ask only for missing user-specific fields;
3. materialize a full `optimization.contract.yaml`;
4. validate the contract;
5. ask for confirmation before running.

Important rule:

> A template must never be executed directly. It must first be materialized into a valid contract, then validated, then run.

---

### 7.5 Expert Mode

Purpose:

> Let expert users provide a complete `optimization.contract.yaml` and run directly.

Flow:

```text
load contract
→ validate contract
→ check Git status
→ run baseline
→ execute optimization loop
→ produce logs and reports
```

Expert Mode should still enforce all safety policies.

---

## 8. Unified Entry Flow

All modes should converge to the same contract format.

```text
Advisor Mode
  → draft contract
  → user confirmation
  → Contract Validator
  → Runner

Guided Mode
  → guided questions
  → generated contract
  → user confirmation
  → Contract Validator
  → Runner

Template Mode
  → template + filled fields
  → generated contract
  → Contract Validator
  → Runner

Expert Mode
  → user contract
  → Contract Validator
  → Runner
```

Avoid separate execution flows for each mode.

---

## 9. Primary Artifact: `optimization.contract.yaml`

The contract is the central interface between the user, scenario packs, and the optimization engine.

### 9.1 MVP Contract Example

```yaml
schema_version: "0.2"

scenario:
  type: faq_retrieval
  name: "FAQ Retrieval Optimization"

workspace:
  path: "./faq-project"

editable_scope:
  - "configs/retrieval.yaml"
  - "configs/embedding_template.yaml"
  - "prompts/reranker_prompt.md"

protected_scope:
  - "eval/"
  - "data/golden_set.json"
  - "scripts/evaluate.py"
  - ".env"
  - "secrets/"
  - "production_config/"

search_space:
  top_k:
    values: [5, 10, 20]
    mapping:
      type: yaml_path
      file: "configs/retrieval.yaml"
      path: "retrieval.top_k"

  threshold:
    values: [0.78, 0.82, 0.86]
    mapping:
      type: yaml_path
      file: "configs/retrieval.yaml"
      path: "retrieval.threshold"

  reranker_enabled:
    values: [false, true]
    mapping:
      type: yaml_path
      file: "configs/reranker.yaml"
      path: "enabled"

evaluation:
  command: "python eval/run_eval.py --json"
  output_format: json
  timeout_seconds: 600

metrics:
  primary:
    name: "top1_accuracy"
    direction: maximize

  secondary:
    - name: "recall_at_5"
      direction: maximize
    - name: "mrr"
      direction: maximize
    - name: "latency_ms"
      direction: minimize
    - name: "cost_per_query"
      direction: minimize

constraints:
  latency_ms:
    max: 1000
  cost_per_query:
    max: 0.02
  all_tests_pass:
    required: true

decision_policy:
  mode: constrained_primary_metric
  min_primary_improvement: 0.001

pareto:
  enabled: true
  profiles:
    - accuracy_first
    - balanced
    - latency_first
    - cost_first

run_policy:
  max_experiments: 30
  stop_if_no_improvement_rounds: 8
  random_seed: 42
  dry_run: false
  max_runtime_minutes: 120
  max_failed_evaluations: 5

version_control:
  enabled: true
  require_clean_worktree: true
  create_branch: true
  branch_prefix: "auto-optimize/"
  commit_accepted_changes: true
  rollback_rejected_changes: true
  push_remote: false
  create_pull_request: false
  commit_message_template: |
    auto-optimize: {experiment_id} {summary}

    Scenario: {scenario_type}
    Primary metric: {primary_metric_before} -> {primary_metric_after}
    Decision: {decision}
    Report: {report_path}

report:
  formats:
    - html
    - markdown
    - csv
    - json
  output_dir: "auto_optimize_outputs"
```

---

## 10. Contract Validation Requirements

Before any experiment is run, validate the contract.

Validation must check:

1. `workspace.path` exists.
2. `editable_scope` exists and is not empty.
3. `protected_scope` does not conflict with `editable_scope`.
4. evaluation command exists or can be executed in the workspace.
5. baseline evaluation runs successfully.
6. baseline output contains the primary metric.
7. all secondary metrics referenced by constraints exist.
8. search space is not empty.
9. each search space mapping points to an existing file.
10. each mapped YAML/JSON path exists unless `create_if_missing: true`.
11. protected files include evaluation data, evaluation scripts, secrets, and production configs by default.
12. run budget is valid.
13. if Git mode is enabled, workspace is a Git repo or can be initialized only with explicit user approval.
14. if `require_clean_worktree: true`, the Git worktree must be clean before running.
15. if `commit_accepted_changes: true`, `version_control.enabled` must also be true.
16. if `push_remote: true` or `create_pull_request: true`, validation must fail in MVP because remote operations are not supported.

If validation fails, do not start optimization. Generate a clear validation report.

---

## 11. MVP Scope

### 11.1 MVP Should Support

MVP should support:

- YAML contract loading;
- contract validation;
- YAML and JSON config modification by path;
- running a command-line evaluation;
- parsing JSON metrics;
- baseline evaluation;
- simple experiment planning from discrete search space values;
- accept / reject decision;
- rollback rejected changes;
- Git clean worktree check;
- optional branch creation;
- optional commit for accepted experiments;
- log all experiments;
- generate Markdown and HTML reports;
- generate CSV and JSONL experiment logs.

### 11.2 MVP Should Not Support Yet

Do not implement in MVP:

- arbitrary code rewriting;
- complex multi-agent planning;
- automatic production deployment;
- web dashboard;
- long-running distributed job queue;
- advanced Bayesian optimization;
- full plugin packaging system;
- LLM-as-judge scoring unless user already provides evaluation command;
- remote Git push;
- automatic PR creation;
- automatic merge;
- editing evaluation scripts;
- editing golden datasets.

The MVP should be boring, safe, and reliable.

---

## 12. Recommended Repository Structure

```text
auto-optimize-skill/
│
├── SKILL.md
├── README.md
├── pyproject.toml
├── requirements.txt
│
├── examples/
│   ├── faq_retrieval/
│   │   ├── optimization.contract.yaml
│   │   ├── sample_eval_output.json
│   │   └── README.md
│   ├── rag_chunking/
│   ├── prompt_optimization/
│   ├── intent_classification/
│   └── memory_retrieval/
│
├── auto_optimize/
│   ├── __init__.py
│   ├── cli.py
│   │
│   ├── shared/
│   │   ├── schemas.py
│   │   ├── errors.py
│   │   ├── paths.py
│   │   └── logging.py
│   │
│   ├── contract/
│   │   ├── loader.py
│   │   ├── validator.py
│   │   └── defaults.py
│   │
│   ├── advisor/
│   │   ├── readiness.py
│   │   ├── recommender.py
│   │   └── draft_contract.py
│   │
│   ├── builder/
│   │   ├── guided_questions.py
│   │   └── contract_builder.py
│   │
│   ├── runner/
│   │   ├── orchestrator.py
│   │   ├── planner.py
│   │   ├── modifier.py
│   │   ├── executor.py
│   │   ├── evaluator.py
│   │   ├── decision.py
│   │   ├── version_control.py
│   │   └── rollback.py
│   │
│   ├── memory/
│   │   ├── experiment_store.py
│   │   ├── learned_knowledge.py
│   │   └── pareto.py
│   │
│   ├── reporting/
│   │   ├── report_model.py
│   │   ├── report_generator.py
│   │   ├── templates/
│   │   │   ├── report.md.j2
│   │   │   └── report.html.j2
│   │   └── charts.py
│   │
│   ├── scenario_packs/
│   │   ├── faq_retrieval.yaml
│   │   ├── rag_chunking.yaml
│   │   ├── prompt_optimization.yaml
│   │   ├── intent_classification.yaml
│   │   └── memory_retrieval.yaml
│   │
│   └── safety/
│       ├── scope_guard.py
│       ├── secret_guard.py
│       ├── budget_guard.py
│       └── eval_integrity_guard.py
│
└── tests/
    ├── test_contract_validator.py
    ├── test_modifier_yaml.py
    ├── test_modifier_json.py
    ├── test_decision_engine.py
    ├── test_git_strategy.py
    ├── test_pareto.py
    ├── test_report_generator.py
    └── fixtures/
```

---

## 13. CLI Requirements

Provide a CLI to make the skill easy for Codex to invoke.

Suggested commands:

```bash
python -m auto_optimize.cli advisor --workspace ./project
python -m auto_optimize.cli validate optimization.contract.yaml
python -m auto_optimize.cli run optimization.contract.yaml
python -m auto_optimize.cli report auto_optimize_outputs/experiment_log.jsonl
```

### 13.1 `advisor`

Read-only mode.

Example:

```bash
python -m auto_optimize.cli advisor --workspace ./faq-project --scenario faq_retrieval
```

Outputs:

```text
auto_optimize_outputs/optimization_advice.md
auto_optimize_outputs/optimization.contract.draft.yaml
auto_optimize_outputs/readiness_report.json
```

### 13.2 `validate`

Example:

```bash
python -m auto_optimize.cli validate optimization.contract.yaml
```

Outputs:

```text
auto_optimize_outputs/contract_validation_report.md
```

### 13.3 `run`

Example:

```bash
python -m auto_optimize.cli run optimization.contract.yaml
```

Outputs:

```text
auto_optimize_outputs/best_config.yaml
auto_optimize_outputs/experiment_log.jsonl
auto_optimize_outputs/experiment_log.csv
auto_optimize_outputs/pareto_solutions.yaml
auto_optimize_outputs/run_summary.json
auto_optimize_outputs/optimization_report.md
auto_optimize_outputs/optimization_report.html
```

### 13.4 `report`

Example:

```bash
python -m auto_optimize.cli report auto_optimize_outputs/experiment_log.jsonl
```

Outputs a new report without rerunning experiments.

---

## 14. Git / Version Control Strategy

Git support is a first-class safety mechanism, not a nice-to-have.

The Runner should use Git to manage accepted and rejected changes when enabled.

### 14.1 Goals

Git integration should support:

```text
safe checkpointing
rejected experiment rollback
accepted experiment commit
clear audit trail
experiment-to-commit traceability
protection of user work in progress
```

### 14.2 Required Git Checks Before Run

If `version_control.enabled: true`, Runner must check:

1. Workspace is a Git repository.
2. Git executable is available.
3. Current branch name is captured.
4. Worktree status is captured.
5. If `require_clean_worktree: true`, worktree must be clean.
6. If worktree is dirty and `require_clean_worktree: false`, Runner must record the dirty state and avoid rolling back unrelated user changes.
7. If workspace is not a Git repo, Runner must not initialize Git unless user explicitly approves.

Recommended default:

```yaml
version_control:
  enabled: true
  require_clean_worktree: true
  create_branch: true
  branch_prefix: "auto-optimize/"
  commit_accepted_changes: true
  rollback_rejected_changes: true
  push_remote: false
  create_pull_request: false
```

### 14.3 Branch Strategy

If `create_branch: true`, Runner should create a new branch before experiments.

Branch name format:

```text
auto-optimize/{scenario_type}-{timestamp}
```

Example:

```text
auto-optimize/faq_retrieval-20260606-143000
```

Rules:

1. Do not run experiments directly on `main`, `master`, or protected branches unless user explicitly disables branch creation.
2. Store the original branch in `run_summary.json`.
3. Store the optimization branch in `run_summary.json`.
4. Do not merge back automatically in MVP.

### 14.4 Checkpoint Strategy

Before each experiment:

1. Record `git rev-parse HEAD`.
2. Record `git status --porcelain`.
3. Record planned candidate change.
4. Apply only allowed changes.

The experiment log should include:

```json
{
  "git_before": {
    "branch": "auto-optimize/faq_retrieval-20260606-143000",
    "head": "abc123",
    "worktree_clean": true
  }
}
```

### 14.5 Accepted Experiment Commit

If a candidate is accepted and `commit_accepted_changes: true`, commit the change.

Commit message template:

```text
auto-optimize: {experiment_id} {summary}

Scenario: {scenario_type}
Candidate: {candidate_summary}
Primary metric: {primary_metric_before} -> {primary_metric_after}
Decision: accepted
Report: {report_path}
```

Commit rules:

1. Commit only files changed by the experiment.
2. Do not commit generated reports unless explicitly configured.
3. Record `commit_hash` in `experiment_log.jsonl`.
4. Record changed files and metric deltas in the commit body.
5. Do not push to remote in MVP.

### 14.6 Rejected Experiment Rollback

If a candidate is rejected and `rollback_rejected_changes: true`, rollback only the candidate changes.

Preferred MVP strategy:

1. Require clean worktree.
2. Apply candidate change.
3. If rejected, use Git checkout/restore to restore changed files.
4. Verify worktree returns to previous expected state.

Rules:

1. Record `rollback_performed: true`.
2. Record rollback method.
3. If rollback fails, stop the run and generate a critical safety warning.
4. Never continue if the worktree is in an unknown state.

### 14.7 Dirty Worktree Policy

Default:

```yaml
require_clean_worktree: true
```

If the worktree is dirty:

1. validation should fail;
2. user should be told to commit, stash, or discard changes;
3. Runner should not proceed.

Advanced future mode may allow dirty worktree support, but MVP should not.

### 14.8 Remote Operations

MVP must not:

```text
git push
create pull request
merge branch
delete remote branch
force push
```

If contract requests these, validation should fail or warn that they are unsupported.

### 14.9 Git Information in Logs

Each experiment log should include:

```json
{
  "git": {
    "enabled": true,
    "branch": "auto-optimize/faq_retrieval-20260606-143000",
    "head_before": "abc123",
    "head_after": "def456",
    "commit_hash": "def456",
    "rollback_performed": false
  }
}
```

### 14.10 Git Tests

Add tests for:

1. clean worktree required;
2. dirty worktree blocks run;
3. accepted experiment creates commit when enabled;
4. rejected experiment restores file content;
5. commit hash is written to log;
6. remote push is not attempted;
7. branch name follows prefix rule.

---

## 15. Experiment Loop

Runner flow:

```text
1. Load contract
2. Validate contract
3. Check Git status
4. Create optimization branch if configured
5. Create output directory
6. Run baseline evaluation
7. Save baseline metrics
8. Generate experiment candidates
9. For each candidate:
   a. record Git checkpoint
   b. apply candidate change
   c. run evaluation
   d. parse metrics
   e. compare with current best / baseline
   f. accept, reject, or add to Pareto frontier
   g. log experiment
   h. rollback rejected changes
   i. commit accepted changes if configured
10. Stop when max experiments reached or no improvement threshold reached
11. Generate report
```

---

## 16. Experiment Planning

MVP planning strategy:

1. Generate candidates from discrete search space values.
2. Prefer one-variable-at-a-time changes first.
3. Then optionally try combinations of accepted promising parameters.
4. Avoid repeating identical experiments.
5. Stop if no improvement for `stop_if_no_improvement_rounds`.

Example:

```text
Round 1: top_k=5
Round 2: top_k=20
Round 3: threshold=0.78
Round 4: threshold=0.86
Round 5: reranker_enabled=true
Round 6: best top_k + best threshold
```

Do not implement advanced optimization in MVP.

---

## 17. Change Application

MVP must support:

- YAML path updates;
- JSON path updates;
- whole-file prompt variant replacement only if declared by adapter or template;
- dry-run diff preview.

For each change, generate:

```json
{
  "parameter": "top_k",
  "file": "configs/retrieval.yaml",
  "path": "retrieval.top_k",
  "before": 10,
  "after": 20
}
```

Never modify files outside `editable_scope`.

Never modify files inside `protected_scope`.

---

## 18. Evaluation

Evaluation command requirements:

- Runs inside `workspace.path`.
- Must return JSON either via stdout or a configured output file.
- Must include the primary metric.
- Should include all secondary and constrained metrics.
- Must complete within `evaluation.timeout_seconds`.

Example JSON output:

```json
{
  "top1_accuracy": 0.892,
  "recall_at_5": 0.934,
  "mrr": 0.781,
  "latency_ms": 720,
  "cost_per_query": 0.008,
  "all_tests_pass": true
}
```

If evaluation fails:

- record the failed experiment;
- reject the change;
- rollback;
- continue unless failure count exceeds a safety threshold.

---

## 19. Decision Engine

MVP decision policies:

### 19.1 `primary_metric_only`

Accept if primary metric improves.

### 19.2 `constrained_primary_metric`

Accept if:

1. primary metric improves by at least `min_primary_improvement`;
2. all constraints are satisfied.

### 19.3 `weighted_score`

Optional for MVP 1.1.

Example:

```yaml
decision_policy:
  mode: weighted_score
  weights:
    top1_accuracy: 0.5
    recall_at_5: 0.3
    latency_ms: -0.1
    cost_per_query: -0.1
```

---

## 20. Pareto Frontier and Solution Classification

Pareto support is important because enterprise systems rarely have one absolute best solution.

A candidate may be worth keeping even if it is not the single accepted best.

### 20.1 Pareto Profiles

Support these profiles:

```text
accuracy_first
balanced
latency_first
cost_first
```

### 20.2 Classification Rules

Suggested MVP rules:

#### Accuracy-first

Highest primary accuracy metric, while not violating hard constraints unless user explicitly allows soft constraints.

#### Balanced

Best weighted score among candidates satisfying all constraints.

#### Latency-first

Lowest latency among candidates whose primary metric is not worse than baseline by more than a configured tolerance.

Example:

```yaml
pareto:
  latency_first:
    min_primary_ratio_to_baseline: 0.98
```

#### Cost-first

Lowest cost among candidates whose primary metric is not worse than baseline by more than a configured tolerance.

Example:

```yaml
pareto:
  cost_first:
    min_primary_ratio_to_baseline: 0.98
```

### 20.3 Pareto Output

Generate:

```text
pareto_solutions.yaml
```

Example:

```yaml
accuracy_first:
  experiment_id: exp_0021
  primary_metric: 0.934
  latency_ms: 1450
  cost_per_query: 0.03

balanced:
  experiment_id: exp_0017
  primary_metric: 0.918
  latency_ms: 760
  cost_per_query: 0.012

latency_first:
  experiment_id: exp_0009
  primary_metric: 0.889
  latency_ms: 390
  cost_per_query: 0.007
```

---

## 21. Experiment Memory and Organizational Learning

Experiment Memory is both an MVP artifact and a future organizational knowledge base.

### 21.1 MVP Memory

For MVP, store experiment memory locally:

```text
auto_optimize_outputs/experiment_log.jsonl
auto_optimize_outputs/learned_knowledge.md
auto_optimize_outputs/run_summary.json
```

It should capture:

```text
what was tried
why it was tried
what changed
metrics before and after
decision
why it succeeded or failed
whether it should be avoided in the future
```

### 21.2 Avoid Repeated Experiments

Runner should avoid repeating identical candidates in the same run.

Use candidate fingerprint:

```text
scenario_type + parameter set + mapped files
```

### 21.3 Learned Knowledge

Reporter should generate a short learned knowledge section.

Example:

```text
- top_k above 20 gave little accuracy gain but increased latency.
- reranker improved MRR significantly in multi-candidate cases.
- threshold above 0.9 caused false negatives.
```

### 21.4 Future Organizational Learning

Future platform version may store experiment memory across projects.

Advisor may then use historical reports to suggest better default search spaces for similar projects.

Do not implement cross-project memory in MVP, but design the local log schema so it can be imported later.

---

## 22. Experiment Log Schema

Use JSONL as the primary experiment log format.

Each line should be one experiment.

```json
{
  "experiment_id": "exp_0007",
  "timestamp": "2026-06-06T14:30:00+09:00",
  "scenario_type": "faq_retrieval",
  "hypothesis": "Increasing top_k may improve recall.",
  "candidate": {
    "top_k": 20
  },
  "changes": [
    {
      "file": "configs/retrieval.yaml",
      "path": "retrieval.top_k",
      "before": 10,
      "after": 20
    }
  ],
  "metrics_before": {
    "top1_accuracy": 0.84,
    "latency_ms": 650
  },
  "metrics_after": {
    "top1_accuracy": 0.846,
    "latency_ms": 930
  },
  "decision": "rejected",
  "reason": "Primary metric improved slightly, but latency increased too much.",
  "constraints_satisfied": false,
  "rollback_performed": true,
  "git": {
    "enabled": true,
    "branch": "auto-optimize/faq_retrieval-20260606-143000",
    "head_before": "abc123",
    "head_after": "abc123",
    "commit_hash": null,
    "rollback_performed": true
  },
  "tags": ["retrieval", "top_k", "low_roi"]
}
```

CSV should be derived from JSONL for readability.

---

## 23. Report Requirements

The reporter must generate a clear report for humans.

Recommended report sections:

```text
1. Executive Summary
2. Baseline vs Final
3. Final Recommended Configuration
4. Optimization Timeline
5. Parameter Impact Ranking
6. Top Successful Experiments
7. Top Failed Experiments
8. Dead-End Analysis
9. Pareto Frontier
10. Git / Version Control Summary
11. Learned Knowledge
12. Risks and Limitations
13. Next Steps
14. Appendix: Full Experiment Log
```

### 23.1 Executive Summary

Should answer:

- How many experiments were run?
- What improved?
- What got worse?
- What is the final recommendation?
- What are the risks?

### 23.2 Git / Version Control Summary

Should include:

```text
original branch
optimization branch
number of accepted commits
number of rejected rollbacks
final HEAD
accepted experiment commit hashes
whether remote push was performed
```

MVP should always report:

```text
remote push: not performed
pull request: not created
```

### 23.3 Parameter Impact Ranking

Summarize which parameters had the largest impact.

Example table:

| Rank | Parameter | Impact | Recommendation |
|---:|---|---:|---|
| 1 | embedding_template | High | Keep title + condition |
| 2 | reranker_enabled | Medium | Use for balanced / accuracy-first |
| 3 | top_k | Low after 20 | Do not increase beyond 20 |

### 23.4 Failure Analysis

Include failed attempts. Failed experiments are not noise; they are knowledge.

Example:

```text
top_k=50 was rejected because recall barely improved while latency increased significantly.
chunk_size=2048 was rejected because semantic noise increased and MRR declined.
```

### 23.5 Pareto Frontier

Show multiple valid recommendations:

```text
Accuracy-first: best score but slower
Balanced: strong score and acceptable latency
Cost-first: lower cost with acceptable accuracy
Latency-first: fastest while preserving acceptable accuracy
```

---

## 24. Safety and Governance Requirements

The system must enforce these rules.

### 24.1 Scope Safety

- Never edit files outside `editable_scope`.
- Never edit files in `protected_scope`.
- Always protect:
  - `.env`
  - `secrets/`
  - `eval/`
  - `test_data/`
  - `benchmark/`
  - production config directories
  - evaluation scripts

### 24.2 Evaluation Integrity

- Do not allow the runner to modify evaluation scripts or golden datasets.
- If evaluation files are in editable scope, validation must fail.
- If evaluation output schema changes between runs, warn and reject the run.

### 24.3 Budget Safety

Respect:

```yaml
run_policy:
  max_experiments
  max_runtime_minutes
  max_cost_usd
```

If not provided, set safe defaults.

### 24.4 Secrets Safety

Never print or store secrets.

If a file path looks like a secret path, block access unless explicitly whitelisted.

### 24.5 Human Approval

For MVP, require user approval before:

- initializing Git;
- saving generated contracts into the project root;
- committing accepted changes if this was not already enabled in contract;
- enabling code modification;
- running more than a safe experiment limit;
- disabling clean worktree requirement.

---

## 25. Scenario Packs

Scenario packs are templates, not core logic.

### 25.1 FAQ Retrieval Pack

Typical search space:

```yaml
search_space:
  top_k:
    values: [5, 10, 20]
  threshold:
    values: [0.78, 0.82, 0.86]
  reranker_enabled:
    values: [false, true]
  embedding_template:
    values:
      - question_only
      - question_with_title
      - question_with_title_and_condition
```

Typical metrics:

```yaml
primary:
  name: top1_accuracy
  direction: maximize
secondary:
  - name: recall_at_5
    direction: maximize
  - name: mrr
    direction: maximize
  - name: false_positive_rate
    direction: minimize
  - name: latency_ms
    direction: minimize
```

### 25.2 RAG Chunking Pack

Typical search space:

```yaml
chunk_size: [256, 512, 768, 1024]
chunk_overlap: [0, 64, 128]
metadata_injection: [none, title, title_section]
reranker_enabled: [false, true]
```

Typical metrics:

```yaml
answer_accuracy
faithfulness
context_precision
recall_at_k
latency_ms
token_cost
```

### 25.3 Prompt Optimization Pack

Typical search space:

```yaml
answer_format:
  - concise
  - structured
  - table_first
  - citation_first
tone:
  - formal
  - concise_professional
  - user_friendly
few_shot_count:
  - 0
  - 2
  - 4
```

Typical metrics:

```yaml
pass_rate
format_compliance
hallucination_rate
groundedness
latency_ms
token_cost
```

### 25.4 Intent Classification Pack

Typical search space:

```yaml
classification_threshold: [0.65, 0.75, 0.85]
top_k_intents: [1, 3, 5]
include_examples: [false, true]
primary_secondary_rule:
  - primary_only
  - primary_secondary
```

Typical metrics:

```yaml
top1_accuracy
top3_recall
macro_f1
false_positive_rate
confusion_rate
unknown_intent_rate
```

### 25.5 Memory Retrieval Pack

Typical search space:

```yaml
recent_window_turns: [4, 6, 8]
summary_length: [short, medium, long]
retrieval_threshold: [0.65, 0.75, 0.85]
memory_top_k: [3, 5, 8]
```

Typical metrics:

```yaml
context_resolution_accuracy
unnecessary_retrieval_rate
missed_reference_rate
latency_ms
token_cost
```

---

## 26. Adapter Strategy

Use three levels of extensibility.

### 26.1 Level 1: Declarative Contract

MVP only needs this.

Users define:

- search space;
- mapping;
- evaluation command;
- metrics;
- constraints.

No custom code required.

### 26.2 Level 2: Script Adapter

Later support scripts:

```yaml
adapter:
  type: script
  propose_experiments: "adapters/faq/propose.py"
  apply_change: "adapters/faq/apply.py"
  parse_metrics: "adapters/faq/parse.py"
  explain_result: "adapters/faq/explain.py"
```

### 26.3 Level 3: Full Plugin Interface

Future:

```python
class OptimizationScenario:
    def validate_workspace(self, workspace): ...
    def get_search_space(self): ...
    def propose_experiments(self, history, budget): ...
    def apply_experiment(self, proposal, workspace): ...
    def run_evaluation(self, workspace): ...
    def parse_metrics(self, raw_output): ...
    def compare(self, baseline, candidate): ...
    def explain_result(self, experiment, metrics): ...
    def generate_report_sections(self, history): ...
```

Do not implement Level 3 in MVP.

---

## 27. Advisor Mode Details

Advisor should produce:

1. Readiness Assessment
2. Optimization Opportunities
3. Recommended Search Space
4. Suggested Evaluation Metrics
5. Draft Contract
6. Risk Warnings

### 27.1 Readiness Score

Example:

```text
Optimization Readiness Score: 72/100

Ready:
- evaluation command exists
- baseline metrics available
- config files are editable

Missing:
- protected_scope not defined
- cost constraint not defined
- evaluation output lacks latency_ms
```

### 27.2 Opportunity Ranking

Example:

```text
Priority 1: Embedding Template
Reason: FAQ questions are short; title and applicable condition may improve semantic matching.

Priority 2: Direct-hit Threshold
Reason: Threshold controls false positives and false negatives.

Priority 3: Reranker
Reason: Multi-candidate conflicts need second-stage ranking.
```

---

## 28. `SKILL.md` Content Requirements

Create a `SKILL.md` that tells Codex how to use the skill.

It should include:

1. When to use this skill.
2. When not to use this skill.
3. Modes:
   - Advisor
   - Guided
   - Template
   - Expert
4. Required artifacts:
   - `optimization.contract.yaml`
   - `experiment_log.jsonl`
5. Safety rules.
6. Git / version control rules.
7. Recommended workflow.
8. CLI commands.
9. Output files.
10. Stop conditions.
11. Human approval requirements.

Suggested `SKILL.md` structure:

```markdown
---
name: auto-optimize
description: Diagnose optimization opportunities, build optimization contracts, run safe experiment loops, compare metrics, manage Git checkpoints, keep better changes, reject worse changes, and generate optimization reports for project components.
---

# AutoOptimize Skill

## When to use

Use this skill when the user wants to improve a project component through controlled experiments based on measurable evaluation results.

## Modes

- Advisor Mode: read-only diagnosis.
- Guided Mode: collect required info and build a contract.
- Template Mode: use a scenario template.
- Expert Mode: run from a complete contract.

## Safety Rules

Never modify protected files.
Never modify eval scripts or golden datasets.
Never access secrets.
Require contract validation before running.
Require clean Git worktree by default.
Require user approval before committing changes unless enabled in contract.

## Git Rules

Use a new optimization branch when configured.
Create checkpoints before each experiment.
Commit accepted experiments if configured.
Rollback rejected experiments.
Never push or create PRs in MVP.

## Workflow

1. If no contract exists, use Advisor or Guided mode.
2. Generate or load `optimization.contract.yaml`.
3. Validate the contract.
4. Check Git state.
5. Run baseline evaluation.
6. Run experiments.
7. Accept or reject changes.
8. Generate logs and report.

## CLI

...
```

---

## 29. Testing Requirements

Write tests for:

### 29.1 Contract Validation

- missing workspace;
- missing primary metric;
- protected/editable conflict;
- invalid mapping file;
- invalid YAML path;
- empty search space;
- unsupported remote Git operations;
- dirty Git worktree when clean worktree is required.

### 29.2 Modifier

- updates YAML path correctly;
- updates JSON path correctly;
- refuses protected file changes;
- creates diff summary.

### 29.3 Evaluation Parser

- parses valid JSON output;
- detects missing primary metric;
- handles command failure;
- handles timeout.

### 29.4 Decision Engine

- accepts improved primary metric;
- rejects worse metric;
- rejects constraint violation;
- handles metric direction correctly.

### 29.5 Git Strategy

- detects clean worktree;
- blocks dirty worktree;
- creates optimization branch;
- commits accepted experiment;
- rolls back rejected experiment;
- records commit hash;
- does not push remote;
- stops on rollback failure.

### 29.6 Rollback

- rejected experiment restores previous content;
- accepted experiment remains;
- logs rollback status.

### 29.7 Reporter

- generates Markdown report;
- generates HTML report;
- includes success and failure experiments;
- includes final recommendation;
- includes Pareto solutions;
- includes Git summary;
- includes appendix.

---

## 30. Implementation Order

Recommended order for Codex:

### Phase 1: Skeleton

1. Create repository structure.
2. Create `SKILL.md`.
3. Create CLI skeleton.
4. Add schema models.

### Phase 2: Contract Validation

1. Implement loader.
2. Implement validator.
3. Add tests.

### Phase 3: Git Foundation

1. Implement Git status checker.
2. Implement clean worktree validation.
3. Implement branch creation.
4. Implement checkpoint capture.
5. Add tests.

### Phase 4: Modifier + Evaluation Runner

1. Implement YAML path update.
2. Implement JSON path update.
3. Implement command runner.
4. Implement metric parser.
5. Add tests.

### Phase 5: Experiment Runner

1. Implement baseline run.
2. Implement candidate generation.
3. Implement accept/reject.
4. Implement rollback.
5. Implement optional commit.
6. Implement JSONL logging.

### Phase 6: Reporter

1. Implement Markdown report.
2. Implement HTML report.
3. Implement CSV export.
4. Implement Git summary.
5. Add sample output.

### Phase 7: Scenario Templates

1. Add FAQ template.
2. Add RAG template.
3. Add Prompt template.
4. Add Intent template.
5. Add Memory template.

### Phase 8: Advisor

1. Implement readiness checker.
2. Implement basic scenario recommendations.
3. Generate draft contract.
4. Add tests.

---

## 31. Definition of Done

The skill is acceptable when:

1. `SKILL.md` exists and clearly describes when the skill should trigger.
2. `python -m auto_optimize.cli validate examples/faq_retrieval/optimization.contract.yaml` works.
3. `python -m auto_optimize.cli run examples/faq_retrieval/optimization.contract.yaml` runs against a sample project.
4. It creates:
   - `experiment_log.jsonl`
   - `experiment_log.csv`
   - `run_summary.json`
   - `pareto_solutions.yaml`
   - `optimization_report.md`
   - `optimization_report.html`
5. Git clean worktree validation works.
6. Optimization branch creation works when configured.
7. Accepted experiments can be committed when configured.
8. Rejected experiments are rolled back.
9. Commit hashes are recorded in the experiment log.
10. Protected files cannot be modified.
11. Evaluation scripts and golden datasets cannot be modified.
12. Reports include successful and failed experiments.
13. Reports include Git summary.
14. Tests pass.
15. README explains how to run Advisor, Validate, Run, and Report modes.

---

## 32. Important Non-Goals

Do not build:

- web UI;
- cloud deployment;
- multi-user auth;
- production deployment automation;
- advanced AutoML;
- arbitrary code transformation;
- secret management system;
- long-running distributed scheduler;
- remote Git push;
- pull request creation;
- automatic merge.

These can be future platform features. The MVP should remain a safe, local, contract-driven skill.

---

## 33. Final Architecture Summary

Final recommended architecture:

```text
AutoOptimize Skill Suite
│
├── Entry Layer
│   ├── Advisor Mode
│   ├── Guided Mode
│   ├── Template Mode
│   └── Expert Mode
│
├── Contract Layer
│   ├── Scenario Contract
│   ├── Contract Validator
│   └── Guided Contract Builder
│
├── Adapter / Template Layer
│   ├── Scenario Templates
│   └── Future Script / Plugin Adapters
│
├── Optimization Core
│   ├── Planner
│   ├── Modifier
│   ├── Executor
│   ├── Evaluator
│   ├── Decision Engine
│   ├── Git / Version Manager
│   ├── Experiment Store
│   └── Pareto Manager
│
├── Safety Layer
│   ├── Scope Guard
│   ├── Secret Guard
│   ├── Budget Guard
│   └── Evaluation Integrity Guard
│
└── Report Layer
    ├── Markdown Report
    ├── HTML Report
    ├── CSV Export
    ├── JSONL Experiment Log
    └── Git Summary
```

The most important implementation principle:

> All modes must converge to `optimization.contract.yaml`, and all scenarios must run through the same safe optimization core.

The most important safety principle:

> AI can modify candidate solutions only inside the approved editable scope. It must never modify the evaluation judge, golden dataset, secrets, or protected files.

The most important Git principle:

> Require a clean worktree by default, use an optimization branch, commit accepted experiments only when configured, and rollback rejected experiments safely.
