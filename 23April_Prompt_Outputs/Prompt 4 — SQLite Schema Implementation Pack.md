# P4 — SQLite SCHEMA IMPLEMENTATION
## Infiniti Solutions Steel Detailing Automation — Phase 5 Desktop Build
**Document ID**: IFS-P4-SCHEMA-20260423  
**Authority Baseline**: IFS-RULE-REG-FINAL-20260423 · MasterDB v3+  
**SQLite Decision Ref**: TDN-DB-001 (April 23 2026)  
**Status**: IMPLEMENTATION READY — DB Team Deliverable

---

## 1. SQLite SCHEMA ARCHITECTURE

### 1.1 Governing Principles

- **Design file is absolute source of truth.** Historical data populates presentation-only tables.
- **57 physical tables** (54 active modules + 3 sub-registry tables) as specified in MasterDB v3+.
- All 293 active rules (R-001 to R-271, FB-RULE-001 to FB-RULE-022) are seeded as rows in `validation_rule_master`.
- 22 geometry reconciliation rules (RC-001 to RC-022) are seeded into `geometry_reconciliation_master`.
- Audit tables are **append-only, immutable** — no UPDATE or DELETE allowed.
- `project_unit_system` (F-006) is **IMMUTABLE** once set — enforced at application layer and schema CHECK.
- SQLite WAL mode enabled for concurrent read/write safety on desktop.

### 1.2 Table Group Map (57 Tables)

| Group | Tables | Module IDs |
|---|---|---|
| **A. Field Dictionary** | `field_master`, `field_dependency_map`, `null_policy_master`, `alias_master` | M-01, M-17, M-23, M-25 |
| **B. Modules Registry** | `module_registry`, `controlled_value_master` | M-11, M-39 |
| **C. Validation Rules** | `validation_rule_master`, `geometry_reconciliation_master`, `tolerance_master` | M-30, M-45, M-47 |
| **D. Source Mapping** | `source_priority_master`, `source_mapping_master`, `conflict_rule_master`, `traceability_path_master` | M-20, M-24, M-32 |
| **E. Fallback Policies** | `fallback_rule_master`, `source_fallback_chain` | M-22 |
| **F. Stage Gates** | `stage_gate_master`, `stage_gate_field_map`, `stage_cascade_rule` | M-33, M-34 |
| **G. Override & Approval** | `override_rule_master`, `override_event_log`, `approval_request`, `approval_decision` | M-28, M-31 |
| **H. Template Library** | `template_master`, `template_field_map`, `title_block_master`, `layout_rule_master` | M-04, M-15 |
| **I. Project Runtime** | `project_master`, `project_file_registry`, `intake_sheet_registry`, `project_stage_status`, `stage_checkpoint` | M-01, M-02, M-33 |
| **J. Field Population** | `field_value_store`, `field_population_event` | M-20, M-32 |
| **K. Validation Results** | `validation_result`, `manual_review_trigger_master`, `manual_review_event` | M-30, M-35 |
| **L. Geometry** | `bay_geometry_master`, `member_registry`, `connection_master`, `bolt_group_master`, `built_up_section_master`, `crane_data_master` | M-40, M-41, M-42, M-43 |
| **M. Output Classes** | `anchor_bolt_master`, `ga_master`, `sheeting_master`, `shop_drawing_master`, `shipping_bundle_master`, `installation_package_master` | M-16 output tables |
| **N. BOQ / Cross-Output** | `boq_check_master`, `cross_output_check_log` | M-44 |
| **O. Audit & Immutable Logs** | `audit_event_log`, `field_extraction_log`, `correction_event_log`, `rule_proposal_log` | M-31, M-32 |
| **P. Learning & Benchmarks** | `benchmark_project_log`, `benchmark_defect_log`, `rule_proposal_log` | M-03, M-36 |
| **Q. Material & Section DB** | `steel_section_master`, `material_grade_master`, `material_grade_mapping_master`, `bolt_spec_master` | M-51, M-52 |
| **R. Design Standards** | `design_standard_master`, `design_standard_field_map` | M-16 |
| **S. Sub-Registries** | `agent_registry`, `role_master`, `db_version_log` | M-31 |

---

## 2. TABLE-BY-TABLE DESIGN

### 2A — FIELD DICTIONARY GROUP

```sql
-- M-01: Master field registry — all 196 fields F-001 to F-196
CREATE TABLE field_master (
    field_id        TEXT PRIMARY KEY CHECK(field_id GLOB 'F-[0-9][0-9][0-9]'),
    field_name      TEXT NOT NULL UNIQUE,
    field_group     TEXT NOT NULL CHECK(field_group IN 
                    ('Governing','Derived','Presentation','Metadata',
                     'Control','Validation-Ref','Output-Only')),
    data_type       TEXT NOT NULL CHECK(data_type IN 
                    ('TEXT','INTEGER','REAL','BOOLEAN','DATE','JSON_LIST')),
    unit_type       TEXT,                        -- mm, kg, degree, ratio, etc.
    is_mandatory    INTEGER NOT NULL DEFAULT 0,  -- 1=mandatory, 0=optional
    is_override_prohibited INTEGER NOT NULL DEFAULT 0,  -- 28 hard-block fields
    is_immutable    INTEGER NOT NULL DEFAULT 0,  -- F-006 only = 1
    is_output_only  INTEGER NOT NULL DEFAULT 0,  -- 5 output-only fields
    output_classes  TEXT,                        -- comma-sep: AB,GA,Shop,Ship,Sheet,Install
    source_priority_required INTEGER,            -- max allowed source priority (1=P1 only)
    historical_fill_allowed  INTEGER NOT NULL DEFAULT 0,  -- 0=prohibited for governing
    null_policy_id  TEXT REFERENCES null_policy_master(policy_id),
    notes           TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- M-25: Dependency map for all 39 derived fields
CREATE TABLE field_dependency_map (
    dep_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    field_id        TEXT NOT NULL REFERENCES field_master(field_id),
    depends_on_field TEXT NOT NULL REFERENCES field_master(field_id),
    dependency_type TEXT NOT NULL CHECK(dependency_type IN 
                    ('required','conditional','formula_input')),
    condition_expr  TEXT,    -- e.g. "F-183='BuiltUp'" for conditional deps
    formula_expr    TEXT,    -- e.g. "F-070 * F-066 * F-069" for derived fields
    notes           TEXT
);
CREATE INDEX idx_field_dep_field ON field_dependency_map(field_id);

-- M-23: Null handling policy for every field
CREATE TABLE null_policy_master (
    policy_id               TEXT PRIMARY KEY,
    policy_name             TEXT NOT NULL,
    null_action             TEXT NOT NULL CHECK(null_action IN 
                            ('BLOCK','WARN','DEFAULT','UNRESOLVED','ACCEPT')),
    default_value_allowed   INTEGER NOT NULL DEFAULT 0,
    default_value           TEXT,    -- only populated when default_value_allowed=1
    notes                   TEXT
);

-- M-17: Alias resolution table for legacy field names
CREATE TABLE alias_master (
    alias_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    alias_text  TEXT NOT NULL UNIQUE,   -- e.g. "Col", "Rft", "fe500"
    canonical   TEXT NOT NULL,          -- resolved standard value
    alias_type  TEXT NOT NULL CHECK(alias_type IN 
                ('abbreviation','legacy_name','unit_variant','case_variant')),
    field_id    TEXT REFERENCES field_master(field_id)  -- NULL = global alias
);
```

### 2B — MODULE REGISTRY GROUP

