from __future__ import annotations

from typing import Any, Dict, List


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize_price_tiers(raw_tiers: Any) -> List[Dict[str, int]]:
    if not isinstance(raw_tiers, list):
        return []

    by_min_quantity: Dict[int, int] = {}
    for item in raw_tiers:
        if not isinstance(item, dict):
            continue
        min_quantity = _as_int(item.get("min_quantity", item.get("quantity")))
        unit_price = _as_int(item.get("unit_price", item.get("price")))
        if min_quantity < 1 or unit_price < 1:
            continue
        by_min_quantity[min_quantity] = unit_price

    tiers = [
        {"min_quantity": min_quantity, "unit_price": unit_price}
        for min_quantity, unit_price in by_min_quantity.items()
    ]
    tiers.sort(key=lambda tier: tier["min_quantity"])
    return tiers


def get_unit_price_vnd(product: Dict[str, Any], quantity: int) -> int:
    base_price = _as_int(product.get("price"))
    if quantity < 1:
        return base_price

    unit_price = base_price
    for tier in normalize_price_tiers(product.get("price_tiers")):
        if quantity >= tier["min_quantity"]:
            unit_price = tier["unit_price"]
        else:
            break
    return unit_price


def get_bonus_quantity(product: Dict[str, Any], purchased_quantity: int) -> int:
    if purchased_quantity < 1:
        return 0
    buy_quantity = _as_int(product.get("promo_buy_quantity"))
    bonus_quantity = _as_int(product.get("promo_bonus_quantity"))
    if buy_quantity < 1 or bonus_quantity < 1:
        return 0
    return (purchased_quantity // buy_quantity) * bonus_quantity


def get_required_stock(product: Dict[str, Any], purchased_quantity: int) -> int:
    if purchased_quantity < 1:
        return 0
    return purchased_quantity + get_bonus_quantity(product, purchased_quantity)


def get_total_price_vnd(product: Dict[str, Any], purchased_quantity: int) -> int:
    if purchased_quantity < 1:
        return 0
    unit_price = get_unit_price_vnd(product, purchased_quantity)
    return unit_price * purchased_quantity


def get_total_price_usdt(product: Dict[str, Any], purchased_quantity: int) -> float:
    if purchased_quantity < 1:
        return 0.0
    return _as_float(product.get("price_usdt")) * purchased_quantity


def get_max_quantity_by_stock(product: Dict[str, Any], stock: int) -> int:
    stock = max(0, _as_int(stock))
    if stock < 1:
        return 0

    left = 0
    right = stock
    while left < right:
        mid = (left + right + 1) // 2
        if get_required_stock(product, mid) <= stock:
            left = mid
        else:
            right = mid - 1
    return left


def get_max_affordable_quantity(
    product: Dict[str, Any],
    balance: float,
    stock: int,
    currency: str = "vnd",
) -> int:
    max_by_stock = get_max_quantity_by_stock(product, stock)
    if max_by_stock < 1:
        return 0

    current_max = 0
    if currency == "usdt":
        for quantity in range(1, max_by_stock + 1):
            if get_total_price_usdt(product, quantity) <= float(balance):
                current_max = quantity
        return current_max

    for quantity in range(1, max_by_stock + 1):
        if get_total_price_vnd(product, quantity) <= int(balance):
            current_max = quantity
    return current_max


def get_pricing_snapshot(product: Dict[str, Any], purchased_quantity: int, currency: str = "vnd") -> Dict[str, Any]:
    bought = max(0, _as_int(purchased_quantity))
    bonus = get_bonus_quantity(product, bought)
    delivered = bought + bonus
    if currency == "usdt":
        unit_price = _as_float(product.get("price_usdt"))
        total_price = get_total_price_usdt(product, bought)
    else:
        unit_price = get_unit_price_vnd(product, bought)
        total_price = get_total_price_vnd(product, bought)
    return {
        "purchased_quantity": bought,
        "bonus_quantity": bonus,
        "delivered_quantity": delivered,
        "unit_price": unit_price,
        "total_price": total_price,
    }
