# 外部检查：DLawBench ask-first 外部检查（adapted run）

> **这是 adapted run，不是 DLawBench 官方榜单。** 主报告的 12-case controlled protocol
> 已经测试了 gate 本体（coverage 57.5%→100%，premature advice 58.3%→0%）；本附录把同一套
> ask-first 策略接到 DLawBench 的公开协议上，测的是“外部协议迁移 + 两个 schema 的边界”，
> 不是第二次 gate 测试。律师端是固定领域问卷的确定性模拟，客户与 judge 也是离线替身。
> 官方 rubric 文本、指标公式、分母未改，但绝对分数不能与 DLawBench leaderboard 直接比较。

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
| answer_first | 30 | 0.016 [0.002, 0.033] | 0.000 [0.000, 0.000] | 0.008 [0.001, 0.017] | 0.016 [0.002, 0.033] | 0.289 [0.177, 0.414] | 0.152 [0.095, 0.216] | 1.000 [1.000, 1.000] |
| gate_only | 30 | 0.628 [0.531, 0.717] | 0.216 [0.142, 0.300] | 0.422 [0.356, 0.486] | 0.614 [0.518, 0.705] | 0.372 [0.259, 0.494] | 0.493 [0.416, 0.570] | 1.000 [1.000, 1.000] |
| full | 30 | 0.696 [0.605, 0.780] | 0.228 [0.153, 0.313] | 0.462 [0.401, 0.525] | 0.683 [0.593, 0.767] | 0.393 [0.282, 0.512] | 0.538 [0.461, 0.616] | 1.000 [1.000, 1.000] |

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

完整逐 case 的 missed facts 在 `runs/external/domain_breakdown.md`。最大的缺口是
不正当竞争（51）和行政（14），但原因**不是“清单缺题”**：`full` 已经把行政的程序/期限题
和不正当竞争的平台题都问了。103 条未覆盖 fact 里有 **56 条（54%）在离线客户端的主题词表
（`textutil.TOPIC_KEYWORDS`）里没有对应主题**，任何问题都触发不了披露。例如
`case_cn_0029` 第 5 轮确实问了“您向平台投诉过吗？平台怎么处理？”，但这条平台事实没有主题
标签，客户端只能回“这个我手上没有材料”。也就是说 Fact Coverage 存在一个与律师策略无关的
上限，这是离线 client 替身的限制，不是问卷设计的问题。

## 6. 真 agent case study（3 个 labor/tort case，1 个在 schema 内）

| Policy | FFS | Fact Coverage | Inquiry | Issue Resolution | Fidelity |
|---|---:|---:|---:|---:|---:|
| answer_first | 1.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| gate_only | 1.000 | 0.000 | 0.133 | 0.094 | 0.143 |
| full | 1.000 | 0.000 | 0.133 | 0.094 | 0.143 |

- `case_cn_0024`（工伤）、`case_cn_0025`（降薪）、`case_cn_0006`（交通事故侵权），共 9 sessions。
- 只有 `case_cn_0006` 真正落在 `tort_injury` schema 内；0024/0025 都是劳动争议，agent 打开的是
  `labor_dismissal` 问卷，属于 schema 边界，**不计入 in-schema**。
- adapter 能跑通；但 FFS=1.000 是 `agent_policy._format_for_dlawbench` 自己拼出 5 个必需小节
  的结果，不是能力分。Fact Coverage 为 0。
- Fidelity 只有 0.000 / 0.143：备忘录的结构化事实表用英文字段名和“当事人陈述”，与对话文本
  对不上，这个指标在 agent 模式下基本失效。
- `case_cn_0025` 的备忘录还有三处事实错误：把“社保缴至 2023 年 3 月”变成解除日 `2023-03-01`、
  `monthly_wage` 被抽成 202（补偿金算成 1,616 元）、把“我据此辞职”记成“单位单方解除”。
  这是 mock LLM 下的事实抽取问题，不是 schema 问题（附录 A.8 已写明）。

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
matcher：180 个 simulation sessions（主表 90 + P_CD 90，不含 checklist_9）中
**712/728 covered facts 判 correct（97.8%）**，**0/1197 claims ungrounded**。它主要只抓
日期/金额矛盾，所以 Fact Resolution 基本跟随 Fact Coverage，Fidelity 是构造性 1.000；
这两个指标保留是为了七项齐全，不作为独立的 accuracy / hallucination 结论。

**Issue Resolution 的口径**：MES 判分依赖人工整理的领域问题库（`legal_library.py`）。该题库
在第一次跑分后扩充过，本轮又清除了其中带具体案件指纹的条目（`C市规划区`、`消防验收`、
`隐蔽工程`、`违法占地/购苗` 等）。因此 MES / Resolution 是“清单覆盖 + 判分阈值”的诊断量，
不是 held-out 的能力分；policy 之间的差值仍然可比，绝对值不能与官方榜单比较。

## 8. Scope / caveat

- 被测对象是**固定领域问卷**，不是 `ConsultationAgent` 的 sufficiency gate；没有测 LLM
  extraction、version-aware corpus、rules、verifier、memory revision。
- 题库是人工整理、并在首轮跑分后扩充过的；本轮已清除可指认到具体案件的条目，并加了自动
  检查（`verify.py`），但它不是 held-out 题库，MES / Resolution 只能作为诊断。
- 离线客户端的主题词表覆盖不全：103 条未覆盖 fact 中 56 条没有对应主题，Fact Coverage
  因此带有与律师策略无关的上限。
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
report/External_Eval_Report.pdf           # 3 页附录，页脚 Appendix A · 1 / 3
report/External_Eval_Report.html          # 附录源稿
```
