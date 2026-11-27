# LexFlow: Ask Before You Answer

**A claim-routed, element-gated legal consultation agent for Chinese labour disputes**

NLP course project report (draft, 2026-11)

---

## Abstract

Legal question answering systems usually assume that the facts are already complete and stable. Real consultations are neither. A client says "my company fired me" and omits the dismissal date, whether the handbook was publicised, and whether the union was notified; each of these facts can change the conclusion from a 2N unlawful-dismissal claim to a lawful no-compensation dismissal, or to a claim already barred by the one-year arbitration limitation period.

This report describes the second iteration of LexFlow. The first iteration supported only two flat claim schemas and silently fell back to `labor_dismissal` when classification failed; a question about a traffic accident could therefore be answered with a labour-arbitration questionnaire. The redesign replaces the flat fallback with (i) a transparent router that can say "out of scope" or "I need to know which kind of problem this is", (ii) twelve labour claims that can run together, (iii) an element tree that traverses claim → element → fact → proof and suppresses branches whose conditions are not met, (iv) a value-of-information (VOI) heuristic that ranks questions by how many distinct outcomes they can distinguish, and (v) a chunk-level BM25 retrieval layer over court and human-resources practice notes, in addition to the version-aware statute retriever.

On 12 scripted consultations covering labour dismissal and traffic-accident injury, gating raises critical-fact coverage from 59.1% to 100% and reduces premature advice from 58.3% to 0%; versioned memory reduces stale conclusions after a correction from 100% to 0%. The current table is a deterministic mock run: the rule layer and the gold answers are authored by the same person, so high agreement on illegality and amount is a consistency result, not evidence of legal capability. We do not claim general legal capability or a new benchmark. We do describe a concrete plan for an AI-generated multi-turn labour benchmark, in which a generator writes cases, a symbolic oracle computes the gold, a second model reviews the case, and humans only spot-check 10–20%.

---

## 1. Introduction

A legal consultation is not a retrieval problem with a natural-language interface. It is a sequence of decisions: which facts matter, which are missing, which version of the law applies, what can be concluded now, and what must wait for evidence. A search assistant answers the first message; a consultation agent has to decide whether the first message is answerable at all.

The first version of LexFlow made this decision with a single alias-counting classifier and a flat questionnaire per cause of action. The failure mode was instructive. The alias list for traffic injury did not contain "交通肇事" (traffic accident), the classifier scored zero, and the code fell back to `labor_dismissal`:

```python
state.case_type = ranked[0][0] if ranked and ranked[0][1] > 0 else "labor_dismissal"
```

The agent then asked about the dismissal date, the employee handbook, and the union — all labour questions — for a traffic accident. Adding one alias would fix that sentence and fail on the next one. The real problem was threefold: a silent default, one flat schema per cause of action, and one active claim at a time.

This report asks four questions:

- **RQ1.** Can a claim router avoid silent defaults and support several active claims in one consultation, without sacrificing the auditability of the rule layer?
- **RQ2.** Does an element tree with conditional branches reduce irrelevant questions and make the reasoning path inspectable, compared with a flat priority list?
- **RQ3.** Can a value-of-information heuristic rank questions by their ability to change the outcome, and can that ranking be evaluated honestly?
- **RQ4.** Can court and human-resources practice notes be retrieved with chunk-level citations (RAG) without letting the model invent legal authority?

The technical points, all of which are implemented and visible in the current demo, are:

- **neuro-symbolic decomposition**: the LLM extracts facts and rewrites questions; the symbolic layer decides which element to ask about, which article applies, and how much is owed;
- **analysis path**: claim basis → element → fact → proof, rendered in the CLI, the web UI and the memorandum;
- **value-of-information (VOI) question ranking**: enumerate plausible answers, run the symbolic layer, and count how many distinct outcomes a question can distinguish;
- **temporal RAG**: a version-aware statute retriever that filters by the law in force on the case date;
- **chunk-level practical-note RAG**: BM25 over court/MOHRSS note chunks with topic filtering, a relative score cutoff, and source citations;
- **incremental truth maintenance**: versioned facts, dependency-aware cache invalidation, and stale-conclusion checks;
- **claim-to-evidence verification with bounded repair**;
- **multi-claim composition and an honest out-of-scope path**.

