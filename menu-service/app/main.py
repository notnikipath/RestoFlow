from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException

from shared.restoflow_common import (
    Dish,
    DishCreateRequest,
    DishPriceUpdateRequest,
    IngredientUnit,
    MenuCategory,
    RecipeItem,
    Role,
    Season,
    Settings,
    TTLCache,
    build_audit_event,
    food_cost,
    has_permission,
    menu_recommendations,
)

settings = Settings(service_name="menu-service", service_port=8502)
app = FastAPI(title="RestoFlow Menu Service", version="1.0.0")

cache = TTLCache(ttl_seconds=45)
audit_log: list[dict[str, Any]] = []

categories: dict[str, MenuCategory] = {
    "CAT-STARTERS": MenuCategory(
        category_id="CAT-STARTERS",
        name="Starters",
        description="Cold and hot starters",
        sort_order=1,
    ),
    "CAT-MAINS": MenuCategory(
        category_id="CAT-MAINS",
        name="Main Dishes",
        description="Chef specialties",
        sort_order=2,
    ),
    "CAT-DESSERTS": MenuCategory(
        category_id="CAT-DESSERTS",
        name="Desserts",
        description="Sweet menu",
        sort_order=3,
    ),
    "CAT-BAR": MenuCategory(
        category_id="CAT-BAR",
        name="Drinks",
        description="Cocktails and beverages",
        sort_order=4,
    ),
    "CAT-FAST": MenuCategory(
        category_id="CAT-FAST",
        name="Fastfood",
        description="Quick meals",
        sort_order=5,
    ),
}


def _dish(
    dish_id: str,
    name: str,
    category_id: str,
    price: float,
    season: Season,
    recipe: list[RecipeItem],
    description: str,
    photo_url: str,
) -> Dish:
    return Dish(
        dish_id=dish_id,
        name=name,
        category_id=category_id,
        price=price,
        description=description,
        photo_url=photo_url,
        season=season,
        recipe=recipe,
        is_active=True,
    )


