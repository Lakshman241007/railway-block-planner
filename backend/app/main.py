"""
FastAPI application for Railway Block Planner.

Exposes REST APIs for interacting with persistent unified railway data,
goods train forecasting, maintenance slot scheduling, and conflict detection.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from backend.app.api.routes import blocks, forecast, maintenance, plans, scheduler, trains
from backend.app.database.connection import SessionLocal, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager: initializes database on startup."""
    init_db()
    yield


app = FastAPI(
    title="Railway Block Planner API",
    description=(
        "Centralized railway maintenance block planning backend exposing "
        "persisted unified operational entities, goods train forecasting, "
        "heuristic slot scheduling, and spatial-temporal conflict detection."
    ),
    version="0.4.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS Configuration
# ---------------------------------------------------------------------------
allowed_origins_raw = os.getenv("CORS_ORIGINS", "*")
allowed_origins = [orig.strip() for orig in allowed_origins_raw.split(",") if orig.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if allowed_origins != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health & Status Endpoints
# ---------------------------------------------------------------------------
@app.get("/health", summary="Health check endpoint", tags=["System"])
def health_check() -> Dict[str, Any]:
    """Check API and database connectivity."""
    db_status = "connected"
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
    except Exception as exc:
        db_status = f"unhealthy: {exc}"

    return {
        "status": "ok" if db_status == "connected" else "degraded",
        "database": db_status,
        "version": "0.4.0",
        "phase": "Phase 4 - Forecast + Scheduler + Conflict Detection",
    }


import logging
from pathlib import Path
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Route Registrations
# ---------------------------------------------------------------------------
app.include_router(trains.router, prefix="/api")
app.include_router(maintenance.router, prefix="/api")
app.include_router(blocks.router, prefix="/api")
app.include_router(plans.router, prefix="/api")
app.include_router(forecast.router, prefix="/api")
app.include_router(scheduler.router, prefix="/api")

# ---------------------------------------------------------------------------
# Frontend Static Files Serving
# ---------------------------------------------------------------------------
FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"

if FRONTEND_DIST.exists():
    # Mount Vite's static assets directory
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")
    
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend(full_path: str):
        # Let API routes pass through to standard 404s
        if full_path.startswith("api/") or full_path in ["docs", "openapi.json", "redoc", "health"]:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Not Found")
        
        # Serve the requested file if it exists, otherwise fallback to index.html for SPA routing
        target_path = FRONTEND_DIST / full_path
        if full_path and target_path.exists() and target_path.is_file():
            return FileResponse(target_path)
            
        index_file = FRONTEND_DIST / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return {"message": "Frontend build incomplete. Missing index.html."}
else:
    @app.get("/", summary="Root index", tags=["System"])
    def root() -> Dict[str, Any]:
        """Root metadata response."""
        return {
            "name": "Railway Block Planner API",
            "version": "0.4.0",
            "docs": "/docs",
            "health": "/health",
            "phase": "Phase 4",
            "note": "Frontend dist directory not found. Serving API only."
        }