The scope is deliberately bounded: Chinese labour law (twelve claims) plus traffic-accident personal injury. The contribution is the mechanism and its measurement, not a new base model or a new benchmark.

---

## 2. Related work

**Labour-law benchmarks.** LabourLawBench (Lan et al., 2026) is the closest Chinese labour-law benchmark: 12 tasks (statute recitation, knowledge QA, case-type prediction, welfare-compensation prediction, NER, claim mining, disputed-issue mining, statute prediction, case analysis) across 12 labour case types, built from Jiangsu judgments, national examination questions and statutes [11]. It is single-turn and task-specific; it does not measure whether an agent asks the right follow-up questions or revises a conclusion after a correction. CLC-UKET (Xie et al., 2024) is the UK counterpart: about 19,090 Employment Tribunal cases with legal annotations, used for case-outcome prediction [12]. It is English and outcome-oriented, but its annotation pipeline and human baseline are a useful methodological reference.

**Consultation benchmarks.** LeCoDe (ACL 2026) collects 3,696 real consultation dialogues and shows that strong models elicit only about 36% of annotated key facts before giving advice [1]. DLawBench (2026) pairs 461 Chinese and U.S. cases with client-belief and court-record views, four client personas, and expert inquiry/resolution rubrics; its best model reaches 0.562 on consultation-grounded legal reasoning and exhibits legal sycophancy [2]. LexRAG (SIGIR 2025) evaluates multi-turn retrieval of legal articles [7]. None is labour-specific and multi-turn at the same time.

**Hallucination and verification.** LexAgentHallu (EMNLP 2026) profiles hallucinations along agent trajectories and reports a right-answer-wrong-reason effect [3]. Harvey's Legal Agent Benchmark and its independent reimplementation add hallucination checks and a three-judge rubric panel [6, 9]. These works motivate mechanical checks on citations and numbers rather than fluency judgments.

**Temporal validity.** LegalSearch-R1 (NLLP 2026) shows that legal agents are temporally biased toward their training cutoff and rarely encode temporal constraints in queries; temporal-indexed RL improves consistency substantially [4]. We do not train; we make the applicable version a property of retrieval and verification.

**Environments and tools.** LegalAgentBench (ACL 2025) provides 300 Chinese tasks and 37 tools [8]; LegalWorld (EMNLP 2026) models civil litigation as a five-stage causal state chain [5]. LexFlow is much smaller: an explicit state machine, a local statute corpus, and a claim/element schema.

The gap we target is narrow but real: existing benchmarks evaluate a consultation in which the fact pattern is fixed. None measures whether a conclusion is revised when the client corrects a fact, and none treats the statute version as part of the agent's state. For Chinese labour disputes specifically, LabourLawBench covers legal knowledge but not multi-turn intake; LeCoDe covers multi-turn intake but is not labour-specific and requires an application. That gap motivates both the system design and the benchmark plan in Section 7.

---

## 3. System

### 3.1 Overview

The control flow is deterministic:

```
input
  → router: labour (multi-claim) / tort / out-of-scope / unclear
  → fact extraction (LLM first, rule fallback; only fields declared by active claims)
  → element gate: claim → element → fact → proof; conditional branches pruned
  → research: version-filtered statute retrieval + practical-note RAG
  → deterministic analyser and calculator per claim
  → memo: conclusion / analysis path / facts / issues / RAG notes / gaps / evidence
  → verifier: citation existence, version validity, quote match, number check, fact freshness
  → bounded repair, then re-verify
```

The model is used for fact extraction, optional routing disambiguation, and optional question rewriting. It does not choose citations, compute amounts, or decide when to stop asking. Those decisions are made by the rule layer.

### 3.2 Routing and claim scope

`src/lexflow/router.py` returns one of four actions: `proceed`, `clarify`, `out_of_scope`, or `switch`. It never defaults to a substantive area.

- Labour is multi-label: one message can activate dismissal, unpaid wages and overtime at the same time.
- Traffic injury is matched by a separate claim (`tort_injury`) with aliases including "交通肇事", "撞了", "追尾", "交强险" and "事故认定书".
- Marriage, loans, housing, ordinary contracts, criminal, consumer, IP and administrative matters are detected as out of scope and answered honestly; the agent says what it does cover instead of forcing a labour template.
- A weak signal such as "公司" alone produces a clarification question that lists the labour claim types; it does not select dismissal by default.
- Short answers inside a consultation ("2026-03-15") keep the current claims instead of re-routing.
- An explicit switch ("不是劳动，是交通事故") resets the claims and the question counters.

