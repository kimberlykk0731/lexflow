# LexFlow × DLawBench — real-agent case study

> **Adapted run, not an official leaderboard entry.**  The lawyer is the real `ConsultationAgent`, restricted to the in-schema cases; the client and judge are deterministic offline stand-ins. Official DLawBench rubric text, metric formulas and denominators are used unchanged, but absolute scores are not comparable to the DLawBench leaderboard.

- Lawyer mode: `agent`
- Generated: `2026-11-25T22:12:51+08:00`
- DLawBench: `https://github.com/SKYLENAGE-AI/DLawBench` @ `9f6325f29f07b296fac110a6e1880bdd5d9ca538` (MIT code / CC BY 4.0 data)
- LexFlow: `4aeec32a0fd0bc3102cf063d9c03941586f40dcd`
- Cases: 3 Chinese-law cases from `cases_cn.jsonl` (case_cn_0006, case_cn_0024, case_cn_0025)
- Persona(s): P_WD · max turns: 10
- Sessions: 9 (3 policies × 3 cases)
- Status: memo_submitted=9
- Judge: `lexflow-rubric-judge` — deterministic lexical rubric matcher, stand-in for the official LLM judge
- CI: 5000 cluster-bootstrap resamples by case, 95% percentile, seed 20261124

## 3 × 7 table

| Policy | n | Fact Coverage | Inquiry | Elicitation | Fact Resolution | Issue Resolution | Resolution | Fidelity |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| answer_first | 3 | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] |
| gate_only | 3 | 0.000 [0.000, 0.000] | 0.133 [0.000, 0.400] | 0.067 [0.000, 0.200] | 0.000 [0.000, 0.000] | 0.094 [0.000, 0.200] | 0.047 [0.000, 0.100] | 0.143 [0.000, 0.429] |
| full | 3 | 0.000 [0.000, 0.000] | 0.133 [0.000, 0.400] | 0.067 [0.000, 0.200] | 0.000 [0.000, 0.000] | 0.094 [0.000, 0.200] | 0.047 [0.000, 0.100] | 0.143 [0.000, 0.429] |

Each cell is `mean [95% CI]`. The CI resamples cases (clusters), not sessions,
so the 3 policies are evaluated on the same resampled case set.

## Official definitions (unchanged)

| Metric | Official input | Formula |
|---|---|---|
| Fact Coverage | `discovery_rate` | covered facts / all case facts |
| Inquiry | `EAS` | mean expected-action rubric score (0/1) |
| Elicitation | derived | (Fact Coverage + Inquiry) / 2 |
| Fact Resolution | `absolute_accuracy` | correct facts / all case facts |
| Issue Resolution | `MES` | mean memo-expectation rubric score (0/1) |
| Resolution | derived | (Fact Resolution + Issue Resolution) / 2 |
| Fidelity | `grounding_rate` | grounded claims / total claims |

Source: `external/dlawbench/upstream/scripts/metrics.py` and
`external/dlawbench/upstream/src/dlawbench/evaluate.py` at the pinned commit.
`FFS` (required sections) is a format filter, not a ranking metric.

## How to read this

- This is a real `ConsultationAgent` case study, not the 30-case simulation.
- `answer_first` disables the gate; `gate_only` enables it without verification;
  `full` enables gate, verification and repair.
- The case study is limited to the 3 cases that fall inside LexFlow's labour/tort
  schemas; Fact Coverage is near zero because the benchmark facts do not match the
  schema fields. Treat this as a schema-boundary result, not a capability score.

## Reproduce

```bash
python external/dlawbench/run.py --n-cases 3 --personas P_WD --lawyer-mode agent
```

## Files

- `runs/external/<policy>/session_*.json` — full dialogue + evaluation
- `runs/external/scores.csv` — one row per session
- `runs/external/run_manifest.json` — commits, licenses, n, hashes, command
- `runs/external/leaderboard.md` — optional mini leaderboard by Elicitation
- `docs/EXTERNAL_EVAL.md` — one-page method and caveats
