from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from shared.restoflow_common import (
    CreateOrderWorkflowResult,
    OrderItemRequest,
    Role,
    Settings,
    VenueType,
    estimate_order_processing_seconds,
    sign_token,
    verify_token,
)


class GatewaySettings(BaseSettings):
    service_name: str = "api-gateway"
    service_port: int = 8500

    reservation_service_url: str = "http://reservation-service:8501"
    menu_service_url: str = "http://menu-service:8502"
    order_service_url: str = "http://order-service:8503"
    kitchen_service_url: str = "http://kitchen-service:8504"
    inventory_service_url: str = "http://inventory-service:8505"
    staff_service_url: str = "http://staff-service:8506"
    analytics_service_url: str = "http://analytics-service:8507"
    notification_service_url: str = "http://notification-service:8508"

    jwt_secret: str = Settings().jwt_secret
    token_exp_minutes: int = 240

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = GatewaySettings()
app = FastAPI(title="RestoFlow API Gateway", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5177",
        "http://127.0.0.1:5177",
        "http://localhost:5176",
        "http://127.0.0.1:5176",
        "http://localhost:32022",
        "http://127.0.0.1:32022",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AuthRequest(BaseModel):
    user_id: str
    role: Role


class CreateOrderWorkflowRequest(BaseModel):
    venue_type: VenueType
    table_id: str
    waiter_id: str
    guest_count: int = Field(gt=0, le=50)
    items: list[OrderItemRequest]
    tip: float = Field(default=0.0, ge=0.0)
    actor_role: Role = Role.WAITER
    notify_when_ready: bool = True
    inventory_async: bool = False


class CloseOrderWorkflowRequest(BaseModel):
    order_id: str
    actor_id: str
    actor_role: Role


class ReservationWorkflowRequest(BaseModel):
    venue_type: VenueType
    guest_name: str
    phone: str
    party_size: int = Field(gt=0, le=30)
    reservation_time: str
    notes: str = ""


AuthRequest.model_rebuild()
CreateOrderWorkflowRequest.model_rebuild()
CloseOrderWorkflowRequest.model_rebuild()
ReservationWorkflowRequest.model_rebuild()


async def _post_json(
    client: httpx.AsyncClient,
    url: str,
    payload: dict[str, Any],
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    response = await client.post(url, json=payload, params=params)
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    return response.json()


async def _get_json(client: httpx.AsyncClient, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    response = await client.get(url, params=params)
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    return response.json()


def _service_urls() -> dict[str, str]:
    return {
        "reservation": settings.reservation_service_url,
        "menu": settings.menu_service_url,
        "order": settings.order_service_url,
        "kitchen": settings.kitchen_service_url,
        "inventory": settings.inventory_service_url,
        "staff": settings.staff_service_url,
        "analytics": settings.analytics_service_url,
        "notification": settings.notification_service_url,
    }


async def _notify_when_ready(order_id: str, waiter_id: str, table_id: str) -> None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        for _ in range(24):
            await asyncio.sleep(5)
            try:
                ticket = await _get_json(client, f"{settings.kitchen_service_url}/kitchen/order/{order_id}")
                if ticket.get("status") == "ready":
                    await _post_json(
                        client,
                        f"{settings.notification_service_url}/notify/order-ready",
                        {
                            "order_id": order_id,
                            "waiter_id": waiter_id,
                            "table_id": table_id,
                            "actor_role": Role.MANAGER.value,
                        },
                    )
                    break
            except Exception:
                continue


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.post("/auth/token")
async def issue_token(request: AuthRequest) -> dict[str, str]:
    token = sign_token(
        {"sub": request.user_id, "role": request.role.value},
        settings.jwt_secret,
        exp_minutes=settings.token_exp_minutes,
    )
    return {"access_token": token, "token_type": "Bearer"}


@app.post("/auth/verify")
async def verify_auth(token: str) -> dict[str, Any]:
    payload = verify_token(token, settings.jwt_secret)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload


@app.get("/services/health")
async def service_health() -> dict[str, Any]:
    statuses: dict[str, Any] = {}
    async with httpx.AsyncClient(timeout=10.0) as client:
        for name, base_url in _service_urls().items():
            try:
                statuses[name] = await _get_json(client, f"{base_url}/health")
            except Exception as exc:
                statuses[name] = {"status": "error", "detail": str(exc)}
    return statuses


@app.post("/workflow/create-reservation")
async def create_reservation_workflow(request: ReservationWorkflowRequest) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=15.0) as client:
        reservation = await _post_json(
            client,
            f"{settings.reservation_service_url}/reservations",
            {
                "venue_type": request.venue_type.value,
                "guest_name": request.guest_name,
                "phone": request.phone,
                "party_size": request.party_size,
                "reservation_time": request.reservation_time,
                "duration_minutes": 120,
                "notes": request.notes,
                "actor_id": "gateway",
                "actor_role": Role.HOSTESS.value,
            },
        )

        notification = await _post_json(
            client,
            f"{settings.notification_service_url}/notify/reservation-confirmed",
            {
                "reservation_id": reservation["reservation_id"],
                "guest_name": reservation["guest_name"],
                "phone": reservation["phone"],
                "reservation_time": reservation["reservation_time"],
                "table_id": reservation.get("table_id"),
                "actor_role": Role.HOSTESS.value,
            },
        )

    return {"reservation": reservation, "notification": notification}


@app.post("/workflow/create-order")
async def create_order_workflow(request: CreateOrderWorkflowRequest) -> dict[str, Any]:
    started = time.perf_counter()

    async with httpx.AsyncClient(timeout=25.0) as client:
        order = await _post_json(
            client,
            f"{settings.order_service_url}/orders",
            {
                "venue_type": request.venue_type.value,
                "table_id": request.table_id,
                "waiter_id": request.waiter_id,
                "guest_count": request.guest_count,
                "items": [item.model_dump(mode="json") for item in request.items],
                "tip": request.tip,
                "actor_role": request.actor_role.value,
            },
        )

        kitchen_ticket = await _post_json(
            client,
            f"{settings.kitchen_service_url}/kitchen/tickets",
            {
                "order_id": order["order_id"],
                "table_id": request.table_id,
                "items": order["items"],
                "priority": 2 if request.guest_count >= 6 else 3,
                "actor_id": "gateway",
                "actor_role": Role.MANAGER.value,
            },
        )

        inventory = await _post_json(
            client,
            f"{settings.inventory_service_url}/inventory/deduct-batch",
            {
                "order_id": order["order_id"],
                "items": [
                    {
                        "dish_id": item.dish_id,
                        "quantity": item.quantity,
                    }
                    for item in request.items
                ],
                "actor_id": "gateway",
                "actor_role": Role.MANAGER.value,
            },
            params={"async_mode": str(request.inventory_async).lower()},
        )

        processing_seconds = estimate_order_processing_seconds(
            items_count=sum(item.quantity for item in request.items),
            parallel_workers=4,
        )

        await _post_json(
            client,
            f"{settings.analytics_service_url}/analytics/ingest/order",
            {
                "order_id": order["order_id"],
                "venue_type": request.venue_type.value,
                "total": order["total"],
                "processing_seconds": processing_seconds,
                "dish_quantities": [
                    {
                        "dish_id": item.dish_id,
                        "quantity": item.quantity,
                    }
                    for item in request.items
                ],
            },
        )

        notifications: list[dict[str, Any]] = []
        notifications.append(
            await _post_json(
                client,
                f"{settings.notification_service_url}/notify/send",
                {
                    "channel": "push",
                    "recipient": request.waiter_id,
                    "subject": f"Order {order['order_id']} accepted",
                    "body": f"Order sent to kitchen for table {request.table_id}.",
                    "severity": "info",
                    "actor_role": Role.MANAGER.value,
                },
            )
        )

    elapsed = round(time.perf_counter() - started, 2)

    if request.notify_when_ready:
        asyncio.create_task(_notify_when_ready(order["order_id"], request.waiter_id, request.table_id))

    result = CreateOrderWorkflowResult(
        order=order,
        kitchen_ticket=kitchen_ticket,
        inventory=inventory,
        notifications=notifications,
        processing_seconds=max(processing_seconds, elapsed),
    )
    return result.model_dump(mode="json")


@app.post("/workflow/close-order")
async def close_order_workflow(request: CloseOrderWorkflowRequest) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=15.0) as client:
        order = await _post_json(
            client,
            f"{settings.order_service_url}/orders/{request.order_id}/status",
            {
                "status": "closed",
                "actor_id": request.actor_id,
                "actor_role": request.actor_role.value,
            },
        )

        ticket = await _get_json(client, f"{settings.kitchen_service_url}/kitchen/order/{request.order_id}")
        if ticket.get("status") != "delivered":
            await _post_json(
                client,
                f"{settings.kitchen_service_url}/kitchen/tickets/{ticket['ticket_id']}/status",
                {
                    "status": "delivered",
                    "actor_id": request.actor_id,
                    "actor_role": Role.CHEF.value,
                },
            )

        notification = await _post_json(
            client,
            f"{settings.notification_service_url}/notify/send",
            {
                "channel": "email",
                "recipient": "finance@restoflow.local",
                "subject": f"Order {request.order_id} closed",
                "body": f"Order {request.order_id} has been closed and ready for end-of-day report.",
                "severity": "info",
                "actor_role": Role.MANAGER.value,
            },
        )

    return {"order": order, "notification": notification}


@app.get("/dashboard/overview")
async def dashboard_overview(date: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=20.0) as client:
        reservations = await _get_json(
            client,
            f"{settings.reservation_service_url}/reservations",
            {"date": date},
        )
        menu = await _get_json(client, f"{settings.menu_service_url}/dishes")
        orders = await _get_json(client, f"{settings.order_service_url}/orders")
        kitchen = await _get_json(client, f"{settings.kitchen_service_url}/kitchen/board")
        low_stock = await _get_json(client, f"{settings.inventory_service_url}/ingredients", {"low_only": True})
        staff = await _get_json(client, f"{settings.staff_service_url}/staff")
        revenue = await _get_json(client, f"{settings.analytics_service_url}/analytics/revenue")
        quality = await _get_json(client, f"{settings.analytics_service_url}/analytics/quality-targets")

    return {
        "date": date,
        "reservations": reservations,
        "menu": {"count": menu.get("count", 0)},
        "orders": orders,
        "kitchen": kitchen,
        "low_stock": low_stock,
        "staff": {"count": staff.get("count", 0)},
        "revenue": revenue,
        "quality": quality,
    }
