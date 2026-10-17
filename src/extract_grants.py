"""Vytažení konkrétních výzev z textu stránky (levný model) a uložení do databáze."""
import hashlib
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from config_loader import load_prompt
from openai_client import chat_json

log = logging.getLogger("extract")

TRACKING = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "fbclid", "gclid"}


def normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    query = urlencode([(k, v) for k, v in parse_qsl(parts.query) if k.lower() not in TRACKING])
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, query, ""))


def make_call_key(g: dict, source_url: str) -> str:
    """Klíč výzvy pro odstranění duplicit: normalizovaná adresa výzvy, nebo (pokud míří jen na seznam) hash z názvu."""
    url = (g.get("call_url") or "").strip()
    if url.startswith("http") and normalize_url(url) != normalize_url(source_url):
        return normalize_url(url)
    basis = "|".join(str(g.get(k) or "").lower().strip() for k in ("title", "funder", "deadline"))
    return "h:" + hashlib.sha1(basis.encode("utf-8")).hexdigest()


def _date(v):
    if not v:
        return None
    try:
        return date.fromisoformat(str(v)[:10]).isoformat()
    except ValueError:
        return None


def _num(v):
    try:
        return float(v) if v is not None and v != "" else None
    except (TypeError, ValueError):
        return None


def to_row(g: dict, source: dict) -> dict | None:
    title = (g.get("title") or "").strip()
    if not title:
        return None
    extra = {k: g.get(k) for k in ("applicant_types", "cofinancing_pct", "cofinancing_note", "funding_mode", "requires_foreign_partner")}
    return {
        "call_key": make_call_key(g, source["url"]),
        "title": title[:300],
        "funder": (g.get("funder") or source.get("name") or "")[:200],
        "call_url": (g.get("call_url") or source["url"]),
        "deadline": _date(g.get("deadline")),
        "opens_on": _date(g.get("opens_on")),
        "amount_min": _num(g.get("amount_min")),
        "amount_max": _num(g.get("amount_max")),
        "currency": g.get("currency"),
        "eligible_applicants": g.get("eligible_applicants"),
        "topics": g.get("topics") if isinstance(g.get("topics"), list) else None,
        "region": g.get("region"),
        "status": g.get("status") or "unknown",
        "category": source.get("category"),
        "source_ids": [source["id"]],
        "source_urls": [source["url"]],
        "summary": g.get("summary"),
        "extra": extra,
    }


def extract_one(item: dict, settings: dict, today: date) -> list[dict]:
    src = item["source"]
    m, c = settings["models"], settings["collect"]
    system = load_prompt("extract").replace("{today}", today.isoformat()).replace("{max_items}", str(c["max_grants_per_page"]))
    user = f"Zdroj: {src['name']}\nAdresa stránky: {src['url']}\n\n--- TEXT STRÁNKY (nedůvěryhodný) ---\n{item['text']}"
    data = chat_json(m["cheap"], system, user, m["max_tokens_cheap"], effort=m.get("effort_cheap"))
    rows = [r for g in (data.get("grants") or []) if isinstance(g, dict) and (r := to_row(g, src))]
    uniq = {r["call_key"]: r for r in rows}
    return list(uniq.values())


def extract_all(items: list[dict], settings: dict, storage, today: date) -> dict:
    """Zpracuje nové stránky. Otisk stránky se uloží jen po úspěšné extrakci, ať se neúspěšná zkusí příště znovu."""
    stats = {"pages": len(items), "pages_failed": 0, "grants_found": 0, "grants_new": 0}

    def work(it):
        try:
            return it, extract_one(it, settings, today), None
        except Exception as e:  # jedna rozbitá stránka nesmí shodit běh
            return it, [], f"{type(e).__name__}: {str(e)[:150]}"

    with ThreadPoolExecutor(max_workers=settings["collect"]["workers_llm"]) as ex:
        results = list(ex.map(work, items))

    all_rows: dict[str, dict] = {}
    seen_rows = []
    for it, rows, err in results:
        src = it["source"]
        if err:
            stats["pages_failed"] += 1
            log.warning("Extrakce %s selhala: %s", src["id"], err)
            continue
        stats["grants_found"] += len(rows)
        for r in rows:
            if r["call_key"] in all_rows:  # stejná výzva z více zdrojů: sloučit zdroje
                prev = all_rows[r["call_key"]]
                prev["source_ids"] = sorted(set(prev["source_ids"] + r["source_ids"]))
                prev["source_urls"] = sorted(set(prev["source_urls"] + r["source_urls"]))
            else:
                all_rows[r["call_key"]] = r
        seen_rows.append({"fingerprint": it["fingerprint"], "source_id": src["id"], "source_name": src["name"],
                          "kind": "web", "url": src["url"], "title": None, "content": None, "processed": True})

    stats["grants_new"] = storage.insert_ignore("grants", list(all_rows.values()), conflict="call_key")
    storage.insert_ignore("raw_items", seen_rows, conflict="fingerprint")
    log.warning("Extrakce: %s", json.dumps(stats, ensure_ascii=False))
    return stats
