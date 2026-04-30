from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.api import projects, stages, handoffs, outputs, learning, ws
from app.db import models
from app.db.session import engine

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Steel Detailing Automation Backend", version="2.0")

# Basic logging configuration
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# CORS middleware - allow all origins (adjust for production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(stages.router, prefix="/api/stages", tags=["stages"])
app.include_router(handoffs.router, prefix="/api/handoffs", tags=["handoffs"])
app.include_router(outputs.router, prefix="/api/outputs", tags=["outputs"])
app.include_router(learning.router, prefix="/api/learning", tags=["learning"])
app.include_router(ws.router, prefix="/ws", tags=["websocket"])

# Root endpoint for health check
@app.get("/")
async def root():
    return {"message": "Steel Detailing Automation backend is running"}
