# AutoOptimize Skill Improvement Roadmap

This roadmap records the next product-oriented improvement plan for AutoOptimize. The goal is not to expand the system for its own sake. The goal is to make the skill easier to start, easier to configure, easier to connect to real user evaluation, and easier to trust after it produces results.

## Product Goal

AutoOptimize should help a user complete this workflow:

1. Describe or inspect a workspace.
2. Generate or author a safe optimization contract.
3. Validate the contract and evaluation setup.
4. Run bounded optimization inside the declared safety scope.
5. Understand whether the result should be adopted, reviewed, or rejected.

The next round should therefore prioritize usability, clarity, evaluation integration, and trust before adding more datasets, providers, or advanced search algorithms.

## Guiding Principles

- Prefer task-oriented workflows over feature inventories.
- Treat public datasets as validation fixtures, not the core product.
- Make the smallest useful contract easy to write and explain.
- Make evaluation integration explicit, testable, and safe.
- Make reports answer user decision questions, not only list artifacts.
- Keep optimization strategies explainable before making them more complex.

## Milestone 1: User Onboarding

### Goal

A new user should be able to understand and run a minimal optimization flow in about ten minutes without reading the full specification.

### Scope

- Write a quickstart that follows the shortest useful path: `advisor -> validate -> run -> report`.
- Add a command guide that explains when to use `advisor`, `guided`, `build`, `template`, `validate`, `run`, and `report`.
- Add walkthroughs for the most common entry points:
  - FAQ configuration optimization.
  - Embedding or reranking benchmark optimization.
  - Custom evaluation script integration.
- Explain expected inputs, commands, generated outputs, and success criteria for each walkthrough.
- Reframe docs around user tasks instead of internal modules.
- Add an examples index explaining which example to choose for each scenario.

### Suggested Deliverables

- `docs/quickstart.md`
- `docs/command-guide.md`
- `docs/walkthrough-faq.md`
- `docs/walkthrough-custom-eval.md`
- `examples/README.md`

### Acceptance Criteria

- A user can run the FAQ example without reading the skill spec.
- The user can identify the right command for their current stage.
- Each walkthrough answers: what to prepare, what to run, and what to inspect.
- The generated outputs are named and explained in plain language.

## Milestone 2: Contract UX

### Goal

A user should be able to generate, inspect, and fix a contract without understanding every field in the full contract schema.

### Scope

- Define a minimal contract shape with only the fields required to start safely.
- Define an expanded contract view showing defaults and derived values.
- Improve contract builder behavior:
  - Infer editable files from known config locations when safe.
  - Infer evaluation command candidates from workspace layout.
  - Recommend metric profile based on scenario.
  - Suggest reasonable budgets from search space size.
- Improve validation messages:
  - Include the contract field or path involved.
  - Explain why the rule exists.
  - Give a concrete remediation suggestion.
- Add an `explain contract` flow or report that describes each section and marks defaults.
- Add minimal contract examples for FAQ, benchmark, and custom eval scenarios.

### Suggested Deliverables

- `docs/contract-authoring.md`
- `docs/contract-fields.md`
- `examples/contracts/minimal_faq.contract.yaml`
- `examples/contracts/minimal_custom_eval.contract.yaml`
- CLI: `build` improvements.
- CLI: `explain-contract` or equivalent report output.

### Acceptance Criteria

- A generated minimal contract can validate without manual schema knowledge.
- Validation failures are actionable, not just descriptive.
- Builder-generated contracts are safe by default.
- A user can identify the five most important contract sections: workspace, editable scope, protected scope, search space, and metrics.

## Milestone 3: Eval Integration

### Goal

A user should be able to connect their own evaluation script safely and verify that it behaves correctly before running optimization.

### Scope

- Define the evaluation protocol:
  - Where the eval reads configuration and data from.
  - Which output formats are supported.
  - Which metrics are required.
  - How exit codes and failures are interpreted.
- Support common output formats:
  - `metrics.json`
  - stdout JSON
  - CSV results plus a metrics summary.
- Add a smoke-eval command that runs evaluation without modifying any editable files.
- Validate eval output schema:
  - Primary metric exists.
  - Metric values are numeric when expected.
  - Latency, size, and cost metrics use consistent units.
- Add optional stability checks:
  - Run the same eval two or three times.
  - Report metric variance.
  - Warn when evaluation is too noisy for optimization.
- Provide eval templates:
  - Generic Python eval script.
  - Retrieval eval script.
  - Reranking eval script.
  - Generic config optimization eval script.
