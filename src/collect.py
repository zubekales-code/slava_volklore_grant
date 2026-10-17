"""Sběr: stáhne zdroje, vyčistí text a pozná, které stránky jsou nové nebo změněné."""
import hashlib
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin

import html2text
from bs4 import BeautifulSoup

from http_fetch import fetch

log = logging.getLogger("collect")


def clean_text(raw: str, via: str, base_url: str, max_chars: int) -> str:
    """HTML na čitelný text s odkazy (markdown). Čtečka r.jina.ai už markdown vrací."""
    if via == "reader":
        text = raw
    else:
        soup = BeautifulSoup(raw, "html.parser")
        for tag in soup(["script", "style", "noscript", "svg", "iframe", "form", "nav", "footer"]):
            tag.decompose()
        for a in soup.find_all("a", href=True):
            a["href"] = urljoin(base_url, a["href"])
        conv = html2text.HTML2Text()
        conv.ignore_images = True
        conv.ignore_emphasis = True
        conv.body_width = 0
        text = conv.handle(str(soup))
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text[:max_chars]


def fingerprint(source_id: str, text: str) -> str:
    norm = re.sub(r"\s+", " ", text).strip().lower()
    return hashlib.sha1(f"{source_id}|{norm}".encode("utf-8")).hexdigest()


def _one(source: dict, settings: dict) -> dict:
    c = settings["collect"]
    r = fetch(source["url"], timeout=c["request_timeout"], reader_fallback=c["use_reader_fallback"],
              verify_ssl=source.get("verify_ssl", True))
    item = {"source": source, "ok": r["ok"], "via": r["via"], "status": r["status"], "error": r["error"], "text": "", "fingerprint": None}
    if r["ok"]:
        item["text"] = clean_text(r["text"], r["via"], source["url"], c["max_chars_per_source"])
        if len(item["text"]) < 200:
            item["ok"] = False
            item["error"] = "prázdný text"
        else:
            item["fingerprint"] = fingerprint(source["id"], item["text"])
    return item


def collect_all(settings: dict, sources: list[dict]) -> list[dict]:
    """Stáhne všechny zdroje paralelně. Vrací seznam položek (i neúspěšných)."""
    with ThreadPoolExecutor(max_workers=settings["collect"]["workers_fetch"]) as ex:
        items = list(ex.map(lambda s: _one(s, settings), sources))
    ok = sum(1 for i in items if i["ok"])
    log.warning("Staženo %d z %d zdrojů", ok, len(items))
    return items


def mark_new(items: list[dict], storage) -> list[dict]:
    """Ponechá jen stránky, které jsme ještě neviděli (podle otisku obsahu)."""
    fps = [i["fingerprint"] for i in items if i["ok"]]
    seen: set[str] = set()
    for k in range(0, len(fps), 40):
        chunk = fps[k : k + 40]
        rows = storage.select("raw_items", {"select": "fingerprint", "fingerprint": f"in.({','.join(chunk)})"})
        seen.update(r["fingerprint"] for r in rows)
    return [i for i in items if i["ok"] and i["fingerprint"] not in seen]
