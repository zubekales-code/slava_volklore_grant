"""Odeslání e-mailu přes Resend. Do Gmailu se nepřihlašuje, ten je jen příjemce."""
import logging

import requests

from config_loader import secret

log = logging.getLogger("email")


def send(settings: dict, subject: str, text: str, html: str | None = None) -> None:
    em = settings["email"]
    payload = {
        "from": f'{em["from_name"]} <{em["from_address"]}>',
        "to": em["to"],
        "subject": subject,
        "text": text,
    }
    if html:
        payload["html"] = html
    r = requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {secret('RESEND_API_KEY')}", "Content-Type": "application/json"},
        json=payload, timeout=30,
    )
    if r.status_code >= 300:
        raise RuntimeError(f"Resend {r.status_code}: {r.text[:300]}")
    log.warning("E-mail odeslán na %s", ", ".join(em["to"]))
