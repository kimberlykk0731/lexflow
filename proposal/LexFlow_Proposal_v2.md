# LexFlow: Ask Before You Answer
## A Sufficiency-Gated Legal Consultation Agent with Versioned Case Memory

NLP Course Project Proposal (revised)

---

## 1  Project objective

LexFlow is an interactive legal **consultation** agent, not a legal search assistant. Given a vague, colloquial description of a dispute, it decides whether the facts it has are sufficient to answer; if not, it asks a small number of targeted questions derived from the elements of the claim. Once the record is sufficient, it retrieves the statutes that were **in force on the relevant date**, performs deterministic calculations (limitation periods, compensation), and writes an auditable memorandum with a fact-status table, issue-by-issue reasoning, explicit information gaps, and a cited-version appendix. If the client later corrects a fact, the agent revises only the conclusions that depend on it.

The project's contribution is a working, measurable agent application with three mechanisms: (i) element-based sufficiency gating, (ii) version-aware legal retrieval and citation, and (iii) fact-level revision with dependency-aware invalidation. We do not propose a new legal benchmark, a new base model, or a reinforcement-learning algorithm.

Three research questions guide the evaluation:

- **RQ1.** Does sufficiency gating increase critical-fact coverage and reduce premature advice, compared with an answer-first pipeline that retrieves and answers immediately?
- **RQ2.** Does versioned case memory with dependency-aware invalidation reduce stale conclusions after a fact correction, compared with reusing an earlier analysis?
- **RQ3.** Can mechanical claim-to-evidence verification detect missing, outdated, mismatched, or numerically inconsistent citations without flagging clean output?

These are hypotheses to be tested on a small, controlled protocol. They are not claims about general legal capability.

---

## 2  Motivation and related work

Legal practice rarely starts from a complete fact pattern. A client says "my company fired me" and omits the dismissal date, whether the handbook was publicised, and whether the union was notified. Each of these facts can flip the conclusion: the same dismissal may be a 2N unlawful-dismissal claim, a lawful no-compensation dismissal under Article 39, or a claim already barred by the one-year arbitration limitation period. A search assistant that answers the first message confidently is not merely imprecise; it is structurally unable to notice what it does not know.

The 2026 literature has moved toward this interaction. **LeCoDe** (ACL 2026) collects 3,696 real consultation dialogues and shows that even strong models elicit only about 36% of annotated key facts before giving advice [1]. **DLawBench** (2026) pairs 461 Chinese and U.S. cases with client-belief and court-record views, four client personas, and expert inquiry/resolution rubrics; its best model reaches only 0.562 on consultation-grounded legal reasoning, and it documents legal sycophancy — adopting an unverified client narrative as the premise of professional-looking analysis [2]. **LexAgentHallu** (EMNLP 2026) profiles hallucinations along agent trajectories and reports a right-answer-wrong-reason effect [3]. **LegalSearch-R1** (NLLP 2026) shows that legal agents are temporally biased toward their training cutoff and rarely encode temporal constraints in queries [4]. **LegalWorld** (EMNLP 2026) models Chinese civil litigation as a five-stage causal state chain [5]. On the product side, Harvey's Legal Agent Benchmark and its independent reimplementation add hallucination checks and a three-judge rubric panel [6, 9].

Two gaps remain relevant at course scale. First, these benchmarks evaluate a consultation in which the fact pattern is **fixed**; none of them measures whether a conclusion is revised when the client corrects a fact. Second, temporal validity is usually studied as a retrieval or RL problem, not as a property of the agent's **state**: which version applies, whether a cited article was in force, and what happens when the date itself changes. LexFlow targets exactly these two properties in a narrow domain where the legal rules are tractable and the failure modes are observable.

The engineering reference for inspectable memory is DeepTutor [7]: traces, facts, and synthesis as separate layers. We implement a small subset for law rather than reproducing a tutoring platform.

---

## 3  Method

### 3.1 Scope and element schemas

The system currently covers two claim types: unlawful dismissal in labour disputes, and personal injury from traffic accidents. For each, `data/elements.json` defines the fields that can change the outcome, their type, a client-facing question, the legal reason for asking, and the statutory basis. Conditional criticality is explicit: questions about the publicity of the handbook are critical only when the employer relies on serious misconduct; the claimant's urban/rural residence is critical for disability or death compensation only before 2022-05-01.

