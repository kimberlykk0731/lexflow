#!/usr/bin/env python3
"""Build the static demo card shown in the screen recording.

Reads ``runs/demo/topic_fix.json`` and ``runs/demo/correction_demo.json`` and
writes ``runs/demo/index.html``.  No dependencies, no server: open the file and
record.  The correction cards are click-to-flip so the recording can show the
revision happening instead of reading a static table.

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
:root { --ink:#141d26; --muted:#5d6b7a; --line:#dce3ec; --bg:#f5f7fa;
        --good:#0f7b4f; --goodbg:#e6f4ed; --bad:#a3342c; --badbg:#fbeae7;
        --panel:#ffffff; --accent:#1f4e8c; }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--ink);
       font-family:"PingFang SC","Helvetica Neue",Arial,sans-serif;
       -webkit-font-smoothing:antialiased; }
.wrap { max-width:1100px; margin:0 auto; padding:54px 52px 72px; }
header { padding-bottom:20px; border-bottom:2px solid var(--ink); }
h1 { font-size:38px; margin:0 0 10px; letter-spacing:.5px; }
.hero { font-size:17px; color:var(--muted); margin:0; }
.hero b { color:var(--ink); }
section { margin-top:56px; }
h2 { font-size:25px; margin:0 0 4px; }
h2 .n { color:var(--muted); font-weight:400; margin-right:10px; }
.lead { color:var(--muted); font-size:15px; margin:0 0 22px; }
/* bars */
.bars { background:var(--panel); border:1px solid var(--line); border-radius:10px;
        padding:22px 26px; }
.bar-row { display:grid; grid-template-columns:110px 1fr 78px; align-items:center;
           gap:14px; padding:9px 0; }
.bar-row + .bar-row { border-top:1px dashed var(--line); }
.name { font-size:15px; color:var(--muted); }
.track { position:relative; height:46px; }
.bar { position:absolute; top:0; height:21px; border-radius:5px;
       display:flex; align-items:center; justify-content:flex-end;
       padding:0 9px; font-size:13px; font-variant-numeric:tabular-nums;
       color:#fff; min-width:46px; transition:width .5s ease; }
.bar.before { background:#b9c3cf; }
.bar.after { background:var(--good); top:25px; }
.delta { font-size:20px; font-weight:700; color:var(--good); text-align:right;
         font-variant-numeric:tabular-nums; }
.delta.flat { color:var(--muted); font-weight:400; }
.legend { margin-top:14px; font-size:13px; color:var(--muted); }
.legend span { display:inline-block; width:10px; height:10px; border-radius:2px;
               margin:0 5px 0 16px; vertical-align:middle; }
.legend .sw-before { background:#b9c3cf; }
.legend .sw-after { background:var(--good); }
/* case */
.case { margin-top:24px; background:var(--panel); border:1px solid var(--line);
        border-radius:10px; overflow:hidden; }
.case h3 { margin:0; padding:14px 20px; background:#eef2f7; font-size:16px; }
.cols { display:grid; grid-template-columns:1fr 1fr; }
.cols > div { padding:20px; }
.cols > div + div { border-left:1px solid var(--line); }
.tag { display:inline-block; font-size:12px; letter-spacing:.7px; padding:2px 9px;
       border-radius:99px; margin-bottom:10px; font-weight:600; }
.tag.before { background:var(--badbg); color:var(--bad); }
.tag.after { background:var(--goodbg); color:var(--good); }
.qa { font-size:15px; line-height:1.7; }
.qa .q { color:var(--muted); display:block; margin-top:8px; }
.qa .a { display:block; }
.meta { margin-top:12px; font-size:14px; color:var(--muted); }
/* interactive correction */
.card { margin-top:30px; background:var(--panel); border:1px solid var(--line);
        border-radius:12px; overflow:hidden; }
.card h3 { margin:0; padding:16px 22px; background:#eef2f7; font-size:18px; }
.card h3 span { color:var(--muted); font-weight:400; font-size:14px; margin-left:8px; }
.play { display:flex; align-items:center; gap:14px; padding:16px 22px;
        border-bottom:1px solid var(--line); background:#fbfcfd; }
.play button { border:0; background:var(--accent); color:#fff; font-size:15px;
               padding:11px 20px; border-radius:7px; cursor:pointer;
               font-family:inherit; }
.play button:hover { background:#173d6e; }
.play .hint { color:var(--muted); font-size:14px; }
.states { padding:22px; }
.card[data-state="after"] .state.after { animation:fade .35s ease; }
@keyframes fade { from { transform:translateY(4px); } to { transform:none; } }
.card[data-state="before"] .state.after { display:none; }
.card[data-state="after"] .state.before { display:none; }
.stitle { font-size:13px; letter-spacing:.8px; color:var(--muted); margin-bottom:10px; }
.kv { width:100%; border-collapse:collapse; font-size:15.5px; }
.kv td { padding:10px 12px; border-bottom:1px solid var(--line); vertical-align:top; }
.kv td:first-child { width:120px; color:var(--muted); white-space:nowrap; }
.kv tr:last-child td { border-bottom:none; }
.mono { font-family:Menlo,Consolas,monospace; font-size:14px; }
.delta-line { color:var(--good); font-weight:600; }
.delta-line.bad { color:var(--bad); font-weight:400; }
.sup { margin-top:14px; padding:14px 16px; background:#fbf7ea;
       border:1px solid #e7dcb8; border-radius:7px; font-size:15px; }
.sup .strike { color:var(--bad); text-decoration:line-through; }
.chip { display:inline-block; font-size:13px; padding:2px 9px; border-radius:5px;
        background:#eef2f7; margin-right:6px; }
footer { margin-top:64px; padding-top:20px; border-top:1px solid var(--line);
         color:var(--muted); font-size:13px; line-height:1.95; }
code { background:#eef2f7; padding:1px 6px; border-radius:4px; font-size:13px; }
"""

