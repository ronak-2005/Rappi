"""HTTP client for the Read API. The agent investigates ONLY through this client, so everything it
learns comes from the read-only side and every call shows up in the Read API's logs."""

import httpx

from shared.domain.errors import DomainError


class ReadApiError(DomainError):
    code = "read_api_error"
    status = 502


class ReadApiClient:
    def __init__(self, http: httpx.Client):
        self.http = http  # httpx.Client(base_url=...) or a TestClient(read_app) in-process

    @classmethod
    def from_url(cls, base_url: str, timeout_s: float = 15.0) -> "ReadApiClient":
        return cls(httpx.Client(base_url=base_url, timeout=timeout_s))

    def _handle(self, r: httpx.Response) -> dict:
        if r.status_code >= 400:
            try:
                err = r.json().get("error", {})
                msg = err.get("message", r.text)
            except ValueError:
                msg = r.text
            raise ReadApiError(f"read_api {r.request.method} {r.request.url.path} → {r.status_code}: {msg}",
                               "write_api.clients.read_api_client")
        return r.json()

    def get(self, path: str, **params) -> dict:
        return self._handle(self.http.get(path, params={k: v for k, v in params.items() if v is not None}))

    def post(self, path: str, body: dict, **params) -> dict:
        return self._handle(self.http.post(path, json=body, params={k: v for k, v in params.items() if v is not None}))
