"""Resolve and download seed papers.

Strategy per paper:
  1. Search Semantic Scholar by title -> grab DOI, externalIds.ArXiv, openAccessPdf.url
  2. If openAccessPdf -> download
  3. Else if arXiv id -> download arXiv PDF
  4. Else -> append to downloads_manual.txt with DOI link for institutional access

No LLM calls. No Google Scholar (Scholar blocks bots). Free APIs only.
"""
from __future__ import annotations

import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import click
import requests
import yaml
from rich.console import Console
from rich.table import Table
from tenacity import retry, stop_after_attempt, wait_exponential

from .. import config

console = Console()

S2_BASE = "https://api.semanticscholar.org/graph/v1"
ARXIV_BASE = "http://export.arxiv.org/api/query"
UNPAYWALL_BASE = "https://api.unpaywall.org/v2"
UNPAYWALL_EMAIL = "research-bot@cbchae.yonsei.ac.kr"
USER_AGENT = "research_bot/0.1 (yonsei intelligence networking lab)"
S2_FIELDS = "title,year,authors,externalIds,openAccessPdf,venue"
S2_PACE_SECONDS = 2.5  # be polite without an API key


@dataclass
class Resolution:
    paper_id: str
    title: str
    year: int
    pdf_url: str | None
    pdf_source: str  # "s2-oa" | "arxiv" | "manual"
    doi: str | None
    arxiv_id: str | None
    note: str = ""


def _safe_filename(s: str) -> str:
    return re.sub(r"[^\w\-]+", "_", s)[:80].strip("_")


def _headers() -> dict:
    h = {"User-Agent": USER_AGENT}
    if config.SEMANTIC_SCHOLAR_API_KEY:
        h["x-api-key"] = config.SEMANTIC_SCHOLAR_API_KEY
    return h


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
def _s2_search(title: str) -> dict | None:
    r = requests.get(
        f"{S2_BASE}/paper/search",
        params={"query": title, "limit": 5, "fields": S2_FIELDS},
        headers=_headers(),
        timeout=20,
    )
    if r.status_code == 429:
        time.sleep(3)
        r.raise_for_status()
    r.raise_for_status()
    data = r.json().get("data", [])
    if not data:
        return None
    # heuristic: pick best title-overlap match
    target = re.sub(r"\W+", " ", title).lower().strip()
    def score(p: dict) -> int:
        t = re.sub(r"\W+", " ", p.get("title") or "").lower()
        return sum(1 for w in target.split() if w in t)
    return max(data, key=score)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
def _arxiv_search(title: str, first_author: str | None = None) -> str | None:
    """Try exact title first, fall back to keyword + author."""
    queries = [f"ti:\"{title}\""]
    # loose: pull 4-5 distinctive title words + first author surname
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z\-]{3,}", title)
             if w.lower() not in {"the", "and", "with", "from", "that", "this", "into",
                                   "using", "based", "via", "for", "system", "systems"}]
    if words:
        loose = " AND ".join(f"all:{w}" for w in words[:5])
        if first_author:
            loose += f" AND au:{first_author}"
        queries.append(loose)

    for q in queries:
        r = requests.get(
            ARXIV_BASE,
            params={"search_query": q, "max_results": 3},
            headers={"User-Agent": USER_AGENT},
            timeout=20,
        )
        r.raise_for_status()
        # parse all <entry>, pick best title match
        entries = re.findall(
            r"<entry>.*?<id>http://arxiv\.org/abs/([^<]+)</id>.*?<title>([^<]+)</title>.*?</entry>",
            r.text,
            flags=re.DOTALL,
        )
        if not entries:
            continue
        target = re.sub(r"\W+", " ", title).lower().strip()
        def score(t: str) -> int:
            t = re.sub(r"\W+", " ", t).lower()
            return sum(1 for w in target.split() if len(w) > 3 and w in t)
        best = max(entries, key=lambda e: score(e[1]))
        if score(best[1]) >= 3:
            return best[0]
    return None


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
def _unpaywall_by_doi(doi: str) -> str | None:
    r = requests.get(
        f"{UNPAYWALL_BASE}/{doi}",
        params={"email": UNPAYWALL_EMAIL},
        headers={"User-Agent": USER_AGENT},
        timeout=20,
    )
    if r.status_code == 404:
        return None
    r.raise_for_status()
    data = r.json()
    loc = data.get("best_oa_location") or {}
    return loc.get("url_for_pdf") or loc.get("url")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
def _unpaywall_search(title: str) -> tuple[str | None, str | None]:
    """Returns (pdf_url, doi)."""
    r = requests.get(
        f"{UNPAYWALL_BASE}/search",
        params={"query": title, "is_oa": "true", "email": UNPAYWALL_EMAIL},
        headers={"User-Agent": USER_AGENT},
        timeout=20,
    )
    r.raise_for_status()
    results = (r.json() or {}).get("results") or []
    if not results:
        return None, None
    target = re.sub(r"\W+", " ", title).lower().strip()
    def score(item: dict) -> int:
        t = re.sub(r"\W+", " ", (item.get("response") or {}).get("title") or "").lower()
        return sum(1 for w in target.split() if len(w) > 3 and w in t)
    best = max(results, key=score)
    if score(best) < 3:
        return None, None
    resp = best.get("response") or {}
    loc = resp.get("best_oa_location") or {}
    return loc.get("url_for_pdf") or loc.get("url"), resp.get("doi")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
