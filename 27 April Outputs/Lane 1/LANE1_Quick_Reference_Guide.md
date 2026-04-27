# LANE 1 — QUICK REFERENCE GUIDE
## Steel Detailing Desktop System · Architecture, Schema, and Lookup Tables

**Document ID:** LANE1_QUICK_REFERENCE  
**Prepared by:** Lane 1 Consolidated Documentation  
**Date:** 2026-04-27  
**Version:** v1.0

---

## TABLE OF CONTENTS

1. [Architecture Overview](#1-architecture-overview)
2. [Schema Entity Relationship Diagram](#2-schema-entity-relationship-diagram)
3. [Table Definitions Quick Lookup](#3-table-definitions-quick-lookup)
4. [Engine Orchestration Flow](#4-engine-orchestration-flow)
5. [Validation Layer Stack](#5-validation-layer-stack)
6. [Stage Progression & Gate Status](#6-stage-progression--gate-status)
7. [Database Pragmas & Settings](#7-database-pragmas--settings)
8. [Common SQL Patterns](#8-common-sql-patterns)
9. [Error Codes & Resolution](#9-error-codes--resolution)
10. [Development Checklist](#10-development-checklist)

---

## 1. ARCHITECTURE OVERVIEW

```
┌─────────────────────────────────────────────────────────────────┐
│                     LANE 1 BACKEND SYSTEM                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Desktop Application (Block 7)                            │  │
│  │  - Project creation, stage progression, result display    │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              ↓                                    │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Engine Core (Block 2)                                    │  │
│  │  - Orchestrator: run(project_id, stage)                   │  │
│  │  - rule_loader, severity_handler, blocker_registry,       │  │
│  │    audit_writer modules                                   │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              ↓                                    │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Validation Layers (Block 3)                              │  │
│  │  - L01: Completeness    L04: Enumeration                  │  │
│  │  - L02: Data Type       L05: Format/Regex                 │  │
│  │  - L03: Unit            L10: Stage Gate + Prerequisites    │  │
│  │  - L06–L13: (Reserved for Block 6+)                       │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              ↓                                    │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  SQLite Database (Block 1)                                │  │
│  │  - 9 core tables, 10 indexes, 6 triggers                  │  │
│  │  - Immutable audit trail, hard-gated stages               │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘

Data Flow:
  App → engine_core.run(project_id, stage)
     → rule_loader.load_rules(stage)
     → [For each rule] → Layer evaluator.evaluate(rule, field_value)
     → severity_handler.record(rule, outcome)
     → blocker_registry.register(failed_rule)
     → engine_core._write_result(project_id, rule_id, outcome)
     → engine_core._update_stage_status(project_id, stage, gate_result)
     → audit_writer.write(event_type, detail)
     → Return gate_result to app
```

---

## 2. SCHEMA ENTITY RELATIONSHIP DIAGRAM

```
┌─────────────────────────────────────────────────────────────────┐
│                        CORE ENTITIES                              │
└─────────────────────────────────────────────────────────────────┘

    ┌──────────────────┐
    │  project_master  │  (PK: project_id)
    │──────────────────│
    │ project_id       │
    │ project_name     │
    │ project_code ────────┐
    │ client_name      │    │ UNIQUE
    │ is_active        │    │
    └──────────────────┘    │
          ↑                  │
          │ (1)             │
          │                  │
    (N)   │                  │
    ┌──────────────────┐    │
    │module_registry   │    │
    │──────────────────│    │
    │ module_id        │←───┘
    │ module_name      │
    │ module_version   │
    │ module_type      │
    │ is_enabled       │
    └──────────────────┘
          ↑
          │ (1)
          │
    (N)   │
    ┌──────────────────┐
    │field_dictionary  │
    │──────────────────│
    │ field_id         │
    │ module_id        │ ──→ module_registry(module_id)
    │ field_name       │
    │ field_label      │
    │ data_type        │
    │ unit_type        │
    │ allowed_values   │ (JSON for ENUM)
    │ is_required      │
    │ is_immutable     │
    │ default_value    │
    └──────────────────┘
       ↑      ↑
       │      └─────────────────┐
       │                        │
       │ (1)                    │ (1)
       │                        │
    (N)│                        │(N)
    ┌──────────────────┐  ┌──────────────────────────┐
    │source_mapping_   │  │source_fallback_chain     │
    │master            │  │──────────────────────────│
    │──────────────────│  │ chain_id                 │
    │ mapping_id       │  │ field_id                 │
    │ field_id ────────┼──│ fallback_order           │
    │ source_system    │  │ source_system            │
    │ source_field_path│  │ fallback_condition       │
    │ transform_rule   │  └──────────────────────────┘
    │ priority         │
    └──────────────────┘

    ┌──────────────────────────────┐
    │validation_rule_master        │  (PK: rule_id)
    │──────────────────────────────│
    │ rule_id                      │
    │ module_id ────→ module_registry(module_id)
    │ field_id ────→ field_dictionary(field_id)
    │ rule_name                    │
    │ layer (L01–L13)              │
    │ severity (BLOCKER,...)       │
    │ stage_scope (S1–S10, NULL)   │
    │ rule_expression              │
    │ error_message                │
    │ is_active                    │
    └──────────────────────────────┘
             ↑
             │ (1)
             │
    (N)      │
    ┌──────────────────────────────┐
    │validation_result             │  (PK: result_id)
    │──────────────────────────────│
    │ result_id                    │
    │ project_id ────→ project_master(project_id)
    │ rule_id ────────→ validation_rule_master(rule_id)
    │ field_id ────→ field_dictionary(field_id)
    │ stage                        │
    │ run_id (batch groups)        │
    │ outcome (PASS/FAIL/SKIP/WARN)│
    │ severity_applied             │
    │ detail_message               │
    │ field_value_snap             │
    │ evaluated_at                 │
    └──────────────────────────────┘

    ┌──────────────────────────────┐
    │project_stage_status          │  (PK: status_id)
    │──────────────────────────────│  (UNIQUE: project_id, stage)
    │ status_id                    │
    │ project_id ────→ project_master(project_id)
    │ stage (S1–S10)               │
    │ gate_status (PENDING,...)    │
    │ gate_result_json             │
    │ evaluated_at                 │
    │ evaluated_by                 │
    │ notes                        │
    └──────────────────────────────┘

    ┌──────────────────────────────┐
    │audit_event_log               │  (PK: audit_id)
    │──────────────────────────────│  ⚠️ IMMUTABLE (INSERT ONLY)
    │ audit_id                     │
    │ event_type                   │
    │ project_id ────→ project_master(project_id)
    │ related_id                   │
    │ related_table                │
    │ actor                        │
    │ event_summary                │
    │ event_detail_json            │
    │ occurred_at                  │
    │ is_immutable = 1             │
    └──────────────────────────────┘

Legend:
  ──→  Foreign Key (PK reference)
  ↑    One-to-Many relationship
  (N), (1): Cardinality
```

---

## 3. TABLE DEFINITIONS QUICK LOOKUP

### project_master
```
project_id          TEXT PRIMARY KEY
project_name        TEXT NOT NULL
project_code        TEXT NOT NULL UNIQUE
client_name         TEXT
description         TEXT
created_at          TEXT DEFAULT now()
updated_at          TEXT DEFAULT now() (auto-updated via trigger)
schema_version      INTEGER DEFAULT 1
is_active           INTEGER CHECK(0 or 1)
```

### module_registry
```
module_id           TEXT PRIMARY KEY
module_name         TEXT NOT NULL UNIQUE
module_version      TEXT NOT NULL
module_type         TEXT NOT NULL (CORE / PLUGIN / EXTENSION)
is_enabled          INTEGER CHECK(0 or 1)
registered_at       TEXT DEFAULT now()
description         TEXT
```

### field_dictionary
```
field_id            TEXT PRIMARY KEY
module_id           TEXT NOT NULL FK → module_registry(module_id) RESTRICT
field_name          TEXT NOT NULL
field_label         TEXT
data_type           TEXT NOT NULL (TEXT / INTEGER / REAL / BOOLEAN / DATE / ENUM)
unit_type           TEXT (length / mass / force / angle / generic)
allowed_values      TEXT (JSON array for ENUM fields)
is_required         INTEGER CHECK(0 or 1)
is_immutable        INTEGER CHECK(0 or 1)
default_value       TEXT
description         TEXT
created_at          TEXT DEFAULT now()
UNIQUE              (module_id, field_name)
```

### validation_rule_master
```
rule_id             TEXT PRIMARY KEY
module_id           TEXT NOT NULL FK → module_registry(module_id) RESTRICT
field_id            TEXT FK → field_dictionary(field_id) SET NULL
rule_name           TEXT NOT NULL
layer               TEXT NOT NULL (L01_COMPLETENESS, L02_DATATYPE, ..., L10_STAGE_GATE)
severity            TEXT NOT NULL CHECK(BLOCKER / RELEASE_BLOCKER / ERROR / WARNING / INFO)
stage_scope         TEXT (S1 / S4 / S5 / S10 or NULL for all stages)
rule_expression     TEXT NOT NULL (rule logic or regex pattern)
error_message       TEXT NOT NULL
is_active           INTEGER CHECK(0 or 1)
created_at          TEXT DEFAULT now()
updated_at          TEXT DEFAULT now() (auto-updated via trigger)
```

### source_mapping_master
```
mapping_id          TEXT PRIMARY KEY
field_id            TEXT NOT NULL FK → field_dictionary(field_id) CASCADE
source_system       TEXT NOT NULL (TEKLA / REVIT / MANUAL / IFC)
source_field_path   TEXT NOT NULL (e.g., "Profile.Material.Grade")
transform_rule      TEXT (e.g., "UPPER", "FLOAT_TO_MM")
priority            INTEGER DEFAULT 1
is_active           INTEGER CHECK(0 or 1)
created_at          TEXT DEFAULT now()
UNIQUE              (field_id, source_system)
```

### source_fallback_chain
```
chain_id            TEXT PRIMARY KEY
field_id            TEXT NOT NULL FK → field_dictionary(field_id) CASCADE
fallback_order      INTEGER NOT NULL (1, 2, 3, ...)
source_system       TEXT NOT NULL (TEKLA / REVIT / MANUAL / IFC)
fallback_condition  TEXT (e.g., "TEKLA_MISSING OR TEKLA_EMPTY")
created_at          TEXT DEFAULT now()
UNIQUE              (field_id, fallback_order)
```

### project_stage_status
```
status_id           TEXT PRIMARY KEY
project_id          TEXT NOT NULL FK → project_master(project_id) CASCADE
stage               TEXT NOT NULL CHECK(S1 / S2 / ... / S10)
gate_status         TEXT NOT NULL CHECK(PENDING / OPEN / PASSED / BLOCKED / LOCKED)
gate_result_json    TEXT (full gate_result snapshot)
evaluated_at        TEXT
evaluated_by        TEXT
notes               TEXT
created_at          TEXT DEFAULT now()
updated_at          TEXT DEFAULT now() (auto-updated via trigger)
UNIQUE              (project_id, stage)
```

### validation_result
```
result_id           TEXT PRIMARY KEY
project_id          TEXT NOT NULL FK → project_master(project_id) CASCADE
rule_id             TEXT NOT NULL FK → validation_rule_master(rule_id) RESTRICT
field_id            TEXT FK → field_dictionary(field_id) SET NULL
stage               TEXT NOT NULL
run_id              TEXT NOT NULL (groups results from one engine run)
outcome             TEXT NOT NULL CHECK(PASS / FAIL / SKIP / WARN)
severity_applied    TEXT NOT NULL CHECK(BLOCKER / RELEASE_BLOCKER / ERROR / WARNING / INFO)
detail_message      TEXT
field_value_snap    TEXT (snapshot of field value at evaluation)
evaluated_at        TEXT DEFAULT now()
```

### audit_event_log (⚠️ IMMUTABLE)
```
audit_id            TEXT PRIMARY KEY
event_type          TEXT NOT NULL (SCHEMA_CHANGE / RULE_FIRED / GATE_TRANSITION / OVERRIDE / SYSTEM)
project_id          TEXT FK → project_master(project_id) SET NULL
related_id          TEXT (FK-agnostic reference)
related_table       TEXT
actor               TEXT DEFAULT 'SYSTEM'
event_summary       TEXT NOT NULL
event_detail_json   TEXT (JSON payload)
occurred_at         TEXT DEFAULT now()
is_immutable        INTEGER CHECK(= 1) ← ENFORCED BY TRIGGER
Triggers:
  - BEFORE UPDATE: ABORT (immutability enforced)
  - BEFORE DELETE: ABORT (immutability enforced)
```

---

## 4. ENGINE ORCHESTRATION FLOW

```
START: engine_core.run(project_id, stage)
  │
  ├─→ [STEP 1] Validate project_id exists in project_master
  │   └─→ FAIL? → Return error; log to audit_event_log
  │
  ├─→ [STEP 2] Load rules for stage
  │   └─→ rule_loader.load_rules(stage)
  │       └─→ SELECT from validation_rule_master
  │           WHERE is_active=1 AND (stage_scope IS NULL OR stage_scope=stage)
  │       └─→ Returns ordered list [by layer, then severity]
  │
  ├─→ [STEP 3] For EACH rule in rules:
  │   │
  │   ├─→ [STEP 3a] Evaluate rule
  │   │   └─→ Call appropriate layer evaluator
  │   │       └─→ L01.evaluate(rule, field_value)
  │   │       └─→ L02.evaluate(rule, field_value, data_type)
  │   │       └─→ ... (other layers)
  │   │       └─→ Returns: PASS / FAIL / SKIP / WARN
  │   │
  │   ├─→ [STEP 3b] Record outcome
  │   │   └─→ severity_handler.record(rule, outcome)
  │   │   └─→ blocker_registry.register(rule) if FAIL
  │   │
  │   └─→ [STEP 3c] Write result
  │       └─→ engine_core._write_result(...)
  │           └─→ INSERT INTO validation_result
  │               (result_id, project_id, rule_id, outcome, ...)
  │
  ├─→ [STEP 4] Check prerequisites for stage
  │   └─→ check_prerequisites(stage, project_stage_status)
  │       └─→ Returns: PASSED or BLOCKED (with missing stages list)
  │
  ├─→ [STEP 5] Compute gate result
  │   └─→ severity_handler.gate_result(stage, blocker_registry, prerequisite_status)
  │       └─→ Returns: gate_result dict
  │           {
  │             "gate_status": "PASSED" | "OPEN" | "BLOCKED",
  │             "is_hard_gate": True if S4 or S5,
  │             "severity_counts": {...},
  │             "blocker_count": N,
  │             "prerequisite_status": "PASSED" | "BLOCKED",
  │             "missing_stages": ["S1", "S2", ...]
  │           }
  │
  ├─→ [STEP 6] Update stage status
  │   └─→ engine_core._update_stage_status(project_id, stage, gate_result)
  │       └─→ UPSERT INTO project_stage_status
  │           (project_id, stage, gate_status, gate_result_json)
  │
  ├─→ [STEP 7] Write audit event
  │   └─→ audit_writer.write('GATE_TRANSITION', ...)
  │       └─→ INSERT INTO audit_event_log
  │           (audit_id, event_type, project_id, event_summary, event_detail_json)
  │
  └─→ [STEP 8] Return gate_result to calling app
      └─→ gate_result dict ready for UI display

Hard-Gate Check (S4 & S5):
  IF stage IN ('S4', 'S5'):
    IF blocker_count > 0 OR release_blocker_count > 0:
      gate_status = 'BLOCKED' ← UNCONDITIONAL
    ELSE IF prerequisite_status == 'BLOCKED':
      gate_status = 'BLOCKED'
    ELSE:
      gate_status = 'PASSED'
```

---

## 5. VALIDATION LAYER STACK

### L01 — Completeness

| Property | Value |
|----------|-------|
| **Purpose** | Ensure required fields are non-null and non-empty |
| **Entry Point** | `layer_01_completeness.evaluate(rule, field_value)` |
| **Logic** | `IF is_required AND (value is NULL OR value is empty_string) THEN FAIL` |
| **Returns** | PASS / FAIL / SKIP |
| **Severity** | BLOCKER (for required fields) |

### L02 — Data Type

| Property | Value |
|----------|-------|
| **Purpose** | Validate value conforms to declared data_type |
| **Entry Point** | `layer_02_datatype.evaluate(rule, field_value, data_type)` |
| **Supported Types** | TEXT, INTEGER, REAL, BOOLEAN, DATE (ISO 8601) |
| **Logic** | Type-specific validation (regex for DATE) |
| **Returns** | PASS / FAIL / SKIP |
| **Severity** | ERROR |

### L03 — Unit

| Property | Value |
|----------|-------|
| **Purpose** | Validate unit label is in allowed_units set |
| **Entry Point** | `layer_03_unit.evaluate(rule, field_value, unit_type)` |
| **Categories** | length, mass, force, angle, generic |
| **Example** | Valid lengths: mm, cm, m, inch, foot |
| **Returns** | PASS / FAIL / SKIP |
| **Severity** | ERROR |

### L04 — Enumeration

| Property | Value |
|----------|-------|
| **Purpose** | Validate value is in allowed_values JSON array |
| **Entry Point** | `layer_04_enumeration.evaluate(rule, field_value, allowed_values)` |
| **Logic** | `IF value NOT IN allowed_values THEN FAIL` |
| **Returns** | PASS / FAIL / SKIP |
| **Severity** | ERROR / WARNING |
| **Notes** | SKIP if no enum constraint defined |

### L05 — Format / Regex

| Property | Value |
|----------|-------|
| **Purpose** | Validate value matches regex pattern |
| **Entry Point** | `layer_05_format.evaluate(rule, field_value)` |
| **Logic** | Regex fullmatch (not partial match) |
| **Returns** | PASS / FAIL / SKIP |
| **Severity** | WARNING |
| **Notes** | SKIP if no pattern defined; gracefully handles invalid regex |

### L10 — Stage Gate

| Property | Value |
|----------|-------|
| **Purpose** | Enforce prerequisite and hard-gate logic |
| **Entry Point** | `layer_10_stage_gate.evaluate_gate(stage, blocker_registry, stage_statuses)` |
| **Logic** | Check prerequisites FIRST; then hard-gate rules |
| **Returns** | gate_status: PASSED / OPEN / BLOCKED |
| **Hard-Gate Stages** | S4, S5 (unconditional block on any BLOCKER/RELEASE_BLOCKER) |

### L06–L13 (Reserved for Block 6+)

| Layer | Purpose | Status |
|-------|---------|--------|
| **L06** | Dependency validation | ⏳ Pending |
| **L07** | Cross-field validation | ⏳ Pending |
| **L08** | Source governance | ⏳ Pending |
| **L09** | Source fallback resolution | ⏳ Pending |
| **L11** | Override logic | ⏳ Pending |
| **L12** | Edge case RC | ⏳ Pending |
| **L13** | Custom plugins | ⏳ Pending |

---

## 6. STAGE PROGRESSION & GATE STATUS

### Stage Sequence

```
Entry → S1 → S2 → S3 → S4 (HARD) → S5 (HARD) → S6 → S7 → S8 → S9 → S10 → Complete
        │    │    │    │          │             │    │    │    │    │
        └────┴────┴────┘          │             └────┴────┴────┴────┘
        Sequential Validation     Release Critical    Post-Release
```

### Prerequisite Map

| Stage | Prerequisites | Type | Enforcement |
|-------|---------------|------|-------------|
| S1 | None | Entry | No check |
| S2 | S1 = PASSED | Sequential | BLOCKED if failed |
| S3 | S1, S2 = PASSED | Sequential | BLOCKED if any failed |
| S4 | S1, S2, S3 = PASSED | HARD GATE | BLOCKED if any failed; also zero blockers |
| S5 | S1–S4 = PASSED | HARD GATE | BLOCKED if any failed; also zero blockers; release-critical |
| S6 | S5 = PASSED | Sequential | BLOCKED if failed; post-release baseline |
| S7 | S5, S6 = PASSED | Sequential | BLOCKED if any failed |
| S8 | S5, S6, S7 = PASSED | Sequential | BLOCKED if any failed |
| S9 | S5, S6, S7, S8 = PASSED | Sequential | BLOCKED if any failed |
| S10 | S5–S9 = PASSED | Sequential | BLOCKED if any failed; final closeout |

### Gate Status Values

| Status | Meaning | Advancement | Notes |
|--------|---------|-------------|-------|
| **PENDING** | Not yet evaluated | Cannot advance | Initial state |
| **OPEN** | Evaluated; errors/warnings but no blockers | Can advance (conditionally) | Not hard-gated |
| **PASSED** | All checks passed | Can advance freely | Prerequisite satisfied for dependents |
| **BLOCKED** | Hard blockers (BLOCKER/RELEASE_BLOCKER) or failed prerequisites | Cannot advance | Manual intervention may be required |
| **LOCKED** | (Reserved for override mechanism; not yet implemented) | Cannot advance | Future Block 6+ feature |

### Hard Gate Logic (S4 & S5)

```
Hard Gate Check for S4 and S5:

IF ANY BLOCKER OR RELEASE_BLOCKER FAILS:
  gate_status = 'BLOCKED' ← UNCONDITIONAL
  is_hard_gate = True

ELSE IF prerequisite_status != 'PASSED':
  gate_status = 'BLOCKED'

ELSE:
  gate_status = 'PASSED'

NOTE: Cannot be overridden at engine level (override mechanism reserved for future)
```

---

## 7. DATABASE PRAGMAS & SETTINGS

### Standard Pragmas (All Connections)

```sql
PRAGMA journal_mode = WAL;
  -- Write-Ahead Log for better concurrency and durability

PRAGMA foreign_keys = ON;
  -- Enable foreign key constraint enforcement
  -- ⚠️ MUST BE RE-ISSUED PER CONNECTION

PRAGMA synchronous = NORMAL;
  -- Balance between safety and performance
  -- (FULL = safest, NORMAL = balance, OFF = fastest)

PRAGMA temp_store = MEMORY;
  -- Store temporary tables/indexes in memory (faster)

PRAGMA cache_size = -32000;
  -- 32 MB page cache (larger = faster for large queries)

PRAGMA auto_vacuum = INCREMENTAL;
  -- Incrementally free unused space (prevents bloat)
```

### Connection Initialization Code

```python
def get_connection(db_path):
    conn = sqlite3.connect(db_path)
    # Re-issue PRAGMA on each connection
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn
```

### Integrity & Maintenance

```sql
-- Verify database integrity
PRAGMA integrity_check;
-- Returns 'ok' if healthy, or list of errors

-- Vacuum unused space
VACUUM;

-- Checkpoint WAL (merge into main DB)
PRAGMA wal_checkpoint(RESTART);

-- Analyze query performance
ANALYZE;
```

---

## 8. COMMON SQL PATTERNS

### Load Rules for a Stage

```sql
SELECT rule_id, module_id, field_id, rule_name, layer, severity, 
       rule_expression, error_message
FROM validation_rule_master
WHERE is_active = 1 
  AND (stage_scope IS NULL OR stage_scope = ?)
ORDER BY layer, severity;
```

### Load Rules by Layer

```sql
SELECT rule_id, rule_name, severity, rule_expression, error_message
FROM validation_rule_master
WHERE is_active = 1 
  AND layer = ?
  AND (stage_scope IS NULL OR stage_scope = ?)
ORDER BY severity;
```

### Insert Validation Result

```sql
INSERT INTO validation_result 
  (result_id, project_id, rule_id, field_id, stage, run_id, 
   outcome, severity_applied, detail_message, field_value_snap)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
```

### Update Project Stage Status (UPSERT)

```sql
INSERT INTO project_stage_status 
  (status_id, project_id, stage, gate_status, gate_result_json)
VALUES (?, ?, ?, ?, json(?))
ON CONFLICT(project_id, stage) DO UPDATE SET
  gate_status = excluded.gate_status,
  gate_result_json = excluded.gate_result_json,
  updated_at = datetime('now');
```

### Write Audit Event

```sql
INSERT INTO audit_event_log 
  (audit_id, event_type, project_id, related_id, related_table, 
   actor, event_summary, event_detail_json)
VALUES (?, ?, ?, ?, ?, ?, ?, json(?));
```

### Get Stage Status with Prerequisites

```sql
SELECT ps.stage, ps.gate_status, ps.gate_result_json
FROM project_stage_status ps
WHERE ps.project_id = ?
  AND ps.stage IN (?, ?, ?, ?)  -- e.g., ('S1', 'S2', 'S3', 'S4')
ORDER BY ps.stage;
```

### Count Rule Outcomes by Severity

```sql
SELECT severity_applied, COUNT(*) as count
FROM validation_result
WHERE project_id = ? AND run_id = ?
GROUP BY severity_applied
ORDER BY severity_applied;
```

---

## 9. ERROR CODES & RESOLUTION

### Schema Errors

| Error | Cause | Resolution |
|-------|-------|-----------|
| **FOREIGN KEY constraint failed** | Insert/Update violates FK | Verify referenced ID exists; check ON DELETE policy |
| **UNIQUE constraint failed** | Duplicate value in UNIQUE column | Check existing values; use INSERT OR IGNORE if appropriate |
| **CHECK constraint failed** | Value violates CHECK condition | Verify value is in allowed enum (e.g., gate_status must be PENDING/OPEN/PASSED/BLOCKED/LOCKED) |
| **PRAGMA foreign_keys not enabled** | FK constraints ignored | Re-issue `PRAGMA foreign_keys = ON;` on connection |

### Engine Errors

| Error | Cause | Resolution |
|-------|-------|-----------|
| **project_id not found** | project_master query returns no rows | Verify project exists; create project_master row first |
| **rule_id references non-existent field_id** | Orphaned FK in validation_rule_master | Run integrity check; delete orphaned rules |
| **blocker_registry overflow** | Accumulating too many failed rules | Check for runaway validation loops; limit rules per stage |
| **gate_result missing mandatory keys** | severity_handler.gate_result() incomplete | Verify all severity counts initialized in handler |

### Audit Errors

| Error | Cause | Resolution |
|-------|-------|-----------|
| **IMMUTABLE: audit_event_log rows cannot be updated** | Attempted UPDATE on audit_event_log | This is expected behavior; audit events are append-only. Use SELECT or INSERT, never UPDATE. |
| **IMMUTABLE: audit_event_log rows cannot be deleted** | Attempted DELETE on audit_event_log | This is expected behavior. Archive old events separately if needed. |

### Migration Errors

| Error | Cause | Resolution |
|-------|-------|-----------|
| **Migration script not found** | migrate_v{N}_to_v{N+1}.sql missing | Create migration script before upgrading |
| **Integrity check failed after migration** | Schema corruption during upgrade | Restore backup; re-run migration carefully; check for broken triggers/indexes |
| **schema_version mismatch** | Database version != expected version | Verify database is correct; check schema_version in project_master |

---

## 10. DEVELOPMENT CHECKLIST

### New Feature Development (e.g., Adding L06 Layer)

- [ ] **Design Phase**
  - [ ] Define layer logic and test cases
  - [ ] Map to validation_rule_master columns
  - [ ] Plan database schema changes (if needed)

- [ ] **Schema Phase**
  - [ ] Write migration script (migrate_v{N}_to_v{N+1}.sql)
  - [ ] Test migration on dev database
  - [ ] Test rollback script (migrate_down_v{N}_to_v{N-1}.sql)
  - [ ] Verify indexes and triggers still work

- [ ] **Implementation Phase**
  - [ ] Implement layer evaluator (layer_06_*.py)
  - [ ] Register in engine_core dispatch
  - [ ] Write unit tests (test_layer_06.py)
  - [ ] Test with sample rules and data

- [ ] **Integration Phase**
  - [ ] Seed L06 rules into validation_rule_master
  - [ ] Test engine.run() with L06 rules active
  - [ ] Verify audit_event_log captures layer execution
  - [ ] Test gate result includes L06 outcomes

- [ ] **Documentation Phase**
  - [ ] Update Block documentation
  - [ ] Update this Quick Reference Guide
  - [ ] Add L06 to Layer Stack (Section 5)
  - [ ] Document new validation rules

- [ ] **Deployment Phase**
  - [ ] Get technical review approval
  - [ ] Create release notes
  - [ ] Plan rollback scenario
  - [ ] Deploy to dev → staging → production

### Database Health Check

```bash
# Run these commands regularly

# 1. Integrity check
sqlite3 lane1.db "PRAGMA integrity_check;"
# Expected: 'ok'

# 2. Foreign key check
sqlite3 lane1.db "PRAGMA foreign_key_list;"
# Expected: All FKs listed correctly

# 3. Row counts
sqlite3 lane1.db << EOF
  SELECT 'project_master' as tbl, COUNT(*) as cnt FROM project_master
  UNION ALL SELECT 'module_registry', COUNT(*) FROM module_registry
  UNION ALL SELECT 'field_dictionary', COUNT(*) FROM field_dictionary
  UNION ALL SELECT 'validation_rule_master', COUNT(*) FROM validation_rule_master
  UNION ALL SELECT 'validation_result', COUNT(*) FROM validation_result
  UNION ALL SELECT 'project_stage_status', COUNT(*) FROM project_stage_status
  UNION ALL SELECT 'audit_event_log', COUNT(*) FROM audit_event_log;
EOF

# 4. Database file size
ls -lh lane1.db lane1.db-wal lane1.db-shm 2>/dev/null || echo "No WAL files"

# 5. Vacuum to clean up space
sqlite3 lane1.db "VACUUM;"

# 6. Checkpoint WAL
sqlite3 lane1.db "PRAGMA wal_checkpoint(RESTART);"
```

### Testing Checklist

- [ ] **Unit Tests**
  - [ ] Each layer evaluator: test on valid, invalid, edge cases
  - [ ] Severity handler: test all severity combinations
  - [ ] Blocker registry: test registration and summary
  - [ ] Audit writer: test immutability (UPDATE/DELETE should fail)

- [ ] **Integration Tests**
  - [ ] engine.run() with S1 → returns gate_result with PASS/BLOCKED
  - [ ] Hard-gate S4 → zero blockers = PASSED; any blocker = BLOCKED
  - [ ] Hard-gate S5 → same + prerequisite S4=PASSED
  - [ ] Prerequisite check → BLOCKED if predecessor not PASSED
  - [ ] Validation result written correctly (run_id, field_value_snap, etc.)
  - [ ] Audit event written correctly (event_type, detail_json, immutable)

- [ ] **Data Quality Tests**
  - [ ] No orphaned FKs (integrity_check passes)
  - [ ] No duplicate entries (UNIQUE constraints enforced)
  - [ ] Seed data counts correct (7 modules, 16+ fields, 15+ rules)
  - [ ] Cascade deletes work correctly (delete module → delete fields → delete mappings)

- [ ] **Performance Tests**
  - [ ] rule_loader.load_rules(stage) < 100ms
  - [ ] engine.run() with 50 rules < 500ms
  - [ ] validation_result INSERT batch of 50 < 100ms
  - [ ] Query large validation_result table (1M+ rows) < 1s

---

## QUICK LINKS

### Documentation
- **Block 1 (Schema):** Lane_1__Block1_schema_core.sql
- **Block 2 (Engine):** Lane1_Block2_Rule_Engine_Core.xlsx
- **Block 3 (Layers):** Lane1_Block3_Core_Layers_Hard_Gates.xlsx
- **Block 4 (Packaging):** BLOCK_4_Lane_Packaging_Note.md
- **Block 5 (Initialization):** BLOCK_5_Seed_Data_Migration_Initialization.md

### Key Configuration Files
- **Database:** lane1.db (SQLite)
- **Seed Data:** lane1_seed_data.sql (to be created)
- **Migration Runner:** migrate.py (to be created)
- **Initialization:** init_lane1.py (to be created)

### Useful Commands

```bash
# Open database
sqlite3 lane1.db

# Export schema
sqlite3 lane1.db ".schema" > schema_dump.sql

# Backup database
cp lane1.db backups/backup_$(date -u +%Y%m%dT%H%M%S).db

# Initialize fresh database
python init_lane1.py --db lane1.db

# Migrate to next version
python migrate.py --db lane1.db --migrate-to 2
```

---

**End of Quick Reference Guide**

*Use this guide for quick lookups during development. Refer to full Block documents for detailed specifications.*
