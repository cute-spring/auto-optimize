# AutoOptimize 中文使用手册

这份手册面向第一次接触 AutoOptimize 的用户。

目标只有一个：让你用最少的概念负担，把“某个具体功能”接进当前项目，完成一次可审计的自动优化。

## 一句话理解它是做什么的

AutoOptimize 不是“直接帮你大改代码”的工具。

它更像一个受控实验执行器：你先声明什么可以改、怎么评估、什么算变好、什么绝对不能碰，然后它自动尝试候选方案、比较结果、回滚失败方案，并产出报告。

## 适合什么问题

适合：

- 你有一个明确想优化的功能
- 你知道哪些参数、配置、开关允许被修改
- 你已经有评估脚本，或者至少能写出一个评估命令
- 你能定义“优化成功”的指标

不适合：

- 只是想“随便看看能不能把代码改好”
- 没有任何评估方法
- 不清楚哪些文件允许改、哪些不能改

## 先记住 4 个核心概念

### 1. `declaration`

用户填写的声明文件，也是推荐入口。

它描述：

- 优化目标
- 可调变量
- 评估命令
- 指标来源
- 比较规则
- 安全边界

### 2. `contract`

更底层的可执行格式。

当前 CLI 最终仍然依赖 contract 执行，但你通常可以直接从 declaration 开始，不一定要手写 contract。

### 3. `evaluation`

你自己的评估命令。

例如：

```bash
python eval/run_eval.py --json
```

它负责输出当前候选方案的指标。

### 4. `safety`

安全边界。

你必须明确：

- 哪些文件允许 AutoOptimize 改
- 哪些目录绝对不允许改

通常会保护：

- `eval/`
- `data/`
- `.env`
- `secrets/`

## 最短上手路径

如果你已经有自己的功能和评估脚本，推荐直接走这条路径：

1. 写一个 `optimization.declaration.yaml`
2. 先 `validate`
3. 再 `run`
4. 最后看 `auto_optimize_outputs/` 里的报告

## 第一步：准备你的功能

在接入之前，先把下面 5 件事想清楚。

### 1. 你要优化哪个功能

例如：

- 检索召回
- reranker 开关与阈值
- prompt 模板
- 配置文件中的参数组合

### 2. 哪些东西允许被改

例如：

- `configs/retrieval.yaml`
- `configs/reranker.yaml`
- `configs/prompt.yaml`

### 3. 评估命令是什么

例如：

```bash
python eval/run_eval.py --json
```

这个命令最好满足两点：

- 从 workspace 根目录可直接执行
- 能稳定输出结构化指标

### 4. 指标从哪里来

当前项目可执行切片支持这些 `metrics_source`：

- `stdout_json`
- `metrics_json`
- `csv_with_summary`
- `generated_parser`

新手最推荐先用 `stdout_json`，因为最直接。

### 5. 什么算优化成功

至少要定义：

- 一个主指标，比如 `top1_accuracy`
- 方向，比如 `maximize`

最好再定义约束，例如：

- 延迟不能超过 200ms
- 成本不能超过某个阈值
- 测试必须通过

## 第二步：写 declaration 文件

下面是一份最小可用示例：

```yaml
workspace:
  path: "."

objective:
  description: "Improve answer quality while keeping latency under 200 ms."

variables:
  - name: top_k
    kind: yaml_path
    target: configs/retrieval.yaml
    path: retrieval.top_k
    values: [5, 10, 20]

evaluation:
  command: "python eval/run_eval.py --json"
  metrics_source: stdout_json

comparison:
  primary_metric: top1_accuracy
  direction: maximize

constraints:
  latency_ms:
    max: 200

safety:
  editable:
    - configs/retrieval.yaml
  protected:
    - eval/
    - data/
```

你也可以直接参考仓库里的样例：

- [examples/declarations/generic_config_optimization.declaration.yaml](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/examples/declarations/generic_config_optimization.declaration.yaml:1)

## 第三步：先检查，再执行

推荐先把 declaration 转成 contract，确认内容正确：

```bash
python -m auto_optimize.cli declare ./optimization.declaration.yaml --output ./optimization.contract.yaml
python -m auto_optimize.cli explain-contract ./optimization.contract.yaml
python -m auto_optimize.cli validate ./optimization.contract.yaml
```

如果你想直接跑，也可以：

```bash
python -m auto_optimize.cli run ./optimization.declaration.yaml
```

这个命令会自动：

1. 加载 declaration
2. 生成 contract
3. 校验可执行性
4. 执行 baseline
5. 尝试候选变量组合
6. 比较结果
7. 生成报告

## 第四步：看输出结果

默认会在 workspace 下生成 `auto_optimize_outputs/`。