def _download(url: str, dest: Path) -> bool:
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=60, allow_redirects=True)
    if r.status_code != 200:
        return False
    if "application/pdf" not in r.headers.get("Content-Type", "") and not r.content.startswith(b"%PDF"):
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(r.content)
    return True


def resolve(paper: dict) -> Resolution:
    pid = paper["id"]
    title = paper["title"]
    year = paper.get("year", 0)
    authors = paper.get("authors") or []
    first_author = None
    if authors:
        # extract surname from "K.-K. Wong" -> "Wong"
        first_author = re.split(r"\s+", authors[0].strip())[-1]

    s2 = None
    try:
        s2 = _s2_search(title)
    except Exception as e:
        console.print(f"  [yellow]s2 lookup failed:[/yellow] {e}")

    doi = None
    arxiv_id = None
    note = ""

    if s2:
        ext = s2.get("externalIds") or {}
        doi = ext.get("DOI")
        arxiv_id = ext.get("ArXiv")
        oa = s2.get("openAccessPdf") or {}
        if oa.get("url"):
            return Resolution(pid, title, year, oa["url"], "s2-oa", doi, arxiv_id)

    # Unpaywall by DOI (S2 found DOI but no OA, often Unpaywall has it)
    if doi:
        try:
            up_url = _unpaywall_by_doi(doi)
            if up_url:
                return Resolution(pid, title, year, up_url, "unpaywall-doi", doi, arxiv_id)
        except Exception as e:
            console.print(f"  [yellow]unpaywall(doi) failed:[/yellow] {e}")

    # Unpaywall by title search (when S2 returned nothing at all)
    if not doi:
        try:
            up_url, up_doi = _unpaywall_search(title)
            if up_url:
                return Resolution(pid, title, year, up_url, "unpaywall-search", up_doi or doi, arxiv_id)
            if up_doi:
                doi = up_doi  # at least we got a DOI for the manual link
        except Exception as e:
            console.print(f"  [yellow]unpaywall(search) failed:[/yellow] {e}")

    # arXiv (loose) fallback
    if not arxiv_id:
        try:
            arxiv_id = _arxiv_search(title, first_author=first_author)
        except Exception as e:
            console.print(f"  [yellow]arxiv lookup failed:[/yellow] {e}")
            note = f"arxiv lookup error: {e}"

    if arxiv_id:
        return Resolution(
            pid, title, year, f"https://arxiv.org/pdf/{arxiv_id}.pdf", "arxiv", doi, arxiv_id, note
        )

    return Resolution(pid, title, year, None, "manual", doi, arxiv_id, note or "no open-access source")


@click.command()
@click.option("--limit", type=int, default=None, help="process only first N papers (for testing)")
@click.option("--skip-existing/--no-skip-existing", default=True)
def main(limit: int | None, skip_existing: bool) -> None:
    seed = yaml.safe_load(config.SEED_PAPERS_YAML.read_text(encoding="utf-8"))
    papers = seed["papers"]
    if limit:
        papers = papers[:limit]

    config.CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    manual_lines: list[str] = []
    table = Table(title=f"Resolving {len(papers)} papers", show_lines=False)
    table.add_column("id", style="cyan")
    table.add_column("source")
    table.add_column("status")

    auto = manual = skipped = 0

    for p in papers:
        pid = p["id"]
        dest = config.CORPUS_DIR / f"{pid}.pdf"
        if skip_existing and dest.exists():
            table.add_row(pid, "-", "[blue]skip (exists)[/blue]")
            skipped += 1
            continue

        time.sleep(S2_PACE_SECONDS)  # be polite to S2 (no API key)
        res = resolve(p)
        if res.pdf_url:
            ok = False
            try:
                ok = _download(res.pdf_url, dest)
            except Exception as e:
                res.note = f"{res.note}; download error: {e}".strip("; ")
            if ok:
                table.add_row(pid, res.pdf_source, "[green]downloaded[/green]")
                auto += 1
                continue

        # manual fallback
        link = (
            f"https://doi.org/{res.doi}" if res.doi
            else f"https://arxiv.org/abs/{res.arxiv_id}" if res.arxiv_id
            else f"(search: {res.title})"
        )
        manual_lines.append(f"{pid}\t{p.get('venue', '')} {res.year}\t{link}\t{p['title']}")
        table.add_row(pid, "manual", f"[red]manual[/red] {res.note}")
        manual = manual + 1

    console.print(table)
    console.print(f"\n[bold]auto[/bold] {auto}   [bold]manual[/bold] {manual}   [bold]skipped[/bold] {skipped}")

    if manual_lines:
        config.MANUAL_DOWNLOADS_FILE.write_text(
            "id\tvenue\tlink\ttitle\n" + "\n".join(manual_lines), encoding="utf-8"
        )
        console.print(f"\nManual list -> [cyan]{config.MANUAL_DOWNLOADS_FILE}[/cyan]")
        console.print("Open each link via your Yonsei IEEE Xplore proxy / SSO and drop the PDFs into corpus/ as <id>.pdf")


if __name__ == "__main__":
    main()
