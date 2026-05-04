"""
CRUD operations for validation_results, stage_checkpoints, and audit_event_log
in the project runtime DB (steel_detailing.db).
"""
from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import AuditEventLog, StageCheckpoint, ValidationResult


# ---------------------------------------------------------------------------
# ValidationResult
# ---------------------------------------------------------------------------

def save_validation_items(
    db: Session,
    project_id: UUID,
    stage_code: str,
    items: list[dict],
) -> list[ValidationResult]:
    """
    Persist per-field validation records.

    Each dict in *items* must contain:
        field_code, status (PRESENT|MISSING|SUSPICIOUS),
        severity (CRITICAL|MAJOR|MINOR).
    Optional keys: source, value, note.
    """
    records: list[ValidationResult] = []
    for item in items:
        record = ValidationResult(
            project_id=project_id,
            stage_code=stage_code,
            field_code=item["field_code"],
            status=item["status"],
            severity=item["severity"],
            source=item.get("source"),
            value=item.get("value"),
            note=item.get("note"),
        )
        db.add(record)
        records.append(record)
    db.flush()
    return records


def get_validation_items(
    db: Session,
    project_id: UUID,
    stage_code: str | None = None,
) -> list[ValidationResult]:
    """Return all validation records for a project, optionally filtered by stage."""
    q = db.query(ValidationResult).filter(ValidationResult.project_id == project_id)
    if stage_code:
        q = q.filter(ValidationResult.stage_code == stage_code)
    return q.order_by(ValidationResult.created_at).all()


def get_validation_summary(
    db: Session,
    project_id: UUID,
    stage_code: str | None = None,
) -> dict:
    """Return counts grouped by status/severity for quick gate assessment."""
    items = get_validation_items(db, project_id, stage_code)
    summary: dict[str, Any] = {
        "total": len(items),
        "present": 0,
        "missing": 0,
        "suspicious": 0,
        "critical": 0,
        "major": 0,
        "minor": 0,
    }
    for item in items:
        status_key = item.status.lower()
        severity_key = item.severity.lower()
        if status_key in summary:
            summary[status_key] += 1
        if severity_key in summary:
            summary[severity_key] += 1
    return summary


# ---------------------------------------------------------------------------
# StageCheckpoint
# ---------------------------------------------------------------------------

def save_checkpoint(
    db: Session,
    project_id: UUID,
    stage_code: str,
    label: str,
    gate_status: str,
    gate_data: dict | None = None,
) -> StageCheckpoint:
    """
    Persist a hard-gate checkpoint.

    gate_status should be one of: PASS | FAIL | PENDING
    gate_data is serialised to JSON for evidence storage.
    """
    checkpoint = StageCheckpoint(
        project_id=project_id,
        stage_code=stage_code,
        checkpoint_label=label,
        gate_status=gate_status,
        gate_data=json.dumps(gate_data or {}, default=str),
    )
    db.add(checkpoint)
    db.flush()
    return checkpoint


def get_checkpoints(
    db: Session,
    project_id: UUID,
    stage_code: str | None = None,
) -> list[StageCheckpoint]:
    q = db.query(StageCheckpoint).filter(StageCheckpoint.project_id == project_id)
    if stage_code:
        q = q.filter(StageCheckpoint.stage_code == stage_code)
    return q.order_by(StageCheckpoint.created_at).all()


# ---------------------------------------------------------------------------
# AuditEventLog
# ---------------------------------------------------------------------------

def log_audit_event(
    db: Session,
    event_type: str,
    *,
    project_id: UUID | None = None,
    actor: str = "system",
    stage_code: str | None = None,
    field_code: str | None = None,
    detail: dict | None = None,
) -> AuditEventLog:
    """
    Write an immutable audit event to the runtime DB.

    event_type examples:
        STAGE_STARTED, STAGE_PASSED, STAGE_FAILED,
        FIELD_EXTRACTED, CONFLICT_RESOLVED, FALLBACK_APPLIED,
        CHECKPOINT_CREATED, VALIDATION_SAVED
    """
    event = AuditEventLog(
        project_id=project_id,
        event_type=event_type,
        actor=actor,
        stage_code=stage_code,
        field_code=field_code,
        detail=json.dumps(detail or {}, default=str),
    )
    db.add(event)
    db.flush()
    return event
