"""Načítání konfigurace z ../config a tajných údajů z proměnných prostředí."""
import os
from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


def load_settings() -> dict:
    with open(CONFIG_DIR / "settings.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_sources(only_enabled: bool = True) -> list[dict]:
    with open(CONFIG_DIR / "sources.yaml", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    sources = data.get("sources", [])
    if only_enabled:
        sources = [s for s in sources if s.get("enabled", True)]
    return sources


def load_prompt(name: str) -> str:
    path = CONFIG_DIR / "prompts" / f"{name}.md"
    return path.read_text(encoding="utf-8")


SECRET_NAMES = [
    "OPENAI_API_KEY",
    "SUPABASE_URL",
    "SUPABASE_KEY",
    "RESEND_API_KEY",
]


def secret(name: str, required: bool = True) -> str:
    value = os.environ.get(name, "").strip()
    if required and not value:
        raise RuntimeError(f"Chybí tajný údaj {name}. Doplňte ho v GitHub → Settings → Secrets and variables → Actions.")
    return value
