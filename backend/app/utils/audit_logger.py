"""
Audit logger — Phase 2 Step 16.

Two layers:
  1. File-based Python logger  — always on; writes to data/logs/audit.log
  2. DB audit event helper     — thin wrapper around crud/validation.log_audit_event

The DB layer is optional; callers that have a live session call
``log_to_db()``.  Callers without a session just use ``get_logger()``.
"""
from __future__ import annotations

import logging
import os
from uuid import UUID

from app.config.settings import settings

# ---------------------------------------------------------------------------
# File-based logger (always initialised at import time)
# ---------------------------------------------------------------------------

log_file_path = os.path.join(settings.log_base_path, "audit.log")
os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

_file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
_file_handler.setFormatter(
    logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
)

_root_audit = logging.getLogger("audit")
_root_audit.setLevel(logging.INFO)
if not _root_audit.handlers:
    _root_audit.addHandler(_file_handler)
    _root_audit.propagate = False


def get_logger(name: str) -> logging.Logger:
    """Return a child logger under the 'audit' hierarchy."""
    child = logging.getLogger(f"audit.{name}")
    if not child.handlers:
        child.addHandler(_file_handler)
        child.propagate = False
    return child


# ---------------------------------------------------------------------------
# DB audit event helper
# ---------------------------------------------------------------------------

def log_to_db(
    db,
    event_type: str,
    *,
    project_id: UUID | None = None,
    actor: str = "system",
    stage_code: str | None = None,
    field_code: str | None = None,
    detail: dict | None = None,
) -> None:
    """
    Write an audit event to the runtime DB.

    Imports lazily to avoid circular imports at module load time.
    Silently swallows exceptions so logging never crashes the pipeline.
    """
    try:
        from app.db.crud.validation import log_audit_event  # noqa: PLC0415
        log_audit_event(
            db,
            event_type,
            project_id=project_id,
            actor=actor,
            stage_code=stage_code,
            field_code=field_code,
            detail=detail,
        )
    except Exception as exc:
        _root_audit.warning("DB audit write failed (%s): %s", event_type, exc)
