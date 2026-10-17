"""Plán: spustit jen v 7:xx pražského času a jen každý N-tý den od zadaného dne."""
from datetime import date, datetime
from zoneinfo import ZoneInfo


def prague_now(settings: dict) -> datetime:
    return datetime.now(ZoneInfo(settings["schedule"]["timezone"]))


def should_run_now(settings: dict, now: datetime | None = None) -> tuple[bool, str]:
    s = settings["schedule"]
    now = now or prague_now(settings)
    if now.hour != s["send_hour"]:
        return False, f"v Praze je {now:%H:%M}, odesílá se v {s['send_hour']}:xx, tenhle běh se přeskakuje"
    days = (now.date() - date.fromisoformat(s["anchor_date"])).days
    if days % s["every_n_days"] != 0:
        return False, f"dnes je den {days} od začátku, odesílá se každý {s['every_n_days']}. den, dnes se nepošle"
    return True, "ano"
