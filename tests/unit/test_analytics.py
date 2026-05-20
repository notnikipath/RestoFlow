from shared.restoflow_common import (
    average_check,
    food_cost,
    forecast_guest_load,
    mape,
    menu_recommendations,
    top_dishes,
)


def test_mape_positive() -> None:
    assert mape([100, 110], [105, 100]) > 0


def test_average_check() -> None:
    assert average_check(12000, 24) == 500


def test_forecast_shape() -> None:
    forecast = forecast_guest_load([10, 20, 30], seasonal_factor=1.1, event_factor=1.0)
    assert len(forecast["forecast"]) == 24


def test_top_dishes() -> None:
    result = top_dishes(
        [
            {"dish_id": "DISH-BURGER", "quantity": 5},
            {"dish_id": "DISH-BURGER", "quantity": 2},
            {"dish_id": "DISH-BRUS", "quantity": 3},
        ],
        limit=2,
    )
    assert result[0]["dish_id"] == "DISH-BURGER"


def test_menu_recommendations_not_empty_for_known_case() -> None:
    rec = menu_recommendations({"A": 140, "B": 20}, {"A": 0.7, "B": 0.3})
    assert rec


def test_food_cost_sum() -> None:
    cost = food_cost(
        [
            {"ingredient_id": "I1", "quantity": 100},
            {"ingredient_id": "I2", "quantity": 50},
        ],
        {"I1": 0.1, "I2": 0.2},
    )
    assert cost == 20