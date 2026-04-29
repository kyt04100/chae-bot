"""Load Claude Code auto-memory files for the current project so they can be
injected into prompts going to claude.ai (web UI manual-paste path).

Slash commands inside Claude Code already auto-load memory, so they should pass
`include_memory=False` to avoid duplication.
"""
from __future__ import annotations

import re
from pathlib import Path

from .config import ROOT


def _encode_project_path(p: Path) -> str:
    """Convert an absolute path to Claude Code's project memory dir naming.
    e.g. C:\\Users\\Yoontae\\Desktop\\research_bot -> C--Users-Yoontae-Desktop-research-bot
    """
    s = str(p.resolve())
    for ch in (":", "\\", "/", "_"):
        s = s.replace(ch, "-")
    return s


def find_memory_dir() -> Path | None:
    """Return the auto-memory directory for this project, or None if missing."""
    base = Path.home() / ".claude" / "projects"
    if not base.exists():
        return None
    candidate = base / _encode_project_path(ROOT) / "memory"
    return candidate if candidate.exists() else None


_FRONTMATTER_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", flags=re.DOTALL)


def _strip_frontmatter(md: str) -> str:
    return _FRONTMATTER_RE.sub("", md, count=1).lstrip()


def load_memory_context() -> str:
    """Read all memory files (excluding MEMORY.md index) and return a single
    formatted block ready to prepend to a prompt. Empty string if no memory."""
    mdir = find_memory_dir()
    if not mdir:
        return ""

    parts: list[str] = []
    for f in sorted(mdir.glob("*.md")):
        if f.name == "MEMORY.md":
            continue
        try:
            content = f.read_text(encoding="utf-8")
        except Exception:
            continue
        body = _strip_frontmatter(content).strip()
        if not body:
            continue
        title = f.stem.replace("_", " ")
        parts.append(f"## {title}\n\n{body}")

    if not parts:
        return ""

    header = (
        "=== USER / LAB / PROJECT MEMORY (loaded from local Claude Code auto-memory) ===\n"
        "Use this as background context about who is asking and the lab they belong to. "
        "Do not echo it back unless the user asks.\n"
    )
    return header + "\n" + "\n\n---\n\n".join(parts) + "\n=== END MEMORY ==="
