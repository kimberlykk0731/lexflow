# LexFlow × DLawBench — adapted external evaluation

> **Adapted run, not an official leaderboard entry.**  The lawyer is the LexFlow
> policy shim; the client and judge are deterministic offline stand-ins. Official
> DLawBench rubric text, metric formulas and denominators are used unchanged, but
> absolute scores are not comparable to the DLawBench leaderboard.

- Generated: `2026-11-24T15:11:54+08:00`
- DLawBench: `https://github.com/SKYLENAGE-AI/DLawBench` @ `9f6325f29f07b296fac110a6e1880bdd5d9ca538` (MIT code / CC BY 4.0 data)
- LexFlow: `99111d97dcf5eb7af42556aeb0d6bf32a9c82298` (dirty working tree)
- Cases: 30 Chinese-law cases from `cases_cn.jsonl` (case_cn_0001, case_cn_0002, case_cn_0003…)
- Persona(s): P_WD · max turns: 10
- Sessions: 90 (3 policies × 30 cases)
- Status: memo_submitted=90
- Judge: `lexflow-rubric-judge` — deterministic lexical rubric matcher, stand-in for the official LLM judge
- CI: 5000 cluster-bootstrap resamples by case, 95% percentile, seed 20261124

## 3 × 7 table

| Policy | n | Fact Coverage | Inquiry | Elicitation | Fact Resolution | Issue Resolution | Resolution | Fidelity |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| answer_first | 30 | 0.016 [0.002, 0.033] | 0.000 [0.000, 0.000] | 0.008 [0.001, 0.017] | 0.016 [0.002, 0.033] | 0.264 [0.162, 0.378] | 0.140 [0.089, 0.198] | 1.000 [1.000, 1.000] |
| gate_only | 30 | 0.628 [0.531, 0.717] | 0.216 [0.142, 0.300] | 0.422 [0.356, 0.486] | 0.614 [0.518, 0.705] | 0.339 [0.233, 0.456] | 0.477 [0.403, 0.549] | 1.000 [1.000, 1.000] |
| full | 30 | 0.696 [0.605, 0.780] | 0.228 [0.153, 0.313] | 0.462 [0.401, 0.525] | 0.683 [0.593, 0.767] | 0.359 [0.254, 0.473] | 0.521 [0.447, 0.595] | 1.000 [1.000, 1.000] |

Each cell is `mean [95% CI]`. The CI resamples cases (clusters), not sessions,
so the three policies are evaluated on the same resampled case set.

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

- `answer_first` never asks a question: memo from the opening message only.
- `gate_only` runs LexFlow's sufficiency gate, asks the domain intake checklist,
  then writes the memo without provenance/verification sections.
- `full` adds per-fact provenance and an explicit verification section, and
  marks unresolved information gaps.
- The shim only sees the DLawBench messages. It never opens the case file,
  the hidden facts, or `evaluation_criteria`.
- The deterministic client reveals a `client_belief` only when the lawyer asks
  about the same topic; it is not the official LLM client.
- Because the judge is lexical, treat **within-run policy deltas** as the signal
  and absolute values as pipeline diagnostics only.

## Reproduce

```bash
python external/dlawbench/run.py --n-cases 30 --personas P_WD
```

## Files

- `runs/external/<policy>/session_*.json` — full dialogue + evaluation
- `runs/external/scores.csv` — one row per session
- `runs/external/run_manifest.json` — commits, licenses, n, hashes, command
- `runs/external/leaderboard.md` — optional mini leaderboard by Elicitation
- `docs/EXTERNAL_EVAL.md` — one-page method and caveats
