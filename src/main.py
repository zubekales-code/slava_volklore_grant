"""Hlavní běh agenta.

python main.py run-dry      stáhne, vyhodnotí, napíše e-mail do logu, NEPOŠLE a neoznačí výzvy jako odeslané
python main.py run-send     totéž a e-mail pošle
python main.py scheduled    jako run-send, ale jen pokud je správný den a hodina (pro plánovač)
"""
import json
import logging
import sys
import traceback

from collect import collect_all, mark_new
from config_loader import load_settings, load_sources
from extract_grants import extract_all
from schedule import prague_now, should_run_now
from scoring import score_pending
from send_email import send
from storage import Storage
from write_newsletter import build_email, select_for_email

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("main")


def run(mode: str) -> None:
    settings = load_settings()
    now = prague_now(settings)
    today = now.date()

    if mode == "scheduled":
        ok, why = should_run_now(settings, now)
        print(f"Plán: {why}")
        if not ok:
            return
        mode = "run-send"

    st = Storage()
    sources = [s for s in load_sources(only_enabled=True) if s.get("priority", 1) in settings["collect"]["priorities"]]
    print(f"Zdroje ke čtení: {len(sources)}", flush=True)

    items = collect_all(settings, sources)
    unreachable = [i["source"]["name"] for i in items if not i["ok"]]
    new_items = mark_new(items, st)
    print(f"Nové nebo změněné stránky: {len(new_items)}", flush=True)

    stats = {"sources_total": len(items), "sources_ok": len(items) - len(unreachable), "pages_new": len(new_items)}
    stats.update(extract_all(new_items, settings, st, today))
    stats["scoring"] = score_pending(settings, st, today)

    selected = select_for_email(settings, st, today)
    print(f"Do e-mailu vybráno výzev: {len(selected)}", flush=True)
    mail = build_email(selected, stats, unreachable, settings, today)

    if mode == "run-dry":
        print("\n===== NÁHLED E-MAILU (neodesláno) =====")
        print("Předmět:", mail["subject"], "\n")
        print(mail["text"])
        print("\n===== KONEC NÁHLEDU =====")
    else:
        send(settings, mail["subject"], mail["text"], mail["html"])
        now_iso = now.isoformat()
        for g in selected:
            st.update("grants", {"id": g["id"]}, {"sent_at": now_iso})
        st.insert_ignore("runs", [{"kind": "send", "stats": stats, "ok": True}], conflict="id")
    print("Statistiky:", json.dumps(stats, ensure_ascii=False, default=str))


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "run-dry"
    if mode not in ("run-dry", "run-send", "scheduled"):
        sys.exit(f"Neznámý režim: {mode}")
    try:
        run(mode)
    except Exception as e:
        tb = traceback.format_exc()
        print(tb, flush=True)
        if mode != "run-dry":
            try:  # pokud to jde, dát vědět e-mailem, ať si chyby někdo všimne
                send(load_settings(), "Grantový agent: běh selhal", f"Agent narazil na chybu:\n\n{type(e).__name__}: {str(e)[:500]}\n\nPodrobnosti jsou v GitHub Actions.")
            except Exception:
                pass
        sys.exit(1)


if __name__ == "__main__":
    main()
