"""SELECT-only access to stock-related facts: inventory, sales, forecasts, promotions, storage, budgets."""

from datetime import date, timedelta

from sqlmodel import Session, select

from shared.db import models as m


def inventory(session: Session, node_id: str, sku_id: str) -> m.Inventory | None:
    return session.exec(select(m.Inventory).where(m.Inventory.node_id == node_id, m.Inventory.sku_id == sku_id)).first()


def inventory_other_nodes(session: Session, sku_id: str, exclude_node: str) -> list[m.Inventory]:
    return session.exec(
        select(m.Inventory).where(m.Inventory.sku_id == sku_id, m.Inventory.node_id != exclude_node)
    ).all()


def sales(session: Session, node_id: str, sku_id: str, today: date, days: int) -> list[m.SalesHistory]:
    return session.exec(
        select(m.SalesHistory)
        .where(
            m.SalesHistory.node_id == node_id,
            m.SalesHistory.sku_id == sku_id,
            m.SalesHistory.day >= today - timedelta(days=days),
            m.SalesHistory.day < today,
        )
        .order_by(m.SalesHistory.day)
    ).all()


def forecast(session: Session, node_id: str, sku_id: str, today: date, days: int) -> list[m.Forecast]:
    return session.exec(
        select(m.Forecast)
        .where(
            m.Forecast.node_id == node_id,
            m.Forecast.sku_id == sku_id,
            m.Forecast.day >= today,
            m.Forecast.day < today + timedelta(days=days),
        )
        .order_by(m.Forecast.day)
    ).all()


def promotions(session: Session, node_id: str, sku_id: str, today: date) -> list[m.Promotion]:
    return session.exec(
        select(m.Promotion).where(
            m.Promotion.node_id == node_id,
            m.Promotion.sku_id == sku_id,
            m.Promotion.end >= today - timedelta(days=14),
        )
    ).all()


def storage_zone(session: Session, node_id: str, zone: str) -> m.StorageZone | None:
    return session.exec(
        select(m.StorageZone).where(m.StorageZone.node_id == node_id, m.StorageZone.zone == zone)
    ).first()


def budget(session: Session, node_id: str, category: str, today: date) -> m.Budget | None:
    return session.exec(
        select(m.Budget).where(
            m.Budget.node_id == node_id,
            m.Budget.category == category,
            m.Budget.period_start <= today,
            m.Budget.period_end >= today,
        )
    ).first()


def received_since(session: Session, node_id: str, sku_id: str, since: date, today: date) -> float:
    pos = session.exec(
        select(m.PurchaseOrder).where(
            m.PurchaseOrder.node_id == node_id,
            m.PurchaseOrder.sku_id == sku_id,
            m.PurchaseOrder.status == "received",
            m.PurchaseOrder.expected_delivery >= since,
            m.PurchaseOrder.expected_delivery < today,
        )
    ).all()
    return float(sum(p.qty_confirmed or p.qty_ordered for p in pos))
