#!/usr/bin/env python3
"""Render the external-evaluation appendix to PDF.

The appendix is authored as HTML with the same CSS as the main report, printed
with a Chromium-based browser, then given continuous page numbers (the main
report has 7 pages, so the appendix starts at 8/10).

Usage:
    python report/make_external_pdf.py

Requires a Chromium-based browser. Page-number overlay uses PyMuPDF when it is
available; otherwise the PDF is still produced, just without footer numbers.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "report"
HTML = REPORT / "External_Eval_Report.html"
PDF = REPORT / "External_Eval_Report.pdf"
RAW = REPORT / "_external_raw.pdf"

BROWSERS = [
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    Path("/usr/bin/microsoft-edge"),
    Path("/usr/bin/google-chrome"),
    Path("/usr/bin/chromium"),
    Path("/usr/bin/chromium-browser"),
    Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
]


def find_browser() -> str:
    for candidate in BROWSERS:
        if candidate.is_file():
            return str(candidate)
    for name in ("msedge", "chrome", "chromium", "google-chrome"):
        found = shutil.which(name)
        if found:
            return found
    raise SystemExit("no Chromium-based browser found; set one in BROWSERS")


def render(raw: Path, profile: Path) -> None:
    browser = find_browser()
    profile.mkdir(parents=True, exist_ok=True)
    url = HTML.as_uri()
    subprocess.run(
        [
            browser,
            "--headless=new",
            "--no-sandbox",
            "--disable-gpu",
            "--disable-crash-reporter",
            "--no-pdf-header-footer",
            f"--user-data-dir={profile}",
            f"--print-to-pdf={raw}",
            url,
        ],
        check=True,
    )


def add_page_numbers(raw: Path, out: Path) -> None:
    try:
        import pymupdf
    except ImportError:
        sys.path.insert(0, str(ROOT.parent / "_deps"))
        try:
            import pymupdf  # type: ignore
        except ImportError:
            shutil.copyfile(raw, out)
            print("PyMuPDF not available; wrote PDF without footer page numbers")
            return

    main = REPORT / "LexFlow_Report.pdf"
    offset = 7
    if main.is_file():
        with pymupdf.open(main) as original:
            offset = original.page_count

    font_path = Path(r"C:\Windows\Fonts\arial.ttf")
    font = pymupdf.Font(fontfile=str(font_path)) if font_path.is_file() else pymupdf.Font("helv")
    grey = (80 / 255, 88 / 255, 100 / 255)

    doc = pymupdf.open(raw)
    total = offset + doc.page_count
    for index, page in enumerate(doc):
        text = f"{offset + index + 1} / {total}"
        width = font.text_length(text, fontsize=6.0)
        x = (page.rect.width - width) / 2
        if font_path.is_file():
            page.insert_font(fontname="arial", fontfile=str(font_path))
            page.insert_text((x, 826.5), text, fontname="arial", fontsize=6.0, color=grey)
        else:
            page.insert_text((x, 826.5), text, fontname="helv", fontsize=6.0, color=grey)

    # Rebuild the document instead of saving the Chromium output in place.
    # This drops tagged-PDF / structure-tree leftovers that some browser PDF
    # viewers reject, and produces a plain PDF 1.7 file.
    clean = pymupdf.open()
    clean.insert_pdf(doc)
    clean.set_metadata({
        "title": "LexFlow — Appendix A: External Benchmark (DLawBench, Adapted Run)",
        "author": "",
        "subject": "Adapted external evaluation of LexFlow on DLawBench",
        "keywords": "LexFlow, DLawBench, legal consultation, evaluation",
        "creator": "Chromium",
        "producer": "MuPDF",
    })
    clean.save(out, garbage=4, clean=True, deflate=True)
    print(f"wrote {out} ({out.stat().st_size} bytes, {clean.page_count} pages)")


def main() -> None:
    if not HTML.is_file():
        raise SystemExit(f"missing source: {HTML}")
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "external_raw.pdf"
        render(raw, Path(tmp) / "profile")
        add_page_numbers(raw, PDF)


if __name__ == "__main__":
    main()
