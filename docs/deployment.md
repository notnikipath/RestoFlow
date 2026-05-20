# Deployment

## Requirements

- Docker and Docker Compose
- Python 3.11 for local lint/testing

## Start

```bash
cd d:\Шарага\Кинжа7\Task_20_RestoFlow
docker compose up --build -d
```

## Stop

```bash
docker compose down
```

## Validate

```bash
python -m ruff check .
python -m pytest -q
docker compose config
```

## Ports

- `8500` gateway
- `8501-8508` backend services
- `5177` frontend
- `55445` PostgreSQL
- `6385` Redis
- `5673` RabbitMQ
- `15673` RabbitMQ management
