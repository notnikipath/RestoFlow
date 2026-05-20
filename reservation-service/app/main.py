from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from shared.restoflow_common import (
    HallLayout,
    ReservationCreateRequest,
    ReservationRecord,
    ReservationStatus,
    Role,
    SeatingAssignmentRequest,
    Settings,
    TablePosition,
    TableStatus,
    VenueType,
    build_audit_event,
    has_permission,
)
from shared.restoflow_common.schemas import RestaurantTable

settings = Settings(service_name="reservation-service", service_port=8501)
app = FastAPI(title="RestoFlow Reservation Service", version="1.0.0")


class ChatbotReservationRequest(BaseModel):
    venue_type: VenueType
    guest_name: str
    phone: str
    party_size: int
    reservation_time: datetime
    notes: str = ""


ChatbotReservationRequest.model_rebuild()


def _table(table_id: str, hall_id: str, label: str, seats: int, x: int, y: int) -> RestaurantTable:
    return RestaurantTable(
        table_id=table_id,
        hall_id=hall_id,
        label=label,
        seats=seats,
        status=TableStatus.AVAILABLE,
        position=TablePosition(x=x, y=y),
    )


halls: dict[str, HallLayout] = {
    "HALL-RESTO": HallLayout(
        hall_id="HALL-RESTO",
        hall_name="Main Dining",
        venue_type=VenueType.RESTAURANT,
        width=24,
        height=14,
        tables=[
            _table("T-101", "HALL-RESTO", "R1", 2, 2, 2),
            _table("T-102", "HALL-RESTO", "R2", 4, 6, 2),
            _table("T-103", "HALL-RESTO", "R3", 4, 10, 2),
            _table("T-104", "HALL-RESTO", "R4", 6, 14, 3),
            _table("T-105", "HALL-RESTO", "R5", 2, 18, 4),
            _table("T-106", "HALL-RESTO", "R6", 8, 7, 8),
        ],
    ),
    "HALL-CAFE": HallLayout(
        hall_id="HALL-CAFE",
        hall_name="Cafe Floor",
        venue_type=VenueType.CAFE,
        width=18,
        height=10,
        tables=[
            _table("T-201", "HALL-CAFE", "C1", 2, 2, 2),
            _table("T-202", "HALL-CAFE", "C2", 2, 5, 2),
            _table("T-203", "HALL-CAFE", "C3", 4, 8, 4),
            _table("T-204", "HALL-CAFE", "C4", 4, 12, 4),
            _table("T-205", "HALL-CAFE", "C5", 6, 15, 6),
        ],
    ),
    "HALL-BAR": HallLayout(
        hall_id="HALL-BAR",
        hall_name="Bar Lounge",
        venue_type=VenueType.BAR,
        width=20,
        height=10,
        tables=[
            _table("T-301", "HALL-BAR", "B1", 2, 2, 2),
            _table("T-302", "HALL-BAR", "B2", 2, 5, 2),
            _table("T-303", "HALL-BAR", "B3", 4, 9, 3),
            _table("T-304", "HALL-BAR", "B4", 4, 13, 3),
            _table("T-305", "HALL-BAR", "B5", 8, 16, 6),
        ],
    ),
    "HALL-FAST": HallLayout(
        hall_id="HALL-FAST",
        hall_name="Fastfood Hall",
        venue_type=VenueType.FASTFOOD,
        width=16,
        height=8,
        tables=[
            _table("T-401", "HALL-FAST", "F1", 2, 2, 1),
            _table("T-402", "HALL-FAST", "F2", 2, 4, 1),
            _table("T-403", "HALL-FAST", "F3", 4, 7, 2),
            _table("T-404", "HALL-FAST", "F4", 4, 11, 2),
            _table("T-405", "HALL-FAST", "F5", 6, 14, 4),
        ],
    ),
    "HALL-CANT": HallLayout(
        hall_id="HALL-CANT",
        hall_name="Canteen Line",
        venue_type=VenueType.CANTEEN,
        width=22,
        height=11,
        tables=[
            _table("T-501", "HALL-CANT", "S1", 4, 3, 2),
            _table("T-502", "HALL-CANT", "S2", 4, 7, 2),
            _table("T-503", "HALL-CANT", "S3", 6, 11, 3),
            _table("T-504", "HALL-CANT", "S4", 6, 15, 3),
            _table("T-505", "HALL-CANT", "S5", 8, 18, 5),
        ],
    ),
}


