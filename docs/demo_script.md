# Demo Script

1. Start platform with `docker compose up --build -d`.
2. Open gateway docs at `http://localhost:8500/docs`.
3. Run `python scripts/demo_pipeline.py` to create an end-to-end order workflow.
4. Check kitchen board: `GET /kitchen/board`.
5. Check low stock and auto reorder: `GET /inventory/reorders`.
6. Open frontend: `http://localhost:5177` and inspect quality KPIs.
