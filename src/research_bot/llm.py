"""Thin wrapper around the Anthropic SDK with prompt caching support."""
from __future__ import annotations

from anthropic import Anthropic
from rich.console import Console

from .config import ANTHROPIC_API_KEY, DEFAULT_MODEL

_client: Anthropic | None = None
_console = Console(stderr=True)


def client() -> Anthropic:
    global _client
    if _client is None:
        if not ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY missing — fill in .env")
        _client = Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


def ask(
    *,
    system: list[dict] | str,
    messages: list[dict],
    model: str = DEFAULT_MODEL,
    max_tokens: int = 2048,
    show_usage: bool = True,
) -> str:
    """Single non-streaming call. `system` may be a string or a list of blocks
    (use blocks with cache_control to enable prompt caching)."""
    resp = client().messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=messages,
    )
    if show_usage and getattr(resp, "usage", None):
        u = resp.usage
        _console.print(
            f"[dim]usage: in={u.input_tokens} out={u.output_tokens} "
            f"cache_read={getattr(u, 'cache_read_input_tokens', 0)} "
            f"cache_write={getattr(u, 'cache_creation_input_tokens', 0)} "
            f"model={model}[/dim]"
        )
    return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