def _table_index() -> dict[str, RestaurantTable]:
    return {
        table.table_id: table
        for hall in halls.values()
        for table in hall.tables
    }


def _venue_hall_ids(venue_type: VenueType) -> set[str]:
    return {hall.hall_id for hall in halls.values() if hall.venue_type == venue_type}


reservations: dict[str, ReservationRecord] = {}
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
            object_type="reservation",
            object_id=object_id,
            details=details or {},
        ).model_dump(mode="json")
    )


def _find_available_table(venue_type: VenueType, party_size: int, hall_id: str | None = None) -> RestaurantTable | None:
    table_map = _table_index()
    candidate_halls = _venue_hall_ids(venue_type)
    if hall_id:
        candidate_halls = {hall_id}
    candidates = [
        table
        for table in table_map.values()
        if table.hall_id in candidate_halls and table.status == TableStatus.AVAILABLE and table.seats >= party_size
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda table: (table.seats - party_size, table.seats))
    return candidates[0]


def _create_reservation(request: ReservationCreateRequest) -> ReservationRecord:
    if request.actor_role != Role.GUEST:
        _assert_permission(request.actor_role, "reservation:create")
    table = _find_available_table(request.venue_type, request.party_size, request.preferred_hall_id)
    reservation = ReservationRecord(
        reservation_id=str(uuid4()),
        venue_type=request.venue_type,
        guest_name=request.guest_name,
        phone=request.phone,
        party_size=request.party_size,
        reservation_time=request.reservation_time,
        duration_minutes=request.duration_minutes,
        notes=request.notes,
        status=ReservationStatus.CONFIRMED if table else ReservationStatus.PENDING,
        table_id=table.table_id if table else None,
    )
    if table:
        table.status = TableStatus.RESERVED
    reservations[reservation.reservation_id] = reservation
    _audit(request.actor_id, request.actor_role, "reservation.create", reservation.reservation_id)
    return reservation


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.get("/halls/schema")
async def hall_schema(venue_type: VenueType | None = None) -> dict[str, Any]:
    items = []
    for hall in halls.values():
        if venue_type and hall.venue_type != venue_type:
            continue
        items.append(hall.model_dump(mode="json"))
    return {"items": items, "count": len(items)}


@app.get("/tables")
async def list_tables(venue_type: VenueType | None = None, status: TableStatus | None = None) -> dict[str, Any]:
    items = []
    for hall in halls.values():
        if venue_type and hall.venue_type != venue_type:
            continue
        for table in hall.tables:
            if status and table.status != status:
                continue
            payload = table.model_dump(mode="json")
            payload["venue_type"] = hall.venue_type.value
            payload["hall_name"] = hall.hall_name
            items.append(payload)
    return {"items": items, "count": len(items)}


@app.post("/reservations")
async def create_reservation(request: ReservationCreateRequest) -> dict[str, Any]:
    reservation = _create_reservation(request)
    payload = reservation.model_dump(mode="json")
    payload["requires_manual_assignment"] = reservation.table_id is None
    return payload


@app.get("/reservations")
async def list_reservations(
    status: ReservationStatus | None = None,
    venue_type: VenueType | None = None,
    date: str | None = None,
) -> dict[str, Any]:
    items = []
    for reservation in reservations.values():
        if status and reservation.status != status:
            continue
        if venue_type and reservation.venue_type != venue_type:
            continue
        if date and reservation.reservation_time.date().isoformat() != date:
            continue
        items.append(reservation.model_dump(mode="json"))
    items.sort(key=lambda item: item["reservation_time"])
    return {"items": items, "count": len(items)}


@app.post("/seating/assign")
async def assign_table(request: SeatingAssignmentRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "seating:update")
    reservation = reservations.get(request.reservation_id)
    if reservation is None:
        raise HTTPException(status_code=404, detail="Reservation not found")
    table = _table_index().get(request.table_id)
    if table is None:
        raise HTTPException(status_code=404, detail="Table not found")
    if table.status not in {TableStatus.AVAILABLE, TableStatus.RESERVED}:
        raise HTTPException(status_code=409, detail="Table is not available")
    if table.seats < reservation.party_size:
        raise HTTPException(status_code=409, detail="Table capacity is insufficient")

    if reservation.table_id:
        previous = _table_index().get(reservation.table_id)
        if previous and previous.table_id != table.table_id:
            previous.status = TableStatus.AVAILABLE

    reservation.table_id = table.table_id
    reservation.status = ReservationStatus.CONFIRMED
    table.status = TableStatus.RESERVED
    _audit(request.actor_id, request.actor_role, "reservation.assign_table", reservation.reservation_id)
    return reservation.model_dump(mode="json")


