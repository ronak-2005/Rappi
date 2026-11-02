"""Mock supplier system (port 8003): a stand-in for suppliers' ordering APIs.

POST /orders           place an order (idempotent on idempotency_key)
GET  /orders           everything received (used by evals to count real supplier-side orders)
POST /admin/scenario   reset state and set per-supplier behaviour for the loaded scenario

Run: uvicorn mock_supplier.server.main:app --port 8003
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from mock_supplier.behaviours import Behaviour, OrderIn, OrderOut, respond


class ScenarioIn(BaseModel):
    behaviours: dict[str, Behaviour] = {}


def create_app() -> FastAPI:
    app = FastAPI(title="Mock supplier", version="0.1.0")
    state = {"behaviours": {}, "orders": {}, "count": {}, "timed_out": set()}
    app.state.store = state

    @app.get("/health")
    def health():
        return {"service": "mock_supplier", "ok": True, "orders": len(state["orders"])}

    @app.post("/admin/scenario")
    def set_scenario(body: ScenarioIn):
        state.update(behaviours=body.behaviours, orders={}, count={}, timed_out=set())
        return {"ok": True, "behaviours": {k: v.model_dump() for k, v in body.behaviours.items()}}

    @app.post("/orders", response_model=OrderOut)
    def place_order(order: OrderIn):
        if order.idempotency_key in state["orders"]:  # retry of an order we already have
            stored: OrderOut = state["orders"][order.idempotency_key]
            return JSONResponse(stored.model_dump(mode="json"), headers={"idempotent-replay": "true"})
        n = state["count"].get(order.supplier_id, 0)
        behaviour = state["behaviours"].get(order.supplier_id, Behaviour())
        out, timeout = respond(order, behaviour, n)
        state["orders"][order.idempotency_key] = out
        state["count"][order.supplier_id] = n + 1
        if timeout and order.supplier_id not in state["timed_out"]:
            state["timed_out"].add(order.supplier_id)
            return JSONResponse({"error": "gateway timeout"}, status_code=504)
        return out

    @app.get("/orders")
    def list_orders():
        return [o.model_dump(mode="json") for o in state["orders"].values()]

    return app


app = create_app()
