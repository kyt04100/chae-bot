"""Build the static GitHub Pages bundle in `docs/`.

Reads seed_papers.yaml + prompts/ and writes JSON files the static UI loads.
Optionally enriches each paper with the arXiv abstract (no API key needed).

Run from project root:
    .venv/Scripts/python -m research_bot.scripts.build_pages
or:
    .venv/Scripts/python -m research_bot.scripts.build_pages --no-abstracts
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import yaml
from rich.console import Console

from .. import config, external

console = Console()
DOCS_DIR = config.ROOT / "docs"
LAB_CONTEXT = (
    "Active context: This bot answers on behalf of a graduate student in "
    "Prof. Chan-Byoung Chae's Intelligence Networking Lab at Yonsei University "
    "(cbchae.yonsei.ac.kr). The lab works on 6G/B6G AI-RAN, MIMO design and prototyping, "
    "full-duplex, fluid antenna systems (FAS), RIS, mmWave/sub-THz, semantic "
    "communications, ISAC, and molecular communications. Treat the user as a "
    "domain expert (6G prototyping focus) when calibrating depth."
)


def _build_personas() -> dict:
    prompts_dir = config.PROMPTS_DIR
    personas = {}
    for name in ("general", "fas", "trihybrid"):
        f = prompts_dir / f"{name}.md"
        body = f.read_text(encoding="utf-8") if f.exists() else ""
        personas[name] = {
            "name": name,
            "persona": body.strip(),
            "lab_context": LAB_CONTEXT,
        }
    return personas


def _build_papers(fetch_abstracts: bool) -> list[dict]:
    seed = yaml.safe_load(config.SEED_PAPERS_YAML.read_text(encoding="utf-8"))
    out = []
    n = len(seed["papers"])
    for i, p in enumerate(seed["papers"], 1):
        rec = {
            "id": p["id"],
            "title": p["title"],
            "authors": p.get("authors") or [],
            "year": p.get("year") or 0,
            "venue": p.get("venue") or "",
            "topics": p.get("topics") or [],
            "lab_paper": bool(p.get("lab_paper", False)),
            "abstract": "",
            "arxiv_url": "",
        }
        if fetch_abstracts:
            console.print(f"  [{i}/{n}] arXiv lookup: {p['title'][:60]}...")
            try:
                hits = external.arxiv_search(p["title"], max_results=2)
                # pick the best match by token overlap
                target_tokens = set(w.lower() for w in p["title"].split() if len(w) > 3)
                best, best_score = None, 0
                for h in hits:
                    t = set(w.lower() for w in h.title.split() if len(w) > 3)
                    score = len(target_tokens & t)
                    if score > best_score:
                        best, best_score = h, score
                if best and best_score >= 2:
                    rec["abstract"] = best.abstract[:1000]
                    rec["arxiv_url"] = best.url
            except Exception as e:
                console.print(f"    [yellow]arxiv error:[/yellow] {e}")
            time.sleep(0.4)  # be polite to arXiv
        out.append(rec)
    return out


def _write_index_meta(papers: list[dict]) -> dict:
    return {
        "n_papers": len(papers),
        "n_with_abstracts": sum(1 for p in papers if p["abstract"]),
        "n_lab_papers": sum(1 for p in papers if p["lab_paper"]),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-abstracts", action="store_true",
                    help="skip arXiv lookups (faster, less rich Lite UX)")
    args = ap.parse_args()

    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    console.print("[bold]building docs/personas.json[/bold]")
    personas = _build_personas()
    (DOCS_DIR / "personas.json").write_text(
        json.dumps(personas, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    console.print(f"  → {len(personas)} personas")

    console.print("[bold]building docs/papers.json[/bold]")
    papers = _build_papers(fetch_abstracts=not args.no_abstracts)
    (DOCS_DIR / "papers.json").write_text(
        json.dumps(papers, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    meta = _write_index_meta(papers)
    console.print(f"  → {meta}")

    (DOCS_DIR / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    console.print("[green]done.[/green]  Commit docs/ and push.")


if __name__ == "__main__":
    main()
