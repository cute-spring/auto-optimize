# 项目状态审核与进度分析报告 (2026-06-07)

## 1. 审核概览

本次审计基于当前项目方向基线 [docs/skill-improvement-roadmap.md](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/docs/skill-improvement-roadmap.md:1)，并对照当前实现、CLI 能力、测试状态与文档一致性进行评估。

### 核心结论

- 项目已经完成“方向纠偏”并落地了第一段可执行的声明优先链路，最关键的成果是 `declare` 命令、声明模型、声明校验、声明转可执行 contract，以及端到端测试闭环，见 [auto_optimize/cli.py](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/auto_optimize/cli.py:17)、[auto_optimize/declaration/loader.py](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/auto_optimize/declaration/loader.py:149)、[auto_optimize/declaration/converter.py](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/auto_optimize/declaration/converter.py:82)、[tests/test_declaration_command.py](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/tests/test_declaration_command.py:16)。
- 现阶段已经不是“只有方向没有代码”，但距离“真正通用、低心智负担的 declaration-driven skill”仍有明显 gap，尤其在动态适配器生成、去场景化改造、guided declaration builder、报告可审计性增强这四块。
- 当前实现最主要的结构性偏差是：执行内核已经相当完整，但 `advisor` / `build` / `guided` 仍建立在静态 scenario 推断和模板拼装上，和 roadmap 的产品方向不一致，见 [auto_optimize/advisor/service.py](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/auto_optimize/advisor/service.py:28) 与 [auto_optimize/builder/service.py](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/auto_optimize/builder/service.py:27)。
- 工程质量层面状态健康。当前测试套件 `58 passed`，说明现有 MVP 内核和本次 declaration slice 已有较好回归保护。

### 审计结论摘要

- 当前总体完成度：约 `58%`
- 距离“声明优先、通用可用”的下一目标状态：约 `42%` gap
- 剩余工作量：约 `10-16` 个聚焦工程日
- 若只追求“下一个可信里程碑”而不是“完整愿景”，剩余工作量约 `4-6` 个工程日

## 2. 计划执行审计

| 计划项 | 状态 | 审计说明 |
| :--- | :--- | :--- |
| Milestone 1: Direction Realignment | ✅ | 已完成。README、SKILL、quickstart、architecture、examples 都已改写为 declaration-first 叙事，见 [README.md](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/README.md:1)、[SKILL.md](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/SKILL.md:1)、[docs/quickstart.md](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/docs/quickstart.md:1)。 |
| Milestone 2: Declaration Protocol | 🟡 | 已完成“定义 + 第一段可执行转换”，但尚未完成“guided conversation 生成 declaration”与“从 existing contract 派生 declaration”。声明当前只支持一部分可执行子集，见 [docs/declaration-protocol.md](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/docs/declaration-protocol.md:1)、[auto_optimize/declaration/converter.py](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/auto_optimize/declaration/converter.py:12)。 |
| Milestone 3: Dynamic Adapter Generation | ❌ | 基本未实现。`adapter_generation` 目前只被保存在 `declaration_context` 中，并没有生成临时代码、没有写入 `generated_adapters/`、也没有执行链路，见 [auto_optimize/declaration/converter.py](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/auto_optimize/declaration/converter.py:176)。 |
| Milestone 4: Generic Execution Loop | 🟡 | 执行器、验证、回滚、报告、memory、可选 Git 已存在，属于“超额完成”的底座；但 evaluation 仍只支持 JSON 输出，且上层 workspace 进入方式仍受 scenario 逻辑影响，见 [auto_optimize/runner/orchestrator.py](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/auto_optimize/runner/orchestrator.py:1)、[auto_optimize/runner/evaluator.py](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/auto_optimize/runner/evaluator.py:16)。 |
| Milestone 5: Usability And Trust | 🟡 | quickstart、validate、explain、报告已有基础能力，但 guided declaration builder、generated-code summary、risk flags、发布质量门都未完成，见 [auto_optimize/reporting/report_generator.py](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/auto_optimize/reporting/report_generator.py:25) 和缺失的 `docs/release_readiness_gate/`。 |

## 3. 详细进展判断

### 已完成或超额完成的部分

