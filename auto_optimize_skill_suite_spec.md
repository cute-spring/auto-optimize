# AutoOptimize Skill Suite — Codex Implementation Specification

> Version: v0.1  
> Target reader: Codex / coding agent  
> Purpose: Create a reusable Skill Suite that helps users diagnose optimization opportunities, build an optimization contract, run controlled experiment loops, and generate readable reports.

---

## 1. Executive Summary

Create an **AutoOptimize Skill Suite** rather than one large monolithic skill.

The suite should help a user improve a project component by:

1. diagnosing what is worth optimizing;
2. helping the user build a safe `optimization.contract.yaml`;
3. running controlled experiments inside the allowed scope;
4. accepting better changes and rejecting worse changes;
5. logging all successful and failed attempts;
6. producing a final human-readable optimization report.

The conceptual inspiration is an AutoResearch-style loop:

```text
hypothesis
→ candidate change
→ run evaluation
→ compare metrics
→ accept / reject
→ record learning
→ repeat
→ report
```

However, this implementation should be enterprise-safe and scenario-agnostic. The core must **not** hard-code FAQ, RAG, Prompt, Intent, or Memory logic. Scenario-specific differences should be isolated through contracts, templates, and adapters.

---

## 2. Recommended Product Shape

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

## 3. Skill Identity

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
description: Diagnose optimization opportunities, build an optimization contract, run controlled experiment loops, compare evaluation metrics, keep better changes, reject worse changes, and generate optimization reports for project components such as RAG, FAQ retrieval, prompts, intent classification, memory retrieval, or performance tuning.
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

---

## 4. Core Design Principle

The main design rule is:

> Keep the optimization engine generic. Put scenario-specific logic into `Scenario Contract`, `Scenario Template`, or `Scenario Adapter`.

The core should know how to:

```text
load contract
validate boundaries
run baseline
propose or load experiments
apply candidate changes
run evaluation command
parse metrics
decide accept / reject
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

## 5. Modes

The suite should support four modes.

### 5.1 Advisor Mode

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
optimization_advice.md
optimization.contract.draft.yaml
readiness_report.json
```

---

### 5.2 Guided Mode

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

Guided Mode should not ask 20 questions at once.

It should eventually generate:

```text
optimization.contract.yaml
```

Then ask user confirmation before running.

---

### 5.3 Template Mode

Purpose:

> Let semi-expert users start from a scenario template.

Examples:

```text
Use FAQ Retrieval template
Use RAG Chunking template
Use Prompt Optimization template
Use Intent Classification template
```

Template Mode should load a scenario template, ask only for missing fields, validate the contract, then optionally run optimization.

---

### 5.4 Expert Mode

Purpose:

> Let expert users provide a complete `optimization.contract.yaml` and run directly.

Flow:

```text
load contract
→ validate contract
→ run baseline
→ execute optimization loop
→ produce logs and reports
```

Expert Mode should still enforce all safety policies.

---

## 6. Unified Entry Flow

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

This is important. Avoid separate execution flows for each mode.

---

## 7. Primary Artifact: `optimization.contract.yaml`

The contract is the central interface between the user, scenario packs, and the optimization engine.

### 7.1 MVP Contract Example

```yaml
schema_version: "0.1"

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

run_policy:
  max_experiments: 30
  stop_if_no_improvement_rounds: 8
  random_seed: 42
  dry_run: false

version_control:
  enabled: true
  commit_accepted_changes: true
  rollback_rejected_changes: true
  branch_prefix: "auto-optimize/"

report:
  formats:
    - html
    - markdown
    - csv
    - json
  output_dir: "auto_optimize_outputs"
```

---

## 8. Contract Validation Requirements

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

If validation fails, do not start optimization. Generate a clear validation report.

---

## 9. MVP Scope

### 9.1 MVP Should Support

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
- log all experiments;
- generate Markdown and HTML reports;
- generate CSV and JSONL experiment logs.

### 9.2 MVP Should Not Support Yet

Do not implement in MVP:

- arbitrary code rewriting;
- complex multi-agent planning;
- automatic production deployment;
- web dashboard;
- long-running distributed job queue;
- advanced Bayesian optimization;
- full plugin packaging system;
- LLM-as-judge scoring unless user already provides evaluation command.

The MVP should be boring, safe, and reliable.

---

## 10. Recommended Repository Structure

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
    ├── test_pareto.py
    ├── test_report_generator.py
    └── fixtures/
