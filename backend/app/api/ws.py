"""
WebSocket endpoint for real-time pipeline status updates.

Connect: ws://host/api/ws/{project_id}

On connect the server immediately sends the current pipeline status snapshot.
During a pipeline run, the orchestrator broadcasts stage transitions via
register_ws / unregister_ws, so the client sees updates without polling.

Message format (JSON):
  {"type": "snapshot", "stages": [...]}          — initial full status
  {"type": "stage_update", "stage_code": "P2-02", "status": "PASSED", "ts": "..."}
"""
from __future__ import annotations

import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.db.crud.stages import list_project_stages
from app.db.session import SessionLocal
from app.orchestrator.controller import register_ws, unregister_ws
from app.utils.audit_logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.websocket("/{project_id}")
async def websocket_endpoint(websocket: WebSocket, project_id: str):
    # 1. Accept the connection first to establish the handshake
    try:
        await websocket.accept()
    except Exception as exc:
        logger.error(f"WebSocket accept failed for {project_id}: {exc}")
        return

    # 2. Validate Project ID
    try:
        from uuid import UUID
        pid_uuid = UUID(project_id)
    except Exception:
        logger.error(f"Invalid Project ID in WebSocket: {project_id}")
        await websocket.close(code=4000)
        return

    # 3. Register for updates
    register_ws(project_id, websocket)

    # 4. Send initial snapshot
    try:
        db: Session = SessionLocal()
        try:
            stages = list_project_stages(db, pid_uuid)
            snapshot = {
                "type": "snapshot",
                "project_id": project_id,
                "stages": [
                    {
                        "stage_code": s.stage_code,
                        "status": s.status.value,
                        "started_at": s.started_at.isoformat() if s.started_at else None,
                        "completed_at": s.completed_at.isoformat() if s.completed_at else None,
                    }
                    for s in stages
                ],
            }
            await websocket.send_text(json.dumps(snapshot))
        finally:
            db.close()
    except Exception as exc:
        logger.warning(f"Failed to send WS snapshot for {project_id}: {exc}")

    # 5. Keep connection alive and respond to pings
    try:
        while True:
            # We use receive_text to listen for pings or client close
            raw = await websocket.receive_text()
            if raw.strip() == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for {project_id}")
    except Exception as exc:
        logger.error(f"WebSocket error for {project_id}: {exc}")
    finally:
        unregister_ws(project_id, websocket)
