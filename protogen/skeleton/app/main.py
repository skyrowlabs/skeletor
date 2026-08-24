"""Application entry point. Generated code is imported here but this file is
never generated -- it is identical in every protogen app."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app import models  # noqa: F401  -- import registers tables on Base.metadata
from app.db import Base, SessionLocal, engine
from app.routes import router
from app.seed import seed
from app.settings import settings


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed(db)
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.mount(
    "/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static"
)
app.include_router(router)


@app.get("/healthz", include_in_schema=False)
def healthz() -> JSONResponse:
    """Liveness *and* database reachability.

    protogen's verify step waits on this endpoint, so it has to fail while the
    database is still coming up -- otherwise the smoke tests start against a
    half-ready app and report a bug that is really a race.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("select 1"))
    except Exception as exc:  # noqa: BLE001 -- surfacing the reason is the point
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=503)
    return JSONResponse({"ok": True, "app": settings.app_name})
