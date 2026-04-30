# Phase 2 Implementation Plan - SQLite Version

**Project:** Infiniti Steel Detailing Automation  
**Scope:** Phase 2 implementation start plan  
**Database decision:** SQLite, local-first  
**Primary DB path:** `DB/master_db.db`  
**Backend app DB URL:** `sqlite:///./app/db/steel_detailing.db`  
**No PostgreSQL URL required.**

Use this file as your working checklist. Mark each task as done only after the expected output is present and the gate condition, if any, is satisfied.

---

## SQLite Setup Rule

For Phase 2, do not use:

```env
DATABASE_URL=postgresql://...
```

Use SQLite:

```env
DATABASE_URL=sqlite:///./app/db/steel_detailing.db
```

Required SQLite connection settings for every DB connection:

```sql
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 5000;
PRAGMA synchronous = FULL;
```

These settings let Phase 2 safely read/write project records, stage status, audit rows, parser outputs, and validation results in a desktop/local environment.

---

# Phase A - Baseline And SQLite Readiness

**Goal:** Confirm the folder structure, SQLite database, schema, and local configuration are ready before Phase 2 code starts.

## Step 1 - Confirm Folder Structure

- [x] Verify these folders exist:
  - `backend/app/agents/phase2`
  - `backend/app/parsers`
  - `backend/app/db`
  - `backend/app/db/crud`
  - `backend/app/orchestrator`
  - `backend/app/tasks`
  - `data/projects`
  - `data/temp`
  - `DB`

**What this does:** Confirms that the project has the required places for Phase 2 ingestion, parsing, persistence, orchestration, and generated outputs.  
**Progress it creates:** You can now add implementation files without changing the project architecture again.

## Step 2 - Confirm SQLite Database Location

- [x] Confirm `DB/master_db.db` exists.
- [x] Confirm backend `.env` uses:

```env
DATABASE_URL=sqlite:///./app/db/steel_detailing.db
```

- [x] Remove or ignore any PostgreSQL URL examples from active configuration.

**What this does:** Locks the project to SQLite instead of PostgreSQL.  
**Progress it creates:** All Phase 2 agents will read and write through the same local DB approach.

## Step 3 - Validate SQLite Schema Health

- [x] Run SQLite integrity check.
- [x] Confirm required Phase 2 tables exist or are mapped:
  - project table
  - file registry table
  - project stage status table
  - stage checkpoint table
  - field value store
  - validation result table
  - audit event log
  - source mapping / fallback / rule master tables

**What this does:** Confirms the database can support ingestion, extraction, validation, checkpoints, and audit records.  
**Progress it creates:** Prevents Phase 2 agents from failing later because a table is missing.

## Step 4 - Confirm SQLite Session Layer

- [x] Confirm `backend/app/db/session.py` creates SQLAlchemy sessions from `settings.database_url`.
- [x] Confirm SQLite PRAGMA settings are applied on connection.
- [x] Confirm `foreign_keys=ON` is enforced.
- [x] Confirm WAL mode is enabled.

**What this does:** Makes the app use SQLite correctly and consistently.  
**Progress it creates:** Enables safe local DB operations for multiple Phase 2 stages.

### Hard Gate 1 - SQLite Baseline Gate

- [x] `DATABASE_URL` is SQLite.
- [x] SQLite DB file exists or can be created by migrations/init.
- [x] Integrity check passes.
- [x] Required tables are present.
- [x] PRAGMA settings are active.

**Gate meaning:** Do not start Phase B until SQLite is proven stable.

---

# Phase B - Project Intake And File Registry

**Goal:** Build the project intake layer so uploaded project files are stored, classified, and registered in SQLite.

## Step 5 - Implement Project Creation API

- [x] Confirm or implement endpoint to create a project.
- [x] Store project metadata in SQLite.
- [x] Generate a stable `project_uuid`.
- [x] Create initial project stage records for Phase 2.

**What this does:** Creates the main project record Phase 2 will work against.  
**Progress it creates:** Every file, stage, validation result, and output can now be linked to a project.

## Step 6 - Implement File Upload Storage

- [x] Store uploaded files under `data/projects/{project_uuid}/input`.
- [x] Preserve original filename.
- [x] Generate internal stored filename/path.
- [x] Save file metadata in SQLite.

**What this does:** Moves incoming project files into controlled project storage.  
**Progress it creates:** The parser layer can now process real project files from a predictable location.

## Step 7 - Implement Source Classification

- [x] Classify files as MBS, STAAD, ETABS, Prota, DXF, PDF, archive, or unsupported.
- [x] Detect likely role:
  - governing
  - supporting
  - template
  - irrelevant
- [x] Save classification confidence in SQLite.

**What this does:** Decides which parser should handle each uploaded file.  
**Progress it creates:** Phase 2 can route files instead of treating all uploads the same.

## Step 8 - Implement Archive Handling

