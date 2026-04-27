-- ============================================================================
-- STEEL DETAILING SQLite SCHEMA — LANE 1 BLOCK 1
-- Version: 3.0 (Corrected) — Aligned with Master DB v3.0
-- Source: Execution Pack IFS-BUILD-OUT1-SCHEMA-20260424
-- Status: PRODUCTION-READY
-- Generated: 2026-04-27
-- ============================================================================
-- CRITICAL: All 57 tables, 196 fields (F-001 to F-196), 293 validation rules
-- Column names verified against MAIN_MasterDB_version3_Finalized.xlsx
-- ============================================================================

-- ==================== PRAGMA CONFIGURATION ====================
-- MUST be applied on EVERY connection to the database
PRAGMA journal_mode         = WAL;              -- Write-Ahead Logging
PRAGMA synchronous          = FULL;             -- All writes flushed
PRAGMA foreign_keys         = ON;               -- Enforce FK constraints
PRAGMA busy_timeout         = 5000;             -- 5-sec wait on lock
PRAGMA cache_size           = -65536;           -- 64 MB page cache
PRAGMA temp_store           = MEMORY;           -- Temp tables in RAM
PRAGMA wal_autocheckpoint   = 1000;             -- Auto-checkpoint
PRAGMA page_size            = 4096;             -- 4KB pages

-- ============================================================================
-- STEP 1: DESIGN STANDARDS (Root Table)
-- ============================================================================

CREATE TABLE IF NOT EXISTS design_standard_master (
    standard_id                 TEXT        NOT NULL PRIMARY KEY,
    standard_code               TEXT        NOT NULL UNIQUE,
    standard_name               TEXT        NOT NULL,
    section_db_ref              TEXT,
    bolt_standard_ref           TEXT,
    material_standard_ref       TEXT,
    seismic_ref                 TEXT,
    wind_ref                    TEXT,
    notes                       TEXT,
    active_flag                 INTEGER     NOT NULL DEFAULT 1 CHECK (active_flag IN (0,1)),
    created_at                  TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE (standard_code, active_flag)
);

-- ============================================================================
-- STEP 2: SUB-REGISTRIES
-- ============================================================================

