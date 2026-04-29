"""FastAPI server exposing the research_bot pipeline as a local web UI.

Run via: research-bot serve
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .. import _rag, config, external
from ..bots import fas as fas_mod, general as general_mod, trihybrid as trihybrid_mod

app = FastAPI(title="chae-bot", description="Local research assistant for the Yonsei Intelligence Networking Lab")

STATIC_DIR = Path(__file__).parent / "static"

PERSONA_MAP = {
    "general": (general_mod.system_prompt, lambda: None),
    "fas": (fas_mod.system_prompt, lambda: fas_mod.DEFAULT_TOPICS),
    "trihybrid": (trihybrid_mod.system_prompt, lambda: trihybrid_mod.DEFAULT_TOPICS),
}


class BuildRequest(BaseModel):
    bot: str = Field(..., description="general | fas | trihybrid")
    question: str
    include_external: bool = True
    k: int = 8


class LocalHit(BaseModel):
    paper_id: str
    title: str
    year: int
    score: float
    snippet: str


class ExternalHitOut(BaseModel):
    source: str
    title: str
    authors: list[str]
    year: int
    venue: str
    url: str
    abstract: str


class BuildResponse(BaseModel):
    persona: str
    local_context: str
    external_context: str
    user_msg: str
    full_prompt: str
    local_hits: list[LocalHit]
    external_hits: list[ExternalHitOut]


@app.post("/api/build", response_model=BuildResponse)
def build(req: BuildRequest) -> BuildResponse:
    if req.bot not in PERSONA_MAP:
        raise HTTPException(400, f"unknown bot: {req.bot}")
    if not req.question.strip():
        raise HTTPException(400, "question is empty")

    persona_fn, topics_fn = PERSONA_MAP[req.bot]
    persona = persona_fn()
    topics = topics_fn()

    try:
        bp = _rag.build_prompt(
            question=req.question,
            persona=persona,
            topics=topics,
            k=req.k,
        )
    except RuntimeError as e:
        raise HTTPException(500, str(e))

    ext_hits = external.search_external(req.question) if req.include_external else []
    ext_context = external.format_external_context(ext_hits) if ext_hits else ""

    full_parts = [bp.persona, bp.context]
    if ext_context:
        full_parts.append(ext_context)
    full_parts.append(f"=== USER QUESTION ===\n{bp.user_msg}")
    full_prompt = "\n\n".join(full_parts)

    return BuildResponse(
        persona=bp.persona,
        local_context=bp.context,
        external_context=ext_context,
        user_msg=bp.user_msg,
        full_prompt=full_prompt,
        local_hits=[
            LocalHit(
                paper_id=h.paper_id,
                title=h.title,
                year=h.year,
                score=h.score,
                snippet=h.text[:240],
            )
            for h in bp.hits
        ],
        external_hits=[ExternalHitOut(**h.to_dict()) for h in ext_hits],
    )


@app.get("/api/status")
def status() -> dict:
    pdf_count = len(list(config.CORPUS_DIR.glob("*.pdf")))
    chunk_count = 0
    paper_count = 0
    try:
        import lancedb
        db = lancedb.connect(str(config.LANCE_DIR))
        tbl = db.open_table("chunks")
        chunk_count = tbl.count_rows()
        arrow = tbl.to_arrow()
        paper_count = len(set(arrow.column("paper_id").to_pylist()))
    except Exception:
        pass
    return {
        "pdfs": pdf_count,
        "chunks": chunk_count,
        "papers": paper_count,
        "api_key_set": bool(config.ANTHROPIC_API_KEY),
        "s2_key_set": bool(config.SEMANTIC_SCHOLAR_API_KEY),
    }


@app.get("/")
def root():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
