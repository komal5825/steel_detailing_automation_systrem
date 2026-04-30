# Phase 2 Task Location Tracker

**Purpose:** Track exactly where each Phase 2 step lives in the project.  
**How to use:** Mark the status column as done only after code, DB behavior, and verification are complete.  
**Current position:** Phase C implementation steps are complete. We are now at **Hard Gate 3 / Phase D - Step 13**.

Status legend:

- `[x]` Done
- `[ ]` Not started / pending

---

## Current Project Position

| Area | Current State |
|---|---|
| SQLite baseline | Complete |
| Backend DB config | Complete |
| Phase 2 folder structure | Complete |
| Project creation API | Complete |
| File upload and registration | Complete |
| Source classification | Complete |
| ZIP archive extraction and registration | Complete |
| MBS parser adapter | Complete |
| STAAD parser adapter | Complete |
| ETABS / Prota / PDF parser adapters | Complete |
| Field normalization | Complete |
| Completeness/rules engine | Next |
| Completeness/rules engine | Pending |
| AB/GA generation | Pending |
| Validation and handoff | Pending |

## Dependency Readiness

| Dependency | Status | Location / Endpoint | Used In |
|---|---|---|---|
| UnRAR | Available | `C:/Program Files/WinRAR/UnRAR.exe` | RAR archive extraction during upload/intake |
| ODA File Converter | Available | `C:/Program Files/ODA/ODAFileConverter 27.1.0/ODAFileConverter.exe` | DWG/DXF conversion and output flow |
| Ollama | Running | `http://localhost:11434`, model `llama3:latest` | LLM-assisted PDF/text interpretation, fallback explanations, summaries |
| Tesseract OCR | Available | `C:/Users/User/AppData/Local/Programs/Tesseract-OCR/tesseract.exe` | Scanned/image PDF OCR |

Backend readiness endpoint:

```text
GET /api/stages/dependencies/readiness
```

**Where we are exactly:**  
We have completed **Step 1 to Step 12**, passed **Hard Gate 1** and **Hard Gate 2**, and the next implementation task is:

```text
Hard Gate 3 verification, then Phase D - Step 13 - Implement Completeness Checker
```

---

# Phase A - Baseline And SQLite Readiness

## Step 1 - Confirm Folder Structure

| Status | Location |
|---|---|
| [x] | `backend/app/agents/phase2/` |
| [x] | `backend/app/parsers/` |
| [x] | `backend/app/db/` |
| [x] | `backend/app/db/crud/` |
| [x] | `backend/app/orchestrator/` |
| [x] | `backend/app/tasks/` |
| [x] | `data/projects/` |
| [x] | `data/temp/` |
| [x] | `DB/` |

**Progress meaning:** The Phase 2 codebase structure exists and is ready for implementation.

## Step 2 - Confirm SQLite Database Location

| Status | Item | Location |
|---|---|---|
| [x] | Master SQLite DB | `DB/master_db.db` |
| [x] | Backend SQLite URL | `backend/.env` |
| [x] | Runtime setting default | `backend/app/config/settings.py` |

**Progress meaning:** The project is SQLite-based. PostgreSQL is not required for Phase 2.

## Step 3 - Validate SQLite Schema Health

| Status | Item | Location |
|---|---|---|
| [x] | DB integrity check | `DB/master_db.db` |
| [x] | Master schema tables | `DB/master_db.db` |
| [x] | Phase 2 table references | `project_master`, `project_file_registry`, `project_stage_status`, `stage_checkpoint`, `field_value_store`, `validation_result`, `audit_event_log` |

**Progress meaning:** The master DB has the tables needed for ingestion, parsing, validation, checkpoints, and audit.

## Step 4 - Confirm SQLite Session Layer

| Status | Item | Location |
|---|---|---|
| [x] | SQLAlchemy engine/session | `backend/app/db/session.py` |
| [x] | SQLite PRAGMAs | `backend/app/db/session.py` |
| [x] | Settings load from `.env` | `backend/app/config/settings.py` |

**Progress meaning:** Backend DB connections now use SQLite correctly with FK enforcement and WAL mode.

## Hard Gate 1 - SQLite Baseline Gate

| Status | Gate Item | Location |
|---|---|---|
| [x] | `DATABASE_URL` is SQLite | `backend/.env` |
| [x] | SQLite DB exists / can be created | `DB/master_db.db`, `backend/app/db/steel_detailing.db` |
| [x] | Integrity check passed | `DB/master_db.db` |
| [x] | Required tables present | `DB/master_db.db` |
| [x] | PRAGMAs active | `backend/app/db/session.py` |

**Gate result:** Passed. Phase B is allowed.

---

# Phase B - Project Intake And File Registry

## Step 5 - Implement Project Creation API

