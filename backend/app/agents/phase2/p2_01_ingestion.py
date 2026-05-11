from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.agents.phase2.output_utils import write_processed_json
from app.db.crud.field_values import create_extracted_field_values, create_parser_run
from app.db.crud.stages import update_stage_result
from app.db.models import FileProcessingStatus, ParserRunStatus, ProjectFile, StageStatus
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

# Source priority for governing file selection (lower = higher priority)
_SOURCE_PRIORITY: dict[str, int] = {
    "MBS": 1,
    "STAAD": 2,
    "ETABS": 3,
    "PROTASTEEL": 4,
    "PDF": 5,
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

    all_parser_results = {}
    for project_file in files:
        parser_class = PARSER_BY_FILE_TYPE[project_file.file_type]
        parser = parser_class()
        try:
            result = parser.parse(project_file.stored_path)
            all_parser_results[project_file.id] = result
            fields = [field_dictionary.normalize_field(field) for field in result["fields"]]
            # Stamp source_path with file type so source priority engine can
            # reliably infer the source regardless of the storage directory name.
            file_type_tag = project_file.file_type
            fields = [
                {**f, "source_path": f"{file_type_tag}::{f.get('source_path', '')}"}
                for f in fields
            ]
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
                db,
                project_id,
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
                db,
                project_id,
                "p2_01_parse_failed",
                {
                    "file_id": str(project_file.id),
                    "file_type": project_file.file_type,
                    "parser": parser_class.__name__,
                    "error": str(exc),
                },
            )

    # --- Write file_inventory.json ---
    all_files = (
        db.query(ProjectFile)
        .filter(ProjectFile.project_id == project_id)
        .all()
    )
    file_inventory = {
        "project_id": str(project_id),
        "total_files": len(all_files),
        "parsed_files": parsed_files,
        "failed_files": failed_files,
        "files": [
            {
                "file_id": str(f.id),
                "original_filename": f.original_filename,
                "file_type": f.file_type,
                "file_category": f.file_category,
                "source_application": f.source_application,
                "likely_role": f.likely_role,
                "classification_confidence": f.classification_confidence,
                "processing_status": f.processing_status.value
                if hasattr(f.processing_status, "value")
                else str(f.processing_status),
            }
            for f in all_files
        ],
    }
    write_processed_json(project_id, "file_inventory.json", file_inventory)

    # --- Write governing_source.json ---
    # Select the governing design file: highest classification_confidence among parseable
    # files, with source priority (MBS > STAAD > ETABS > PROTASTEEL > PDF) as tiebreaker.
    candidates = [f for f in all_files if f.file_type in PARSER_BY_FILE_TYPE]
    governing_file = None
    if candidates:
        governing_file = max(
            candidates,
            key=lambda f: (
                f.classification_confidence,
                -_SOURCE_PRIORITY.get(f.file_type, 99),
            ),
        )

    governing_payload: dict = {
        "project_id": str(project_id),
        "governing_file": (
            {
                "file_id": str(governing_file.id),
                "original_filename": governing_file.original_filename,
                "file_type": governing_file.file_type,
                "source_application": governing_file.source_application,
                "likely_role": governing_file.likely_role,
                "classification_confidence": governing_file.classification_confidence,
            }
            if governing_file
            else None
        ),
        "selection_method": "SINGLE_FILE" if len(candidates) == 1 else "HIGHEST_CONFIDENCE_WITH_SOURCE_PRIORITY",
        "rationale": (
            f"Only one parseable file found: '{governing_file.original_filename}'"
            if len(candidates) == 1 else
            f"Selected '{governing_file.original_filename}' "
            f"(type={governing_file.file_type}, "
            f"confidence={governing_file.classification_confidence})"
            if governing_file
            else "No parseable files found"
        ),
        "candidates": [
            {
                "file_id": str(f.id),
                "original_filename": f.original_filename,
                "file_type": f.file_type,
                "classification_confidence": f.classification_confidence,
            }
            for f in sorted(
                candidates,
                key=lambda f: (
                    -f.classification_confidence,
                    _SOURCE_PRIORITY.get(f.file_type, 99),
                ),
            )
        ],
    }
    write_processed_json(project_id, "governing_source.json", governing_payload)

    governing_details = {}
    if governing_file and governing_file.id in all_parser_results:
        res = all_parser_results[governing_file.id]
        for f in res.get("fields", []):
            if f["field_name"] in ["node_count", "member_count", "support_count", "job_date", "unit_system"]:
                governing_details[f["field_name"]] = f["raw_value"]

    overall_status = "PASS"
    if parsed_files == 0 and failed_files > 0:
        overall_status = "FAIL"
    elif failed_files > 0:
        overall_status = "PASS_WITH_WARNINGS"
    elif len(files) == 0:
        overall_status = "BLOCKED"

    result = {
        "status": "success" if failed_files == 0 else "partial_success",
        "overall": overall_status,
        "project_id": str(project_id),
        "files_found": len(files),
        "parsed_files": parsed_files,
        "failed_files": failed_files,
        "extracted_fields": extracted_fields,
        "normalized_fields": normalized_fields,
        "governing_file": governing_payload["governing_file"],
        "governing_details": governing_details,
        "main_output": "reports/p2-01_summary.json",
    }
    write_processed_json(project_id, "p2-01_summary.json", result)
    
    # Map overall_status string back to StageStatus enum for DB
    db_status = StageStatus.PASSED
    if overall_status == "PASS_WITH_WARNINGS":
        db_status = StageStatus.PASS_WITH_WARNINGS
    elif overall_status == "FAIL":
        db_status = StageStatus.FAILED
    elif overall_status == "BLOCKED":
        db_status = StageStatus.BLOCKED

    update_stage_result(
        db,
        project_id=project_id,
        stage_code="P2-01",
        status=db_status,
        result=result,
    )
    db.commit()
    return result
