from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from shared.restoflow_common import (
    NotificationChannel,
    NotificationRequest,
    OrderReadyNotificationRequest,
    Role,
    Settings,
    Severity,
    has_permission,
)

settings = Settings(service_name="notification-service", service_port=8508)
app = FastAPI(title="RestoFlow Notification Service", version="1.0.0")

messages: list[dict[str, Any]] = []


class ReservationNotificationRequest(BaseModel):
    reservation_id: str
    guest_name: str
    phone: str
    reservation_time: str
    table_id: str | None = None
    actor_role: Role


ReservationNotificationRequest.model_rebuild()


def _assert_permission(role: Role, action: str) -> None:
    if not has_permission(role, action):
        raise HTTPException(status_code=403, detail=f"Role {role.value} cannot perform {action}")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.post("/notify/send")
async def send(request: NotificationRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "notification:send")
    payload = request.model_dump(mode="json")
    payload["status"] = "queued"
    payload["created_at"] = datetime.now(UTC).isoformat()
    messages.append(payload)
    return payload


@app.post("/notify/order-ready")
async def order_ready(request: OrderReadyNotificationRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "notification:send")
    payload = {
        "channel": NotificationChannel.PUSH.value,
        "recipient": request.waiter_id,
        "subject": f"Order {request.order_id} ready",
        "body": f"Table {request.table_id}: pick up order {request.order_id} from the kitchen.",
        "severity": Severity.INFO.value,
        "status": "queued",
        "created_at": datetime.now(UTC).isoformat(),
    }
    messages.append(payload)
    return payload


@app.post("/notify/reservation-confirmed")
async def reservation_confirmed(request: ReservationNotificationRequest) -> dict[str, Any]:
    if request.actor_role not in {Role.HOSTESS, Role.MANAGER, Role.ADMIN}:
        raise HTTPException(status_code=403, detail="Forbidden")
    payload = {
        "channel": NotificationChannel.SMS.value,
        "recipient": request.phone,
        "subject": "Reservation confirmed",
        "body": (
            f"Hello, {request.guest_name}. Reservation {request.reservation_id} confirmed for "
            f"{request.reservation_time}. Table: {request.table_id or 'assigned on arrival'}."
        ),
        "severity": Severity.INFO.value,
        "status": "queued",
        "created_at": datetime.now(UTC).isoformat(),
    }
    messages.append(payload)
    return payload


@app.get("/notify/history")
async def history(channel: NotificationChannel | None = None) -> dict[str, Any]:
    items = [message for message in messages if not channel or message.get("channel") == channel.value]
    return {"items": items, "count": len(items)}


@app.get("/notify/templates")
async def templates() -> dict[str, Any]:
    return {
        "order_ready": "Table {table_id}: pick up order {order_id} from the kitchen.",
        "reservation_confirmed": "Reservation {reservation_id} confirmed for {reservation_time}.",
    }


# Seed one notification
messages.append(
    {
        "channel": NotificationChannel.PUSH.value,
        "recipient": "WTR-001",
        "subject": "Order ORD-DEMO ready",
        "body": "Table T-102: pick up order ORD-DEMO from the kitchen.",
        "severity": Severity.INFO.value,
        "status": "queued",
        "created_at": datetime.now(UTC).isoformat(),
    }
)
