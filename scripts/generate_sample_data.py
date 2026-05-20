from __future__ import annotations

import json
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

VENUE_TYPES = ["restaurant", "cafe", "bar", "fastfood", "canteen"]
DISHES = ["DISH-BRUS", "DISH-SALMON", "DISH-OKRO", "DISH-PUMPKIN", "DISH-APPLEPIE", "DISH-MULLED", "DISH-BURGER"]
TABLES = ["T-101", "T-102", "T-103", "T-104", "T-201", "T-202", "T-301", "T-401", "T-501"]


def generate_record(index: int) -> dict:
    venue_type = random.choice(VENUE_TYPES)
    items_count = random.randint(1, 4)
    items = []
    for _ in range(items_count):
        dish_id = random.choice(DISHES)
        items.append({"dish_id": dish_id, "quantity": random.randint(1, 3)})
    processing_seconds = round(random.uniform(11.5, 34.5), 2)
    return {
        "order_id": f"ORD-{index:06d}",
        "reservation_id": f"RSV-{index:06d}",
        "venue_type": venue_type,
        "table_id": random.choice(TABLES),
        "guest_count": random.randint(1, 8),
        "total": round(random.uniform(650, 5600), 2),
        "items": items,
        "processing_seconds": processing_seconds,
        "predicted_load": random.randint(20, 110),
        "actual_load": random.randint(18, 120),
        "status": random.choice(["created", "ready", "served", "closed"]),
        "created_at": (datetime.now(UTC) - timedelta(minutes=index)).isoformat(),
    }


if __name__ == "__main__":
    random.seed(42)
    output = Path(__file__).resolve().parents[1] / "data" / "samples" / "restoflow_events.json"
    payload = [generate_record(index) for index in range(1, 6001)]
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(payload)} records to {output}")
