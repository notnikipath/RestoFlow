from __future__ import annotations

from math import ceil

from .schemas import VenueType


def service_rate_for_venue(venue_type: VenueType) -> float:
    return {
        VenueType.RESTAURANT: 0.1,
        VenueType.CAFE: 0.08,
        VenueType.BAR: 0.1,
        VenueType.FASTFOOD: 0.0,
        VenueType.CANTEEN: 0.03,
    }[venue_type]


def estimate_kitchen_ready_minutes(item_count: int, workload_index: float = 0.6, priority: int = 3) -> int:
    base = max(6, item_count * 4)
    workload_penalty = round(base * max(workload_index, 0) * 0.45)
    priority_discount = max(0, (5 - priority) * 2)
    return max(4, base + workload_penalty - priority_discount)


def calculate_order_totals(
    venue_type: VenueType,
    items: list[dict[str, float | int]],
    tip: float = 0.0,
) -> dict[str, float]:
    subtotal = 0.0
    for item in items:
        quantity = int(item.get("quantity", 0))
        unit_price = float(item.get("unit_price", 0.0))
        subtotal += quantity * unit_price
    subtotal = round(subtotal, 2)
    service_charge = round(subtotal * service_rate_for_venue(venue_type), 2)
    total = round(subtotal + service_charge + max(tip, 0.0), 2)
    return {
        "subtotal": subtotal,
        "service_charge": service_charge,
        "tip": round(max(tip, 0.0), 2),
        "total": total,
    }


def split_bill_evenly(total: float, participants: list[str]) -> list[dict[str, float | str]]:
    if total <= 0 or not participants:
        return []
    share = round(total / len(participants), 2)
    parts: list[dict[str, float | str]] = []
    allocated = 0.0
    for index, payer in enumerate(participants):
        amount = share
        if index == len(participants) - 1:
            amount = round(total - allocated, 2)
        allocated += amount
        parts.append({"payer": payer, "amount": amount})
    return parts


def parallel_order_plan(pending_orders: int, cooks: int) -> dict[str, int]:
    workers = max(1, min(16, cooks * 2))
    batch_size = max(1, ceil(max(pending_orders, 1) / workers))
    return {
        "pending_orders": pending_orders,
        "cooks": cooks,
        "workers": workers,
        "batch_size": batch_size,
    }


def estimate_staffing_requirements(expected_guests: int, avg_dishes_per_guest: float = 1.8) -> dict[str, int]:
    waiters = max(1, ceil(expected_guests / 14))
    chefs = max(1, ceil((expected_guests * avg_dishes_per_guest) / 30))
    hostesses = 1 if expected_guests < 80 else 2
    return {
        "expected_guests": expected_guests,
        "waiters": waiters,
        "chefs": chefs,
        "hostesses": hostesses,
    }


def estimate_order_processing_seconds(
    items_count: int,
    parallel_workers: int,
    queue_delay_seconds: float = 4.0,
) -> float:
    kitchen = max(8.0, items_count * 2.8)
    parallel_gain = min(0.45, max(parallel_workers - 1, 0) * 0.06)
    total = kitchen * (1 - parallel_gain) + queue_delay_seconds
    return round(max(6.0, total), 2)
