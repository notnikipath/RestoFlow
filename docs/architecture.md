# Architecture

## Context

RestoFlow automates day-to-day operations for single and multi-venue food businesses. The platform supports reservation management, menu governance, order execution, kitchen flow, stock control, staffing, and operational analytics.

## Service map

- `api-gateway`: single entry point, service orchestration, auth, and cross-service workflows
- `reservation-service`: hall plans, table inventory, booking lifecycle, seating operations
- `menu-service`: menu categories, seasonal dishes, pricing and media, recommendation feed
- `order-service`: waiter order API, order state transitions, split-bill handling
- `kitchen-service`: ticket board by status, prep timers, kitchen workload plan
- `inventory-service`: ingredient ledger, recipe deduction, minimum-level auto reorder, async stock queue
- `staff-service`: shifts, tips, payroll views, staffing forecast
- `analytics-service`: revenue, average check, dish popularity, forecast accuracy (MAPE), KPI target checks
- `notification-service`: reservation and order notifications across channels
- `frontend`: management dashboard for operations and quality metrics

## Infrastructure

- PostgreSQL for operational persistence
- Redis for hot-path caching and short-lived coordination
- RabbitMQ for asynchronous integration points and queue-ready architecture
- Docker Compose for local deployment

## Key workflows

1. Online reservation creation with automatic table match
2. Waiter order creation and kitchen ticket generation
3. Inventory deduction by recipe and low-stock reorder trigger
4. Kitchen readiness notification to waiter
5. Analytics ingestion for revenue and SLA KPIs

## Scalability strategy

- Menu caching reduces read pressure
- Kitchen parallel-plan endpoint supports increasing throughput
- Async inventory queue decouples heavy stock updates from customer-facing latency
- Service isolation enables horizontal scaling for network deployment (100 venues target)
