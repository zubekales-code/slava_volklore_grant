"""Výběr výzev do e-mailu a napsání souhrnu (silný model)."""
import json
import logging
from datetime import date

import markdown

from config_loader import CONFIG_DIR, load_prompt
from openai_client import chat

log = logging.getLogger("write")

BUCKET_ORDER = {"fit": 0, "adapt": 1, "later": 2}


def days_left(g: dict, today: date):
    d = g.get("deadline")
    return (date.fromisoformat(d) - today).days if d else None


def select_for_email(settings: dict, storage, today: date) -> list[dict]:
    sel = settings["selection"]
    rows = storage.select("grants", {
        "select": "*", "sent_at": "is.null", "bucket": "in.(fit,adapt,later)",
        "score": f"gte.{sel['min_score']}", "order": "score.desc", "limit": "400",
    })
    urgent = sel["deadline_urgent_days"]
    picked, per_source, later = [], {}, 0
    ranked = []
    for g in rows:
        dl = days_left(g, today)
        if dl is not None and dl < 0:
            continue
        if g["bucket"] == "later" and g["score"] < sel["min_score_later"]:
            continue
        g["days_left"] = dl
        ranked.append(g)
    ranked.sort(key=lambda g: (
        0 if g["days_left"] is not None and g["days_left"] <= urgent else 1,
        BUCKET_ORDER[g["bucket"]], -g["score"], g["days_left"] if g["days_left"] is not None else 9999))
    for g in ranked:
        if len(picked) >= sel["max_items_total"]:
            break
        src = (g.get("source_ids") or ["?"])[0]
        if per_source.get(src, 0) >= sel["max_per_source"]:
            continue
        if g["bucket"] == "later":
            if later >= sel["max_later"]:
                continue
            later += 1
        per_source[src] = per_source.get(src, 0) + 1
        picked.append(g)
    return picked


def _payload(g: dict) -> dict:
    extra = g.get("extra") or {}
    return {
        "title": g.get("title"), "funder": g.get("funder"), "call_url": g.get("call_url"),
        "deadline": g.get("deadline"), "days_left": g.get("days_left"),
        "amount_min": g.get("amount_min"), "amount_max": g.get("amount_max"), "currency": g.get("currency"),
        "eligible_applicants": g.get("eligible_applicants"), "bucket": g.get("bucket"), "score": g.get("score"),
        "angle": g.get("angle"), "summary": g.get("summary"),
        "blockers": extra.get("blockers") or [], "unlock": extra.get("unlock"),
        "finance_burden": extra.get("finance_burden"), "form_status": extra.get("form_status"),
    }


def write_markdown(items: list[dict], settings: dict, today: date) -> str:
    m = settings["models"]
    profile = (CONFIG_DIR / "profile.md").read_text(encoding="utf-8")
    system = load_prompt("write") + "\n\n# PROFIL ŽADATELE (kontext)\n" + profile
    user = f"Dnes je {today.isoformat()}.\n\n" + json.dumps({"grants": [_payload(g) for g in items]}, ensure_ascii=False)
    return chat(m["strong"], system, user, m["max_tokens_strong"], effort=m.get("effort_strong"))


def footer(stats: dict, unreachable: list[str]) -> str:
    lines = ["---", f"Zkontrolováno zdrojů: {stats.get('sources_ok', 0)} z {stats.get('sources_total', 0)}, "
                   f"nových nebo změněných stránek: {stats.get('pages_new', 0)}, nových výzev: {stats.get('grants_new', 0)}."]
    if unreachable:
        lines.append("Nedostupné zdroje: " + ", ".join(unreachable) + ".")
    return "\n\n".join(lines)


HTML = """<html><body style="font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;max-width:680px;margin:0 auto;padding:16px;color:#1a1a1a;line-height:1.5">
{body}
</body></html>"""


def to_html(md_text: str) -> str:
    return HTML.format(body=markdown.markdown(md_text, extensions=["extra", "sane_lists"]))


def empty_markdown(today: date) -> str:
    return ("Dnes jsem nenašel žádnou novou výzvu, která by dobře seděla na Sláva Volklore. "
            "Agent běží a zdroje se kontrolují, další přehled přijde za dva dny.")


def build_email(items: list[dict], stats: dict, unreachable: list[str], settings: dict, today: date) -> dict:
    md_text = write_markdown(items, settings, today) if items else empty_markdown(today)
    md_text = md_text.rstrip() + "\n\n" + footer(stats, unreachable)
    n = len(items)
    subject = f"{settings['email']['subject_prefix']} – {today.day}. {today.month}. {today.year}" + (f" ({n})" if n else " (nic nového)")
    return {"subject": subject, "text": md_text, "html": to_html(md_text)}
