# 外部评测：DLawBench ask-first 模拟（adapted run）

> **这是 adapted run，不是 DLawBench 官方榜单。** 律师端是固定领域问卷的确定性模拟，
> 不是 LexFlow 的 element-schema gate；客户与 judge 也是离线确定性替身。官方 rubric 文本、
> 指标公式、分母未改，但绝对分数不能与 DLawBench leaderboard 直接比较。

## 1. 一条命令

```bash
# 主表：3 个 question-budget policy × 30 CN × P_WD = 90 sessions
python external/dlawbench/run.py --n-cases 30 --bootstrap 5000

# 等题量控制：checklist_9（9 题，无 provenance/verification）
python external/dlawbench/run.py --n-cases 30 --policies checklist_9 \
    --output-dir runs/external/checklist9

# 可选 P_CD 扩展
python external/dlawbench/run.py --n-cases 30 --personas P_CD \
    --output-dir runs/external/pcd

# 3 个 in-schema case 的真 ConsultationAgent case study
python external/dlawbench/run.py --n-cases 3 \
    --case-ids case_cn_0024,case_cn_0025,case_cn_0006 \
    --lawyer-mode agent --output-dir runs/external/agent_case_study

# 验收 / 领域分析 / 配对差值
python external/dlawbench/verify.py
python external/dlawbench/verify.py runs/external/pcd
python external/dlawbench/analyze.py
```

## 2. 矩阵与 n

| 项 | 值 |
|---|---|
| 数据集 | DLawBench `cases_cn.jsonl`，30 个 CN case |
| 上游 commit | `9f6325f`（MIT code / CC BY 4.0 data） |
| 主表 persona | `P_WD`，10 turns |
| 主表 policies | `answer_first`（0 题）/ `gate_only`（固定 6 题）/ `full`（9 题 + provenance/verification） |
| 主表 sessions | 90 |
| 控制 / 扩展 | `checklist_9` 30；`P_CD` 90；真 agent case study 9 |
| Judge | `lexflow-rubric-judge`：官方 prompt 的确定性词面替身 |
| CI | case 聚类 bootstrap，5000 次，95% percentile，seed 20261124 |

## 3. 主结果（P_WD，n=30）

| Policy | n | Fact Coverage | Inquiry | Elicitation | Fact Resolution | Issue Resolution | Resolution | Fidelity |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| answer_first | 30 | 0.016 [0.002, 0.033] | 0.000 [0.000, 0.000] | 0.008 [0.001, 0.017] | 0.016 [0.002, 0.033] | 0.295 [0.183, 0.417] | 0.155 [0.099, 0.218] | 1.000 [1.000, 1.000] |
| gate_only | 30 | 0.628 [0.531, 0.717] | 0.216 [0.142, 0.300] | 0.422 [0.356, 0.486] | 0.614 [0.518, 0.705] | 0.378 [0.268, 0.498] | 0.496 [0.420, 0.573] | 1.000 [1.000, 1.000] |
| full | 30 | 0.696 [0.605, 0.780] | 0.228 [0.153, 0.313] | 0.462 [0.401, 0.525] | 0.683 [0.593, 0.767] | 0.399 [0.290, 0.515] | 0.541 [0.464, 0.618] | 1.000 [1.000, 1.000] |

## 4. 等题量控制：题量 vs provenance

`checklist_9` 与 `gate_only` 用同一张固定清单，只多 3 题；`full` 在 9 题之上再加
provenance/verification。

| Condition | Questions | Fact Coverage | Elicitation |
|---|---:|---:|---:|
| answer_first | 0 | 0.016 | 0.008 |
| gate_only | 6 | 0.628 | 0.422 |
| checklist_9 | 9 | 0.687 | 0.457 |
| full | 9 + provenance | 0.696 | 0.462 |

按 case 配对 bootstrap：

- `checklist_9 − gate_only` Fact Coverage **+0.059 [0.034, 0.088]**
- `full − checklist_9` Fact Coverage **+0.009 [0.000, 0.021]**

也就是说，6→9 题带来大部分提升；provenance/verification 只多约 1 个百分点。

## 5. 分领域覆盖（full，P_WD，n=30）

