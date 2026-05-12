from contextlib import asynccontextmanager
import traceback
from uuid import uuid4
from fastapi import FastAPI
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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


@app.middleware("http")
async def attach_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", str(uuid4()))
    tb = traceback.format_exc()
    log.error("Unhandled exception [%s] %s %s: %s\n%s", request_id, request.method, request.url.path, exc, tb)
    return JSONResponse(
        status_code=500,
        content={
            "detail": {
                "message": "Unhandled server exception",
                "root_cause": str(exc),
                "stage": "api_runtime",
                "request_id": request_id,
                "suggested_fix": "Check backend logs for stack trace and validate request payload/schema.",
            }
        },
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
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