SCRIPT = """
document.querySelectorAll('.card').forEach(function (card) {
  var button = card.querySelector('button[data-toggle]');
  if (!button) return;
  button.addEventListener('click', function () {
    var before = card.dataset.state !== 'after';
    card.dataset.state = before ? 'after' : 'before';
    button.textContent = before ? '↺ 回到更正前' : button.dataset.label;
  });
});
"""


def esc(value) -> str:
    return html.escape(str(value))


def plain(value) -> str:
    text = str(value).replace("**", "")
    return re.sub(r"^[-•]\s*", "", text.strip())


def show(value) -> str:
    return esc(plain(value))


def render_superseded(line: str) -> str:
    return re.sub(r"~~(.*?)~~", lambda m: f"<span class='strike'>{m.group(1)}</span>", show(line))


def bar_rows(rows: list[dict]) -> str:
    out = []
    for row in rows:
        delta = row["coverage_delta"]
        cls = "" if delta > 0 else " flat"
        out.append(f"""
      <div class="bar-row">
        <div class="name">{esc(row['policy'])}</div>
        <div class="track">
          <div class="bar before" style="width:{row['coverage_before'] * 100:.1f}%">
            {row['coverage_before']:.3f}</div>
          <div class="bar after" style="width:{row['coverage_after'] * 100:.1f}%">
            {row['coverage_after']:.3f}</div>
        </div>
        <div class="delta{cls}">{delta:+.3f}</div>
      </div>""")
    return "".join(out)