The schema now has twelve labour claims plus traffic injury:

| Claim | Typical question | Main calculation / judgment |
|---|---|---|
| `labor_dismissal` | dismissal, redundancy, forced resignation, non-renewal | N / N+1 / 2N, illegality, limitation |
| `labor_wage` | unpaid wages, commission, bonus, pay cut | amount owed, art. 85 additional compensation |
| `labor_overtime` | 996, weekend work, invisible overtime | 150% / 200% / 300%, special working hours |
| `labor_double_pay` | no written contract | up to 11 months, Interpretation II arts. 6–7 |
| `labor_work_injury` | injury recognition, disability benefits | 30-day / 1-year windows, one-time subsidy |
| `labor_social_insurance` | contribution gaps, back-payment, forced resignation | administrative back-payment vs arbitration |
| `labor_annual_leave` | unused annual leave | 5/10/15 days, 200% extra |
| `labor_noncompete` | compensation, liquidated damages, release | 30%, 2-year cap, 3-month non-payment |
| `labor_maternity` | dismissal during pregnancy, maternity pay | 2N, maternity-insurance top-up |
| `labor_dispatch` | dispatch, outsourcing, gig work | subordination, responsible entity |
| `labor_contract` | probation, transfer, pay cut | probation limits, written variation |
| `labor_procedure` | final award, jurisdiction, limitation | 45+15 days, 15-day appeal |

The statute corpus grew from 15 instruments / 1,340 articles to 26 instruments / 1,810 articles. New instruments include the 2025 Interpretation II of the labour-dispute judicial interpretation, the Work-Injury Insurance Regulation, the Social Insurance Law, the Annual Leave Regulation, the Wage Payment Regulation, the Special Provisions on Female Employees, the Labour Supervision Regulation, the Trade Union Law, the Migrant-Wage Regulation and the Unemployment Insurance Regulation.

### 3.3 Element tree and analysis path

`data/elements.json` is generated by `tools/build_elements.py`. It has two layers:

- `facts`: a shared catalogue of 90 facts, one canonical question per fact;
- `claims`: 13 claims (12 labour + tort), each referencing facts and organising them into `elements` with a `requires` condition, a `why`, and a `proof` list.

An element is a legal requirement, not a form section. For dismissal:

| Element | Facts | Condition |
|---|---|---|
| Relationship exists | start date, employer, written contract | always |
| Dismissal act and date | dismissal date, who initiated | always |
| Illegality / procedure | reason, handbook, misconduct evidence, union, training, notice | serious misconduct / incompetence / objective change / redundancy branches |
| Remedy and amount | claim type, monthly wage, compensation paid | always |
| Limitation and procedure | arbitration filed, deadline awareness | after core facts |

Conditional criticality is explicit. For example:

```json
{"key": "training_or_transfer", "critical_if": [{"stated_reason": "不胜任工作"}]}
{"key": "union_notified", "critical_if": [{"who_initiated__in": ["单位单方解除", "被迫解除"]}]}
```

When the client says "I was dismissed for serious misconduct", the agent asks about handbook publicity, misconduct evidence and the democratic procedure. When the client says "incompetence", it asks about training/transfer and pay in lieu of notice. When the client says "I resigned", it stops asking about the union and 2N, and asks whether this was a forced resignation under Article 38.

The same tree is rendered as an **analysis path** in three places: the CLI demo prints it after every turn (and `/path` shows it on demand), the Streamlit UI has an "Analysis path" tab, and the memorandum's second section is the path. The path includes the **claim basis** (for dismissal: Arts. 48, 87, 46, 47) and the possible remedies (continue performance / 2N / N / N+1 / 0). This makes the "why" behind each question visible to the user and to a reviewer.

### 3.4 Dynamic question selection: static leverage plus VOI

Questions are first filtered by the element tree: only facts on an active branch, only critical facts, only facts that are not already known or explicitly unknown. The remaining frontier is ordered by a combination of legal priority and a lightweight **value-of-information** heuristic (`src/lexflow/voi.py`):

