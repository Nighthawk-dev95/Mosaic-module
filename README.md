# Mosaic Module

Standalone scaffold for the Mosaic module of the Practice Command Centre, built without access to
the real PCC repo — intended to be merged into it once repo access is available. Architecture
matches what was described for PCC: FastAPI service layer -> API routes -> frontend, querying
Databricks EDW directly via `databricks-sql-connector` (no local SQLite in this scaffold yet -
add if the module needs local state like action items/journal entries, per the real PCC pattern).

## Backend

```
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Requires `DATABRICKS_SERVER_HOSTNAME`, `DATABRICKS_HTTP_PATH`, `DATABRICKS_TOKEN` as environment
variables (already set on this machine). Endpoints:

- `GET /api/mosaic/snapshot` - Enterprise Snapshot KPIs
- `GET /api/mosaic/adoption-stages` - Adoption Stage Distribution
- `GET /api/mosaic/recently-active?limit=20` - Recently Active Radiologists feed
- `GET /api/mosaic/alerts` - Active Alerts (utilization <30% at 60+ days post-deployment)
- `GET /api/mosaic/roster?practice=&subspecialty=&deployment_status=&limit=&offset=` - Radiologist roster

All read from views in `edw_dev.mosaictechops` (see `ALL_DDL_mosaic_module.sql` in the memory
directory) - the same objects the Genie Space will use as trusted assets.

## Data layer dependency

This backend assumes the DDL in `ALL_DDL_mosaic_module.sql` has already been run in Databricks.
If any view is renamed/changed there, update `app/services/mosaic_service.py` to match.
