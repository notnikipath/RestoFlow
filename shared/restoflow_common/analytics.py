from __future__ import annotations

from collections import Counter
from statistics import mean


def mape(predicted: list[float], actual: list[float]) -> float:
    if not predicted or not actual or len(predicted) != len(actual):
        return 0.0
    errors: list[float] = []
    for p, a in zip(predicted, actual, strict=True):
        if a <= 0:
            continue
        errors.append(abs((a - p) / a))
    if not errors:
        return 0.0
    return round(sum(errors) / len(errors) * 100, 2)


def average_check(revenue: float, orders: int) -> float:
    if orders <= 0:
        return 0.0
    return round(revenue / orders, 2)


def top_dishes(dish_quantities: list[dict[str, object]], limit: int = 5) -> list[dict[str, object]]:
    counter: Counter[str] = Counter()
    for item in dish_quantities:
        dish_id = str(item.get("dish_id", ""))
        qty = int(item.get("quantity", 0))
        if dish_id:
            counter[dish_id] += qty
    return [{"dish_id": dish_id, "quantity": qty} for dish_id, qty in counter.most_common(limit)]


def forecast_guest_load(
    reservations_by_hour: list[int],
    seasonal_factor: float = 1.0,
    event_factor: float = 1.0,
) -> dict[str, object]:
    if not reservations_by_hour:
        reservations_by_hour = [0] * 24
    normalized = (reservations_by_hour + [0] * 24)[:24]
    forecast = []
    for hour, value in enumerate(normalized):
        projected = round(max(0, value) * seasonal_factor * event_factor)
        forecast.append({"hour": hour, "expected_guests": projected})
    peak = max(forecast, key=lambda item: int(item["expected_guests"]))
    return {
        "forecast": forecast,
        "peak_hour": peak["hour"],
        "peak_guests": peak["expected_guests"],
        "avg_hourly_guests": round(mean([int(item["expected_guests"]) for item in forecast]), 2),
    }


def menu_recommendations(
    sales_by_dish: dict[str, int],
    margin_by_dish: dict[str, float],
) -> list[dict[str, str | float]]:
    recommendations: list[dict[str, str | float]] = []
    for dish_id, sales in sales_by_dish.items():
        margin = margin_by_dish.get(dish_id, 0.0)
        if sales >= 120 and margin >= 0.65:
            recommendations.append(
                {
                    "dish_id": dish_id,
                    "action": "promote",
                    "reason": "high demand and strong margin",
                    "margin": round(margin, 2),
                }
            )
        elif sales < 35 and margin < 0.45:
            recommendations.append(
                {
                    "dish_id": dish_id,
                    "action": "replace",
                    "reason": "low demand and weak margin",
                    "margin": round(margin, 2),
                }
            )
        elif sales >= 90 and margin < 0.5:
            recommendations.append(
                {
                    "dish_id": dish_id,
                    "action": "raise_price",
                    "reason": "high demand but low margin",
                    "margin": round(margin, 2),
                }
            )
    return recommendations


def food_cost(recipe: list[dict[str, float | str]], ingredient_prices: dict[str, float]) -> float:
    total = 0.0
    for item in recipe:
        ingredient_id = str(item.get("ingredient_id", ""))
        quantity = float(item.get("quantity", 0.0))
        price = ingredient_prices.get(ingredient_id, 0.0)
        total += quantity * price
    return round(total, 2)