1. take the frontier questions;
2. enumerate plausible answers (enum options, a few number/date bands);
3. substitute each answer into the deterministic rule layer;
4. count how many distinct outcome signatures the question can distinguish (e.g. "unlawful / lawful", "2N / N / 0", "limitation expired / not expired");
5. rank questions by the number of distinguishable outcomes, weighted by static legal priority.

The user sees the result as an extra line: "Information value: answering this can distinguish 2 possible outcomes (other facts held fixed)". A question that cannot change any outcome receives zero VOI. This is not a full Bayesian belief update; it is a model-based active-interrogation heuristic that uses the symbolic layer as a world model. It is inspectable, requires no training, and cannot disagree with the rule layer.

When all remaining critical questions are outcome-neutral and no "must-ask" fact (claim type, dates, wage, amount, duration) is left, the agent may stop and answer with explicit gaps. In the 12 scripted cases this early stop rarely triggers; the measured effect is reported in Section 5.6, including the honest null result.

### 3.5 Version-aware statute retrieval and practical-note RAG

The statute corpus stores `valid_from` and `valid_to` for every article. Retrieval is dependency-free BM25 over character bigrams with a small legal synonym table; results can be restricted to the version in force on the case date. This is a temporal constraint on RAG that most legal retrieval systems omit: relevance is not enough, the article must also be the one in force at the time.

Court and human-resources practice notes are stored separately in `data/knowledge/practice_notes.json`: 16 notes from the Supreme People's Court, MOHRSS, the People's Court Daily, the 12348 legal service platform, Beijing human-resources authorities and statute-based checklists. Each note has a publisher, date, URL, topics and 3–6 paraphrased points; long copyrighted passages are not copied.

The note retriever is a chunk-level RAG pipeline (`src/lexflow/knowledge.py`):

1. split each note into chunks (title, each point, caveat);
2. build a Chinese bigram BM25 index;
3. build the query from the active claim labels and the identified issues;
4. hard-filter chunks by claim topic, then rank by BM25 and apply a relative score cutoff;
5. pass the matched chunk plus publisher, date, URL and BM25 score into the memorandum.

The memo section is labelled "Practical notes (RAG retrieval)". The system does not ask an LLM to summarise the notes freely; it retrieves and cites them, which avoids inventing a court holding. The retriever is sparse and dependency-free; the interface is deliberately compatible with a future hybrid dense + sparse + rerank upgrade.

### 3.6 Versioned memory and cache

Facts are stored with provenance (`user-stated`, `documentary`, `verified`, `unknown`), a revision number, and a superseded chain. A new statement does not silently overwrite a documentary record; a conflict is surfaced and the user is asked to check the original. Each change increments the case revision and invalidates only the cache entries whose declared fact dependencies intersect the changed keys. Public statute lookups have no fact dependencies and remain reusable.

This is a simplified incremental truth-maintenance mechanism: the system records which facts each conclusion depends on, and propagates a correction only to those conclusions.

### 3.7 Verification and bounded repair

Every conclusion carries article IDs, a quoted span, dependent facts, and the case revision used. The verifier emits typed defects: `MISSING_SOURCE`, `UNKNOWN_SOURCE`, `VERSION_NOT_IN_FORCE`, `QUOTE_MISMATCH`, `SUPERSEDED_FACT`, `MISSING_DEPENDENCY`, `UNVERIFIED_NUMBER`. Repair is bounded to one cycle: replace a citation with the version in force, drop a mismatched quote, or drop an unknown source. Unresolved defects remain visible in the memorandum. The verifier is mechanical, not an LLM judge.

### 3.8 Worker-facing artefacts

The chat answer is a summary; the system also produces the artefacts a worker can use:

| Artefact | What it contains |
|---|---|
| Legal opinion | facts, legal analysis, conclusion, requests, risks, declaration |
| Arbitration application | request items with computed amounts, facts, evidence list, addressee |
| Evidence list | element-by-element checklist with blanks |
| Demand letter | requests, deadline, consequences, signature block |
| Forced-resignation notice | Article 38 grounds, delivery-proof warning |
| Arbitration vs litigation | forum, limitation, hearing time, fees, finality, enforcement, pros/cons |
| Worker rights map | before/during/after employment and dispute stages, plus complaint channels |
| Deadline card | arbitration limitation, work-injury 30-day/1-year windows, annual leave, non-compete |
| Contract audit | probation, non-compete, liquidated damages, social-insurance waiver, 996, unilateral transfer |