```

---

## 11. CLI Requirements

Provide a CLI to make the skill easy for Codex to invoke.

Suggested commands:

```bash
python -m auto_optimize.cli advisor --workspace ./project
python -m auto_optimize.cli validate optimization.contract.yaml
python -m auto_optimize.cli run optimization.contract.yaml
python -m auto_optimize.cli report auto_optimize_outputs/experiment_log.jsonl
```

### 11.1 `advisor`

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

### 11.2 `validate`

Example:

```bash
python -m auto_optimize.cli validate optimization.contract.yaml
```

Outputs:

```text
auto_optimize_outputs/contract_validation_report.md
```

### 11.3 `run`

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

### 11.4 `report`

Example:

```bash
python -m auto_optimize.cli report auto_optimize_outputs/experiment_log.jsonl
```

Outputs a new report without rerunning experiments.

---

## 12. Experiment Loop

Runner flow:

```text
1. Load contract
2. Validate contract
3. Create output directory
4. Run baseline evaluation
5. Save baseline metrics
6. Generate experiment candidates
7. For each candidate:
   a. create checkpoint
   b. apply candidate change
   c. run evaluation
   d. parse metrics
   e. compare with current best / baseline
   f. accept, reject, or add to Pareto frontier
   g. log experiment
   h. rollback rejected changes
   i. commit accepted changes if configured
8. Stop when max experiments reached or no improvement threshold reached
9. Generate report
```

---

## 13. Experiment Planning

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

## 14. Change Application

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

## 15. Evaluation

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

## 16. Decision Engine

MVP decision policies:

### 16.1 `primary_metric_only`

Accept if primary metric improves.

### 16.2 `constrained_primary_metric`

Accept if:

1. primary metric improves by at least `min_primary_improvement`;
2. all constraints are satisfied.

### 16.3 `weighted_score`

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

### 16.4 Pareto Handling

Even if a candidate is not globally accepted, it may be kept as a Pareto solution if it offers a useful tradeoff.

Examples:

- accuracy-first;
- balanced;
- cost-first;
- latency-first.

---

## 17. Experiment Log Schema

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
  "commit_hash": null,
  "tags": ["retrieval", "top_k", "low_roi"]
}
```

CSV should be derived from JSONL for readability.

---

## 18. Report Requirements

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
10. Learned Knowledge
11. Risks and Limitations
12. Next Steps
13. Appendix: Full Experiment Log
```

### 18.1 Executive Summary

Should answer:

- How many experiments were run?
- What improved?
- What got worse?
- What is the final recommendation?
- What are the risks?

### 18.2 Parameter Impact Ranking

Summarize which parameters had the largest impact.

Example table:

| Rank | Parameter | Impact | Recommendation |
|---:|---|---:|---|
| 1 | embedding_template | High | Keep title + condition |
| 2 | reranker_enabled | Medium | Use for balanced / accuracy-first |
| 3 | top_k | Low after 20 | Do not increase beyond 20 |

### 18.3 Failure Analysis

Include failed attempts. Failed experiments are not noise; they are knowledge.

Example:

```text
top_k=50 was rejected because recall barely improved while latency increased significantly.
chunk_size=2048 was rejected because semantic noise increased and MRR declined.
```

### 18.4 Pareto Frontier

Show multiple valid recommendations:

```text
Accuracy-first: best score but slower
Balanced: strong score and acceptable latency
Cost-first: lower cost with acceptable accuracy
```

---

## 19. Safety and Governance Requirements

The system must enforce these rules.

### 19.1 Scope Safety

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

### 19.2 Evaluation Integrity

- Do not allow the runner to modify evaluation scripts or golden datasets.
- If evaluation files are in editable scope, validation must fail.
- If evaluation output schema changes between runs, warn and reject the run.

### 19.3 Budget Safety

Respect:

```yaml
run_policy:
  max_experiments
  max_runtime_minutes
  max_cost_usd
```

If not provided, set safe defaults.

### 19.4 Secrets Safety

Never print or store secrets.

If a file path looks like a secret path, block access unless explicitly whitelisted.

### 19.5 Human Approval

For MVP, require user approval before:

- initializing Git;
- committing accepted changes;
- writing generated contract to project root;
- enabling code modification;
- running more than a safe experiment limit.

---

## 20. Scenario Packs

Scenario packs are templates, not core logic.

### 20.1 FAQ Retrieval Pack

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

### 20.2 RAG Chunking Pack

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

### 20.3 Prompt Optimization Pack

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

### 20.4 Intent Classification Pack

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

### 20.5 Memory Retrieval Pack

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

## 21. Adapter Strategy

Use three levels of extensibility.

### 21.1 Level 1: Declarative Contract

MVP only needs this.

Users define:

- search space;
- mapping;
- evaluation command;
- metrics;
- constraints.

No custom code required.

### 21.2 Level 2: Script Adapter

Later support scripts:

```yaml
adapter:
  type: script
  propose_experiments: "adapters/faq/propose.py"
  apply_change: "adapters/faq/apply.py"
  parse_metrics: "adapters/faq/parse.py"
  explain_result: "adapters/faq/explain.py"
