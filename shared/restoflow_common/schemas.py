from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class VenueType(str, Enum):
    RESTAURANT = "restaurant"
    CAFE = "cafe"
    BAR = "bar"
    FASTFOOD = "fastfood"
    CANTEEN = "canteen"


class Role(str, Enum):
    GUEST = "guest"
    HOSTESS = "hostess"
    WAITER = "waiter"
    CHEF = "chef"
    CASHIER = "cashier"
    MANAGER = "manager"
    ADMIN = "admin"


class TableStatus(str, Enum):
    AVAILABLE = "available"
    RESERVED = "reserved"
    OCCUPIED = "occupied"
    CLEANING = "cleaning"


class ReservationStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    SEATED = "seated"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"
    COMPLETED = "completed"


class Season(str, Enum):
    ALL = "all"
    SPRING = "spring"
    SUMMER = "summer"
    AUTUMN = "autumn"
    WINTER = "winter"


class OrderStatus(str, Enum):
    CREATED = "created"
    SENT_TO_KITCHEN = "sent_to_kitchen"
    PREPARING = "preparing"
    READY = "ready"
    SERVED = "served"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class KitchenStatus(str, Enum):
    QUEUED = "queued"
    PREPARING = "preparing"
    READY = "ready"
    DELIVERED = "delivered"


class PaymentStatus(str, Enum):
    UNPAID = "unpaid"
    PARTIAL = "partial"
    PAID = "paid"


class PaymentMethod(str, Enum):
    CASH = "cash"
    CARD = "card"
    QR = "qr"
    ONLINE = "online"


class IngredientUnit(str, Enum):
    G = "g"
    ML = "ml"
    PCS = "pcs"


class NotificationChannel(str, Enum):
    PUSH = "push"
    SMS = "sms"
    EMAIL = "email"
    TELEGRAM = "telegram"
    WEBHOOK = "webhook"


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class TablePosition(BaseModel):
    x: int = Field(ge=0)
    y: int = Field(ge=0)


class RestaurantTable(BaseModel):
    table_id: str
    hall_id: str
    label: str
    seats: int = Field(gt=0)
    status: TableStatus = TableStatus.AVAILABLE
    position: TablePosition


class HallLayout(BaseModel):
    hall_id: str
    hall_name: str
    venue_type: VenueType
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    tables: list[RestaurantTable] = Field(default_factory=list)


class ReservationCreateRequest(BaseModel):
    venue_type: VenueType
    guest_name: str
    phone: str
    party_size: int = Field(gt=0, le=30)
    reservation_time: datetime
    duration_minutes: int = Field(default=120, ge=30, le=360)
    notes: str = ""
    preferred_hall_id: str | None = None
    actor_id: str = "guest"
    actor_role: Role = Role.GUEST


class ReservationRecord(BaseModel):
    reservation_id: str
    venue_type: VenueType
    guest_name: str
    phone: str
    party_size: int
    reservation_time: datetime
    duration_minutes: int
    notes: str = ""
    status: ReservationStatus = ReservationStatus.PENDING
    table_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SeatingAssignmentRequest(BaseModel):
    reservation_id: str
    table_id: str
    actor_id: str
    actor_role: Role


class MenuCategory(BaseModel):
    category_id: str
    name: str
    description: str = ""
    sort_order: int = Field(default=100, ge=1)


class RecipeItem(BaseModel):
    ingredient_id: str
    quantity: float = Field(gt=0)
    unit: IngredientUnit


class Dish(BaseModel):
    dish_id: str
    name: str
    category_id: str
    price: float = Field(gt=0)
    description: str
    photo_url: str
    season: Season = Season.ALL
    is_active: bool = True
    recipe: list[RecipeItem] = Field(default_factory=list)


class DishCreateRequest(BaseModel):
    name: str
    category_id: str
    price: float = Field(gt=0)
    description: str
    photo_url: str
    season: Season = Season.ALL
    recipe: list[RecipeItem] = Field(default_factory=list)
    actor_id: str
    actor_role: Role


class DishPriceUpdateRequest(BaseModel):
    price: float = Field(gt=0)
    actor_id: str
    actor_role: Role


class OrderItemRequest(BaseModel):
    dish_id: str
    quantity: int = Field(gt=0, le=50)
    notes: str = ""


class OrderItem(BaseModel):
    dish_id: str
    dish_name: str
    quantity: int
    unit_price: float
    line_total: float
    notes: str = ""


class OrderCreateRequest(BaseModel):
    venue_type: VenueType
    table_id: str
    waiter_id: str
    guest_count: int = Field(gt=0, le=50)
    items: list[OrderItemRequest] = Field(default_factory=list)
    tip: float = Field(default=0, ge=0)
    actor_role: Role