All documents are drafts with blanks for identity details; the system never invents a party name, amount, case number or court.

### 3.9 Interface

A Streamlit interface shows the conversation on the left and, on the right, the live fact table, the analysis path, the memorandum, the issue-by-issue citations, the generated documents and the execution trace. The analysis-path tab also shows the VOI ranking of the next questions.

---

## 4. Evaluation

The main results in Section 5 are fully automated: a scripted client, a hidden fact sheet, hand-computed gold answers, and metrics computed in code. Human review is a supplementary check on memorandum quality; it is not the source of any number in the main table, and no public benchmark was run. Section 7 explains why and what we plan instead.

### 4.1 Controlled consultation protocol

We construct 12 scripted cases (7 labour, 5 tort). Each case contains an opening message, a hidden fact sheet, a set of critical facts, hand-computed gold conclusions, and — for two cases — a correction delivered after the first memorandum. A scripted client answers only the fields it is asked about and says "I don't know" otherwise. This removes human annotation from the loop and makes every run reproducible.

The labour cases cover handbook not publicised, handbook publicised, incompetence without training, compliant incompetence dismissal, negotiated termination, an expired limitation period, and a corrected dismissal date. The tort cases cover accidents on both sides of the 2022-05-01 interpretation boundary, a 2020 accident governed by the 2003 interpretation, and a corrected accident date that crosses the boundary.

The 12 cases were written for the two-claim version. The twelve new labour claims are covered by unit tests and smoke dialogues, but not yet by the scripted protocol; extending the protocol is the first task of the benchmark plan in Section 7.

### 4.2 Conditions and metrics

Five conditions use the same model, tools, and budget: `answer_first` (no gate, no verification), `gate_only`, `full` (gate + verification + revision + VOI), `full_no_voi` (same as full but no VOI ordering), and `full_no_revision` (the same system, deliberately reusing the analysis produced before the correction).

Metrics are: fact coverage at memorandum time; inquiry recall over facts not volunteered in the opening; number of questions; premature-advice rate; citation support rate; agreement with hand-computed gold on illegality, amount, limitation deadline, and interpretation version; and stale-conclusion rate after correction.

Because the rule layer and the gold answers are authored by the same person, high agreement on illegality and amount is a **consistency** result, not evidence of legal capability. The informative comparisons are the behavioural ones: coverage, premature advice, citation support, and stale conclusions.

### 4.3 Verification probe and cache replay

A guardrail that never fires is not evidence. We inject five defect types into clean analyses: an unknown article, a version not in force, a fabricated quote, a superseded dependency, and an altered amount. We also replay a turn with no new facts with the cache on and off, and correct one fact to observe which entries are invalidated.

---

## 5. Results

### 5.1 Main ablation

The current table is a **mock** run: the LLM is disabled and the rule layer is deterministic. It is a regression and mechanism check, not a model-capability result. The earlier API run (149k input / 11k output tokens, about RMB 0.17) was on the old two-claim architecture and is not comparable; an API rerun is pending.

| Condition | Coverage | Inquiry recall | Questions | Premature | Citation support | Illegality | Amount | Limitation | Version | Stale |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| answer_first | 59.1% | 41.7% | 0.0 | 58.3% | 83.3% | 85.7% | 0% | 50.0% | 100% | 0% |
| gate_only | 100% | 99.1% | 5.2 | 0% | 100% | 100% | 100% | 100% | 100% | 0% |
| full | 100% | 99.1% | 5.2 | 0% | 100% | 100% | 100% | 100% | 100% | 0% |
| full_no_voi | 100% | 99.1% | 5.2 | 0% | 100% | 100% | 100% | 100% | 100% | 0% |
| full_no_revision | 100% | 99.1% | 5.2 | 0% | 92.2% | 100% | 85.7% | 83.3% | 80% | 100% |

Three observations:

1. **Gating is the main driver.** Without it, the agent answers from whatever the opening contains: coverage 59.1%, premature advice 58.3%, and the compensation amount is never computable. With it, coverage reaches 100% and premature advice disappears.
2. **Verification does not change the normal path.** `gate_only` and `full` are identical because the rule layer produces valid citations; the verifier is a guardrail, not a quality booster. Its value is measured by injection.
3. **Memory is not revision.** `full_no_revision` has the same coverage but keeps the pre-correction analysis: 100% stale conclusions, 85.7% amount accuracy, 83.3% limitation accuracy, 80% version accuracy. Versioning is what turns memory into an update.

### 5.2 Verifier probe

| Defect | Injections | Detected | Rate |
|---|---:|---:|---:|
| `UNKNOWN_SOURCE` | 12 | 12 | 100% |
| `VERSION_NOT_IN_FORCE` | 12 | 12 | 100% |
| `QUOTE_MISMATCH` | 12 | 12 | 100% |
| `SUPERSEDED_FACT` | 12 | 12 | 100% |
| `UNVERIFIED_NUMBER` | 7 | 7 | 100% |

Clean analyses: 0 false positives across 12 cases.

### 5.3 Cache replay

| Scenario | Tools executed | Cache hits |
|---|---:|---:|
| Cache on, replay with no new facts | 0 | 18 |
| Cache off, same replay | 18 | 0 |
| After correcting one date | 8 | 10 |

Correcting the dismissal date invalidates one dependent cache entry; the other ten calls (public statute lookups) remain valid. This is the intended granularity: not a session-wide flush, and not a stale reuse.

### 5.4 Element-tree and routing tests

The new claim layer is covered by 48 unit tests, including:

- routing: "交通肇事" goes to tort, "我要离婚" is out of scope, "我被公司欺负了" asks for clarification rather than defaulting to dismissal;
- conditional branches: serious misconduct asks about handbook publicity but not training/transfer; incompetence asks about training and pay in lieu of notice; resignation does not ask about the union;
- calculators: overtime, double pay (11-month cap), annual leave (200% extra), non-compete (30%), work-injury disability subsidy;
- end-to-end: a dismissal consultation reaches a 2N memo; a traffic consultation never contains labour questions; unpaid wages plus overtime activates two claims;
- VOI: publicity has positive value before it is known; the democratic-procedure question becomes outcome-neutral after a publicity defect is established.

### 5.5 RAG retrieval behaviour

The practical-note retriever is evaluated qualitatively, not with a labelled retrieval set. For a dismissal query, it returns the "employer bears the burden, rules must be democratic and publicised, union procedure" note; for overtime, the Shanghai No. 2 Intermediate Court note on invisible overtime; for annual leave, the 200% note; for non-compete, the typical-case and Interpretation II notes. The relative score cutoff prevents generic "dismissal / 2N" passages from crowding out the specific note. A labelled retrieval evaluation is future work.

### 5.6 VOI ordering

In the 12 scripted cases, `full` and `full_no_voi` both average 5.2 questions, with identical coverage and accuracy. The VOI heuristic changes the order and the explanation ("this question can distinguish 2 outcomes") but does not reduce the number of questions in this sample. The early-stop rule only fires when all remaining critical questions are outcome-neutral and no must-ask fact is left; that situation is rare in the scripted cases. We therefore report a **null efficiency result** and do not claim that VOI saves questions. A targeted experiment with must-ask facts satisfied and only outcome-neutral residuals is future work.

---

## 6. Error analysis

**The routing bug that motivated the redesign.** The first version classified "交通肇事" as zero and fell back to `labor_dismissal`, so the agent asked about dismissal dates, handbooks and unions. The fix is not an extra alias: the new router can return `clarify` or `out_of_scope`, and labour is multi-label. The regression test `test_traffic_accident_alias_is_tort` now guards this case.

**The month-precision bug.** The first API pass failed L06's limitation check: the client said "2024年1月", the model normalised it to `2024-01-01`, and the gate treated it as a day-precision fact, so the deadline became 2025-01-01 instead of 2025-01-05. The fix was to recover month precision from the original text and ask for the exact day. This illustrates the project's thesis: the dangerous error is not a wrong sentence, but a wrong state that later reasoning treats as certain.

**Same-author gold.** The rule layer and the gold answers were written by the same person. The 100% agreement on illegality, amount, limitation, and version is therefore a consistency check, not a capability result. The behavioural deltas (coverage, premature advice, stale conclusions) are less exposed to this criticism because they are defined by the protocol, not by the rules.

