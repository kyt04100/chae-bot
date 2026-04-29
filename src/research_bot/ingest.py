"""PDF -> chunks -> embeddings -> LanceDB.

One row per chunk with paper metadata duplicated for filterable retrieval.
"""
from __future__ import annotations

from pathlib import Path

import yaml
from rich.console import Console

from . import _models, config
from .chunking import chunk_text

TABLE = "chunks"
console = Console()


def _load_seed_meta() -> dict[str, dict]:
    seed = yaml.safe_load(config.SEED_PAPERS_YAML.read_text(encoding="utf-8"))
    return {p["id"]: p for p in seed["papers"]}


def _extract_pdf(path: Path) -> str:
    from pdfminer.high_level import extract_text
    return extract_text(str(path))


def _connect():
    import lancedb
    return lancedb.connect(str(config.LANCE_DIR))


def _existing_paper_ids(db) -> set[str]:
    try:
        tbl = db.open_table(TABLE)
    except Exception:
        return set()
    arrow = tbl.to_arrow()
    if "paper_id" not in arrow.schema.names:
        return set()
    return set(arrow.column("paper_id").to_pylist())


def ingest_corpus(force: bool = False) -> dict:
    meta_by_id = _load_seed_meta()
    pdfs = sorted(config.CORPUS_DIR.glob("*.pdf"))
    if not pdfs:
        console.print("[yellow]no PDFs in corpus/ — run download_papers first[/yellow]")
        return {"ingested": 0, "skipped": 0, "chunks": 0}

    db = _connect()
    if force:
        try:
            db.drop_table(TABLE)
        except Exception:
            pass

    existing = _existing_paper_ids(db)

    rows: list[dict] = []
    ingested = skipped = 0

    for pdf in pdfs:
        pid = pdf.stem
        if pid in existing:
            console.print(f"[blue]skip[/blue] {pid} (already ingested)")
            skipped += 1
            continue

        meta = meta_by_id.get(pid)
        if not meta:
            console.print(f"[yellow]warn[/yellow] {pid}.pdf has no metadata in seed_papers.yaml — using filename only")
            meta = {"title": pid, "year": 0, "topics": [], "lab_paper": False, "authors": []}

        try:
            raw = _extract_pdf(pdf)
        except Exception as e:
            console.print(f"[red]extract failed[/red] {pid}: {e}")
            continue

        chunks = chunk_text(raw)
        if not chunks:
            console.print(f"[yellow]empty extraction[/yellow] {pid}")
            continue

        vectors = _models.encode(chunks)
        for i, (text, vec) in enumerate(zip(chunks, vectors)):
            rows.append({
                "paper_id": pid,
                "chunk_id": f"{pid}#{i:04d}",
                "chunk_idx": i,
                "text": text,
                "title": meta.get("title", ""),
                "authors": meta.get("authors", []) or [],
                "year": int(meta.get("year", 0) or 0),
                "venue": meta.get("venue", "") or "",
                "topics": meta.get("topics", []) or [],
                "lab_paper": bool(meta.get("lab_paper", False)),
                "vector": vec,
            })
        ingested += 1
        console.print(f"[green]ok[/green]   {pid}  ({len(chunks)} chunks)")

    if not rows:
        return {"ingested": ingested, "skipped": skipped, "chunks": 0}

    try:
        tbl = db.open_table(TABLE)
        tbl.add(rows)
    except Exception:
        db.create_table(TABLE, data=rows)

    return {"ingested": ingested, "skipped": skipped, "chunks": len(rows)}
