from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException

from shared.restoflow_common import (
    IngredientUnit,
    InventoryBatchDeductRequest,
    InventoryDeductResult,
    InventoryStock,
    RecipeItem,
    Role,
    Settings,
    build_audit_event,
    food_cost,
    has_permission,
)

settings = Settings(service_name="inventory-service", service_port=8505)
app = FastAPI(title="RestoFlow Inventory Service", version="1.0.0")

inventory: dict[str, InventoryStock] = {
    "ING-BREAD": InventoryStock(
        ingredient_id="ING-BREAD",
        name="Ciabatta",
        unit=IngredientUnit.G,
        quantity=22000,
        min_quantity=5000,
        price_per_unit=0.06,
        supplier="Bakery Partner",
    ),
    "ING-TOMATO": InventoryStock(
        ingredient_id="ING-TOMATO",
        name="Tomato",
        unit=IngredientUnit.G,
        quantity=18000,
        min_quantity=4500,
        price_per_unit=0.09,
        supplier="FreshFarm",
    ),
    "ING-OLIVE": InventoryStock(
        ingredient_id="ING-OLIVE",
        name="Olive Oil",
        unit=IngredientUnit.ML,
        quantity=6500,
        min_quantity=1800,
        price_per_unit=0.23,
        supplier="OliveHub",
    ),
    "ING-SALMON": InventoryStock(
        ingredient_id="ING-SALMON",
        name="Salmon Fillet",
        unit=IngredientUnit.G,
        quantity=12000,
        min_quantity=4000,
        price_per_unit=1.95,
        supplier="SeaMarket",
    ),
    "ING-LEMON": InventoryStock(
        ingredient_id="ING-LEMON",
        name="Lemon",
        unit=IngredientUnit.G,
        quantity=5000,
        min_quantity=1200,
        price_per_unit=0.12,
        supplier="FreshFarm",
    ),
    "ING-BUN": InventoryStock(
        ingredient_id="ING-BUN",
        name="Burger Bun",
        unit=IngredientUnit.PCS,
        quantity=300,
        min_quantity=80,
        price_per_unit=20,
        supplier="Bakery Partner",
    ),
    "ING-BEEF": InventoryStock(
        ingredient_id="ING-BEEF",
        name="Beef Patty",
        unit=IngredientUnit.G,
        quantity=15000,
        min_quantity=3000,
        price_per_unit=0.85,
        supplier="MeatLine",
    ),
    "ING-CHEESE": InventoryStock(
        ingredient_id="ING-CHEESE",
        name="Cheddar",
        unit=IngredientUnit.G,
        quantity=7000,
        min_quantity=1800,
        price_per_unit=0.44,
        supplier="MilkWorks",
    ),
}

recipe_book: dict[str, list[RecipeItem]] = {
    "DISH-BRUS": [
        RecipeItem(ingredient_id="ING-BREAD", quantity=80, unit=IngredientUnit.G),
        RecipeItem(ingredient_id="ING-TOMATO", quantity=60, unit=IngredientUnit.G),
        RecipeItem(ingredient_id="ING-OLIVE", quantity=12, unit=IngredientUnit.ML),
    ],
    "DISH-SALMON": [
        RecipeItem(ingredient_id="ING-SALMON", quantity=220, unit=IngredientUnit.G),
        RecipeItem(ingredient_id="ING-LEMON", quantity=25, unit=IngredientUnit.G),
        RecipeItem(ingredient_id="ING-OLIVE", quantity=15, unit=IngredientUnit.ML),
    ],
    "DISH-BURGER": [
        RecipeItem(ingredient_id="ING-BUN", quantity=1, unit=IngredientUnit.PCS),
        RecipeItem(ingredient_id="ING-BEEF", quantity=140, unit=IngredientUnit.G),
        RecipeItem(ingredient_id="ING-CHEESE", quantity=25, unit=IngredientUnit.G),
    ],
}

reorder_queue: list[dict[str, Any]] = []
pending_adjustments: list[dict[str, Any]] = []
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
            object_type="inventory",
            object_id=object_id,
            details=details or {},
        ).model_dump(mode="json")
    )


def _queue_reorder(item: InventoryStock) -> None:
    recommended_quantity = round(max(item.min_quantity * 3 - item.quantity, item.min_quantity), 2)
    reorder_queue.append(
        {
            "reorder_id": str(uuid4()),
            "ingredient_id": item.ingredient_id,
            "ingredient_name": item.name,
            "recommended_quantity": recommended_quantity,
            "unit": item.unit.value,
            "supplier": item.supplier,
            "created_at": datetime.now(UTC).isoformat(),
            "status": "new",
        }
    )


