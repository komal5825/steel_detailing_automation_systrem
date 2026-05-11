from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.api import projects, stages, handoffs, outputs, learning, ws, reports
from app.db import models
from app.db.session import engine

models.Base.metadata.create_all(bind=engine)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
log = logging.getLogger("main")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────────────
    from app.scheduler.scheduler import start_scheduler
    started = start_scheduler()
    if started:
        log.info("Automated report scheduler is RUNNING.")
    else:
        log.warning("Automated report scheduler is DISABLED (APScheduler not installed).")

    yield  # application runs here

    # ── Shutdown ─────────────────────────────────────────────────────────────
    from app.scheduler.scheduler import stop_scheduler
    stop_scheduler()
    log.info("Scheduler stopped on shutdown.")


app = FastAPI(
    title="Steel Detailing Automation Backend",
    version="2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router, prefix="/api/projects",  tags=["projects"])
app.include_router(stages.router,   prefix="/api/stages",    tags=["stages"])
app.include_router(handoffs.router, prefix="/api/handoffs",  tags=["handoffs"])
app.include_router(outputs.router,  prefix="/api/outputs",   tags=["outputs"])
app.include_router(learning.router, prefix="/api/learning",  tags=["learning"])
app.include_router(reports.router,  prefix="/api/reports",   tags=["reports"])
app.include_router(ws.router,       prefix="/ws",            tags=["websocket"])


@app.get("/")
async def root():
    return {"message": "Steel Detailing Automation backend is running"}
