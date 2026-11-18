# 2026 年法律 AI 进展速览（截至 2026-11）

> 这是给项目定方向用的定向调研，不追求穷尽。所有条目都给了可核实的链接；数字来自论文摘要或官方博客，未复现。

## 0. 一句话结论

法律 AI 在 2026 年的竞争点，已经从“答对法考选择题”转到三件事：**会不会做完整的法律工作（agentic legal work）、会不会在信息不全时先问、以及能不能被核验**。单纯做一个“法律问答 RAG”在课程里已经很难讲出差异；单纯做一个“多轮咨询助手”也已经被 benchmark 化。真正还有空间的是**某个具体机制**：事实修订后的结论一致性、法条时间效力、引用可核验性、程序性期限计算。

---

## 1. 五个值得知道的变化

### 1.1 从“答题”到“做工作”：Harvey LAB

[Harvey 的 Legal Agent Benchmark（LAB）](https://www.harvey.ai/blog/introducing-harveys-legal-agent-benchmark) 在 2026 年 5 月发布，用真实工作产物（文档、表格、演示、文件系统工具）组织任务，按专家 rubric 做 all-pass 评分。它的一个直接观察是：模型分数呈现“锯齿状智能”——不同法域由不同模型领先，聚合分数会掩盖task 级别的灾难性失败。

2026 年 10 月，Artificial Analysis 发布 [LAB-AA v1.1](https://artificialanalysis.ai/articles/harvey-lab-aa-v1-1)，加入 **hallucination checks**，并把 rubric 从单 judge 改为三 judge 面板（GPT-6 Sol / Grok 4.7 / Claude Opus 5.5）。这说明“做得像”已经不够，**核验**成为一等公民。

> 对本项目的含义：如果 demo 只有“回答 + 引用”，在 2026 年的语境里是 2023 年的产品。把“核验结果”显式做进界面，比多接一个工具更有区分度。

### 1.2 多轮咨询被 benchmark 化：LeCoDe 与 DLawBench

- [LeCoDe](https://aclanthology.org/2026.acl-long.1667/)（ACL 2026）：3,696 段真实直播咨询、110,008 轮对话，标注了原子关键事实与重要性。核心指标是**追问能力**（Recall、加权 Recall、Recall@5、NDCG）与建议质量。即使 GPT-4 级别的模型，追问召回也只有约 36%；领域微调模型（ChatLaw、Lawyer-LLaMA）更差，常常跳过追问直接给建议。
- [DLawBench](https://arxiv.org/abs/2606.13931)（arXiv 2606.13931，2026-06）：461 个中/美真实案件改写，5,532 对“当事人认知 vs 法院认定”事实，3,411 条 Inquiry rubric、3,348 条 Issue rubric。它把咨询拆成 **Elicitation（Fact Coverage + Inquiry）→ Resolution（Fact Resolution + Issue Resolution）→ Fidelity（Claim Support）**，并引入四种当事人人格（Cooperative / Dependent / Withdrawn / Adversarial）。最强模型 GPT-5.5 的 Resolution 也只有 0.562，且暴露出**法律谄媚**（把当事人未经证实的说法包装成法律分析）与“当事人越需要引导、模型越弱”的悖论。

> 对本项目的含义：**“做提问咨询助手”本身不再新**，2026 年已经有专门 benchmark。但这两篇都指出同一个空白：它们评的是“一次咨询里问得全不全、答得好不好”，**没有评“当事人更正事实之后，结论会不会跟着改”**。这正是本项目现有 demo 的记忆/修订机制可以切入的地方。

### 1.3 幻觉从“结果指标”变成“轨迹指标”：LexAgentHallu

[LexAgentHallu](https://aclanthology.org/2026.emnlp-main.2121/)（EMNLP 2026）：3,414 个实例、17 个法律类别、6 类任务，7 大类 / 27 子类的双层幻觉分类（实体层 + agent 过程层），逐步骤定位 agent 在哪一步开始错。它评了 18 个 agent，发现 **Right-Answer-Wrong-Reason**：答案对，但轨迹里的工具调用、引用、推理是错的；而且错误子类会按 agent 框架聚集。

> 对本项目的含义：这直接支持“claim-to-evidence 表 + 引用核验”的做法。但不声称做了幻觉 benchmark；本项目只是在自建小语料上做了**机械核验**，并诚实说明它抓不到论证错误。

### 1.4 时间效力成为 agentic search 的研究点：LegalSearch-R1

[LegalSearch-R1](https://aclanthology.org/2026.nllp-1.2/)（NLLP 2026）：指出法律 LLM 有“训练截止时间偏置”，搜索 agent 也几乎不把时间约束写进 query；提出本地法条 RAG + 在线搜索 + 按修订期索引的数据做端到端 RL，7B 模型在 13 个法律任务上比 deep research 框架高 12.9–29.8%，时间一致性高 57.7–80.3%。

另外有工作专门诊断法条问答的时间失效模式（ChronosLex / LexTempus 一类），说明“该用哪一版法条”是一个独立且困难的问题。

> 对本项目的含义：时间效力是**已被证明重要、但工程实现仍然稀缺**的点。本项目不需要做 RL；把“按案发日过滤法条版本 + 引用版本表 + 版本失效告警”做扎实，就是一个清楚的课程级贡献。注意在 related work 里引用 LegalSearch-R1，别把“时间效力”说成自己首创。

### 1.5 从“单点任务”到“生命周期环境”：LegalWorld

[LegalWorld](https://aclanthology.org/2026.emnlp-main.390/)（EMNLP 2026）：把中国民事诉讼建模成五个阶段、七个场景的因果状态链，基于 75,309 对民事判决，配 local/global case memory 与 Skill/Tool library，用 18,992 条法律背景评分验证轨迹的程序真实性。它发现：总体分接近的模型，在单个阶段上可以差 15 个归一化点。

> 对本项目的含义：个人做“用法官立案思路做 RL 标注”的方向，学界已经在用“生命周期 + 程序真实性”做了，而且规模远超单人标注。个人项目不必碰这个；但可以在报告里引用它，说明项目清楚边界在哪。

---

## 2. 后训练（RL）这条线现在在做什么

2026 年法律 RL 的主流不是“用 RL 提升法律知识”，而是：

- **结构化法律推理的后训练**：例如 JPO（Juris Policy Optimization）一类工作，把“法条匹配 → 罪名 → 量刑”的结构约束写进奖励/策略，而不是只看最终标签。
- **推理链与答案的信号平衡**：如 [Signal Balancing and Reward Scheduling](https://aclanthology.org/2026.findings-emnlp.1273/)（EMNLP 2026 Findings），指出 SFT 在推理链远长于答案时答案信号被稀释，RL 则有奖励设计贵、平台期、reward hacking 的问题，于是做两阶段训练。
- **agentic search 的 RL**：LegalSearch-R1 把“什么时候搜、搜什么、是否满足时间约束”作为策略学习目标。
- **多轮咨询的 SFT/RL**：LeCoDe 试了 Direct SFT / Key-fact SFT / Key-fact-e SFT，关键事实驱动的 SFT 把追问召回从 ~36% 提到 ~54%，但仍远不够。

共性：**奖励信号来自可验证的结构**（法条 id、要件、时间、计算），而不是“像不像律师”。这与项目前期的 GRPO 实验一致：问题定义与标签结构比算法重要。

> 对本项目的含义：课程项目不要碰 RL 训练。可以在“未来工作”里写：把本项目的要件 schema 与核验器输出当作 reward 的可验证信号，是比人工标注更便宜的后训练路线。这句话有分量，但不需要真的训。

---

## 3. 对本项目的取舍

### 不要做

1. **通用法律问答 RAG**：2023 年就饱和了，且项目前期已经做过召回优化。
2. **“多轮咨询助手”作为唯一卖点**：LeCoDe / DLawBench 已经把这件事 benchmark 化，课程里也很难做出差异。
3. **自己标 RL 数据 / 复刻法官立案思路**：标注成本高，且 LegalWorld 这类工作已经把规模做上去了。
4. **多 agent 角色扮演**（Planner/Researcher/Analyst/Verifier 四个 agent）：课程项目里通常是 prompt 换皮，增加失败面，不增加可测价值。

### 可以做

**把“事实会变”做成第一等公民**。现有咨询 benchmark 都假设“一次咨询、事实固定”；真实咨询里当事人会改口、补材料、记错日期。本项目可以只回答一个问题：

> 当事实被更正时，agent 能不能只更新受影响的部分，并且不再引用旧结论？

这个问题：
- 有清楚的机制（版本化事实 + 依赖失效 + 重算）；
- 有干净的指标（旧结论残留率、重算正确率、缓存失效条数）；
- 有现成的对照（`full` vs `full_no_revision`）；
- 和大 benchmark 不冲突（它们是外部效度，不是主实验）；
- 与法律实务判断强相关（哪些事实一改，结论就翻）。

时间效力是第二个可加的点，因为它和“事实日期”共用同一套状态：解除日期/事故日期一变，适用版本、时效、金额全都变。这比再做一个“类案检索”更便宜，也更有法律味。

---

## 4. 参考文献（可直接放进 proposal）

1. Zhang et al. **DLawBench: Evaluating LLMs Through Multi-Turn Legal Consultation.** arXiv:2606.13931, 2026. https://arxiv.org/abs/2606.13931
2. Yuan et al. **LeCoDe: A Benchmark Dataset for Interactive Legal Consultation Dialogue Evaluation.** ACL 2026. https://aclanthology.org/2026.acl-long.1667/
3. Zhou et al. **LexAgentHallu: A Hierarchical Benchmark for Profiling Hallucinations in Legal Agents.** EMNLP 2026. https://aclanthology.org/2026.emnlp-main.2121/
4. Fan et al. **Can LLMs Time Travel? Enhancing Temporal Consistency in Legal Agentic Search through Reinforcement Learning.** NLLP 2026. https://aclanthology.org/2026.nllp-1.2/
5. Zuo et al. **LegalWorld: A Life-Cycle Interactive Environment for Legal Agents.** EMNLP 2026. https://aclanthology.org/2026.emnlp-main.390/
6. Li et al. **LegalAgentBench: Evaluating LLM Agents in Legal Domain.** ACL 2025. https://aclanthology.org/2025.acl-long.116/
7. Li et al. **LexRAG: Benchmarking Retrieval-Augmented Generation in Multi-Turn Legal Consultation Conversation.** SIGIR 2025. https://arxiv.org/abs/2502.20640
8. Harvey. **Introducing Harvey's Legal Agent Benchmark.** 2026-05. https://www.harvey.ai/blog/introducing-harveys-legal-agent-benchmark
9. Artificial Analysis. **Harvey LAB-AA v1.1: adding hallucination checks.** 2026-10-08. https://artificialanalysis.ai/articles/harvey-lab-aa-v1-1
