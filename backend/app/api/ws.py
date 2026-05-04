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

router = APIRouter()


@router.websocket("/{project_id}")
async def websocket_endpoint(websocket: WebSocket, project_id: str):
    await websocket.accept()
    register_ws(project_id, websocket)

    # Send an immediate snapshot of current stage states
    try:
        db: Session = SessionLocal()
        try:
            from uuid import UUID  # noqa
            stages = list_project_stages(db, UUID(project_id))
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
        except Exception:
            pass
        finally:
            db.close()
    except Exception:
        pass

    # Keep connection alive; the orchestrator pushes updates
    try:
        while True:
            raw = await websocket.receive_text()
            # Echo ping/pong for connection health checks
            if raw.strip() == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        pass
    finally:
        unregister_ws(project_id, websocket)
