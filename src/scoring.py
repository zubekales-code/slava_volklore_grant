"""Hodnocení výzev podle profilu (levný model) + tvrdá pravidla v kódu."""
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import date

from config_loader import CONFIG_DIR, load_prompt
from openai_client import chat_json

log = logging.getLogger("scoring")

BUCKETS = {"fit", "adapt", "later", "no"}
BATCH = 5


def _profile() -> str:
    return (CONFIG_DIR / "profile.md").read_text(encoding="utf-8")


def compact(g: dict) -> dict:
    extra = g.get("extra") or {}
    return {
        "id": g["id"], "title": g.get("title"), "funder": g.get("funder"), "deadline": g.get("deadline"),
        "status": g.get("status"), "amount_min": g.get("amount_min"), "amount_max": g.get("amount_max"),
        "currency": g.get("currency"), "eligible_applicants": g.get("eligible_applicants"),
        "applicant_types": extra.get("applicant_types"), "region": g.get("region"), "topics": g.get("topics"),
        "cofinancing_pct": extra.get("cofinancing_pct"), "cofinancing_note": extra.get("cofinancing_note"),
        "funding_mode": extra.get("funding_mode"), "requires_foreign_partner": extra.get("requires_foreign_partner"),
        "summary": g.get("summary"),
    }


def is_expired(g: dict, today: date) -> bool:
    if g.get("status") == "closed":
        return True
    d = g.get("deadline")
    return bool(d) and date.fromisoformat(d) < today


def apply_rules(res: dict, g: dict, settings: dict) -> dict:
    """Pravidla v kódu mají přednost před úsudkem modelu."""
    bucket = res.get("bucket") if res.get("bucket") in BUCKETS else "no"
    score = max(1, min(10, int(res.get("score") or 1)))
    blockers = [str(b) for b in (res.get("blockers") or [])]
    burden = res.get("finance_burden") or "unknown"
    form = res.get("form_status") or "unknown"
    # Vysoká finanční zátěž: výzva není pro dnešek, ale nezahazujeme ji
    if burden == "high" and bucket in ("fit", "adapt"):
        bucket = "later"
        blockers.append("finančně náročné vzhledem k dnešním volným prostředkům")
    # Vyžaduje jinou formu: také „až později“
    if form == "other_form" and bucket in ("fit", "adapt"):
        bucket = "later"
    return {
        "score": score, "bucket": bucket, "angle": res.get("angle"),
        "extra": {**(g.get("extra") or {}), "finance_burden": burden, "form_status": form,
                  "blockers": blockers, "unlock": res.get("unlock")},
    }


def _score_batch(batch: list[dict], settings: dict) -> dict[int, dict]:
    m = settings["models"]
    system = (load_prompt("score") + "\n\n# PROFIL ŽADATELE\n" + _profile() +
              f"\n\n# FINANČNÍ OMEZENÍ\nVolné vlastní peníze žadatele: asi {settings['finance']['free_cash_czk']} Kč.")
    user = json.dumps({"grants": [compact(g) for g in batch]}, ensure_ascii=False)
    data = chat_json(m["cheap"], system, user, m["max_tokens_cheap"], effort=m.get("effort_cheap"))
    return {int(r["id"]): r for r in (data.get("results") or []) if isinstance(r, dict) and "id" in r}


def score_pending(settings: dict, storage, today: date) -> dict:
    rows = storage.select("grants", {"select": "*", "score": "is.null", "limit": "500", "order": "id.asc"})
    stats = {"to_score": len(rows), "expired": 0, "scored": 0, "failed": 0}
    todo = []
    for g in rows:
        if is_expired(g, today):
            storage.update("grants", {"id": g["id"]}, {"score": 0, "bucket": "no"})
            stats["expired"] += 1
        else:
            todo.append(g)
    batches = [todo[i : i + BATCH] for i in range(0, len(todo), BATCH)]

    def work(b):
        try:
            return b, _score_batch(b, settings), None
        except Exception as e:
            return b, {}, f"{type(e).__name__}: {str(e)[:150]}"

    with ThreadPoolExecutor(max_workers=settings["collect"]["workers_llm"]) as ex:
        results = list(ex.map(work, batches))
    for b, res_by_id, err in results:
        if err:
            log.warning("Hodnocení dávky selhalo: %s", err)
        for g in b:
            r = res_by_id.get(g["id"])
            if not r:
                stats["failed"] += 1  # zůstane bez skóre a zkusí se příště
                continue
            storage.update("grants", {"id": g["id"]}, apply_rules(r, g, settings))
            stats["scored"] += 1
    log.warning("Hodnocení: %s", json.dumps(stats, ensure_ascii=False))
    return stats
