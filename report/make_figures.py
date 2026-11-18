#!/usr/bin/env python3
"""Generate the result chart and the architecture diagram (no matplotlib)."""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "report" / "figures"
FIG.mkdir(parents=True, exist_ok=True)
FONT = "/System/Library/Fonts/Supplemental/Arial.ttf"

CONDITIONS = [
    ("answer_first", "Answer-first"),
    ("gate_only", "Gate only"),
    ("full", "Full"),
    ("full_no_revision", "Full w/o revision"),
]
METRICS = [
    ("coverage", "Coverage", (37, 99, 235)),
    ("premature_rate", "Premature advice", (220, 38, 38)),
    ("stale_rate", "Stale conclusions", (217, 119, 6)),
]


def font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT, size)


def draw_chart() -> None:
    data = json.loads((ROOT / "runs" / "api" / "eval_results.json").read_text(encoding="utf-8"))
    agg = data["aggregate"]
    W, H = 1240, 660
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    left, top, right, bottom = 90, 175, W - 50, H - 80
    d.text((40, 26), "LexFlow ablation: 12 scripted consultations (DeepSeek API)",
           font=font(28), fill=(15, 23, 42))
    d.text((40, 68), "Behavioral metrics; n = 12, descriptive only. Higher coverage is better; "
                     "lower premature / stale is better.", font=font(16), fill=(71, 85, 105))

    # legend on its own row
    lx = 40
    for _, label, color in METRICS:
        d.rounded_rectangle([lx, 103, lx + 14, 117], radius=3, fill=color)
        d.text((lx + 20, 99), label, font=font(14), fill=(51, 65, 85))
        lx += 190

    for v in range(0, 101, 25):
        y = bottom - (bottom - top) * v / 100
        d.line([(left, y), (right, y)], fill=(226, 232, 240), width=1)
        d.text((left - 50, y - 9), f"{v}%", font=font(14), fill=(100, 116, 139))
    d.line([(left, top), (left, bottom)], fill=(148, 163, 184), width=2)
    d.line([(left, bottom), (right, bottom)], fill=(148, 163, 184), width=2)

    group_w = (right - left) / len(CONDITIONS)
    bar_w, gap = 46, 10
    for gi, (cond, label) in enumerate(CONDITIONS):
        gx = left + gi * group_w + group_w / 2
        start = gx - (len(METRICS) * bar_w + (len(METRICS) - 1) * gap) / 2
        for mi, (key, _, color) in enumerate(METRICS):
            value = agg.get(cond, {}).get(key)
            value = 0.0 if value is None else float(value) * 100
            x0 = start + mi * (bar_w + gap)
            y0 = bottom - (bottom - top) * value / 100
            d.rounded_rectangle([x0, y0, x0 + bar_w, bottom], radius=4, fill=color)
            d.text((x0 + bar_w / 2, max(y0 - 22, top - 4)), f"{value:.0f}%", font=font(14),
                   fill=(30, 41, 59), anchor="mm")
        d.text((gx, bottom + 22), label, font=font(16), fill=(30, 41, 59), anchor="mm")

    d.text((40, H - 34), "Source: runs/api/eval_results.json. Rule layer and gold are "
                         "same-author; the behavioral deltas are the informative part.",
           font=font(13), fill=(100, 116, 139))
    img.save(FIG / "results.png")


def svg_box(x, y, w, h, title, sub="", fill="#f8fafc", stroke="#cbd5e1"):
    parts = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" '
             f'fill="{fill}" stroke="{stroke}" stroke-width="2"/>']
    ty = y + h / 2 - (10 if sub else 0)
    parts.append(f'<text x="{x + w/2}" y="{ty}" text-anchor="middle" '
                 f'font-family="Helvetica, Arial" font-size="17" font-weight="600" '
                 f'fill="#0f172a">{title}</text>')
    if sub:
        for i, line in enumerate(sub.split("|")):
            parts.append(f'<text x="{x + w/2}" y="{ty + 24 + i*18}" text-anchor="middle" '
                         f'font-family="Helvetica, Arial" font-size="13" fill="#475569">'
                         f'{line}</text>')
    return "\n".join(parts)


def line(x1, y1, x2, y2, label="", dashed=False, color="#64748b", lx=None, ly=None):
    dash = ' stroke-dasharray="6 5"' if dashed else ""
    out = (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" '
           f'stroke-width="2" marker-end="url(#arrow)"{dash}/>')
    if label:
        out += (f'<text x="{lx if lx is not None else (x1+x2)/2}" '
                f'y="{ly if ly is not None else (y1+y2)/2 - 8}" text-anchor="middle" '
                f'font-family="Helvetica, Arial" font-size="13" fill="#475569">{label}</text>')
    return out