```sql
-- M-11: Registry of all 54 active modules
CREATE TABLE module_registry (
    module_id       TEXT PRIMARY KEY CHECK(module_id GLOB 'M-[0-9]*'),
    module_name     TEXT NOT NULL,
    module_group    TEXT NOT NULL,   -- FieldDict, Rules, Source, etc.
    db_table_name   TEXT,            -- physical table name it maps to
    is_active       INTEGER NOT NULL DEFAULT 1,
    is_deferred     INTEGER NOT NULL DEFAULT 0,
    notes           TEXT
);

-- M-39: All controlled vocabularies CV-01 to CV-22
CREATE TABLE controlled_value_master (
    cv_id       TEXT NOT NULL CHECK(cv_id GLOB 'CV-[0-9][0-9]'),
    field_id    TEXT NOT NULL REFERENCES field_master(field_id),
    cv_value    TEXT NOT NULL,
    cv_label    TEXT,
    sort_order  INTEGER,
    design_standard TEXT,  -- NULL=all, or IS-Indian|AISC-US|BS-UK|Eurocode-EU
    is_active   INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (cv_id, cv_value)
);
CREATE INDEX idx_cv_field ON controlled_value_master(field_id);
```

### 2C — VALIDATION RULES GROUP

```sql
-- M-30: All 293 active validation rules (R-001 to R-271 + FB-RULE-001 to FB-RULE-022)
CREATE TABLE validation_rule_master (
    rule_id             TEXT PRIMARY KEY,   -- R-001, FB-RULE-001, etc.
    rule_name           TEXT NOT NULL,
    rule_type           TEXT NOT NULL CHECK(rule_type IN 
                        ('Validation','Cross-Field','Source Governance',
                         'Stage-Gate','Override','Fallback Policy')),
    sub_category        TEXT NOT NULL,      -- Completeness,DataType,Unit,Enumeration,etc.
    stage_applies_to    TEXT NOT NULL,      -- S1,S2,...,S10,All,S1-S10
    severity            TEXT NOT NULL CHECK(severity IN 
                        ('Release-Blocker','Error','Warning','Informational')),
    blocking_flag       INTEGER NOT NULL DEFAULT 0,  -- 1=blocks generation
    override_allowed    INTEGER NOT NULL DEFAULT 0,
    override_approval_req INTEGER NOT NULL DEFAULT 0,
    component_module    TEXT NOT NULL,      -- M-nn,M-nn references
    output_classes      TEXT NOT NULL,      -- AB,GA,Sheet,Shop,Ship,Install,All
    status              TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE','DEPRECATED')),
    condition_logic     TEXT,               -- pseudocode for the validation condition
    pass_condition      TEXT,
    fail_condition      TEXT,
    auto_fix_allowed    INTEGER NOT NULL DEFAULT 0,
    auto_fix_type       TEXT,               -- format-only, normalisation-only, sequence-only
    implementation_notes TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_vrm_stage ON validation_rule_master(stage_applies_to);
CREATE INDEX idx_vrm_type ON validation_rule_master(rule_type);
CREATE INDEX idx_vrm_severity ON validation_rule_master(severity);
CREATE INDEX idx_vrm_blocking ON validation_rule_master(blocking_flag);

-- M-45: Geometry reconciliation rules RC-001 to RC-022 (separate table per spec)
CREATE TABLE geometry_reconciliation_master (
    rc_rule_id      TEXT PRIMARY KEY CHECK(rc_rule_id GLOB 'RC-[0-9][0-9][0-9]'),
    check_name      TEXT NOT NULL,
    category        TEXT NOT NULL,      -- Grid System, Building Envelope, etc.
    db_field_ref    TEXT NOT NULL,      -- e.g. F-172 dir=X
    dxf_entity      TEXT NOT NULL,      -- DXF entity type to extract
    comparison_logic TEXT NOT NULL,     -- pseudocode comparison
    tolerance_id    TEXT NOT NULL REFERENCES tolerance_master(tolerance_id),
    severity        TEXT NOT NULL CHECK(severity IN ('Critical','Major','Minor')),
    blocking        INTEGER NOT NULL DEFAULT 1,
    stage_applies_to TEXT NOT NULL,
    output_classes  TEXT NOT NULL,
    conditional_on  TEXT,               -- e.g. F-060=CraneBay
    notes           TEXT
);

-- M-47: Tolerance master — 14 tolerance rules
CREATE TABLE tolerance_master (
    tolerance_id    TEXT PRIMARY KEY CHECK(tolerance_id GLOB 'TOL-[0-9][0-9][0-9]'),
    parameter_type  TEXT NOT NULL,
    value           REAL NOT NULL,
    unit            TEXT NOT NULL,       -- mm, %
    condition       TEXT NOT NULL,       -- absolute, percentage
    applies_to_rc   TEXT,               -- comma-sep RC rule IDs
    building_size_condition TEXT,
    notes           TEXT
);
```

### 2D — SOURCE MAPPING GROUP

```sql
-- M-20: Source priority hierarchy (P1–P8)
CREATE TABLE source_priority_master (
    priority_rank   INTEGER PRIMARY KEY CHECK(priority_rank BETWEEN 1 AND 8),
    priority_code   TEXT NOT NULL UNIQUE,   -- P1, P2, ... P8
    priority_name   TEXT NOT NULL,
    description     TEXT,
    allowed_for_governing INTEGER NOT NULL DEFAULT 0,   -- only P1, P2 allowed
    allowed_for_derived   INTEGER NOT NULL DEFAULT 0,
    is_historical   INTEGER NOT NULL DEFAULT 0           -- P8 only = 1
);

-- Source mapping rules per field (extracted from Phase 3 output)
CREATE TABLE source_mapping_master (
    mapping_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    field_id        TEXT NOT NULL REFERENCES field_master(field_id),
    source_parser   TEXT NOT NULL,          -- STAAD, MBS, ETABS, Prota, DXF, PDF, Manual
    priority_rank   INTEGER NOT NULL REFERENCES source_priority_master(priority_rank),
    extraction_method TEXT NOT NULL,        -- XPath, regex, table_lookup, manual, derived
    extraction_expr TEXT,                   -- specific expression/path
    confidence_baseline INTEGER,            -- baseline confidence 0–100
    design_standard TEXT,                   -- NULL=all standards or IS-Indian etc.
    is_active       INTEGER NOT NULL DEFAULT 1,
    notes           TEXT
);
CREATE INDEX idx_sm_field ON source_mapping_master(field_id);
CREATE INDEX idx_sm_parser ON source_mapping_master(source_parser);

-- M-24: Conflict resolution rules when multiple sources disagree
CREATE TABLE conflict_rule_master (
    conflict_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    field_id        TEXT NOT NULL REFERENCES field_master(field_id),
    source_a_rank   INTEGER NOT NULL,
    source_b_rank   INTEGER NOT NULL,
    resolution      TEXT NOT NULL CHECK(resolution IN 
                    ('HIGHER_PRIORITY_WINS','MANUAL_REVIEW','BLOCK')),
    condition       TEXT,    -- e.g. only when difference > 2%
    notes           TEXT
);

-- M-32: Traceability path master
CREATE TABLE traceability_path_master (
    trace_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    field_id        TEXT NOT NULL REFERENCES field_master(field_id),
    source_file_type TEXT NOT NULL,
    trace_path      TEXT NOT NULL,      -- document trail description
    documentation_ref TEXT,
    is_active       INTEGER NOT NULL DEFAULT 1
);
```

