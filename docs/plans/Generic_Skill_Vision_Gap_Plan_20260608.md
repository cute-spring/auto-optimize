# Generic Skill Vision Gap Plan

最后更新：2026-06-08

## 背景

当前项目已经完成了 `docs/plans/AutoOptimize_Execution_Checklist_20260608.md` 中定义的主线执行清单，形成了一个可运行、可验证、可审计的 declaration-first slice。

当前已具备的能力包括：

- declaration -> contract -> validate -> run 主闭环
- `advisor` / `guided` 的 declaration-first 主路径
- 动态 metrics parser adapter 最小闭环
- trust/reporting 的 provenance、risk、decision rationale
- `env_var`、`cli_arg`、`csv_with_summary` 等执行扩展
- contract -> declaration 反向派生
- release readiness gate、DoD、status signals 等治理工件

但这些完成度主要对应“阶段执行清单收口”，还不等同于“generic declaration-driven skill 远景完全达成”。

本计划用于描述：在当前主线清单完成之后，项目距离远景还剩下哪些关键 gap，以及建议如何分阶段推进。

## 当前状态判断

建议将当前状态分成两个维度看待：

- 执行清单完成度：接近 `100%`
- 远景产品完成度：约 `75%-85%`

更准确地说，项目已经越过“方向纠偏 + 最小闭环验证”阶段，进入了“从可运行原型走向真正低心智负担产品入口”的阶段。

## 剩余的 4 个关键愿景 Gap

### Gap 1: Declaration-Native Execution

当前 declaration 已经是主叙事和主 authoring artifact，但执行入口仍然偏向：

- `declare`
- `validate contract`
- `run contract`

这意味着当前更准确的状态是：

- declaration-first authoring
- 而不是 declaration-native execution

如果远景是 generic declaration-driven skill，那么用户最自然的心智模型应当是：

- 直接运行 declaration
- contract 保持为内部执行层，而不是用户必须理解的中间层

### Gap 2: Richer Adapter Platform

当前已经完成了一条最小动态 adapter 通路，但它仍然主要是：

- generated parser
- metrics parser adapter

这足以证明 declaration-first slice 可执行，但还不是一个更通用的 adapter platform。

距离远景还差：

- 第二条 adapter lane
- 更清晰的 adapter registry / materialization / execution 结构
- 更可扩展的 adapter provenance 与风险模型

### Gap 3: True Guided Declaration Builder UX

当前 `advisor` / `guided` 已经 declaration-first，并能输出 draft declaration，但它更像：

- workspace inspection
- draft generation
- readiness reporting

还不是成熟的 declaration builder UX。

距离远景还差：

- 结构化 declaration gap model
- declaration completeness / readiness score
- 自动补齐低风险默认值
- 更明确的 failure remediation

### Gap 4: Status-Audit Automation Closed Loop

当前治理工件已经建立，包括：

- 执行清单
- release readiness gate
- Definition of Done
- `status_audit_signals.yaml`

但自动消费层还没有完全接上。

一个明显信号是：

- 历史状态快照文档仍然不能真实反映当前完成度

这说明当前“信号源”已经存在，但“自动汇总为当前状态真相”的链路还没真正闭环。

## 总体推进策略

建议把后续工作拆成 4 个主项目包，按以下顺序执行：

1. Declaration-Native Execution
2. Status-Audit Automation
3. Guided Declaration Builder UX
4. Richer Adapter Platform

这个顺序的原因是：

- 第一步最直接降低用户心智负担
- 第二步让后续推进状态可见、可审计
- 第三步把 declaration-first 的入口体验真正产品化
- 第四步再扩能力层，避免先做平台扩张而入口仍然别扭

## Phase A: Declaration-Native Execution

当前进展：

- [x] 已完成（2026-06-08）
- `run` 现在可直接接受 `optimization.declaration.yaml`
- declaration-native run 会自动生成 contract，并在 run summary / report 中记录 `execution_mode = declaration_native`
- 已补 focused tests，并通过全量 `pytest -q`，当前基线为 `86 passed`

### 目标

让 declaration 成为真正的一等执行入口，让用户无需手动先执行 `declare` 才能运行任务。

### 当前问题

当前虽然 declaration 是主作者入口，但实际执行仍依赖 contract 作为显式用户步骤。