def polyline(points, label="", dashed=False):
    dash = ' stroke-dasharray="6 5"' if dashed else ""
    path = " ".join(f"{x},{y}" for x, y in points)
    out = (f'<polyline points="{path}" fill="none" stroke="#64748b" stroke-width="2" '
           f'marker-end="url(#arrow)"{dash}/>')
    if label:
        x, y = points[0]
        out += (f'<text x="{x}" y="{y - 10}" text-anchor="middle" '
                f'font-family="Helvetica, Arial" font-size="13" fill="#475569">{label}</text>')
    return out


def write_architecture() -> None:
    W, H = 1280, 640
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
           f'viewBox="0 0 {W} {H}">',
           '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" '
           'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
           '<path d="M 0 0 L 10 5 L 0 10 z" fill="#64748b"/></marker></defs>',
           '<rect width="100%" height="100%" fill="white"/>',
           '<text x="40" y="46" font-family="Helvetica, Arial" font-size="26" '
           'font-weight="700" fill="#0f172a">LexFlow: ask before you answer</text>',
           '<text x="40" y="72" font-family="Helvetica, Arial" font-size="14" '
           'fill="#64748b">Deterministic control flow + LLM extraction, with a versioned case record</text>']

    # row 1
    svg.append(svg_box(30, 120, 160, 84, "Client", "vague facts|corrections"))
    svg.append(svg_box(240, 120, 180, 84, "Intake", "LLM extraction|provenance"))
    svg.append('<polygon points="560,96 660,162 560,228 460,162" fill="#eef2ff" '
               'stroke="#818cf8" stroke-width="2"/>'
               '<text x="560" y="157" text-anchor="middle" font-family="Helvetica, Arial" '
               'font-size="16" font-weight="600" fill="#312e81">Sufficient?</text>'
               '<text x="560" y="177" text-anchor="middle" font-family="Helvetica, Arial" '
               'font-size="12" fill="#4338ca">critical elements</text>')
    svg.append(svg_box(740, 120, 200, 84, "Research", "versioned statutes|rules + arithmetic",
                       fill="#f0fdf4", stroke="#86efac"))
    svg.append(svg_box(990, 120, 200, 84, "Memo", "claims + citations|gaps + assumptions"))

    # row 2
    svg.append(svg_box(30, 320, 180, 90, "Case memory", "facts · status · revision|supersession chain",
                       fill="#f5f3ff", stroke="#c4b5fd"))
    svg.append(svg_box(460, 320, 180, 90, "Ask 1–2 questions", "ordered by legal leverage",
                       fill="#fef2f2", stroke="#fca5a5"))
    svg.append(svg_box(740, 320, 200, 90, "Statute corpus", "1,340 articles · 15 instruments|valid_from / valid_to",
                       fill="#eff6ff", stroke="#93c5fd"))
    svg.append(svg_box(990, 320, 200, 90, "Verifier", "existence · validity|quote · number · stale",
                       fill="#fff7ed", stroke="#fdba74"))

    # row 3
    svg.append(svg_box(990, 460, 200, 78, "Repair (bounded)", "swap version · drop quote|re-verify once",
                       fill="#fff7ed", stroke="#fdba74"))

    # main flow
    svg.append(line(190, 162, 240, 162))
    svg.append(line(420, 162, 460, 162))
    svg.append(line(660, 162, 740, 162, "yes", ly=152))
    svg.append(line(940, 162, 990, 162))

    # gate no -> ask
    svg.append(line(560, 228, 560, 320, "no", ly=280))

    # ask -> intake (right-then-up)
    svg.append(polyline([(460, 365), (400, 365), (400, 204)]))

    # memory -> intake
    svg.append(line(120, 320, 120, 204, "facts", lx=95, ly=270))

    # research <-> corpus (two vertical lines)
    svg.append(line(820, 204, 820, 320, "query", lx=800, ly=270))
    svg.append(line(880, 320, 880, 204, "evidence", lx=905, ly=270))

    # memo -> verifier
    svg.append(line(1090, 204, 1090, 320))

    # verifier -> repair / re-check
    svg.append(line(1060, 410, 1060, 460, "defects", lx=1032, ly=440))
    svg.append(line(1170, 460, 1170, 410, "re-check", lx=1198, ly=440))

    # pass -> release
    svg.append('<text x="1205" y="355" font-family="Helvetica, Arial" font-size="12" fill="#475569">pass →</text>')
    svg.append('<text x="1205" y="372" font-family="Helvetica, Arial" font-size="12" fill="#475569">memo</text>')

    # note
    svg.append('<text x="40" y="590" font-family="Helvetica, Arial" font-size="13" fill="#475569">'
               'fact change → revision++ → invalidate only dependent cache entries → '
               'recompute limitation / compensation / applicable version</text>')
    svg.append('</svg>')
    (FIG / "architecture.svg").write_text("\n".join(svg), encoding="utf-8")


if __name__ == "__main__":
    draw_chart()
    write_architecture()
    print("wrote", FIG / "results.png", "and", FIG / "architecture.svg")
