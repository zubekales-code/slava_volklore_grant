"""Diagnostika: ověří klíče, OpenAI, Supabase, odesílání e-mailu a všechny zdroje. Spouští se ručně z GitHub Actions.

Na konci vypíše souhrn. Log stačí zkopírovat a poslat Claudovi.
"""
import logging
import sys
import time

from config_loader import SECRET_NAMES, load_settings, load_sources, secret
from http_fetch import fetch

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

OK, WARN, ERR = "OK  ", "WARN", "ERR "
results: list[tuple[str, str, str]] = []


def report(status: str, area: str, msg: str):
    results.append((status, area, msg))
    print(f"[{status}] {area}: {msg}", flush=True)


def check_secrets():
    for name in SECRET_NAMES:
        v = secret(name, required=False)
        if v:
            report(OK, "klíče", f"{name} vyplněn ({len(v)} znaků)")
        else:
            report(ERR, "klíče", f"{name} chybí")
    url = secret("SUPABASE_URL", required=False)
    if url and "/rest/v1" in url:
        report(WARN, "klíče", "SUPABASE_URL obsahuje /rest/v1 – stačí https://<projekt>.supabase.co (kód si poradí)")


def check_openai(settings):
    try:
        from openai_client import chat, client
        ids = {m.id for m in client().models.list().data}
        report(OK, "openai", f"připojeno, dostupných modelů: {len(ids)}")
        for role in ("cheap", "strong"):
            model = settings["models"][role]
            if model not in ids:
                report(ERR, "openai", f"model {model} ({role}) není pro tento klíč dostupný")
                continue
            t0 = time.time()
            text = chat(model, "Odpovídej jedním slovem.", "Napiš slovo: funguje", settings["models"][f"max_tokens_{role}"])
            report(OK, "openai", f"{model} odpověděl za {time.time()-t0:.1f} s: {text[:30]!r}")
    except Exception as e:
        report(ERR, "openai", f"{type(e).__name__}: {str(e)[:200]}")


def check_supabase():
    try:
        from storage import Storage
        st = Storage()
        for table in ("raw_items", "grants", "runs", "diag_test"):
            ok, info = st.ping(table)
            if ok:
                report(OK, "supabase", f"tabulka {table} čitelná")
            else:
                report(ERR, "supabase", f"tabulka {table}: {info} (spusťte sql/schema.sql v SQL Editoru)")
        rows = [{"key": "diag-a", "note": "test"}, {"key": "diag-b"}]  # různé tvary klíčů
        n1 = st.insert_ignore("diag_test", rows, conflict="key")
        n2 = st.insert_ignore("diag_test", rows, conflict="key")  # podruhé musí přeskočit duplicity
        cleaned = st.delete("diag_test", {"key": "diag-a"}) + st.delete("diag_test", {"key": "diag-b"})
        if n1 == 2 and n2 == 0 and cleaned == 2:
            report(OK, "supabase", "zápis, přeskočení duplicit i úklid fungují")
        else:
            report(ERR, "supabase", f"zápis nesedí: poprvé {n1}/2, podruhé {n2}/0, smazáno {cleaned}/2. "
                                    "Spustili jste sql/schema.sql v Supabase?")
    except Exception as e:
        report(ERR, "supabase", f"{type(e).__name__}: {str(e)[:200]}")


def check_email(settings):
    """Pošle testovací e-mail přes Resend. Do Gmailu se nepřihlašuje, ten je jen příjemce."""
    import requests
    key = secret("RESEND_API_KEY", required=False)
    if not key:
        report(ERR, "e-mail", "chybí RESEND_API_KEY")
        return
    em = settings["email"]
    try:
        r = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "from": f'{em["from_name"]} <{em["from_address"]}>',
                "to": em["to"],
                "subject": "Grantový agent – test diagnostiky",
                "text": "Tohle je testovací e-mail z diagnostiky. Odesílání funguje.",
            },
            timeout=30,
        )
        if r.status_code < 300:
            report(OK, "e-mail", f"testovací e-mail odeslán na {', '.join(em['to'])}")
        else:
            report(ERR, "e-mail", f"Resend {r.status_code}: {r.text[:200]} "
                                  "(bez ověřené domény jde posílat jen na e-mail, kterým jste se v Resendu registrovali)")
    except Exception as e:
        report(ERR, "e-mail", f"{type(e).__name__}: {str(e)[:150]}")


def check_sources(settings):
    sources = load_sources(only_enabled=True)
    timeout = settings["collect"]["request_timeout"]
    fallback = settings["collect"]["use_reader_fallback"]
    print(f"\nZdroje ({len(sources)}):", flush=True)
    for s in sources:
        r = fetch(s["url"], timeout=timeout, reader_fallback=fallback, verify_ssl=s.get("verify_ssl", True))
        label = f'{s["id"]} {s["name"]}'
        if r["ok"] and r["via"] == "direct":
            report(OK, "zdroj", f"{label} – přímo, {len(r['text'])//1000} kB, {r['seconds']} s")
        elif r["ok"]:
            report(WARN, "zdroj", f"{label} – jen přes čtečku (přímo status {r['status']}), {r['seconds']} s")
        else:
            report(ERR, "zdroj", f"{label} – nedostupné (status {r['status']}, {r['error']})")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    settings = load_settings()
    print("=== Diagnostika grantového agenta ===\n", flush=True)
    check_secrets()
    if mode in ("all", "services"):
        check_openai(settings)
        check_supabase()
        check_email(settings)
    if mode in ("all", "sources"):
        check_sources(settings)

    oks = sum(1 for r in results if r[0] == OK)
    warns = [r for r in results if r[0] == WARN]
    errs = [r for r in results if r[0] == ERR]
    print("\n=== SOUHRN ===")
    print(f"v pořádku: {oks}, varování: {len(warns)}, chyby: {len(errs)}")
    for status, area, msg in warns + errs:
        print(f"  [{status}] {area}: {msg}")
    # Workflow neselže kvůli nedostupným zdrojům, jen kvůli službám
    service_errs = [r for r in errs if r[1] != "zdroj"]
    sys.exit(1 if service_errs else 0)


if __name__ == "__main__":
    main()
