"""External paper search (arXiv + Semantic Scholar). No API key required.

S2 uses SEMANTIC_SCHOLAR_API_KEY if set in .env (higher rate limit), otherwise unauthenticated.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import requests

from .config import SEMANTIC_SCHOLAR_API_KEY

ARXIV_BASE = "http://export.arxiv.org/api/query"
S2_BASE = "https://api.semanticscholar.org/graph/v1"
USER_AGENT = "research_bot/0.1 (yonsei intelligence networking lab)"
TIMEOUT = 15


@dataclass
class ExternalHit:
    source: str           # "arxiv" | "s2"
    title: str
    authors: list[str]
    year: int
    abstract: str
    url: str
    venue: str = ""

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "title": self.title,
            "authors": self.authors,
            "year": self.year,
            "abstract": self.abstract,
            "url": self.url,
            "venue": self.venue,
        }


def arxiv_search(query: str, max_results: int = 3) -> list[ExternalHit]:
    try:
        r = requests.get(
            ARXIV_BASE,
            params={"search_query": f"all:{query}", "max_results": max_results,
                    "sortBy": "relevance", "sortOrder": "descending"},
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
    except Exception:
        return []

    out: list[ExternalHit] = []
    for entry in re.findall(r"<entry>(.*?)</entry>", r.text, flags=re.DOTALL):
        title_m = re.search(r"<title>(.*?)</title>", entry, flags=re.DOTALL)
        summary_m = re.search(r"<summary>(.*?)</summary>", entry, flags=re.DOTALL)
        link_m = re.search(r"<id>http://arxiv\.org/abs/([^<]+)</id>", entry)
        year_m = re.search(r"<published>(\d{4})", entry)
        authors = re.findall(r"<name>(.*?)</name>", entry)
        if not (title_m and summary_m):
            continue
        out.append(ExternalHit(
            source="arxiv",
            title=re.sub(r"\s+", " ", title_m.group(1)).strip(),
            authors=[a.strip() for a in authors[:5]],
            year=int(year_m.group(1)) if year_m else 0,
            abstract=re.sub(r"\s+", " ", summary_m.group(1)).strip()[:1200],
            url=f"https://arxiv.org/abs/{link_m.group(1)}" if link_m else "",
        ))
    return out


def s2_search(query: str, max_results: int = 3) -> list[ExternalHit]:
    headers = {"User-Agent": USER_AGENT}
    if SEMANTIC_SCHOLAR_API_KEY:
        headers["x-api-key"] = SEMANTIC_SCHOLAR_API_KEY
    try:
        r = requests.get(
            f"{S2_BASE}/paper/search",
            params={
                "query": query,
                "limit": max_results,
                "fields": "title,authors,year,abstract,externalIds,venue,paperId",
            },
            headers=headers,
            timeout=TIMEOUT,
        )
        if not r.ok:
            return []
        data = r.json().get("data") or []
    except Exception:
        return []

    out: list[ExternalHit] = []
    for p in data:
        pid = p.get("paperId") or ""
        out.append(ExternalHit(
            source="s2",
            title=(p.get("title") or "").strip(),
            authors=[a.get("name", "") for a in (p.get("authors") or [])][:5],
            year=int(p.get("year") or 0),
            abstract=(p.get("abstract") or "")[:1200],
            url=f"https://www.semanticscholar.org/paper/{pid}" if pid else "",
            venue=p.get("venue") or "",
        ))
    return out


def search_external(query: str, max_per_source: int = 3) -> list[ExternalHit]:
    """Combined arXiv + Semantic Scholar search. Failures in one source don't break the other."""
    return arxiv_search(query, max_per_source) + s2_search(query, max_per_source)


def format_external_context(hits: list[ExternalHit]) -> str:
    if not hits:
        return ""
    parts = []
    for h in hits:
        head = f"[{h.source}] {h.title}"
        meta_bits = []
        if h.authors:
            meta_bits.append(", ".join(h.authors))
        if h.year:
            meta_bits.append(str(h.year))
        if h.venue:
            meta_bits.append(h.venue)
        if h.url:
            meta_bits.append(h.url)
        if meta_bits:
            head += " — " + " / ".join(meta_bits)
        body = h.abstract or "(no abstract)"
        parts.append(f"{head}\n{body}")
    return "=== EXTERNAL CONTEXT (arxiv + S2) ===\n" + "\n\n---\n\n".join(parts) + "\n=== END EXTERNAL ==="