```

### 21.3 Level 3: Full Plugin Interface

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

## 22. Advisor Mode Details

Advisor should produce:

1. Readiness Assessment
2. Optimization Opportunities
3. Recommended Search Space
4. Suggested Evaluation Metrics
5. Draft Contract
6. Risk Warnings

### 22.1 Readiness Score

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

### 22.2 Opportunity Ranking

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

## 23. `SKILL.md` Content Requirements

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
6. Recommended workflow.
7. CLI commands.
8. Output files.
9. Stop conditions.
10. Human approval requirements.

Suggested `SKILL.md` structure:

```markdown
---
name: auto-optimize
description: Diagnose optimization opportunities, build optimization contracts, run safe experiment loops, compare metrics, keep better changes, reject worse changes, and generate optimization reports for project components.
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
Require user approval before committing changes.

## Workflow

1. If no contract exists, use Advisor or Guided mode.
2. Generate or load `optimization.contract.yaml`.
3. Validate the contract.
4. Run baseline evaluation.
5. Run experiments.
6. Accept or reject changes.
7. Generate logs and report.

## CLI

...
```

---

## 24. Testing Requirements

Write tests for:

### 24.1 Contract Validation

- missing workspace;
- missing primary metric;
- protected/editable conflict;
- invalid mapping file;
- invalid YAML path;
- empty search space.

### 24.2 Modifier

- updates YAML path correctly;
- updates JSON path correctly;
- refuses protected file changes;
- creates diff summary.

### 24.3 Evaluation Parser

- parses valid JSON output;
- detects missing primary metric;
- handles command failure;
- handles timeout.

### 24.4 Decision Engine

- accepts improved primary metric;
- rejects worse metric;
- rejects constraint violation;
- handles metric direction correctly.

### 24.5 Rollback

- rejected experiment restores previous content;
- accepted experiment remains;
- logs rollback status.

### 24.6 Reporter

- generates Markdown report;
- generates HTML report;
- includes success and failure experiments;
- includes final recommendation;
- includes appendix.

---

## 25. Implementation Order

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

### Phase 3: Modifier + Evaluation Runner

1. Implement YAML path update.
2. Implement JSON path update.
3. Implement command runner.
4. Implement metric parser.
5. Add tests.

### Phase 4: Experiment Runner

1. Implement baseline run.
2. Implement candidate generation.
3. Implement accept/reject.
4. Implement rollback.
5. Implement JSONL logging.

### Phase 5: Reporter

1. Implement Markdown report.
2. Implement HTML report.
3. Implement CSV export.
4. Add sample output.

### Phase 6: Scenario Templates

1. Add FAQ template.
2. Add RAG template.
3. Add Prompt template.
4. Add Intent template.
5. Add Memory template.

### Phase 7: Advisor

1. Implement readiness checker.
2. Implement basic scenario recommendations.
3. Generate draft contract.
4. Add tests.

---

## 26. Definition of Done

The skill is acceptable when:

1. `SKILL.md` exists and clearly describes when the skill should trigger.
2. `python -m auto_optimize.cli validate examples/faq_retrieval/optimization.contract.yaml` works.
3. `python -m auto_optimize.cli run examples/faq_retrieval/optimization.contract.yaml` runs against a sample project.
4. It creates:
   - `experiment_log.jsonl`
   - `experiment_log.csv`
   - `run_summary.json`
   - `optimization_report.md`
   - `optimization_report.html`
5. Rejected experiments are rolled back.
6. Accepted experiments are recorded.
7. Protected files cannot be modified.
8. Reports include both successful and failed experiments.
9. Tests pass.
10. README explains how to run Advisor, Validate, Run, and Report modes.

---

## 27. Important Non-Goals

Do not build:

- web UI;
- cloud deployment;
- multi-user auth;
- production deployment automation;
- advanced AutoML;
- arbitrary code transformation;
- secret management system;
- long-running distributed scheduler.

These can be future platform features. The MVP should remain a safe, local, contract-driven skill.

---

## 28. Final Architecture Summary

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
│   ├── Version Manager
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
    └── JSONL Experiment Log
```

The most important implementation principle:

> All modes must converge to `optimization.contract.yaml`, and all scenarios must run through the same safe optimization core.

This keeps the suite extensible, testable, safe, and understandable.
