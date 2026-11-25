# LexFlow × DLawBench — fixed-checklist protocol simulation

> **Adapted run, not an official leaderboard entry.**  The lawyer is a fixed-domain questionnaire simulation, not the LexFlow element-schema gate; the client and judge are deterministic offline stand-ins. Official DLawBench rubric text, metric formulas and denominators are used unchanged, but absolute scores are not comparable to the DLawBench leaderboard.

- Lawyer mode: `simulation`
- Generated: `2026-11-25T18:00:30+08:00`
- DLawBench: `https://github.com/SKYLENAGE-AI/DLawBench` @ `9f6325f29f07b296fac110a6e1880bdd5d9ca538` (MIT code / CC BY 4.0 data)
- LexFlow: `7cb291102495ce3a975c85415c94b41bb35f4fce` (dirty working tree)
- Cases: 30 Chinese-law cases from `cases_cn.jsonl` (case_cn_0001, case_cn_0002, case_cn_0003…)
- Persona(s): P_WD · max turns: 10
- Sessions: 30 (1 policies × 30 cases)
- Status: memo_submitted=30
- Judge: `lexflow-rubric-judge` — deterministic lexical rubric matcher, stand-in for the official LLM judge
- CI: 5000 cluster-bootstrap resamples by case, 95% percentile, seed 20261124

## 3 × 7 table

| Policy | n | Fact Coverage | Inquiry | Elicitation | Fact Resolution | Issue Resolution | Resolution | Fidelity |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| checklist_9 | 30 | 0.687 [0.594, 0.773] | 0.228 [0.153, 0.313] | 0.457 [0.394, 0.522] | 0.673 [0.581, 0.760] | 0.384 [0.272, 0.504] | 0.529 [0.452, 0.608] | 1.000 [1.000, 1.000] |

Each cell is `mean [95% CI]`. The CI resamples cases (clusters), not sessions,
so the 1 policies are evaluated on the same resampled case set.

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
- `gate_only` runs a fixed six-question domain checklist, not LexFlow's
  element-schema gate.
- `checklist_9` adds three questions without provenance/verification; `full` adds
  provenance and an explicit verification section.
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