这会带来两个问题：

- 用户需要理解内部 contract 层
- declaration-first 的产品心智还不够彻底

### 具体要做什么

#### A1. 让 `run` 直接接受 declaration 输入

支持如下使用方式：

```bash
python -m auto_optimize.cli run path/to/optimization.declaration.yaml
```

CLI 需要能够识别输入类型，包括但不限于：

- `.declaration.yaml`
- `.contract.yaml`
- `.contract.generated.yaml`

#### A2. 定义 declaration-native run 内部链路

建议执行流程固定为：

1. load declaration
2. validate declaration
3. generate executable contract
4. validate contract
5. execute run
6. write report and summary

#### A3. 定义生成 contract 的生命周期

需要明确 declaration-native run 中生成 contract 的落盘策略。

建议：

- 默认生成到 workspace 下的 `auto_optimize_outputs/optimization.contract.generated.yaml`
- run summary 中显式记录：
  - source declaration path
  - generated contract path
  - execution mode = declaration_native

#### A4. 统一 declaration-native run 的成功与失败文案

成功输出应重点说明：

- 本次运行使用的 declaration
- 自动生成的 contract 路径
- 产出的 run summary 与 report

失败输出应优先给 declaration remediation，而不是只暴露 contract 层内部细节。

#### A5. 补齐 declaration-native run 测试

最少应覆盖：

- declaration path 直接 run 成功
- declaration path 校验失败
- declaration path -> generated parser -> run
- declaration path + `env_var`
- declaration path + `cli_arg`
- declaration path + `csv_with_summary`

### 建议涉及文件

- `/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/auto_optimize/cli.py`
- `/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/auto_optimize/declaration/converter.py`
- `/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/auto_optimize/declaration/loader.py`
- `/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/auto_optimize/runner/orchestrator.py`
- `/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/tests/test_run_command.py`
- `/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/tests/test_declaration_command.py`

### 验收标准

- 用户不需要手动先执行 `declare`
- declaration 可以直接触发 validate + run
- report / summary / provenance 不丢失
- 全量测试继续通过

### 预计工作量

- `1 - 1.5` 个工程日

## Phase B: Status-Audit Automation

当前进展：

- [x] 已完成（2026-06-08）
- 新增 `python -m auto_optimize.cli status-audit`
- `status_audit_signals.yaml` 现在会被消费并生成当前 snapshot Markdown + JSON
- 已生成新的当前状态快照：
  - `docs/assessments/Project_Status_Snapshot_20260608.md`
  - `docs/assessments/Project_Status_Snapshot_20260608.json`
- 历史快照 `Project_Status_Snapshot_20260607.md` 已被明确降级为 historical baseline

### 目标

让项目状态快照能够从结构化信号自动生成，而不是依赖人工阅读多份文档后再手动判断。

### 当前问题

当前虽然已经有：

- checklist
- release readiness gate
- DoD
- `status_audit_signals.yaml`

但“当前状态快照”的自动生成还没有闭环。

### 具体要做什么

#### B1. 实现 status snapshot generator

新增一个轻量命令或脚本，用于消费状态信号并生成快照。

候选形式：

```bash
python -m auto_optimize.cli status-audit
```

或

```bash
python tools/generate_status_snapshot.py
```

#### B2. 设计固定的 snapshot schema

建议输出至少包含：

- overall completion
- current full test baseline
- each stage status
- evidence links
- unresolved strategic gaps
- recommended next milestone

#### B3. 扩展 `status_audit_signals.yaml`

建议补充字段：

- `goal_status`
- `current_focus`
- `strategic_gaps`
- `recommended_next_step`
- `last_full_test_at`

#### B4. 区分历史快照与当前快照

已有旧快照应被明确视为历史记录，而不是当前真相来源。

建议：

- 新生成快照使用新日期文件名
- 在新快照中说明旧快照为 historical baseline

#### B5. 让 release gate 与 snapshot 建立关联

目标是把两者角色分开但打通：

- status snapshot 回答“项目现在在哪里”
- release gate 回答“这次切片能不能放行”

### 建议涉及文件

