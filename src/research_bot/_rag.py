"""Shared RAG loop: retrieve -> compose context -> Claude call.

`build_prompt` is the LLM-agnostic assembly step (used by the CLI `prompt` command
so Claude Code itself can be the LLM via slash commands, no API key required).
`rag_answer` adds an Anthropic API call on top.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import config, llm, memory, retrieve

CITATION_HINT = (
    "When you cite, use the bracket form like [paper-id] matching the IDs shown above. "
    "If retrieval returned nothing relevant, say so plainly — do not invent citations."
)


@dataclass
class BuiltPrompt:
    memory_block: str      # user/lab/project context (may be empty)
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
    include_memory: bool = True,
) -> BuiltPrompt:
    hits = retrieve.search(
        question, topics=topics, lab_only=lab_only, year_min=year_min, k=k
    )
    context = _format_context(hits)
    user_msg = question if not extra_user_context else f"{extra_user_context}\n\n---\n\n{question}"
    memory_block = memory.load_memory_context() if include_memory else ""
    return BuiltPrompt(
        memory_block=memory_block,
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
    include_memory: bool = False,
) -> str:
    """API path: include_memory defaults to False because the API doesn't need
    the local-paste enrichment, and memory in the system prompt would burn cache
    on personal data that rarely affects the answer. Override if needed."""
    try:
        bp = build_prompt(
            question=question,
            persona=persona,
            topics=topics,
            lab_only=lab_only,
            year_min=year_min,
            k=k,
            extra_user_context=extra_user_context,
            include_memory=include_memory,
        )
    except RuntimeError as e:
        return f"[error] {e}"

    # System split into blocks:
    #   1. (optional) memory — rarely-changing user/lab context, cacheable
    #   2. persona + citation rules (static per bot) — cached
    #   3. retrieved context (varies per query) — not cached
    system_blocks: list[dict] = []
    if bp.memory_block:
        system_blocks.append({"type": "text", "text": bp.memory_block, "cache_control": {"type": "ephemeral"}})
    system_blocks.append({"type": "text", "text": bp.persona, "cache_control": {"type": "ephemeral"}})
    system_blocks.append({"type": "text", "text": bp.context})

    return llm.ask(
        system=system_blocks,
        messages=[{"role": "user", "content": bp.user_msg}],
        model=model or config.DEFAULT_MODEL,
        max_tokens=2048,
    )
