#!/usr/bin/env python3
"""Render the report markdown to a print-ready PDF with Chromium."""
from __future__ import annotations

import json
from pathlib import Path

import markdown
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "report"
SRC = REPORT / "LexFlow_Report.md"
HTML = REPORT / "_report.html"
PDF = REPORT / "LexFlow_Report.pdf"

CSS = """
@page { size: A4; margin: 18mm 16mm 18mm 16mm; }
body { font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
       font-size: 10.5pt; line-height: 1.55; color: #1f2937; }
h1 { font-size: 22pt; margin: 0 0 4pt 0; color: #0f172a; }
h2 { font-size: 14pt; margin: 18pt 0 6pt; color: #0f172a;
     border-bottom: 1px solid #e2e8f0; padding-bottom: 3pt; }
h3 { font-size: 11.5pt; margin: 12pt 0 4pt; color: #1e293b; }
p { margin: 4pt 0; text-align: justify; }
ul, ol { margin: 4pt 0 4pt 16pt; }
li { margin: 2pt 0; }
table { border-collapse: collapse; width: 100%; margin: 8pt 0; font-size: 9pt; }
th { background: #f1f5f9; border: 1px solid #cbd5e1; padding: 4pt 5pt;
     text-align: left; }
td { border: 1px solid #cbd5e1; padding: 4pt 5pt; }
tr:nth-child(even) td { background: #f8fafc; }
img { max-width: 100%; display: block; margin: 10pt auto; }
code { background: #f1f5f9; padding: 1pt 3pt; border-radius: 3pt;
       font-family: Menlo, Consolas, monospace; font-size: 9pt; }
pre { background: #f8fafc; border: 1px solid #e2e8f0; padding: 8pt;
      border-radius: 4pt; overflow: auto; font-size: 8.5pt; }
blockquote { border-left: 3px solid #cbd5e1; margin: 8pt 0; padding: 2pt 10pt;
             color: #475569; }
hr { border: none; border-top: 1px solid #e2e8f0; margin: 14pt 0; }
a { color: #1d4ed8; text-decoration: none; }
"""


def main() -> None:
    text = SRC.read_text(encoding="utf-8")
    body = markdown.markdown(text, extensions=["tables", "fenced_code", "sane_lists"])
    html = f"""<!doctype html><html><head><meta charset="utf-8">
    <style>{CSS}</style></head><body>{body}</body></html>"""
    HTML.write_text(html, encoding="utf-8")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-gpu"])
        page = browser.new_page(viewport={"width": 1000, "height": 1400})
        page.goto(HTML.as_uri(), wait_until="networkidle")
        page.wait_for_timeout(800)
        page.pdf(path=str(PDF), format="A4", print_background=True,
                 display_header_footer=True,
                 header_template="<div></div>",
                 footer_template=(
                     '<div style="width:100%;font-size:8px;color:#94a3b8;'
                     'text-align:center;font-family:Arial;">'
                     '<span class="pageNumber"></span> / <span class="totalPages"></span>'
                     "</div>"),
                 margin={"top": "18mm", "bottom": "18mm", "left": "16mm", "right": "16mm"})
        browser.close()
    print("wrote", PDF, PDF.stat().st_size, "bytes")
    print(json.dumps({"pages_html_bytes": len(html)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
