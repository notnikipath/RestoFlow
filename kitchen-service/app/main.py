from __future__ import annotations

from datetime import UTC, datetime, timedelta
from statistics import mean
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException

from shared.restoflow_common import (
    KitchenStatus,
    KitchenStatusUpdateRequest,
    KitchenTicket,
    KitchenTicketCreateRequest,
    Role,
    Settings,
    build_audit_event,
    estimate_kitchen_ready_minutes,
    has_permission,
    parallel_order_plan,
)

settings = Settings(service_name="kitchen-service", service_port=8504)
app = FastAPI(title="RestoFlow Kitchen Service", version="1.0.0")

tickets: dict[str, KitchenTicket] = {}
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
            object_type="kitchen",
            object_id=object_id,
            details=details or {},
        ).model_dump(mode="json")
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.post("/kitchen/tickets")
async def create_ticket(request: KitchenTicketCreateRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "kitchen:update")
    queue_depth = len(
        [
            ticket
            for ticket in tickets.values()
            if ticket.status in {KitchenStatus.QUEUED, KitchenStatus.PREPARING}
        ]
    )
    workload = min(1.5, 0.45 + queue_depth * 0.08)
    estimate = estimate_kitchen_ready_minutes(len(request.items), workload_index=workload, priority=request.priority)
    ticket = KitchenTicket(
        ticket_id=str(uuid4()),
        order_id=request.order_id,
        table_id=request.table_id,
        items=request.items,
        priority=request.priority,
        status=KitchenStatus.QUEUED,
        estimated_ready_minutes=estimate,
        started_at=datetime.now(UTC),
        ready_at=datetime.now(UTC) + timedelta(minutes=estimate),
    )
    tickets[ticket.ticket_id] = ticket
    _audit(
        request.actor_id,
        request.actor_role,
        "kitchen.ticket.create",
        ticket.ticket_id,
        {"order_id": request.order_id},
    )
    return ticket.model_dump(mode="json")


@app.get("/kitchen/tickets")
async def list_tickets(status: KitchenStatus | None = None, order_id: str | None = None) -> dict[str, Any]:
    items = []
    for ticket in tickets.values():
        if status and ticket.status != status:
            continue
        if order_id and ticket.order_id != order_id:
            continue
        items.append(ticket.model_dump(mode="json"))
    items.sort(key=lambda item: item["started_at"])
    return {"items": items, "count": len(items)}


@app.get("/kitchen/tickets/{ticket_id}")
async def get_ticket(ticket_id: str) -> dict[str, Any]:
    ticket = tickets.get(ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    payload = ticket.model_dump(mode="json")
    payload["remaining_seconds"] = max(
        0,
        int((ticket.ready_at - datetime.now(UTC)).total_seconds()) if ticket.ready_at else 0,
    )
    return payload


@app.post("/kitchen/tickets/{ticket_id}/status")
async def update_status(ticket_id: str, request: KitchenStatusUpdateRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "kitchen:update")
    ticket = tickets.get(ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    ticket.status = request.status
    if request.status == KitchenStatus.PREPARING and ticket.ready_at is None:
        ticket.ready_at = datetime.now(UTC) + timedelta(minutes=ticket.estimated_ready_minutes)
    if request.status == KitchenStatus.READY:
        ticket.ready_at = datetime.now(UTC)
    _audit(request.actor_id, request.actor_role, "kitchen.ticket.status", ticket_id, {"status": request.status.value})
    return ticket.model_dump(mode="json")


@app.get("/kitchen/board")
async def kitchen_board() -> dict[str, Any]:
    board = {
        KitchenStatus.QUEUED.value: [],
        KitchenStatus.PREPARING.value: [],
        KitchenStatus.READY.value: [],
        KitchenStatus.DELIVERED.value: [],
    }
    for ticket in tickets.values():
        board[ticket.status.value].append(ticket.model_dump(mode="json"))
    return board


@app.get("/kitchen/timers")
async def timer_metrics() -> dict[str, Any]:
    estimates = [ticket.estimated_ready_minutes for ticket in tickets.values()]
    return {
        "tickets_total": len(tickets),
        "avg_estimated_ready_minutes": round(mean(estimates), 2) if estimates else 0.0,
        "max_estimated_ready_minutes": max(estimates) if estimates else 0,
        "ready_now": len([ticket for ticket in tickets.values() if ticket.status == KitchenStatus.READY]),
    }


@app.get("/kitchen/parallel-plan")
async def parallel_plan(pending_orders: int = 24, cooks: int = 4) -> dict[str, Any]:
    return parallel_order_plan(pending_orders, cooks)


@app.get("/kitchen/order/{order_id}")
async def get_order_ticket(order_id: str) -> dict[str, Any]:
    for ticket in tickets.values():
        if ticket.order_id == order_id:
            return ticket.model_dump(mode="json")
    raise HTTPException(status_code=404, detail="Order ticket not found")


@app.get("/audit")
async def audit(limit: int = 100, actor_role: Role = Role.ADMIN) -> dict[str, Any]:
    _assert_permission(actor_role, "audit:read")
    return {"items": audit_log[-limit:]}


# Seed ticket
seed = KitchenTicket(
    ticket_id="KITCHEN-DEMO",
    order_id="ORD-DEMO",
    table_id="T-102",
    items=[],
    priority=3,
    status=KitchenStatus.PREPARING,
    estimated_ready_minutes=12,
    started_at=datetime.now(UTC) - timedelta(minutes=4),
    ready_at=datetime.now(UTC) + timedelta(minutes=8),
)
tickets[seed.ticket_id] = seed