def topic_section(payload: dict) -> str:
    before, after = payload["case_before"], payload["case_after"]
    return f"""
<section>
  <h2><span class="n">1</span>客户端披露规则</h2>
  <p class="lead">同一套 30 个案例、同一张问卷、同一判分，只改离线客户端的披露规则。
    问题序列完全没变，所以 Inquiry 一模一样。</p>
  <div class="bars">
    {bar_rows(payload['rows'])}
    <div class="legend"><span class="sw-before"></span>修复前
      <span class="sw-after"></span>修复后（Fact Coverage）</div>
  </div>
  <div class="case">
    <h3>案例 <span class="mono">{esc(payload['case_id'])}</span> · 一条平台事实的两种命运</h3>
    <div class="cols">
      <div>
        <span class="tag before">修复前</span>
        <div class="qa"><span class="q">Q：{show(before['question'])}</span>
          <span class="a">A：{show(before['answer'])}</span></div>
        <div class="meta">对话里出现平台事实：{'✅' if before['disclosed'] else '❌'}
          　备忘录采用：{'✅' if before['memo_has_fact'] else '❌'}
          　Coverage {before['coverage']:.3f}</div>
      </div>
      <div>
        <span class="tag after">修复后</span>
        <div class="qa"><span class="q">Q：{show(after['question'])}</span>
          <span class="a">A：{show(after['answer'])}</span></div>
        <div class="meta">对话里出现平台事实：{'✅' if after['disclosed'] else '❌'}
          　备忘录采用：{'✅' if after['memo_has_fact'] else '❌'}
          　Coverage {after['coverage']:.3f}</div>
      </div>
    </div>
  </div>
</section>"""


def correction_card(record: dict) -> str:
    timing_after = record["timing_after"] or "（无时效警示：更正后不再届满）"
    applicable_after = record["applicable_after"] or "—"
    applicable_before = record["applicable_before"] or "—"
    sup = "".join(f"<div>{render_superseded(line)}</div>"
                  for line in (record["superseded_block"] or ["（无）"]))
    conclusion_class = "delta-line" if record["conclusion_before"] != record["conclusion_after"] else "delta-line bad"
    version_class = "delta-line" if applicable_before != applicable_after else "delta-line bad"
    return f"""
  <div class="card" data-state="before">
    <h3>{esc(record['case_id'])}<span>{esc(record['case_type'])}</span></h3>
    <div class="play">
      <button data-toggle data-label="▶ 播放客户更正">▶ 播放客户更正</button>
      <div class="hint">“{show(record['correction'])}”</div>
    </div>
    <div class="states">
      <div class="state before">
        <div class="stitle">更正前</div>
        <table class="kv">
          <tr><td>解除/事故日</td><td class="mono">{esc(record['old'])}</td></tr>
          <tr><td>时效</td><td>{show(record['timing_before'] or '—')}</td></tr>
          <tr><td>结论</td><td>{show(record['conclusion_before'] or '—')}</td></tr>
          <tr><td>适用版本</td><td>{show(applicable_before)}</td></tr>
        </table>
      </div>
      <div class="state after">
        <div class="stitle">客户更正后</div>
        <table class="kv">
          <tr><td>解除/事故日</td>
              <td class="mono">{esc(record['old'])} → <b>{esc(record['new'])}</b></td></tr>
          <tr><td>时效</td><td>{show(timing_after)}</td></tr>
          <tr><td>结论</td><td class="{conclusion_class}">{show(record['conclusion_after'] or '—')}</td></tr>
          <tr><td>适用版本</td><td class="{version_class}">{show(applicable_after)}</td></tr>
        </table>
        <div class="sup"><b>已被更正的事实</b>（旧值不再作为结论依据）{sup}</div>
      </div>
    </div>
  </div>"""


def correction_section(payload: dict) -> str:
    return f"""
<section>
  <h2><span class="n">2</span>更正传播</h2>
  <p class="lead">客户改口之后，事实表、结论和适用法条版本一起更新。点按钮看它发生。</p>
  {''.join(correction_card(record) for record in payload['records'])}
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
  <p class="hero">同一个律师、同一套题：<b>问题没变，客户肯说了</b>；<b>客户改口，结论跟着改</b>。</p>
</header>
{topic_section(topic)}
{correction_section(correction)}
<footer>
  复现：<code>make demo-cards</code>（或分别跑
  <code>python external/dlawbench/demo_topic_fix.py</code>、
  <code>PYTHONPATH=src python eval/correction_demo.py</code>）<br>
  说明：两个 demo 都是机制演示，不是基准结果；extended 客户端默认关闭，
  已提交的 30 案主表数字不受影响。
</footer>
</div><script>{SCRIPT}</script></body></html>"""
    (DEMO / "index.html").write_text(page, encoding="utf-8")
    print(f"[out] {DEMO / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
