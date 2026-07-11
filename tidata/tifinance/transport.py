"""Transport seam — how rows arrive, separated from what Ticker does with them.

The interface is one method: ``fetch(path, params) -> list[dict]``. The HTTP
adapter hides the session, pagination, response-envelope unwrapping, and error
mapping. Tests supply an in-memory adapter instead of faking the network.
"""

from __future__ import annotations

from typing import Protocol

import requests

from .exceptions import from_code

_PAGE_SIZE = 1000


class Transport(Protocol):
    """Fetch all rows for an endpoint, assembling paginated results."""

    def fetch(self, path: str, params: dict) -> list: ...


class HttpTransport:
    """Transport backed by the TradeInsight HTTP API via ``requests``.

    Owns the session, pagination, envelope unwrapping, and error mapping.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        timeout: int = 30,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._session = requests.Session()
        if api_key:
            self._session.headers.update({"Authorization": f"Bearer {api_key}"})

    def fetch(self, path: str, params: dict) -> list:
        rows: list = []
        offset = 0
        while True:
            page_params = {**params, "limit": _PAGE_SIZE, "offset": offset}
            response = self._session.get(
                f"{self.base_url}/{path.lstrip('/')}",
                params=page_params,
                timeout=self.timeout,
            )
            if not response.ok:
                self._raise_for_error(response)
            data = response.json()
            if isinstance(data, list):
                page = data
            elif isinstance(data, dict) and "data" in data:
                page = data["data"]
            else:
                page = []
            rows.extend(page)
            if len(page) < _PAGE_SIZE:
                break
            offset += _PAGE_SIZE
        return rows

    def _raise_for_error(self, response: requests.Response) -> None:
        try:
            body = response.json()
            code = body.get("code", f"HTTP_{response.status_code}")
            message = body.get("message", response.text or "Unknown error")
        except Exception:
            code = f"HTTP_{response.status_code}"
            message = response.text or "Unknown error"
        raise from_code(code, message)