dishes: dict[str, Dish] = {
    "DISH-BRUS": _dish(
        "DISH-BRUS",
        "Bruschetta",
        "CAT-STARTERS",
        420,
        Season.ALL,
        [
            RecipeItem(ingredient_id="ING-BREAD", quantity=80, unit=IngredientUnit.G),
            RecipeItem(ingredient_id="ING-TOMATO", quantity=60, unit=IngredientUnit.G),
            RecipeItem(ingredient_id="ING-OLIVE", quantity=12, unit=IngredientUnit.ML),
        ],
        "Ciabatta, tomato salsa, olive oil",
        "https://cdn.restoflow.local/bruschetta.jpg",
    ),
    "DISH-SALMON": _dish(
        "DISH-SALMON",
        "Grilled Salmon",
        "CAT-MAINS",
        1280,
        Season.ALL,
        [
            RecipeItem(ingredient_id="ING-SALMON", quantity=220, unit=IngredientUnit.G),
            RecipeItem(ingredient_id="ING-LEMON", quantity=25, unit=IngredientUnit.G),
            RecipeItem(ingredient_id="ING-OLIVE", quantity=15, unit=IngredientUnit.ML),
        ],
        "Salmon steak with lemon butter",
        "https://cdn.restoflow.local/salmon.jpg",
    ),
    "DISH-OKRO": _dish(
        "DISH-OKRO",
        "Okroshka",
        "CAT-MAINS",
        520,
        Season.SUMMER,
        [
            RecipeItem(ingredient_id="ING-KEFIR", quantity=250, unit=IngredientUnit.ML),
            RecipeItem(ingredient_id="ING-POTATO", quantity=120, unit=IngredientUnit.G),
            RecipeItem(ingredient_id="ING-GREENS", quantity=30, unit=IngredientUnit.G),
        ],
        "Seasonal chilled soup",
        "https://cdn.restoflow.local/okroshka.jpg",
    ),
    "DISH-PUMPKIN": _dish(
        "DISH-PUMPKIN",
        "Pumpkin Cream Soup",
        "CAT-MAINS",
        560,
        Season.AUTUMN,
        [
            RecipeItem(ingredient_id="ING-PUMPKIN", quantity=240, unit=IngredientUnit.G),
            RecipeItem(ingredient_id="ING-CREAM", quantity=80, unit=IngredientUnit.ML),
        ],
        "Autumn soup with cream",
        "https://cdn.restoflow.local/pumpkin_soup.jpg",
    ),
    "DISH-APPLEPIE": _dish(
        "DISH-APPLEPIE",
        "Apple Pie",
        "CAT-DESSERTS",
        460,
        Season.ALL,
        [
            RecipeItem(ingredient_id="ING-APPLE", quantity=140, unit=IngredientUnit.G),
            RecipeItem(ingredient_id="ING-DOUGH", quantity=120, unit=IngredientUnit.G),
        ],
        "Warm apple pie with cinnamon",
        "https://cdn.restoflow.local/apple_pie.jpg",
    ),
    "DISH-MULLED": _dish(
        "DISH-MULLED",
        "Mulled Wine",
        "CAT-BAR",
        490,
        Season.WINTER,
        [
            RecipeItem(ingredient_id="ING-WINE", quantity=180, unit=IngredientUnit.ML),
            RecipeItem(ingredient_id="ING-SPICES", quantity=6, unit=IngredientUnit.G),
        ],
        "Hot spiced wine",
        "https://cdn.restoflow.local/mulled_wine.jpg",
    ),
    "DISH-BURGER": _dish(
        "DISH-BURGER",
        "Classic Burger",
        "CAT-FAST",
        510,
        Season.ALL,
        [
            RecipeItem(ingredient_id="ING-BUN", quantity=1, unit=IngredientUnit.PCS),
            RecipeItem(ingredient_id="ING-BEEF", quantity=140, unit=IngredientUnit.G),
            RecipeItem(ingredient_id="ING-CHEESE", quantity=25, unit=IngredientUnit.G),
        ],
        "Beef burger with cheddar",
        "https://cdn.restoflow.local/burger.jpg",
    ),
}


ingredient_prices: dict[str, float] = {
    "ING-BREAD": 0.06,
    "ING-TOMATO": 0.09,
    "ING-OLIVE": 0.23,
    "ING-SALMON": 1.95,
    "ING-LEMON": 0.12,
    "ING-KEFIR": 0.05,
    "ING-POTATO": 0.03,
    "ING-GREENS": 0.13,
    "ING-PUMPKIN": 0.04,
    "ING-CREAM": 0.09,
    "ING-APPLE": 0.07,
    "ING-DOUGH": 0.05,
    "ING-WINE": 0.25,
    "ING-SPICES": 0.32,
    "ING-BUN": 20.0,
    "ING-BEEF": 0.85,
    "ING-CHEESE": 0.44,
}

sales_by_dish: dict[str, int] = {
    "DISH-BRUS": 138,
    "DISH-SALMON": 96,
    "DISH-OKRO": 62,
    "DISH-PUMPKIN": 28,
    "DISH-APPLEPIE": 142,
    "DISH-MULLED": 80,
    "DISH-BURGER": 178,
}

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


def _audit(actor_id: str, actor_role: Role, action: str, object_id: str, details: dict[str, Any] | None = None) -> None:
    audit_log.append(
        build_audit_event(
            actor_id=actor_id,
            actor_role=actor_role,
            action=action,
            object_type="menu",
            object_id=object_id,
            details=details or {},
        ).model_dump(mode="json")
    )


def _menu_payload(
    category_id: str | None = None,
    season: Season | None = None,
    active_only: bool = True,
) -> list[dict[str, Any]]:
    items = []
    for dish in dishes.values():
        if active_only and not dish.is_active:
            continue
        if category_id and dish.category_id != category_id:
            continue
        if season and dish.season not in {Season.ALL, season}:
            continue
        payload = dish.model_dump(mode="json")
        fallback_category = MenuCategory(category_id="UNK", name="Unknown")
        payload["category_name"] = categories.get(dish.category_id, fallback_category).name
        items.append(payload)
    items.sort(key=lambda item: (item["category_id"], item["name"]))
    return items


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.service_name}


