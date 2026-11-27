# 两个机制 demo（录屏用）

一页静态页面，展示两个机制，不需要起服务：

```bash
make demo-cards
open runs/demo/index.html      # macOS；Linux 用 xdg-open
```

页面分两节：

1. **客户端披露规则**：同一套 30 个 DLawBench 中文案例、同一张问卷、同一判分，只改离线
   客户端的披露规则。两条柱状图对比修复前后的 Fact Coverage，下面是一个具体案例
   （`case_cn_0007` 的平台事实）修复前/后的问答对照。**Inquiry 完全不变**——问题序列没变，
   涨的全部是客户端肯说。
2. **更正传播**：两个案例（L07 解除日期、T05 事故日期），点“播放客户更正”按钮，页面从
   “更正前”切到“更正后”，能看到结论、时效、适用法条版本一起变，旧值进入“已被更正”的
   删除线。

## 数字（demo 级，不是基准结果）

| Policy | Fact Coverage 前 | 后 | Δ | Inquiry 前 | 后 |
|---|---:|---:|---:|---:|---:|
| full | 0.696 | 0.851 | +0.155 | 0.228 | 0.228 |
| gate_only | 0.628 | 0.713 | +0.085 | 0.216 | 0.216 |

- **默认客户端没有改**：extended 模式由 `LEXFLOW_CLIENT_EXTENDED=1` 打开，所以
  `runs/external/` 里已提交的主表数字不受影响。
- 两个 demo 都只用于展示机制，不构成 benchmark 结论。

## 脚本

| 脚本 | 作用 |
|---|---|
| `external/dlawbench/demo_topic_fix.py` | 跑修复前/后两套 30 案矩阵，写 `runs/demo/topic_fix.{md,json}` |
| `eval/correction_demo.py` | 真 `ConsultationAgent` 跑 L07/T05 的更正，写 `runs/demo/correction_demo.{md,json}` |
| `eval/build_demo_page.py` | 读两份 json，写 `runs/demo/index.html` |

## 录屏口径

- 第 1 节一句话：“同一个律师、同一套题，问题没变（Inquiry 一模一样），只是客户端肯说，
  coverage 从 0.696 到 0.851。”
- 第 2 节点按钮，一句话：“客户改口，解除日期从 2025-08 改成 2026-02，时效从已过变成还剩
  75 天；旧值只留在删除线里。”T05 再补一句：“事故日期跨过 2022-05-01，适用解释从 2022
  版切到 2020 版。”
