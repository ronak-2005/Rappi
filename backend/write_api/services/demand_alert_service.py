"""Use-case (Scenario 3): demand monitoring raises an alert for a product at a store."""

import uuid

from sqlmodel import Session

from shared.db import models as m
from shared.db import snapshot


def create(session: Session, *, node: str, sku: str, message: str) -> m.DemandAlert:
    alert = m.DemandAlert(
        id=f"AL-{uuid.uuid4().hex[:8]}",
        node_id=node,
        sku_id=sku,
        message=message,
        raised_on=snapshot.world(session).today,
    )
    session.add(alert)
    session.commit()
    return alert