### 2E — FALLBACK POLICY GROUP

```sql
-- M-22: Fallback rules FB-RULE-001 to FB-RULE-022
CREATE TABLE fallback_rule_master (
    fallback_id     TEXT PRIMARY KEY,       -- FB-RULE-001 etc.
    rule_name       TEXT NOT NULL,
    field_group     TEXT NOT NULL,          -- Governing-Eng, Derived-Eng, Presentation, etc.
    fallback_type   TEXT NOT NULL CHECK(fallback_type IN
                    ('Prohibited Source','Dependency Chain','Fallback Chain',
                     'Mandatory Metadata','Workflow Control','Special Case')),
    prohibited_source TEXT,                 -- P7, P8, etc. if prohibited
    allowed_fallback_chain TEXT,            -- e.g. "P3 Template → P8 Historical → system_default"
    blocking_on_fail INTEGER NOT NULL DEFAULT 0,
    escalation_required INTEGER NOT NULL DEFAULT 0,
    error_flag_code TEXT,                   -- DERIVED_BROKEN, NULL_NO_DEFAULT, etc.
    stage_applies_to TEXT NOT NULL,
    output_classes  TEXT NOT NULL,
    implementation_notes TEXT
);

-- Explicit fallback chains per field (computed from fallback rules)
CREATE TABLE source_fallback_chain (
    chain_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    field_id        TEXT NOT NULL REFERENCES field_master(field_id),
    step_order      INTEGER NOT NULL,       -- 1=first try, 2=second try, etc.
    source_priority_rank INTEGER NOT NULL REFERENCES source_priority_master(priority_rank),
    is_blocked      INTEGER NOT NULL DEFAULT 0,  -- 1=this source is prohibited for this field
    block_reason    TEXT,
    on_fail_action  TEXT NOT NULL CHECK(on_fail_action IN
                    ('TRY_NEXT','WARN','BLOCK','UNRESOLVED','ESCALATE')),
    UNIQUE(field_id, step_order)
);
CREATE INDEX idx_sfc_field ON source_fallback_chain(field_id);
```

### 2F — STAGE GATE GROUP

```sql
-- M-33: 10 stage gates S1–S10
CREATE TABLE stage_gate_master (
    gate_id         TEXT PRIMARY KEY CHECK(gate_id IN
                    ('S1','S2','S3','S4','S5','S6','S7','S8','S9','S10')),
    gate_name       TEXT NOT NULL,
    gate_purpose    TEXT NOT NULL,
    is_hard_gate    INTEGER NOT NULL DEFAULT 0,  -- S4 and S5 = 1 (hard block all downstream)
    blocks_output_classes TEXT,  -- which output classes blocked until this gate passes
    multi_role_bypass_required INTEGER NOT NULL DEFAULT 0,  -- S4/S5 bypass needs PM+DE
    prerequisite_gates TEXT,     -- comma-sep: e.g. S4 before S5 can pass
    mandatory_rules TEXT         -- comma-sep rule IDs that must all PASS for gate to open
);

-- Maps which fields are checked at each gate
CREATE TABLE stage_gate_field_map (
    map_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    gate_id     TEXT NOT NULL REFERENCES stage_gate_master(gate_id),
    field_id    TEXT NOT NULL REFERENCES field_master(field_id),
    is_blocking INTEGER NOT NULL DEFAULT 1,  -- 1 = field null → gate fails
    UNIQUE(gate_id, field_id)
);
CREATE INDEX idx_sgfm_gate ON stage_gate_field_map(gate_id);

-- M-34: Cascade rules — what re-runs when upstream stage changes
CREATE TABLE stage_cascade_rule (
    cascade_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    trigger_gate    TEXT NOT NULL REFERENCES stage_gate_master(gate_id),
    cascades_to     TEXT NOT NULL,    -- comma-sep gate IDs that must re-run
    trigger_condition TEXT NOT NULL,  -- e.g. "AB change after S4"
    notes           TEXT
);
```

### 2G — OVERRIDE & APPROVAL GROUP

```sql
-- M-28: Override governance rules (72 rules R-200 to R-271)
CREATE TABLE override_rule_master (
    rule_id             TEXT PRIMARY KEY REFERENCES validation_rule_master(rule_id),
    field_id            TEXT NOT NULL REFERENCES field_master(field_id),
    override_status     TEXT NOT NULL CHECK(override_status IN
                        ('override-prohibited','override-not-applicable',
                         'override-allowed-with-review','override-allowed-with-approval',
                         'override-allowed-for-presentation-only',
                         'override-allowed-for-metadata-only',
                         'override-allowed-for-sequence-control-only')),
    required_role       TEXT,       -- drafter, checker, detailing_lead, design_engineer, pm
    multi_role_quorum   INTEGER NOT NULL DEFAULT 0,   -- 1 = requires simultaneous approval
    evidence_required   INTEGER NOT NULL DEFAULT 0,
    engineering_justification_required INTEGER NOT NULL DEFAULT 0,
    audit_mandatory     INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX idx_orm_field ON override_rule_master(field_id);
CREATE INDEX idx_orm_status ON override_rule_master(override_status);

-- Runtime override events (append-only audit)
CREATE TABLE override_event_log (
    event_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    project_uuid        TEXT NOT NULL REFERENCES project_master(project_uuid),
    field_id            TEXT NOT NULL REFERENCES field_master(field_id),
    rule_id             TEXT NOT NULL REFERENCES override_rule_master(rule_id),
    original_value      TEXT,
    overridden_value    TEXT NOT NULL,
    override_reason     TEXT NOT NULL,
    supporting_evidence TEXT,
    override_status     TEXT NOT NULL,   -- status of the override rule applied
    role_applied        TEXT NOT NULL,
    approved_by         TEXT,
    approval_timestamp  TEXT,
    event_timestamp     TEXT NOT NULL DEFAULT (datetime('now'))
    -- NO UPDATE, NO DELETE allowed
);
CREATE INDEX idx_oel_project ON override_event_log(project_uuid);
CREATE INDEX idx_oel_field ON override_event_log(field_id);

-- Approval request queue
CREATE TABLE approval_request (
    request_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    project_uuid    TEXT NOT NULL REFERENCES project_master(project_uuid),
    field_id        TEXT REFERENCES field_master(field_id),
    gate_id         TEXT REFERENCES stage_gate_master(gate_id),
    request_type    TEXT NOT NULL CHECK(request_type IN
                    ('override','gate_bypass','rule_change','release')),
    requested_by    TEXT NOT NULL,
    requested_at    TEXT NOT NULL DEFAULT (datetime('now')),
    required_roles  TEXT NOT NULL,      -- comma-sep roles that must approve
    status          TEXT NOT NULL DEFAULT 'PENDING' CHECK(status IN
                    ('PENDING','APPROVED','REJECTED','EXPIRED')),
    context_json    TEXT                -- JSON snapshot of relevant values
);
CREATE INDEX idx_ar_project ON approval_request(project_uuid);
CREATE INDEX idx_ar_status ON approval_request(status);

-- Approval decisions (one row per approver per request)
CREATE TABLE approval_decision (
    decision_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id      INTEGER NOT NULL REFERENCES approval_request(request_id),
    role_name       TEXT NOT NULL,
    decided_by      TEXT NOT NULL,
    decision        TEXT NOT NULL CHECK(decision IN ('APPROVED','REJECTED')),
    decision_notes  TEXT,
    decided_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
```

### 2H — TEMPLATE LIBRARY GROUP

