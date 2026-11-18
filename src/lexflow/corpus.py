"""Version-aware statute corpus with a dependency-free BM25 retriever.

Every article carries the period during which its *version* was in force.
Retrieval can therefore be restricted to the law as it stood on the date that
matters for the case, which is what Chinese courts call 法律适用（时间效力）.
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .config import STATUTES

CJK = re.compile(r"[\u4e00-\u9fff]")
LATIN = re.compile(r"[a-zA-Z0-9]+")

# Query expansion for common colloquial legal vocabulary.  The mapping is
# deliberately small and inspectable; it is not a general synonym engine.
SYNONYMS = {
    "辞退": ["解除", "解除劳动合同"],
    "开除": ["解除", "解除劳动合同"],
    "炒": ["解除"],
    "双倍": ["二倍"],
    "两倍": ["二倍"],
    "2n": ["二倍", "赔偿金"],
    "赔偿": ["赔偿金", "经济补偿"],
    "补偿": ["经济补偿"],
    "公示": ["公示", "告知"],
    "告知": ["告知", "公示"],
    "社保": ["社会保险"],
    "欠薪": ["劳动报酬", "拖欠"],
    "加班费": ["延长工作时间", "加班"],
    "工伤": ["工伤保险", "工伤"],
    "时效": ["时效", "期间"],
    "过期": ["时效", "期间"],
    "多久": ["时效", "期间"],
    "交通事故": ["交通事故", "机动车"],
    "撞": ["交通事故", "机动车"],
    "残疾": ["残疾赔偿金", "伤残"],
    "死亡": ["死亡赔偿金"],
    "农村": ["农村居民", "城镇居民"],
    "城镇": ["城镇居民"],
}

STOPWORDS = set("的了和与或在是为对及等这那有被将把就都也还因此但而如果因为所以")


def tokenize(text: str) -> list[str]:
    """Character-bigram tokenizer for Chinese plus word tokens for Latin/digits.

    Bigrams work well for Chinese legal text without a segmentation model and
    keep the project dependency-free.  Single CJK characters are added only for
    very short queries so that one-character topics remain searchable.
    """
    text = (text or "").lower()
    tokens: list[str] = []
    for run in re.findall(r"[\u4e00-\u9fff]+", text):
        run = "".join(ch for ch in run if ch not in STOPWORDS)
        if len(run) == 1:
            tokens.append(run)
        else:
            tokens.extend(run[i:i + 2] for i in range(len(run) - 1))
    tokens.extend(LATIN.findall(text))
    return tokens


def expand_query(query: str) -> str:
    q = query.lower()
    extra: list[str] = []
    for key, values in SYNONYMS.items():
        if key in q:
            extra.extend(values)
    return query + (" " + " ".join(extra) if extra else "")


@dataclass
class Article:
    id: str
    law_id: str
    law: str
    law_short: str
    level: str
    article_no: str
    article_int: int
    text: str
    valid_from: str
    valid_to: str
    publish: str
    tags: list[str]
    note: str
    source: str
    official: str

    @property
    def citation(self) -> str:
        return f"《{self.law_short}》{self.article_no}"

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d["citation"] = self.citation
        return d


class StatuteCorpus:
    def __init__(self, path: Path = STATUTES):
        self.path = Path(path)
        self.articles: list[Article] = []
        self.by_id: dict[str, Article] = {}
        self._load()
        self._build_index()

    def _load(self) -> None:
        if not self.path.exists():
            raise FileNotFoundError(
                f"corpus not found: {self.path}. Run `python3 tools/build_corpus.py` first."
            )
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            art = Article(**json.loads(line))
            self.articles.append(art)
            self.by_id[art.id] = art

    def _build_index(self) -> None:
        self.docs: list[list[str]] = []
        self.df: Counter = Counter()
        for art in self.articles:
            toks = tokenize(art.law_short + " " + " ".join(art.tags) + " " + art.text)
            self.docs.append(toks)
            for t in set(toks):
                self.df[t] += 1
        self.n = len(self.docs)
        self.avgdl = sum(len(d) for d in self.docs) / max(self.n, 1)
        self.tf: list[Counter] = [Counter(d) for d in self.docs]
        self.idf = {
            t: math.log(1 + (self.n - df + 0.5) / (df + 0.5))
            for t, df in self.df.items()
        }

    # ------------------------------------------------------------------ lookup
    def get(self, article_id: str) -> Article | None:
        return self.by_id.get(article_id)

    def versions(self, law_id: str, article_no: str) -> list[Article]:
        found = [a for a in self.articles if a.law_id == law_id and a.article_no == article_no]
        return sorted(found, key=lambda a: a.valid_from)

    def find(self, law_id: str, article_no: str, as_of: str | None = None) -> Article | None:
        for art in self.versions(law_id, article_no):
            if as_of is None or self.is_valid(art, as_of):
                return art
        return None

    @staticmethod
    def is_valid(art: Article, as_of: str) -> bool:
        return art.valid_from <= as_of < art.valid_to

    def superseding(self, art: Article, as_of: str | None = None) -> Article | None:
        """Return a later version of the same article that is in force now/then."""
        later = [a for a in self.versions(art.law_id, art.article_no)
                 if a.valid_from > art.valid_from]
        if not later:
            return None
        if as_of is None:
            return later[-1]
        for a in later:
            if self.is_valid(a, as_of):
                return a
        return None

    # ------------------------------------------------------------------ search
    def search(
        self,
        query: str,
        as_of: str | None = None,
        law_ids: list[str] | None = None,
        k: int = 6,
        expand: bool = True,
    ) -> list[dict]:
        q = expand_query(query) if expand else query
        q_tokens = tokenize(q)
        if not q_tokens:
            return []
        q_set = set(q_tokens)
        k1, b = 1.5, 0.75
        scored: list[tuple[float, int]] = []
        for i, art in enumerate(self.articles):
            if law_ids and art.law_id not in law_ids:
                continue
            if as_of and not self.is_valid(art, as_of):
                continue
            tf = self.tf[i]
            dl = len(self.docs[i])
            score = 0.0
            matched = 0
            for t in q_set:
                f = tf.get(t, 0)
                if not f:
                    continue
                matched += 1
                idf = self.idf.get(t, 0.0)
                score += idf * (f * (k1 + 1)) / (f + k1 * (1 - b + b * dl / self.avgdl))
            if matched == 0:
                continue
            # Require a minimum share of query terms to avoid one-common-bigram hits.
            coverage = matched / len(q_set)
            if coverage < 0.2:
                continue
            score *= (0.5 + coverage)
            if query and query in art.text:
                score += 2.0
            scored.append((score, i))
        scored.sort(key=lambda x: (-x[0], self.articles[x[1]].article_int))
        return [self._hit(self.articles[i], s, as_of) for s, i in scored[:k]]

    def _hit(self, art: Article, score: float, as_of: str | None) -> dict:
        newer = self.superseding(art, as_of) if as_of else self.superseding(art)
        return {
            "id": art.id,
            "citation": art.citation,
            "law": art.law,
            "law_short": art.law_short,
            "article_no": art.article_no,
            "text": art.text,
            "valid_from": art.valid_from,
            "valid_to": art.valid_to,
            "score": round(score, 4),
            "version_status": self._version_status(art, as_of),
            "superseded_by": newer.citation if newer else None,
            "source": art.source,
        }

    def _version_status(self, art: Article, as_of: str | None) -> str:
        if as_of is None:
            return "in_force" if art.valid_to > "2099-01-01" else "historical"
        if self.is_valid(art, as_of):
            return "in_force_at_case_date"
        return "not_in_force_at_case_date"

    def citation_block(self, article_ids: list[str]) -> list[dict]:
        out = []
        for aid in dict.fromkeys(article_ids):
            art = self.get(aid)
            if art:
                out.append({
                    "id": art.id,
                    "citation": art.citation,
                    "valid_from": art.valid_from,
                    "valid_to": art.valid_to,
                    "text": art.text,
                    "source": art.source,
                })
        return out
