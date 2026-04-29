from pathlib import Path

from .._rag import rag_answer
from ..config import PROMPTS_DIR

PROMPT_FILE = PROMPTS_DIR / "fas.md"
DEFAULT_TOPICS = ["fas", "ris", "multiple-access", "ai-comm"]


def system_prompt() -> str:
    return PROMPT_FILE.read_text(encoding="utf-8") if PROMPT_FILE.exists() else ""


def answer(question: str, *, draft_path: str | None = None, model: str | None = None) -> str:
    extra = ""
    if draft_path:
        p = Path(draft_path)
        if p.exists():
            extra = f"=== USER DRAFT ({p.name}) ===\n{p.read_text(encoding='utf-8')}\n=== END DRAFT ==="
    return rag_answer(
        question=question,
        persona=system_prompt(),
        topics=DEFAULT_TOPICS,
        k=8,
        extra_user_context=extra,
        model=model,
    )
