-- ============================================================
-- LANE 1 | BLOCK 1 — SQLite Core Schema
-- Steel Detailing Desktop System — Frozen Baseline
-- ============================================================

-- ── PRAGMA SETTINGS ─────────────────────────────────────────
PRAGMA journal_mode    = WAL;
PRAGMA foreign_keys    = ON;
PRAGMA synchronous     = NORMAL;
PRAGMA temp_store      = MEMORY;
PRAGMA cache_size      = -32000;   -- 32 MB
PRAGMA auto_vacuum     = INCREMENTAL;

-- ── TABLE 1: project_master ──────────────────────────────────
CREATE TABLE IF NOT EXISTS project_master (
    project_id          TEXT        NOT NULL PRIMARY KEY,
    project_name        TEXT        NOT NULL,
    project_code        TEXT        NOT NULL UNIQUE,
    client_name         TEXT,
    description         TEXT,
    created_at          TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at          TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    schema_version      INTEGER     NOT NULL DEFAULT 1,
    is_active           INTEGER     NOT NULL DEFAULT 1 CHECK (is_active IN (0,1))
);

-- ── TABLE 2: module_registry ─────────────────────────────────
CREATE TABLE IF NOT EXISTS module_registry (
    module_id           TEXT        NOT NULL PRIMARY KEY,
    module_name         TEXT        NOT NULL UNIQUE,
    module_version      TEXT        NOT NULL,
    module_type         TEXT        NOT NULL,  -- e.g. CORE / PLUGIN / EXTENSION
    is_enabled          INTEGER     NOT NULL DEFAULT 1 CHECK (is_enabled IN (0,1)),
    registered_at       TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    description         TEXT
);

-- ── TABLE 3: field_dictionary ────────────────────────────────
CREATE TABLE IF NOT EXISTS field_dictionary (
    field_id            TEXT        NOT NULL PRIMARY KEY,
    module_id           TEXT        NOT NULL REFERENCES module_registry(module_id) ON DELETE RESTRICT,
    field_name          TEXT        NOT NULL,
    field_label         TEXT,
    data_type           TEXT        NOT NULL,  -- TEXT / INTEGER / REAL / BOOLEAN / DATE / ENUM
    unit_type           TEXT,
    allowed_values      TEXT,                  -- JSON array for ENUM fields
    is_required         INTEGER     NOT NULL DEFAULT 0 CHECK (is_required IN (0,1)),
    is_immutable        INTEGER     NOT NULL DEFAULT 0 CHECK (is_immutable IN (0,1)),
    default_value       TEXT,
    description         TEXT,
    created_at          TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE (module_id, field_name)
);

