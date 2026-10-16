"""Práce se Supabase přes REST (PostgREST). Bez další knihovny, jen requests."""
import json
import logging

import requests

from config_loader import secret

log = logging.getLogger("storage")


class Storage:
    def __init__(self):
        url = secret("SUPABASE_URL").rstrip("/")
        if url.endswith("/rest/v1"):
            url = url[: -len("/rest/v1")]
        self.base = f"{url}/rest/v1"
        key = secret("SUPABASE_KEY")
        self.headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }

    # ---------- čtení
    def select(self, table: str, params: dict | None = None) -> list[dict]:
        r = requests.get(f"{self.base}/{table}", headers=self.headers, params=params or {}, timeout=30)
        if r.status_code >= 300:
            log.error("Čtení %s selhalo: %s %s", table, r.status_code, r.text[:300])
            return []
        return r.json()

    def ping(self, table: str) -> tuple[bool, str]:
        r = requests.get(f"{self.base}/{table}", headers=self.headers, params={"select": "*", "limit": "1"}, timeout=30)
        return r.status_code < 300, f"{r.status_code} {r.text[:120]}"

    # ---------- zápis
    @staticmethod
    def _normalize(rows: list[dict]) -> list[dict]:
        """Všechny objekty v dávce musí mít stejné klíče (jinak PGRST102)."""
        keys = sorted({k for row in rows for k in row})
        return [{k: row.get(k) for k in keys} for row in rows]

    def insert_ignore(self, table: str, rows: list[dict], conflict: str) -> int:
        """Vloží řádky, duplicity (podle sloupce conflict) přeskočí. Vrací skutečný počet nových."""
        if not rows:
            return 0
        headers = dict(self.headers)
        headers["Prefer"] = "resolution=ignore-duplicates,return=representation"
        r = requests.post(
            f"{self.base}/{table}?on_conflict={conflict}",
            headers=headers,
            data=json.dumps(self._normalize(rows), ensure_ascii=False, default=str),
            timeout=60,
        )
        if r.status_code >= 300:
            log.error("Zápis do %s selhal: %s %s", table, r.status_code, r.text[:300])
            return 0
        return len(r.json())

    def upsert(self, table: str, rows: list[dict], conflict: str) -> int:
        """Vloží nebo přepíše řádky podle sloupce conflict. Vrací počet zapsaných."""
        if not rows:
            return 0
        headers = dict(self.headers)
        headers["Prefer"] = "resolution=merge-duplicates,return=representation"
        r = requests.post(
            f"{self.base}/{table}?on_conflict={conflict}",
            headers=headers,
            data=json.dumps(self._normalize(rows), ensure_ascii=False, default=str),
            timeout=60,
        )
        if r.status_code >= 300:
            log.error("Upsert do %s selhal: %s %s", table, r.status_code, r.text[:300])
            return 0
        return len(r.json())

    def update(self, table: str, match: dict, values: dict) -> int:
        params = {k: f"eq.{v}" for k, v in match.items()}
        headers = dict(self.headers)
        headers["Prefer"] = "return=representation"
        r = requests.patch(f"{self.base}/{table}", headers=headers, params=params,
                           data=json.dumps(values, default=str), timeout=30)
        if r.status_code >= 300:
            log.error("Úprava %s selhala: %s %s", table, r.status_code, r.text[:300])
            return 0
        return len(r.json())

    def delete(self, table: str, match: dict) -> int:
        params = {k: f"eq.{v}" for k, v in match.items()}
        headers = dict(self.headers)
        headers["Prefer"] = "return=representation"
        r = requests.delete(f"{self.base}/{table}", headers=headers, params=params, timeout=30)
        if r.status_code >= 300:
            log.error("Mazání v %s selhalo: %s %s", table, r.status_code, r.text[:300])
            return 0
        return len(r.json())
