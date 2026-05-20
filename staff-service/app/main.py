from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException

from shared.restoflow_common import (
    PayrollRecord,
    Role,
    Settings,
    ShiftCreateRequest,
    ShiftRecord,
    StaffMember,
    TipRecord,
    build_audit_event,
    estimate_staffing_requirements,
    has_permission,
)

settings = Settings(service_name="staff-service", service_port=8506)
app = FastAPI(title="RestoFlow Staff Service", version="1.0.0")

staff: dict[str, StaffMember] = {
    "WTR-001": StaffMember(staff_id="WTR-001", full_name="Irina Petrova", role=Role.WAITER, hourly_rate=520),
    "WTR-002": StaffMember(staff_id="WTR-002", full_name="Alex Smirnov", role=Role.WAITER, hourly_rate=510),
    "CHF-001": StaffMember(staff_id="CHF-001", full_name="Maksim Sokolov", role=Role.CHEF, hourly_rate=690),
    "HST-001": StaffMember(staff_id="HST-001", full_name="Nina Volkova", role=Role.HOSTESS, hourly_rate=450),
    "MGR-001": StaffMember(staff_id="MGR-001", full_name="Darya Romanova", role=Role.MANAGER, hourly_rate=900),
}

shifts: list[ShiftRecord] = [
    ShiftRecord(
        shift_id="SHIFT-001",
        staff_id="WTR-001",
        shift_date="2026-05-14",
        start_time="10:00",
        end_time="18:00",
        planned_hours=8,
    ),
    ShiftRecord(
        shift_id="SHIFT-002",
        staff_id="CHF-001",
        shift_date="2026-05-14",
        start_time="11:00",
        end_time="20:00",
        planned_hours=9,
    ),
]

tips: list[TipRecord] = [
    TipRecord(tip_id="TIP-001", staff_id="WTR-001", amount=1250, source="card"),
    TipRecord(tip_id="TIP-002", staff_id="WTR-001", amount=740, source="cash"),
    TipRecord(tip_id="TIP-003", staff_id="WTR-002", amount=910, source="card"),
]

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
            object_type="staff",
            object_id=object_id,
            details=details or {},
        ).model_dump(mode="json")
    )


def _parse_time(value: str) -> tuple[int, int]:
    hour, minute = value.split(":")
    return int(hour), int(minute)


def _hours_between(start: str, end: str) -> float:
    sh, sm = _parse_time(start)
    eh, em = _parse_time(end)
    start_minutes = sh * 60 + sm
    end_minutes = eh * 60 + em
    if end_minutes <= start_minutes:
        end_minutes += 24 * 60
    return round((end_minutes - start_minutes) / 60, 2)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.get("/staff")
async def list_staff(role: Role | None = None, active_only: bool = True) -> dict[str, Any]:
    items = []
    for person in staff.values():
        if role and person.role != role:
            continue
        if active_only and not person.is_active:
            continue
        items.append(person.model_dump(mode="json"))
    return {"items": items, "count": len(items)}


@app.get("/shifts")
async def list_shifts(staff_id: str | None = None, shift_date: str | None = None) -> dict[str, Any]:
    items = [
        shift.model_dump(mode="json")
        for shift in shifts
        if (not staff_id or shift.staff_id == staff_id) and (not shift_date or shift.shift_date == shift_date)
    ]
    return {"items": items, "count": len(items)}


@app.post("/shifts")
async def create_shift(request: ShiftCreateRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "staff:update")
    if request.staff_id not in staff:
        raise HTTPException(status_code=404, detail="Staff member not found")
    planned_hours = _hours_between(request.start_time, request.end_time)
    shift = ShiftRecord(
        shift_id=str(uuid4()),
        staff_id=request.staff_id,
        shift_date=request.shift_date,
        start_time=request.start_time,
        end_time=request.end_time,
        planned_hours=planned_hours,
    )
    shifts.append(shift)
    _audit(request.actor_id, request.actor_role, "staff.shift.create", shift.shift_id)
    return shift.model_dump(mode="json")


@app.post("/tips")
async def add_tip(staff_id: str, amount: float, source: str, actor_id: str, actor_role: Role) -> dict[str, Any]:
    _assert_permission(actor_role, "staff:update")
    if staff_id not in staff:
        raise HTTPException(status_code=404, detail="Staff member not found")
    record = TipRecord(tip_id=str(uuid4()), staff_id=staff_id, amount=amount, source=source)
    tips.append(record)
    _audit(actor_id, actor_role, "staff.tip.add", record.tip_id, {"staff_id": staff_id, "amount": amount})
    return record.model_dump(mode="json")


@app.get("/tips")
async def list_tips(staff_id: str | None = None) -> dict[str, Any]:
    items = [tip.model_dump(mode="json") for tip in tips if not staff_id or tip.staff_id == staff_id]
    return {"items": items, "count": len(items)}


@app.get("/payroll/{period}")
async def payroll(period: str) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for person in staff.values():
        person_hours = sum(
            shift.planned_hours
            for shift in shifts
            if shift.staff_id == person.staff_id and shift.shift_date.startswith(period)
        )
        base_salary = round(person_hours * person.hourly_rate, 2)
        tips_sum = round(
            sum(
                tip.amount
                for tip in tips
                if tip.staff_id == person.staff_id and tip.created_at.strftime("%Y-%m") == period
            ),
            2,
        )
        bonus = round(base_salary * 0.05 if person.role in {Role.CHEF, Role.MANAGER} else 0.0, 2)
        record = PayrollRecord(
            staff_id=person.staff_id,
            period=period,
            base_salary=base_salary,
            tips=tips_sum,
            bonus=bonus,
            total=round(base_salary + tips_sum + bonus, 2),
        )
        records.append(record.model_dump(mode="json"))
    return {"period": period, "items": records, "count": len(records)}


@app.get("/staffing/forecast")
async def staffing_forecast(expected_guests: int = 120) -> dict[str, Any]:
    return estimate_staffing_requirements(expected_guests)


@app.get("/kpi/staff/{staff_id}")
async def staff_kpi(staff_id: str) -> dict[str, Any]:
    person = staff.get(staff_id)
    if person is None:
        raise HTTPException(status_code=404, detail="Staff member not found")
    person_shifts = [shift for shift in shifts if shift.staff_id == staff_id]
    total_hours = round(sum(shift.planned_hours for shift in person_shifts), 2)
    tips_total = round(sum(tip.amount for tip in tips if tip.staff_id == staff_id), 2)
    tip_per_hour = round(tips_total / total_hours, 2) if total_hours else 0.0
    return {
        "staff_id": staff_id,
        "role": person.role.value,
        "total_hours": total_hours,
        "tips_total": tips_total,
        "tips_per_hour": tip_per_hour,
    }


@app.get("/audit")
async def audit(limit: int = 100, actor_role: Role = Role.ADMIN) -> dict[str, Any]:
    _assert_permission(actor_role, "audit:read")
    return {"items": audit_log[-limit:]}


@app.get("/heartbeat")
async def heartbeat() -> dict[str, Any]:
    return {"utc": datetime.now(UTC).isoformat(), "staff_online": len([p for p in staff.values() if p.is_active])}