- `/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/docs/release_readiness_gate/status_audit_signals.yaml`
- `/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/docs/assessments/Project_Status_Snapshot_20260607.md`
- `/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/docs/plans/AutoOptimize_Execution_Checklist_20260608.md`
- `/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/auto_optimize/cli.py`
- 可能新增一个脚本或生成模块

### 验收标准

- 能自动产出新的项目状态快照
- 快照能反映当前真实完成度
- 不再出现“状态信号已完成但 snapshot 仍然过时”的割裂

### 预计工作量

- `1 - 1.5` 个工程日

## Phase C: Guided Declaration Builder UX

当前进展：

- [x] 已完成（2026-06-08）
- `advisor` 的 readiness report 现在新增：
  - `declaration_gaps`
  - `readiness_scores`
  - `autofill_applied`
  - `manual_decisions_required`
- `advisor` 现在同时产出：
  - `draft declaration`
  - `normalized declaration`
- `guided` 已切到使用 normalized declaration 生成 contract
- `guided` / `advisor` 的 CLI 输出现在会直接展示：
  - readiness scores
  - autofill applied count
  - manual decisions count
  - top declaration gaps with remediation
- `advisor` 现在会在 workspace 已存在 metrics artifact 时主动推断：
  - `evaluation.metrics_source`
  - `evaluation.metrics_path`
- 已通过 focused tests 与全量 `pytest -q`，当前基线为 `95 passed`

### 目标

把当前 `advisor` / `guided` 从“能生成 draft declaration 的工具”推进成“能真正引导用户补齐 declaration 的 builder UX”。

### 当前问题

当前能力已经不错，但仍然偏向：

- 自动检查 workspace
- 生成 draft declaration
- 给出 readiness report

距离理想 builder 体验还差一层更强的 gap detection 与 completion guidance。

### 具体要做什么

#### C1. 建立 declaration gap taxonomy

把 declaration 的缺口显式结构化，例如：

- missing objective
- missing editable variables
- missing protected scope
- missing evaluation command
- missing metrics source
- missing comparison rule
- missing constraints
- missing adapter permission

#### C2. 增加 readiness scores

建议区分至少三类得分：

- `authoring_completeness`
- `execution_readiness`
- `safety_readiness`

目的不是为了漂亮，而是为了：

- 量化距离“可运行”还有多远
- 为 guided 后续行为提供稳定依据

#### C3. 自动补齐低风险默认值

只对低风险字段自动补齐，例如：

- timeout defaults
- budget defaults
- report defaults
- metrics path 候选默认值
- protected scope 的保守默认值

#### C4. 明确区分三类输出

建议在语义和文档中明确三层产物：

- `draft_declaration`
- `normalized_declaration`
- `generated_contract`

#### C5. 进一步降低 reference fixtures 的中心性

当前 benchmark / FAQ / template 资产已经被降级为 reference fixtures。

下一步应继续做到：

- fixture 只提供 hints
- fixture 不再主导输出结构
- 用户不需要理解 benchmark/FAQ 才能完成 declaration

#### C6. 补强 guided failure UX

针对常见失败情形提供更可执行 remediation，例如：

- eval 命令找不到
- metrics source 无法推断
- editable scope 太宽或太空
- protected scope 缺关键保护
- declaration 核心字段缺失

### 建议新增数据结构

建议在 readiness report 中增加：

- `declaration_gaps`
- `readiness_scores`
- `autofill_applied`
- `manual_decisions_required`

### 建议涉及文件

- `/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/auto_optimize/advisor/service.py`
- `/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/auto_optimize/builder/service.py`
- `/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/auto_optimize/cli.py`
- `/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/tests/test_advisor_command.py`
- `/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/tests/test_builder_command.py`

### 验收标准

- `guided` 不只是草拟 declaration
- 它能够稳定解释“还缺什么、已经补了什么、下一步该做什么”
- 用户不需要先理解 scenario/template 才能推进

### 预计工作量

- `1.5 - 2.5` 个工程日

## Phase D: Richer Adapter Platform

当前进展：

- [x] 已完成（2026-06-08）
- 现有 `metrics_parser` generated adapter 路径已经从 evaluator 中抽离为独立的 registry / materialization 层
- 新增 `auto_optimize/runner/generated_adapters.py`
- 第二条 adapter lane 已落地：
  - `eval_wrapper`
  - `last_json_line`
