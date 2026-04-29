from pathlib import Path
import os
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

CORPUS_DIR = ROOT / "corpus"
DATA_DIR = ROOT / "data"
PROMPTS_DIR = ROOT / "prompts"
DRAFTS_DIR = ROOT / "drafts"

SEED_PAPERS_YAML = DATA_DIR / "seed_papers.yaml"
LANCE_DIR = DATA_DIR / "papers.lance"
META_DB = DATA_DIR / "papers.db"
GROBID_DIR = DATA_DIR / "grobid_xml"
MANUAL_DOWNLOADS_FILE = ROOT / "downloads_manual.txt"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
SEMANTIC_SCHOLAR_API_KEY = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
VOYAGE_API_KEY = os.getenv("VOYAGE_API_KEY")

DEFAULT_MODEL = "claude-sonnet-4-6"
DEEP_MODEL = "claude-opus-4-7"

for d in (CORPUS_DIR, DATA_DIR, DRAFTS_DIR, PROMPTS_DIR):
    d.mkdir(parents=True, exist_ok=True)