```sql
-- M-04: Template families
CREATE TABLE template_master (
    template_id         TEXT PRIMARY KEY,   -- e.g. TPL-GA-001
    template_family     TEXT NOT NULL,
    drawing_class       TEXT NOT NULL,      -- GA, AB, ASM, DET, Shipping, Installation
    output_class        TEXT NOT NULL,
    sheet_size          TEXT NOT NULL,      -- A0,A1,A2,A3
    confidence_threshold REAL NOT NULL DEFAULT 60.0,  -- minimum for auto-select
    source              TEXT NOT NULL CHECK(source IN ('reference_job','standard','custom')),
    is_active           INTEGER NOT NULL DEFAULT 1,
    notes               TEXT
);

-- M-15: Maps which fields take values from template vs live extraction
CREATE TABLE template_field_map (
    map_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id     TEXT NOT NULL REFERENCES template_master(template_id),
    field_id        TEXT NOT NULL REFERENCES field_master(field_id),
    default_value   TEXT,
    is_overridable  INTEGER NOT NULL DEFAULT 1,  -- presentation fields always overridable
    UNIQUE(template_id, field_id)
);

-- Title block variants per template
CREATE TABLE title_block_master (
    title_block_id  TEXT PRIMARY KEY,
    template_id     TEXT NOT NULL REFERENCES template_master(template_id),
    field_layout    TEXT NOT NULL    -- JSON describing field positions
);

-- Layout rules for drawing generation
CREATE TABLE layout_rule_master (
    layout_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id     TEXT NOT NULL REFERENCES template_master(template_id),
    rule_type       TEXT NOT NULL,   -- view_placement, dimension_style, north_arrow, etc.
    rule_value      TEXT NOT NULL,
    notes           TEXT
);
```

### 2I — PROJECT RUNTIME GROUP

```sql
-- Core project table
CREATE TABLE project_master (
    project_uuid    TEXT PRIMARY KEY,           -- system-generated UUID, immutable PK
    proposal_id     TEXT NOT NULL,              -- e.g. Q-157
    project_location TEXT NOT NULL,             -- e.g. Palghar
    display_id      TEXT GENERATED ALWAYS AS (proposal_id || '-' || project_location) STORED,
    project_name    TEXT,
    client_code     TEXT,
    unit_system     TEXT NOT NULL CHECK(unit_system IN ('metric','imperial')),  -- IMMUTABLE
    design_standard TEXT NOT NULL CHECK(design_standard IN
                    ('IS-Indian','AISC-US','BS-UK','Eurocode-EU')),
    building_type   TEXT,
    project_status  TEXT NOT NULL DEFAULT 'INTAKE' CHECK(project_status IN
                    ('INTAKE','PROCESSING','REVIEW','APPROVED','REJECTED')),
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    last_updated    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX idx_pm_display ON project_master(display_id);

-- All uploaded files per project
CREATE TABLE project_file_registry (
    file_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    project_uuid    TEXT NOT NULL REFERENCES project_master(project_uuid),
    filename        TEXT NOT NULL,
    file_type       TEXT NOT NULL CHECK(file_type IN
                    ('STAAD','MBS','ETABS','Prota','DWG','DXF','PDF_Text','PDF_Image','ZIP','RAR','Other')),
    file_path       TEXT NOT NULL,   -- path within project Raw_Inputs/
    revision        TEXT,
    is_governing    INTEGER NOT NULL DEFAULT 0,  -- 1=selected as governing design file
    parser_priority INTEGER,          -- parser priority rank 1–8
    upload_timestamp TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_pfr_project ON project_file_registry(project_uuid);

-- Sheet-level intake registry (M-02)
CREATE TABLE intake_sheet_registry (
    sheet_reg_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    project_uuid    TEXT NOT NULL REFERENCES project_master(project_uuid),
    file_id         INTEGER NOT NULL REFERENCES project_file_registry(file_id),
    sheet_code      TEXT NOT NULL,   -- e.g. GA-01
    drawing_class   TEXT NOT NULL,
    drawing_title   TEXT,
    revision_code   TEXT,
    is_superseded   INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_isr_project ON intake_sheet_registry(project_uuid);

-- Gate status tracker per project
CREATE TABLE project_stage_status (
    status_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    project_uuid    TEXT NOT NULL REFERENCES project_master(project_uuid),
    gate_id         TEXT NOT NULL REFERENCES stage_gate_master(gate_id),
    gate_status     TEXT NOT NULL CHECK(gate_status IN
                    ('NOT_STARTED','RUNNING','PASS','PASS_WITH_WARNINGS',
                     'FAIL','BLOCKED','ESCALATE_ENGINEERING','ESCALATE_IT',
                     'RE_RUN_REQUIRED','REJECTED')),
    started_at      TEXT,
    completed_at    TEXT,
    agent_id        TEXT REFERENCES agent_registry(agent_id),
    warning_count   INTEGER NOT NULL DEFAULT 0,
    blocker_count   INTEGER NOT NULL DEFAULT 0,
    notes           TEXT,
    UNIQUE(project_uuid, gate_id)
);
CREATE INDEX idx_pss_project ON project_stage_status(project_uuid);

-- Checkpoint snapshots for rollback
CREATE TABLE stage_checkpoint (
    checkpoint_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    project_uuid    TEXT NOT NULL REFERENCES project_master(project_uuid),
    gate_id         TEXT NOT NULL REFERENCES stage_gate_master(gate_id),
    state_snapshot  TEXT NOT NULL,  -- JSON of all field values at checkpoint time
    checkpoint_at   TEXT NOT NULL DEFAULT (datetime('now')),
    rollback_available INTEGER NOT NULL DEFAULT 1
);
```

### 2J — FIELD POPULATION GROUP

```sql
-- All field values extracted/populated per project (one row per field per project)
CREATE TABLE field_value_store (
    value_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    project_uuid    TEXT NOT NULL REFERENCES project_master(project_uuid),
    field_id        TEXT NOT NULL REFERENCES field_master(field_id),
    value_text      TEXT,            -- raw stored value as TEXT (engine casts)
    value_status    TEXT NOT NULL CHECK(value_status IN
                    ('POPULATED','UNRESOLVED','DERIVED','MANUAL','OVERRIDE',
                     'DERIVED_BROKEN','PENDING_REVIEW')),
    source_priority_rank INTEGER REFERENCES source_priority_master(priority_rank),
    source_file_id  INTEGER REFERENCES project_file_registry(file_id),
    confidence_score INTEGER CHECK(confidence_score BETWEEN 0 AND 100),
    extraction_method TEXT,
    is_historical_source INTEGER NOT NULL DEFAULT 0,  -- must be 0 for governing fields
    last_updated    TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(project_uuid, field_id)
);
CREATE INDEX idx_fvs_project ON field_value_store(project_uuid);
CREATE INDEX idx_fvs_status ON field_value_store(value_status);

-- Immutable log of every population event (audit trail)
CREATE TABLE field_population_event (
    event_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    project_uuid    TEXT NOT NULL REFERENCES project_master(project_uuid),
    field_id        TEXT NOT NULL REFERENCES field_master(field_id),
    value_populated TEXT,
    source_priority_rank INTEGER,
    source_file_id  INTEGER REFERENCES project_file_registry(file_id),
    source_path     TEXT,           -- specific location in source file
    extraction_method TEXT,
    transformation_applied TEXT,    -- normalisation, alias, unit conversion
    confidence_score INTEGER,
    agent_id        TEXT REFERENCES agent_registry(agent_id),
    event_timestamp TEXT NOT NULL DEFAULT (datetime('now'))
    -- IMMUTABLE: no UPDATE or DELETE
);
CREATE INDEX idx_fpe_project ON field_population_event(project_uuid, field_id);
```

