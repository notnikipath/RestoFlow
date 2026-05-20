from shared.restoflow_common import (
    calculate_order_totals,
    estimate_kitchen_ready_minutes,
    estimate_order_processing_seconds,
    estimate_staffing_requirements,
    parallel_order_plan,
)
from shared.restoflow_common.schemas import VenueType


def test_order_totals_and_service_charge() -> None:
    totals = calculate_order_totals(
        VenueType.RESTAURANT,
        [
            {"quantity": 2, "unit_price": 500},
            {"quantity": 1, "unit_price": 300},
        ],
        tip=100,
    )
    assert totals["subtotal"] == 1300
    assert totals["total"] > totals["subtotal"]


def test_kitchen_ready_estimate_positive() -> None:
    eta = estimate_kitchen_ready_minutes(item_count=4, workload_index=0.7, priority=3)
    assert eta >= 4


def test_parallel_order_plan_has_workers() -> None:
    plan = parallel_order_plan(pending_orders=120, cooks=5)
    assert plan["workers"] >= 1
    assert plan["batch_size"] >= 1


def test_staffing_forecast_not_zero() -> None:
    staffing = estimate_staffing_requirements(expected_guests=140)
    assert staffing["waiters"] >= 1
    assert staffing["chefs"] >= 1


def test_processing_seconds_target_range() -> None:
    seconds = estimate_order_processing_seconds(items_count=6, parallel_workers=4)
    assert seconds > 0
    assert seconds < 40
