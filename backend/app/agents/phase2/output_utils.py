from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from app.config.settings import settings
from app.db.models import ExtractedFieldValue


def project_output_dir(project_id: UUID, output_type: str) -> Path:
    root = Path(settings.project_data_root)
    path = root / str(project_id) / "outputs" / output_type
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_project_field_map(db: Session, project_id: UUID) -> dict[str, str]:
    values = (
        db.query(ExtractedFieldValue)
        .filter(ExtractedFieldValue.project_id == project_id)
        .order_by(ExtractedFieldValue.created_at)
        .all()
    )
    field_map: dict[str, str] = {}
    for value in values:
        field_map[value.field_code] = value.normalized_value
    return field_map


def write_json_output(project_id: UUID, output_type: str, filename: str, payload: dict) -> Path:
    output_path = project_output_dir(project_id, output_type) / filename
    output_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return output_path
