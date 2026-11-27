# LexFlow Bench v2 运行说明

代码基于上游 f8db186b0bc597b1c7eab64b3094cd70103190fc。评测核心只使用Python标准库；不需要GPU，不需要启动Streamlit。

## 文件与职责

| 文件 | 职责 |
|---|---|
| eval/gen_cases.py、case_seeds.py | 38个设计种子/模板案例；可选API开场改写，不能改写事实和gold |
| eval/reference_oracle.py | 独立公式，不导入生产规则 |
| eval/oracle.py | 把生产规则与独立gold交叉检查，不生成gold |
| eval/validate_cases.py | 枚举、日期、去重、gold重现、分支覆盖与审定状态 |
| eval/review_cases.py | 案例卡、7例人工抽查表、可选不同模型审题 |
| eval/protocol_v2.py、metrics_v2.py | 只通过对话披露事实，逐请求权评分与更正评分 |
| eval/api_audit.py | 全部模型调用站点的成功/失败、重试、tokens |
| eval/run_evals_v2.py | 主评测、分诊专项、CSV、轨迹、案例聚类区间 |
| eval/verify_bench_v2.py | 隔离注入错误，区分检出与真正修复 |

## 离线复现

在仓库根目录执行，输出目录必须是新目录。

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 eval/validate_cases.py
python3 eval/oracle.py --out runs/bench_v2/my_oracle.json
python3 eval/verify_bench_v2.py --out runs/bench_v2/my_verifier.json
PYTHONPATH=src python3 eval/run_evals_v2.py --split test --llm mock --repeats 3 --out runs/bench_v2/my_mock
```

主表是26个测试案例、4配置、3个固定措辞变体，共312会话。`--repeats`取1、2或3，指固定表达版本，不表示模型随机种子。`--seed`仅控制bootstrap。默认单会话最多14个问题，每阶段最多12轮；更正前后的问题数累计。

```bash
PYTHONPATH=src python3 eval/run_evals_v2.py --split test --conditions full,full_no_voi --max-questions 4 --skip-router --out runs/bench_v2/my_voi4
PYTHONPATH=src python3 eval/run_evals_v2.py --split test --conditions full,full_no_voi --max-questions 8 --skip-router --out runs/bench_v2/my_voi8
PYTHONPATH=src python3 eval/run_evals_v2.py --split test --conditions full_no_revision --skip-router --out runs/bench_v2/my_revision_fault
```

## 接入真实模型

使用本地环境变量或仓库已有的.env配置机制设置以下名称；不要提交密钥文件。

```text
LLM_API_KEY
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
```

```bash
PYTHONPATH=src python3 eval/run_evals.py --llm api --limit 3 --conditions full --out runs/bench_v2/my_api_connection_check
PYTHONPATH=src python3 eval/run_evals_v2.py --split dev --llm api --conditions full --repeats 1 --out runs/bench_v2/my_api_smoke
PYTHONPATH=src python3 eval/run_evals_v2.py --split test --llm api --repeats 3 --out runs/bench_v2/my_api_test
```

第一条API命令用旧3例做连通检查，不计入v2主表。API模式缺密钥立即报错，不会替换成mock；mock模式也不会受已有API环境变量影响而意外调用付费模型。接口失败或模型JSON抽取失败仍可能触发产品自身的规则兜底，这会在调用记录与fallback比例中显式保留。没有成功模型调用时API运行以非零状态退出。

需要费用估算时，同时提供`--input-price-per-million`和`--output-price-per-million`，数值取实际账单单价。未配置时费用为空；不能沿用仓库历史硬编码价格作为当前价格。

## 生成、审题与人工抽查

已交付的数据内容通过SHA-256固定。修改种子、假设或gold后需发布数据新版本并重跑全部配置，不能只重跑表现差的配置。

```bash
# 重建独立目录，避免覆盖已发布的数据
python3 eval/gen_cases.py --out-dir data/eval/rebuilt_v2
# 可选API口语改写；事实与gold保持固定，语义仍需复核
python3 eval/gen_cases.py --rewrite-api --model YOUR_GENERATOR_MODEL --out-dir data/eval/api_surfaces_v2
python3 eval/review_cases.py --out runs/bench_v2/my_review
# 可选不同模型审题：使用已配置的兼容接口，review-model应与生成器不同
python3 eval/review_cases.py --llm api --review-model YOUR_REVIEW_MODEL --out runs/bench_v2/my_model_review
```

`human_review_sample.csv`中的7例需核对真实性、事实一致性、假设和gold依据，填写结论与理由。发现问题应修正题目或规则并记录版本，不能把“不得改gold”作为保留错误的理由。案例JSON的`review.human_status`由实际审查者更新为`approved`；模型审题不会自动改成人工通过。

```bash
python3 eval/validate_cases.py --require-human-review
```

## 看结果与分母

`SUMMARY.md`为主表，`summary.json`有完整分母、案例聚类置信区间和配置差值；`results.csv`用于筛选失败，`results.jsonl`保留逐断言证据，`trajectories/`保留所有轮次。

正确事实覆盖以本案适用且可获知的关键事实为分母，未知事实不按“有值”算正确。抽取评分只给已在对话披露的真值记分。初始请求权F1仅看首次分诊。公式分数与作者指定的行为断言分开；不存在全案例通用的“金额准确率”。

客户模拟器按结构化问题key回答，因此不能证明问题措辞对真人有效。更正成功率仅在完成更正协议的案例中统计，同时单报协议完成率。过早无条件备忘录、信息不足处理只是结构代理指标；法律论证和自然语言承诺需人工审查。

## 本轮结论范围

当前是工程评测，非经过律师审定的法律能力基准。38例来自设计种子/模板；3种表达不代表充分的自然语言多样性；预留测试分组非外部盲测。旧12例回归、DLawBench离线adapted run与v2主表分开报告。详细结果见BENCH_REPORT_V2.md。