- [x] Extract ZIP files.
- [x] Extract RAR files if supported locally.
- [x] Register extracted files in SQLite.
- [x] Preserve parent archive relationship.
- [x] Flag unsupported nested files.

**What this does:** Makes project intake work with real client/job packages, not only loose files.  
**Progress it creates:** Phase 2 can process full project submissions.

### Hard Gate 2 - Intake Gate

- [x] A project can be created.
- [x] Files can be uploaded and stored.
- [x] Files are registered in SQLite.
- [x] Source classification is saved.
- [x] Archives are extracted and registered.

**Gate meaning:** Do not start Phase C until project files can be reliably stored and classified.

---

# Phase C - Parser Adapter Implementation

**Goal:** Convert project files into normalized field values, with traceability back to each source.

## Step 9 - Implement MBS Parser Adapter

- [x] Parse MBS exports.
- [x] Extract building geometry, grids, bays, member data, and project metadata where available.
- [x] Save extracted values to SQLite.
- [x] Log source traceability for every field.

**What this does:** Turns MBS project data into normalized Phase 2 records.  
**Progress it creates:** MBS projects can feed AB and GA generation.

## Step 10 - Implement STAAD Parser Adapter

- [x] Parse `.std` files.
- [x] Extract nodes, members, sections, material references, supports, and loads where available.
- [x] Save extracted values to SQLite.
- [x] Log parser confidence.

**What this does:** Reads STAAD model data as a high-priority engineering source.  
**Progress it creates:** Phase 2 can use structural model data for validation and generation.

## Step 11 - Implement ETABS / Prota / PDF Parser Adapters

- [x] Parse ETABS Excel exports.
- [x] Parse Prota/DXF/PDF sources where available.
- [x] Extract text/table data from PDFs.
- [x] Route scanned PDFs to OCR if required.
- [x] Save extracted values and confidence in SQLite.

**What this does:** Adds support for secondary and alternate project sources.  
**Progress it creates:** Phase 2 becomes source-flexible instead of depending on one software format.

## Step 12 - Implement Field Normalization Layer

- [x] Map parser outputs to standard field codes.
- [x] Normalize units.
- [x] Normalize controlled vocabulary values.
- [x] Resolve aliases using the alias/field dictionary tables.
- [x] Store normalized results in SQLite.

**What this does:** Converts raw parser values into standard project fields.  
**Progress it creates:** Downstream completeness checks and drawing generation can use consistent data.

### Hard Gate 3 - Parser And Normalization Gate

- [ ] At least one real sample file parses successfully.
- [ ] Extracted values are saved in SQLite.
- [ ] Field traceability is stored.
- [ ] Normalized field values are available by `project_uuid`.
- [ ] Parser failures are logged without crashing the whole project.

**Gate meaning:** Do not start Phase D until raw project files become normalized project data.

---

# Phase D - Completeness, Rules, And Hard Gates

**Goal:** Decide whether a project has enough valid information to generate AB and GA outputs.

## Step 13 - Implement Completeness Checker

- [ ] Load mandatory Phase 2 fields from SQLite.
- [ ] Check missing, null, invalid, and unresolved fields.
- [ ] Mark fields as complete, warning, blocker, or manual review.
- [ ] Store completeness results in SQLite.

**What this does:** Identifies whether the project is ready for AB/GA generation.  
**Progress it creates:** Prevents drawing generation from starting with missing governing data.

## Step 14 - Implement Source Priority And Conflict Rules

- [ ] Apply source priority hierarchy.
- [ ] Detect conflicts between source files.
- [ ] Prefer governing source over lower-priority source.
- [ ] Log conflicts and selected winning values.
- [ ] Store conflict results in SQLite.

**What this does:** Resolves cases where multiple files disagree.  
**Progress it creates:** Phase 2 gets one controlled value per required field.

## Step 15 - Implement Fallback Policy

- [ ] Load fallback rules from SQLite.
- [ ] Apply fallback only where allowed.
- [ ] Block fallback for prohibited governing fields.
- [ ] Save fallback reason, confidence, and source.
- [ ] Route low-confidence fallback to manual review.

**What this does:** Fills allowed gaps without violating governance rules.  
**Progress it creates:** More projects can continue safely while true blockers remain controlled.

## Step 16 - Implement Stage Checkpoint And Audit Logging

- [ ] Save checkpoint after ingestion.
- [ ] Save checkpoint after completeness.
- [ ] Save checkpoint after AB generation.
- [ ] Save checkpoint after GA generation.
- [ ] Write append-only audit events for all stage transitions.

**What this does:** Creates recovery and traceability points.  
**Progress it creates:** Failed runs can be diagnosed, retried, or escalated without losing history.

### Hard Gate 4 - Completeness And Governance Gate

