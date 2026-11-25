#!/usr/bin/env python3
"""Build the static demo card shown in the screen recording.

Reads ``runs/demo/topic_fix.json`` and ``runs/demo/correction_demo.json`` and
writes ``runs/demo/index.html``.  No dependencies, no server: open the file and
record.

    python eval/build_demo_page.py
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "runs" / "demo"

STYLE = """
:root { --ink:#16202b; --muted:#5b6b7c; --line:#dbe3ec; --bg:#f6f8fb;
        --good:#0f7b4f; --bad:#a3342c; --panel:#ffffff; }
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--ink);
       font-family:"PingFang SC","Helvetica Neue",Arial,sans-serif; }
.wrap { max-width:1120px; margin:0 auto; padding:56px 56px 80px; }
header { border-bottom:2px solid var(--ink); padding-bottom:18px; margin-bottom:40px; }
h1 { font-size:34px; margin:0 0 8px; letter-spacing:.3px; }
header .sub { color:var(--muted); font-size:15px; }
section { margin:52px 0 0; }
h2 { font-size:24px; margin:0 0 6px; }
h2 .n { display:inline-block; width:30px; color:var(--muted); font-weight:400; }
.lead { color:var(--muted); font-size:15px; margin:0 0 20px; }
table { width:100%; border-collapse:collapse; background:var(--panel);
        border:1px solid var(--line); font-size:17px; }