### 2K — VALIDATION RESULTS GROUP

```sql
-- All validation results per project per rule
CREATE TABLE validation_result (
    result_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    project_uuid    TEXT NOT NULL REFERENCES project_master(project_uuid),
    rule_id         TEXT NOT NULL REFERENCES validation_rule_master(rule_id),
    gate_id         TEXT NOT NULL REFERENCES stage_gate_master(gate_id),
    field_id        TEXT REFERENCES field_master(field_id),
    result_status   TEXT NOT NULL CHECK(result_status IN
                    ('PASS','FAIL','WARNING','INFORMATIONAL','SKIPPED')),
    actual_value    TEXT,
    expected_value  TEXT,
    severity        TEXT NOT NULL,
    generation_blocked INTEGER NOT NULL DEFAULT 0,
    manual_review_required INTEGER NOT NULL DEFAULT 0,
    remediation_taken TEXT,
    validated_at    TEXT NOT NULL DEFAULT (datetime('now')),
    agent_id        TEXT REFERENCES agent_registry(agent_id)
);
CREATE INDEX idx_vr_project ON validation_result(project_uuid);
CREATE INDEX idx_vr_status ON validation_result(result_status, generation_blocked);

-- M-30: 25 manual review trigger definitions T-001 to T-025 (M-30 + M-58 merged)
CREATE TABLE manual_review_trigger_master (
    trigger_id      TEXT PRIMARY KEY CHECK(trigger_id GLOB 'T-[0-9][0-9][0-9]'),
    trigger_name    TEXT NOT NULL,
    trigger_condition TEXT NOT NULL,
    severity        TEXT NOT NULL,
    required_action TEXT NOT NULL,
    escalation_type TEXT CHECK(escalation_type IN ('ENGINEERING','IT','DRAFTING','NONE'))
);

-- Runtime manual review events
CREATE TABLE manual_review_event (
    review_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    project_uuid    TEXT NOT NULL REFERENCES project_master(project_uuid),
    trigger_id      TEXT NOT NULL REFERENCES manual_review_trigger_master(trigger_id),
    rule_id         TEXT REFERENCES validation_rule_master(rule_id),
    field_id        TEXT REFERENCES field_master(field_id),
    description     TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'OPEN' CHECK(status IN
                    ('OPEN','RESOLVED','ESCALATED','REJECTED')),
    resolution_notes TEXT,
    resolved_by     TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    resolved_at     TEXT
);
CREATE INDEX idx_mre_project ON manual_review_event(project_uuid, status);
```

### 2L — GEOMETRY TABLES GROUP

```sql
-- M-41: Bay geometry per project (per direction, per bay)
CREATE TABLE bay_geometry_master (
    bay_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_uuid    TEXT NOT NULL REFERENCES project_master(project_uuid),
    direction       TEXT NOT NULL CHECK(direction IN ('X','Y')),
    bay_sequence    INTEGER NOT NULL,
    bay_label       TEXT,
    bay_dimension   REAL NOT NULL,        -- mm
    bay_type_code   TEXT CHECK(bay_type_code IN
                    ('Standard','CraneBay','ExpansionJoint','EndBay')),
    cumulative_dim  REAL,                  -- running total from origin
    UNIQUE(project_uuid, direction, bay_sequence)
);
CREATE INDEX idx_bgm_project ON bay_geometry_master(project_uuid);

-- Member registry per project
CREATE TABLE member_registry (
    member_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    project_uuid    TEXT NOT NULL REFERENCES project_master(project_uuid),
    member_mark     TEXT NOT NULL,        -- F-067
    member_type     TEXT NOT NULL,        -- F-064
    member_section_size TEXT NOT NULL,    -- F-063
    material_grade  TEXT NOT NULL,        -- F-065
    member_length   REAL,                 -- F-066, mm
    member_quantity INTEGER,              -- F-069
    grid_location   TEXT,                 -- grid intersection reference
    weight_per_m    REAL,                 -- F-070 kg/m
    total_weight    REAL,                 -- F-071 kg
    surface_treatment TEXT,              -- F-073
    section_type    TEXT CHECK(section_type IN ('RolledStandard','BuiltUp')),
    UNIQUE(project_uuid, member_mark)
);
CREATE INDEX idx_mr_project ON member_registry(project_uuid);

-- M-40: Connection records
CREATE TABLE connection_master (
    conn_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    project_uuid    TEXT NOT NULL REFERENCES project_master(project_uuid),
    member_id       INTEGER NOT NULL REFERENCES member_registry(member_id),
    connection_type TEXT NOT NULL,        -- F-075
    bolt_size       TEXT,                 -- F-076
    bolt_grade      TEXT,                 -- F-077
    bolt_qty        INTEGER,              -- F-078
    weld_size       REAL,                 -- F-079
    weld_type       TEXT,                 -- F-165
    conn_source_type TEXT,               -- F-170
    edge_distance   REAL,                 -- F-163 mm
    end_distance    REAL,                 -- F-162 mm
    bolt_pitch      REAL,                 -- F-164 mm
    plate_thickness REAL,                 -- F-157 mm
    stiffener_req   TEXT,                 -- F-167
    eccentricity    REAL                  -- F-169 mm
);
CREATE INDEX idx_cm_project ON connection_master(project_uuid);

-- M-43: Built-up section details
CREATE TABLE built_up_section_master (
    bu_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    project_uuid    TEXT NOT NULL REFERENCES project_master(project_uuid),
    member_id       INTEGER NOT NULL UNIQUE REFERENCES member_registry(member_id),
    top_flange_width REAL NOT NULL,       -- F-184
    top_flange_thickness REAL NOT NULL,  -- F-185
    web_height      REAL NOT NULL,        -- F-186
    web_thickness   REAL NOT NULL,        -- F-187
    bot_flange_width REAL NOT NULL,       -- F-188
    bot_flange_thickness REAL NOT NULL,  -- F-189
    weight_per_m    REAL,                 -- F-190 calculated
    total_depth     REAL GENERATED ALWAYS AS (top_flange_thickness + web_height + bot_flange_thickness) STORED
);

-- M-42: Crane data when frame_type = CraneBay
CREATE TABLE crane_data_master (
    crane_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    project_uuid    TEXT NOT NULL REFERENCES project_master(project_uuid),
    crane_type      TEXT NOT NULL,        -- F-125
    crane_capacity  REAL NOT NULL,        -- F-126 tonnes
    crane_span      REAL,                 -- F-127
    crane_rail_level REAL NOT NULL,       -- F-128 mm
    min_clearance   REAL,                 -- F-182 mm (≥200mm IS807)
    rail_section    TEXT,                 -- F-177
    end_stop_type   TEXT,                 -- F-180
    bracket_plate_size TEXT               -- F-178
);
```

### 2M — OUTPUT CLASS TABLES

