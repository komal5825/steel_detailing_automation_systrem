from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import ExtractedFieldValue, ParserRun, ParserRunStatus


def create_parser_run(
    db: Session,
    *,
    project_id: UUID,
    project_file_id: UUID,
    parser_name: str,
    status: ParserRunStatus,
    confidence: int,
    message: str | None = None,
) -> ParserRun:
    parser_run = ParserRun(
        project_id=project_id,
        project_file_id=project_file_id,
        parser_name=parser_name,
        status=status,
        confidence=confidence,
        message=message,
    )
    db.add(parser_run)
    db.flush()
    return parser_run


def create_extracted_field_values(
    db: Session,
    *,
    project_id: UUID,
    project_file_id: UUID,
    parser_run_id: UUID,
    fields: list[dict],
) -> list[ExtractedFieldValue]:
    values = [
        ExtractedFieldValue(
            project_id=project_id,
            project_file_id=project_file_id,
            parser_run_id=parser_run_id,
            field_code=field["field_code"],
            field_name=field["field_name"],
            raw_value=str(field["raw_value"]),
            normalized_value=str(field.get("normalized_value", field["raw_value"])),
            unit=field.get("unit"),
            source_path=field["source_path"],
            confidence=int(field.get("confidence", 0)),
        )
        for field in fields
    ]
    db.add_all(values)
    db.flush()
    return values
