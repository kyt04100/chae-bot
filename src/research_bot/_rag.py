"""Shared RAG loop: retrieve -> compose context -> Claude call.

`build_prompt` is the LLM-agnostic assembly step (used by the CLI `prompt` command
so Claude Code itself can be the LLM via slash commands, no API key required).
`rag_answer` adds an Anthropic API call on top.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import config, llm, retrieve

CITATION_HINT = (
    "When you cite, use the bracket form like [paper-id] matching the IDs shown above. "
    "If retrieval returned nothing relevant, say so plainly — do not invent citations."
)


@dataclass
class BuiltPrompt:
    persona: str           # bot persona + citation rule (cacheable)
    context: str           # retrieved chunks block (varies per query)
    user_msg: str          # final user message (question + optional draft)
    hits: list[retrieve.Hit]


def _format_context(hits: list[retrieve.Hit]) -> str:
    if not hits:
        return "(no chunks retrieved)"
    parts = []
    for h in hits:
        authors = ", ".join(h.authors) if h.authors else ""
        head = f"[{h.paper_id}] {h.title} — {authors} ({h.year}, {h.venue})"
        parts.append(f"{head}\n{h.text}")
    return "\n\n---\n\n".join(parts)


def build_prompt(
    *,
    question: str,
    persona: str,
    topics: list[str] | None = None,
    lab_only: bool = False,
    year_min: int | None = None,
    k: int = 8,
    extra_user_context: str = "",
) -> BuiltPrompt:
    hits = retrieve.search(
        question, topics=topics, lab_only=lab_only, year_min=year_min, k=k
    )
    context = _format_context(hits)
    user_msg = question if not extra_user_context else f"{extra_user_context}\n\n---\n\n{question}"
    return BuiltPrompt(
        persona=f"{persona}\n\n{CITATION_HINT}",
        context=f"=== RETRIEVED CONTEXT ===\n{context}\n=== END CONTEXT ===",
        user_msg=user_msg,
        hits=hits,
    )


def rag_answer(
    *,
    question: str,
    persona: str,
    topics: list[str] | None = None,
    lab_only: bool = False,
    year_min: int | None = None,
    k: int = 8,
    model: str | None = None,
    extra_user_context: str = "",
) -> str:
    try:
        bp = build_prompt(
            question=question,
            persona=persona,
            topics=topics,
            lab_only=lab_only,
            year_min=year_min,
            k=k,
            extra_user_context=extra_user_context,
        )
    except RuntimeError as e:
        return f"[error] {e}"

    # System split into 2 blocks:
    #   1. persona + citation rules (static per bot)  → cached
    #   2. retrieved context (varies per query)       → not cached
    system_blocks = [
        {"type": "text", "text": bp.persona, "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": bp.context},
    ]

    return llm.ask(
        system=system_blocks,
        messages=[{"role": "user", "content": bp.user_msg}],
        model=model or config.DEFAULT_MODEL,
        max_tokens=2048,
    )
