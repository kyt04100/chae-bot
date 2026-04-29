import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import click
from rich.console import Console
from rich.table import Table

from .bots import BOTS

console = Console()


@click.group(invoke_without_command=True)
@click.pass_context
def main(ctx: click.Context) -> None:
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@main.command()
@click.argument("bot_name", type=click.Choice(list(BOTS.keys())))
@click.argument("question", nargs=-1, required=True)
@click.option("--deep", is_flag=True, help="use opus-4-7 instead of sonnet-4-6 (slower, deeper)")
@click.option("--draft", "draft_path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="path to draft file (fas bot only)")
def ask(bot_name: str, question: tuple[str, ...], deep: bool, draft_path: str | None) -> None:
    """research-bot ask <general|fas|trihybrid> "your question" [--deep] [--draft PATH]"""
    from . import config

    if draft_path and bot_name != "fas":
        console.print("[red]--draft is only supported for the fas bot[/red]")
        sys.exit(2)

    q = " ".join(question)
    model = config.DEEP_MODEL if deep else config.DEFAULT_MODEL
    fn = BOTS[bot_name]
    kwargs = {"model": model}
    if bot_name == "fas":
        kwargs["draft_path"] = draft_path

    try:
        out = fn(q, **kwargs)
    except NotImplementedError as e:
        console.print(f"[yellow]{bot_name} bot not implemented yet:[/yellow] {e}")
        sys.exit(1)
    except RuntimeError as e:
        console.print(f"[red]{e}[/red]")
        sys.exit(1)
    console.print(out)


@main.command(name="prompt")
@click.argument("bot_name", type=click.Choice(list(BOTS.keys())))
@click.argument("question", nargs=-1, required=True)
@click.option("--draft", "draft_path", type=click.Path(exists=True, dir_okay=False),
              default=None, help="path to draft file (fas bot only)")
@click.option("-k", default=8, help="number of chunks to retrieve")
@click.option("--no-memory", "no_memory", is_flag=True,
              help="skip injecting Claude Code auto-memory (use inside slash commands "
                   "where Claude already has memory loaded)")
def prompt_cmd(bot_name: str, question: tuple[str, ...], draft_path: str | None,
               k: int, no_memory: bool) -> None:
    """Print self-contained prompt (memory + persona + retrieved context + question) to stdout.

    Used by Claude Code slash commands so Claude Max users can answer with no API call.
    """
    from pathlib import Path
    from . import _rag
    from .bots import fas as fas_mod, general as general_mod, trihybrid as trihybrid_mod

    if draft_path and bot_name != "fas":
        console.print("[red]--draft is only supported for the fas bot[/red]")
        sys.exit(2)

    q = " ".join(question)

    persona_map = {
        "general": (general_mod.system_prompt(), None, False),
        "fas":     (fas_mod.system_prompt(),     fas_mod.DEFAULT_TOPICS, False),
        "trihybrid": (trihybrid_mod.system_prompt(), trihybrid_mod.DEFAULT_TOPICS, False),
    }
    persona, topics, lab_only = persona_map[bot_name]

    extra = ""
    if draft_path:
        p = Path(draft_path)
        extra = f"=== USER DRAFT ({p.name}) ===\n{p.read_text(encoding='utf-8')}\n=== END DRAFT ==="

    try:
        bp = _rag.build_prompt(
            question=q,
            persona=persona,
            topics=topics,
            lab_only=lab_only,
            k=k,
            extra_user_context=extra,
            include_memory=not no_memory,
        )
    except RuntimeError as e:
        console.print(f"[red]{e}[/red]")
        sys.exit(1)

    # Plain stdout (no rich markup) so slash commands feed it cleanly to the LLM.
    if bp.memory_block:
        print(bp.memory_block)
        print()
    print(bp.persona)
    print()
    print(bp.context)
    print()
    print("=== USER QUESTION ===")
    print(bp.user_msg)


@main.command()
@click.option("--force", is_flag=True, help="drop existing chunks and re-ingest all")
def ingest(force: bool) -> None:
    """Run PDF -> chunks -> embeddings pipeline over corpus/."""
    from . import ingest as ingest_mod
    stats = ingest_mod.ingest_corpus(force=force)
    console.print(f"[bold]ingested[/bold] {stats['ingested']}  "
                  f"[bold]skipped[/bold] {stats['skipped']}  "
                  f"[bold]new chunks[/bold] {stats['chunks']}")


@main.command()
@click.argument("query", nargs=-1, required=True)
@click.option("-k", default=5, help="number of hits")
@click.option("--topic", multiple=True, help="filter by topic tag (repeatable)")
@click.option("--lab-only", is_flag=True)
@click.option("--year-min", type=int, default=None)
def query(query: tuple[str, ...], k: int, topic: tuple[str, ...], lab_only: bool, year_min: int | None) -> None:
    """Raw retrieval, no LLM. For sanity-checking the index."""
    from . import retrieve
    q = " ".join(query)
    try:
        hits = retrieve.search(
            q, topics=list(topic) or None, lab_only=lab_only, year_min=year_min, k=k
        )
    except RuntimeError as e:
        console.print(f"[red]{e}[/red]")
        sys.exit(1)
    if not hits:
        console.print("[yellow]no hits[/yellow]")
        return
    t = Table(title=f"top {len(hits)} for: {q}", show_lines=True)
    t.add_column("score", style="cyan", width=6)
    t.add_column("paper", style="magenta")
    t.add_column("snippet")
    for h in hits:
        snippet = h.text.replace("\n", " ")[:240] + ("…" if len(h.text) > 240 else "")
        t.add_row(f"{h.score:.3f}", f"{h.paper_id}\n[dim]{h.year}[/dim]", snippet)
    console.print(t)


@main.command()
@click.option("--host", default="127.0.0.1", help="bind address (default loopback only)")
@click.option("--port", default=8000, type=int)
@click.option("--reload", is_flag=True, help="auto-reload on code changes (dev)")
def serve(host: str, port: int, reload: bool) -> None:
    """Launch the local web UI at http://HOST:PORT."""
    try:
        import uvicorn
    except ImportError:
        console.print("[red]uvicorn not installed.[/red] Run: [bold]pip install -e .[web][/bold]")
        sys.exit(1)
    console.print(f"[green]chae-bot[/green] → http://{host}:{port}")
    uvicorn.run("research_bot.webui.server:app", host=host, port=port, reload=reload)


@main.command()
def status() -> None:
    """Show what's wired up so far."""
    from . import config

    rows = [
        ("corpus dir", config.CORPUS_DIR, config.CORPUS_DIR.exists()),
        ("seed papers yaml", config.SEED_PAPERS_YAML, config.SEED_PAPERS_YAML.exists()),
        ("vector db", config.LANCE_DIR, config.LANCE_DIR.exists()),
        ("ANTHROPIC_API_KEY", "set" if config.ANTHROPIC_API_KEY else "missing", bool(config.ANTHROPIC_API_KEY)),
    ]
    for label, val, ok in rows:
        mark = "[green]OK[/green]" if ok else "[red]--[/red]"
        console.print(f"{mark}  {label}: {val}")

    pdf_count = len(list(config.CORPUS_DIR.glob("*.pdf")))
    console.print(f"      PDFs in corpus: {pdf_count}")

    try:
        import lancedb
        db = lancedb.connect(str(config.LANCE_DIR))
        try:
            tbl = db.open_table("chunks")
        except Exception:
            tbl = None
        if tbl is not None:
            n_chunks = tbl.count_rows()
            arrow = tbl.to_arrow()
            ids = arrow.column("paper_id").to_pylist() if "paper_id" in arrow.schema.names else []
            n_papers = len(set(ids))
            console.print(f"      indexed chunks: {n_chunks}  ({n_papers} papers)")
    except Exception as e:
        console.print(f"      [yellow]index check failed:[/yellow] {e}")


if __name__ == "__main__":
    main()
