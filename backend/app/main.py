from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import mosaic
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


@app.on_event("startup")
def _start_refresh_loop():
    # Populates the SQLite cache immediately on startup, then every REFRESH_INTERVAL_SECONDS
    # after that, in a background thread - see app/services/refresh_service.py.
    refresh_service.start_background_loop()


@app.get("/health")
def health():
    return {"status": "ok"}
