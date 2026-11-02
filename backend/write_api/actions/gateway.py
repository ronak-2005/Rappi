"""The purchasing clerk: the ONLY code path that turns a decision into purchase orders.

For each order line:
  1. idempotency key = hash(run, attempt, line) → if a PO with that key exists, reuse it (never duplicate)
  2. create the PO as 'draft', then mark 'sent' and call the supplier (client retries with the same key)
  3. store the supplier's answer (confirmed / partially_confirmed / rejected, qty, date, price)
  4. commit the confirmed value to the budget
The caller (orchestrator) has already validated the plan and obtained approval when required.
"""

import hashlib
import logging
from datetime import date, timedelta

from sqlmodel import Session

from shared.db import models as m
from shared.db import snapshot
from shared.domain.decision import ExecutionLine, ExecutionResult
from shared.domain.planning import PlanLine, TransferLine
from shared.engine.options import earliest_arrival
from write_api.clients.supplier_client import SupplierClient
from write_api.repositories import availability_repository
from write_api.repositories import order_repository as orders

log = logging.getLogger("write_api.actions.gateway")


def idempotency_key(run_id: str, attempt_tag: str, index: int, line: PlanLine, delivery_iso: str) -> str:
    raw = f"{run_id}|{attempt_tag}|{index}|{line.supplier_id}|{line.qty}|{line.mode}|{delivery_iso}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def execute(
    session: Session,
    supplier: SupplierClient,
    *,
    run_id: str,
    attempt_tag: str,
    node: str,
    sku: str,
    lines: list[PlanLine],
    recommendation_id: str | None = None,
    transfers: list[TransferLine] | None = None,
) -> ExecutionResult:
    ctx = snapshot.build_context(session, node, sku, recommendation_id)
    sku_row = session.get(m.Sku, sku)
    results: list[ExecutionLine] = []
    for j, t in enumerate(transfers or []):  # internal moves: no supplier involved
        src = next(x for x in ctx.transfer_sources if x.node_id == t.from_node)
        eta = ctx.today + timedelta(days=src.lead_days)
        tid = "TR-" + hashlib.sha256(f"{run_id}|{attempt_tag}|t{j}|{t.from_node}|{t.qty}".encode()).hexdigest()[:10]
        existing = orders.transfer(session, tid)
        if existing is None:
            orders.create_transfer(
                session,
                transfer_id=tid,
                from_node=t.from_node,
                to_node=node,
                sku=sku,
                qty=t.qty,
                eta=eta,
                run_id=run_id,
            )
        results.append(
            ExecutionLine(
                po_id=tid,
                supplier_id=f"transfer:{t.from_node}",
                qty_requested=t.qty,
                qty_confirmed=t.qty,
                status="confirmed",
                requested_delivery=eta.isoformat(),
                confirmed_delivery=eta.isoformat(),
                unit_cost=src.cost_per_unit,
                message=f"transfer from {t.from_node}",
                replayed=existing is not None,
            )
        )
    for i, line in enumerate(lines):
        offer = next(o for o in ctx.offers if o.supplier_id == line.supplier_id)
        day = line.delivery_day if line.delivery_day is not None else earliest_arrival(ctx, offer, line.mode)
        delivery = ctx.today + timedelta(days=day)
        unit_cost = offer.unit_cost + (offer.express_premium_per_unit if line.mode == "express" else 0.0)
        key = idempotency_key(run_id, attempt_tag, i, line, delivery.isoformat())

        po = orders.by_idempotency_key(session, key)
        if po is not None and po.status not in ("draft", "sent"):
            log.info("line %d already executed as %s (idempotent reuse)", i, po.id)
            results.append(_line_from_po(po, line.qty, delivery.isoformat(), replayed=True, attempts=0))
            continue
        if po is None:
            po = orders.create_po(
                session,
                id=orders.next_po_id(session),
                node_id=node,
                sku_id=sku,
                supplier_id=line.supplier_id,
                qty_ordered=line.qty,
                unit_cost=round(unit_cost, 4),
                mode=line.mode,
                status="draft",
                order_date=ctx.today,
                expected_delivery=delivery,
                remaining_shelf_life_days=offer.remaining_shelf_life_days,
                idempotency_key=key,
                run_id=run_id,
                created_by="agent",
            )
            orders.add_event(session, po.id, "created", {"qty": line.qty, "delivery": delivery.isoformat()})

        orders.update_po(session, po, status="sent")
        reply = supplier.place_order(
            idempotency_key=key,
            po_id=po.id,
            supplier_id=line.supplier_id,
            sku_id=sku,
            qty=line.qty,
            unit_cost=round(unit_cost, 4),
            requested_delivery=delivery,
            mode=line.mode,
        )
        if reply.attempts > 1:
            orders.add_event(session, po.id, "retried", {"attempts": reply.attempts, "replayed": reply.replayed})
        if not reply.ok:
            orders.update_po(session, po, status="failed", qty_confirmed=0, notes=reply.error)
            orders.add_event(session, po.id, "failed", {"error": reply.error, "attempts": reply.attempts})
            results.append(
                ExecutionLine(
                    po_id=po.id,
                    supplier_id=line.supplier_id,
                    qty_requested=line.qty,
                    qty_confirmed=0,
                    status="failed",
                    requested_delivery=delivery.isoformat(),
                    unit_cost=unit_cost,
                    message=reply.error,
                    attempts=reply.attempts,
                )
            )
            continue

        d = reply.data
        po = orders.update_po(
            session,
            po,
            status=d["status"],
            qty_confirmed=d["qty_confirmed"],
            expected_delivery=_date(d["delivery_date"]),
            unit_cost=d["unit_cost"],
            notes=d.get("message", ""),
        )
        orders.add_event(session, po.id, d["status"], d)
        if d["qty_confirmed"] < line.qty:  # remember: this supplier can't supply more right now
            availability_repository.record_unavailable(
                session, line.supplier_id, sku, ctx.today, 14, d.get("message", "")
            )
        if d["qty_confirmed"] > 0:
            orders.commit_budget(session, node, sku_row.category, ctx.today, d["qty_confirmed"] * d["unit_cost"])
        results.append(
            _line_from_po(po, line.qty, delivery.isoformat(), replayed=reply.replayed, attempts=reply.attempts)
        )
    return ExecutionResult(lines=results)


def _date(s: str) -> date:
    return date.fromisoformat(s)


def _line_from_po(
    po: m.PurchaseOrder, requested: int, requested_delivery: str, replayed: bool, attempts: int
) -> ExecutionLine:
    return ExecutionLine(
        po_id=po.id,
        supplier_id=po.supplier_id,
        qty_requested=requested,
        qty_confirmed=po.qty_confirmed or 0,
        status=po.status,
        requested_delivery=requested_delivery,
        confirmed_delivery=po.expected_delivery.isoformat(),
        unit_cost=po.unit_cost,
        message=po.notes,
        attempts=attempts,
        replayed=replayed,
    )