class OrderRecord(BaseModel):
    order_id: str
    venue_type: VenueType
    table_id: str
    waiter_id: str
    guest_count: int
    items: list[OrderItem] = Field(default_factory=list)
    subtotal: float = Field(ge=0)
    service_charge: float = Field(ge=0)
    tip: float = Field(ge=0)
    total: float = Field(ge=0)
    status: OrderStatus = OrderStatus.CREATED
    payment_status: PaymentStatus = PaymentStatus.UNPAID
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class OrderStatusUpdateRequest(BaseModel):
    status: OrderStatus
    actor_id: str
    actor_role: Role


class SplitBillPart(BaseModel):
    payer: str
    amount: float = Field(gt=0)
    method: PaymentMethod


class SplitBillRequest(BaseModel):
    parts: list[SplitBillPart] = Field(default_factory=list)
    actor_id: str
    actor_role: Role


class SplitBillResult(BaseModel):
    order_id: str
    total: float
    paid: float
    debt: float
    status: PaymentStatus
    parts: list[SplitBillPart] = Field(default_factory=list)


class KitchenTicketCreateRequest(BaseModel):
    order_id: str
    table_id: str
    items: list[OrderItem]
    priority: int = Field(default=3, ge=1, le=5)
    actor_id: str
    actor_role: Role


class KitchenTicket(BaseModel):
    ticket_id: str
    order_id: str
    table_id: str
    status: KitchenStatus = KitchenStatus.QUEUED
    priority: int = Field(default=3, ge=1, le=5)
    items: list[OrderItem] = Field(default_factory=list)
    estimated_ready_minutes: int = Field(ge=1)
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    ready_at: datetime | None = None


class KitchenStatusUpdateRequest(BaseModel):
    status: KitchenStatus
    actor_id: str
    actor_role: Role


class InventoryStock(BaseModel):
    ingredient_id: str
    name: str
    unit: IngredientUnit
    quantity: float = Field(ge=0)
    min_quantity: float = Field(ge=0)
    price_per_unit: float = Field(ge=0)
    supplier: str


class InventoryDeductRequest(BaseModel):
    dish_id: str
    quantity: int = Field(gt=0)


class InventoryBatchDeductRequest(BaseModel):
    order_id: str
    items: list[InventoryDeductRequest] = Field(default_factory=list)
    actor_id: str
    actor_role: Role


class InventoryDeductResult(BaseModel):
    order_id: str
    deducted: list[dict[str, Any]] = Field(default_factory=list)
    low_stock: list[dict[str, Any]] = Field(default_factory=list)


class StaffMember(BaseModel):
    staff_id: str
    full_name: str
    role: Role
    hourly_rate: float = Field(gt=0)
    is_active: bool = True


class ShiftCreateRequest(BaseModel):
    staff_id: str
    shift_date: str
    start_time: str
    end_time: str
    actor_id: str
    actor_role: Role


class ShiftRecord(BaseModel):
    shift_id: str
    staff_id: str
    shift_date: str
    start_time: str
    end_time: str
    planned_hours: float = Field(gt=0)


class TipRecord(BaseModel):
    tip_id: str
    staff_id: str
    amount: float = Field(gt=0)
    source: str = "card"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PayrollRecord(BaseModel):
    staff_id: str
    period: str
    base_salary: float = Field(ge=0)
    tips: float = Field(ge=0)
    bonus: float = Field(ge=0)
    total: float = Field(ge=0)


class NotificationRequest(BaseModel):
    channel: NotificationChannel
    recipient: str
    subject: str
    body: str
    severity: Severity = Severity.INFO
    actor_role: Role


class OrderReadyNotificationRequest(BaseModel):
    order_id: str
    waiter_id: str
    table_id: str
    actor_role: Role


class ReservationAnalyticsIngestRequest(BaseModel):
    venue_type: VenueType
    hour: int = Field(ge=0, le=23)
    expected: int = Field(ge=0)
    actual: int = Field(ge=0)


class OrderAnalyticsIngestRequest(BaseModel):
    order_id: str
    venue_type: VenueType
    total: float = Field(ge=0)
    processing_seconds: float = Field(ge=0)
    dish_quantities: list[dict[str, Any]] = Field(default_factory=list)


class LoadForecastRequest(BaseModel):
    venue_type: VenueType
    reservations_by_hour: list[int] = Field(default_factory=list)
    seasonal_factor: float = Field(default=1.0, ge=0.5, le=2.0)
    event_factor: float = Field(default=1.0, ge=0.5, le=2.5)


class CreateOrderWorkflowResult(BaseModel):
    order: dict[str, Any]
    kitchen_ticket: dict[str, Any]
    inventory: dict[str, Any]
    notifications: list[dict[str, Any]] = Field(default_factory=list)
    processing_seconds: float = Field(ge=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AuditEvent(BaseModel):
    event_id: str
    actor_id: str
    actor_role: Role | str
    action: str
    object_type: str
    object_id: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