@app.post("/reservations/{reservation_id}/seat")
async def seat_guest(reservation_id: str, actor_id: str, actor_role: Role) -> dict[str, Any]:
    _assert_permission(actor_role, "seating:update")
    reservation = reservations.get(reservation_id)
    if reservation is None:
        raise HTTPException(status_code=404, detail="Reservation not found")
    if not reservation.table_id:
        raise HTTPException(status_code=409, detail="Reservation has no assigned table")

    table = _table_index()[reservation.table_id]
    reservation.status = ReservationStatus.SEATED
    table.status = TableStatus.OCCUPIED
    _audit(actor_id, actor_role, "reservation.seat", reservation_id)
    return reservation.model_dump(mode="json")


@app.post("/reservations/{reservation_id}/complete")
async def complete_visit(reservation_id: str, actor_id: str, actor_role: Role) -> dict[str, Any]:
    _assert_permission(actor_role, "reservation:update")
    reservation = reservations.get(reservation_id)
    if reservation is None:
        raise HTTPException(status_code=404, detail="Reservation not found")
    reservation.status = ReservationStatus.COMPLETED
    if reservation.table_id:
        _table_index()[reservation.table_id].status = TableStatus.CLEANING
    _audit(actor_id, actor_role, "reservation.complete", reservation_id)
    return reservation.model_dump(mode="json")


@app.post("/reservations/{reservation_id}/cancel")
async def cancel_reservation(reservation_id: str, actor_id: str, actor_role: Role) -> dict[str, Any]:
    _assert_permission(actor_role, "reservation:update")
    reservation = reservations.get(reservation_id)
    if reservation is None:
        raise HTTPException(status_code=404, detail="Reservation not found")
    reservation.status = ReservationStatus.CANCELLED
    if reservation.table_id:
        _table_index()[reservation.table_id].status = TableStatus.AVAILABLE
    _audit(actor_id, actor_role, "reservation.cancel", reservation_id)
    return reservation.model_dump(mode="json")


@app.post("/chatbot/reserve")
async def chatbot_reserve(request: ChatbotReservationRequest) -> dict[str, Any]:
    reservation = _create_reservation(
        ReservationCreateRequest(
            venue_type=request.venue_type,
            guest_name=request.guest_name,
            phone=request.phone,
            party_size=request.party_size,
            reservation_time=request.reservation_time,
            duration_minutes=120,
            notes=request.notes,
            actor_id="chatbot",
            actor_role=Role.GUEST,
        )
    )
    return {
        "message": (
            f"Бронь создана на {reservation.reservation_time.isoformat()} для {reservation.guest_name}. "
            f"Стол: {reservation.table_id or 'подбор вручную'}"
        ),
        "reservation": reservation.model_dump(mode="json"),
    }


@app.get("/load/hourly")
async def reservation_load(date: str) -> dict[str, Any]:
    buckets = [0] * 24
    for reservation in reservations.values():
        if reservation.reservation_time.date().isoformat() != date:
            continue
        if reservation.status in {ReservationStatus.CANCELLED, ReservationStatus.NO_SHOW}:
            continue
        buckets[reservation.reservation_time.hour] += reservation.party_size
    return {"date": date, "guests_by_hour": buckets}


@app.post("/maintenance/release-cleaning")
async def release_cleaning(actor_id: str, actor_role: Role) -> dict[str, Any]:
    _assert_permission(actor_role, "reservation:update")
    released = 0
    for table in _table_index().values():
        if table.status == TableStatus.CLEANING:
            table.status = TableStatus.AVAILABLE
            released += 1
    _audit(actor_id, actor_role, "tables.release_cleaning", str(released), {"released": released})
    return {"released": released}


@app.get("/audit")
async def audit(limit: int = 100, actor_role: Role = Role.ADMIN) -> dict[str, Any]:
    _assert_permission(actor_role, "audit:read")
    return {"items": audit_log[-limit:]}


# Seed one active reservation for demo workflow
_seed = ReservationCreateRequest(
    venue_type=VenueType.RESTAURANT,
    guest_name="Demo Guest",
    phone="+79990000000",
    party_size=2,
    reservation_time=datetime.now(UTC) + timedelta(hours=2),
    actor_id="seed",
    actor_role=Role.ADMIN,
)
_create_reservation(_seed)