```sql
-- Anchor Bolt master per project
CREATE TABLE anchor_bolt_master (
    ab_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    project_uuid    TEXT NOT NULL REFERENCES project_master(project_uuid),
    anchor_bolt_code TEXT NOT NULL,       -- F-089
    column_ref      TEXT NOT NULL,
    bolt_diameter   REAL NOT NULL,        -- F-081 mm
    bolt_grade      TEXT NOT NULL,        -- F-082
    bolt_qty_per_col INTEGER NOT NULL,    -- F-083
    bolt_spacing_x  REAL NOT NULL,        -- F-084 mm
    bolt_spacing_y  REAL NOT NULL,        -- F-085 mm
    embedment_depth REAL NOT NULL,        -- F-086 mm
    projection_above_ffl REAL NOT NULL,   -- F-087/F-192 mm
    grout_pad_thickness REAL NOT NULL,    -- F-193 mm
    pattern_orientation TEXT NOT NULL,   -- F-088
    column_base_axis TEXT,                -- F-194
    base_plate_size TEXT NOT NULL,        -- F-080
    base_plate_thickness REAL NOT NULL,  -- F-090 mm
    UNIQUE(project_uuid, anchor_bolt_code)
);

-- Shipping bundles
CREATE TABLE shipping_bundle_master (
    bundle_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    project_uuid    TEXT NOT NULL REFERENCES project_master(project_uuid),
    bundle_code     TEXT NOT NULL,        -- F-108
    bundle_members  TEXT NOT NULL,        -- JSON array of member_marks
    bundle_sequence INTEGER NOT NULL,    -- F-111
    bundle_weight   REAL,                 -- F-110 kg
    destination     TEXT,                 -- F-112
    dispatch_date   TEXT,                 -- F-113
    UNIQUE(project_uuid, bundle_code)
);

-- Installation packages
CREATE TABLE installation_package_master (
    install_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    project_uuid    TEXT NOT NULL REFERENCES project_master(project_uuid),
    package_code    TEXT NOT NULL,        -- F-114
    assembly_codes  TEXT NOT NULL,        -- JSON array
    sequence_num    INTEGER NOT NULL,    -- F-115
    crane_req       TEXT,                 -- F-116
    assembly_weight REAL,                 -- F-117
    setup_time_est  REAL,                 -- F-118 hours
    temp_bracing    TEXT,                 -- F-119
    install_notes   TEXT,                 -- F-120
    UNIQUE(project_uuid, package_code)
);
```

### 2N — BOQ / CROSS-OUTPUT CHECK

```sql
-- M-44: Cross-output checks (GA vs Shop, Ship vs Shop, Install vs Shop)
CREATE TABLE boq_check_master (
    check_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    project_uuid    TEXT NOT NULL REFERENCES project_master(project_uuid),
    check_type      TEXT NOT NULL CHECK(check_type IN
                    ('GA_MARK_vs_SHOP','SHIP_QTY_vs_SHOP','BOQ_TOTAL_WEIGHT',
                     'INSTALL_REF_vs_SHOP','AB_GRID_vs_GA_GRID')),
    rule_id         TEXT NOT NULL REFERENCES validation_rule_master(rule_id),
    result          TEXT NOT NULL CHECK(result IN ('PASS','FAIL','WARN')),
    delta_value     REAL,     -- measured variance
    tolerance_used  REAL,
    detail_json     TEXT,     -- JSON with specific mismatch detail
    checked_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_bcm_project ON boq_check_master(project_uuid);

CREATE TABLE cross_output_check_log (
    log_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_uuid    TEXT NOT NULL REFERENCES project_master(project_uuid),
    source_output   TEXT NOT NULL,
    target_output   TEXT NOT NULL,
    field_id        TEXT REFERENCES field_master(field_id),
    source_value    TEXT,
    target_value    TEXT,
    match_result    TEXT NOT NULL CHECK(match_result IN ('MATCH','MISMATCH','NOT_CHECKED')),
    logged_at       TEXT NOT NULL DEFAULT (datetime('now'))
);
```

### 2O — AUDIT & IMMUTABLE LOGS GROUP

```sql
-- Master audit event log — append only, NEVER update/delete
CREATE TABLE audit_event_log (
    audit_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    project_uuid    TEXT REFERENCES project_master(project_uuid),
    event_type      TEXT NOT NULL CHECK(event_type IN
                    ('FIELD_POPULATED','VALIDATION_RESULT','GATE_STATUS_CHANGE',
                     'OVERRIDE_APPLIED','APPROVAL_GRANTED','APPROVAL_REJECTED',
                     'ESCALATION_RAISED','CORRECTION_APPLIED','RULE_PROPOSAL',
                     'RELEASE_DECISION','AGENT_ACTION','SYSTEM_EVENT')),
    field_id        TEXT REFERENCES field_master(field_id),
    rule_id         TEXT REFERENCES validation_rule_master(rule_id),
    gate_id         TEXT REFERENCES stage_gate_master(gate_id),
    agent_id        TEXT REFERENCES agent_registry(agent_id),
    user_id         TEXT,
    event_detail    TEXT NOT NULL,  -- human-readable event description
    data_snapshot   TEXT,           -- JSON of relevant values at time of event
    source_file_ref TEXT,
    event_timestamp TEXT NOT NULL DEFAULT (datetime('now'))
    -- IMMUTABLE: application layer enforces no UPDATE/DELETE
);
CREATE INDEX idx_ael_project ON audit_event_log(project_uuid, event_timestamp);
CREATE INDEX idx_ael_type ON audit_event_log(event_type);

-- Field-level extraction log (immutable)
CREATE TABLE field_extraction_log (
    log_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_uuid    TEXT NOT NULL REFERENCES project_master(project_uuid),
    field_id        TEXT NOT NULL REFERENCES field_master(field_id),
    source_file_id  INTEGER REFERENCES project_file_registry(file_id),
    raw_extracted   TEXT,       -- raw string before normalisation
    normalised_to   TEXT,       -- after transformation
    confidence_score INTEGER,
    extraction_method TEXT,
    extraction_tool TEXT,       -- parser name/version
    logged_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Correction events (when fallback/escalation triggers correction)
CREATE TABLE correction_event_log (
    event_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    project_uuid    TEXT NOT NULL REFERENCES project_master(project_uuid),
    gate_id         TEXT NOT NULL REFERENCES stage_gate_master(gate_id),
    field_id        TEXT NOT NULL REFERENCES field_master(field_id),
    original_value  TEXT,
    corrected_value TEXT NOT NULL,
    correction_source TEXT NOT NULL,  -- manual_input, re_extraction, fallback
    corrected_by    TEXT,
    corrected_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Rule proposal log (Level 1 learning proposals)
CREATE TABLE rule_proposal_log (
    proposal_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    field_id        TEXT NOT NULL REFERENCES field_master(field_id),
    rule_id         TEXT REFERENCES validation_rule_master(rule_id),
    proposal_type   TEXT NOT NULL CHECK(proposal_type IN
                    ('RULE_UPDATE','NEW_RULE','THRESHOLD_CHANGE')),
    current_rule_text TEXT,
    proposed_rule_text TEXT NOT NULL,
    trigger_count   INTEGER NOT NULL,   -- number of correction events that triggered this
    proposed_at     TEXT NOT NULL DEFAULT (datetime('now')),
    status          TEXT NOT NULL DEFAULT 'PENDING' CHECK(status IN
                    ('PENDING','APPROVED','REJECTED','ARCHIVED')),
    reviewed_by     TEXT,
    reviewed_at     TEXT,
    review_notes    TEXT
);
```

### 2P — LEARNING & BENCHMARK GROUP