| Status | Item | Location |
|---|---|---|
| [x] | Create project endpoint | `backend/app/api/projects.py` |
| [x] | Project create schema | `backend/app/schemas/project.py` |
| [x] | Project ORM model | `backend/app/db/models.py` |
| [x] | Project CRUD | `backend/app/db/crud/projects.py` |
| [x] | Initial P2 stage rows | `backend/app/db/crud/projects.py` |

**Progress meaning:** A real project can now be created and linked to Phase 2 stage tracking.

## Step 6 - Implement File Upload Storage

| Status | Item | Location |
|---|---|---|
| [x] | Upload endpoint | `backend/app/api/projects.py` |
| [x] | Project file ORM model | `backend/app/db/models.py` |
| [x] | Project file response schema | `backend/app/schemas/project.py` |
| [x] | File registration CRUD | `backend/app/db/crud/projects.py` |
| [x] | Stored files | `data/projects/{project_uuid}/input/` |

**Progress meaning:** Uploaded project files are stored and registered in SQLite.

## Step 7 - Implement Source Classification

| Status | Item | Location |
|---|---|---|
| [x] | File type enum | `backend/app/config/constants.py` |
| [x] | Source classifier | `backend/app/parsers/source_classifier.py` |
| [x] | Classification saved | `backend/app/api/projects.py`, `backend/app/db/crud/projects.py` |

**Progress meaning:** Uploaded files are now routed as STAAD, MBS, ETABS, PDF, DXF, archive, or unsupported.

## Step 8 - Implement Archive Handling

| Status | Item | Location |
|---|---|---|
| [x] | Archive extractor | `backend/app/parsers/archive_handler.py` |
| [x] | ZIP upload handling | `backend/app/api/projects.py` |
| [x] | Parent-child file relation | `backend/app/db/models.py` |
| [x] | Extracted file registration | `backend/app/api/projects.py` |

**Progress meaning:** ZIP packages can be uploaded, extracted, classified, and registered.

## Hard Gate 2 - Intake Gate

| Status | Gate Item | Location |
|---|---|---|
| [x] | Project can be created | `backend/app/api/projects.py` |
| [x] | Files can be uploaded and stored | `backend/app/api/projects.py`, `data/projects/{project_uuid}/input/` |
| [x] | Files are registered in SQLite | `backend/app/db/models.py`, `backend/app/db/crud/projects.py` |
| [x] | Source classification is saved | `backend/app/parsers/source_classifier.py` |
| [x] | Archives are extracted and registered | `backend/app/parsers/archive_handler.py` |

**Gate result:** Passed. Phase C is allowed.

---

# Phase C - Parser Adapter Implementation

## Step 9 - Implement MBS Parser Adapter

| Status | Item | Location |
|---|---|---|
| [x] | MBS parser implementation | `backend/app/parsers/mbs_parser.py` |
| [x] | Phase 2 ingestion agent integration | `backend/app/agents/phase2/p2_01_ingestion.py` |
| [x] | Extracted field persistence | `backend/app/db/crud/field_values.py` |
| [x] | Traceability logging | `backend/app/utils/traceability.py`, `backend/app/utils/audit_logger.py` |

**Progress meaning:** MBS files become structured project data.

## Step 10 - Implement STAAD Parser Adapter

| Status | Item | Location |
|---|---|---|
| [x] | STAAD parser implementation | `backend/app/parsers/staad_parser.py` |
| [x] | Phase 2 ingestion agent integration | `backend/app/agents/phase2/p2_01_ingestion.py` |
| [x] | Parser confidence logging | `backend/app/db/models.py`, `backend/app/db/crud/field_values.py` |

**Progress meaning:** STAAD `.std` files become usable engineering data.

## Step 11 - Implement ETABS / Prota / PDF Parser Adapters

| Status | Item | Location |
|---|---|---|
| [x] | ETABS parser | `backend/app/parsers/etabs_parser.py` |
| [x] | Prota parser | `backend/app/parsers/protasteel_parser.py` |
| [x] | PDF text/OCR parsing | `backend/app/parsers/pdf_parser.py` |
| [x] | Adapter routing | `backend/app/agents/phase2/p2_01_ingestion.py` |

**Progress meaning:** Phase 2 can process multiple source formats, not only MBS/STAAD.

## Step 12 - Implement Field Normalization Layer

| Status | Item | Location |
|---|---|---|
| [x] | Standard field mapping | `backend/app/utils/field_dictionary.py` |
| [x] | Unit normalization | `backend/app/utils/field_dictionary.py` |
| [x] | Alias resolution | `DB/master_db.db` tables: `alias_master`, `field_master` |
| [x] | Normalized value storage | `backend/app/db/models.py`, `backend/app/db/crud/field_values.py` |

**Progress meaning:** Raw parser output becomes standard Phase 2 field values.

