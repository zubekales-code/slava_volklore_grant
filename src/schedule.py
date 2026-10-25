"""Plán: spustit jen ráno v pražském čase (okno send_hour až send_until_hour) a jen každý N-tý den od zadaného dne.

GitHub plánované běhy často zpožďuje (i o několik hodin), proto je okno široké
a v main.py se navíc hlídá, aby se za jeden den neposlalo dvakrát.
"""
from datetime import date, datetime
from zoneinfo import ZoneInfo


def prague_now(settings: dict) -> datetime:
    return datetime.now(ZoneInfo(settings["schedule"]["timezone"]))


def should_run_now(settings: dict, now: datetime | None = None) -> tuple[bool, str]:
    s = settings["schedule"]
    now = now or prague_now(settings)
    start = s["send_hour"]
    end = s.get("send_until_hour", start)
    if not (start <= now.hour <= end):
        return False, f"v Praze je {now:%H:%M}, odesílá se mezi {start}:00 a {end}:59, tenhle běh se přeskakuje"
    days = (now.date() - date.fromisoformat(s["anchor_date"])).days
    if days % s["every_n_days"] != 0:
        return False, f"dnes je den {days} od začátku, odesílá se každý {s['every_n_days']}. den, dnes se nepošle"
    return True, "ano"
