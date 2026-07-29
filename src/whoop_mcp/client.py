"""HTTP-Client fuer die WHOOP API v2.

Kuemmert sich um Bearer-Auth, Token-Erneuerung bei 401, Backoff bei 429 und
Cursor-Pagination ueber ``next_token``.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any, Iterator

import httpx

from .auth import AuthError, TokenManager
from .config import API_BASE

MAX_PAGE_SIZE = 25
MAX_RETRIES = 4


class WhoopAPIError(RuntimeError):
    def __init__(self, status_code: int, message: str):
        super().__init__(f"WHOOP API {status_code}: {message}")
        self.status_code = status_code


def iso(dt: datetime) -> str:
    """Datetime als ISO-8601 in UTC, wie von der WHOOP API erwartet."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def window(days: int, end: datetime | None = None) -> tuple[str, str]:
    """Start/Ende fuer die letzten ``days`` Tage."""
    end = end or datetime.now(timezone.utc)
    return iso(end - timedelta(days=days)), iso(end)


class WhoopClient:
    def __init__(
        self,
        tokens: TokenManager | None = None,
        http: httpx.Client | None = None,
        base_url: str = API_BASE,
    ):
        self.tokens = tokens or TokenManager()
        self.base_url = base_url.rstrip("/")
        self._http = http or httpx.Client(timeout=30)

    def close(self) -> None:
        self._http.close()

    def _get(self, path: str, params: dict | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        params = {k: v for k, v in (params or {}).items() if v is not None}
        force_refresh = False
        for attempt in range(MAX_RETRIES):
            token = self.tokens.access_token(force_refresh=force_refresh)
            response = self._http.get(
                url, params=params, headers={"Authorization": f"Bearer {token}"}
            )
            if response.status_code == 401 and not force_refresh:
                force_refresh = True
                continue
            if response.status_code == 429:
                delay = float(response.headers.get("Retry-After", 2 ** attempt))
                time.sleep(min(delay, 30))
                continue
            if response.status_code >= 500 and attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
                continue
            if response.status_code >= 400:
                raise WhoopAPIError(response.status_code, response.text)
            return response.json()
        raise WhoopAPIError(429, "Rate-Limit nach mehreren Versuchen weiterhin aktiv.")

    def _collection(
        self, path: str, days: int, limit: int | None = None, end: datetime | None = None
    ) -> list[dict]:
        start_iso, end_iso = window(days, end)
        records: list[dict] = []
        next_token: str | None = None
        while True:
            page_size = MAX_PAGE_SIZE
            if limit is not None:
                remaining = limit - len(records)
                if remaining <= 0:
                    break
                page_size = min(MAX_PAGE_SIZE, remaining)
            payload = self._get(
                path,
                {
                    "start": start_iso,
                    "end": end_iso,
                    "limit": page_size,
                    "nextToken": next_token,
                },
            )
            records.extend(payload.get("records", []))
            next_token = payload.get("next_token")
            if not next_token:
                break
        return records

    # -- Sammlungen ---------------------------------------------------------

    def recoveries(self, days: int = 7, limit: int | None = None) -> list[dict]:
        return self._collection("/v2/recovery", days, limit)

    def sleeps(self, days: int = 7, limit: int | None = None) -> list[dict]:
        return self._collection("/v2/activity/sleep", days, limit)

    def cycles(self, days: int = 7, limit: int | None = None) -> list[dict]:
        return self._collection("/v2/cycle", days, limit)

    def workouts(self, days: int = 14, limit: int | None = None) -> list[dict]:
        return self._collection("/v2/activity/workout", days, limit)

    # -- Einzelressourcen ---------------------------------------------------

    def body_measurement(self) -> dict:
        return self._get("/v2/user/measurement/body")

    def profile(self) -> dict:
        return self._get("/v2/user/profile/basic")
