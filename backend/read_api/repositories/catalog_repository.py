"""SELECT-only access to master data: world, nodes, SKUs, suppliers, recommendations."""

from sqlmodel import Session, select

from shared.db import models as m


def world(session: Session) -> m.World | None:
    return session.get(m.World, 1)


def nodes(session: Session) -> list[m.Node]:
    return list(session.exec(select(m.Node)).all())


def sku(session: Session, sku_id: str) -> m.Sku | None:
    return session.get(m.Sku, sku_id)


def skus(session: Session) -> list[m.Sku]:
    return list(session.exec(select(m.Sku)).all())


def supplier(session: Session, supplier_id: str) -> m.Supplier | None:
    return session.get(m.Supplier, supplier_id)


def recommendation(session: Session, rec_id: str) -> m.Recommendation | None:
    return session.get(m.Recommendation, rec_id)


def recommendations(session: Session) -> list[m.Recommendation]:
    return list(session.exec(select(m.Recommendation)).all())
