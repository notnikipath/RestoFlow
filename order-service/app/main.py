from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException

from shared.restoflow_common import (
    OrderCreateRequest,
    OrderItem,
    OrderRecord,
    OrderStatus,
    OrderStatusUpdateRequest,
    PaymentMethod,
    PaymentStatus,
    Role,
    Settings,
    SplitBillPart,
    SplitBillRequest,
    SplitBillResult,
    VenueType,
    build_audit_event,
    calculate_order_totals,
    has_permission,
    split_bill_evenly,
)

settings = Settings(service_name="order-service", service_port=8503)
app = FastAPI(title="RestoFlow Order Service", version="1.0.0")

menu_snapshot: dict[str, dict[str, Any]] = {
    "DISH-BRUS": {"name": "Bruschetta", "price": 420.0},
    "DISH-SALMON": {"name": "Grilled Salmon", "price": 1280.0},
    "DISH-OKRO": {"name": "Okroshka", "price": 520.0},
    "DISH-PUMPKIN": {"name": "Pumpkin Cream Soup", "price": 560.0},
    "DISH-APPLEPIE": {"name": "Apple Pie", "price": 460.0},
    "DISH-MULLED": {"name": "Mulled Wine", "price": 490.0},
    "DISH-BURGER": {"name": "Classic Burger", "price": 510.0},
}

orders: dict[str, OrderRecord] = {}
payments: dict[str, list[SplitBillPart]] = {}
audit_log: list[dict[str, Any]] = []


def _assert_permission(role: Role, action: str) -> None:
    if not has_permission(role, action):
        raise HTTPException(status_code=403, detail=f"Role {role.value} cannot perform {action}")


def _audit(actor_id: str, actor_role: Role, action: str, object_id: str, details: dict[str, Any] | None = None) -> None:
    audit_log.append(
        build_audit_event(
            actor_id=actor_id,
            actor_role=actor_role,
            action=action,
            object_type="order",
            object_id=object_id,
            details=details or {},
        ).model_dump(mode="json")
    )


def _build_order_items(request: OrderCreateRequest) -> list[OrderItem]:
    if not request.items:
        raise HTTPException(status_code=422, detail="Order must contain at least one item")
    items: list[OrderItem] = []
    for requested in request.items:
        dish = menu_snapshot.get(requested.dish_id)
        if dish is None:
            raise HTTPException(status_code=404, detail=f"Dish {requested.dish_id} not found")
        unit_price = float(dish["price"])
        line_total = round(unit_price * requested.quantity, 2)
        items.append(
            OrderItem(
                dish_id=requested.dish_id,
                dish_name=str(dish["name"]),
                quantity=requested.quantity,
                unit_price=unit_price,
                line_total=line_total,
                notes=requested.notes,
            )
        )
    return items


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.get("/menu/snapshot")
async def menu_snapshot_view() -> dict[str, Any]:
    return {"items": menu_snapshot, "count": len(menu_snapshot)}


@app.get("/orders")
async def list_orders(
    status: OrderStatus | None = None,
    venue_type: VenueType | None = None,
    waiter_id: str | None = None,
) -> dict[str, Any]:
    items = []
    for order in orders.values():
        if status and order.status != status:
            continue
        if venue_type and order.venue_type != venue_type:
            continue
        if waiter_id and order.waiter_id != waiter_id:
            continue
        items.append(order.model_dump(mode="json"))
    items.sort(key=lambda item: item["created_at"], reverse=True)
    return {"items": items, "count": len(items)}