def _apply_adjustment(dish_id: str, quantity: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    recipe = recipe_book.get(dish_id)
    if recipe is None:
        raise HTTPException(status_code=404, detail=f"Recipe for dish {dish_id} not found")

    deducted: list[dict[str, Any]] = []
    low_stock: list[dict[str, Any]] = []
    for ingredient in recipe:
        stock = inventory.get(ingredient.ingredient_id)
        if stock is None:
            raise HTTPException(status_code=404, detail=f"Ingredient {ingredient.ingredient_id} not found")

        required = round(ingredient.quantity * quantity, 2)
        if stock.quantity < required:
            raise HTTPException(
                status_code=409,
                detail=f"Insufficient stock: {stock.ingredient_id} requires {required}, available {stock.quantity}",
            )
        stock.quantity = round(stock.quantity - required, 2)
        deducted.append(
            {
                "dish_id": dish_id,
                "ingredient_id": stock.ingredient_id,
                "required": required,
                "remaining": stock.quantity,
                "unit": stock.unit.value,
            }
        )
        if stock.quantity <= stock.min_quantity:
            _queue_reorder(stock)
            low_stock.append(
                {
                    "ingredient_id": stock.ingredient_id,
                    "quantity": stock.quantity,
                    "min_quantity": stock.min_quantity,
                }
            )
    return deducted, low_stock


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.get("/ingredients")
async def list_ingredients(low_only: bool = False) -> dict[str, Any]:
    items = []
    for stock in inventory.values():
        if low_only and stock.quantity > stock.min_quantity:
            continue
        items.append(stock.model_dump(mode="json"))
    items.sort(key=lambda item: item["ingredient_id"])
    return {"items": items, "count": len(items)}


@app.post("/ingredients/upsert")
async def upsert_ingredient(stock: InventoryStock, actor_id: str, actor_role: Role) -> dict[str, Any]:
    _assert_permission(actor_role, "inventory:update")
    inventory[stock.ingredient_id] = stock
    _audit(actor_id, actor_role, "inventory.upsert", stock.ingredient_id)
    return stock.model_dump(mode="json")


@app.post("/inventory/deduct-batch")
async def deduct_batch(request: InventoryBatchDeductRequest, async_mode: bool = False) -> dict[str, Any]:
    _assert_permission(request.actor_role, "inventory:update")
    deducted: list[dict[str, Any]] = []
    low_stock: list[dict[str, Any]] = []

    if async_mode:
        for item in request.items:
            pending_adjustments.append(
                {
                    "order_id": request.order_id,
                    "dish_id": item.dish_id,
                    "quantity": item.quantity,
                    "queued_at": datetime.now(UTC).isoformat(),
                }
            )
        _audit(
            request.actor_id,
            request.actor_role,
            "inventory.deduct.queued",
            request.order_id,
            {"items": len(request.items)},
        )
        return {
            "order_id": request.order_id,
            "status": "queued",
            "queued_items": len(request.items),
        }

    for item in request.items:
        item_deducted, item_low = _apply_adjustment(item.dish_id, item.quantity)
        deducted.extend(item_deducted)
        low_stock.extend(item_low)

    result = InventoryDeductResult(order_id=request.order_id, deducted=deducted, low_stock=low_stock)
    _audit(request.actor_id, request.actor_role, "inventory.deduct", request.order_id, {"entries": len(deducted)})
    return result.model_dump(mode="json")


@app.post("/inventory/async/apply")
async def apply_async_updates(actor_id: str, actor_role: Role) -> dict[str, Any]:
    _assert_permission(actor_role, "inventory:update")
    applied = 0
    failed = 0
    errors: list[str] = []

    while pending_adjustments:
        adjustment = pending_adjustments.pop(0)
        try:
            _apply_adjustment(str(adjustment["dish_id"]), int(adjustment["quantity"]))
            applied += 1
        except HTTPException as exc:
            failed += 1
            errors.append(str(exc.detail))

    _audit(actor_id, actor_role, "inventory.async.apply", str(applied), {"failed": failed})
    return {"applied": applied, "failed": failed, "errors": errors}


@app.get("/inventory/reorders")
async def list_reorders(status: str | None = None) -> dict[str, Any]:
    items = [
        entry for entry in reorder_queue if not status or str(entry.get("status")) == status
    ]
    return {"items": items, "count": len(items)}


@app.post("/inventory/reorders/{reorder_id}/status")
async def set_reorder_status(reorder_id: str, status: str, actor_id: str, actor_role: Role) -> dict[str, Any]:
    _assert_permission(actor_role, "inventory:update")
    for entry in reorder_queue:
        if entry["reorder_id"] == reorder_id:
            entry["status"] = status
            entry["updated_at"] = datetime.now(UTC).isoformat()
            _audit(actor_id, actor_role, "inventory.reorder.status", reorder_id, {"status": status})
            return entry
    raise HTTPException(status_code=404, detail="Reorder not found")


@app.get("/inventory/cost/{dish_id}")
async def dish_food_cost(dish_id: str) -> dict[str, Any]:
    recipe = recipe_book.get(dish_id)
    if recipe is None:
        raise HTTPException(status_code=404, detail="Dish recipe not found")
    recipe_payload = [item.model_dump(mode="json") for item in recipe]
    prices = {item.ingredient_id: item.price_per_unit for item in inventory.values()}
    return {
        "dish_id": dish_id,
        "food_cost": food_cost(recipe_payload, prices),
        "recipe_items": recipe_payload,
    }


@app.get("/inventory/queue")
async def async_queue_state() -> dict[str, Any]:
    return {"queued": pending_adjustments, "count": len(pending_adjustments)}


@app.get("/audit")
async def audit(limit: int = 100, actor_role: Role = Role.ADMIN) -> dict[str, Any]:
    _assert_permission(actor_role, "audit:read")
    return {"items": audit_log[-limit:]}
