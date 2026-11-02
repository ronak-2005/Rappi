"""HTTP client for the supplier system. Retries timeouts / 5xx with the SAME idempotency key,
so a lost response can never create a second order."""

import logging
from dataclasses import dataclass
from datetime import date

import httpx

log = logging.getLogger("write_api.clients.supplier_client")


@dataclass
class SupplierReply:
    ok: bool
    data: dict | None
    attempts: int
    replayed: bool
    error: str = ""


class SupplierClient:
    """`http` is an httpx.Client with base_url set (timeouts configured on it), or a TestClient in tests."""

    @classmethod
    def from_url(cls, base_url: str, timeout_s: float = 10.0) -> "SupplierClient":
        return cls(httpx.Client(base_url=base_url, timeout=timeout_s))

    def __init__(self, http: httpx.Client, max_attempts: int = 3):
        self.http = http
        self.max_attempts = max_attempts

    def place_order(
        self,
        *,
        idempotency_key: str,
        po_id: str,
        supplier_id: str,
        sku_id: str,
        qty: int,
        unit_cost: float,
        requested_delivery: date,
        mode: str,
    ) -> SupplierReply:
        body = {
            "idempotency_key": idempotency_key,
            "po_id": po_id,
            "supplier_id": supplier_id,
            "sku_id": sku_id,
            "qty": qty,
            "unit_cost": unit_cost,
            "requested_delivery": requested_delivery.isoformat(),
            "mode": mode,
        }
        error = ""
        for attempt in range(1, self.max_attempts + 1):
            try:
                r = self.http.post("/orders", json=body)
            except httpx.TransportError as exc:
                error = f"transport error: {exc}"
                log.warning("supplier %s attempt %d failed: %s", supplier_id, attempt, error)
                continue
            if r.status_code >= 500:
                error = f"HTTP {r.status_code}"
                log.warning(
                    "supplier %s attempt %d: %s, retrying with same idempotency key", supplier_id, attempt, error
                )
                continue
            if r.status_code >= 400:
                return SupplierReply(False, None, attempt, False, f"HTTP {r.status_code}: {r.text[:200]}")
            return SupplierReply(True, r.json(), attempt, r.headers.get("idempotent-replay") == "true")
        return SupplierReply(False, None, self.max_attempts, False, error or "no response")

    def set_scenario(self, behaviours: dict) -> None:
        self.http.post("/admin/scenario", json={"behaviours": behaviours}).raise_for_status()

    def orders(self) -> list[dict]:
        return self.http.get("/orders").json()
