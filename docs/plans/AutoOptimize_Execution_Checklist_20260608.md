# AutoOptimize 执行清单

最后更新：2026-06-08

基线来源：

- [项目状态审核与进度分析报告 (2026-06-07)](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/docs/assessments/Project_Status_Audit_20260607.md:1)
- [Generic Skill Improvement Roadmap](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/docs/skill-improvement-roadmap.md:1)

目标：

- 把当前“已能跑的 declaration-first slice”推进到“真正可用的 generic declaration-driven skill”
- 优先补齐动态 adapter、declaration-first guided path、trust/reporting、治理工件

## 阶段进度

- Phase 1: Direction Realignment: 100%
- Phase 2: Declaration Protocol: 100%
- Phase 3: Dynamic Adapter Generation: 100%
- Phase 4: Generic Execution Loop: 100%
- Phase 5: Usability And Trust: 100%

## 已完成基线

- [x] 将项目主叙事改为 generic declaration-driven skill
- [x] 重写 `README.md`、`SKILL.md`、`quickstart`、`architecture` 等方向文档
- [x] 新增 declaration 数据模型与 YAML loader
- [x] 新增 declaration 校验
- [x] 新增 declaration -> executable contract 转换
- [x] 新增 `python -m auto_optimize.cli declare ...`
- [x] 新增 generic declaration 示例
- [x] 让 `declare -> explain-contract -> validate` 端到端可执行
- [x] 为 declaration slice 补充测试覆盖
- [x] 保持全量测试通过，当前基线为 `79 passed`

## Priority 1: 动态 Adapter 最小闭环

目标：
让 declaration 不再只能处理现成 JSON 输出和静态文件映射，至少支持一种“运行时生成的 helper code”。

预计工作量：2-3 个工程日

- [x] 新增 `auto_optimize_outputs/generated_adapters/` 运行时目录约定
- [x] 设计 adapter 元数据结构
- [x] 在 run 前生成第一个最小可用 adapter
- [x] 优先实现 `metrics_parser` 或 `eval_wrapper` 二选一
- [x] 将生成的 adapter 接入现有 evaluation 执行链路
- [x] 为生成 adapter 增加安全边界校验
- [x] 在 validation 阶段识别 declaration 是否需要 adapter
- [x] 在 run summary 中记录 adapter 路径、类型、用途
- [x] 在 Markdown report 中展示 generated adapter summary
- [x] 为 adapter generation 增加端到端测试

## Priority 2: Guided Path 去场景化

目标：
让 `advisor` / `guided` 不再先推断 FAQ、benchmark、reranking 等静态场景，而是围绕 declaration 收集信息。

预计工作量：1-2 个工程日

- [x] 审视 `advisor` 当前输出，拆分“workspace inspection”和“scenario template assembly”
- [x] 将 `advisor` 输出改为 declaration-ready context 或 draft declaration
- [x] 将 `guided` 主路径改为 declaration-first，而不是 contract template-first
- [x] 弱化 `SCENARIO_TO_PROFILE` / `infer_scenario()` 在主流程里的中心地位
- [x] 保留现有 scenario assets 作为 reference fixtures，而非主入口
- [x] 为新的 guided/advisor 路径补充测试

本次最小推进（2026-06-08）：

- [x] `advisor` 额外输出 generic `draft declaration`
- [x] `readiness_report.json` 增加 `draft_declaration_path`
- [x] `readiness_report.json` 增加 `declaration_first_next_actions`
- [x] 补测试覆盖 `advisor -> draft declaration -> declare -> validate`
- [x] `guided` 默认走 `draft declaration -> declare -> generated contract`
- [x] `readiness_report.json` 核心就绪判断改为 declaration-first，并保留 template compatibility context
- [x] `builder` / `advisor` 输出显式记录 reference fixture context
- [x] 补齐 benchmark guided 与 custom output 的 declaration-first 测试

## Priority 3: Trust / Reporting 补齐

目标：
让用户能直接看懂本次优化改了什么、生成了什么、风险是什么，而不必翻原始日志。

预计工作量：1 个工程日

- [x] 在 report 中增加 generated-code summary
- [x] 在 report 中增加 adapter provenance
- [x] 在 report 中增加 risk flags
- [x] 在 report 中增加 decision rationale 汇总
- [x] 在 report 中明确区分 declaration input、generated contract、generated adapters
- [x] 为报告新增内容补充测试或快照验证

## Priority 4: Declaration 执行覆盖面扩展

目标：
把当前 declaration 支持范围从“第一条通路”扩展到更接近日常项目接入需求。

预计工作量：3-5 个工程日

- [x] 支持 `env_var` 变量类型
- [x] 支持 `cli_arg` 变量类型
- [x] 评估是否引入 `generated_adapter` 变量类型的最小可执行版本（结论：当前切片 defer，见 `docs/assessments/Generated_Adapter_Variable_Evaluation_20260608.md`）
- [x] 支持除 `stdout_json` / `metrics_json` 以外的下一个 metrics source
- [x] 增加 declaration -> run 的失败提示与 remediation 文案
- [x] 为新增 declaration 类型补充验证和执行测试

## Priority 5: 治理与发布工件

目标：
让项目进度、发布就绪度和后续审计不再依赖人工解读。

预计工作量：0.5-1 个工程日

- [x] 建立 `docs/plans/` 目录并创建结构化执行清单
- [x] 建立 `docs/release_readiness_gate/`
- [x] 增加发布质量门模板
- [x] 增加阶段完成定义（Definition of Done）
- [x] 为后续 `status-audit` 维护可统计的阶段进度信号
- [x] 约定每次里程碑推进后更新本清单

## 可延后项

- [ ] 支持从 existing contract 反向生成 declaration
- [ ] 重新梳理 benchmark/reference 资产与 generic flow 的边界
- [ ] 统一 `SKILL.md` 与最新 CLI 示例，补上 `declare`
- [ ] 评估是否需要 declaration lint / format 命令

## 建议执行顺序

- [x] 先完成 Priority 1: 动态 Adapter 最小闭环
- [x] 再完成 Priority 2: Guided Path 去场景化
- [x] 然后完成 Priority 3: Trust / Reporting 补齐
- [x] 接着推进 Priority 4: Declaration 执行覆盖面扩展
- [x] 最后补齐 Priority 5: 治理与发布工件

## 下一个可信里程碑定义

满足以下条件即可视为“下一个可信里程碑完成”：

- [x] declaration 可以触发至少一种动态 adapter 生成
- [x] generated adapter 被真实执行，而不是只记录在 context 中
- [x] report 能展示 generated adapter summary 与 risk flags
- [x] `advisor` / `guided` 的主路径已经 declaration-first
- [x] 全量测试保持通过

## 备注

- 当前不建议继续扩 static scenario catalog。
- 当前最值得投入的工作不在 runner 底座，而在 adapter、入口层和 trust 层。
- 这个清单应作为后续推进和 `status-audit` 的主输入之一。