**Verifier blind spots.** It cannot detect a legally wrong but valid-version citation, a gap in argument, or a non-comparable precedent. It checks existence, validity, quote match, number consistency, and fact freshness; nothing more.

**RAG blind spots.** BM25 with character bigrams has no semantic generalisation; a query about "被开除了" relies on the synonym table to reach "解除". The relative cutoff is a heuristic. A wrong but topically related note can still be retrieved; the memo shows the source and score so a human can reject it.

**VOI approximation.** The heuristic enumerates single-fact answers holding other facts fixed. It does not model joint information or question cost, and it does not calibrate probabilities. It is a ranking aid, not a decision-theoretic guarantee.

**Scripted client too cooperative.** Real clients are emotional, inconsistent, and sometimes misleading. The protocol does not test sycophancy or adversarial disclosure; DLawBench's four personas are the natural next step.

---

## 7. External evaluation and an AI-generated benchmark plan

### 7.1 Why LabourLawBench is not the main table

LabourLawBench is the closest Chinese labour-law benchmark, but it is single-turn and task-specific. Running it would measure statute recall, case-type classification or case analysis, not the mechanisms this project is about: element gating, follow-up questions, correction handling, and citation verification. It is a useful **knowledge-layer** evaluation and a future external-validity check, not a substitute for the consultation protocol. The dataset is CC BY 4.0 and requires a free IEEE DataPort login [11].

CLC-UKET is the UK employment-tribunal dataset, with about 19,090 cases and 14,582 outcome-prediction instances [12]. It is not Chinese law and not a consultation benchmark, but its annotation pipeline (LLM-assisted annotation with legal experts) and human baseline are a methodological reference.

LeCoDe (ACL 2026) is the closest multi-turn consultation benchmark, but it is not labour-specific and requires an application [1]. DLawBench has four client personas and is closer to a consultation, but its Chinese subset is not labour-specific and its lawyer policy is general-purpose [2].

### 7.2 The gap

There is, to our knowledge, no public Chinese benchmark that is **both labour-specific and multi-turn**: it should provide hidden facts, test whether the agent asks for the right ones, and test whether the agent revises after a correction. LabourLawBench covers the law but not the dialogue; LeCoDe covers the dialogue but not labour; CLC-UKET covers employment tribunals but in the UK and for outcome prediction. This is the gap the project can address.

### 7.3 AI-generated benchmark plan (not yet implemented)

Manual gold annotation is expensive and is exactly what the user of this project asked to avoid. We propose a pipeline in which AI does most of the work and humans only spot-check:

1. **Seed sampling.** Sample claim type, element branch, amount band (around the 12× local minimum wage finality threshold), date band (around 2022-05-01 and 2025-09-01), and single- vs multi-claim composition.
2. **Generator LLM.** Write the case: hidden fact sheet, colloquial opening (possibly with a wrong legal understanding), and one correction.
3. **Symbolic oracle.** Substitute the hidden facts into `rules.analyse_many` and compute the gold illegality/amount/limitation/version. If the rule layer cannot produce a determinate result, discard and regenerate. The generator never writes the gold.
4. **Code filters.** Check date order, enum validity, branch coverage, no answer leakage in the opening, correction actually changes the outcome, and de-duplicate by claim + fact combination.
5. **Reviewer LLM.** A second model judges whether the case looks like a real consultation and whether it is legally coherent; failures are regenerated or flagged.
6. **Scripted client.** Reuse `eval/protocol.py`: answer only the asked keys, say "I don't know" otherwise, inject the correction after the first memo.
7. **Human spot-check.** Review 10–20% of cases for realism and ambiguity; do not rewrite the gold.

Acceptance target: 30–50 cases, at least two per claim, every `critical_if` branch covered at least once, at least eight multi-claim cases, at least ten correction cases, and every gold reproducible by the symbolic oracle at the recorded code/corpus version. The risks are distribution shift from synthetic cases, gold leakage, and the rule layer's own simplifications; the mitigations are real statutes and practice notes as seeds, code filters, a separate reviewer model, and a small human audit.

---

## 8. Limitations