- 文档方向重构已经完成，且一致性总体较好。roadmap 中要求的“文档先转向 generic declaration-driven skill”已经兑现，见 [docs/skill-improvement-roadmap.md](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/docs/skill-improvement-roadmap.md:25)。
- 声明到 contract 的第一条可执行通路已经打通：
  - CLI 新增 `declare` 命令，见 [auto_optimize/cli.py](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/auto_optimize/cli.py:52) 和 [auto_optimize/cli.py](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/auto_optimize/cli.py:210)。
  - 声明结构化加载与必填校验已实现，见 [auto_optimize/declaration/loader.py](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/auto_optimize/declaration/loader.py:149)。
  - 泛化字段映射到现有 executable contract 已实现，见 [auto_optimize/declaration/converter.py](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/auto_optimize/declaration/converter.py:120)。
  - 新增泛型声明示例，见 [examples/declarations/generic_config_optimization.declaration.yaml](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/examples/declarations/generic_config_optimization.declaration.yaml:1)。
- 执行内核比 roadmap 中“下一步想做什么”更成熟。当前已经具备 baseline eval、候选生成、文件修改、回滚、报告、memory 和可选 Git 能力，见 [auto_optimize/runner/orchestrator.py](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/auto_optimize/runner/orchestrator.py:1)。
- 回归保护较好。本次审计时全量测试为 `58 passed`，并且新增 declaration slice 有独立测试覆盖，见 [tests/test_declaration_command.py](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/tests/test_declaration_command.py:177)。

### 尚未完成的关键缺口

- 动态适配器生成未落地。
  - roadmap 明确要求生成 eval wrapper、metrics parser、config mutator 等临时代码，见 [docs/skill-improvement-roadmap.md](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/docs/skill-improvement-roadmap.md:72)。
  - 当前实现仅在 `declaration_context` 记录 `adapter_generation`，没有真正生成或执行任何 adapter，见 [auto_optimize/declaration/converter.py](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/auto_optimize/declaration/converter.py:176)。
- 声明协议的可执行覆盖面仍偏窄。
  - 文档宣称的变量类型包括 `env_var`、`cli_arg`、`generated_adapter`，metrics source 包括 `csv_with_summary`、`generated_parser`，但当前执行只接受 `yaml_path`、`json_path`、`stdout_json`、`metrics_json`，见 [auto_optimize/declaration/converter.py](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/auto_optimize/declaration/converter.py:12)。
- `advisor` / `build` / `guided` 仍是 scenario-first，而非 declaration-first。
  - `SCENARIO_TO_PROFILE`、`SCENARIO_REQUIRED_FILES`、`infer_scenario()` 仍是核心入口，见 [auto_optimize/builder/service.py](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/auto_optimize/builder/service.py:27)。
  - `advisor` 生成的是 scenario draft contract，不是 declaration draft，见 [auto_optimize/advisor/service.py](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/auto_optimize/advisor/service.py:28)。
- 报告的“信任增强”部分未完成。
  - 当前 report 有 metric delta、accepted experiments、benchmark context、memory 等，但没有 generated-code summary、risk flags、adapter provenance，见 [auto_optimize/reporting/report_generator.py](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/auto_optimize/reporting/report_generator.py:25)。
- 治理工件偏弱。
  - `docs/release_readiness_gate/` 不存在。
  - `status-audit` 脚本对当前 docs 扫描后得到 `0 tasks / 0 progress signals`，说明项目尚未采用结构化计划跟踪工件，见 [docs/assessments/Project_Status_Snapshot_20260607.md](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/docs/assessments/Project_Status_Snapshot_20260607.md:1)。

## 4. 偏差与调整分析

### 4.1 先做 scenario 系统、后回调 generic direction

- 现状：
  - builder / advisor 仍以固定场景和模板为核心，见 [auto_optimize/builder/service.py](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/auto_optimize/builder/service.py:27)。
  - 但 roadmap 已明确说明这不是产品方向，见 [docs/skill-improvement-roadmap.md](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/docs/skill-improvement-roadmap.md:17)。
- 合理性：
  - 这是一种“先做可跑 MVP，再抽象通用层”的典型路径，不是坏事。
  - 现有 scenario 资产现在扮演 regression fixture 的角色，能降低泛化改造风险。
- 影响：
  - 如果继续扩 scenario，会和 roadmap 冲突。
  - 如果不继续抽离，后续 declaration-first UX 会长期停留在“文档先进于实现”的状态。

### 4.2 文档方向已经领先于实现

- 现状：
  - 文档中已把 declaration 设为主入口，见 [docs/quickstart.md](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/docs/quickstart.md:1)。
  - 但 `SKILL.md` 的 CLI 示例还没体现 `declare` 命令，见 [SKILL.md](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/SKILL.md:94)。
- 影响：
  - 对外叙事总体正确，但内部操作手册仍有轻微不一致。
  - 这不是阻塞项，但会影响团队理解和后续协作。

### 4.3 执行内核成熟度高于产品入口成熟度

