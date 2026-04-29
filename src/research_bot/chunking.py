"""Section-aware chunker.

v1: simple character-based sliding window. Strips noisy artifacts (page headers,
line numbers, repeated whitespace). Section detection added in v2 if needed.
"""
from __future__ import annotations

import re

CHUNK_CHARS = 3000   # ~750 tokens
OVERLAP = 400        # ~100 tokens overlap

_RE_FORMFEED = re.compile(r"\f+")
_RE_HYPHEN_LINEBREAK = re.compile(r"-\n([a-z])")
_RE_MULTI_NEWLINE = re.compile(r"\n{3,}")
_RE_INLINE_PAGENUM = re.compile(r"\n\s*\d{1,3}\s*\n")


def clean_text(raw: str) -> str:
    s = raw
    s = _RE_HYPHEN_LINEBREAK.sub(r"\1", s)         # join hyphenated line breaks
    s = _RE_INLINE_PAGENUM.sub("\n", s)            # drop bare page numbers
    s = _RE_FORMFEED.sub("\n\n", s)
    s = _RE_MULTI_NEWLINE.sub("\n\n", s)
    return s.strip()


def chunk_text(text: str, chunk_chars: int = CHUNK_CHARS, overlap: int = OVERLAP) -> list[str]:
    text = clean_text(text)
    if len(text) <= chunk_chars:
        return [text] if text else []
    step = chunk_chars - overlap
    out: list[str] = []
    i = 0
    while i < len(text):
        chunk = text[i : i + chunk_chars]
        if chunk.strip():
            out.append(chunk)
        i += step
    return out