th, td { padding:12px 14px; border-bottom:1px solid var(--line); text-align:left; }
th { background:#eef2f7; font-size:14px; color:var(--muted); font-weight:600; }
td.num, th.num { text-align:right; font-variant-numeric:tabular-nums; }
tr:last-child td { border-bottom:none; }
.up { color:var(--good); font-weight:700; }
.flat { color:var(--muted); }
.case { margin-top:26px; background:var(--panel); border:1px solid var(--line);
        border-radius:8px; overflow:hidden; }
.case h3 { margin:0; padding:14px 18px; background:#eef2f7; font-size:16px; }
.cols { display:grid; grid-template-columns:1fr 1fr; }
.cols > div { padding:18px; }
.cols > div + div { border-left:1px solid var(--line); }
.tag { display:inline-block; font-size:12px; letter-spacing:.6px; padding:2px 8px;
       border-radius:99px; margin-bottom:10px; }
.tag.before { background:#fbe9e7; color:var(--bad); }
.tag.after { background:#e3f4ec; color:var(--good); }
.qa { font-size:15px; line-height:1.65; margin:8px 0 0; color:var(--ink); }
.qa .q { color:var(--muted); display:block; margin-bottom:2px; }
.qa .a { display:block; }
.chip { display:inline-block; font-size:14px; padding:2px 9px; border-radius:5px;
        background:#eef2f7; margin-right:6px; }
.correction { margin:34px 0 0; background:var(--panel); border:1px solid var(--line);
              border-radius:8px; overflow:hidden; }
.correction h3 { margin:0; padding:14px 18px; background:#eef2f7; font-size:17px; }
.correction .quote { padding:14px 18px; border-bottom:1px solid var(--line);
                     color:var(--muted); font-size:16px; }
.correction .quote b { color:var(--ink); }
.correction .body { padding:18px; }
.mono { font-family:Menlo,Consolas,monospace; font-size:13px; }
.sup { margin-top:16px; padding:14px 16px; background:#fbf7ea; border:1px solid #e7dcb8;
       border-radius:6px; font-size:15px; }
.sup .strike { color:var(--bad); text-decoration:line-through; }
footer { margin-top:60px; padding-top:20px; border-top:1px solid var(--line);
         color:var(--muted); font-size:13px; line-height:1.9; }
code { background:#eef2f7; padding:1px 5px; border-radius:4px; font-size:13px; }
"""


def esc(value) -> str:
    return html.escape(str(value))


def plain(value) -> str:
    """Strip the light markdown the memo uses (bold, bullets)."""
    text = str(value).replace("**", "")
    return re.sub(r"^[-•]\s*", "", text.strip())


def show(value) -> str:
    return esc(plain(value))


def render_superseded(line: str) -> str:
    """Render ``~~old~~ -> vN`` with the old value struck through."""
    return re.sub(r"~~(.*?)~~", r"<span class='strike'>\1</span>", show(line))


def topic_section(payload: dict) -> str:
    rows = payload["rows"]
    body = []
    for row in rows:
        delta = row["coverage_delta"]
        cls = "up" if delta > 0 else "flat"
        body.append(
            f"<tr><td>{esc(row['policy'])}</td>"
            f"<td class='num'>{row['n']}</td>"
            f"<td class='num'>{row['coverage_before']:.3f}</td>"
            f"<td class='num'>{row['coverage_after']:.3f}</td>"
            f"<td class='num {cls}'>{delta:+.3f}</td>"
            f"<td class='num'>{row['inquiry_before']:.3f}</td>"
            f"<td class='num'>{row['inquiry_after']:.3f}</td></tr>")
    before, after = payload["case_before"], payload["case_after"]
    return f"""
<section>
  <h2><span class="n">1</span>客户端披露规则</h2>
  <p class="lead">同一套 30 个案例、同一张问卷、同一判分，只改离线客户端的披露规则。</p>
  <table>
    <thead><tr><th>Policy</th><th class="num">n</th>
      <th class="num">Fact Coverage 修复前</th><th class="num">修复后</th>
      <th class="num">Δ</th><th class="num">Inquiry 修复前</th>
      <th class="num">修复后</th></tr></thead>
    <tbody>{''.join(body)}</tbody>
  </table>
  <div class="case">
    <h3>案例 <span class="mono">{esc(payload['case_id'])}</span> · 平台事实</h3>
    <div class="cols">
      <div>
        <span class="tag before">修复前</span>
        <div class="qa"><span class="q">Q：{show(before['question'])}</span>
          <span class="a">A：{show(before['answer'])}</span></div>
        <p class="lead" style="margin-top:12px">对话里出现平台事实：
          {'✅' if before['disclosed'] else '❌'}　备忘录采用：
          {'✅' if before['memo_has_fact'] else '❌'}　Coverage
          {before['coverage']:.3f}</p>
      </div>
      <div>
        <span class="tag after">修复后</span>
        <div class="qa"><span class="q">Q：{show(after['question'])}</span>
          <span class="a">A：{show(after['answer'])}</span></div>
        <p class="lead" style="margin-top:12px">对话里出现平台事实：
          {'✅' if after['disclosed'] else '❌'}　备忘录采用：
          {'✅' if after['memo_has_fact'] else '❌'}　Coverage
          {after['coverage']:.3f}</p>
      </div>
    </div>
  </div>
  <p class="lead" style="margin-top:16px">Inquiry 完全不变：问题序列没变，涨的全部是客户端肯说。</p>
</section>"""


def correction_section(payload: dict) -> str:
    blocks = []
    for record in payload["records"]:
        timing_after = record["timing_after"] or "（无时效警示：更正后不再届满）"
        applicable_after = record["applicable_after"] or "—"
        applicable_before = record["applicable_before"] or "—"
        sup = "".join(f"<div>{render_superseded(line)}</div>"
                      for line in (record["superseded_block"] or ["（无）"]))
        blocks.append(f"""
  <div class="correction">
    <h3>{esc(record['case_id'])} <span class="mono">· {esc(record['case_type'])}</span></h3>
    <div class="quote">客户更正：<b>“{show(record['correction'])}”</b></div>
    <div class="body">
      <table>
        <thead><tr><th></th><th>更正前</th><th>更正后</th></tr></thead>
        <tbody>
          <tr><td>原值 → 新值</td>
              <td class="mono">{esc(record['old'])}</td>
              <td class="mono">{esc(record['new'])}</td></tr>
          <tr><td>时效</td><td>{show(record['timing_before'] or '—')}</td>
              <td>{show(timing_after)}</td></tr>
          <tr><td>结论</td><td>{show(record['conclusion_before'] or '—')}</td>
              <td>{show(record['conclusion_after'] or '—')}</td></tr>
          <tr><td>适用版本</td><td>{show(applicable_before)}</td>
              <td>{show(applicable_after)}</td></tr>
        </tbody>
      </table>
      <div class="sup"><b>已被更正的事实</b>{sup}</div>
    </div>
  </div>""")
    return f"""
<section>
  <h2><span class="n">2</span>更正传播</h2>
  <p class="lead">客户改口后，事实表版本、结论和适用法条版本一起更新。</p>
  {''.join(blocks)}
</section>"""


def main() -> int:
    topic = json.loads((DEMO / "topic_fix.json").read_text(encoding="utf-8"))
    correction = json.loads((DEMO / "correction_demo.json").read_text(encoding="utf-8"))
    page = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>LexFlow · 两个机制 demo</title><style>{STYLE}</style></head>
<body><div class="wrap">
<header>
  <h1>LexFlow · 两个机制 demo</h1>
  <div class="sub">DLawBench 外部协议 · mock LLM（规则层） · 2026-11-25</div>
</header>
{topic_section(topic)}
{correction_section(correction)}
<footer>
  复现：<code>python external/dlawbench/demo_topic_fix.py</code> ·
  <code>PYTHONPATH=src python eval/correction_demo.py</code> ·
  <code>python eval/build_demo_page.py</code><br>
  说明：两个 demo 都是机制演示，不是基准结果；默认客户端未开启 extended 模式，
  已提交的 30 案主表数字不受影响。
</footer>
</div></body></html>"""
    (DEMO / "index.html").write_text(page, encoding="utf-8")
    print(f"[out] {DEMO / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
