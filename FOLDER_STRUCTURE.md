# Infiniti Solutions — Steel Detailing System · Execution Folder Structure

> **Complete directory layout for source code, runtime data, project files, and outputs**
> Every path explained with purpose, file types, access rules, and lifecycle notes

---

## Table of Contents

1. [Repository Root](#1-repository-root)
2. [Backend Source Tree](#2-backend-source-tree)
3. [Frontend Source Tree](#3-frontend-source-tree)
4. [Runtime Data Directories](#4-runtime-data-directories)
5. [Per-Project Folder Structure](#5-per-project-folder-structure)
6. [Reference Jobs Folder (50 Jobs)](#6-reference-jobs-folder-50-jobs)
7. [Master Database Data Files](#7-master-database-data-files)
8. [Logs & Audit Trail](#8-logs--audit-trail)
9. [ChromaDB Persistence](#9-chromadb-persistence)
10. [ODA File Converter Paths](#10-oda-file-converter-paths)
11. [Naming Conventions](#11-naming-conventions)
12. [Access & Lifecycle Rules](#12-access--lifecycle-rules)
13. [Backup Strategy](#13-backup-strategy)
14. [Environment Paths Reference](#14-environment-paths-reference)

---

## 1. Repository Root

```
infiniti-steel-agent/                    ← Git repository root
│
├── backend/                             ← FastAPI + LangGraph Python backend
├── frontend/                            ← React + Vite frontend
├── data/                                ← ALL runtime data (gitignored)
│   ├── projects/                        ← Per-project execution data
│   ├── reference_jobs/                  ← 50 training reference jobs
│   ├── chromadb/                        ← ChromaDB vector database persistence
│   ├── master_db_exports/               ← Phase 1 JSON export snapshots
│   ├── temp/                            ← Temporary processing files
│   └── logs/                            ← Application-level logs
│
├── docs/                                ← Project documentation
│   ├── Infiniti_Steel_Agent_Architecture_v1.0.docx
│   ├── Infiniti_Steel_Agent_System.html
│   ├── README.md                        ← System overview
│   ├── README_BACKEND.md                ← Backend developer reference
│   ├── README_FRONTEND.md               ← Frontend developer reference
│   └── FOLDER_STRUCTURE.md             ← This file
│
├── scripts/                             ← One-time setup and utility scripts
│   ├── init_db.py                       ← Create all PostgreSQL tables
│   ├── seed_phase1.py                   ← Run Phase 1 on 50 reference jobs
│   └── check_oda.py                     ← Verify ODA File Converter path
│
├── .gitignore                           ← Ignores: data/, .env, venv/, node_modules/
├── docker-compose.yml                   ← PostgreSQL + Redis local setup
└── README.md                            ← Top-level README
```

---

## 2. Backend Source Tree

```
backend/
│
├── main.py                              ← FastAPI app entry point
│                                          Creates app, registers routers,
│                                          starts WebSocket manager on startup
│
├── requirements.txt                     ← Python package list
├── .env                                 ← Environment config (NEVER committed)
├── .env.example                         ← Template with all required keys
│
├── alembic/                             ← Database migration management
│   ├── alembic.ini                      ← DB connection URL + migration settings
│   ├── env.py                           ← Migration env (imports all models)
│   └── versions/                        ← Auto-generated migration scripts
│       ├── 001_initial_tables.py
│       ├── 002_add_master_db_tables.py
│       └── 003_add_learning_tables.py
│
└── app/
    │
    ├── api/                             ← HTTP routes (FastAPI routers)
    │   ├── __init__.py
    │   ├── projects.py                  ← POST/GET projects, file upload
    │   ├── stages.py                    ← Stage status, approve, re-run
    │   ├── handoffs.py                  ← Handoff package read
    │   ├── outputs.py                   ← Output files, download
    │   ├── learning.py                  ← Rule proposals, suggestions
    │   └── ws.py                        ← WebSocket endpoint /ws/{uuid}
    │
    ├── orchestrator/                    ← Master Orchestration Agent
    │   ├── controller.py                ← Main evaluate_stage() logic
    │   ├── dependency_checker.py        ← Prereq validation per stage
    │   ├── cascade_manager.py           ← Re-run cascade rules table
    │   ├── handoff_manager.py           ← Create/validate handoff packages
    │   └── status_model.py             ← StageStatus enum definition
    │
    ├── agents/
    │   │
    │   ├── phase1/                      ← Master DB creation (one-time)
    │   │   ├── p1_01_template_extraction.py
    │   │   ├── p1_02_field_dictionary.py
    │   │   ├── p1_03_source_mapping.py
    │   │   ├── p1_04_validation_rules.py
    │   │   └── p1_05_db_consolidator.py
    │   │
    │   ├── phase2/                      ← Per-project AB/GA (sequential)
    │   │   ├── p2_01_ingestion.py       ← File scan, classify, rank
    │   │   ├── p2_02_completeness.py    ← Field-by-field readiness check
    │   │   ├── p2_03_ab_generation.py   ← AB data package builder
    │   │   ├── p2_04_ga_generation.py   ← GA data package (after AB only)
    │   │   └── p2_05_abga_validation.py ← Cross-validation gate
    │   │
    │   ├── phase3/                      ← Per-project detailing & release
    │   │   ├── p3_01_sheeting.py
    │   │   ├── p3_02_shop_detail.py
    │   │   ├── p3_03_shipping.py
    │   │   ├── p3_04_installation.py
    │   │   └── p3_05_final_check.py
    │   │
    │   └── support/                     ← Infrastructure agents
    │       ├── validator.py             ← StageValidator class
    │       ├── fallback.py              ← FallbackAgent class (1 retry)
    │       ├── checkpoint.py            ← State snapshot save/restore
    │       ├── state_tracker.py         ← DB status updates
    │       ├── notification.py          ← WebSocket broadcast
    │       ├── escalation.py            ← Escalation creation + routing
    │       └── output_generator.py      ← DXF→DWG→PDF pipeline
    │
    ├── learning/                        ← Three-level learning service
    │   ├── correction_listener.py       ← Logs to correction_events table
    │   ├── rule_analyser.py             ← Reads events, writes proposals
    │   ├── suggestion_engine.py         ← ChromaDB query + suggestion build
    │   └── vector_updater.py            ← Embeds approved project profiles
    │
    ├── parsers/                         ← Data extraction layer
    │   ├── staad_parser.py              ← .std plain text parser
    │   ├── mbs_parser.py                ← MBS XML/text export parser
    │   ├── etabs_parser.py              ← ETABS Excel export (openpyxl)
    │   ├── prota_parser.py              ← Prota Steel DXF + PDF
    │   ├── dwg_dxf_parser.py            ← ezdxf + ODA wrapper
    │   ├── pdf_text_parser.py           ← pdfplumber text extraction
    │   ├── pdf_image_parser.py          ← PyMuPDF + Tesseract OCR
    │   ├── archive_handler.py           ← ZIP + RAR recursive extract
    │   └── source_classifier.py         ← File type/role classification
    │
    ├── cad/                             ← CAD output generation
    │   ├── dxf_builder.py               ← ezdxf drawing construction
    │   ├── oda_converter.py             ← ODA File Converter subprocess wrapper
    │   ├── pdf_renderer.py              ← matplotlib DXF→PDF renderer
    │   └── template_populator.py        ← Map master DB template → DXF layout
    │
    ├── db/                              ← Database access layer
    │   ├── session.py                   ← SQLAlchemy engine + session factory
    │   ├── models.py                    ← All ORM model classes
    │   └── crud/                        ← CRUD functions per entity
    │       ├── projects.py
    │       ├── stages.py
    │       ├── handoffs.py
    │       ├── validation.py
    │       ├── learning.py
    │       └── master_db.py
    │
    ├── schemas/                         ← Pydantic API models
    │   ├── project.py
    │   ├── stage.py
    │   ├── handoff.py
    │   ├── validation.py
    │   ├── output.py
    │   └── learning.py
    │
    ├── tasks/                           ← Celery async task definitions
    │   ├── celery_app.py                ← Celery instance + config
    │   ├── phase1_tasks.py
    │   ├── phase2_tasks.py
    │   ├── phase3_tasks.py
    │   └── learning_tasks.py
    │
    ├── vector/                          ← ChromaDB interface
    │   ├── chroma_client.py             ← ChromaDB client init
    │   ├── embedder.py                  ← Project profile → vector
    │   └── searcher.py                  ← Similarity queries
    │
    ├── config/
    │   ├── settings.py                  ← All config from .env (Pydantic settings)
    │   └── constants.py                 ← Stage codes, status enums, failure classes
    │
    └── utils/
        ├── file_utils.py                ← Path helpers, UUID generation
        ├── traceability.py              ← Traceability matrix builder
        └── audit_logger.py              ← Structured audit log writer
```

---

## 3. Frontend Source Tree

```
frontend/
│
├── index.html                           ← Vite HTML entry point
├── vite.config.js                       ← Vite + React plugin config
├── tailwind.config.js                   ← Tailwind theme extension
├── postcss.config.js                    ← PostCSS (needed for Tailwind)
├── package.json
├── .env                                 ← VITE_API_BASE_URL etc.
│
└── src/
    ├── main.jsx                         ← React DOM render entry
    ├── App.jsx                          ← Router + global providers
    │
    ├── pages/                           ← One component per route
    │   ├── Dashboard.jsx                ← All projects grid
    │   ├── NewProject.jsx               ← Create project + upload files
    │   ├── ProjectDetail.jsx            ← Live stage tracking (main screen)
    │   ├── StageDetail.jsx              ← Drilldown into one stage
    │   ├── ValidationReport.jsx         ← Full validation matrix for a stage
    │   ├── EscalationInbox.jsx          ← All open escalations
    │   ├── EscalationDetail.jsx         ← Review + resolve one escalation
    │   ├── RuleProposals.jsx            ← Learning agent rule proposals list
    │   ├── RuleProposalDetail.jsx       ← Diff view + approve/reject
    │   ├── Outputs.jsx                  ← Release gate + output downloads
    │   └── Settings.jsx                 ← App config (ODA path, LLM model)
    │
    ├── components/
    │   ├── layout/
    │   │   ├── Sidebar.jsx              ← Navigation (Projects, Escalations, Rules)
    │   │   ├── TopBar.jsx               ← Project name + status + WS indicator
    │   │   └── PageWrapper.jsx          ← Page padding + heading
    │   │
    │   ├── project/
    │   │   ├── ProjectCard.jsx          ← Dashboard tile per project
    │   │   ├── ProjectStatusBadge.jsx
    │   │   ├── FileUploadPanel.jsx      ← Drag-and-drop file upload
    │   │   ├── FileInventoryTable.jsx   ← P2-01 classification results
    │   │   └── RevisionConflictPanel.jsx ← Human: pick governing design file
    │   │
    │   ├── stages/
    │   │   ├── StageStatusBoard.jsx     ← Full 10-stage colour-coded table
    │   │   ├── StageRow.jsx             ← Single stage row
    │   │   ├── StageProgressBar.jsx     ← % complete progress bar
    │   │   ├── StageTimeline.jsx        ← Visual flow with icons
    │   │   ├── CheckpointTrail.jsx      ← CP1→CP2→CP3 with rollback
    │   │   └── LiveLogPanel.jsx         ← WebSocket log stream
    │   │
    │   ├── decisions/                   ← All human gate components
    │   │   ├── MissingFieldPanel.jsx    ← P2-02 missing field input
    │   │   ├── SuggestionPopup.jsx      ← Level 2 Accept/Reject popup
    │   │   ├── EscalationCard.jsx       ← Escalation summary card
    │   │   ├── FallbackAlertBanner.jsx  ← Alert: fallback was triggered
    │   │   ├── HandoffApprovalPanel.jsx ← Stage handoff approval
    │   │   └── FinalReleaseGate.jsx     ← P3-05 release approval + output selection
    │   │
    │   ├── validation/
    │   │   ├── ValidationMatrix.jsx     ← Field-by-field validation table
    │   │   ├── ValidationRow.jsx
    │   │   ├── SeverityBadge.jsx        ← CRITICAL / MAJOR / MINOR
    │   │   ├── FailureClassTag.jsx      ← FIELD_MISSING, GEOMETRY_CONFLICT etc.
    │   │   └── ValidationSummaryCard.jsx
    │   │
    │   ├── learning/
    │   │   ├── RuleDiffViewer.jsx       ← Old vs proposed rule side-by-side
    │   │   ├── RuleProposalCard.jsx
    │   │   ├── CorrectionEventsList.jsx
    │   │   └── LearningActivityLog.jsx
    │   │
    │   ├── outputs/
    │   │   ├── OutputPackageCard.jsx    ← AB/GA/Shop etc. with file links
    │   │   ├── OutputFileRow.jsx        ← DXF / DWG / PDF download row
    │   │   ├── ReleaseChecklist.jsx     ← Pre-release summary
    │   │   └── OutputSelectionPanel.jsx ← Choose which outputs to generate
    │   │
    │   └── shared/
    │       ├── StatusBadge.jsx
    │       ├── InfoBox.jsx
    │       ├── ConfirmDialog.jsx
    │       ├── LoadingSpinner.jsx
    │       ├── EmptyState.jsx
    │       ├── ErrorBoundary.jsx
    │       └── Tooltip.jsx
    │
    ├── hooks/
    │   ├── useWebSocket.js              ← WS connection + message routing
    │   ├── useProject.js
    │   ├── useStages.js
    │   ├── useEscalations.js
    │   ├── useOutputs.js
    │   └── useLearning.js
    │
    ├── api/                             ← Axios API client
    │   ├── client.js                    ← Axios instance + interceptors
    │   ├── projects.js
    │   ├── stages.js
    │   ├── validations.js
    │   ├── escalations.js
    │   ├── outputs.js
    │   └── learning.js
    │
    ├── store/                           ← Zustand global state
    │   ├── projectStore.js
    │   ├── wsStore.js
    │   ├── notificationStore.js
    │   └── userStore.js
    │
    ├── constants/
    │   ├── stages.js                    ← Stage code → name mapping
    │   ├── statusColors.js              ← Tailwind classes per status
    │   ├── failureClasses.js
    │   └── outputTypes.js
    │
    └── utils/
        ├── formatters.js
        ├── statusHelpers.js
        └── downloadHelpers.js
```

---

## 4. Runtime Data Directories

These directories are under `data/` at the repo root. They are gitignored. Paths are configured via `.env`.

```
data/
│
├── projects/                            ← One subfolder per project (UUID-named)
│   ├── {project_uuid_1}/
│   ├── {project_uuid_2}/
│   └── ...
│
├── reference_jobs/                      ← 50 training reference jobs
│   ├── JOB-001/
│   ├── JOB-002/
│   └── ...
│
├── chromadb/                            ← ChromaDB local persistence
│   ├── chroma.sqlite3                   ← Main ChromaDB index
│   └── {collection_id}/
│       └── data_level0.bin              ← HNSW index binary
│
├── master_db_exports/                   ← Phase 1 JSON exports (review copies)
│   ├── phase1_run_2026-04-17/
│   │   ├── template_library.json
│   │   ├── field_dictionary.json
│   │   ├── source_mapping_rules.json
│   │   ├── validation_rules.json
│   │   └── phase1_summary_report.json
│   └── phase1_run_YYYY-MM-DD/
│
├── temp/                                ← Temp files during processing
│   ├── extracted_archives/              ← Unpacked ZIP/RAR contents
│   ├── oda_input/                       ← DXF files waiting for ODA conversion
│   └── oda_output/                      ← DWG files returned from ODA
│
└── logs/
    ├── app.log                          ← General application log
    ├── celery.log                       ← Celery worker log
    ├── audit.log                        ← Immutable audit trail
    └── error.log                        ← Error-only log
```

---

## 5. Per-Project Folder Structure

Every project gets a folder named by its internal UUID under `data/projects/`.

```
data/projects/{project_uuid}/
│
├── project_meta.json                    ← Project ID, name, location, type, status
│                                          Written at project creation, read-only after
│
├── Raw_Inputs/                          ← All uploaded files, preserved as received
│   ├── model_latest.std                 ← STAAD Pro design file
│   ├── model_old.std                    ← Older revision (if present)
│   ├── general_arrangement.dwg          ← Reference GA drawing
│   ├── ab_reference.dwg                 ← Reference AB drawing
│   ├── notes.pdf                        ← Any PDF document
│   ├── plates_list.xlsx                 ← Supporting spreadsheet
│   └── project_files.rar                ← Original archive (preserved)
│                                          Files are never modified in Raw_Inputs/
│
├── Processed/                           ← Intermediate parsed/normalized data
│   ├── file_inventory.json              ← P2-01 output: all files classified
│   ├── governing_source.json            ← Selected governing design file + reason
│   ├── extracted_staad.json             ← STAAD parser output (normalized)
│   ├── extracted_mbs.json               ← MBS parser output (if applicable)
│   ├── completeness_matrix.json         ← P2-02 field-by-field check results
│   ├── ab_structured_package.json       ← P2-03 structured AB data
│   ├── ga_structured_package.json       ← P2-04 structured GA data
│   ├── abga_validation_report.json      ← P2-05 cross-validation results
│   ├── sheeting_package.json            ← P3-01 output
│   ├── shop_detail_package.json         ← P3-02 output
│   ├── shipping_package.json            ← P3-03 output
│   ├── installation_package.json        ← P3-04 output
│   └── final_check_report.json          ← P3-05 supervisor report
│
├── Outputs/                             ← Generated drawing files
│   ├── AB/
│   │   ├── {project_id}_AB_Rev01.dxf    ← ezdxf-generated DXF
│   │   ├── {project_id}_AB_Rev01.dwg    ← ODA-converted DWG (R2018)
│   │   └── {project_id}_AB_Rev01.pdf    ← matplotlib-rendered PDF
│   │
│   ├── GA/
│   │   ├── {project_id}_GA_Rev01.dxf
│   │   ├── {project_id}_GA_Rev01.dwg
│   │   └── {project_id}_GA_Rev01.pdf
│   │
│   ├── SHOP/
│   │   ├── {project_id}_SHOP_Rev01.dxf
│   │   ├── {project_id}_SHOP_Rev01.dwg
│   │   └── {project_id}_SHOP_Rev01.pdf
│   │
│   ├── SHEETING/
│   │   ├── {project_id}_SHEETING_Rev01.dxf
│   │   └── {project_id}_SHEETING_LIST_Rev01.pdf
│   │
│   ├── SHIPPING/
│   │   ├── {project_id}_SHIPPING_Rev01.xlsx
│   │   └── {project_id}_SHIPPING_Rev01.pdf
│   │
│   ├── INSTALLATION/
│   │   ├── {project_id}_INSTALL_Rev01.dxf
│   │   ├── {project_id}_INSTALL_Rev01.dwg
│   │   └── {project_id}_INSTALL_Rev01.pdf
│   │
│   └── REPORTS/
│       ├── {project_id}_VALIDATION_REPORT_Rev01.pdf
│       ├── {project_id}_AUDIT_TRAIL_Rev01.pdf
│       └── {project_id}_FINAL_CHECK_REPORT_Rev01.pdf
│
├── PACKAGE.zip                          ← Full release package
│                                          Created by Output Generator after final approval
│                                          Contents: all Outputs/ subdirectories
│
└── Logs/
    ├── ingestion.log                    ← P2-01 detailed log
    ├── completeness.log                 ← P2-02 detailed log
    ├── ab_generation.log                ← P2-03 detailed log
    ├── ga_generation.log                ← P2-04 detailed log
    ├── abga_validation.log              ← P2-05 detailed log
    ├── sheeting.log                     ← P3-01 detailed log
    ├── shop_detail.log                  ← P3-02 detailed log
    ├── shipping.log                     ← P3-03 detailed log
    ├── installation.log                 ← P3-04 detailed log
    ├── final_check.log                  ← P3-05 detailed log
    ├── orchestrator.log                 ← Master orchestrator decisions
    ├── corrections.log                  ← All correction events for this project
    └── escalations.log                  ← All escalation events for this project
```

**Output naming convention:**
```
{project_proposal_id}_{OUTPUT_TYPE}_Rev{revision_number}.{extension}

Examples:
  Q-157_AB_Rev01.dwg
  Q-157_GA_Rev02.pdf          ← Rev02 if output was re-generated after a correction
  Q-157_SHOP_Rev01.dxf
  Q-157_SHIPPING_Rev01.xlsx
  Q-157_FINAL_CHECK_REPORT_Rev01.pdf
```

---

## 6. Reference Jobs Folder (50 Jobs)

The 50 reference jobs must be organized consistently before Phase 1 is run.

```
data/reference_jobs/
│
├── JOB-001/                             ← One folder per reference job
│   ├── job_meta.json                    ← { "job_id": "JOB-001", "project_type": "Warehouse", "year": 2023 }
│   ├── design/
│   │   └── model.std                    ← Governing design file
│   ├── drawings/
│   │   ├── AB_Drawing.dwg
│   │   ├── GA_Drawing.dwg
│   │   ├── Shop_Drawings.dwg
│   │   └── Installation.dwg
│   ├── pdfs/
│   │   ├── AB_Drawing.pdf
│   │   └── GA_Drawing.pdf
│   └── docs/
│       └── notes.xlsx
│
├── JOB-002/
│   └── ...
│
└── JOB-050/
    └── ...
```

**Rules for reference job folder preparation (IT team):**
- Every job folder must have at minimum one design file and one drawing type
- File naming does not need to be standardized — Phase 1 agents handle classification
- Include a `job_meta.json` in each folder with at minimum `job_id` and `project_type`
- Do NOT mix jobs from different companies or standards in the same reference set
- Preserve original filenames — do not rename before Phase 1
- Archive files (RAR/ZIP) can stay as-is — Phase 1 ingestion handles unpacking

---

## 7. Master Database Data Files

Phase 1 writes to PostgreSQL tables, but also exports JSON snapshots for review.

```
data/master_db_exports/
│
└── phase1_run_{YYYY-MM-DD}/             ← One folder per Phase 1 execution
    │
    ├── template_library.json            ← All template families extracted
    │   {
    │     "templates": [
    │       { "template_code": "AB-T01", "output_class": "AB", "status": "standard", ... },
    │       ...
    │     ],
    │     "total": 24,
    │     "generated_at": "2026-04-17T09:15:00Z"
    │   }
    │
    ├── field_dictionary.json            ← All fields defined
    │   { "fields": [ { "field_code": "BOLT_SIZE", ... }, ... ], "total": 187 }
    │
    ├── source_mapping_rules.json        ← Per-field source rules
    ├── validation_rules.json            ← All validation rules
    ├── override_rules.json              ← Conflict resolution rules
    │
    └── phase1_summary_report.json       ← Human-readable summary
        {
          "jobs_analyzed": 50,
          "template_families_found": 8,
          "fields_defined": 187,
          "mapping_rules_created": 245,
          "validation_rules_created": 112,
          "override_rules_created": 38,
          "outlier_jobs": ["JOB-007", "JOB-031"],
          "unresolved_issues": [...],
          "engineer_review_required": [...]
        }
```

---

## 8. Logs & Audit Trail

```
data/logs/
│
├── app.log                              ← Rolling application log
│   Format: TIMESTAMP | LEVEL | MODULE | MESSAGE
│   Retention: 30 days, max 100MB, daily rotation
│
├── celery.log                           ← Celery worker and task log
│   Retention: 14 days
│
├── audit.log                            ← IMMUTABLE audit trail
│   Every engineer action logged:
│     { "timestamp": "...", "engineer": "...", "action": "approve_handoff",
│       "project_uuid": "...", "stage_code": "P2-03", "result": "approved" }
│   Never deleted — required for engineering release discipline
│   Append-only. Copied to PostgreSQL audit table simultaneously.
│
└── error.log                            ← Error-only, monitored for alerts
```

Per-project logs under `data/projects/{uuid}/Logs/`:
```
ingestion.log       — Every file classified, confidence scores, revision detections
completeness.log    — Every field checked, status (PRESENT/MISSING/SUSPICIOUS), source found
ab_generation.log   — Every field extracted, template zone populated, traceability recorded
ga_generation.log   — Geometry extraction, AB grid references used, template population
abga_validation.log — Every field compared, pass/fail per field, critical failures flagged
...etc per stage
corrections.log     — { timestamp, field, original_value, corrected_value, source, agent }
escalations.log     — { timestamp, type, stage, reason, severity, evidence, status }
orchestrator.log    — { timestamp, stage_code, decision, reason, downstream_eligible }
```

---

## 9. ChromaDB Persistence

```
data/chromadb/
│
├── chroma.sqlite3                       ← ChromaDB metadata + collection registry
│
└── {collection_uuid}/                   ← One folder per collection
    ├── data_level0.bin                  ← HNSW index binary (vector graph)
    ├── header.bin
    ├── id_to_uuid.bin
    └── uuid_to_id.bin
```

**Collections:**

| Collection | Purpose | Entry Trigger | Searched By |
|-----------|---------|--------------|-------------|
| `project_profiles` | Profile embedding per approved project | Project receives FINAL APPROVED | Level 2 (missing field suggestion), Level 3 (template suggestion) |
| `template_patterns` | Template pattern embeddings from Phase 1 | Phase 1 P1-01 runs | Level 2 (layout suggestions) |

**ChromaDB backup:** Copy entire `data/chromadb/` folder — it is self-contained.

---

## 10. ODA File Converter Paths

The ODA File Converter is installed separately, not inside the repo.

```
Windows (default install):
  C:\Program Files\ODA\ODAFileConverter\ODAFileConverter.exe

Linux (AppImage):
  /home/{user}/Apps/ODAFileConverter.AppImage
  (chmod a+x required)

macOS:
  /Applications/ODAFileConverter.app/Contents/MacOS/ODAFileConverter
```

**Temp files created during DXF → DWG conversion:**
```
data/temp/oda_input/
  {uuid}_ab.dxf           ← Input DXF to be converted
data/temp/oda_output/
  {uuid}_ab.dwg           ← DWG output from ODA
```

Both temp files are moved to `Outputs/AB/` and renamed to the project convention after conversion. Temp files are cleaned up after successful conversion.

---

## 11. Naming Conventions

### Project UUID vs Proposal ID
```
project_uuid    = Internal system identifier (UUID4, auto-generated)
                  Used for: all DB FK relationships, folder names, API URLs
                  Example: 550e8400-e29b-41d4-a716-446655440000

proposal_id     = Human-readable reference (user-entered)
                  Used for: output filenames, UI display, cross-references
                  Example: Q-157

Combined form:  Q-157-Palghar  (used in project display name / search)
```

### Stage Codes
```
P1-01 to P1-05  → Phase 1 agents (one-time)
P2-01 to P2-05  → Phase 2 agents (per project, sequential)
P3-01 to P3-05  → Phase 3 agents (per project, sequential)
```

### File Names
```
Rule: {proposal_id}_{OUTPUT_TYPE}_Rev{NN}.{ext}

OUTPUT_TYPE values:
  AB          → Anchor Bolt drawing
  GA          → General Arrangement drawing
  SHOP        → Shop/Detail drawings
  SHEETING    → Sheeting & BOQ
  SHEETING_LIST → Sheeting list (separate from drawing)
  SHIPPING    → Shipping list
  INSTALL     → Installation/Erection drawings
  VALIDATION_REPORT → Stage validation report
  AUDIT_TRAIL → Audit trail document
  FINAL_CHECK_REPORT → P3-05 report

Revision:
  Rev01 = first generation
  Rev02 = second generation (after a correction and re-run)
  RevNN = increments on each approved output generation
```

### Structured Data JSON Files
```
file_inventory.json             → P2-01 output
governing_source.json           → P2-01 human decision result
extracted_{source}.json         → Parser output per source type
completeness_matrix.json        → P2-02 output
ab_structured_package.json      → P2-03 output
ga_structured_package.json      → P2-04 output
abga_validation_report.json     → P2-05 output
sheeting_package.json           → P3-01 output
shop_detail_package.json        → P3-02 output
shipping_package.json           → P3-03 output
installation_package.json       → P3-04 output
final_check_report.json         → P3-05 output
```

---

## 12. Access & Lifecycle Rules

| Directory | Who Reads | Who Writes | Deletion |
|-----------|----------|-----------|---------|
| `Raw_Inputs/` | Parsers, Ingestion Agent | Engineer upload only | Never deleted |
| `Processed/` | All agents (downstream) | Agent that generated it | Never deleted (audit) |
| `Outputs/` | Frontend download, ZIP packager | Output Generator Agent only | Never auto-deleted |
| `Logs/` | Log viewer, audit reporter | All agents (append-only) | App log: 30-day rotation; Audit: never |
| `data/temp/` | ODA converter, archive extractor | Parsers, ODA wrapper | Auto-cleaned after use |
| `reference_jobs/` | Phase 1 agents | IT setup only (manual) | Never during normal operation |
| `chromadb/` | ChromaDB client | Learning Agent (Level 3) | Never deleted (Vector DB) |
| `master_db_exports/` | Engineers for review | Phase 1 consolidator | Manual cleanup only |

**Critical rule:** `Raw_Inputs/` is read-only after upload. Nothing may modify, rename, or delete the original uploaded files. All processing uses copies in `Processed/` or `temp/`.

---

## 13. Backup Strategy

| What | How Often | Destination | Method |
|------|----------|-------------|--------|
| PostgreSQL database | Daily | `/backup/postgres/{date}.sql` | `pg_dump` via cron / Windows Task Scheduler |
| ChromaDB | Daily | `/backup/chromadb/{date}/` | `cp -r data/chromadb/` |
| `data/projects/` | After each project release | External drive / network share | Robocopy (Windows) or `rsync` (Linux) |
| `data/reference_jobs/` | After any job added | External drive | Manual or scheduled |
| `audit.log` | Weekly | Secure archive | Append-only copy |

**Minimum backup before Phase 1 re-run:** Always back up PostgreSQL + `master_db_exports/` before triggering a Phase 1 periodic re-run.

---

## 14. Environment Paths Reference

All paths that must be set in `backend/.env`:

```env
# ── Storage paths ─────────────────────────────────────────────────
STORAGE_BASE_PATH=./data/projects          ← Per-project root
REFERENCE_JOBS_PATH=./data/reference_jobs  ← 50 reference jobs
CHROMA_PERSIST_DIR=./data/chromadb         ← ChromaDB storage
TEMP_PATH=./data/temp                      ← Temp processing files
LOG_BASE_PATH=./data/logs                  ← Application logs

# ── CAD tools ─────────────────────────────────────────────────────
# Windows:
ODA_CONVERTER_PATH=C:\Program Files\ODA\ODAFileConverter\ODAFileConverter.exe
# Linux:
# ODA_CONVERTER_PATH=/home/user/Apps/ODAFileConverter.AppImage

# ── PostgreSQL ────────────────────────────────────────────────────
DATABASE_URL=postgresql://infiniti:password@localhost:5432/steel_agent_db

# ── Redis ─────────────────────────────────────────────────────────
REDIS_URL=redis://localhost:6379/0

# ── Ollama ────────────────────────────────────────────────────────
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3
```

All paths support both absolute and relative forms. Relative paths are resolved from the `backend/` directory.

---

## Summary: Key Paths Quick Reference

| What | Path |
|------|------|
| Project data root | `data/projects/{project_uuid}/` |
| Raw uploaded files | `data/projects/{uuid}/Raw_Inputs/` |
| Agent JSON outputs | `data/projects/{uuid}/Processed/` |
| Generated DXF/DWG/PDF | `data/projects/{uuid}/Outputs/{TYPE}/` |
| Release ZIP | `data/projects/{uuid}/PACKAGE.zip` |
| Per-project logs | `data/projects/{uuid}/Logs/` |
| 50 reference jobs | `data/reference_jobs/JOB-NNN/` |
| Phase 1 export snapshots | `data/master_db_exports/phase1_run_{date}/` |
| ChromaDB vectors | `data/chromadb/` |
| Application logs | `data/logs/` |
| Audit trail | `data/logs/audit.log` |
| Temp ODA input | `data/temp/oda_input/` |
| Temp ODA output | `data/temp/oda_output/` |
| Backend source | `backend/app/` |
| Frontend source | `frontend/src/` |
| DB migrations | `backend/alembic/versions/` |
| Setup scripts | `scripts/` |

---

*Infiniti Solutions — Steel Detailing Multi-Agent System | Execution Folder Structure Document | v1.0 April 2026 | CONFIDENTIAL — Internal Use Only*
