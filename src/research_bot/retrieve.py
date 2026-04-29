"""Hybrid retrieval over LanceDB. v1: dense-only with metadata post-filtering."""
from __future__ import annotations

from dataclasses import dataclass

from . import _models, config

TABLE = "chunks"


@dataclass
class Hit:
    paper_id: str
    chunk_id: str
    score: float
    text: str
    title: str
    authors: list[str]
    year: int
    venue: str
    topics: list[str]
    lab_paper: bool


def search(
    query: str,
    *,
    topics: list[str] | None = None,
    lab_only: bool = False,
    year_min: int | None = None,
    k: int = 8,
) -> list[Hit]:
    import lancedb

    db = lancedb.connect(str(config.LANCE_DIR))
    try:
        tbl = db.open_table(TABLE)
    except Exception as e:
        raise RuntimeError("no ingested chunks. run: research-bot ingest") from e

    qvec = _models.encode([query])[0]

    over = max(k * 4, 32)  # over-fetch then post-filter on list-type fields
    q = tbl.search(qvec).limit(over)

    where_parts = []
    if lab_only:
        where_parts.append("lab_paper = true")
    if year_min is not None:
        where_parts.append(f"year >= {year_min}")
    if where_parts:
        q = q.where(" AND ".join(where_parts))

    rows = q.to_list()

    if topics:
        wanted = set(topics)
        rows = [r for r in rows if wanted & set(r.get("topics") or [])]

    rows = rows[:k]

    out: list[Hit] = []
    for r in rows:
        # LanceDB returns _distance for L2 / vector_distance; cosine -> sim = 1 - dist
        dist = r.get("_distance", r.get("_relevance_score", 0.0))
        score = 1.0 - float(dist) if "_distance" in r else float(dist)
        out.append(Hit(
            paper_id=r["paper_id"],
            chunk_id=r["chunk_id"],
            score=score,
            text=r["text"],
            title=r.get("title", ""),
            authors=list(r.get("authors") or []),
            year=int(r.get("year", 0)),
            venue=r.get("venue", ""),
            topics=list(r.get("topics") or []),
            lab_paper=bool(r.get("lab_paper", False)),
        ))
    return out
