# LexFlow — 劳动争议「先问再答」咨询 Agent

NLP 课程项目。一个面向**劳动争议咨询**（不是法律检索）的 Agent：它先判断“现在掌握的事实够不够下结论”，缺关键事实就追问；事实齐备后检索**案发时有效**的法条、做确定性计算、生成带引用与信息缺口的备忘录和文书；当事人更正事实后，它重算而不是沿用旧结论。

> 本项目是课程演示，输出不构成法律意见。法条原文来自公开整理仓库，正式引用应以 [国家法律法规数据库](https://flk.npc.gov.cn/) 为准。

---

## 0. 这次返工解决了什么

旧版只有“劳动争议解除 / 交通事故”两张**扁平问卷**，分类 0 分时**默认 `labor_dismissal`**。于是输入“交通肇事”会问出解除日期、规章制度、工会——全是劳动仲裁。

新版做了三件事：

1. **分诊不默认**：劳动 / 交通侵权 / 其他领域 / 不确定，四种结果；其他领域明确说“不覆盖”，不确定就问“是哪类问题”。
2. **请求权多标签**：一句话可以同时是“辞退 + 欠薪 + 加班费”，系统分别分析、合并成一份备忘录。
3. **要件树代替固定问卷**：`请求权 → 要件 → 要件事实 → 证据`；`requires` 条件不满足时整条分支不问。例如“自己辞职”不再问工会和 2N，改问是否属于第 38 条被迫解除。

详见 [`docs/LABOR_PIVOT.md`](docs/LABOR_PIVOT.md)。

---

## 1. 一句话卖点

**大多数法律 RAG 回答“问题”，LexFlow 先判断“这个问题现在能不能回答”，再决定问什么、怎么算、出什么文书。**

| 机制 | 做法 | 对应指标 |
|---|---|---|
| 分诊 + 多请求权 | 劳动 12 类 + 交通；不默认、不硬套 | 分诊准确率、超范围拒答率 |
| 要件事实门控 | 每个请求权维护要件树；条件分支不满足就不问 | 事实覆盖率、过早结论率、追问召回 |
| 时间效力 | 法条按版本/生效期入库；检索与引用限定在案发日有效版本 | 版本选择一致率、时效一致率 |
| 版本化案件记忆 | 事实带来源、修订号、被取代链；更正后只失效依赖该事实的缓存与结论 | 旧结论残留率、缓存失效条数 |
| 可核验产出 | 引用存在/有效/引文对得上/金额=计算值/事实未过期 | 引用可核验率 |

---

## 2. 快速开始（无需 API Key）

```bash
# 在仓库根目录执行
PYTHONPATH=src python3 -m lexflow.cli demo          # 劳动争议演示 + 备忘录
PYTHONPATH=src python3 eval/run_evals.py            # 12 个回归案例 × 5 配置；新版评测见第 6 节
PYTHONPATH=src python3 eval/verify_probe.py         # 给核验器注入 5 类错误
PYTHONPATH=src python3 eval/cache_bench.py          # 缓存命中与失效
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

零第三方依赖即可跑通；`mock` 模式是确定性的工程脚手架，**不是模型能力结论**。

### 接入真实模型

```bash
export LEXFLOW_LLM=api
export LLM_BASE_URL=https://api.deepseek.com   # 或任意 OpenAI-compatible 端点
export LLM_API_KEY=sk-...
export LLM_MODEL=deepseek-flash
export LLM_THINKING=disabled
PYTHONPATH=src python3 -m lexflow.cli chat
```

模型负责**事实抽取**、可选的分诊消歧、追问措辞改写和白话解释；是否追问、引用哪条法条、金额与期限怎么算，由确定性规则层完成。这样引用和数字才可核验、可复现。

### 网页演示

历史咨询保存在本机 `runs/ui.sqlite`。侧边栏「历史会话 → 恢复会话」可恢复对话、
案件事实、分析日期、备忘录和分析路径；刷新带 `session` 参数的页面也会恢复同一会话。
「新会话」保留旧记录并创建独立咨询，「载入示例对话」也会新建会话。
模型会收到同一会话最近最多 8 条消息（总计最多 10,000 字符），用于理解指代和简短回答；
结构化事实仍以最新版本为准，完整原文留在数据库中。对前文的解释不会修改案件事实。

```bash
pip install streamlit
PYTHONPATH=src streamlit run app/streamlit_app.py
```

左侧对话，右侧实时看**要件链**、事实表、备忘录、争点依据、文书和运行轨迹。

---

## 3. 覆盖范围

| 请求权 | 典型问题 | 主要计算/判断 |
|---|---|---|
| 解除/辞退 | 辞退、裁员、被迫解除、合同到期不续签 | N / N+1 / 2N、违法解除、时效 |
| 工资/欠薪 | 拖欠工资、提成、年终奖、降薪 | 欠付金额、第 85 条加付赔偿 |
| 加班费 | 996、大小周、隐形加班 | 150%/200%/300%、特殊工时 |
| 未签合同二倍工资 | 没签书面合同 | 最多 11 个月、解释二第 6/7 条 |
| 工伤 | 工伤认定、伤残待遇 | 30 日/1 年、一次性伤残补助金 |
| 社保/公积金 | 断缴、补缴、被迫解除 | 补缴路径 vs 仲裁路径 |
| 年休假 | 未休年假 | 5/10/15 天、200% 额外 |
| 竞业限制 | 补偿、违约金、解除 | 30%、2 年上限、3 个月未付 |
| 三期/生育 | 孕期被辞、产假工资 | 2N、生育津贴补差 |
| 派遣/外包/新业态 | 骑手、主播、外包 | 从属性、责任主体 |
| 合同/试用期 | 试用期、调岗降薪 | 试用期上限、书面变更 |
| 仲裁/诉讼程序 | 一裁终局、管辖、时效 | 45+15 日、15 日起诉 |
| 交通事故人身损害 | 责任、伤残、保险 | 2022 城乡标准、三年时效 |

法条库：**26 部、1810 条**，含劳动争议司法解释（二）（2025-09-01）、工伤保险条例、社会保险法、年休假条例、工资支付暂行规定、女职工保护规定等。

---

## 4. 它怎么工作

```
用户输入
  │
  ├─ 分诊：劳动（可多请求权）/ 交通 / 其他领域 / 不确定
  │        └─ 其他领域 → 明确说“不覆盖”，不硬套
  │
  ├─ 事实抽取（LLM 优先，规则兜底；只抽当前请求权声明的字段）
  │        └─ 版本化案件记录（来源、修订号、取代链）
  │
  ├─ 要件树遍历：请求权 → 要件 → 事实 → 证据
  │        ├─ 分支条件不满足 → 不问
  │        ├─ 缺关键事实 → 按“法律杠杆”追问 1–2 个
  │        └─ 事实齐备 → 研究
  │
  ├─ 研究：按案发日过滤法条版本 → 检索 → 每个请求权一个分析器 + 确定性计算
  │
  ├─ 备忘录：结论 / 要件链 / 事实状态 / 争点依据 / 实务提示 / 缺口 / 证据清单
  │
  └─ 核验：引用存在？案发日有效？引文对得上？金额=计算值？事实没过期？
           └─ 有缺陷 → 有界修复（换正确版本 / 去错引文），再核验一次
```

### 为什么“追问”是有意义的 agent 行为

同一句“公司把我辞退了”，在知道/不知道解除日期、制度是否公示、是否通知工会时，结论可以从“2N 赔偿”变成“时效已过、先解决时效抗辩”。追问不是礼貌，是在**缩小假设空间**。

新版还让追问**随分支变化**：

- “严重违纪” → 问制度公示、违纪证据、民主程序、工会；
- “不胜任” → 问培训/调岗、代通知金；
- “自己辞职” → 不问工会/2N，改问是否第 38 条被迫解除；
- “没有加班” → 不问加班时长，直接结束加班费分支；
- 日期只精确到月 → 追问具体哪一天（影响时效和工作年限）。

### 分析路径直接展示

每次追问或出备忘录，都会渲染同一条路径：

```text
【请求权】劳动争议 · 解除/辞退
  请求权基础：《劳动合同法》第48条；第87条；第46条；第47条
  可能后果：继续履行；或违法解除赔偿金 2N；合法解除时可能为 N / N+1 / 0
  ○ 要件：劳动关系成立（待确认）
    ? 入职日期
    ? 用人单位
  ⚠️ 要件：解除行为与时间（部分具备）
    ✓ 解除日期 = 2026-03-15
  ⚠️ 要件：解除理由与程序合法性（部分具备）
    ✓ 解除理由 = 严重违纪
    ? 规章制度是否公示或告知
     证据：员工手册及签收记录、违纪证据、工会通知
```

- CLI：demo 每轮打印 `[分析路径]`，`/path` 可随时查看；
- 网页：右侧「分析路径」页签，显示要件状态 + 下一步问题的信息价值排序；
- 备忘录：第二节就是这条路径，带请求权基础和可能后果。

### 知识库是 RAG 吗？

是，但目前是**轻量、无向量库的 RAG**：

- 法条：按案发日过滤版本 → 中文 bigram BM25 检索；
- 实务提示：每条拆成 chunk（标题/要点/caveat）→ 请求权 topic 硬过滤 → BM25 → 相对阈值截断；
- 命中结果带发布机关、日期、URL、BM25 分数，进备忘录“实务提示（RAG 检索）”；
- 没有 embedding / cross-encoder rerank，接口已留好（`KnowledgeBase.retrieve`）。

**为什么不用向量库**：课程环境要求零第三方依赖、可复现；中文法律短文本上 BM25 + 同义词扩展已经够用。
升级路径是 hybrid（BM25 + dense）+ rerank，不是重写。

### 技术点（可展示、可度量）

- **神经符号分解**：LLM 只抽取/改写，追问、法条、金额由符号层决定；
- **VOI 主动问询**：枚举假设回答 → 跑规则层 → 数“能区分几种结果”，优先问最能改变结论的；
- **时间效力感知检索**：引用前检查案发日版本；
- **依赖感知缓存失效**：更正一个事实只失效依赖它的计算；
- **claim-to-evidence 核验 + 有界修复**；
- **多轮受控评测**：隐藏事实、脚本化当事人、更正注入。

详见 [`docs/TECH_HIGHLIGHTS.md`](docs/TECH_HIGHLIGHTS.md)。其中 VOI 是规则模型上的枚举近似，
不是完整贝叶斯 belief update——报告里要这么写，不能吹成“学习型问询策略”。

### 时间效力为什么值得做

- 劳动争议：2008-05-01 前仲裁申请期是 **60 日**（劳动法第 82 条），之后是 **1 年**（调解仲裁法第 27 条）。
- 人身损害：2017-10-01 前身体受伤诉讼时效 **1 年**（民法通则第 136 条），之后 **3 年**。
- 赔偿标准：2022-05-01 前残疾/死亡赔偿金区分城乡，之后统一按城镇居民标准。
- 2025-09-01 起适用劳动争议司法解释（二），二倍工资按月计算、社保放弃约定无效、竞业限制收紧。

这些边界都在 `data/corpus/manifest.json` 里，并由 `rules.py` 按案发日选择。

---

## 5. 能出什么文书

| 功能 | CLI | 说明 |
|---|---|---|
| 法律意见书 | `/letter` | 事实摘要、法律分析、结论、请求、风险、声明 |
| 劳动仲裁申请书 | `/arbitration` | 请求事项自动带金额、事实理由、证据清单、此致仲裁委 |
| 证据清单 | `/evidence` | 按要件列证据，带勾选框 |
| 催告函/律师函 | `/demand` | 草稿，需律师审核盖章 |
| 被迫解除通知书 | `/resign` | 第 38 条模板，提示留痕送达 |
| 仲裁 vs 诉讼 | `/compare` | 前置、管辖、时效、审限、费用、一裁终局、执行、优缺点 |
| 打工人权益地图 | `/rights` | 入职前/在职/离职/维权四阶段 + 投诉渠道 |
| 关键期限卡片 | `/deadlines` | 仲裁时效、工伤 30 日/1 年、年假、竞业 |
| 合同条款体检 | `/contract <条款>` | 试用期、竞业、违约金、放弃社保、996、调岗降薪等 |

---

## 6. 评测

### Bench v2（2026-11-27）

新增 **38 个劳动争议案例（12 开发 + 26 测试）和 12 个分诊案例**，覆盖全部 12 类劳动请求权；包含 8 个多请求权、12 个事实更正、6 个信息不足案例。
25 个 `critical_if` 条件字段均有触发与不触发样例，这不等于所有程序分支或时间效力边界都已覆盖。

```bash
python3 eval/validate_cases.py
PYTHONPATH=src python3 eval/run_evals_v2.py --split test --llm mock --repeats 3 --out runs/bench_v2/my_mock
python3 eval/oracle.py
python3 eval/verify_bench_v2.py
```

已完成 312 次主表 mock 会话：`full` 的正确事实覆盖率 **57.6%**，独立公式一致率 **64.4%**（适用 15 个案例，按案例宏平均）。
这些分数采用新案例、新分母和事实值正确性检查，与下面旧表不直接比较。完整事实输入时，50 个更正前/后分析阶段与独立参考断言一致。
案例当前为设计种子＋模板生成，独立人工法律审定尚未完成。真实 DeepSeek API 的修复前后测试已在本地完成：修复后 `full` 正确事实覆盖率为 **99.3%**，公式一致率为 **100.0%**（适用15个案例）。这是同一数据集上的回归复测，详见 [本地API运行记录](docs/LOCAL_API_REPORT_20261127.md)及 [修复后结果](runs/bench_v2/api_test_revised/SUMMARY.md)。

使用方法见 [BENCH_V2_GUIDE.md](docs/BENCH_V2_GUIDE.md)，运行分析见 [BENCH_REPORT_V2.md](docs/BENCH_REPORT_V2.md)。

### 原有 12 案协议（历史主表，现作回归）

以下表格是 v1 历史运行记录；当前回归结果及新旧口径差异见 [运行索引](runs/SUMMARY.md)。

主实验是**受控咨询协议**：12 个案例（7 劳动 + 5 侵权），每个案例有隐藏事实表；脚本化当事人只回答被问到的问题，其余回答“不清楚”；其中 2 个案例在第一次备忘录之后给出更正。金标准结论由作者依据法条手工计算，不由系统生成。

五个配置：

- `answer_first`：不追问、不核验，直接出结论
- `gate_only`：追问 + 检索 + 备忘录
- `full`：追问 + 检索 + 核验/修复 + 版本化记忆 + VOI 排序
- `full_no_voi`：关掉 VOI 排序，用来对照提问顺序
- `full_no_revision`：刻意复用更正前的分析，模拟“事实改了、结论没跟着变”

当前 **mock** 结果（`runs/SUMMARY.md`）：

| 条件 | 事实覆盖率 | 追问召回 | 过早结论率 | 引用可核验率 | 违法认定 | 金额 | 时效 | 版本 | 旧结论残留 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| answer_first | 59.1% | 41.7% | 58.3% | 83.3% | 85.7% | 0% | 50.0% | 100% | — |
| gate_only | 100% | 99.1% | 0% | 100% | 100% | 100% | 100% | 100% | 0% |
| full | 100% | 99.1% | 0% | 100% | 100% | 100% | 100% | 100% | 0% |
| full_no_voi | 100% | 99.1% | 0% | 100% | 100% | 100% | 100% | 100% | 0% |
| full_no_revision | 100% | 99.1% | 0% | 92.2% | 100% | 85.7% | 83.3% | 80% | 100% |

注意：`full` 的高准确率是**规则层与金标准同源**导致的，只能说明管线一致，不能说明法律能力。真正有信息量的是：追问把覆盖率从 59.1% 拉到 100%、把过早结论率从 58.3% 压到 0%；版本化记忆把旧结论残留从 100% 压到 0%。

**外部评测**：中国已有专门的劳动法基准 [LabourLawBench](https://ieee-dataport.org/documents/labor-law-bench)（12 任务 × 12 案由，CC BY 4.0，需登录下载），但以**单轮**任务为主；多轮劳动争议咨询评测仍是空白。CLC-UKET（Huiyuan Xie 等，NLLP 2024）是英国 employment tribunal 数据集，可作方法学参照。详见 [`docs/LABOR_PIVOT.md`](docs/LABOR_PIVOT.md) 第 7 节。

### 5.1 外部检查：DLawBench ask-first 策略（adapted run）

主报告的 12-case controlled protocol 已经测了 gate 本体（critical-fact coverage
59.1%→100%，premature advice 58.3%→0%）。这一节把同一套 ask-first 策略接到
DLawBench 的公开协议上，测的是**外部协议迁移 + 两个 schema 的边界**，不是第二次 gate
测试。

```bash
python external/dlawbench/run.py --n-cases 30   # 90 sessions 主表
python external/dlawbench/run.py --n-cases 30 --policies checklist_9 \
    --output-dir runs/external/checklist9       # 等题量控制
python external/dlawbench/verify.py             # 验收自检
```

结果在 [`runs/external/summary.md`](runs/external/summary.md)，方法与 caveat 见
[`docs/EXTERNAL_EVAL.md`](docs/EXTERNAL_EVAL.md)。**这是 adapted run，不是官方
leaderboard**：被测对象是固定问卷，不是 LexFlow 的 element-schema gate；30 个 CN case
里只有 1 个（交通侵权）真正落在 schema 内，另外 2 个（工伤、降薪）是 schema 边界，真 agent
只能做 case study。题库是人工整理、并在首轮跑分后扩充过的，所以 Issue Resolution /
Resolution 只作诊断，不作能力分。绝对分数不可与官方榜单比较，也不能和上面 12 案的主表
混成一张表。

---

## 7. 目录

```
lexflow/
├── README.md
├── docs/LABOR_PIVOT.md           # 返工说明 + 开源调研 + 评测集调研
├── docs/TECH_HIGHLIGHTS.md       # 技术点：哪些高级、哪些只是工程
├── docs/TODO_AI_BENCH.md         # AI 自建多轮评测集（少人工）
├── docs/EXTERNAL_EVAL.md         # DLawBench adapted run 的方法与 caveat
├── data/
│   ├── corpus/manifest.json      # 26 部法律法规/司法解释的版本与生效期
│   ├── corpus/statutes.jsonl     # 1810 条法条（生成物，已提交）
│   ├── elements.json             # 90 事实 + 13 请求权 + 要件树（生成物）
│   ├── knowledge/practice_notes.json   # 16 条法院/人社实务提示
│   ├── knowledge/worker_rights_map.json
│   ├── eval/scripted_cases.json  # 12 个脚本案例
│   └── sources/                  # 法条源文件缓存
├── src/lexflow/
│   ├── router.py                 # 分诊：劳动多标签 / 交通 / 超范围 / 切换
│   ├── elements.py               # 事实目录、请求权、条件求值
│   ├── issues.py                 # 要件树遍历 + 动态问题排序
│   ├── questions.py              # 上下文锚定 + 可选 LLM 改写
│   ├── voi.py                    # 价值信息（VOI）问题排序
│   ├── path.py                   # 请求权→要件→事实 路径渲染
│   ├── extract.py                # 事实抽取
│   ├── rules.py                  # 13 个分析器 + 计算器
│   ├── documents.py              # 法律意见书/仲裁申请/证据清单/催告函/被迫解除
│   ├── guides.py                 # 仲裁 vs 诉讼、权益地图、期限、合同体检
│   ├── knowledge.py              # 实务提示
│   ├── agent.py                  # 编排
│   ├── memo.py                   # 备忘录渲染
│   ├── memory.py                 # SQLite 版本化案件状态 + 依赖感知缓存
│   ├── verify.py                 # claim-to-evidence 核验
│   └── cli.py                    # demo / chat / 文书命令
├── app/streamlit_app.py
├── external/dlawbench/           # DLawBench adapted run
├── tools/build_corpus.py
├── tools/build_elements.py
├── eval/
└── tests/
```

---

## 8. 交付物

- [报告 PDF（11 页）](report/LexFlow_Report.pdf) ｜ [Markdown 源稿](report/LexFlow_Report.md)
- [外部评测附录 PDF（DLawBench，adapted run）](report/External_Eval_Report.pdf) ｜ [HTML 源稿](report/External_Eval_Report.html)
- [幻灯片 PDF（8 页）](report/LexFlow_Slides.pdf) ｜ [大纲](report/slides_outline.md)
- [5 分钟演示脚本](report/demo_script.md)
- [运行汇总](runs/SUMMARY.md)
- [界面截图](runs/ui_api.png) ｜ [架构图](report/figures/architecture.png) ｜ [结果图](report/figures/results.png)

---

## 9. 已知局限

1. **金额计算有简化**：未接入当地社平工资 3 倍封顶、工伤地方补助金、医疗票据、伤残系数。
2. **规则层是作者编码的**：保证一致性，不保证法律论证正确；高风险结论需律师复核。
3. **外部评测还没跑**：LabourLawBench 需登录下载；LeCoDe 需申请。当前主表是内部 mock 脚本。
4. **知识库是摘要**：不是裁判文书全文；地区差异用 `caveat` 标注。
5. **没有类案检索**：语料只有法条与司法解释 + 实务提示，没有裁判文书；不虚构案号。
6. **时效起算点简化**：以解除日/事故发生日起算，实际可能是送达日、确诊日、鉴定日。
7. **不能预测胜诉率**；不做“包赢”承诺。

---

## 10. 语料来源与重建

`data/corpus/statutes.jsonl` 由 `tools/build_corpus.py` 从 [LawRefBook/Laws](https://github.com/LawRefBook/Laws) 下载并逐条解析。每条记录带 `law_id / article_no / valid_from / valid_to / source`。版本与生效期在 `manifest.json` 中人工核对，特殊说明写在 `note` 字段。

```bash
python3 tools/build_corpus.py            # 联网重建
python3 tools/build_corpus.py --offline  # 用 data/sources 缓存重建
python3 tools/build_elements.py          # 从 Python 源生成 data/elements.json
```

新增法条只需在 manifest 里加一项再跑一次；`corpus_version` 会变化，旧缓存自动失效。

---

## 11. 免责声明

课程演示，非法律服务。系统会明确标注不知道、时效风险、金额假设与需人工核实的材料；使用者不应据此作出法律决定。
