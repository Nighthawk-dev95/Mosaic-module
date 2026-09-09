# Mosaic Module

Standalone scaffold for the Mosaic module of the Practice Command Centre, built without access to
the real PCC repo — intended to be merged into it once repo access is available. Architecture
matches what was described for PCC: FastAPI service layer -> API routes -> frontend, querying
Databricks EDW via `databricks-sql-connector`.

EDW is **not** queried per request. A background refresh loop pulls every dataset into a local
SQLite cache and the routes read from that — see [Caching and refresh](#caching-and-refresh).

## Backend

```
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Serves on `http://127.0.0.1:8000`. CORS is open only to `localhost:5173` / `127.0.0.1:5173`
(see `app/main.py`), so the frontend must run on port 5173.

### Environment

Required (already set as Windows user environment variables on this machine):

| Variable | Notes |
|---|---|
| `DATABRICKS_SERVER_HOSTNAME` | e.g. `adb-....azuredatabricks.net` |
| `DATABRICKS_HTTP_PATH` | e.g. `/sql/1.0/warehouses/<id>` |
| `DATABRICKS_TOKEN` | PAT |
| `MOSAIC_CATALOG` | optional, defaults to `edw_dev` |
| `MOSAIC_SCHEMA` | optional, defaults to `mosaictechops` |

> **Launching from Git Bash / MSYS2:** `DATABRICKS_HTTP_PATH` starts with `/`, so MSYS2 rewrites
> it into a Windows path (`C:/.../Git/sql/1.0/warehouses/...`) when it spawns `python.exe`. The
> warehouse ID stops resolving and Databricks returns **HTTP 404 on OpenSession**, which surfaces
> as the unhelpful `RequestError: Error during request to server` on every dataset. Prefix the
> command to opt out:
>
> ```bash
> MSYS2_ENV_CONV_EXCL="DATABRICKS_HTTP_PATH" .venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000
> ```
>
> PowerShell, cmd, and the VS Code terminal are unaffected.

## Frontend

```
cd frontend
npm install
npm run dev
```

Vite dev server on `http://localhost:5173`. React 19 + React Router 7 + Recharts 3.
Other scripts: `npm run build` (tsc + vite build), `npm run lint` (oxlint), `npm run preview`.

## API

All routes are `GET` unless noted. Query params are shown with their defaults.

**Overview**

- `/health` - liveness probe
- `/api/mosaic/mosaic-intelligence` - Mosaic Intelligence snapshot KPIs
- `/api/mosaic/rad-summary-stats?practice=&drafting_group=` - radiologist summary stats
- `/api/mosaic/rpce-trend` - RPCE reporting/drafting trend over time
- `/api/mosaic/roster?practice=&subspecialty=&deployment_status=&limit=100&offset=0` - radiologist roster
- `/api/mosaic/utilization/by-practice?days_back=30` - utilization by practice

**Deployment**

- `/api/mosaic/deployment/by-radiologist?limit=500&offset=0`
- `/api/mosaic/deployment/by-practice`
- `/api/mosaic/deployment/funnel/reporting`
- `/api/mosaic/deployment/funnel/drafting`
- `/api/mosaic/deployment/funnel/ct-abdpel`
- `/api/mosaic/deployment/blockers/drafting`
- `/api/mosaic/deployment/blockers/ct-abdpel`

**Efficiency**

- `/api/mosaic/efficiency?mode=full_mosaic` - efficiency detail
- `/api/mosaic/efficiency/filters` - available filter values
- `/api/mosaic/efficiency/population?mode=full_mosaic&practice=&subspecialty=&modality_code=&parent_procedure_name=&exam_category=`
- `/api/mosaic/efficiency/trend?exam_category=`
- `/api/mosaic/efficiency/trend/rp-avg`

**Capacity**

- `/api/mosaic/capacity/by-radiologist?limit=500&offset=0`
- `/api/mosaic/capacity/by-practice`

**Cache control**

- `POST /api/mosaic/refresh` - trigger a full refresh
- `/api/mosaic/refresh/status` - per-dataset `refreshed_at`, `errors`, `in_progress`

Interactive docs at `http://127.0.0.1:8000/docs`; the machine-readable list is always
`http://127.0.0.1:8000/openapi.json`.

## Caching and refresh

`app/services/refresh_service.py` defines 17 datasets and refreshes all of them on startup, then
every `REFRESH_INTERVAL_SECONDS` (30 minutes) in a background thread. Routes read the cache, never
EDW, so filtering and pagination happen in `cache_service.py` / `efficiency_store.py` over
already-cached data.

- Cache file: `backend/mosaic_cache.sqlite3` (gitignored).
- Generic datasets are stored as JSON blobs by `app/db/cache_store.py`.
- `efficiency_matrix` is the exception — ~780K rows, too large to parse as JSON per request, so it
  gets its own indexed SQLite table via `app/db/efficiency_store.py`. Its `cache_store` entry only
  records a refresh timestamp so it still appears in `/refresh/status`.

The first startup refresh takes several minutes. Until it finishes, routes serve the previous
cache contents, so the app is usable immediately after a restart. Failures are per-dataset and
non-fatal: check `errors` in `/api/mosaic/refresh/status`, or the `[refresh] <name>: FAILED` lines
on stdout.

## Data layer dependency

This backend assumes the DDL in `ALL_DDL_mosaic_module.sql` (in the memory directory) has already
been run in Databricks, against `edw_dev.mosaictechops` — the same objects the Genie Space uses as
trusted assets. If any view is renamed or changed there, update `app/services/mosaic_service.py`
to match.