- 现状：
  - runner、rollback、report、memory、Git 已经比 roadmap 的“理想 generic loop”更完整，见 [auto_optimize/runner/orchestrator.py](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/auto_optimize/runner/orchestrator.py:1)。
  - 但用户入口层仍有 declaration 覆盖面有限、guided path 未声明化的问题。
- 影响：
  - 好消息是：剩余工作更多是“产品化整合”而不是“从零造底座”。
  - 坏消息是：如果入口层不补齐，项目会显得“能力很多，但主路径不顺手”。

## 5. Gap 分析

### 与期望状态相比的主要 gap

- Gap 1: 声明协议不是完整执行入口，只是“第一条通路”
  - 还缺少更多变量类型、更多 metrics source、从 declaration 直接进入 run 的自然流程。
- Gap 2: 缺少动态适配器生成
  - 这是 roadmap 中最关键、也最能降低用户接入成本的部分。
- Gap 3: 仍存在明显 scenario-first 代码路径
  - 当前 `advisor` / `build` / `guided` 仍会把用户拉回模板和场景。
- Gap 4: trust 层不够完整
  - 报告尚未回答“生成了什么代码、为什么安全、风险在哪里”。
- Gap 5: 治理工件不够结构化
  - 缺少 release gate、缺少带勾选状态的计划文档、缺少可自动统计的阶段进度标记。

### 哪些 gap 最值得优先补

- 第一优先：动态适配器最小闭环
  - 至少做出第一个 `metrics_parser` 或 `eval_wrapper`。
- 第二优先：把 guided path 改成 declaration-first
  - 不再先推断 `faq_retrieval` / `reranking_benchmark` 这种场景。
- 第三优先：报告补齐 generated adapter summary 和 risk flags
  - 这会显著提升“可审计”和“敢用”的程度。
- 第四优先：清理残余文档与 CLI 不一致
  - 成本低、收益高。

## 6. 剩余工作量估算

### 以“达到下一个可信里程碑”为目标

目标定义：

- 用户可从 declaration 出发，不依赖固定 scenario；
- 至少一种动态 adapter 可以自动生成并被报告；
- guided path 不再以 static scenario 为中心；
- 报告能说明生成代码与风险。

预计工作量：`4-6` 个工程日。

拆分建议：

- 最小 adapter 生成与执行接入：`2-3` 天
- guided declaration builder 首版：`1-2` 天
- report 增强与文档收口：`1` 天

### 以“达到 roadmap 当前愿景的 MVP 完整态”为目标

目标定义：

- declaration 覆盖多个变量类型与 metrics source；
- adapter 生成、执行、记录、风险确认闭环完整；
- scenario-first 辅助路径退居次要；
- trust 与治理工件完整可审计。

预计工作量：`10-16` 个工程日。

风险因素：

- 如果要支持 `env_var`、`cli_arg`、`generated_parser` 等多种 declaration 类型，复杂度会明显上升。
- 如果希望保留现有 scenario assets 又同时彻底抽象入口层，需要额外做兼容设计和回归测试。

## 7. 下一步优先级执行计划

### Priority 1: 动态适配器最小闭环

- 核心目标：从 declaration 自动生成第一个真正可执行的 helper code，优先选 `metrics_parser` 或 `eval_wrapper`。
- 首要任务：新增 `generated_adapters/` 写入与执行路径，并在 report 中记录生成文件路径、摘要和使用原因。

### Priority 2: Guided Path 去场景化

- 核心目标：让 `guided` / `advisor` 以 declaration 收集为主，而不是先做 scenario 推断。
- 首要任务：把 [auto_optimize/advisor/service.py](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/auto_optimize/advisor/service.py:108) 的输出从 draft contract 调整为 draft declaration 或 declaration-ready context。

### Priority 3: 信任层补齐

- 核心目标：让用户不用翻原始日志，也能知道本次优化到底改了什么、生成了什么、风险是什么。
- 首要任务：扩展 [auto_optimize/reporting/report_generator.py](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/auto_optimize/reporting/report_generator.py:25)，加入 generated-code summary、risk flags、decision rationale 汇总。

### Priority 4: 治理与发布工件

- 核心目标：让后续 `status-audit` 不再只能做人工判断。
- 首要任务：建立 `docs/release_readiness_gate/` 与一个带 `[x] / [ ]` 状态的执行计划文档。

## 8. 决策记录

- 2026-06-07: 审计确认项目已完成 direction realignment，并已落地第一段 declaration-first executable slice。
- 2026-06-07: 审计确认最大 gap 不在 runner 底座，而在 adapter generation、guided UX 和去场景化产品入口。
- 2026-06-07: 审计建议将下一阶段目标收敛为“最小动态 adapter + guided declaration + report trust”，而不是继续扩 scenario catalog。
