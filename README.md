# RestoFlow

RestoFlow is a microservice platform for restaurant business automation: table reservations, menu management, waiter order intake, kitchen execution, inventory control, staff planning, and analytics.

## Supported venue types

- `restaurant`
- `cafe`
- `bar`
- `fastfood`
- `canteen`

## Services

- `api-gateway` - orchestration, auth token issuance, cross-service workflows, dashboard aggregation
- `reservation-service` - hall schema, table statuses, online reservations, seating assignment, chatbot booking endpoint
- `menu-service` - categories, seasonal menu, dish catalog with photos, pricing, recipe metadata, menu cache
- `order-service` - order lifecycle, waiter terminal API, split bill operations
- `kitchen-service` - kitchen tickets, status board, readiness timers, parallel processing plan
- `inventory-service` - ingredient stock, recipe-based deduction, auto reorder queue, async stock updates
- `staff-service` - staffing directory, shifts, tips, payroll, staffing forecast
- `analytics-service` - revenue, average check, dish popularity, load forecast MAPE, quality targets
- `notification-service` - ready-order notifications, reservation confirmation, generic notifications
- `frontend` - React operations dashboard

## Implemented optional improvements

- A1: load forecasting for staffing planning
- A2: menu recommendations based on sales and margin
- A3: automatic food-cost calculation from recipes and ingredient prices
- A4: chatbot reservation endpoint
- C1: menu caching via shared TTL cache
- C2: parallel order processing plan
- C4: asynchronous inventory update queue

## Tech stack

- Backend: Python + FastAPI
- Data: PostgreSQL, Redis
- Queue: RabbitMQ
- Frontend: React + Vite
- Mobile path: documented for React Native waiter/kitchen clients

## Local run

```bash
cd RestoFlow
docker compose up --build -d
```

## Useful URLs

- Frontend: `http://localhost:5177`
- Gateway health: `http://localhost:8500/health`
- Services health: `http://localhost:8500/services/health`
- Gateway docs: `http://localhost:8500/docs`
- RabbitMQ management: `http://localhost:15673`

## Validation

```bash
python -m ruff check .
python -m pytest -q
docker compose config
```

## Demo workflow

```bash
python scripts/demo_pipeline.py
```

## Sample data

Generate synthetic restaurant events:

```bash
python scripts/generate_sample_data.py
```

Result file: `data/samples/restoflow_events.json`
