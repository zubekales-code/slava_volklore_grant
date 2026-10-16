"""Stahování webů: přímo s prohlížečovou hlavičkou, při blokaci přes čtečku r.jina.ai."""
import logging
import time

import requests

log = logging.getLogger("fetch")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "cs,en;q=0.8",
}


def fetch(url: str, timeout: int = 25, reader_fallback: bool = True) -> dict:
    """Vrátí {ok, status, via, text, seconds, error}."""
    t0 = time.time()
    result = {"ok": False, "status": None, "via": "direct", "text": "", "seconds": 0.0, "error": None}
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        result["status"] = r.status_code
        if r.status_code < 400 and len(r.text) > 500:
            result.update(ok=True, text=r.text)
    except requests.RequestException as e:
        result["error"] = type(e).__name__
    if not result["ok"] and reader_fallback:
        try:
            r = requests.get(f"https://r.jina.ai/{url}", headers={"Accept": "text/plain"}, timeout=timeout + 20)
            if r.status_code < 400 and len(r.text) > 300:
                result.update(ok=True, via="reader", status=r.status_code, text=r.text, error=None)
        except requests.RequestException as e:
            result["error"] = (result["error"] or "") + f" / reader {type(e).__name__}"
    result["seconds"] = round(time.time() - t0, 1)
    return result