@app.get("/orders/{order_id}")
async def get_order(order_id: str, actor_role: Role = Role.WAITER) -> dict[str, Any]:
    _assert_permission(actor_role, "order:read")
    order = orders.get(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    payload = order.model_dump(mode="json")
    payload["payments"] = [part.model_dump(mode="json") for part in payments.get(order_id, [])]
    return payload


@app.post("/orders")
async def create_order(request: OrderCreateRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "order:create")
    items = _build_order_items(request)
    totals = calculate_order_totals(
        request.venue_type,
        [
            {
                "quantity": item.quantity,
                "unit_price": item.unit_price,
            }
            for item in items
        ],
        tip=request.tip,
    )
    order = OrderRecord(
        order_id=str(uuid4()),
        venue_type=request.venue_type,
        table_id=request.table_id,
        waiter_id=request.waiter_id,
        guest_count=request.guest_count,
        items=items,
        subtotal=totals["subtotal"],
        service_charge=totals["service_charge"],
        tip=totals["tip"],
        total=totals["total"],
        status=OrderStatus.CREATED,
        payment_status=PaymentStatus.UNPAID,
    )
    orders[order.order_id] = order
    _audit(request.waiter_id, request.actor_role, "order.create", order.order_id)
    return order.model_dump(mode="json")


@app.post("/orders/{order_id}/status")
async def update_order_status(order_id: str, request: OrderStatusUpdateRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "order:update")
    order = orders.get(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    order.status = request.status
    _audit(request.actor_id, request.actor_role, "order.status", order_id, {"status": request.status.value})
    return order.model_dump(mode="json")


@app.post("/orders/{order_id}/split-bill")
async def split_bill(order_id: str, request: SplitBillRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "payment:split")
    order = orders.get(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    if not request.parts:
        raise HTTPException(status_code=422, detail="Split parts are required")
    paid = round(sum(part.amount for part in request.parts), 2)
    debt = round(max(order.total - paid, 0.0), 2)
    order.payment_status = PaymentStatus.PAID if debt == 0 else PaymentStatus.PARTIAL
    payments[order_id] = request.parts
    _audit(request.actor_id, request.actor_role, "order.split_bill", order_id, {"paid": paid, "debt": debt})
    return SplitBillResult(
        order_id=order_id,
        total=order.total,
        paid=paid,
        debt=debt,
        status=order.payment_status,
        parts=request.parts,
    ).model_dump(mode="json")


@app.post("/orders/{order_id}/split-even")
async def split_even(order_id: str, participants: str, actor_id: str, actor_role: Role) -> dict[str, Any]:
    _assert_permission(actor_role, "payment:split")
    order = orders.get(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    names = [part.strip() for part in participants.split(",") if part.strip()]
    parts_raw = split_bill_evenly(order.total, names)
    parts = [
        SplitBillPart(
            payer=str(item["payer"]),
            amount=float(item["amount"]),
            method=PaymentMethod.CARD,
        )
        for item in parts_raw
    ]
    if not parts:
        raise HTTPException(status_code=422, detail="Participants are required")
    payments[order_id] = parts
    order.payment_status = PaymentStatus.PAID
    _audit(actor_id, actor_role, "order.split_even", order_id, {"participants": names})
    return SplitBillResult(
        order_id=order_id,
        total=order.total,
        paid=order.total,
        debt=0.0,
        status=PaymentStatus.PAID,
        parts=parts,
    ).model_dump(mode="json")


@app.get("/orders/{order_id}/receipt")
async def receipt(order_id: str) -> dict[str, Any]:
    order = orders.get(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return {
        "order_id": order.order_id,
        "table_id": order.table_id,
        "waiter_id": order.waiter_id,
        "items": [item.model_dump(mode="json") for item in order.items],
        "subtotal": order.subtotal,
        "service_charge": order.service_charge,
        "tip": order.tip,
        "total": order.total,
        "payment_status": order.payment_status.value,
    }


@app.get("/audit")
async def audit(limit: int = 100, actor_role: Role = Role.ADMIN) -> dict[str, Any]:
    _assert_permission(actor_role, "audit:read")
    return {"items": audit_log[-limit:]}


# Seed one order
seed_order = OrderCreateRequest(
    venue_type=VenueType.RESTAURANT,
    table_id="T-102",
    waiter_id="WTR-001",
    guest_count=2,
    items=[{"dish_id": "DISH-BRUS", "quantity": 1}, {"dish_id": "DISH-SALMON", "quantity": 1}],
    tip=150,
    actor_role=Role.ADMIN,
)
create_payload = _build_order_items(seed_order)
seed_totals = calculate_order_totals(
    seed_order.venue_type,
    [{"quantity": item.quantity, "unit_price": item.unit_price} for item in create_payload],
    tip=seed_order.tip,
)
seed = OrderRecord(
    order_id="ORD-DEMO",
    venue_type=seed_order.venue_type,
    table_id=seed_order.table_id,
    waiter_id=seed_order.waiter_id,
    guest_count=seed_order.guest_count,
    items=create_payload,
    subtotal=seed_totals["subtotal"],
    service_charge=seed_totals["service_charge"],
    tip=seed_totals["tip"],
    total=seed_totals["total"],
)
orders[seed.order_id] = seed
