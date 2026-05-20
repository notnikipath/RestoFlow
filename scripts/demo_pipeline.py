from __future__ import annotations

import json
import urllib.request

BASE = "http://localhost:8500"


def request(method: str, path: str, payload: dict | None = None) -> dict:
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(f"{BASE}{path}", data=data, headers=headers, method=method)
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode("utf-8"))


if __name__ == "__main__":
    result = request(
        "POST",
        "/workflow/create-order",
        {
            "venue_type": "restaurant",
            "table_id": "T-102",
            "waiter_id": "WTR-001",
            "guest_count": 2,
            "items": [
                {"dish_id": "DISH-BRUS", "quantity": 1},
                {"dish_id": "DISH-SALMON", "quantity": 1},
            ],
            "tip": 150,
            "actor_role": "waiter",
            "notify_when_ready": True,
            "inventory_async": False,
        },
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