- adapter provenance / report 现在开始显式记录：
  - execution phase
  - expected input
  - failure mode
  - remediation hint
- adapter validation 现在开始消费 registry metadata，显式校验：
  - required fields
  - required risk flags
  - declaration allowed kinds
- 已通过 focused tests 与全量 `pytest -q`，当前基线为 `95 passed`

### 目标

把当前“最小动态 adapter 闭环”推进成更通用、更易扩展的 adapter platform。

### 当前问题

当前已有的 adapter 路径证明了方向是可行的，但还存在以下限制：

- adapter kind 偏少
- adapter 执行与生成逻辑还不够模块化
- 扩第二条 lane 的成本偏高

### 具体要做什么

#### D1. 抽象 adapter registry

建议建立统一 registry，定义每类 adapter 的：

- adapter kind
- template
- required fields
- execution mode
- provenance builder
- risk flags

#### D2. 抽离 adapter materialization / execution 层

建议把以下逻辑从当前分散实现中抽出来：

- ensure adapter artifact
- write generated adapter
- invoke adapter
- collect adapter outputs
- parse adapter outputs

#### D3. 落第二条 adapter lane

优先建议实现：

- `eval_wrapper`

优先级高于继续增加更多 parser template，因为它能解决更广泛的真实接入问题。

#### D4. 完善 adapter validation matrix

每种 adapter 应明确：

- 必填字段
- 支持的 template
- 是否要求 `adapter_generation.allowed`
- 是否要求 output dir
- 适用风险等级

#### D5. 扩展 report / provenance / risk model

建议让每个 adapter 在 report 中都能明确展示：

- 来源
- 触发原因
- 输入输出工件
- 失败模式
- remediation hint

#### D6. 保持 `generated_adapter` variable 的 defer 结论

当前不建议直接把 `generated_adapter` 变量类型推进成执行特性。

更合理的下一步是：

- 先完成 adapter platform 分层
- 再单独评估 artifact-producing candidate abstraction

### 建议涉及文件

- `/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/auto_optimize/runner/evaluator.py`
- `/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/auto_optimize/declaration/converter.py`
- `/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/auto_optimize/contract/validator.py`
- `/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/auto_optimize/reporting/report_generator.py`
- `/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/auto_optimize/runner/orchestrator.py`
- 可能新增 adapter registry / execution 模块

### 验收标准

- 至少存在两条可执行 adapter lane
- adapter 配置、生成、执行、报告不再是散落逻辑
- 用户能看懂“为什么生成了 adapter、它如何被执行、它有什么风险”

### 预计工作量

- `2 - 3` 个工程日

## 建议总排期

建议按以下顺序推进：

1. Phase C: Guided Declaration Builder UX
2. Phase D: Richer Adapter Platform

粗略估算总工作量：

- `0`（本计划定义的剩余项目已完成）

## 每个 Phase 的交付物

### Phase A 交付物

- declaration-native `run`
- declaration 直达执行测试
- CLI / README / command guide 更新

### Phase C 交付物

- 更结构化的 readiness report
- guided/autofill/gap guidance 增强
- declaration builder 路径测试

### Phase D 交付物

- adapter registry 或等价抽象层
- 第二条 adapter lane
- provenance / risk / report 增强

## 不建议当前优先投入的事项

以下事项当前不建议抢在上述 4 个主项目包之前做：

- 继续扩 static scenario catalog
- 直接实现 `generated_adapter` variable execution
- 优先做 declaration lint / format command
- 无节制地继续增加 metrics source，而不先统一 declaration-native 执行入口

## 完成定义

当以下条件满足时，可以认为项目从“可运行 slice”迈向了“更接近远景的 generic skill”：

- declaration 成为真正的一等执行入口
- 项目状态快照可以从结构化信号自动生成
- guided 能稳定收敛 declaration 缺口，而不只是输出草稿
- 动态 adapter 不再只有单一路径，而是具备更明确的平台化结构

当前状态：以上条件均已满足。

## 建议的下一步

如果继续投入，下一步已经不再属于本计划的“剩余项目”，而是新一轮增量方向，例如：

- 更强的交互式 guided 补全
- 更丰富的 adapter kinds
- artifact-producing candidate abstraction
