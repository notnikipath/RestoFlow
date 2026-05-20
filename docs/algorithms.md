# Algorithms

## Reservation and seating

- Best-fit table assignment minimizes wasted seats.
- Reservation status transitions: `pending -> confirmed -> seated -> completed`.

## Kitchen timing

- Readiness estimate uses item count, queue workload index, and priority.
- Parallel plan calculates worker pool and batch size for pending tickets.

## Inventory deduction

- Each order line is converted to recipe ingredient requirements.
- Minimum stock breach creates automatic reorder entries.
- Async queue mode allows deferred stock updates.

## Forecast and analytics

- Guest load forecast applies seasonal and event multipliers.
- Forecast quality uses MAPE over expected vs actual hourly load.
- Menu recommendations combine sales volume and gross margin.

## Payment

- Split bill supports explicit custom shares and even split helper.
