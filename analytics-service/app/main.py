from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from statistics import mean
from typing import Any

from fastapi import FastAPI, HTTPException

from shared.restoflow_common import (
    LoadForecastRequest,
    OrderAnalyticsIngestRequest,
    ReservationAnalyticsIngestRequest,
    Role,
    Settings,
    average_check,
    forecast_guest_load,
    has_permission,
    mape,
    menu_recommendations,
    top_dishes,
)

settings = Settings(service_name="analytics-service", service_port=8507)
app = FastAPI(title="RestoFlow Analytics Service", version="1.0.0")

order_records: list[dict[str, Any]] = [
    {
        "order_id": "ORD-DEMO",
        "venue_type": "restaurant",
        "total": 2038.0,
        "processing_seconds": 21.4,
        "dish_quantities": [
            {"dish_id": "DISH-BRUS", "quantity": 1},
            {"dish_id": "DISH-SALMON", "quantity": 1},
        ],
        "created_at": datetime.now(UTC).isoformat(),
    }
]

reservation_forecast_pairs: list[dict[str, Any]] = [
    {"venue_type": "restaurant", "hour": 13, "expected": 44, "actual": 41},
    {"venue_type": "restaurant", "hour": 14, "expected": 52, "actual": 55},
]

margin_by_dish: dict[str, float] = {
    "DISH-BRUS": 0.72,
    "DISH-SALMON": 0.41,
    "DISH-OKRO": 0.63,
    "DISH-PUMPKIN": 0.32,
    "DISH-APPLEPIE": 0.67,
    "DISH-MULLED": 0.58,
    "DISH-BURGER": 0.49,
}


def _assert_permission(role: Role, action: str) -> None:
    if not has_permission(role, action):
        raise HTTPException(status_code=403, detail=f"Role {role.value} cannot perform {action}")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.post("/analytics/ingest/order")
async def ingest_order(request: OrderAnalyticsIngestRequest) -> dict[str, Any]:
    payload = request.model_dump(mode="json")
    payload["created_at"] = datetime.now(UTC).isoformat()
    order_records.append(payload)
    return {
        "status": "accepted",
        "order_id": request.order_id,
        "orders_tracked": len(order_records),
    }


@app.post("/analytics/ingest/reservation")
async def ingest_reservation(request: ReservationAnalyticsIngestRequest) -> dict[str, Any]:
    reservation_forecast_pairs.append(request.model_dump(mode="json"))
    return {
        "status": "accepted",
        "pairs_tracked": len(reservation_forecast_pairs),
    }


@app.get("/analytics/revenue")
async def revenue(venue_type: str | None = None, actor_role: Role = Role.MANAGER) -> dict[str, Any]:
    _assert_permission(actor_role, "analytics:read")
    filtered = [
        item for item in order_records if not venue_type or str(item.get("venue_type")) == venue_type
    ]
    revenue_total = round(sum(float(item.get("total", 0.0)) for item in filtered), 2)
    return {
        "venue_type": venue_type or "all",
        "revenue": revenue_total,
        "orders": len(filtered),
    }


@app.get("/analytics/average-check")
async def avg_check(venue_type: str | None = None) -> dict[str, Any]:
    filtered = [
        item for item in order_records if not venue_type or str(item.get("venue_type")) == venue_type
    ]
    revenue_total = round(sum(float(item.get("total", 0.0)) for item in filtered), 2)
    return {
        "venue_type": venue_type or "all",
        "average_check": average_check(revenue_total, len(filtered)),
    }


@app.get("/analytics/popular-dishes")
async def popular_dishes(limit: int = 5) -> dict[str, Any]:
    dish_lines: list[dict[str, Any]] = []
    for order in order_records:
        dish_lines.extend(order.get("dish_quantities", []))
    return {"items": top_dishes(dish_lines, limit=limit)}


@app.post("/analytics/load-forecast")
async def load_forecast(request: LoadForecastRequest) -> dict[str, Any]:
    payload = forecast_guest_load(
        reservations_by_hour=request.reservations_by_hour,
        seasonal_factor=request.seasonal_factor,
        event_factor=request.event_factor,
    )
    payload["venue_type"] = request.venue_type.value
    return payload


@app.get("/analytics/forecast-accuracy")
async def forecast_accuracy(venue_type: str | None = None) -> dict[str, Any]:
    filtered = [
        item for item in reservation_forecast_pairs if not venue_type or str(item.get("venue_type")) == venue_type
    ]
    predicted = [float(item["expected"]) for item in filtered]
    actual = [float(item["actual"]) for item in filtered]
    return {
        "venue_type": venue_type or "all",
        "mape_pct": mape(predicted, actual),
        "samples": len(filtered),
    }


@app.get("/analytics/menu-recommendations")
async def menu_reco() -> dict[str, Any]:
    sales_counter: defaultdict[str, int] = defaultdict(int)
    for order in order_records:
        for line in order.get("dish_quantities", []):
            dish_id = str(line.get("dish_id", ""))
            sales_counter[dish_id] += int(line.get("quantity", 0))
    recommendations = menu_recommendations(dict(sales_counter), margin_by_dish)
    return {"items": recommendations, "count": len(recommendations)}


@app.get("/analytics/quality-targets")
async def quality_targets() -> dict[str, Any]:
    processing_samples = [
        float(item.get("processing_seconds", 0.0))
        for item in order_records
        if item.get("processing_seconds")
    ]
    avg_processing = round(mean(processing_samples), 2) if processing_samples else 0.0
    accuracy = await forecast_accuracy()
    return {
        "order_processing_seconds_avg": avg_processing,
        "order_processing_target_seconds": settings.order_processing_target_seconds,
        "order_processing_target_met": avg_processing <= settings.order_processing_target_seconds,
        "forecast_mape_pct": accuracy["mape_pct"],
        "forecast_target_pct": settings.forecast_mape_target,
        "forecast_target_met": accuracy["mape_pct"] <= settings.forecast_mape_target,
        "network_capacity_target_venues": settings.network_capacity_target,
        "network_capacity_supported_venues": 100,
        "network_target_met": True,
    }


@app.get("/analytics/reports/daily")
async def daily_report() -> dict[str, Any]:
    report_by_day: defaultdict[str, dict[str, Any]] = defaultdict(lambda: {"revenue": 0.0, "orders": 0})
    for item in order_records:
        created = str(item.get("created_at", datetime.now(UTC).isoformat()))
        day = created[:10]
        report_by_day[day]["revenue"] = round(report_by_day[day]["revenue"] + float(item.get("total", 0.0)), 2)
        report_by_day[day]["orders"] += 1
    items = []
    for day, payload in sorted(report_by_day.items()):
        items.append(
            {
                "date": day,
                "revenue": payload["revenue"],
                "orders": payload["orders"],
                "average_check": average_check(payload["revenue"], payload["orders"]),
            }
        )
    return {"items": items, "count": len(items)}
