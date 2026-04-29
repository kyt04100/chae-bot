# chae-bot

Local research assistants for Prof. Chan-Byoung Chae's Intelligence Networking Lab at Yonsei. Three personas (`general`, `fas`, `trihybrid`) over a local paper index, with optional external search (arXiv + Semantic Scholar).

Designed to work without an Anthropic API key — the web UI assembles a self-contained prompt that you paste into Claude Code or claude.ai. If you do set `ANTHROPIC_API_KEY`, the `ask` CLI command will call the API directly.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate         # Windows
pip install -e .[ingest,web]
cp .env.example .env           # optional: ANTHROPIC_API_KEY, SEMANTIC_SCHOLAR_API_KEY
```

## Build the index

```bash
python -m research_bot.scripts.download_papers   # auto-fetch open-access seed PDFs
research-bot ingest                              # PDFs → chunks → vector index
research-bot status                              # sanity check
```

Paywalled papers are listed in `downloads_manual.txt`; drop them into `corpus/` as `<id>.pdf` and re-run `ingest`.

## Three ways to ask

### 1. Web UI (recommended, no API key needed)

```bash
research-bot serve              # http://127.0.0.1:8000
```

Open in Chrome → pick a bot → type question → "build prompt" → "copy prompt" → paste into Claude Code or claude.ai. The prompt includes local retrieval + external (arXiv/S2) results.

### 2. Claude Code slash commands

Inside `claude` (in this repo):

```
/general 최근 lab의 ISAC 관련 논문 어떤 게 있어?
/fas FAS Part I/II/III의 기여를 한 문단씩 비교해줘
/trihybrid RF lens vs phase shifter trade-off 정리
```

Claude Code runs the local pipeline and answers using your Max plan.

### 3. Direct API call (needs ANTHROPIC_API_KEY)

```bash
research-bot ask fas "FAS oversampling이 왜 필수적인지 설명"
research-bot ask general --deep "lab의 6G 방향성"      # uses opus-4-7
research-bot ask fas --draft drafts/myfile.tex "이 문장 출처 검증"
```

## Raw retrieval (no LLM)

```bash
research-bot query "fluid antenna outage probability" -k 5 --topic fas
research-bot prompt fas "FAS oversampling" > /tmp/p.txt    # assembled prompt only
```

## Layout

```
src/research_bot/
  cli.py               ask | prompt | query | ingest | serve | status
  _rag.py              build_prompt + rag_answer
  retrieve.py          dense vector search (LanceDB) + filters
  external.py          arXiv + Semantic Scholar search
  ingest.py            PDF → chunks → embeddings
  chunking.py          sliding-window chunker
  llm.py               Anthropic client w/ prompt caching
  bots/{general,fas,trihybrid}.py
  webui/               FastAPI server + static SPA
  scripts/download_papers.py
prompts/               bot personas (markdown)
data/seed_papers.yaml  30 seed paper metadata
.claude/commands/      Claude Code slash commands
```
