"""When would an order placed now actually arrive? (order cut-off time + supplier delivery weekdays)"""

from datetime import date, timedelta


def order_day(now_hour: int, cutoff_hour: int) -> int:
    """Orders after the supplier's cut-off hour count as placed tomorrow."""
    return 0 if now_hour < cutoff_hour else 1


def is_delivery_day(today: date, offset: int, delivery_weekdays: list[int]) -> bool:
    return (today + timedelta(days=offset)).weekday() in delivery_weekdays


def next_delivery_day(today: date, earliest: int, delivery_weekdays: list[int]) -> int:
    if not delivery_weekdays:
        raise ValueError("supplier has no delivery weekdays")
    day = earliest
    while not is_delivery_day(today, day, delivery_weekdays):
        day += 1
    return day


def arrival_day(today: date, now_hour: int, lead_days: int, cutoff_hour: int, delivery_weekdays: list[int]) -> int:
    """Earliest arrival offset (days from today) for an order placed now."""
    return next_delivery_day(today, order_day(now_hour, cutoff_hour) + lead_days, delivery_weekdays)
