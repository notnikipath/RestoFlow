# API Overview

## Gateway

- `POST /auth/token`
- `POST /auth/verify`
- `GET /services/health`
- `POST /workflow/create-reservation`
- `POST /workflow/create-order`
- `POST /workflow/close-order`
- `GET /dashboard/overview`

## Reservation service

- `GET /halls/schema`
- `GET /tables`
- `POST /reservations`
- `GET /reservations`
- `POST /seating/assign`
- `POST /reservations/{reservation_id}/seat`
- `POST /chatbot/reserve`

## Menu service

- `GET /categories`
- `GET /dishes`
- `GET /dishes/{dish_id}`
- `POST /dishes`
- `POST /dishes/{dish_id}/price`
- `GET /menu/seasonal/{season}`
- `GET /menu/recommendations`
- `GET /menu/cost/{dish_id}`

## Order service

- `GET /orders`
- `GET /orders/{order_id}`
- `POST /orders`
- `POST /orders/{order_id}/status`
- `POST /orders/{order_id}/split-bill`
- `POST /orders/{order_id}/split-even`
- `GET /orders/{order_id}/receipt`

## Kitchen service

- `POST /kitchen/tickets`
- `GET /kitchen/tickets`
- `POST /kitchen/tickets/{ticket_id}/status`
- `GET /kitchen/board`
- `GET /kitchen/timers`
- `GET /kitchen/parallel-plan`

## Inventory service

- `GET /ingredients`
- `POST /ingredients/upsert`
- `POST /inventory/deduct-batch`
- `POST /inventory/async/apply`
- `GET /inventory/reorders`
- `GET /inventory/cost/{dish_id}`

## Staff service

- `GET /staff`
- `GET /shifts`
- `POST /shifts`
- `POST /tips`
- `GET /payroll/{period}`
- `GET /staffing/forecast`

## Analytics service

- `POST /analytics/ingest/order`
- `POST /analytics/ingest/reservation`
- `GET /analytics/revenue`
- `GET /analytics/average-check`
- `GET /analytics/popular-dishes`
- `POST /analytics/load-forecast`
- `GET /analytics/forecast-accuracy`
- `GET /analytics/quality-targets`

## Notification service

- `POST /notify/send`
- `POST /notify/order-ready`
- `POST /notify/reservation-confirmed`
- `GET /notify/history`
