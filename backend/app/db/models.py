import uuid
from datetime import datetime
from sqlalchemy import CHAR, Column, String, Integer, DateTime, Text, ForeignKey, Enum as SAEnum
from sqlalchemy.types import TypeDecorator
from sqlalchemy.orm import relationship
from app.db.session import Base
import enum


class GUID(TypeDecorator):
    """Platform-independent UUID storage.

    SQLite stores UUID values as 36-character strings, while PostgreSQL can use
    its native UUID type later if the project ever moves databases.
    """

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import UUID

            return dialect.type_descriptor(UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if not isinstance(value, uuid.UUID):
            value = uuid.UUID(str(value))
        return value if dialect.name == "postgresql" else str(value)

    def process_result_value(self, value, dialect):
        if value is None or isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))

class ProjectStatus(str, enum.Enum):
    CREATED = "CREATED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class StageStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PASSED = "PASSED"
    PASS_WITH_WARNINGS = "PASS_WITH_WARNINGS"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    SKIPPED = "SKIPPED"
    AWAITING_INPUT = "AWAITING_INPUT"


class FileProcessingStatus(str, enum.Enum):
    PENDING = "PENDING"
    PARSED = "PARSED"
    EXTRACTED = "EXTRACTED"
    UNSUPPORTED = "UNSUPPORTED"
    FAILED = "FAILED"