Sufficiency is a schema operation, not a model judgement: the agent answers only when every critical field is present at day-level precision, or when the question budget is exhausted — in which case the memorandum states the gaps instead of filling them.

### 3.2 Version-aware corpus and retrieval

`tools/build_corpus.py` builds an article-level corpus from a public markdown collection of Chinese statutes [8], currently 15 instruments and 1,340 articles. Every article carries `valid_from`, `valid_to`, its source path, and a manual note where the text is a consolidated version. Retrieval is dependency-free BM25 over character bigrams with a small legal synonym table; results can be filtered to the version in force on the case date, and the agent can locate the predecessor or successor of an article. The appendix of every memorandum lists the cited article, its validity window, an excerpt, and a source link.

The rule layer encodes the parts of law that are definitional or arithmetic:

- labour arbitration limitation: 60 days before 2008-05-01 (Labour Law art. 82), one year afterwards (Mediation and Arbitration Act art. 27);
- tort limitation: one year before 2017-10-01 (General Principles of Civil Law art. 136), three years afterwards (General Principles of Civil Law 2017 art. 188, Civil Code art. 188);
- compensation: 0 under lawful Article 39 dismissal, N under Articles 40/41/46, 2N under Article 87, with the six-month rounding rule and an optional one-month payment in lieu of notice;
- damages standards: the 2003, 2020 and 2022 interpretations of personal-injury compensation, including the 2022 unification of urban and rural standards;
- tort liability: the Tort Liability Law before 2021-01-01, the Civil Code afterwards.

These are exactly the places where an LLM is least reliable and where a deterministic implementation is both cheaper and more honest.

### 3.3 Control flow and memory

The control flow is an explicit state machine: intake → sufficiency gate → research → draft → verify → revise. Questions are ordered by legal leverage (limitation first, then the ground for dismissal, then computation), at most two per turn and at most fourteen per session. The model is used for fact extraction, optional question-selection assistance, and a short plain-language explanation; it does not choose citations or compute amounts.

Facts are stored with provenance (`user-stated`, `documentary`, `verified`, `unknown`), a revision number, and a superseded chain. A new statement does not silently overwrite a documentary record; a conflict is surfaced and the user is asked to check the original. Each change increments the case revision and invalidates only the cache entries whose declared fact dependencies intersect the changed keys. Public statute lookups have no fact dependencies and remain reusable.

A claim-to-evidence table links every conclusion to article IDs, quoted spans, dependent facts, and the case revision used. The verifier emits typed defects: `MISSING_SOURCE`, `UNKNOWN_SOURCE`, `VERSION_NOT_IN_FORCE`, `QUOTE_MISMATCH`, `SUPERSEDED_FACT`, `MISSING_DEPENDENCY`, `UNVERIFIED_NUMBER`. Repair is bounded to one cycle: replace a citation with the version in force, drop a mismatched quote, or drop an unknown source. Unresolved defects remain visible in the memorandum.

### 3.4 Interface

A Streamlit interface shows the conversation on the left and, on the right, the live fact table, the memorandum, the issue-by-issue citations, and the execution trace. The point of the interface is to make the agent's uncertainty and its state transitions inspectable during the classroom demonstration.

---

## 4  Data and evaluation

### 4.1 Controlled consultation protocol

We construct 12 scripted cases (7 labour, 5 tort). Each case contains an opening message, a hidden fact sheet, a set of critical facts, hand-computed gold conclusions, and — for two cases — a correction delivered after the first memorandum. A scripted client answers only the fields it is asked about and says "I don't know" otherwise. This removes human annotation from the loop and makes every run reproducible.

The 12 cases cover: handbook not publicised, handbook publicised, incompetence without training, compliant incompetence dismissal, negotiated termination, an expired limitation period, and a corrected dismissal date; and, for tort, accidents on both sides of the 2022-05-01 interpretation boundary, a 2020 accident governed by the 2003 interpretation, and a corrected accident date that crosses the boundary.

### 4.2 Conditions and metrics

Four conditions use the same model, tools, and budget: `answer_first` (no gate, no verification), `gate_only`, `full` (gate + verification + revision), and `full_no_revision` (the same system, deliberately reusing the analysis produced before the correction).

Metrics are: fact coverage at memorandum time; inquiry recall over facts not volunteered in the opening; number of questions; premature-advice rate; citation support rate; agreement with hand-computed gold on illegality, amount, limitation deadline, and interpretation version; and stale-conclusion rate after correction.

