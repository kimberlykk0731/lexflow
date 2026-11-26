# LexFlow — 先问再答的法律咨询 Agent

NLP 课程项目。一个面向**法律咨询**（而不是法律检索）的 Agent：它先判断“现在掌握的事实够不够下结论”，缺关键事实就追问；事实齐备后检索**案发时有效**的法条、做确定性计算、生成带引用与信息缺口的备忘录；当事人更正事实后，它重算而不是沿用旧结论。

> 本项目是课程演示，输出不构成法律意见。法条原文来自公开整理仓库，正式引用应以 [国家法律法规数据库](https://flk.npc.gov.cn/) 为准。

---

## 1. 一句话卖点

**大多数法律 RAG 回答“问题”，LexFlow 先判断“这个问题现在能不能回答”。**

三个可测量的机制：

| 机制 | 做法 | 对应指标 |
|---|---|---|
| 要件事实门控 | 每个案由维护一份「要件事实」schema；关键事实缺失就追问，不硬答 | 事实覆盖率、过早结论率、追问召回 |
| 时间效力 | 法条按版本/生效期入库；检索与引用都限定在案发日有效的版本 | 版本选择一致率、时效一致率 |
| 版本化案件记忆 | 事实带来源、修订号、被取代链；更正后只失效依赖该事实的缓存与结论 | 旧结论残留率、缓存失效条数 |

另有一个机械核验器：引用是否存在、是否在案发日有效、引文是否对得上、结论金额是否等于计算结果、所依赖事实是否已被更正。

---

## 2. 快速开始（无需 API Key）

```bash
# 在仓库根目录执行
PYTHONPATH=src python3 -m lexflow.cli demo          # 6 轮劳动争议演示 + 备忘录
PYTHONPATH=src python3 eval/run_evals.py            # 12 个脚本案例 × 4 配置消融
PYTHONPATH=src python3 eval/verify_probe.py         # 给核验器注入 5 类错误
PYTHONPATH=src python3 eval/cache_bench.py          # 缓存命中与失效
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

零第三方依赖即可跑通；`mock` 模式是确定性的工程脚手架，**不是模型能力结论**。

### 接入真实模型

```bash
export LEXFLOW_LLM=api
export LLM_BASE_URL=https://api.deepseek.com/v1   # 或任意 OpenAI-compatible 端点
export LLM_API_KEY=sk-...
export LLM_MODEL=deepseek-chat
PYTHONPATH=src python3 -m lexflow.cli chat
```

模型只负责**事实抽取**和**白话解释**；是否追问、引用哪条法条、金额与期限怎么算，由确定性规则层完成。这样引用和数字才可核验、可复现。

### 网页演示

```bash
pip install streamlit
PYTHONPATH=src streamlit run app/streamlit_app.py
```

左侧对话，右侧实时看事实表、备忘录、争点依据和执行轨迹。

---

## 3. 目录

```
lexflow/
├── README.md                     # 本文件
├── QUICKSTART.md                 # 三种打开方式：看报告 / 本地跑 / 部署
├── Makefile                      # demo / ui / report / test 快捷命令
├── requirements.txt
├── .env.example                  # 真实模型配置样例（不含密钥）
├── data/
│   ├── corpus/manifest.json      # 15 部法律法规/司法解释的版本与生效期
│   ├── corpus/statutes.jsonl     # 1340 条法条（生成物，已提交）
│   ├── elements.json             # 两个案由的要件事实 schema 与追问话术
│   └── eval/scripted_cases.json  # 12 个脚本案例（隐藏事实 + 金标准 + 更正）
├── src/lexflow/
│   ├── corpus.py                 # BM25 检索 + 版本过滤 + 新旧版本定位
│   ├── elements.py               # 要件 schema、充分性判断、日期/金额归一化
│   ├── extract.py                # 事实抽取：LLM 优先，规则兜底（含更正识别）
│   ├── rules.py                  # 确定性法律层：时效、补偿、版本、侵权标准
│   ├── agent.py                  # intake → gate → research → memo → verify
│   ├── memo.py                   # 备忘录渲染
│   ├── verify.py                 # claim-to-evidence 核验
│   ├── memory.py                 # SQLite 版本化案件状态 + 依赖感知缓存
│   ├── tools.py                  # 工具封装（检索/取条文/计算/规则分析）
│   ├── llm.py                    # OpenAI-compatible 适配器 + mock
│   └── cli.py                    # demo / chat
├── eval/
│   ├── protocol.py               # 脚本化当事人 + 指标
│   ├── run_evals.py              # 消融主脚本
│   ├── verify_probe.py           # 核验器注入测试
│   └── cache_bench.py            # 缓存实验
├── app/streamlit_app.py
├── tools/build_corpus.py         # 从 LawRefBook 重新生成语料
├── tests/
├── docs/                         # 评测设计、盲审表、2026 法律 AI 调研
│   └── proposal/                 # 英文 proposal 源稿
├── report/                       # 报告与幻灯片（PDF + 源稿）、图、演示脚本
└── runs/                         # 评测输出、截图、SUMMARY
```

---

## 4. 它怎么工作

```
用户输入
  │
  ├─ 事实抽取（LLM / 规则）──→ 版本化案件记录（来源、修订号、取代链）
  │                                   │
  │                          事实冲突？→ 不覆盖材料记载，要求核对原件
  │
  ├─ 充分性门控：要件事实齐了吗？
  │        ├─ 否 → 按“法律杠杆”排序追问 1–2 个问题（时效 → 解除依据 → 计算）
  │        └─ 是 → 研究
  │
  ├─ 研究：按案发日过滤法条版本 → 检索 → 规则分析（时效/补偿/版本）
  │
  ├─ 备忘录：结论 / 事实状态 / 争点与依据 / 缺口 / 下一步材料 / 引用版本表
  │
  └─ 核验：引用存在？案发日有效？引文对得上？金额=计算值？事实没过期？
           └─ 有缺陷 → 有界修复（换正确版本 / 去错引文），再核验一次
```

### 为什么“追问”是有意义的 agent 行为

同一句“公司把我辞退了”，在知道/不知道解除日期、制度是否公示、是否通知工会时，结论可以从“2N 赔偿”变成“时效已过、先解决时效抗辩”。追问不是礼貌，是在**缩小假设空间**。项目把这件事做成可测量的：缺哪些字段、先问哪个、问几次、什么时候必须停下来承认不知道。

### 时间效力为什么值得做

- 劳动争议：2008-05-01 前仲裁申请期是 **60 日**（劳动法第 82 条），之后是 **1 年**（调解仲裁法第 27 条）。
- 人身损害：2017-10-01 前身体受伤诉讼时效 **1 年**（民法通则第 136 条），之后 **3 年**（民法总则/民法典第 188 条）。
- 赔偿标准：2022-05-01 前残疾/死亡赔偿金区分城乡，之后统一按城镇居民标准。
- 2021-01-01 前适用《侵权责任法》，之后适用《民法典》侵权责任编。

这些边界都能在 `data/corpus/manifest.json` 里查到，并由 `rules.py` 按案发日选择。检索时若拿到的是案发日尚未生效的版本，核验器会报 `VERSION_NOT_IN_FORCE`。

---

## 5. 评测怎么讲得通

主实验是**受控咨询协议**：12 个案例（7 劳动 + 5 侵权），每个案例有隐藏事实表；脚本化当事人只回答被问到的问题，其余回答“不清楚”；其中 2 个案例在第一次备忘录之后给出更正。金标准结论由作者依据法条手工计算，不由系统生成。

四个配置：

- `answer_first`：不追问、不核验，直接出结论（“搜索助手”基线）
- `gate_only`：追问 + 检索 + 备忘录
- `full`：追问 + 检索 + 核验/修复 + 版本化记忆
- `full_no_revision`：刻意复用更正前的分析，模拟“事实改了、结论没改”

当前 **DeepSeek API** 结果（`runs/SUMMARY.md`；12 案例 × 4 配置，共 149k 输入 + 11k 输出 tokens，约 **0.17 元**）：

| 条件 | 事实覆盖率 | 追问召回 | 过早结论率 | 引用可核验率 | 旧结论残留 |
|---|---:|---:|---:|---:|---:|
| answer_first | 57.5% | 41.7% | 58.3% | 83.3% | — |
| gate_only | 100% | 100% | 0% | 100% | 0% |
| full | 100% | 100% | 0% | 100% | 0% |
| full_no_revision | 100% | 100% | 0% | 92.2% | 100% |

注意：`full` 在“违法认定/金额/时效/版本”上的 100% 是**规则层与金标准同源**导致的，只能说明管线一致，不能说明法律能力。真正有信息量的是：追问把覆盖率从 57.5% 拉到 100%、把过早结论率从 58.3% 压到 0%；版本化记忆把旧结论残留从 100% 压到 0%。

核验器的价值用注入测试单独衡量（`runs/verify_probe.json`）：5 类缺陷各注入 12 次（金额类 7 次），检出率均为 100%，干净分析 0 误报。

缓存实验（`runs/cache_bench.json`）：同一轮无新事实重放，开缓存执行 0 次、命中 18 次；关缓存执行 18 次。更正一个日期后，只失效 1 条依赖该事实的缓存，其余 10 次调用继续命中。

详见 [`docs/eval_design.md`](docs/eval_design.md)。

### 5.1 外部检查：DLawBench ask-first 策略（adapted run）

主报告的 12-case controlled protocol 已经测了 gate 本体（critical-fact coverage
57.5%→100%，premature advice 58.3%→0%）。这一节把同一套 ask-first 策略接到
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

## 6. 交付物

- [报告 PDF（7 页）](report/LexFlow_Report.pdf) ｜ [Markdown 源稿](report/LexFlow_Report.md)
- [外部评测附录 PDF（DLawBench，adapted run）](report/External_Eval_Report.pdf) ｜ [HTML 源稿](report/External_Eval_Report.html)
- [幻灯片 PDF（8 页）](report/LexFlow_Slides.pdf) ｜ [大纲](report/slides_outline.md)
- [5 分钟演示脚本](report/demo_script.md)
- [运行汇总（API 主结果 + mock 附录）](runs/SUMMARY.md)
- [界面截图](runs/ui_api.png) ｜ [架构图](report/figures/architecture.png) ｜ [结果图](report/figures/results.png)

---

## 7. 已知局限

1. **覆盖案由少**：只有劳动争议解除、交通事故人身损害两个 schema，不能外推为通用法律 AI。
2. **已用真实 API 跑过，但样本小**：12 案例 × 4 配置，DeepSeek 官方 API，约 0.17 元；mock 只保留作离线兜底。
3. **规则层是作者编码的**：它能保证一致性，不保证法律论证正确；需要人工盲审。
4. **金额计算有简化**：未接入当地社平工资、奖金口径、伤残系数、医疗票据；结果只作区间与项目清单。
5. **脚本化当事人过于配合**：真实当事人会答非所问、情绪化、隐瞒；DLawBench 的四种人格可作下一阶段扩展。
6. **没有类案检索**：语料只有法条与司法解释，没有裁判文书；避免用虚构类案冒充真实裁判。
7. **时效起算点简化**：以解除日/事故发生日起算，实际可能是送达日、确诊日、鉴定日。

---

## 8. 语料来源与重建

`data/corpus/statutes.jsonl` 由 `tools/build_corpus.py` 从 [LawRefBook/Laws](https://github.com/LawRefBook/Laws) 下载并逐条解析，共 15 部法律法规/司法解释、1340 条。每条记录带 `law_id / article_no / valid_from / valid_to / source`。版本与生效期在 `manifest.json` 中人工核对，特殊说明写在 `note` 字段。

```bash
python3 tools/build_corpus.py            # 联网重建
python3 tools/build_corpus.py --offline  # 用 data/sources 缓存重建
```

新增法条只需在 manifest 里加一项，再跑一次；`corpus_version` 会变化，旧缓存自动失效。

---

## 9. 免责声明

课程演示，非法律服务。系统会明确标注不知道、时效风险、金额假设与需人工核实的材料；使用者不应据此作出法律决定。