class ParserRunStatus(str, enum.Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"

class Project(Base):
    __tablename__ = "projects"
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    proposal_id = Column(String(50), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    location = Column(String(255))
    project_type = Column(String(100))
    status = Column(SAEnum(ProjectStatus), default=ProjectStatus.CREATED)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    stages = relationship("Stage", back_populates="project")
    files = relationship("ProjectFile", back_populates="project")

class Stage(Base):
    __tablename__ = "stages"
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    project_id = Column(GUID(), ForeignKey("projects.id"), nullable=False)
    stage_code = Column(String(10), nullable=False)  # e.g. P2-01
    status = Column(SAEnum(StageStatus), default=StageStatus.PENDING)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    error_message = Column(Text)
    result_json = Column(Text)   # JSON-serialised output summary
    revision = Column(Integer, default=1)
    project = relationship("Project", back_populates="stages")


class ProjectFile(Base):
    __tablename__ = "project_files"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    project_id = Column(GUID(), ForeignKey("projects.id"), nullable=False)
    original_filename = Column(String(500), nullable=False)
    stored_path = Column(String(1000), nullable=False)
    file_extension = Column(String(20))
    file_type = Column(String(50), nullable=False)
    file_category = Column(String(100), nullable=False)
    source_application = Column(String(100), nullable=False)
    likely_role = Column(String(100), nullable=False)
    classification_confidence = Column(Integer, nullable=False, default=0)
    processing_status = Column(SAEnum(FileProcessingStatus), default=FileProcessingStatus.PENDING)
    parent_file_id = Column(GUID(), ForeignKey("project_files.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="files")


class ParserRun(Base):
    __tablename__ = "parser_runs"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    project_id = Column(GUID(), ForeignKey("projects.id"), nullable=False)
    project_file_id = Column(GUID(), ForeignKey("project_files.id"), nullable=False)
    parser_name = Column(String(100), nullable=False)
    status = Column(SAEnum(ParserRunStatus), nullable=False)
    confidence = Column(Integer, nullable=False, default=0)
    message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class ExtractedFieldValue(Base):
    __tablename__ = "extracted_field_values"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    project_id = Column(GUID(), ForeignKey("projects.id"), nullable=False)
    project_file_id = Column(GUID(), ForeignKey("project_files.id"), nullable=False)
    parser_run_id = Column(GUID(), ForeignKey("parser_runs.id"), nullable=False)
    field_code = Column(String(100), nullable=False)
    field_name = Column(String(255), nullable=False)
    raw_value = Column(Text, nullable=False)
    normalized_value = Column(Text, nullable=False)
    unit = Column(String(50))
    source_path = Column(String(1000), nullable=False)
    confidence = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

class Handoff(Base):
    __tablename__ = "handoffs"
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    project_id = Column(GUID(), ForeignKey("projects.id"), nullable=False)
    from_stage = Column(String(10), nullable=False)
    to_stage = Column(String(10), nullable=False)
    package_path = Column(String(500))   # path to handoff JSON
    approved = Column(Integer, default=0)  # 0=pending, 1=approved, -1=rejected
    approved_by = Column(String(100))
    approved_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

class Escalation(Base):
    __tablename__ = "escalations"
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    project_id = Column(GUID(), ForeignKey("projects.id"), nullable=False)
    stage_code = Column(String(10))
    severity = Column(String(20))   # CRITICAL / MAJOR / MINOR
    reason = Column(Text)
    evidence = Column(Text)
    status = Column(String(20), default="OPEN")  # OPEN / RESOLVED
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime)

class CorrectionEvent(Base):
    __tablename__ = "correction_events"
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    project_id = Column(GUID(), ForeignKey("projects.id"), nullable=False)
    stage_code = Column(String(10))
    field_code = Column(String(100))
    original_value = Column(Text)
    corrected_value = Column(Text)
    source = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)

class RuleProposal(Base):
    __tablename__ = "rule_proposals"
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    field_code = Column(String(100))
    proposed_rule = Column(Text)
    rationale = Column(Text)
    status = Column(String(20), default="PENDING")  # PENDING / APPROVED / REJECTED
    created_at = Column(DateTime, default=datetime.utcnow)
    reviewed_at = Column(DateTime)


class ValidationResult(Base):
    """Per-field validation record produced by the completeness checker."""
    __tablename__ = "validation_results"
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    project_id = Column(GUID(), ForeignKey("projects.id"), nullable=False)
    stage_code = Column(String(10), nullable=False)
    field_code = Column(String(100), nullable=False)
    status = Column(String(20), nullable=False)    # PRESENT / MISSING / SUSPICIOUS
    severity = Column(String(20), nullable=False)  # CRITICAL / MAJOR / MINOR
    source = Column(String(100))
    value = Column(Text)
    note = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class StageCheckpoint(Base):
    """Hard-gate checkpoint record written by CheckpointManager."""
    __tablename__ = "stage_checkpoints"
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    project_id = Column(GUID(), ForeignKey("projects.id"), nullable=False)
    stage_code = Column(String(10), nullable=False)
    checkpoint_label = Column(String(200), nullable=False)
    gate_status = Column(String(20), nullable=False)   # PASS / FAIL / PENDING
    gate_data = Column(Text)                           # JSON-serialised evidence
    created_at = Column(DateTime, default=datetime.utcnow)


class AuditEventLog(Base):
    """Immutable audit trail for every significant system action."""
    __tablename__ = "audit_event_log"
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    project_id = Column(GUID(), ForeignKey("projects.id"), nullable=True)
    event_type = Column(String(100), nullable=False)
    actor = Column(String(100))
    stage_code = Column(String(10))
    field_code = Column(String(100))
    detail = Column(Text)   # JSON
    created_at = Column(DateTime, default=datetime.utcnow)


class ReportType(str, enum.Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    BM = "BM"


class ReportRecord(Base):
    """Stores metadata and payload for every generated automated report."""
    __tablename__ = "report_records"
    id            = Column(GUID(), primary_key=True, default=uuid.uuid4)
    project_id    = Column(GUID(), ForeignKey("projects.id"), nullable=True)
    report_type   = Column(SAEnum(ReportType), nullable=False)
    report_date   = Column(String(20), nullable=False)   # YYYY-MM-DD / YYYY-WNN / YYYY-MM
    sequence      = Column(Integer, default=1)            # 001, 002 … same day/run counter
    report_id_str = Column(String(200))                  # named ID: daily_proj-uuid_v2.0_2026-05-06_001
    report_data   = Column(Text)                          # JSON payload
    generated_at  = Column(DateTime, default=datetime.utcnow)
    generated_by  = Column(String(100), default="automated_reporting_layer")
    build_version = Column(String(50), default="2.0")
    export_path   = Column(String(500))                  # path to primary JSON file on disk
    qc_status     = Column(String(20), default="pending") # pending / approved / rejected
    signed_off_by = Column(String(100))
    signed_off_at = Column(DateTime)


class AgentExecutionLog(Base):
    """Persistent per-attempt execution trace for stage agents."""
    __tablename__ = "agent_execution_logs"
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    project_id = Column(GUID(), ForeignKey("projects.id"), nullable=False)
    stage_code = Column(String(10), nullable=False)
    trigger_type = Column(String(30), nullable=False, default="manual")
    status = Column(String(20), nullable=False, default="RUNNING")
    input_payload = Column(Text)
    output_payload = Column(Text)
    error_message = Column(Text)
    root_cause = Column(Text)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
