from .._rag import rag_answer
from ..config import PROMPTS_DIR

PROMPT_FILE = PROMPTS_DIR / "trihybrid.md"
DEFAULT_TOPICS = ["tri-hybrid", "hybrid-beamforming", "rf-lens", "mmwave", "near-field", "xl-mimo"]


def system_prompt() -> str:
    return PROMPT_FILE.read_text(encoding="utf-8") if PROMPT_FILE.exists() else ""


def answer(question: str, *, model: str | None = None) -> str:
    return rag_answer(
        question=question,
        persona=system_prompt(),
        topics=DEFAULT_TOPICS,
        k=8,
        model=model,
    )
