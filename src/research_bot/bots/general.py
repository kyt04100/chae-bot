from .._rag import rag_answer
from ..config import PROMPTS_DIR

PROMPT_FILE = PROMPTS_DIR / "general.md"


def system_prompt() -> str:
    return PROMPT_FILE.read_text(encoding="utf-8") if PROMPT_FILE.exists() else ""


def answer(question: str, *, model: str | None = None) -> str:
    # general bot: lab-first but not lab-only — fall through to all sources
    return rag_answer(
        question=question,
        persona=system_prompt(),
        k=8,
        model=model,
    )
