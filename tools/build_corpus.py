#!/usr/bin/env python3
"""Build the local statute corpus (article-level, version-aware).

Source: LawRefBook/Laws (https://github.com/LawRefBook/Laws), a public
markdown collection of Chinese statutes.  The official text is published on
flk.npc.gov.cn; this script keeps the source path and dates so every article
can be traced back.

Output:
    lexflow/data/corpus/statutes.jsonl   one record per (law version, article)
    lexflow/data/corpus/corpus_version.json

Usage:
    python3 tools/build_corpus.py [--offline]

The generated files are committed so the demo runs with no network access.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "corpus" / "manifest.json"
SOURCES = ROOT / "data" / "sources"
OUT = ROOT / "data" / "corpus" / "statutes.jsonl"
VERSION_FILE = ROOT / "data" / "corpus" / "corpus_version.json"

RAW_BASE = "https://raw.githubusercontent.com/LawRefBook/Laws/master/"

CN_DIGITS = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
             "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
CN_UNITS = {"十": 10, "百": 100, "千": 1000}
ARTICLE_RE = re.compile(r"^第([零〇一二两三四五六七八九十百千]+)条(之[一二三四五六七八九十]+)?\s*(.*)$")
CHAPTER_RE = re.compile(r"^#{1,4}\s")


def cn_to_int(text: str) -> int:
    """Convert a Chinese numeral (<= 9999) to int. Raises ValueError otherwise."""
    total, section, num = 0, 0, 0
    for ch in text:
        if ch in CN_DIGITS:
            num = CN_DIGITS[ch]
        elif ch in CN_UNITS:
            unit = CN_UNITS[ch]
            if num == 0:
                num = 1
            section += num * unit
            num = 0
        else:
            raise ValueError(f"not a Chinese numeral: {text!r}")
    return section + num


def download(law: dict, offline: bool) -> Path:
    SOURCES.mkdir(parents=True, exist_ok=True)
    dest = SOURCES / f"{law['law_id']}.md"
    if dest.exists() and dest.stat().st_size > 200:
        return dest
    if offline:
        raise SystemExit(f"missing cached source for {law['law_id']}: {dest}")
    url = RAW_BASE + urllib.parse.quote(law["path"])
    req = urllib.request.Request(url, headers={"User-Agent": "lexflow-course-project/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()
    dest.write_bytes(data)
    print(f"downloaded {law['law_id']} <- {law['path']} ({len(data)} bytes)")
    return dest


def clean(text: str) -> str:
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = re.sub(r"[ \t\u3000]+", " ", text)
    text = text.replace("**", "").replace("__", "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def parse_articles(raw: str) -> list[dict]:
    lines = clean(raw).splitlines()
    articles: list[dict] = []
    current = None
    buffer: list[str] = []

    def flush():
        if current is None:
            return
        body = "\n".join(buffer).strip()
        if body:
            articles.append({**current, "text": body})

    for line in lines:
        stripped = line.strip()
        m = ARTICLE_RE.match(stripped)
        if m:
            flush()
            number = cn_to_int(m.group(1))
            suffix = m.group(2) or ""
            first = m.group(3).strip()
            current = {"article_no": f"第{number}条{suffix}", "article_int": number}
            buffer = [first] if first else []
            continue
        if CHAPTER_RE.match(stripped):
            # A new chapter ends the previous article but is not article text.
            flush()
            current, buffer = None, []
            continue
        if current is not None:
            buffer.append(stripped)
    flush()
    return articles


def article_id(law_id: str, valid_from: str, article_no: str) -> str:
    num = re.search(r"第(\d+)条(之[一二三四五六七八九十]+)?", article_no)
    token = num.group(0) if num else article_no
    return f"{law_id}@{valid_from}:{token}"


def build(offline: bool) -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    records: list[dict] = []
    for law in manifest["laws"]:
        src = download(law, offline)
        articles = parse_articles(src.read_text(encoding="utf-8"))
        if not articles:
            raise SystemExit(f"no articles parsed for {law['law_id']}")
        numeric = [a["article_int"] for a in articles]
        for art in articles:
            records.append({
                "id": article_id(law["law_id"], law["valid_from"], art["article_no"]),
                "law_id": law["law_id"],
                "law": law["title"],
                "law_short": law["short"],
                "level": law["level"],
                "article_no": art["article_no"],
                "article_int": art["article_int"],
                "text": art["text"],
                "valid_from": law["valid_from"],
                "valid_to": law["valid_to"],
                "publish": law["publish"],
                "tags": law["tags"],
                "note": law.get("note", ""),
                "source": f"{manifest['source_repo']}/blob/master/{law['path']}",
                "official": "https://flk.npc.gov.cn/",
            })
        print(f"  {law['law_id']}: {len(articles)} articles "
              f"(第{min(numeric)}条 – 第{max(numeric)}条)")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    digest = hashlib.sha256(OUT.read_bytes()).hexdigest()[:16]
    VERSION_FILE.write_text(json.dumps({
        "corpus_version": digest,
        "n_articles": len(records),
        "n_laws": len(manifest["laws"]),
        "source_repo": manifest["source_repo"],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nwrote {len(records)} articles -> {OUT.relative_to(ROOT)}")
    print(f"corpus_version = {digest}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="use cached sources only")
    args = ap.parse_args()
    build(args.offline)
