# LexFlow 当前运行结果索引

## 最新真实API运行（用户本地结果）

- [修复前基线](bench_v2/api_test_baseline/SUMMARY.md)与[修复后结果](bench_v2/api_test_revised/SUMMARY.md)：每轮26个测试案例、3个表达版本、4配置，共312会话。
- 修复后full：正确事实覆盖99.3%，公式一致100.0%（15个适用案例），更正成功100.0%；仍有7/78会话存在关键字段缺口。
- [本地运行记录](../docs/LOCAL_API_REPORT_20261127.md)；[七例辅助初核](../docs/BENCH_V2_REVIEW_NOTES.md)。人工法律审定仍为pending，复测不作为外部盲测。
- 逐案CSV/JSONL、配置及汇总随仓库保存；完整逐轮轨迹保留在本地，可按相同命令重跑。

## 早期mock运行存档

日期：2026-11-27。当前评测入口为Bench v2.0.1；原README中的12例表格保留为历史记录，不作为新增12类劳动请求权的现行结果。

- [v2主表](bench_v2/v2_0_1/test_mock/SUMMARY.md)：26个测试案例、4配置、3表达，312会话；full正确事实覆盖57.6%，独立公式一致64.4%（适用15案例）。
- [实施报告](../docs/BENCH_REPORT_V2.md)；[复现说明](../docs/BENCH_V2_GUIDE.md)。
- [独立参考交叉检查](bench_v2/v2_0_1/oracle_crosscheck.json)：50阶段，既定断言无不一致；非法律正确率100%。
- [核验与修复注入](bench_v2/v2_0_1/verifier_repair.json)：20次均检出；只有引文错误的4次清除了全部机械缺陷。
- [VOI四题预算](bench_v2/v2_0_1/voi_budget4/SUMMARY.md)；[八题预算](bench_v2/v2_0_1/voi_budget8/SUMMARY.md)。
- [版本记忆故障对照](bench_v2/v2_0_1/revision_fault/SUMMARY.md)。
- [旧12例当前回归](bench_v2/legacy_final/eval_table.md)：full金额/期限/版本一致率100%；问题数现在包含重复问题。
- [人工审查状态](bench_v2/v2_0_1/review/review_status.json)：7例已抽取，人工审定pending，模型审题未运行。

本节所列v2.0.1为早期mock存档；最新真实API结果见上方入口，二者不混为同一实验。完整轨迹不纳入git版本控制。