1. The scripted evaluation still covers only the original two claim families; the twelve labour claims are unit-tested and smoke-tested, not yet benchmarked.
2. Limitation start dates are simplified to the dismissal/accident date; in practice they may be the date of service, diagnosis, or disability assessment.
3. The three-times local average wage cap and the twelve-year cap are documented but not computed; local statistics are not integrated.
4. Tort damages are not computed: disability grade, medical receipts, and local income data are required.
5. The union-notification rule assumes an established union; the conclusion says so.
6. No case-law retrieval; the corpus contains statutes, judicial interpretations and practice notes, not judgments.
7. The current main table is a mock run; the earlier API numbers are not comparable after the redesign. An API rerun is pending.
8. The RAG retriever is sparse; there is no dense embedding or reranker.
9. VOI is a single-fact enumeration heuristic; the 12-case experiment shows no reduction in question count.
10. No statistical significance is claimed; 12 cases and a scripted client are a mechanism check.

---

## 9. Conclusion and future work

LexFlow shows that a small, deterministic legal layer plus a language model can make a consultation agent's uncertainty inspectable: it routes before answering, traverses a claim/element tree, asks for the fact that can change the outcome, cites the version in force, retrieves practical notes with sources, and revises when the facts change. The redesign from two flat schemas to twelve claims and an element tree is the main engineering contribution; the VOI ranking and the chunk-level practical-note RAG are the main technical mechanisms that are visible in the demo.

The next steps are concrete:

1. implement the AI-generated benchmark pipeline in Section 7.3 and run 30–50 cases;
2. rerun the external API experiment on the new architecture and report cost/latency;
3. add a labelled retrieval set for the practical-note RAG and compare BM25 with a hybrid retriever;
4. run a targeted VOI experiment with must-ask facts satisfied and outcome-neutral residuals;
5. extend the scripted protocol to all twelve claims, then add DLawBench personas and a human blind review.

The longer-term direction is to use the element schema and the verifier as a source of verifiable reward signals for post-training, which is cheaper and more auditable than annotating free-text legal opinions.

---

## References

[1] W. Yuan et al. LeCoDe: A Benchmark Dataset for Interactive Legal Consultation Dialogue Evaluation. ACL 2026. https://aclanthology.org/2026.acl-long.1667/

[2] L. Zhang et al. DLawBench: Evaluating LLMs Through Multi-Turn Legal Consultation. arXiv:2606.13931, 2026. https://arxiv.org/abs/2606.13931

[3] Y. Zhou et al. LexAgentHallu: A Hierarchical Benchmark for Profiling Hallucinations in Legal Agents. EMNLP 2026. https://aclanthology.org/2026.emnlp-main.2121/

[4] W. Fan et al. Can LLMs Time Travel? Enhancing Temporal Consistency in Legal Agentic Search through Reinforcement Learning. NLLP 2026. https://aclanthology.org/2026.nllp-1.2/

[5] S. Zuo et al. LegalWorld: A Life-Cycle Interactive Environment for Legal Agents. EMNLP 2026. https://aclanthology.org/2026.emnlp-main.390/

[6] Harvey. Introducing Harvey's Legal Agent Benchmark. 2026. https://www.harvey.ai/blog/introducing-harveys-legal-agent-benchmark

[7] H. Li et al. LexRAG: Benchmarking Retrieval-Augmented Generation in Multi-Turn Legal Consultation Conversation. SIGIR 2025. https://arxiv.org/abs/2502.20640

[8] H. Li et al. LegalAgentBench: Evaluating LLM Agents in Legal Domain. ACL 2025. https://aclanthology.org/2025.acl-long.116/

[9] Artificial Analysis. Harvey LAB-AA v1.1: adding hallucination checks. 2026-10-08. https://artificialanalysis.ai/articles/harvey-lab-aa-v1-1

[10] LawRefBook. Laws: Chinese statutes and judicial interpretations. https://github.com/LawRefBook/Laws

[11] Z. Lan et al. Chinese Labor Law Large Language Model Benchmark. arXiv:2601.09972, 2026. Dataset: https://ieee-dataport.org/documents/labor-law-bench

[12] H. Xie, F. Steffek, J. De Faria, C. Carter, J. Rutherford. The CLC-UKET Dataset: Benchmarking Case Outcome Prediction for the UK Employment Tribunal. NLLP 2024. https://aclanthology.org/2024.nllp-1.7/

[13] X. Li et al. LabourLawLLM / LabourLawBench case-type taxonomy. 2026. (See [11].)
