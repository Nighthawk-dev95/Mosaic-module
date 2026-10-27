from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.routes import cube, mosaic
from app.services import refresh_service

app = FastAPI(title="Mosaic Module API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(mosaic.router)
app.include_router(cube.router)


@app.on_event("startup")
def _start_refresh_loop():
    # Populates the SQLite cache immediately on startup, then every REFRESH_INTERVAL_SECONDS
    # after that, in a background thread - see app/services/refresh_service.py.
    refresh_service.start_background_loop()


@app.get("/health")
def health():
    return {"status": "ok"}


# Serves the built React app (frontend/vite.config.ts outputs here) so the whole project
# runs as one process under Databricks Apps, which only exposes a single port. Absent in
# local dev (no build has been run), so the Vite dev server on :5173 is unaffected.
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        candidate = STATIC_DIR / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(STATIC_DIR / "index.html")