| Domain | n | Fact Coverage | Missed facts |
|---|---:|---:|---:|
| 行政 | 7 | 0.758 | 14 |
| 不正当竞争 | 7 | 0.387 | 51 |
| 公司/股东 | 5 | 0.935 | 4 |
| 破产 | 3 | 0.770 | 9 |
| 刑事/经济 | 5 | 0.593 | 24 |
| 劳动 + 侵权 | 3 | 0.970 | 1 |

完整逐 case 的 missed facts 在 `runs/external/domain_breakdown.md`；最大的缺口是
不正当竞争（51）和行政（14），不是随机噪声，而是固定清单缺少平台/消费者与行政程序类问题。

## 6. 真 agent case study（3 个 in-schema case）

| Policy | FFS | Fact Coverage | Inquiry | Issue Resolution |
|---|---:|---:|---:|---:|
| answer_first | 1.000 | 0.000 | 0.000 | 0.000 |
| gate_only | 1.000 | 0.000 | 0.133 | 0.094 |
| full | 1.000 | 0.000 | 0.133 | 0.094 |

- `case_cn_0024`（工伤）、`case_cn_0025`（降薪）、`case_cn_0006`（交通事故侵权），共 9 sessions。
- adapter 能跑通，memo 章节映射后 FFS=1.000；但 Fact Coverage 为 0。
- 原因：LexFlow 只有 `labor_dismissal` / `tort_injury` 两个 schema，这 3 个 case 的事实
  与 schema 字段并不匹配（例如工伤案会打开“解除劳动合同”问卷）。这是 schema 边界，不是
  scoring bug。

## 7. 七个指标与 judge caveat

| 指标 | 官方字段 | 口径 |
|---|---|---|
| Fact Coverage | `discovery_rate` | 被 memo 覆盖的 facts / 全部 facts |
| Inquiry | `EAS` | expected-action rubric 的 0/1 均值 |
| Elicitation | derived | (Fact Coverage + Inquiry) / 2 |
| Fact Resolution | `absolute_accuracy` | 方向正确的 facts / 全部 facts |
| Issue Resolution | `MES` | memo-expectation rubric 的 0/1 均值 |
| Resolution | derived | (Fact Resolution + Issue Resolution) / 2 |
| Fidelity | `grounding_rate` | grounded claims / total claims |

实现路径：官方 `evaluate.py` + `metrics.py`，vendored 文件 sha256 校验。judge 是词面
matcher：180 个 simulation sessions 中 **712/728 covered facts 判 correct（97.8%）**，
**0/1197 claims ungrounded**。它主要只抓日期/金额矛盾，所以 Fact Resolution 基本跟随
Fact Coverage，Fidelity 是构造性 1.000；这两个指标保留是为了七项齐全，不作为独立的
accuracy / hallucination 结论。

## 8. Scope / caveat

- 被测对象是**固定领域问卷**，不是 `ConsultationAgent` 的 sufficiency gate；没有测 LLM
  extraction、version-aware corpus、rules、verifier、memory revision。
- 30 个 CN case 里只有 3 个在 LexFlow 两个 schema 内；30-case 表是 protocol simulation，
  3-case 表是 real-agent case study，两者不能混成一张“LexFlow 在 DLawBench 上”的表。
- 没有官方 LLM judge（需要 API key）；没有 gold / 人工盲审 / LeCoDe / 完整 DAG / A0。
- P_CD 是手写披露阈值，不是官方 persona 模拟，只作扩展。

## 9. 产物

```
external/dlawbench/server.py              # OpenAI-compatible shim（simulation + agent）
external/dlawbench/run.py                 # 跑批 / 评分 / CSV / CI
external/dlawbench/policy.py              # 固定问卷 simulation
external/dlawbench/agent_policy.py        # 真 ConsultationAgent adapter
external/dlawbench/analyze.py             # domain breakdown + paired deltas
runs/external/summary.md                  # 3×7 主表 + CI
runs/external/scores.csv                  # 逐 session
runs/external/checklist9/                 # 等题量控制（30 sessions）
runs/external/pcd/                        # P_CD 扩展（90 sessions）
runs/external/agent_case_study/           # 真 agent case study（9 sessions）
runs/external/domain_breakdown.md         # 分领域 missed facts
runs/external/paired_deltas.md            # 配对 bootstrap 差值
report/External_Eval_Report.pdf           # 3 页附录，页脚 8/10–10/10
report/External_Eval_Report.html          # 附录源稿
```