- Strengthen eval safety:
  - Eval files remain in protected scope.
  - Eval output writes only to allowed output locations.
  - Eval does not mutate protected inputs.

### Suggested Deliverables

- `docs/eval-protocol.md`
- `docs/eval-templates.md`
- `examples/eval_templates/`
- CLI: `smoke-eval`
- Validator support for eval output schema checks.
- Report section for eval stability.

### Acceptance Criteria

- A user can adapt a template into their own eval script.
- `smoke-eval` can detect missing or malformed metrics before optimization starts.
- Validation can flag eval protocol problems with remediation advice.
- Reports can warn when evaluation is too unstable to support a confident recommendation.

## Milestone 4: Trustworthy Reports

### Goal

A user should be able to read the report and decide whether to adopt the optimized result, review it manually, or reject it.

### Scope

- Strengthen baseline versus best comparison:
  - Metric deltas.
  - Changed parameters.
  - File diff summary.
  - Constraint status.
- Add an experiment decision table:
  - Candidate id.
  - Changed parameters.
  - Result metrics.
  - Accepted or rejected status.
  - Decision reason.
- Add risk flags:
  - Sample size appears too small.
  - Primary metric improved but latency, size, or cost worsened.
  - Metric variance is high.
  - Best result only slightly improves on baseline.
  - A rejected candidate performs better on an important secondary metric.
- Add final recommendation levels:
  - `adopt`
  - `review_manually`
  - `do_not_adopt`
- Add profile-based summaries:
  - FAQ profile highlights top-1 accuracy, hit rate, and hard-negative behavior.
  - Embedding profile highlights recall, nDCG, latency, and index size.
  - Reranking profile highlights MRR, rerank gain, and reranking latency.
- Add a machine-readable report schema for CI and other agents.

### Suggested Deliverables

- `docs/reporting.md`
- `auto_optimize_outputs/optimization_report.md`
- `auto_optimize_outputs/optimization_report.json`
- Report section: Baseline vs Best.
- Report section: Experiment Decisions.
- Report section: Risk Flags.
- Report section: Final Recommendation.

### Acceptance Criteria

- The report explains why the final result was selected.
- The report identifies meaningful risks and tradeoffs.
- The user can understand the optimization process without reading JSONL logs.
- Another agent or CI job can consume the structured report.

## Milestone 5: Practical Optimization

### Goal

Optimization should become more stable, less wasteful, and easier to explain before adding heavyweight search algorithms.

### Scope

- Add strategy recommendation:
  - Use search space size, budget, and metric profile to recommend a strategy.
  - Suggest parameter priority when the scenario is known.
- Add candidate deduplication:
  - Skip combinations already tried in prior runs.
  - Skip candidates equivalent to the current configuration.
- Add early stopping:
  - Stop after repeated non-improvements.
  - Stop or deprioritize candidate families that violate latency, size, or cost constraints.
- Add budget-aware planning:
  - Estimate experiment count.
  - Estimate total evaluation time when possible.
  - Prune or rank candidates when the plan exceeds budget.
- Add memory-aware search:
  - Use prior run history to avoid repeated failures.
  - Prefer historically promising parameter ranges.
- Add explainable planning:
  - Record why each candidate was generated.
  - Report the search strategy, pruning decisions, and stop reason.

### Suggested Deliverables

- `docs/search-strategies.md`
- Planner support for strategy recommendation.
- Planner support for candidate deduplication.
- Planner support for budget-aware pruning.
- Runner support for early stopping.
- Report section: Search Plan and Stop Reason.

### Acceptance Criteria

- A run can estimate how many experiments it plans to execute.
- The optimizer avoids obvious duplicate trials.
- Budget limits affect planning before the run blindly spends the budget.
- The report explains both what was tried and why the run stopped.
- The default strategy remains suitable for new users.

## Recommended Execution Order

1. User Onboarding.
2. Contract UX.
3. Eval Integration.
4. Trustworthy Reports.
5. Practical Optimization.

This order is intentional: first make the skill understandable, then make contracts easier, then make user evals easy to connect, then make results trustworthy, and only then make optimization more sophisticated.

## First Execution Slice

The first implementation slice should stay small and high-impact:

- Add `docs/quickstart.md`.
- Add `docs/command-guide.md`.
- Add `docs/contract-authoring.md`.
- Add `docs/eval-protocol.md`.
- Improve validation report remediation guidance.
- Add a `smoke-eval` CLI command.

This slice directly improves usability without introducing a large new algorithmic surface area.