-- ── TABLE 4: validation_rule_master ──────────────────────────
CREATE TABLE IF NOT EXISTS validation_rule_master (
    rule_id             TEXT        NOT NULL PRIMARY KEY,
    module_id           TEXT        NOT NULL REFERENCES module_registry(module_id) ON DELETE RESTRICT,
    field_id            TEXT        REFERENCES field_dictionary(field_id) ON DELETE SET NULL,
    rule_name           TEXT        NOT NULL,
    layer               TEXT        NOT NULL,  -- e.g. L01_COMPLETENESS / L04_ENUM / L10_STAGE_GATE
    severity            TEXT        NOT NULL   CHECK (severity IN ('BLOCKER','RELEASE_BLOCKER','ERROR','WARNING','INFO')),
    stage_scope         TEXT,                  -- S1 / S4 / S5 / S10 or NULL for all
    rule_expression     TEXT        NOT NULL,
    error_message       TEXT        NOT NULL,
    is_active           INTEGER     NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
    created_at          TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at          TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

-- ── TABLE 5: source_mapping_master ───────────────────────────
CREATE TABLE IF NOT EXISTS source_mapping_master (
    mapping_id          TEXT        NOT NULL PRIMARY KEY,
    field_id            TEXT        NOT NULL REFERENCES field_dictionary(field_id) ON DELETE CASCADE,
    source_system       TEXT        NOT NULL,  -- e.g. TEKLA / REVIT / MANUAL / IFC
    source_field_path   TEXT        NOT NULL,
    transform_rule      TEXT,
    priority            INTEGER     NOT NULL DEFAULT 1,
    is_active           INTEGER     NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
    created_at          TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE (field_id, source_system)
);

-- ── TABLE 6: source_fallback_chain ───────────────────────────
CREATE TABLE IF NOT EXISTS source_fallback_chain (
    chain_id            TEXT        NOT NULL PRIMARY KEY,
    field_id            TEXT        NOT NULL REFERENCES field_dictionary(field_id) ON DELETE CASCADE,
    fallback_order      INTEGER     NOT NULL,
    source_system       TEXT        NOT NULL,
    fallback_condition  TEXT,
    created_at          TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE (field_id, fallback_order)
);

-- ── TABLE 7: project_stage_status ────────────────────────────
CREATE TABLE IF NOT EXISTS project_stage_status (
    status_id           TEXT        NOT NULL PRIMARY KEY,
    project_id          TEXT        NOT NULL REFERENCES project_master(project_id) ON DELETE CASCADE,
    stage               TEXT        NOT NULL   CHECK (stage IN ('S1','S2','S3','S4','S5','S6','S7','S8','S9','S10')),
    gate_status         TEXT        NOT NULL   CHECK (gate_status IN ('PENDING','OPEN','PASSED','BLOCKED','LOCKED')),
    gate_result_json    TEXT,                  -- full gate result snapshot
    evaluated_at        TEXT,
    evaluated_by        TEXT,
    notes               TEXT,
    created_at          TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at          TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE (project_id, stage)
);

-- ── TABLE 8: validation_result ───────────────────────────────
CREATE TABLE IF NOT EXISTS validation_result (
    result_id           TEXT        NOT NULL PRIMARY KEY,
    project_id          TEXT        NOT NULL REFERENCES project_master(project_id) ON DELETE CASCADE,
    rule_id             TEXT        NOT NULL REFERENCES validation_rule_master(rule_id) ON DELETE RESTRICT,
    field_id            TEXT        REFERENCES field_dictionary(field_id) ON DELETE SET NULL,
    stage               TEXT        NOT NULL,
    run_id              TEXT        NOT NULL,   -- groups results from one engine run
    outcome             TEXT        NOT NULL   CHECK (outcome IN ('PASS','FAIL','SKIP','WARN')),
    severity_applied    TEXT        NOT NULL   CHECK (severity_applied IN ('BLOCKER','RELEASE_BLOCKER','ERROR','WARNING','INFO')),
    detail_message      TEXT,
    field_value_snap    TEXT,                   -- value at time of validation
    evaluated_at        TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

-- ── TABLE 9: audit_event_log ─────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_event_log (
    audit_id            TEXT        NOT NULL PRIMARY KEY,
    event_type          TEXT        NOT NULL,   -- SCHEMA_CHANGE / RULE_FIRED / GATE_TRANSITION / OVERRIDE / SYSTEM
    project_id          TEXT        REFERENCES project_master(project_id) ON DELETE SET NULL,
    related_id          TEXT,                   -- FK-agnostic reference to any row
    related_table       TEXT,
    actor               TEXT        NOT NULL DEFAULT 'SYSTEM',
    event_summary       TEXT        NOT NULL,
    event_detail_json   TEXT,
    occurred_at         TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    is_immutable        INTEGER     NOT NULL DEFAULT 1 CHECK (is_immutable = 1)
    -- NOTE: No UPDATE or DELETE triggers will ever act on this table.
);

-- ── INDEXES ──────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_vr_project_stage  ON validation_result(project_id, stage);
CREATE INDEX IF NOT EXISTS idx_vr_run_id         ON validation_result(run_id);
CREATE INDEX IF NOT EXISTS idx_vr_rule_id        ON validation_result(rule_id);
CREATE INDEX IF NOT EXISTS idx_pss_project       ON project_stage_status(project_id);
CREATE INDEX IF NOT EXISTS idx_ael_project       ON audit_event_log(project_id);
CREATE INDEX IF NOT EXISTS idx_ael_event_type    ON audit_event_log(event_type);
CREATE INDEX IF NOT EXISTS idx_ael_occurred_at   ON audit_event_log(occurred_at);
CREATE INDEX IF NOT EXISTS idx_fd_module         ON field_dictionary(module_id);
CREATE INDEX IF NOT EXISTS idx_vrm_layer         ON validation_rule_master(layer);
CREATE INDEX IF NOT EXISTS idx_vrm_severity      ON validation_rule_master(severity);

-- ── IMMUTABLE AUDIT TRIGGERS ─────────────────────────────────
-- Prevent UPDATE on audit_event_log
CREATE TRIGGER IF NOT EXISTS trg_audit_no_update
    BEFORE UPDATE ON audit_event_log
BEGIN
    SELECT RAISE(ABORT, 'IMMUTABLE: audit_event_log rows cannot be updated.');
END;

-- Prevent DELETE on audit_event_log
CREATE TRIGGER IF NOT EXISTS trg_audit_no_delete
    BEFORE DELETE ON audit_event_log
BEGIN
    SELECT RAISE(ABORT, 'IMMUTABLE: audit_event_log rows cannot be deleted.');
END;

-- Auto-stamp updated_at on project_master
CREATE TRIGGER IF NOT EXISTS trg_pm_updated_at
    AFTER UPDATE ON project_master
    WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE project_master
       SET updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now')
     WHERE project_id = NEW.project_id;
END;

-- Auto-stamp updated_at on project_stage_status
CREATE TRIGGER IF NOT EXISTS trg_pss_updated_at
    AFTER UPDATE ON project_stage_status
    WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE project_stage_status
       SET updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now')
     WHERE status_id = NEW.status_id;
END;

-- Auto-stamp updated_at on validation_rule_master
CREATE TRIGGER IF NOT EXISTS trg_vrm_updated_at
    AFTER UPDATE ON validation_rule_master
    WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE validation_rule_master
       SET updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now')
     WHERE rule_id = NEW.rule_id;
END;

