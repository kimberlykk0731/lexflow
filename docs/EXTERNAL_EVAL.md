# 外部评测：LexFlow × DLawBench（adapted run）

> **这是 adapted run，不是 DLawBench 官方榜单。** 律师端是 LexFlow 的 policy shim，
> 客户与 judge 都是离线确定性替身；官方 rubric 文本、指标公式、分母未改，但绝对分数
> 不能与 DLawBench leaderboard 直接比较。

## 1. 一条命令

```bash
# D1 最小矩阵：3 policies × 10 CN × P_WD = 30 sessions
python external/dlawbench/run.py --n-cases 10

# D2 扩展：3 policies × 30 CN × P_WD = 90 sessions（仓库内已交付这一版）
python external/dlawbench/run.py --n-cases 30 --bootstrap 5000

# 验收自检
python external/dlawbench/verify.py
```

脚本依次完成：启动 shim → 跑 dialogue → 调官方 `dlawbench.evaluate.evaluate_session`
评分 → 调官方 `metrics.py` 公式 → 按 case 聚类 bootstrap → 写
`runs/external/{summary.md,scores.csv,leaderboard.md,run_manifest.json}`。

## 2. 矩阵与 n

| 项 | 值 |
|---|---|
| 数据集 | DLawBench `data/case_backgrounds/cases_cn.jsonl`，30 个 CN case（全量） |
| 上游 commit | `9f6325f29f07b296fac110a6e1880bdd5d9ca538`（MIT code / CC BY 4.0 data） |
| Persona | `P_WD`（理性合作者），max turns = 10 |
| Policies | `answer_first` / `gate_only` / `full` |
| Sessions | 90（3 × 30） |
| Judge | `lexflow-rubric-judge`：确定性词面 rubric matcher，官方 prompt 的离线替身 |
| CI | case 聚类 bootstrap，5000 次，95% percentile，seed 20261124 |

## 3. 结果（2026-11-24，n=30 / policy）

| Policy | n | Fact Coverage | Inquiry | Elicitation | Fact Resolution | Issue Resolution | Resolution | Fidelity |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| answer_first | 30 | 0.016 [0.002, 0.033] | 0.000 [0.000, 0.000] | 0.008 [0.001, 0.017] | 0.016 [0.002, 0.033] | 0.295 [0.183, 0.417] | 0.155 [0.099, 0.218] | 1.000 [1.000, 1.000] |
| gate_only | 30 | 0.628 [0.531, 0.717] | 0.216 [0.142, 0.300] | 0.422 [0.356, 0.486] | 0.614 [0.518, 0.705] | 0.378 [0.268, 0.498] | 0.496 [0.420, 0.573] | 1.000 [1.000, 1.000] |
| full | 30 | 0.696 [0.605, 0.780] | 0.228 [0.153, 0.313] | 0.462 [0.401, 0.525] | 0.683 [0.593, 0.767] | 0.399 [0.290, 0.515] | 0.541 [0.464, 0.618] | 1.000 [1.000, 1.000] |

每个数字是 `mean [95% CI]`；CI 重采样 case（不是 session），三个 policy 共用同一批
重采样 case。`answer_first` 不追问，memo 只基于开场白；`gate_only` 先问 6 轮再写 memo；
`full` 问 9 轮并附事实来源/核验段。

## 4. 七个指标（官方定义，未改）

| 指标 | 官方字段 | 口径 |
|---|---|---|
| Fact Coverage | `discovery_rate` | 被 memo 覆盖的 case facts / 全部 facts |
| Inquiry | `EAS` | expected-action rubric 的 0/1 均值 |
| Elicitation | derived | (Fact Coverage + Inquiry) / 2 |
| Fact Resolution | `absolute_accuracy` | 方向正确的 facts / 全部 facts |
| Issue Resolution | `MES` | memo-expectation rubric 的 0/1 均值 |
| Resolution | derived | (Fact Resolution + Issue Resolution) / 2 |
| Fidelity | `grounding_rate` | grounded claims / total claims |

实现路径：`external/dlawbench/upstream/src/dlawbench/evaluate.py` +
`external/dlawbench/upstream/scripts/metrics.py`，均为 pinned commit 的字节级拷贝
（`VENDORED.json` 有 sha256，`verify.py` 会重算）。`FFS` 只作格式过滤，不进主表。

## 5. 为什么 judge 是确定性的

本机没有配置任何 LLM API key，无法调用 DLawBench 官方 LLM judge。为了先证明
pipeline 通，`judge.py` 用同一份官方 prompt（rubric 文本、对话记录、memo）做词面
rubric 匹配，返回官方 JSON schema；`evaluate.py` 的公式与分母不变。

因此：

- **绝对分数不可与官方榜单比较**，只能看同一 judge 下三个 policy 的相对差异；
- `Fidelity` 在本轮饱和为 1.000：三份 memo 的事实句全部来自对话原文，规则层没有
  生成新的日期/金额，这个指标在本设置下不具区分度，保留是为了七项齐全；
- 若要跑真实 LLM judge，设置 `OPENAI_BASE_URL`/`OPENAI_API_KEY` 后加
  `--judge-model <model>` 即可（默认仍是 `lexflow-rubric-judge`）：

```bash
OPENAI_BASE_URL=https://api.deepseek.com/v1 OPENAI_API_KEY=sk-... \
python external/dlawbench/run.py --n-cases 30 --judge-model deepseek-chat
```

## 6. shim 边界（没读 rubric）

`server.py` 只接收 DLawBench 发来的 OpenAI messages；`policy.py` 只用开场白和客户
回答做追问与 memo；`client_sim.py` 只读官方 client prompt 里的 `client_belief`；
`legal_library.py` 是领域级问题清单，不含任何 case 数据。`verify.py` 会静态扫描
`evaluation_criteria / expected_inquiries / memo_expectations / court_record /
actual_situation / cases_cn / case_backgrounds` 是否出现在 shim 代码里。

## 7. Caveat / 未做

- **不是官方 leaderboard**：judge、client 均为离线替身；30/264 CN cases；只跑 P_WD。
- 没有 gold、没有人工盲审、没有 LeCoDe、没有完整 provenance DAG、没有 4 personas ×
  600 sessions；legacy 12 案没有混进主表。
- `answer_first` 的 Issue Resolution 并非 0：它的 memo 仍会套用领域级法律问题清单；
  这正是“不追问也能写出一份通用分析”的基线，不代表它掌握了本案事实。
- 复核方式：`python external/dlawbench/verify.py`（18 项检查全过）。

## 8. 产物

```
external/dlawbench/server.py        # OpenAI-compatible shim
external/dlawbench/run.py           # 3 policies 顺序跑 + 官方评分 + CSV + CI
external/dlawbench/policy.py        # answer_first / gate_only / full
external/dlawbench/client_sim.py    # 确定性 P_WD client（替身）
external/dlawbench/judge.py         # 官方 prompt 的确定性 judge（替身）
external/dlawbench/verify.py        # 验收自检
external/dlawbench/upstream/        # DLawBench pinned subset + VENDORED.json
runs/external/<policy>/session_*.json
runs/external/summary.md            # 3×7 表 + 95% CI
runs/external/scores.csv            # 逐 session
runs/external/leaderboard.md        # 按 Elicitation 排序的 mini leaderboard
runs/external/run_manifest.json     # commit / license / n / hashes / command
```