Because the rule layer and the gold answers are authored by the same person, high agreement on illegality/amount is a **consistency** result, not evidence of legal capability. The informative comparisons are the behavioural ones: coverage, premature advice, citation support, and stale conclusions.

### 4.3 Verification probe, cache replay, and human review

A guardrail that never fires is not evidence. We inject five defect types into clean analyses (unknown article, version not in force, fabricated quote, superseded dependency, altered amount) and measure detection. We also replay a turn with no new facts with the cache on and off, and correct one fact to observe which entries are invalidated.

Finally, two reviewers independently score ten memoranda, blinded to condition, on traceability, separation of facts and assumptions, honesty about gaps, temporal validity, and readability, and we report agreement and disagreements. The review sheet is in `docs/memo_review_sheet.md`.

### 4.4 External validity

DLawBench and LeCoDe are the closest public benchmarks; we use them as design references and as the natural next step, not as our scoreboard. Running them would require a general legal schema and, for LeCoDe, a data-use agreement; our schema covers two claim types. We therefore report a bounded, reproducible internal evaluation and state the limitation explicitly rather than adapting a public benchmark and presenting the adaptation as an official result.

---

## 5  Current status and plan

The repository currently contains a working end-to-end system with no third-party dependencies: corpus builder, version-aware retrieval, element schemas, extraction with LLM and rule fallbacks, the rule layer, SQLite memory and cache, the verifier, memorandum rendering, CLI demo, Streamlit interface, 12-case protocol, verifier probe, cache experiment, and 21 unit tests.

With DeepSeek's official API (12 cases × 4 conditions, 149k input and 11k output tokens, about RMB 0.17 at the October 2026 price), gating raises fact coverage from 57.5% to 100% and reduces premature advice from 58.3% to 0%; versioned memory reduces stale conclusions after correction from 100% to 0%. The verifier detects all five injected defect types with no false positives on clean analyses. High agreement on illegality, amount, limitation and version is a consistency result, because the rule layer and the gold answers were authored by the same person; the behavioural deltas are the informative part. Mock mode is retained only so that the pipeline runs without a key.

| Week | Deliverable |
|---|---|
| 1 | Run the protocol with a real model; freeze prompts and budgets; add one claim type (e.g. private lending) |
| 2 | Retrieval upgrade (embedding + rerank) as a controlled comparison; four client personas; human blind review |
| 3 | Error analysis, report, slides, recorded demonstration |

Risks: mock-to-API gap; same-author gold and rules; narrow domain; simplification of limitation start dates and local average wage caps; and the possibility that the question budget truncates coverage in harder cases. Each is stated in the report rather than hidden.

---

## References

[1] W. Yuan et al. LeCoDe: A Benchmark Dataset for Interactive Legal Consultation Dialogue Evaluation. ACL 2026. https://aclanthology.org/2026.acl-long.1667/

[2] L. Zhang et al. DLawBench: Evaluating LLMs Through Multi-Turn Legal Consultation. arXiv:2606.13931, 2026. https://arxiv.org/abs/2606.13931

[3] Y. Zhou et al. LexAgentHallu: A Hierarchical Benchmark for Profiling Hallucinations in Legal Agents. EMNLP 2026. https://aclanthology.org/2026.emnlp-main.2121/

[4] W. Fan et al. Can LLMs Time Travel? Enhancing Temporal Consistency in Legal Agentic Search through Reinforcement Learning. NLLP 2026. https://aclanthology.org/2026.nllp-1.2/

[5] S. Zuo et al. LegalWorld: A Life-Cycle Interactive Environment for Legal Agents. EMNLP 2026. https://aclanthology.org/2026.emnlp-main.390/

[6] Harvey. Introducing Harvey's Legal Agent Benchmark. 2026. https://www.harvey.ai/blog/introducing-harveys-legal-agent-benchmark

[7] HKUDS. DeepTutor: Lifelong Personalized Tutoring. https://github.com/HKUDS/DeepTutor

[8] LawRefBook. Laws: Chinese statutes and judicial interpretations (markdown). https://github.com/LawRefBook/Laws

[9] Artificial Analysis. Harvey LAB-AA v1.1: adding hallucination checks. 2026-10-08. https://artificialanalysis.ai/articles/harvey-lab-aa-v1-1