- [ ] Mandatory fields checked.
- [ ] Blocking issues are identified.
- [ ] Source conflicts are resolved or escalated.
- [ ] Fallback is applied only where allowed.
- [ ] Audit and checkpoint rows are written.

**Gate meaning:** Do not start Phase E until the project is either generation-ready or formally blocked/escalated.

---

# Phase E - AB And GA Generation

**Goal:** Generate controlled Anchor Bolt and General Arrangement outputs from validated SQLite project data.

## Step 17 - Implement AB Generation Agent

- [ ] Load validated field values from SQLite.
- [ ] Generate anchor bolt layout data.
- [ ] Apply template and title block rules.
- [ ] Save AB output metadata in SQLite.
- [ ] Save generated files under `data/projects/{project_uuid}/outputs/ab`.

**What this does:** Produces the first controlled Phase 2 drawing output.  
**Progress it creates:** The project now has a generated AB package ready for validation.

## Step 18 - Implement GA Generation Agent

- [ ] Load validated field values from SQLite.
- [ ] Generate GA layout data.
- [ ] Apply grid, geometry, member, and title block rules.
- [ ] Save GA output metadata in SQLite.
- [ ] Save generated files under `data/projects/{project_uuid}/outputs/ga`.

**What this does:** Produces the controlled GA output.  
**Progress it creates:** Phase 2 now covers both required AB and GA deliverables.

## Step 19 - Implement DXF / PDF / DWG Output Flow

- [ ] Generate DXF first.
- [ ] Render PDF preview.
- [ ] Convert DXF to DWG using ODA where available.
- [ ] Save output paths and status in SQLite.
- [ ] Log conversion failures without losing DXF/PDF.

**What this does:** Creates usable drawing files in the required formats.  
**Progress it creates:** AB/GA outputs become reviewable by users and downstream teams.

---

# Phase F - Validation, UI Status, And Release Readiness

**Goal:** Validate generated outputs, expose status to the frontend, and make Phase 2 ready for controlled handoff to Phase 3.

## Step 20 - Implement AB/GA Validation Agent

- [ ] Validate AB output against rules.
- [ ] Validate GA output against rules.
- [ ] Run geometry reconciliation checks.
- [ ] Run cross-output checks between AB and GA.
- [ ] Store validation pass/fail rows in SQLite.

**What this does:** Checks whether generated drawings match the rule database and source project data.  
**Progress it creates:** Phase 2 can distinguish approved outputs from drafts needing correction.

## Step 21 - Implement Frontend Stage Status Updates

- [ ] Expose Phase 2 stage statuses through API.
- [ ] Broadcast live status through WebSocket.
- [ ] Show statuses:
  - pending
  - running
  - passed
  - blocked
  - failed
  - escalated
- [ ] Show hard gate result and blocker reason.

**What this does:** Makes Phase 2 visible to the user while agents run.  
**Progress it creates:** Users can see exactly where a project is and what action is needed.

## Step 22 - Implement Final Handoff Package

- [ ] Create Phase 2 handoff summary.
- [ ] Include AB and GA output links.
- [ ] Include validation summary.
- [ ] Include unresolved blockers or manual approvals.
- [ ] Mark Phase 3 eligibility in SQLite.

**What this does:** Closes Phase 2 with a controlled release package.  
**Progress it creates:** Phase 3 can start only when AB/GA outputs are valid and traceable.

### Hard Gate 5 - Phase 2 Release Gate

- [ ] AB generated.
- [ ] GA generated.
- [ ] AB/GA validation completed.
- [ ] Geometry reconciliation completed.
- [ ] All blockers resolved or escalated.
- [ ] Phase 2 handoff package generated.
- [ ] Phase 3 eligibility explicitly set in SQLite.

**Gate meaning:** Phase 2 is complete only after generated outputs are validated and handoff-ready.

---

# Summary - What Each Phase Achieves

| Phase | Main Work | What It Progresses In The Project |
|---|---|---|
| Phase A | SQLite baseline and config | Confirms local DB foundation is ready |
| Phase B | Project intake and file registry | Creates project records and registers source files |
| Phase C | Parser adapters and normalization | Converts raw files into standard field values |
| Phase D | Completeness, rules, fallback, audit | Decides whether generation is allowed or blocked |
| Phase E | AB and GA generation | Produces controlled drawing outputs |
| Phase F | Validation, UI status, handoff | Confirms outputs are acceptable and Phase 3-ready |

---

# Execution Order

Do the work in this exact order:

1. Phase A - Steps 1 to 4
2. Hard Gate 1
3. Phase B - Steps 5 to 8
4. Hard Gate 2
5. Phase C - Steps 9 to 12
6. Hard Gate 3
7. Phase D - Steps 13 to 16
8. Hard Gate 4
9. Phase E - Steps 17 to 19
10. Phase F - Steps 20 to 22
11. Hard Gate 5

Only mark a hard gate as done when every item inside that gate is complete.