@app.get("/categories")
async def list_categories() -> dict[str, Any]:
    items = [category.model_dump(mode="json") for category in categories.values()]
    items.sort(key=lambda item: item["sort_order"])
    return {"items": items, "count": len(items)}


@app.get("/dishes")
async def list_dishes(
    category_id: str | None = None,
    season: Season | None = None,
    active_only: bool = True,
    use_cache: bool = True,
) -> dict[str, Any]:
    cache_key = f"dishes:{category_id}:{season}:{active_only}"
    if use_cache:
        cached = cache.get(cache_key)
        if cached is not None:
            return {"items": cached, "count": len(cached), "cache": "hit"}

    items = _menu_payload(category_id, season, active_only)
    if use_cache:
        cache.set(cache_key, items)
    return {"items": items, "count": len(items), "cache": "miss"}


@app.get("/dishes/{dish_id}")
async def get_dish(dish_id: str) -> dict[str, Any]:
    dish = dishes.get(dish_id)
    if dish is None:
        raise HTTPException(status_code=404, detail="Dish not found")
    payload = dish.model_dump(mode="json")
    payload["food_cost"] = food_cost([item.model_dump(mode="json") for item in dish.recipe], ingredient_prices)
    return payload


@app.post("/dishes")
async def create_dish(request: DishCreateRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "menu:update")
    dish = Dish(
        dish_id=str(uuid4()),
        name=request.name,
        category_id=request.category_id,
        price=request.price,
        description=request.description,
        photo_url=request.photo_url,
        season=request.season,
        recipe=request.recipe,
        is_active=True,
    )
    dishes[dish.dish_id] = dish
    cache.clear()
    _audit(request.actor_id, request.actor_role, "menu.dish.create", dish.dish_id)
    return dish.model_dump(mode="json")


@app.post("/dishes/{dish_id}/price")
async def update_price(dish_id: str, request: DishPriceUpdateRequest) -> dict[str, Any]:
    _assert_permission(request.actor_role, "menu:update")
    dish = dishes.get(dish_id)
    if dish is None:
        raise HTTPException(status_code=404, detail="Dish not found")
    old_price = dish.price
    dish.price = request.price
    cache.clear()
    _audit(
        request.actor_id,
        request.actor_role,
        "menu.dish.price",
        dish_id,
        {"old_price": old_price, "new_price": request.price},
    )
    return dish.model_dump(mode="json")


@app.get("/menu/seasonal/{season}")
async def seasonal_menu(season: Season) -> dict[str, Any]:
    items = _menu_payload(season=season)
    return {"season": season.value, "items": items, "count": len(items)}


@app.get("/menu/recommendations")
async def recommendations() -> dict[str, Any]:
    return {
        "items": menu_recommendations(sales_by_dish, margin_by_dish),
        "source": "sales+margin",
    }


@app.get("/menu/cost/{dish_id}")
async def dish_cost(dish_id: str) -> dict[str, Any]:
    dish = dishes.get(dish_id)
    if dish is None:
        raise HTTPException(status_code=404, detail="Dish not found")
    cost = food_cost([item.model_dump(mode="json") for item in dish.recipe], ingredient_prices)
    margin = round(max(0.0, (dish.price - cost) / max(dish.price, 1.0)), 2)
    return {
        "dish_id": dish_id,
        "dish_name": dish.name,
        "price": dish.price,
        "food_cost": cost,
        "gross_margin": margin,
    }


@app.get("/cache/state")
async def cache_state() -> dict[str, Any]:
    return {"ttl_seconds": cache.ttl_seconds}


@app.get("/audit")
async def audit(limit: int = 100, actor_role: Role = Role.ADMIN) -> dict[str, Any]:
    _assert_permission(actor_role, "audit:read")
    return {"items": audit_log[-limit:]}