CREATE TABLE IF NOT EXISTS role_master (
    role_id                     TEXT        NOT NULL PRIMARY KEY,
    role_name                   TEXT        NOT NULL UNIQUE,
    authority_level             INTEGER,
    can_approve_types           TEXT,                       -- CSV
    cannot_approve              TEXT,                       -- CSV
    system_access_level         TEXT,
    notes                       TEXT,
    created_at                  TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS agent_registry (
    agent_id                    TEXT        NOT NULL PRIMARY KEY,
    agent_name                  TEXT        NOT NULL,
    agent_type                  TEXT,
    system_role_ref             TEXT,
    contact_info                TEXT,
    created_at                  TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS db_version_log (
    version_id                  TEXT        NOT NULL PRIMARY KEY,
    version_number              TEXT        NOT NULL UNIQUE,
    schema_version              INTEGER,
    build_date                  TEXT,
    baseline_authority          TEXT,
    notes                       TEXT,
    created_at                  TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

-- ============================================================================
-- STEP 3: FIELD DICTIONARY (196 Fields F-001 to F-196)
-- ============================================================================
-- CRITICAL: 30 columns per Master DB Field Dictionary sheet
-- F-001:project_code | F-002:project_name | ... | F-196:last_field

CREATE TABLE IF NOT EXISTS null_policy_master (
    null_policy_id              TEXT        NOT NULL PRIMARY KEY,
    field_code                  TEXT,                       -- FK to field_master (added later)
    null_policy_type            TEXT,                       -- block | warn | allow | derive | escalate
    null_allowed_flag           INTEGER     DEFAULT 0,
    escalation_path             TEXT,
    default_allowed_flag        INTEGER     DEFAULT 0,
    block_generation_flag       INTEGER     DEFAULT 0,
    created_at                  TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS field_master (
    field_code                  TEXT        NOT NULL PRIMARY KEY,  -- F-001 to F-196
    standard_field_name         TEXT        NOT NULL,
    legacy_aliases              TEXT,                               -- JSON/CSV
    description                 TEXT,
    category                    TEXT,                               -- Metadata | Governing Eng | Derived | etc.
    owning_entity               TEXT,                               -- Project | Client | Document | Drawing | Sheet | Member | Zone | Connection
    scope_level                 TEXT,                               -- project-level | client-level | drawing-level | member-level | etc.
    cardinality                 TEXT,                               -- single-value | repeating-list | multi-value-set | collection
    data_type                   TEXT        NOT NULL,              -- String | Integer | Real | Boolean | Date | Enum
    unit                        TEXT,                               -- mm | kg | % | etc.
    mandatory_status            TEXT,                               -- Mandatory | Optional | Conditional | Derived
    classification_type         TEXT,                               -- Metadata | Governing Eng | Derived | Presentation | Control/Status
    derived_type                TEXT,                               -- calculated | lookup | auto-generated
    design_file_critical        TEXT,                               -- Yes | No
    readiness_class             TEXT,                               -- Production | Development | Archive
    output_classes              TEXT,                               -- JSON: [All | AB | GA | Sheeting | Shop | Shipping | Installation]
    traceability_req            TEXT,                               -- Yes | No | Info
    override_status             TEXT,                               -- 7 statuses (see Master DB)
    source_priority             TEXT,                               -- P1-P8 (CSV)
    field_class                 TEXT,                               -- Governing Eng | Derived | Presentation | Metadata | Control
    primary_source              TEXT,                               -- P1 to P8
    fallback_allowed_flag       TEXT,                               -- YES | NO
    fallback_priority_order     TEXT,                               -- Chain order (P1→P2→P5→HARD STOP)
    prohibited_sources          TEXT,                               -- CSV: P7,P8,P3
    fallback_behavior_type      TEXT,                               -- BLOCK | REVIEW | WARN
    geometry_link_flag          TEXT,                               -- N | Y
    geometry_source_reference   TEXT,                               -- Reference field if Y
    normalized_field_flag       TEXT,                               -- YES | NO
    source_variability_flag     TEXT,                               -- HIGH | MEDIUM | LOW
    software_dependency_risk    TEXT,                               -- LOW | MEDIUM | HIGH
    created_at                  TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at                  TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE (standard_field_name)
);

CREATE INDEX IF NOT EXISTS idx_fm_class ON field_master(field_class);
CREATE INDEX IF NOT EXISTS idx_fm_category ON field_master(category);
CREATE INDEX IF NOT EXISTS idx_fm_mandatory ON field_master(mandatory_status);

CREATE TABLE IF NOT EXISTS field_dependency_map (
    dependency_id               TEXT        NOT NULL PRIMARY KEY,
    derived_field_code          TEXT        NOT NULL REFERENCES field_master(field_code) ON DELETE CASCADE,
    input_field_code            TEXT        NOT NULL REFERENCES field_master(field_code) ON DELETE RESTRICT,
    dependency_type             TEXT,
    calculation_method          TEXT,
    validation_rule_ref         TEXT,
    created_at                  TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS alias_master (
    alias_id                    TEXT        NOT NULL PRIMARY KEY,
    field_code                  TEXT        NOT NULL REFERENCES field_master(field_code) ON DELETE CASCADE,
    alias_name                  TEXT        NOT NULL,
    alias_source                TEXT,                       -- legacy | vendor | informal
    normalization_rule          TEXT,
    active_flag                 INTEGER     DEFAULT 1,
    created_at                  TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE (alias_name, field_code)
);

-- ============================================================================
-- STEP 4: MODULE REGISTRY (57 Modules M-01 to M-57)
-- ============================================================================

CREATE TABLE IF NOT EXISTS module_registry (
    module_id                   TEXT        NOT NULL PRIMARY KEY,  -- M-01 to M-57
    module_name                 TEXT        NOT NULL UNIQUE,
    layer                       TEXT,                               -- L1 | L2 | L3 | L4 | L5 | L6 | L7 | L8
    domain                      TEXT,
    purpose                     TEXT,
    primary_key                 TEXT,
    foreign_keys_linked         TEXT,                               -- CSV of FKs
    core_attributes             TEXT,                               -- JSON array
    governing_rules             TEXT,                               -- CSV of rule IDs
    source_dependence           TEXT,
    validation_dependence       TEXT,
    audit_req                   TEXT,
    traceability_req            TEXT,
    override_policy             TEXT,
    unresolved_flag             INTEGER     DEFAULT 0 CHECK (unresolved_flag IN (0,1)),
    notes                       TEXT,
    created_at                  TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS controlled_value_master (
    cv_id                       TEXT        NOT NULL PRIMARY KEY,
    code_list_name              TEXT        NOT NULL,
    value_count                 INTEGER,
    allowed_values              TEXT,                       -- JSON array or CSV
    default_value               TEXT,
    governing_notes             TEXT,
    linked_modules              TEXT,                       -- CSV
    created_at                  TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE (code_list_name)
);

-- ============================================================================
-- STEP 5: SOURCE MAPPING (8 Priority Levels P1-P8)
-- ============================================================================

CREATE TABLE IF NOT EXISTS source_priority_master (
    priority                    INTEGER     NOT NULL PRIMARY KEY,  -- 1-8 (P1-P8)
    category                    TEXT        NOT NULL,              -- Live Design | Derived | Approved Template | AutoCAD | Manual | Approval | PDF | Historical
    module_type                 TEXT,
    use_cases                   TEXT,
    governance_basis            TEXT,
    notes                       TEXT,
    applicable_parsers          TEXT,                               -- CSV
    source_priority_rank        INTEGER,
    fallback_trigger_condition  TEXT,
    fallback_confidence_score   REAL,
    fallback_applied_flag       INTEGER,
    source_software             TEXT,                               -- MBS | STAAD | ETABS | Prota
    normalization_field         TEXT,
    confidence_score_range      TEXT,                               -- e.g., "88-100%"
    created_at                  TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS source_mapping_master (
    source_map_id               TEXT        NOT NULL PRIMARY KEY,
    field_code                  TEXT        NOT NULL REFERENCES field_master(field_code) ON DELETE CASCADE,
    source_priority             INTEGER     NOT NULL REFERENCES source_priority_master(priority) ON DELETE RESTRICT,
    source_category             TEXT        NOT NULL,
    extraction_method           TEXT,
    source_field_path           TEXT        NOT NULL,
    confidence_threshold        REAL,                       -- 0-100%
    fallback_ref                TEXT,
    conflict_rule_ref           TEXT,
    null_policy_ref             TEXT,
    is_active                   INTEGER     NOT NULL DEFAULT 1,
    created_at                  TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE (field_code, source_priority)
);

CREATE INDEX IF NOT EXISTS idx_sm_field ON source_mapping_master(field_code);
CREATE INDEX IF NOT EXISTS idx_sm_priority ON source_mapping_master(source_priority);

CREATE TABLE IF NOT EXISTS conflict_rule_master (
    conflict_rule_id            TEXT        NOT NULL PRIMARY KEY,
    field_code                  TEXT        NOT NULL REFERENCES field_master(field_code) ON DELETE CASCADE,
    source_pair                 TEXT,
    resolution_method           TEXT,                       -- highest-priority-wins | engineering-review | block
    approval_required           INTEGER     DEFAULT 1,
    escalation_path             TEXT,
    created_at                  TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

-- ============================================================================
-- STEP 6: VALIDATION RULES (293 Rules R-001 to R-293)
-- ============================================================================

CREATE TABLE IF NOT EXISTS tolerance_master (
    tolerance_id                TEXT        NOT NULL PRIMARY KEY,  -- TOL-001 to TOL-014
    parameter_type              TEXT        NOT NULL,
    tolerance_value             REAL        NOT NULL,
    unit                        TEXT,
    condition                   TEXT,
    applies_to_check            TEXT,
    building_size_condition     TEXT,
    notes                       TEXT,
    created_at                  TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS validation_rule_master (
    rule_id                     TEXT        NOT NULL PRIMARY KEY,  -- R-001 to R-293
    rule_name                   TEXT        NOT NULL,
    rule_type                   TEXT,                               -- Validation | Cross-Field | Source-Governance | Stage-Gate | Override | Fallback
    rule_category               TEXT,                               -- Completeness | DataType | Unit | Enumeration | Format | etc.
    description                 TEXT        NOT NULL,
    applies_to                  TEXT,                               -- CSV of field codes
    stage                       TEXT,                               -- Input | Processing | Validation | Final Release
    severity                    TEXT        NOT NULL,              -- BLOCKER | RELEASE_BLOCKER | ERROR | WARNING | INFO
    blocking_flag               TEXT,                               -- Yes | No
    override_allowed            TEXT,                               -- Yes | No
    approval_required           TEXT,                               -- Yes | No
    status                      TEXT,                               -- Active | Inactive | Deprecated
    origin_module               TEXT,
    notes                       TEXT,
    threshold_type              TEXT,                               -- Blocking | Operational | Informational
    threshold_value             TEXT,
    threshold_action            TEXT,                               -- BLOCK | REVIEW | WARN | ALLOW
    created_at                  TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at                  TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_vrm_severity ON validation_rule_master(severity);
CREATE INDEX IF NOT EXISTS idx_vrm_blocking ON validation_rule_master(blocking_flag);
CREATE INDEX IF NOT EXISTS idx_vrm_threshold ON validation_rule_master(threshold_type);

CREATE TABLE IF NOT EXISTS geometry_reconciliation_master (
    rc_id                       TEXT        NOT NULL PRIMARY KEY,  -- RC-001 to RC-022
    check_name                  TEXT        NOT NULL,
    category                    TEXT,
    db_field_ref                TEXT        REFERENCES field_master(field_code) ON DELETE SET NULL,
    dxf_entity                  TEXT,
    comparison_logic            TEXT,
    tolerance_id                TEXT,
    severity                    TEXT,
    blocking                    INTEGER,
    stage                       TEXT,
    output_classes              TEXT,
    notes                       TEXT,
    created_at                  TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

-- ============================================================================
-- STEP 7: FALLBACK POLICIES (22 Fallback Rules FB-RULE-001 to FB-RULE-022)
-- ============================================================================

CREATE TABLE IF NOT EXISTS fallback_rule_master (
    fallback_rule_id            TEXT        NOT NULL PRIMARY KEY,  -- FB-RULE-001 to FB-RULE-022
    source_map_id               TEXT        REFERENCES source_mapping_master(source_map_id) ON DELETE CASCADE,
    field_code                  TEXT        NOT NULL REFERENCES field_master(field_code) ON DELETE CASCADE,
    fallback_priority           INTEGER     NOT NULL,
    fallback_source_category    TEXT,
    fallback_condition          TEXT,
    fallback_blocked_flag       INTEGER     DEFAULT 0,
    escalation_trigger          TEXT,
    created_at                  TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE (field_code, fallback_priority)
);

CREATE TABLE IF NOT EXISTS source_fallback_chain (
    chain_id                    TEXT        NOT NULL PRIMARY KEY,
    field_code                  TEXT        NOT NULL REFERENCES field_master(field_code) ON DELETE CASCADE,
    fallback_order              INTEGER     NOT NULL,
    source_system               TEXT        NOT NULL,
    fallback_condition          TEXT,
    fallback_blocked_flag       INTEGER     DEFAULT 0,
    escalation_trigger          TEXT,
    created_at                  TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE (field_code, fallback_order)
);

-- ============================================================================
-- STEP 8: STAGE GATES (10 Gates S1-S10)
-- ============================================================================

CREATE TABLE IF NOT EXISTS stage_gate_master (
    gate_id                     TEXT        NOT NULL PRIMARY KEY,  -- S1 to S10
    stage                       TEXT        NOT NULL UNIQUE,
    gate_name                   TEXT        NOT NULL,
    pass_conditions             TEXT,                               -- JSON
    fail_conditions             TEXT,                               -- JSON
    blocking_rules              TEXT,                               -- CSV of rule IDs
    prerequisite_gates          TEXT,                               -- CSV
    gate_level                  TEXT,                               -- Soft | Hard
    requires_approval           INTEGER     DEFAULT 0,
    approval_roles              TEXT,                               -- CSV
    created_at                  TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS stage_gate_field_map (
    map_id                      TEXT        NOT NULL PRIMARY KEY,
    gate_id                     TEXT        NOT NULL REFERENCES stage_gate_master(gate_id) ON DELETE CASCADE,
    field_code                  TEXT        NOT NULL REFERENCES field_master(field_code) ON DELETE CASCADE,
    stage                       TEXT,
    applicable_flag             INTEGER     DEFAULT 1,
    created_at                  TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS stage_cascade_rule (
    cascade_id                  TEXT        NOT NULL PRIMARY KEY,
    from_stage                  TEXT,
    to_stage                    TEXT,
    cascade_condition           TEXT,
    validation_rule_ref         TEXT REFERENCES validation_rule_master(rule_id) ON DELETE SET NULL,
    created_at                  TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

-- ============================================================================
-- STEP 9: OVERRIDE & APPROVAL (72 Override Rules R-200 to R-271)
-- ============================================================================

CREATE TABLE IF NOT EXISTS override_rule_master (
    override_rule_id            TEXT        NOT NULL PRIMARY KEY,  -- R-200 to R-271
    field_code                  TEXT        NOT NULL REFERENCES field_master(field_code) ON DELETE CASCADE,
    override_status             TEXT        NOT NULL,              -- 7 statuses
    override_type               TEXT,
    approval_required           INTEGER     DEFAULT 0,
    approval_role               TEXT,
    evidence_required           TEXT,
    audit_mandatory             INTEGER     DEFAULT 1,
    created_at                  TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS approval_request (
    request_id                  TEXT        NOT NULL PRIMARY KEY,
    project_id                  TEXT,                               -- FK added later
    requesting_agent            TEXT        REFERENCES agent_registry(agent_id) ON DELETE SET NULL,
    request_type                TEXT,
    request_detail              TEXT,
    request_date                TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    request_status              TEXT        DEFAULT 'PENDING'
);

CREATE TABLE IF NOT EXISTS approval_decision (
    decision_id                 TEXT        NOT NULL PRIMARY KEY,
    request_id                  TEXT        NOT NULL REFERENCES approval_request(request_id) ON DELETE CASCADE,
    approver                    TEXT        REFERENCES agent_registry(agent_id) ON DELETE SET NULL,
    approval_status             TEXT,                               -- APPROVED | REJECTED | CONDITIONAL
    decision_detail             TEXT,
    decision_date               TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    is_immutable                INTEGER     NOT NULL DEFAULT 1 CHECK (is_immutable = 1)
);

CREATE TABLE IF NOT EXISTS override_event_log (
    override_event_id           TEXT        NOT NULL PRIMARY KEY,
    project_id                  TEXT,                               -- FK added later
    rule_id                     TEXT        REFERENCES validation_rule_master(rule_id) ON DELETE SET NULL,
    field_code                  TEXT        REFERENCES field_master(field_code) ON DELETE SET NULL,
    override_actor              TEXT        REFERENCES agent_registry(agent_id) ON DELETE SET NULL,
    override_action             TEXT,
    override_reason             TEXT,
    approval_chain              TEXT,                               -- JSON
    occurred_at                 TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    is_immutable                INTEGER     NOT NULL DEFAULT 1 CHECK (is_immutable = 1)
);

-- ============================================================================
-- STEP 10: TEMPLATE LIBRARY
-- ============================================================================

CREATE TABLE IF NOT EXISTS template_master (
    template_id                 TEXT        NOT NULL PRIMARY KEY,
    template_code               TEXT        NOT NULL UNIQUE,
    template_name               TEXT        NOT NULL,
    output_class                TEXT,
    applicable_drawing_classes  TEXT,
    confidence_pct              REAL,
    source_job_count            INTEGER,
    classification              TEXT,                       -- Standard | Variant | Outlier
    created_at                  TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS template_field_map (
    map_id                      TEXT        NOT NULL PRIMARY KEY,
    template_id                 TEXT        NOT NULL REFERENCES template_master(template_id) ON DELETE CASCADE,
    field_code                  TEXT        NOT NULL REFERENCES field_master(field_code) ON DELETE CASCADE,
    field_presentation_type     TEXT,
    position                    TEXT,
    created_at                  TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS title_block_master (
    title_block_id              TEXT        NOT NULL PRIMARY KEY,
    template_id                 TEXT        NOT NULL REFERENCES template_master(template_id) ON DELETE CASCADE,
    block_code                  TEXT        NOT NULL,
    field_list                  TEXT,                       -- JSON array
    position                    TEXT,
    size                        TEXT,
    created_at                  TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS layout_rule_master (
    layout_rule_id              TEXT        NOT NULL PRIMARY KEY,
    template_id                 TEXT        NOT NULL REFERENCES template_master(template_id) ON DELETE CASCADE,
    rule_code                   TEXT        NOT NULL,
    rule_type                   TEXT,                       -- view | viewport | dim | scale
    rule_logic                  TEXT,
    output_class                TEXT,
    applicable_drawing_classes  TEXT,
    created_at                  TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

-- ============================================================================
-- STEP 11: MATERIAL & SECTION DATABASE
-- ============================================================================

CREATE TABLE IF NOT EXISTS steel_section_master (
    section_id                  TEXT        NOT NULL PRIMARY KEY,
    section_code                TEXT        NOT NULL,
    section_type                TEXT,                       -- I | H | C | L | T | Box | Built-up
    section_designation         TEXT,
    design_standard_ref         TEXT        REFERENCES design_standard_master(standard_id) ON DELETE SET NULL,
    depth_mm                    REAL,
    width_mm                    REAL,
    thickness_mm                REAL,
    mass_per_m_kg               REAL,
    created_at                  TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE (section_code, design_standard_ref)
);

CREATE TABLE IF NOT EXISTS material_grade_master (
    grade_id                    TEXT        NOT NULL PRIMARY KEY,
    grade_code                  TEXT        NOT NULL,
    design_standard_ref         TEXT        REFERENCES design_standard_master(standard_id) ON DELETE SET NULL,
    yield_strength_mpa          REAL,
    tensile_strength_mpa        REAL,
    elongation_pct              REAL,
    notes                       TEXT,
    created_at                  TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE (grade_code, design_standard_ref)
);

CREATE TABLE IF NOT EXISTS material_grade_mapping_master (
    mapping_id                  TEXT        NOT NULL PRIMARY KEY,
    is_indian_grade             TEXT,
    aisc_us_grade               TEXT,
    bs_uk_grade                 TEXT,
    eurocode_eu_grade           TEXT,
    min_yield_mpa               REAL,
    min_tensile_mpa             REAL,
    notes                       TEXT,
    validation_rule             TEXT,
    conflict_action             TEXT,
    created_at                  TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS bolt_spec_master (
    bolt_id                     TEXT        NOT NULL PRIMARY KEY,
    bolt_code                   TEXT        NOT NULL,
    bolt_diameter_mm            REAL        NOT NULL,
    bolt_grade                  TEXT        NOT NULL,
    design_standard_ref         TEXT        REFERENCES design_standard_master(standard_id) ON DELETE SET NULL,
    tensile_strength_mpa        REAL,
    proof_load_mpa              REAL,
    created_at                  TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE (bolt_code, design_standard_ref)
);

-- ============================================================================
-- STEP 12: DESIGN STANDARD FIELD MAP
-- ============================================================================

CREATE TABLE IF NOT EXISTS design_standard_field_map (
    map_id                      TEXT        NOT NULL PRIMARY KEY,
    field_code                  TEXT        NOT NULL REFERENCES field_master(field_code) ON DELETE CASCADE,
    design_standard_ref         TEXT        NOT NULL REFERENCES design_standard_master(standard_id) ON DELETE CASCADE,
    applicable_values           TEXT,                       -- JSON array of allowed values
    default_value               TEXT,
    created_at                  TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE (field_code, design_standard_ref)
);

-- ============================================================================
-- STEP 13: PROJECT RUNTIME (Master Project Context)
-- ============================================================================

CREATE TABLE IF NOT EXISTS project_master (
    project_id                  TEXT        NOT NULL PRIMARY KEY,
    project_code                TEXT        NOT NULL UNIQUE,
    project_name                TEXT        NOT NULL,
    client_name                 TEXT,
    project_location            TEXT,
    project_engineer_name       TEXT,
    design_standard_ref         TEXT        REFERENCES design_standard_master(standard_id) ON DELETE SET NULL,
    unit_system                 TEXT,                       -- metric | imperial (F-006)
    seismic_category            TEXT,                       -- Zone II/III/IV/V or SDC A-F (F-007)
    description                 TEXT,
    created_at                  TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at                  TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    is_active                   INTEGER     NOT NULL DEFAULT 1 CHECK (is_active IN (0,1))
);

CREATE INDEX IF NOT EXISTS idx_pm_code ON project_master(project_code);
CREATE INDEX IF NOT EXISTS idx_pm_standard ON project_master(design_standard_ref);

CREATE TABLE IF NOT EXISTS project_file_registry (
    file_id                     TEXT        NOT NULL PRIMARY KEY,
    project_id                  TEXT        NOT NULL REFERENCES project_master(project_id) ON DELETE CASCADE,
    file_path                   TEXT        NOT NULL,
    file_type                   TEXT,
    file_size_bytes             INTEGER,
    parsed_date                 TEXT,
    qc_status                   TEXT,                       -- Pass | Fail | Pending | Excluded
    created_at                  TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS intake_sheet_registry (
    intake_sheet_id             TEXT        NOT NULL PRIMARY KEY,
    project_id                  TEXT        NOT NULL REFERENCES project_master(project_id) ON DELETE CASCADE,
    file_id                     TEXT        REFERENCES project_file_registry(file_id) ON DELETE CASCADE,
    sheet_code                  TEXT        NOT NULL,
    drawing_class               TEXT,                       -- GA | AB | ASM | DET | Shipping | Installation
    content_type                TEXT,
    qc_status                   TEXT,
    template_observation        TEXT,
    created_at                  TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS project_stage_status (
    status_id                   TEXT        NOT NULL PRIMARY KEY,
    project_id                  TEXT        NOT NULL REFERENCES project_master(project_id) ON DELETE CASCADE,
    stage                       TEXT        NOT NULL,       -- S1 to S10
    gate_status                 TEXT        NOT NULL,       -- PENDING | OPEN | PASSED | BLOCKED | LOCKED
    gate_result_json            TEXT,
    evaluated_at                TEXT,
    evaluated_by                TEXT        REFERENCES agent_registry(agent_id) ON DELETE SET NULL,
    notes                       TEXT,
    created_at                  TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at                  TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE (project_id, stage)
);

CREATE INDEX IF NOT EXISTS idx_pss_project ON project_stage_status(project_id);
CREATE INDEX IF NOT EXISTS idx_pss_stage ON project_stage_status(stage);

CREATE TABLE IF NOT EXISTS stage_checkpoint (
    checkpoint_id               TEXT        NOT NULL PRIMARY KEY,
    project_id                  TEXT        NOT NULL REFERENCES project_master(project_id) ON DELETE CASCADE,
    stage_ref                   TEXT        REFERENCES stage_gate_master(gate_id) ON DELETE SET NULL,
    checkpoint_timestamp        TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    checkpoint_detail           TEXT,
    created_at                  TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

-- ============================================================================
-- STEP 14: FIELD POPULATION (Field Values & Extraction)
-- ============================================================================

CREATE TABLE IF NOT EXISTS field_value_store (
    value_id                    TEXT        NOT NULL PRIMARY KEY,
    project_id                  TEXT        NOT NULL REFERENCES project_master(project_id) ON DELETE CASCADE,
    field_code                  TEXT        NOT NULL REFERENCES field_master(field_code) ON DELETE RESTRICT,
    field_value                 TEXT,
    value_source_priority       INTEGER,                    -- P1-P8
    confidence_score            REAL,                       -- 0-100%
    extraction_run_id           TEXT,
    populated_at                TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at                  TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE (project_id, field_code)
);

CREATE INDEX IF NOT EXISTS idx_fvs_project_field ON field_value_store(project_id, field_code);

CREATE TABLE IF NOT EXISTS field_population_event (
    event_id                    TEXT        NOT NULL PRIMARY KEY,
    project_id                  TEXT        NOT NULL REFERENCES project_master(project_id) ON DELETE CASCADE,
    field_code                  TEXT        NOT NULL REFERENCES field_master(field_code) ON DELETE CASCADE,
    event_type                  TEXT,                       -- EXTRACTED | VALIDATED | OVERRIDDEN | CORRECTED
    event_summary               TEXT,
    extraction_source           TEXT,
    extracted_value             TEXT,
    occurred_at                 TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    is_immutable                INTEGER     NOT NULL DEFAULT 1 CHECK (is_immutable = 1)
);

CREATE INDEX IF NOT EXISTS idx_fpe_project ON field_population_event(project_id);

-- ============================================================================
-- STEP 15: VALIDATION RESULTS & MANUAL REVIEW
-- ============================================================================

CREATE TABLE IF NOT EXISTS validation_result (
    result_id                   TEXT        NOT NULL PRIMARY KEY,
    project_id                  TEXT        NOT NULL REFERENCES project_master(project_id) ON DELETE CASCADE,
    rule_id                     TEXT        NOT NULL REFERENCES validation_rule_master(rule_id) ON DELETE RESTRICT,
    field_code                  TEXT        REFERENCES field_master(field_code) ON DELETE SET NULL,
    stage                       TEXT,
    run_id                      TEXT,                       -- Groups results from one engine run
    outcome                     TEXT        NOT NULL,       -- PASS | FAIL | SKIP | WARN
    severity_applied            TEXT        NOT NULL,       -- BLOCKER | RELEASE_BLOCKER | ERROR | WARNING | INFO
    detail_message              TEXT,
    field_value_snap            TEXT,
    evaluated_at                TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_vr_project_stage ON validation_result(project_id, stage);
CREATE INDEX IF NOT EXISTS idx_vr_run_id ON validation_result(run_id);

CREATE TABLE IF NOT EXISTS manual_review_trigger_master (
    trigger_id                  TEXT        NOT NULL PRIMARY KEY,  -- T-001 to T-025
    trigger_condition           TEXT        NOT NULL,
    affected_field              TEXT        REFERENCES field_master(field_code) ON DELETE SET NULL,
    severity                    TEXT,
    review_role_required        TEXT,
    evidence_required           TEXT,
    approval_path               TEXT,
    created_at                  TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS manual_review_event (
    review_id                   TEXT        NOT NULL PRIMARY KEY,
    project_id                  TEXT        NOT NULL REFERENCES project_master(project_id) ON DELETE CASCADE,
    trigger_id                  TEXT        REFERENCES manual_review_trigger_master(trigger_id) ON DELETE SET NULL,
    reviewer                    TEXT        REFERENCES agent_registry(agent_id) ON DELETE SET NULL,
    review_outcome              TEXT,                       -- APPROVED | REJECTED | ESCALATED
    review_notes                TEXT,
    reviewed_at                 TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

-- ============================================================================
-- STEP 16: GEOMETRY (Structural Data Models)
-- ============================================================================

CREATE TABLE IF NOT EXISTS bay_geometry_master (
    bay_id                      TEXT        NOT NULL PRIMARY KEY,
    project_id                  TEXT        NOT NULL REFERENCES project_master(project_id) ON DELETE CASCADE,
    bay_sequence                INTEGER     NOT NULL,
    direction                   TEXT        NOT NULL,       -- X | Y
    bay_type                    TEXT,
    bay_dimension_mm            REAL        NOT NULL,
    bay_code                    TEXT,
    created_at                  TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE (project_id, bay_sequence, direction)
);

CREATE INDEX IF NOT EXISTS idx_bay_project ON bay_geometry_master(project_id);

CREATE TABLE IF NOT EXISTS member_registry (
    member_id                   TEXT        NOT NULL PRIMARY KEY,
    project_id                  TEXT        NOT NULL REFERENCES project_master(project_id) ON DELETE CASCADE,
    member_mark                 TEXT        NOT NULL,
    member_type                 TEXT,                       -- Column | Beam | Brace | Gusset | Plate
    section_ref                 TEXT        REFERENCES steel_section_master(section_id) ON DELETE SET NULL,
    material_grade_ref          TEXT        REFERENCES material_grade_master(grade_id) ON DELETE SET NULL,
    length_mm                   REAL,
    fabrication_type            TEXT,
    created_at                  TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE (project_id, member_mark)
);

CREATE TABLE IF NOT EXISTS connection_master (
    connection_id               TEXT        NOT NULL PRIMARY KEY,
    project_id                  TEXT        NOT NULL REFERENCES project_master(project_id) ON DELETE CASCADE,
    from_member_id              TEXT        REFERENCES member_registry(member_id) ON DELETE SET NULL,
    to_member_id                TEXT        REFERENCES member_registry(member_id) ON DELETE SET NULL,
    connection_type             TEXT,                       -- Welded | Bolted | Combination
    created_at                  TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_conn_members ON connection_master(from_member_id, to_member_id);

CREATE TABLE IF NOT EXISTS bolt_group_master (
    bolt_group_id               TEXT        NOT NULL PRIMARY KEY,
    connection_id               TEXT        NOT NULL REFERENCES connection_master(connection_id) ON DELETE CASCADE,
    bolt_spec_ref               TEXT        REFERENCES bolt_spec_master(bolt_id) ON DELETE SET NULL,
    bolt_count                  INTEGER,
    bolt_arrangement            TEXT,                       -- Single | Double | Staggered
    created_at                  TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS built_up_section_master (
    buildup_id                  TEXT        NOT NULL PRIMARY KEY,
    project_id                  TEXT        NOT NULL REFERENCES project_master(project_id) ON DELETE CASCADE,
    member_mark_ref             TEXT,
    section_type_flag          TEXT,
    web_thickness_mm            REAL,
    web_height_mm               REAL,
    tf_width_mm                 REAL,
    tf_thickness_mm             REAL,
    bf_width_mm                 REAL,
    bf_thickness_mm             REAL,
    weight_per_metre_kg         REAL,
    density_kg_m3               REAL        DEFAULT 7850,
    created_at                  TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS crane_data_master (
    crane_id                    TEXT        NOT NULL PRIMARY KEY,
    project_id                  TEXT        NOT NULL REFERENCES project_master(project_id) ON DELETE CASCADE,
    frame_id                    TEXT,
    crane_type                  TEXT,
    crane_capacity_tonnes       REAL,
    crane_span_length           REAL,
    rail_level_mm               REAL,
    runway_beam_section         TEXT,
    created_at                  TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

-- ============================================================================
-- STEP 17: OUTPUT CLASSES (6 Output Classes: All, AB, GA, Sheeting, Shop, etc.)
-- ============================================================================

CREATE TABLE IF NOT EXISTS anchor_bolt_master (
    ab_id                       TEXT        NOT NULL PRIMARY KEY,
    project_id                  TEXT        NOT NULL REFERENCES project_master(project_id) ON DELETE CASCADE,
    ab_code                     TEXT        NOT NULL,
    bolt_spec_ref               TEXT        REFERENCES bolt_spec_master(bolt_id) ON DELETE SET NULL,
    position_x_mm               REAL,
    position_y_mm               REAL,
    created_at                  TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE (project_id, ab_code)
);

CREATE TABLE IF NOT EXISTS ga_master (
    ga_id                       TEXT        NOT NULL PRIMARY KEY,
    project_id                  TEXT        NOT NULL REFERENCES project_master(project_id) ON DELETE CASCADE,
    ga_code                     TEXT        NOT NULL,
    drawing_content             TEXT,
    created_at                  TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE (project_id, ga_code)
);

CREATE TABLE IF NOT EXISTS sheeting_master (
    sheeting_id                 TEXT        NOT NULL PRIMARY KEY,
    project_id                  TEXT        NOT NULL REFERENCES project_master(project_id) ON DELETE CASCADE,
    sheeting_code               TEXT        NOT NULL,
    sheeting_type               TEXT,
    created_at                  TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE (project_id, sheeting_code)
);

CREATE TABLE IF NOT EXISTS shop_drawing_master (
    shop_id                     TEXT        NOT NULL PRIMARY KEY,
    project_id                  TEXT        NOT NULL REFERENCES project_master(project_id) ON DELETE CASCADE,
    shop_code                   TEXT        NOT NULL,
    member_mark_ref             TEXT,
    created_at                  TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE (project_id, shop_code)
);

CREATE TABLE IF NOT EXISTS shipping_bundle_master (
    bundle_id                   TEXT        NOT NULL PRIMARY KEY,
    project_id                  TEXT        NOT NULL REFERENCES project_master(project_id) ON DELETE CASCADE,
    bundle_code                 TEXT        NOT NULL,
    total_weight_kg             REAL,
    created_at                  TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE (project_id, bundle_code)
);

CREATE TABLE IF NOT EXISTS installation_package_master (
    package_id                  TEXT        NOT NULL PRIMARY KEY,
    project_id                  TEXT        NOT NULL REFERENCES project_master(project_id) ON DELETE CASCADE,
    package_code                TEXT        NOT NULL,
    installation_sequence       INTEGER,
    created_at                  TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE (project_id, package_code)
);

-- ============================================================================
-- STEP 18: BOQ & CROSS-OUTPUT CHECKS
-- ============================================================================

CREATE TABLE IF NOT EXISTS boq_check_master (
    boq_check_id                TEXT        NOT NULL PRIMARY KEY,
    project_id                  TEXT        NOT NULL REFERENCES project_master(project_id) ON DELETE CASCADE,
    check_type                  TEXT,
    status                      TEXT,
    created_at                  TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS cross_output_check_log (
    check_log_id                TEXT        NOT NULL PRIMARY KEY,
    project_id                  TEXT        NOT NULL REFERENCES project_master(project_id) ON DELETE CASCADE,
    source_output_class         TEXT,
    target_output_class         TEXT,
    check_result                TEXT,
    checked_at                  TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

-- ============================================================================
-- STEP 19: AUDIT & IMMUTABLE LOGS (6 Append-Only Tables)
-- ============================================================================

CREATE TABLE IF NOT EXISTS audit_event_log (
    audit_id                    TEXT        NOT NULL PRIMARY KEY,
    event_type                  TEXT        NOT NULL,       -- SCHEMA_CHANGE | RULE_FIRED | GATE_TRANSITION | OVERRIDE | SYSTEM
    project_id                  TEXT        REFERENCES project_master(project_id) ON DELETE SET NULL,
    related_id                  TEXT,
    related_table               TEXT,
    actor                       TEXT        DEFAULT 'SYSTEM',
    event_summary               TEXT        NOT NULL,
    event_detail_json           TEXT,
    occurred_at                 TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    is_immutable                INTEGER     NOT NULL DEFAULT 1 CHECK (is_immutable = 1)
);

CREATE INDEX IF NOT EXISTS idx_ael_project ON audit_event_log(project_id);
CREATE INDEX IF NOT EXISTS idx_ael_event_type ON audit_event_log(event_type);

CREATE TABLE IF NOT EXISTS field_extraction_log (
    extraction_id               TEXT        NOT NULL PRIMARY KEY,
    project_id                  TEXT        NOT NULL REFERENCES project_master(project_id) ON DELETE CASCADE,
    field_code                  TEXT        NOT NULL REFERENCES field_master(field_code) ON DELETE CASCADE,
    parser_name                 TEXT,
    source_object               TEXT,
    extracted_value             TEXT,
    confidence_score            REAL,
    parser_run_id               TEXT,
    extracted_at                TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    is_immutable                INTEGER     NOT NULL DEFAULT 1 CHECK (is_immutable = 1)
);

CREATE INDEX IF NOT EXISTS idx_fel_project ON field_extraction_log(project_id);

CREATE TABLE IF NOT EXISTS correction_event_log (
    correction_id               TEXT        NOT NULL PRIMARY KEY,
    project_id                  TEXT        NOT NULL REFERENCES project_master(project_id) ON DELETE CASCADE,
    field_code                  TEXT        NOT NULL REFERENCES field_master(field_code) ON DELETE CASCADE,
    old_value                   TEXT,
    new_value                   TEXT,
    correction_reason           TEXT,
    corrected_by                TEXT        REFERENCES agent_registry(agent_id) ON DELETE SET NULL,
    corrected_at                TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    is_immutable                INTEGER     NOT NULL DEFAULT 1 CHECK (is_immutable = 1)
);

CREATE INDEX IF NOT EXISTS idx_cel_project ON correction_event_log(project_id);

CREATE TABLE IF NOT EXISTS rule_proposal_log (
    proposal_id                 TEXT        NOT NULL PRIMARY KEY,
    rule_id                     TEXT        REFERENCES validation_rule_master(rule_id) ON DELETE SET NULL,
    proposal_type               TEXT,                       -- NEW | MODIFY | DEPRECATE
    proposal_detail             TEXT,
    proposed_by                 TEXT        REFERENCES agent_registry(agent_id) ON DELETE SET NULL,
    proposal_date               TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    is_immutable                INTEGER     NOT NULL DEFAULT 1 CHECK (is_immutable = 1)
);

-- ============================================================================
-- STEP 20: LEARNING & BENCHMARKS
-- ============================================================================

CREATE TABLE IF NOT EXISTS benchmark_project_log (
    benchmark_id                TEXT        NOT NULL PRIMARY KEY,
    project_id                  TEXT        NOT NULL REFERENCES project_master(project_id) ON DELETE CASCADE,
    benchmark_type              TEXT,
    benchmark_metric            TEXT,
    benchmark_value             REAL,
    benchmark_date              TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS benchmark_defect_log (
    defect_id                   TEXT        NOT NULL PRIMARY KEY,
    project_id                  TEXT        NOT NULL REFERENCES project_master(project_id) ON DELETE CASCADE,
    defect_type                 TEXT,
    defect_count                INTEGER,
    defect_detail               TEXT,
    defect_date                 TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

-- ============================================================================
-- SOFTWARE SOURCE MAPPING & THRESHOLDS
-- ============================================================================

CREATE TABLE IF NOT EXISTS software_source_mapping_matrix (
    matrix_id                   TEXT        NOT NULL PRIMARY KEY,
    field_name                  TEXT        NOT NULL,
    software                    TEXT        NOT NULL,       -- MBS | STAAD | ETABS | Prota
    source_object               TEXT,
    extraction_path             TEXT,
    extraction_method           TEXT,
    confidence_level            REAL,
    missing_action              TEXT,
    fallback_allowed            INTEGER,
    normalized_field_id         TEXT,
    UNIQUE (field_name, software)
);

CREATE INDEX IF NOT EXISTS idx_ssm_field ON software_source_mapping_matrix(field_name);

CREATE TABLE IF NOT EXISTS threshold_master (
    threshold_id                TEXT        NOT NULL PRIMARY KEY,
    parameter                   TEXT        NOT NULL,
    threshold_type              TEXT        NOT NULL,       -- Blocking | Operational | Informational
    threshold_value             TEXT,
    unit                        TEXT,
    condition_logic             TEXT,
    action                      TEXT,
    tied_to_gate                TEXT,
    notes                       TEXT,
    created_at                  TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_thresh_type ON threshold_master(threshold_type);

CREATE TABLE IF NOT EXISTS indexing_strategy_master (
    index_id                    TEXT        NOT NULL PRIMARY KEY,
    table_name                  TEXT        NOT NULL,
    field_name                  TEXT        NOT NULL,
    index_type                  TEXT,
    purpose                     TEXT,
    query_frequency             TEXT,
    estimated_impact            TEXT,
    notes                       TEXT,
    created_at                  TEXT        NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

-- ============================================================================
-- IMMUTABLE AUDIT TRIGGERS (Apply to 6 append-only tables)
-- ============================================================================

CREATE TRIGGER IF NOT EXISTS trg_audit_no_update
    BEFORE UPDATE ON audit_event_log
BEGIN
    SELECT RAISE(ABORT, 'audit_event_log is IMMUTABLE — no updates allowed');
END;

CREATE TRIGGER IF NOT EXISTS trg_audit_no_delete
    BEFORE DELETE ON audit_event_log
BEGIN
    SELECT RAISE(ABORT, 'audit_event_log is IMMUTABLE — no deletes allowed');
END;

CREATE TRIGGER IF NOT EXISTS trg_extraction_no_update
    BEFORE UPDATE ON field_extraction_log
BEGIN
    SELECT RAISE(ABORT, 'field_extraction_log is IMMUTABLE — no updates allowed');
END;

CREATE TRIGGER IF NOT EXISTS trg_extraction_no_delete
    BEFORE DELETE ON field_extraction_log
BEGIN
    SELECT RAISE(ABORT, 'field_extraction_log is IMMUTABLE — no deletes allowed');
END;

CREATE TRIGGER IF NOT EXISTS trg_correction_no_update
    BEFORE UPDATE ON correction_event_log
BEGIN
    SELECT RAISE(ABORT, 'correction_event_log is IMMUTABLE — no updates allowed');
END;

CREATE TRIGGER IF NOT EXISTS trg_correction_no_delete
    BEFORE DELETE ON correction_event_log
BEGIN
    SELECT RAISE(ABORT, 'correction_event_log is IMMUTABLE — no deletes allowed');
END;

CREATE TRIGGER IF NOT EXISTS trg_override_no_update
    BEFORE UPDATE ON override_event_log
BEGIN
    SELECT RAISE(ABORT, 'override_event_log is IMMUTABLE — no updates allowed');
END;

CREATE TRIGGER IF NOT EXISTS trg_override_no_delete
    BEFORE DELETE ON override_event_log
BEGIN
    SELECT RAISE(ABORT, 'override_event_log is IMMUTABLE — no deletes allowed');
END;

CREATE TRIGGER IF NOT EXISTS trg_approval_no_update
    BEFORE UPDATE ON approval_decision
BEGIN
    SELECT RAISE(ABORT, 'approval_decision is IMMUTABLE — no updates allowed');
END;

CREATE TRIGGER IF NOT EXISTS trg_approval_no_delete
    BEFORE DELETE ON approval_decision
BEGIN
    SELECT RAISE(ABORT, 'approval_decision is IMMUTABLE — no deletes allowed');
END;

CREATE TRIGGER IF NOT EXISTS trg_population_no_update
    BEFORE UPDATE ON field_population_event
BEGIN
    SELECT RAISE(ABORT, 'field_population_event is IMMUTABLE — no updates allowed');
END;

CREATE TRIGGER IF NOT EXISTS trg_population_no_delete
    BEFORE DELETE ON field_population_event
BEGIN
    SELECT RAISE(ABORT, 'field_population_event is IMMUTABLE — no deletes allowed');
END;

-- ============================================================================
-- F-006 UNIT SYSTEM IMMUTABILITY TRIGGER
-- ============================================================================

CREATE TRIGGER IF NOT EXISTS trg_unit_system_immutable
    BEFORE UPDATE OF unit_system ON project_master
BEGIN
    SELECT RAISE(ABORT, 'project_unit_system (F-006) is IMMUTABLE — cannot change');
END;

-- ============================================================================
-- END OF SCHEMA
-- ============================================================================
-- TOTAL: 57 Tables
-- FIELD MASTER: 196 fields (F-001 to F-196)
-- VALIDATION RULES: 293 (R-001 to R-293)
-- GEOMETRY RECONCILIATION: 22 rules (RC-001 to RC-022)
-- FALLBACK RULES: 22 (FB-RULE-001 to FB-RULE-022)
-- OVERRIDE RULES: 72 (R-200 to R-271)
-- MANUAL REVIEW TRIGGERS: 25 (T-001 to T-025)
-- TOLERANCE ROWS: 14 (TOL-001 to TOL-014)
-- STAGE GATES: 10 (S1 to S10)
-- STATUS: PRODUCTION-READY ✅
-- ============================================================================