最值得先看的文件通常是：

- `optimization.contract.generated.yaml`
- `contract_validation_report.md`
- `experiment_log.jsonl`
- `run_summary.json`
- `optimization_report.md`

如果只是想重新生成报告：

```bash
python -m auto_optimize.cli report auto_optimize_outputs
```

## 最推荐的新手操作顺序

如果你是第一次使用，建议严格照这个顺序：

1. 先跑参考示例，确认环境没问题
2. 再仿照示例写自己的 declaration
3. 先 `declare` 和 `validate`
4. 确认安全边界后再 `run`
5. 最后根据报告迭代 declaration

## 如何先跑一个参考示例

这是最短的本地演示路径：

```bash
python -m auto_optimize.cli advisor --workspace examples/faq_retrieval/workspace
python -m auto_optimize.cli validate examples/faq_retrieval/optimization.contract.yaml
python -m auto_optimize.cli run examples/faq_retrieval/optimization.contract.yaml
python -m auto_optimize.cli report examples/faq_retrieval/workspace/auto_optimize_outputs
```

对应说明可看：

- [docs/walkthrough-faq.md](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/docs/walkthrough-faq.md:1)

## 当前 CLI 命令怎么理解

最常用的是这几个：

### `run`

真正执行优化。

支持传入：

- declaration
- contract

### `validate`

执行前的安全和就绪性检查。

建议每次必跑。

### `explain-contract`

把 contract 翻译成人更容易读懂的说明。

适合确认“这次到底会改什么、评估什么、比较什么”。

### `advisor`

从 workspace 推断一个草稿声明和 readiness 报告。

适合你还没完全整理好 declaration 的时候拿来找灵感。

### `guided`

当前更接近“生成草稿 + 生成 contract”的辅助入口，不是强交互式逐步问答向导。

这一点要有预期。

## 当前 skill 能做到什么

当前 skill 已经能：

- 以 declaration 为主入口
- 校验声明和安全边界
- 从 declaration 生成 contract
- 对一部分变量类型执行受控实验
- 产出可审计报告

当前 skill 还不够完整的地方：

- `advisor` / `guided` 还不是完整的对话式表单向导
- 并不是所有声明能力都已经落成可执行能力
- 一些更广义的动态 adapter 仍在演进中

换句话说，它已经能“执行”，但还没有完全做到“低门槛手把手带填”。

## 新手最容易踩的坑

### 1. 没有稳定的评估命令

如果 `evaluation.command` 本身不稳定，优化结果就不可信。

### 2. 指标输出格式不清晰

如果评估脚本不能稳定输出 JSON、metrics 文件或 summary CSV，AutoOptimize 就很难读取结果。

### 3. 把不该改的目录放进 editable

尤其不要轻易允许修改：

- `eval/`
- `data/`
- 金标数据
- 秘钥文件

### 4. 主指标定义太模糊

如果没有明确的 `primary_metric` 和方向，系统无法判断哪个候选更好。

### 5. 一上来就想优化“整个系统”

更好的做法是一次只优化一个局部功能，例如：

- 先只调检索参数
- 先只调 prompt 模板
- 先只调 reranker 开关和阈值

## 遇到问题时怎么排查

建议按这个顺序看：

1. `validate` 有没有报错
2. `contract_validation_report.md` 写了什么
3. `evaluation.command` 能不能手工跑通
4. `metrics_source` 和输出格式是否匹配
5. `editable` / `protected` 是否冲突
6. `optimization_report.md` 和 `run_summary.json` 是否记录了失败原因

## 给第一次接项目的人一个建议

如果你不是要扩展框架本身，而只是想“把自己的某个功能接进来跑一次优化”，最省力的方法是：

1. 先跑 FAQ 参考示例
2. 抄一份 declaration 样例
3. 只替换：
   - `workspace.path`
   - `variables`
   - `evaluation.command`
   - `comparison`
   - `constraints`
   - `safety`
4. 先验证，再执行

## 进一步阅读

- [README.md](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/README.md:1)
- [docs/quickstart.md](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/docs/quickstart.md:1)
- [docs/command-guide.md](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/docs/command-guide.md:1)
- [docs/declaration-protocol.md](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/docs/declaration-protocol.md:1)
- [docs/walkthrough-custom-eval.md](/Users/gavinzhang/ws-ai-recharge-2026/auto-optimize/docs/walkthrough-custom-eval.md:1)

## 一句话总结

把它当成“声明驱动的自动实验器”来用，而不是“万能自动改代码器”。

只要你的目标、变量、评估和安全边界足够清楚，这个项目现在已经能帮你把一个特定功能的优化流程跑起来。
