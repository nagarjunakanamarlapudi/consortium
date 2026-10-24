"""Price helpers."""

PRICE_THRESHOLDS = [5, 10, 15, 20]


def total_price(unit_price: int, quantity: int) -> int:
    return unit_price * quantity