```sql
-- Benchmark project reference log
CREATE TABLE benchmark_project_log (
    bench_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    project_uuid    TEXT NOT NULL REFERENCES project_master(project_uuid),
    is_reference_job INTEGER NOT NULL DEFAULT 0,  -- 1 = one of 50 reference jobs
    job_type        TEXT,
    accuracy_overall REAL,           -- 0–100%
    accuracy_ab     REAL,
    accuracy_ga     REAL,
    accuracy_shop   REAL,
    defect_count    INTEGER DEFAULT 0,
    learning_eligible INTEGER NOT NULL DEFAULT 0,  -- 1 = can be used for Level 2/3 learning
    finalised_at    TEXT
);

-- Defect log per project
CREATE TABLE benchmark_defect_log (
    defect_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    project_uuid    TEXT NOT NULL REFERENCES project_master(project_uuid),
    gate_id         TEXT REFERENCES stage_gate_master(gate_id),
    field_id        TEXT REFERENCES field_master(field_id),
    defect_type     TEXT NOT NULL,      -- EXTRACTION_ERROR, RULE_FAIL, MISSING_VALUE, etc.
    severity        TEXT NOT NULL,
    description     TEXT NOT NULL,
    resolution      TEXT,
    logged_at       TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_bdl_project ON benchmark_defect_log(project_uuid);
```

### 2Q — MATERIAL & SECTION DB GROUP

```sql
-- Steel section database (IS, AISC, BS, Eurocode)
CREATE TABLE steel_section_master (
    section_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    section_name    TEXT NOT NULL,           -- e.g. W12X40, 200UB25.4
    design_standard TEXT NOT NULL,
    section_type    TEXT NOT NULL CHECK(section_type IN ('I','H','C','L','T','RHS','CHS','Other')),
    depth_mm        REAL,
    flange_width_mm REAL,
    web_thickness_mm REAL,
    flange_thickness_mm REAL,
    weight_per_m_kg REAL NOT NULL,
    area_cm2        REAL,
    is_active       INTEGER NOT NULL DEFAULT 1,
    UNIQUE(section_name, design_standard)
);
CREATE INDEX idx_ssm_std ON steel_section_master(design_standard);

-- M-52: Material grade mapping across standards
CREATE TABLE material_grade_master (
    grade_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    grade_code      TEXT NOT NULL,
    design_standard TEXT NOT NULL,
    yield_strength  REAL,    -- MPa
    tensile_strength REAL,   -- MPa
    is_rebar        INTEGER NOT NULL DEFAULT 0,  -- Fe500/Fe550 are rebar — blocked for structural
    is_active       INTEGER NOT NULL DEFAULT 1,
    UNIQUE(grade_code, design_standard)
);

CREATE TABLE material_grade_mapping_master (
    mapping_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    grade_code_is   TEXT,
    grade_code_aisc TEXT,
    grade_code_bs   TEXT,
    grade_code_eu   TEXT,
    grade_category  TEXT,    -- structural, high_strength, etc.
    notes           TEXT
);

-- Bolt specifications per design standard
CREATE TABLE bolt_spec_master (
    spec_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    bolt_application TEXT NOT NULL CHECK(bolt_application IN ('Anchor','Connection_HSFG','Connection_Standard')),
    design_standard TEXT NOT NULL,
    diameter_mm     REAL NOT NULL,
    grade           TEXT NOT NULL,
    is_active       INTEGER NOT NULL DEFAULT 1,
    UNIQUE(bolt_application, design_standard, diameter_mm, grade)
);
```

### 2R — DESIGN STANDARDS GROUP

```sql
CREATE TABLE design_standard_master (
    std_code        TEXT PRIMARY KEY CHECK(std_code IN ('IS-Indian','AISC-US','BS-UK','Eurocode-EU')),
    std_name        TEXT NOT NULL,
    region          TEXT NOT NULL,
    unit_preference TEXT NOT NULL CHECK(unit_preference IN ('metric','imperial'))
);

-- Which fields have standard-specific validation logic
CREATE TABLE design_standard_field_map (
    map_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    std_code        TEXT NOT NULL REFERENCES design_standard_master(std_code),
    field_id        TEXT NOT NULL REFERENCES field_master(field_id),
    validation_ref  TEXT,    -- e.g. IS 800 Cl.10.2.2
    lookup_table    TEXT,    -- reference table name
    notes           TEXT,
    UNIQUE(std_code, field_id)
);
```

### 2S — SUB-REGISTRY TABLES

```sql
-- Agent registry
CREATE TABLE agent_registry (
    agent_id        TEXT PRIMARY KEY,    -- e.g. P2-01-INGESTION, P2-03-AB-VALIDATOR
    agent_name      TEXT NOT NULL,
    pipeline_stage  TEXT NOT NULL,
    version         TEXT NOT NULL DEFAULT '1.0',
    is_active       INTEGER NOT NULL DEFAULT 1
);

-- Role master
CREATE TABLE role_master (
    role_id         TEXT PRIMARY KEY,    -- drafter, checker, detailing_lead, design_engineer, pm, document_controller
    role_name       TEXT NOT NULL,
    can_approve_override INTEGER NOT NULL DEFAULT 0,
    can_approve_gate_bypass INTEGER NOT NULL DEFAULT 0,
    can_release     INTEGER NOT NULL DEFAULT 0
);

-- DB version/migration log
CREATE TABLE db_version_log (
    version_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    schema_version  TEXT NOT NULL,
    migration_script TEXT,
    applied_at      TEXT NOT NULL DEFAULT (datetime('now')),
    applied_by      TEXT,
    notes           TEXT
);
```

---

## 3. INDEX STRATEGY

### Primary Indexes (Defined Above In-Line)

All foreign key columns and high-query columns have explicit indexes. Summary of critical indexes:

| Index Name | Table | Columns | Rationale |
|---|---|---|---|
| `idx_fvs_project` | `field_value_store` | `project_uuid` | Every field lookup is project-scoped |
| `idx_fvs_status` | `field_value_store` | `value_status` | Fast filter for UNRESOLVED fields |
| `idx_vr_project` | `validation_result` | `project_uuid` | Gate evaluation queries |
| `idx_vr_status` | `validation_result` | `result_status, generation_blocked` | Block detection |
| `idx_ael_project` | `audit_event_log` | `project_uuid, event_timestamp` | Audit trail retrieval |
| `idx_vrm_stage` | `validation_rule_master` | `stage_applies_to` | Stage-scoped rule loading |
| `idx_vrm_blocking` | `validation_rule_master` | `blocking_flag` | Fast blocker identification |
| `idx_ar_status` | `approval_request` | `status` | Pending approval queue |
| `idx_bgm_project` | `bay_geometry_master` | `project_uuid` | Geometry lookups |
| `idx_mr_project` | `member_registry` | `project_uuid` | Member cross-checks |

### Index Policy
- All `project_uuid` FK columns: **indexed**.
- All `status` and `gate_status` columns: **indexed**.
- All `field_id` FK columns in frequently-joined tables: **indexed**.
- Audit tables: `project_uuid + event_timestamp` composite index.
- Append-only audit tables: no additional non-primary indexes (inserts must be fast).

---

## 4. AUDIT AND IMMUTABILITY DESIGN

### 4.1 Immutable Tables (Application-Layer Enforcement)
The following tables are **append-only**. No UPDATE or DELETE operations are permitted from any application code path:

| Table | Reason |
|---|---|
| `audit_event_log` | Complete tamper-proof event history |
| `field_population_event` | Source traceability — every field extraction logged permanently |
| `field_extraction_log` | Raw extraction evidence |
| `override_event_log` | Override audit — required for compliance |
| `correction_event_log` | Correction history |
| `approval_decision` | Approval chain evidence |

**Enforcement**: Application-layer ORM/access class raises exception on UPDATE/DELETE to these tables. A SQLite trigger is also applied:

```sql
-- Example: Enforce immutability on audit_event_log
CREATE TRIGGER audit_no_update BEFORE UPDATE ON audit_event_log
BEGIN
    SELECT RAISE(ABORT, 'audit_event_log is immutable — no updates allowed');
END;

CREATE TRIGGER audit_no_delete BEFORE DELETE ON audit_event_log
BEGIN
    SELECT RAISE(ABORT, 'audit_event_log is immutable — no deletes allowed');
END;
```

*Apply the same trigger pattern to all 6 immutable tables listed above.*

### 4.2 Immutability of project_unit_system
```sql
-- F-006 immutability: prevent unit_system change after project creation
CREATE TRIGGER unit_system_immutable BEFORE UPDATE OF unit_system ON project_master
BEGIN
    SELECT RAISE(ABORT, 'project_unit_system (F-006) is IMMUTABLE — cannot be changed after project creation');
END;
```

### 4.3 Audit Mandatory Attributes
Every row in `audit_event_log` must carry all 10 mandatory attributes specified in Architecture v1.0:
1. Field code (`field_id`)
2. Value (`event_detail`)
3. Source system (`source_file_ref`)
4. Source priority (in `data_snapshot` JSON)
5. Extraction method (in `data_snapshot` JSON)
6. Transformation rules applied (in `data_snapshot` JSON)
7. Validation result (`event_type`)
8. Population timestamp (`event_timestamp`)
9. User/system (`user_id` / `agent_id`)
10. Traceability path (in `data_snapshot` JSON)

Application validates all 10 attributes before INSERT into `audit_event_log`. Missing attributes → INSERT rejected with R-193 violation.

---

## 5. SEED DATA STRATEGY

### 5.1 Load Order (Dependency-Ordered)

```
LOAD ORDER:
01. design_standard_master        — 4 rows (IS, AISC, BS, Eurocode)
02. role_master                   — ~7 rows (drafter, checker, DL, DE, PM, DC, QC_lead)
03. agent_registry                — ~15 rows (all pipeline agents P1-01 to P3-05)
04. null_policy_master            — ~8 rows (BLOCK, WARN, DEFAULT, UNRESOLVED, etc.)
05. field_master                  — 196 rows (F-001 to F-196)
06. field_dependency_map          — 39 derived field dependency rows
07. alias_master                  — ~50 rows (abbreviations, unit variants)
08. source_priority_master        — 8 rows (P1–P8)
09. controlled_value_master       — ~200 rows (CV-01 to CV-22, all enum values)
10. validation_rule_master        — 293 rows (R-001 to R-271 + FB-RULE-001 to FB-RULE-022)
11. tolerance_master              — 14 rows (TOL-001 to TOL-014)
12. geometry_reconciliation_master — 22 rows (RC-001 to RC-022)
13. module_registry               — 57 rows (all active modules)
14. source_priority_master        — already loaded (step 08)
15. fallback_rule_master          — 22 rows (FB-RULE-001 to FB-RULE-022)
16. stage_gate_master             — 10 rows (S1–S10)
17. override_rule_master          — 72 rows (R-200 to R-271)
18. manual_review_trigger_master  — 25 rows (T-001 to T-025)
19. stage_cascade_rule            — cascade relationships
20. steel_section_master          — bulk section data per design standard
21. material_grade_master         — grade data per standard
22. material_grade_mapping_master — 8 cross-standard mapping rows
23. bolt_spec_master              — bolt spec data
24. template_master               — template families from 50 reference jobs
25. design_standard_field_map     — standard-specific field validation refs
26. db_version_log                — schema version v1.0 seed entry
```

### 5.2 Seed Data Validation
After seed load, run count assertions:
```sql
SELECT COUNT(*) FROM field_master;              -- Must = 196
SELECT COUNT(*) FROM validation_rule_master;    -- Must = 293
SELECT COUNT(*) FROM geometry_reconciliation_master; -- Must = 22
SELECT COUNT(*) FROM stage_gate_master;         -- Must = 10
SELECT COUNT(*) FROM override_rule_master;      -- Must = 72
SELECT COUNT(*) FROM manual_review_trigger_master; -- Must = 25
SELECT COUNT(*) FROM tolerance_master;          -- Must = 14
SELECT COUNT(*) FROM fallback_rule_master;      -- Must = 22
SELECT COUNT(*) FROM controlled_value_master WHERE cv_id IS NOT NULL; -- Must = 22 CV groups
```

### 5.3 Seed Files
Seed data stored as versioned `.sql` or `.csv` files in `/seed_data/` folder:
- `seed_01_standards.sql`
- `seed_02_roles_agents.sql`
- `seed_03_field_master_196.csv`
- `seed_04_rules_293.csv`
- `seed_05_rc_rules_22.csv`
- `seed_06_tolerance_14.csv`
- `seed_07_templates.csv`
- `seed_08_sections_grades.csv`

---

## 6. VERSIONING AND MIGRATION STRATEGY

### 6.1 Schema Version Table
`db_version_log` tracks every schema change. First seed entry:
```sql
INSERT INTO db_version_log (schema_version, applied_at, applied_by, notes)
VALUES ('1.0.0', datetime('now'), 'IT_LEAD', 'Phase 5 initial schema — IFS-P4-SCHEMA-20260423');
```

### 6.2 Migration Approach
- Each migration is a numbered SQL file: `migrate_1.0.0_to_1.0.1.sql`
- Migrations apply via Python script `db_migrate.py` using SQLite `BEGIN TRANSACTION` / `COMMIT`
- Migration script logs entry to `db_version_log` on successful apply
- Failed migration rolls back and logs to stderr; DB state preserved

### 6.3 Rule Version Control
`validation_rule_master` does not DELETE rows. When a rule changes:
- Old row: `status = 'DEPRECATED'` (field added but never set to deprecated in v3 — kept for future)
- New row: insert with updated content
- Rule proposals tracked via `rule_proposal_log` with engineering sign-off before activation

### 6.4 Backup / Restore
- SQLite DB file: daily backup via OS task to `/backups/ifs_db_YYYYMMDD_HHMMSS.sqlite`
- Before each project release gate (S10): snapshot backup
- Restore: copy backup file; run `PRAGMA integrity_check;` to verify
- Stage checkpoints (`stage_checkpoint` table) allow point-in-time field value rollback without full DB restore

---

## 7. IMPLEMENTATION RISKS

| Risk | Severity | Mitigation |
|---|---|---|
| SQLite WAL mode conflicts on networked drives | Medium | Deploy DB on local SSD only; no network path |
| Large JSON blobs in `data_snapshot` impacting query performance | Low | Keep snapshots lean; use field_population_event for detail |
| Missing seed data for 196 fields causing R-166 UNRESOLVED false positives | High | Seed validation script must pass all 9 count assertions before any project can be created |
| `unit_system` trigger bypassed via direct DB tool | Medium | DB file is app-access-only; restrict to application layer only |
| Audit table growth over hundreds of projects | Low | SQLite handles millions of rows; schedule annual archive of closed projects |
| CV-23 decision pending (OM-003) | Low | M-52 mapping table used interim; raise CR if CV-23 required |
| section_name uniqueness across standards | Medium | UNIQUE(section_name, design_standard) enforced; section DB seeded per standard |
| RC rules stored separately from semantic rules | Low | Both seeded before any project starts; engine loads from correct table |

---

*P4 — SQLite Schema Implementation | IFS-P4-SCHEMA-20260423 | DB Team Deliverable | Phase 5 Desktop Build*