## Hard Gate 3 - Parser And Normalization Gate

| Status | Gate Item | Location |
|---|---|---|
| [ ] | At least one real sample parses | `backend/app/parsers/` |
| [ ] | Extracted values saved | SQLite field value storage |
| [ ] | Field traceability stored | `backend/app/utils/traceability.py` |
| [ ] | Normalized values available by project | API/CRUD layer under `backend/app/` |
| [ ] | Parser failures logged safely | `backend/app/utils/audit_logger.py` |

**Gate result:** Pending. This is the next gate to work toward.

---

# Phase D - Completeness, Rules, And Hard Gates

## Step 13 - Implement Completeness Checker

| Status | Location |
|---|---|
| [ ] | `backend/app/agents/phase2/p2_02_completeness.py` |
| [ ] | `backend/app/db/crud/validation.py` |
| [ ] | `backend/app/schemas/validation.py` |

## Step 14 - Implement Source Priority And Conflict Rules

| Status | Location |
|---|---|
| [ ] | `DB/master_db.db` tables: `source_priority_master`, `conflict_rule_master` |
| [ ] | new rule module under `backend/app/agents/phase2/` or `backend/app/utils/` |

## Step 15 - Implement Fallback Policy

| Status | Location |
|---|---|
| [ ] | `DB/master_db.db` tables: `fallback_rule_master`, `source_fallback_chain` |
| [ ] | `backend/app/agents/support/fallback.py` |

## Step 16 - Implement Stage Checkpoint And Audit Logging

| Status | Location |
|---|---|
| [ ] | `backend/app/agents/support/checkpoint.py` |
| [ ] | `backend/app/utils/audit_logger.py` |
| [ ] | SQLite tables: `stage_checkpoint`, `audit_event_log` |

## Hard Gate 4 - Completeness And Governance Gate

| Status | Location |
|---|---|
| [ ] | `backend/app/agents/phase2/p2_02_completeness.py` |
| [ ] | `backend/app/db/crud/validation.py` |
| [ ] | `backend/app/agents/support/fallback.py` |
| [ ] | `backend/app/utils/audit_logger.py` |

---

# Phase E - AB And GA Generation

## Step 17 - Implement AB Generation Agent

| Status | Location |
|---|---|
| [ ] | `backend/app/agents/phase2/p2_03_ab_generation.py` |
| [ ] | output folder `data/projects/{project_uuid}/outputs/ab/` |

## Step 18 - Implement GA Generation Agent

| Status | Location |
|---|---|
| [ ] | `backend/app/agents/phase2/p2_04_ga_generation.py` |
| [ ] | output folder `data/projects/{project_uuid}/outputs/ga/` |

## Step 19 - Implement DXF / PDF / DWG Output Flow

| Status | Location |
|---|---|
| [ ] | `backend/app/agents/support/output_generator.py` |
| [ ] | future CAD modules under `backend/app/cad/` if added |
| [ ] | ODA config in `backend/.env` and `backend/app/config/settings.py` |

---

# Phase F - Validation, UI Status, And Release Readiness

## Step 20 - Implement AB/GA Validation Agent

| Status | Location |
|---|---|
| [ ] | `backend/app/agents/phase2/p2_05_abga_validation.py` |
| [ ] | `backend/app/agents/support/validator.py` |
| [ ] | `backend/app/db/crud/validation.py` |

## Step 21 - Implement Frontend Stage Status Updates

| Status | Location |
|---|---|
| [ ] | `backend/app/api/stages.py` |
| [ ] | `backend/app/api/ws.py` |
| [ ] | frontend status UI under `frontend/` |

## Step 22 - Implement Final Handoff Package

| Status | Location |
|---|---|
| [ ] | `backend/app/orchestrator/handoff_manager.py` |
| [ ] | `backend/app/api/handoffs.py` |
| [ ] | `backend/app/db/crud/handoffs.py` |
| [ ] | SQLite handoff/release status records |

## Hard Gate 5 - Phase 2 Release Gate

| Status | Location |
|---|---|
| [ ] | AB output: `data/projects/{project_uuid}/outputs/ab/` |
| [ ] | GA output: `data/projects/{project_uuid}/outputs/ga/` |
| [ ] | validation records in SQLite |
| [ ] | handoff package generated by `backend/app/orchestrator/handoff_manager.py` |
| [ ] | Phase 3 eligibility status saved in SQLite |

---

# Overall Progress

| Progress Item | Count |
|---|---:|
| Total implementation steps | 22 |
| Completed steps | 12 |
| Pending steps | 10 |
| Total hard gates | 5 |
| Passed hard gates | 2 |
| Pending hard gates | 3 |

**Next exact task:** verify Hard Gate 3, then implement `backend/app/agents/phase2/p2_02_completeness.py`.
