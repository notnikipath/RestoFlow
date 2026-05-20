from pathlib import Path

from fastapi.testclient import TestClient

from tests.integration.helpers import load_module

ROOT = Path(__file__).resolve().parents[2]

reservation_module = load_module("reservation_module", ROOT / "reservation-service" / "app" / "main.py")
menu_module = load_module("menu_module", ROOT / "menu-service" / "app" / "main.py")
order_module = load_module("order_module", ROOT / "order-service" / "app" / "main.py")
kitchen_module = load_module("kitchen_module", ROOT / "kitchen-service" / "app" / "main.py")
inventory_module = load_module("inventory_module", ROOT / "inventory-service" / "app" / "main.py")
staff_module = load_module("staff_module", ROOT / "staff-service" / "app" / "main.py")
analytics_module = load_module("analytics_module", ROOT / "analytics-service" / "app" / "main.py")
notification_module = load_module("notification_module", ROOT / "notification-service" / "app" / "main.py")

reservation_client = TestClient(reservation_module.app)
menu_client = TestClient(menu_module.app)
order_client = TestClient(order_module.app)
kitchen_client = TestClient(kitchen_module.app)
inventory_client = TestClient(inventory_module.app)
staff_client = TestClient(staff_module.app)
analytics_client = TestClient(analytics_module.app)
notification_client = TestClient(notification_module.app)


def test_core_order_pipeline() -> None:
    reservation = reservation_client.post(
        "/reservations",
        json={
            "venue_type": "restaurant",
            "guest_name": "Test Guest",
            "phone": "+79995550101",
            "party_size": 2,
            "reservation_time": "2026-05-14T19:00:00Z",
            "duration_minutes": 120,
            "notes": "window",
            "actor_id": "HOST-001",
            "actor_role": "hostess",
        },
    )
    assert reservation.status_code == 200
    assert reservation.json()["status"] in {"confirmed", "pending"}

    menu = menu_client.get("/dishes", params={"season": "all"})
    assert menu.status_code == 200
    assert menu.json()["count"] > 0

    order = order_client.post(
        "/orders",
        json={
            "venue_type": "restaurant",
            "table_id": "T-102",
            "waiter_id": "WTR-001",
            "guest_count": 2,
            "items": [
                {"dish_id": "DISH-BRUS", "quantity": 1, "notes": ""},
                {"dish_id": "DISH-SALMON", "quantity": 1, "notes": "medium"},
            ],
            "tip": 120,
            "actor_role": "waiter",
        },
    )
    assert order.status_code == 200
    payload = order.json()
    assert payload["total"] > 0

    ticket = kitchen_client.post(
        "/kitchen/tickets",
        json={
            "order_id": payload["order_id"],
            "table_id": payload["table_id"],
            "items": payload["items"],
            "priority": 3,
            "actor_id": "MGR-001",
            "actor_role": "manager",
        },
    )
    assert ticket.status_code == 200

    deduct = inventory_client.post(
        "/inventory/deduct-batch",
        json={
            "order_id": payload["order_id"],
            "items": [
                {"dish_id": "DISH-BRUS", "quantity": 1},
                {"dish_id": "DISH-SALMON", "quantity": 1},
            ],
            "actor_id": "MGR-001",
            "actor_role": "manager",
        },
    )
    assert deduct.status_code == 200

    analytics = analytics_client.post(
        "/analytics/ingest/order",
        json={
            "order_id": payload["order_id"],
            "venue_type": payload["venue_type"],
            "total": payload["total"],
            "processing_seconds": 23.2,
            "dish_quantities": [
                {"dish_id": "DISH-BRUS", "quantity": 1},
                {"dish_id": "DISH-SALMON", "quantity": 1},
            ],
        },
    )
    assert analytics.status_code == 200

    ready = notification_client.post(
        "/notify/order-ready",
        json={
            "order_id": payload["order_id"],
            "waiter_id": payload["waiter_id"],
            "table_id": payload["table_id"],
            "actor_role": "manager",
        },
    )
    assert ready.status_code == 200


def test_staffing_and_split_payment_flow() -> None:
    split = order_client.post(
        "/orders/ORD-DEMO/split-even",
        params={
            "participants": "Alice,Bob",
            "actor_id": "CASH-001",
            "actor_role": "cashier",
        },
    )
    assert split.status_code == 200
    assert split.json()["status"] == "paid"

    shift = staff_client.post(
        "/shifts",
        json={
            "staff_id": "WTR-002",
            "shift_date": "2026-05-14",
            "start_time": "12:00",
            "end_time": "20:00",
            "actor_id": "MGR-001",
            "actor_role": "manager",
        },
    )
    assert shift.status_code == 200

    payroll = staff_client.get("/payroll/2026-05")
    assert payroll.status_code == 200
    assert payroll.json()["count"] >= 1

    quality = analytics_client.get("/analytics/quality-targets")
    assert quality.status_code == 200
    assert "order_processing_target_met" in quality.json()
