#!/usr/bin/env python3
"""Print report/slides.html to an 8-page 16:9 PDF."""
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "report" / "slides.html"
PDF = ROOT / "report" / "LexFlow_Slides.pdf"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-gpu"])
    page = browser.new_page(viewport={"width": 1280, "height": 720})
    page.goto(SRC.resolve().as_uri(), wait_until="networkidle")
    page.wait_for_timeout(600)
    page.pdf(path=str(PDF), width="13.333in", height="7.5in",
             print_background=True,
             margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
    browser.close()
print("wrote", PDF)
