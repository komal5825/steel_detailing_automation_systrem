from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.db.crud.field_values import create_extracted_field_values, create_parser_run
from app.db.crud.stages import update_stage_result
from app.db.models import FileProcessingStatus, ParserRunStatus, ProjectFile
from app.db.session import SessionLocal
from app.parsers.etabs_parser import EtabsParser
from app.parsers.mbs_parser import MBSParser
from app.parsers.pdf_parser import PDFParser
from app.parsers.protasteel_parser import ProtaSteelParser
from app.parsers.staad_parser import StaadParser
from app.utils.field_dictionary import get_field_dictionary
from app.utils.traceability import trace_action


PARSER_BY_FILE_TYPE = {
    "DXF": ProtaSteelParser,
    "ETABS": EtabsParser,
    "EXCEL": EtabsParser,
    "MBS": MBSParser,
    "PDF": PDFParser,
    "PROTASTEEL": ProtaSteelParser,
    "STAAD": StaadParser,
}


def run_ingestion(project_id: str, db: Session | None = None) -> dict:
    owns_session = db is None
    session = db or SessionLocal()
    try:
        return _run_ingestion(UUID(str(project_id)), session)
    finally:
        if owns_session:
            session.close()


def _run_ingestion(project_id: UUID, db: Session) -> dict:
    files = (
        db.query(ProjectFile)
        .filter(ProjectFile.project_id == project_id)
        .filter(ProjectFile.file_type.in_(PARSER_BY_FILE_TYPE.keys()))
        .all()
    )

    parsed_files = 0
    failed_files = 0
    extracted_fields = 0
    normalized_fields = 0
    field_dictionary = get_field_dictionary()

    for project_file in files:
        parser_class = PARSER_BY_FILE_TYPE[project_file.file_type]
        parser = parser_class()
        try:
            result = parser.parse(project_file.stored_path)
            fields = [field_dictionary.normalize_field(field) for field in result["fields"]]
            normalized_fields += sum(
                1
                for original, normalized in zip(result["fields"], fields)
                if original["field_code"] != normalized["field_code"]
            )
            parser_run = create_parser_run(
                db,
                project_id=project_id,
                project_file_id=project_file.id,
                parser_name=result["parser"],
                status=ParserRunStatus.SUCCESS,
                confidence=result["confidence"],
                message=f"Extracted {result['field_count']} fields",
            )
            create_extracted_field_values(
                db,
                project_id=project_id,
                project_file_id=project_file.id,
                parser_run_id=parser_run.id,
                fields=fields,
            )
            project_file.processing_status = FileProcessingStatus.PARSED
            parsed_files += 1
            extracted_fields += result["field_count"]
            trace_action(
                str(project_id),
                "p2_01_parse_success",
                {
                    "file_id": str(project_file.id),
                    "file_type": project_file.file_type,
                    "parser": result["parser"],
                    "field_count": result["field_count"],
                    "normalized_count": normalized_fields,
                },
            )
        except Exception as exc:
            create_parser_run(
                db,
                project_id=project_id,
                project_file_id=project_file.id,
                parser_name=parser_class.__name__,
                status=ParserRunStatus.FAILED,
                confidence=0,
                message=str(exc),
            )
            project_file.processing_status = FileProcessingStatus.FAILED
            failed_files += 1
            trace_action(
                str(project_id),
                "p2_01_parse_failed",
                {
                    "file_id": str(project_file.id),
                    "file_type": project_file.file_type,
                    "parser": parser_class.__name__,
                    "error": str(exc),
                },
            )

    result = {
        "status": "success" if failed_files == 0 else "partial_success",
        "project_id": str(project_id),
        "files_found": len(files),
        "parsed_files": parsed_files,
        "failed_files": failed_files,
        "extracted_fields": extracted_fields,
        "normalized_fields": normalized_fields,
    }
    update_stage_result(
        db,
        project_id=project_id,
        stage_code="P2-01",
        status=StageStatus.PASSED if failed_files == 0 else StageStatus.FAILED,
        result=result,
    )
    db.commit()
    return result
