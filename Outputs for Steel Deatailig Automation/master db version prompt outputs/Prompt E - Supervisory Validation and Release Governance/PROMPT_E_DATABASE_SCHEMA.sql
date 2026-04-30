-- PROMPT E: SUPERVISORY VALIDATION AND RELEASE GOVERNANCE
-- Database Schema (Production-Ready DDL)
-- Date: April 2026
-- Authority: Engineering Controls & Release Management
-- Status: READY FOR DEPLOYMENT

-- ============================================================================
-- TABLE 1: supervisory_validation_master
-- Purpose: Central registry of all validation sessions (S1-S8)
-- Scope: One row per job analysis/revision; tracks all 8 stage results
-- ============================================================================

CREATE TABLE supervisory_validation_master (
    -- Identity & Session Keys
    validation_id TEXT PRIMARY KEY,  -- Format: VLD-{timestamp}-{seq}, e.g., VLD-20260421T140500Z-001
    job_id TEXT NOT NULL,
    revision_number INTEGER NOT NULL,
    analysis_type TEXT NOT NULL CHECK (analysis_type IN ('INITIAL', 'RE-ANALYSIS', 'POST-RELEASE')),
    
    -- Session Timeline
    analysis_start_timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    analysis_end_timestamp DATETIME,  -- NULL until analysis complete
    analysis_duration_minutes INTEGER,  -- Calculated: (end - start) in minutes
    
    -- Source References
    source_dxf_file TEXT,  -- DXF filename used (if any)
    source_dxf_parse_timestamp DATETIME,
    source_database_version TEXT,  -- Which database snapshot
    source_manual_input TEXT,  -- Notes on manual data entry (if any)
    
    -- Stage Results (One column per stage)
    stage_s1_status TEXT CHECK (stage_s1_status IN ('PASS', 'HOLD', 'BLOCK', 'PENDING')),
    stage_s1_gate_log_id TEXT,  -- Foreign key to design_validation_gate_log
    stage_s1_result_timestamp DATETIME,
    stage_s1_authority_role TEXT,  -- Role that made decision
    
    stage_s2_status TEXT CHECK (stage_s2_status IN ('PASS', 'HOLD', 'BLOCK', 'PENDING', 'SKIPPED')),
    stage_s2_gate_log_id TEXT,
    stage_s2_result_timestamp DATETIME,
    stage_s2_authority_role TEXT,
    
    stage_s3_status TEXT CHECK (stage_s3_status IN ('PASS', 'HOLD', 'BLOCK', 'PENDING', 'SKIPPED')),
    stage_s3_gate_log_id TEXT,
    stage_s3_result_timestamp DATETIME,
    stage_s3_authority_role TEXT,
    
    stage_s4_status TEXT CHECK (stage_s4_status IN ('PASS', 'HOLD', 'BLOCK', 'PENDING', 'SKIPPED')),
    stage_s4_gate_log_id TEXT,  -- Links to geometry_check_result_log (Prompt D)
    stage_s4_result_timestamp DATETIME,
    stage_s4_authority_role TEXT,
    
    stage_s5_status TEXT CHECK (stage_s5_status IN ('PASS', 'HOLD', 'BLOCK', 'PENDING', 'SKIPPED')),
    stage_s5_gate_log_id TEXT,
    stage_s5_result_timestamp DATETIME,
    stage_s5_authority_role TEXT,
    
    stage_s6_status TEXT CHECK (stage_s6_status IN ('PASS', 'HOLD', 'BLOCK', 'PENDING', 'SKIPPED')),
    stage_s6_gate_log_id TEXT,
    stage_s6_result_timestamp DATETIME,
    stage_s6_authority_role TEXT,
    
    stage_s7_status TEXT CHECK (stage_s7_status IN ('PASS', 'HOLD', 'BLOCK', 'PENDING', 'SKIPPED')),
    stage_s7_gate_log_id TEXT,
    stage_s7_result_timestamp DATETIME,
    stage_s7_authority_role TEXT,
    
    stage_s8_status TEXT CHECK (stage_s8_status IN ('PASS', 'HOLD', 'BLOCK', 'PENDING')),
    stage_s8_gate_log_id TEXT,
    stage_s8_result_timestamp DATETIME,
    stage_s8_authority_role TEXT,
    
    -- Overall Status & Severity Counts
    overall_validation_status TEXT NOT NULL CHECK (overall_validation_status IN ('PASS', 'HOLD', 'BLOCK', 'PENDING')),
    confidence_score DECIMAL(3,2),  -- 0.00 to 1.00
    critical_issues_count INTEGER DEFAULT 0,
    high_issues_count INTEGER DEFAULT 0,
    medium_issues_count INTEGER DEFAULT 0,
    low_issues_count INTEGER DEFAULT 0,
    total_issues_count INTEGER DEFAULT 0,  -- Calculated sum
    
    -- Override Tracking
    has_overrides BOOLEAN DEFAULT FALSE,
    override_ids TEXT,  -- Comma-separated list of override_ids from override_audit_log
    total_overrides_count INTEGER DEFAULT 0,
    
    -- Approval Status (Critical for S8/Release)
    p3_approval_status TEXT DEFAULT 'PENDING' CHECK (p3_approval_status IN ('PENDING', 'APPROVED', 'APPROVED_WITH_CONDITIONS', 'REJECTED')),
    p3_approval_timestamp DATETIME,
    p3_approver_name TEXT,
    p3_approval_notes TEXT,
    
    pm_approval_status TEXT DEFAULT 'PENDING' CHECK (pm_approval_status IN ('PENDING', 'APPROVED', 'APPROVED_WITH_CONDITIONS', 'REJECTED')),
    pm_approval_timestamp DATETIME,
    pm_approver_name TEXT,
    pm_approval_notes TEXT,
    
    -- Release Authority & Sign-Off
    release_authority_id TEXT,  -- FK to release_authority_master
    supervisory_sign_off_id TEXT,  -- FK to supervisory_sign_off_log
    final_release_timestamp DATETIME,  -- When released to production (S8 PASS)
    final_released_by_role TEXT,  -- Role that authorized release
    final_released_by_name TEXT,  -- Person name
    
    -- Audit Trail & System Fields
    audit_trail_complete BOOLEAN DEFAULT FALSE,  -- Set TRUE when all decisions logged & immutable
    audit_trail_locked_timestamp DATETIME,  -- When audit trail became immutable
    
    created_timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT NOT NULL,
    updated_by TEXT NOT NULL,
    
    -- Constraints
    UNIQUE (job_id, revision_number, analysis_type, analysis_start_timestamp),
    FOREIGN KEY (job_id) REFERENCES job_master(job_id),
    FOREIGN KEY (release_authority_id) REFERENCES release_authority_master(release_authority_id)
);

-- Indexes for supervisory_validation_master
CREATE INDEX idx_svm_job_id ON supervisory_validation_master(job_id);
CREATE INDEX idx_svm_overall_status ON supervisory_validation_master(overall_validation_status);
CREATE INDEX idx_svm_analysis_start ON supervisory_validation_master(analysis_start_timestamp DESC);
CREATE INDEX idx_svm_p3_approval ON supervisory_validation_master(p3_approval_status, p3_approval_timestamp);
CREATE INDEX idx_svm_pm_approval ON supervisory_validation_master(pm_approval_status, pm_approval_timestamp);
CREATE INDEX idx_svm_release_timestamp ON supervisory_validation_master(final_release_timestamp);
CREATE INDEX idx_svm_job_rev ON supervisory_validation_master(job_id, revision_number);

-- ============================================================================
-- TABLE 2: approval_role_matrix
-- Purpose: Define authorization by role and processing stage
-- Scope: 4 roles × 8 stages = 32 base rules (customizable per stage)
-- ============================================================================

CREATE TABLE approval_role_matrix (
    -- Identity
    approval_rule_id TEXT PRIMARY KEY,  -- Format: ARM-{role}-{stage}, e.g., ARM-P3-S4
    role_id TEXT NOT NULL,  -- DQE, P2, P3, PM
    role_name TEXT NOT NULL,  -- Full role name
    processing_stage TEXT NOT NULL CHECK (processing_stage IN ('S1', 'S2', 'S3', 'S4', 'S5', 'S6', 'S7', 'S8')),
    
    -- Decision Authority (What can this role do at this stage?)
    can_approve_pass BOOLEAN NOT NULL DEFAULT FALSE,
    can_approve_hold BOOLEAN NOT NULL DEFAULT FALSE,
    can_approve_block BOOLEAN NOT NULL DEFAULT FALSE,
    can_escalate BOOLEAN NOT NULL DEFAULT TRUE,
    escalates_to_role TEXT,  -- Which role receives escalation (e.g., 'P2', 'P3', 'PM')
    
    -- SLA & Timeline
    sla_hours INTEGER NOT NULL,  -- Decision deadline (4, 24, 48 hours typical)
    auto_escalate_if_unresolved BOOLEAN DEFAULT TRUE,
    escalation_target_role TEXT,  -- Role receiving auto-escalation if SLA exceeded
    escalation_sla_hours INTEGER,  -- SLA for escalation target
    
    -- Concurrence & Multi-Role Requirements
    requires_concurrence_from TEXT,  -- Role that must also approve (if any)
    concurrent_approval_required BOOLEAN DEFAULT FALSE,  -- TRUE = must approve at same time
    
    -- Authority Level & Limits
    decision_authority_level INTEGER NOT NULL CHECK (decision_authority_level BETWEEN 1 AND 4),  -- 1=lowest, 4=highest
    approval_limit_criticality TEXT,  -- Max issue severity this role can approve alone (CRITICAL/HIGH/MEDIUM/LOW)
    cannot_override TEXT,  -- Roles this role cannot override decisions from (comma-separated)
    
    -- Documentation & Audit
    required_documentation TEXT,  -- What must be documented (comma-separated)
    audit_trail_required BOOLEAN DEFAULT TRUE,
    notification_on_decision TEXT,  -- Roles to notify (comma-separated)
    
    -- Special Conditions
    requires_pm_concurrence_if TEXT,  -- Condition: "severity=CRITICAL" or similar
    requires_p3_concurrence_if TEXT,
    requires_client_notification_if TEXT,
    
    created_timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT NOT NULL,
    
    -- Constraints
    UNIQUE (role_id, processing_stage),
    FOREIGN KEY (escalates_to_role) REFERENCES approval_role_matrix(role_id)
);

-- Indexes
CREATE INDEX idx_arm_role_id ON approval_role_matrix(role_id);
CREATE INDEX idx_arm_stage ON approval_role_matrix(processing_stage);
CREATE INDEX idx_arm_authority_level ON approval_role_matrix(decision_authority_level);

-- ============================================================================
-- TABLE 3: release_authority_master
-- Purpose: Define release approval rules and conditions
-- Scope: Standards, emergency, and conditional release authorities
-- ============================================================================

CREATE TABLE release_authority_master (
    -- Identity
    release_authority_id TEXT PRIMARY KEY,  -- Format: REL-{type}, e.g., REL-STANDARD
    authority_type TEXT NOT NULL UNIQUE CHECK (authority_type IN ('STANDARD', 'EMERGENCY', 'CONDITIONAL')),
    
    -- Role Requirements
    primary_approver_role TEXT NOT NULL,  -- Primary authority (e.g., 'PM')
    secondary_approver_role TEXT,  -- Supporting role (e.g., 'P3')
    tertiary_approver_role TEXT,  -- Optional third role
    
    -- Approval Sequence
    approval_sequence INTEGER NOT NULL CHECK (approval_sequence IN (1, 2)),  -- 1=serial, 2=concurrent
    minimum_approvals_required INTEGER NOT NULL CHECK (minimum_approvals_required BETWEEN 1 AND 3),
    
    -- Release Conditions (Can release proceed if issues exist?)
    can_release_with_issues BOOLEAN NOT NULL DEFAULT FALSE,
    issue_type_allowed TEXT,  -- Which types: CRITICAL, HIGH, MEDIUM, LOW (comma-separated)
    issue_count_limit INTEGER,  -- Max unresolved issues allowed
    
    -- Justification Requirements
    requires_technical_justification BOOLEAN NOT NULL DEFAULT TRUE,
    requires_business_justification BOOLEAN NOT NULL DEFAULT TRUE,
    
    -- SLA & Escalation
    sla_hours INTEGER NOT NULL,
    escalation_if_disagreement TEXT,  -- Role that decides if approvers disagree
    
    -- Notifications & Compliance
    notification_recipients TEXT,  -- Roles/departments to notify (comma-separated)
    requires_audit_trail_complete BOOLEAN DEFAULT TRUE,
    requires_client_notification BOOLEAN DEFAULT FALSE,
    requires_compliance_review BOOLEAN DEFAULT FALSE,
    
    -- Emergency & Override Rules
    emergency_override_allowed BOOLEAN DEFAULT FALSE,
    emergency_override_approver TEXT,  -- Role that can authorize emergency override
    emergency_override_conditions TEXT,  -- When allowed (comma-separated conditions)
    
    -- Post-Release Tracking
    post_release_deviation_tracking BOOLEAN DEFAULT TRUE,
    post_release_sla_hours INTEGER DEFAULT 24,  -- SLA for handling post-release issues
    
    -- Monitoring & History
    automatic_compliance_check BOOLEAN DEFAULT TRUE,
    historical_approval_rate DECIMAL(3,2),  -- 0.00 to 1.00 (e.g., 0.98 = 98%)
    
    created_timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT NOT NULL
);

-- Indexes
CREATE INDEX idx_ram_authority_type ON release_authority_master(authority_type);
CREATE INDEX idx_ram_primary_approver ON release_authority_master(primary_approver_role);

-- ============================================================================
-- TABLE 4: manual_review_trigger_master
-- Purpose: Define when and why manual review is required
-- Scope: 10+ trigger conditions with escalation paths
-- ============================================================================

CREATE TABLE manual_review_trigger_master (
    -- Identity
    trigger_id TEXT PRIMARY KEY,  -- Format: MRT-{severity}-{category}, e.g., MRT-CRITICAL-GEOMETRY
    trigger_category TEXT NOT NULL CHECK (trigger_category IN (
        'GEOMETRY', 'DATABASE', 'SOURCE', 'OVERRIDE', 
        'GATE_BLOCK', 'SLA_ESCALATION', 'CONFLICT', 'DATA_QUALITY'
    )),
    trigger_name TEXT NOT NULL,  -- Human-readable: "Geometry CRITICAL Mismatch"
    severity_level TEXT NOT NULL CHECK (severity_level IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW')),
    
    -- Trigger Conditions
    processing_stages TEXT NOT NULL,  -- Comma-separated: S1,S2,S4 (stages affected)
    condition_description TEXT NOT NULL,  -- Plain English: "Grid spacing exceeds tolerance by >10mm"
    detection_method TEXT NOT NULL,  -- How to detect: SQL query or logic
    
    -- Review Authority & SLA
    required_reviewer_role TEXT NOT NULL,  -- Role that MUST review
    secondary_reviewer_role TEXT,  -- Optional concurrent reviewer
    sla_hours INTEGER NOT NULL,  -- Decision deadline
    escalation_role_if_unresolved TEXT NOT NULL,  -- Role to escalate if SLA exceeded
    escalation_sla_hours INTEGER NOT NULL,  -- Escalation deadline
    
    -- Review Options & Conditions
    review_options TEXT NOT NULL,  -- Comma-separated available actions
    approval_condition TEXT NOT NULL,  -- What reviewer must verify
    documentation_required TEXT NOT NULL,  -- Required documentation (comma-separated)
    
    -- Gate Impact
    notification_on_trigger TEXT,  -- Roles to notify
    auto_block_gate_until_resolved BOOLEAN NOT NULL DEFAULT TRUE,  -- Blocks current gate?
    blocks_downstream_gates TEXT,  -- Blocks downstream gates (S5,S6,S7,S8)?
    
    -- Override Capability
    can_be_overridden BOOLEAN NOT NULL DEFAULT FALSE,
    override_authority TEXT,  -- Role that can override this trigger
    override_requires_concurrence TEXT,  -- Role(s) that must concur with override
    
    -- Historical Performance
    historical_approval_rate DECIMAL(3,2),  -- % approved (0.00-1.00)
    historical_average_resolution_hours DECIMAL(5,2),
    escalation_history_count_12m INTEGER DEFAULT 0,  -- Times escalated in past 12 months
    
    created_timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT NOT NULL
);

-- Indexes
CREATE INDEX idx_mrt_category ON manual_review_trigger_master(trigger_category);
CREATE INDEX idx_mrt_severity ON manual_review_trigger_master(severity_level);
CREATE INDEX idx_mrt_reviewer_role ON manual_review_trigger_master(required_reviewer_role);
CREATE INDEX idx_mrt_can_override ON manual_review_trigger_master(can_be_overridden);

-- ============================================================================
-- TABLE 5: gate_bypass_control_master
-- Purpose: Define when and how gates can be bypassed
-- Scope: 8 bypass types with risk levels and compensating controls
-- ============================================================================

CREATE TABLE gate_bypass_control_master (
    -- Identity
    bypass_rule_id TEXT PRIMARY KEY,  -- Format: GBY-{stage}-{type}, e.g., GBY-S4-GEOMETRY_OVERRIDE
    bypass_type TEXT NOT NULL CHECK (bypass_type IN (
        'SOURCE_CORRECTION', 'DB_UPDATE', 'GEOMETRY_OVERRIDE', 'SKIP_VALIDATION',
        'GATE_OVERRIDE', 'CONFIDENCE_EXCEPTION', 'SLA_EXTENSION', 'POST_RELEASE_DEVIATION'
    )),
    processing_stage TEXT NOT NULL,  -- Affected stage(s)
    
    -- Bypass Definition
    bypass_condition TEXT NOT NULL,  -- What allows this bypass
    bypass_description TEXT NOT NULL,  -- Human-readable description
    
    -- Approval Requirements
    requires_approval_role TEXT NOT NULL,  -- Primary role that must approve
    requires_concurrence_from TEXT,  -- Role(s) that must also approve
    approval_required_count INTEGER NOT NULL CHECK (approval_required_count BETWEEN 1 AND 3),
    sla_hours INTEGER NOT NULL,  -- Approval deadline
    
    -- Risk Assessment
    risk_level TEXT NOT NULL CHECK (risk_level IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    risk_mitigation_actions TEXT NOT NULL,  -- Comma-separated required actions
    requires_impact_assessment BOOLEAN NOT NULL DEFAULT TRUE,
    
    -- Justification Requirements
    requires_technical_justification BOOLEAN NOT NULL DEFAULT TRUE,
    requires_business_justification BOOLEAN NOT NULL DEFAULT TRUE,
    
    -- Auto-Approval Logic (If any conditions met, can auto-approve?)
    can_auto_approve_if TEXT,  -- Conditions: "severity=LOW AND..."
    
    -- Gate Impact
    blocks_release_until_resolved BOOLEAN NOT NULL,  -- Does bypass block release?
    permanent_audit_trail_required BOOLEAN DEFAULT TRUE,
    creates_variance_log_entry BOOLEAN DEFAULT FALSE,  -- Creates engineering variance?
    
    -- Notifications & Compliance
    notification_recipients TEXT,  -- Roles to notify (comma-separated)
    external_compliance_impact BOOLEAN DEFAULT FALSE,
    client_notification_required BOOLEAN DEFAULT FALSE,
    
    -- Compensating Controls & QA
    qa_revalidation_required BOOLEAN DEFAULT FALSE,
    qa_revalidation_sla_hours INTEGER,  -- When QA must re-validate
    compensating_controls TEXT,  -- What controls exist if bypass granted
    
    created_timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT NOT NULL
);

-- Indexes
CREATE INDEX idx_gbc_bypass_type ON gate_bypass_control_master(bypass_type);
CREATE INDEX idx_gbc_stage ON gate_bypass_control_master(processing_stage);
CREATE INDEX idx_gbc_risk_level ON gate_bypass_control_master(risk_level);

-- ============================================================================
-- TABLE 6: supervisory_sign_off_log (Audit Trail)
-- Purpose: Permanent, immutable record of all S8 release decisions
-- Scope: Final sign-off log for compliance & audit
-- ============================================================================

CREATE TABLE supervisory_sign_off_log (
    -- Identity
    sign_off_id TEXT PRIMARY KEY,  -- Format: SGN-{timestamp}-{seq}
    validation_id TEXT NOT NULL,  -- FK to supervisory_validation_master
    job_id TEXT NOT NULL,
    revision_number INTEGER NOT NULL,
    
    -- Sign-Off Authority
    p3_engineer_name TEXT NOT NULL,
    p3_engineer_role TEXT NOT NULL DEFAULT 'P3',
    p3_approval_decision TEXT NOT NULL CHECK (p3_approval_decision IN ('APPROVED', 'APPROVED_WITH_CONDITIONS', 'REJECTED')),
    p3_approval_timestamp DATETIME NOT NULL,
    p3_approval_notes TEXT,
    
    pm_manager_name TEXT NOT NULL,
    pm_manager_role TEXT NOT NULL DEFAULT 'PM',
    pm_approval_decision TEXT NOT NULL CHECK (pm_approval_decision IN ('APPROVED', 'APPROVED_WITH_CONDITIONS', 'REJECTED')),
    pm_approval_timestamp DATETIME NOT NULL,
    pm_approval_notes TEXT,
    
    -- Final Release Decision
    final_decision TEXT NOT NULL CHECK (final_decision IN ('RELEASED', 'HELD', 'REJECTED', 'EMERGENCY_OVERRIDE')),
    final_decision_timestamp DATETIME NOT NULL,
    
    -- Issues Status at Release
    critical_issues_at_release INTEGER DEFAULT 0,
    high_issues_at_release INTEGER DEFAULT 0,
    overrides_applied INTEGER DEFAULT 0,
    
    -- Conditions/Exceptions
    released_with_conditions BOOLEAN DEFAULT FALSE,
    release_conditions TEXT,  -- Comma-separated list of conditions
    
    -- Audit Trail Integrity
    audit_trail_locked_timestamp DATETIME NOT NULL,
    audit_trail_hash TEXT,  -- SHA-256 hash of complete audit trail for integrity check
    
    -- Compliance
    compliance_check_passed BOOLEAN DEFAULT FALSE,
    compliance_check_timestamp DATETIME,
    compliance_notes TEXT,
    
    -- Post-Release
    actual_release_timestamp DATETIME,  -- When actually deployed to production
    released_to_environment TEXT,  -- Environment (DEV, STAGING, PRODUCTION)
    
    created_timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    -- Note: No updated_timestamp; this is append-only
    created_by TEXT NOT NULL,
    
    -- Constraints
    UNIQUE (validation_id),
    FOREIGN KEY (validation_id) REFERENCES supervisory_validation_master(validation_id),
    FOREIGN KEY (job_id) REFERENCES job_master(job_id)
);

-- Indexes
CREATE INDEX idx_ssl_validation_id ON supervisory_sign_off_log(validation_id);
CREATE INDEX idx_ssl_job_id ON supervisory_sign_off_log(job_id);
CREATE INDEX idx_ssl_final_decision ON supervisory_sign_off_log(final_decision);
CREATE INDEX idx_ssl_release_timestamp ON supervisory_sign_off_log(actual_release_timestamp);

-- ============================================================================
-- TABLE 7: override_audit_log (Comprehensive Override Tracking)
-- Purpose: Permanent record of every override applied
-- Scope: Tracks who approved what, when, and why
-- ============================================================================

CREATE TABLE override_audit_log (
    -- Identity
    override_id TEXT PRIMARY KEY,  -- Format: OVR-{timestamp}-{seq}
    validation_id TEXT NOT NULL,  -- FK to supervisory_validation_master
    bypass_rule_id TEXT NOT NULL,  -- FK to gate_bypass_control_master
    
    -- Override Type & Trigger
    override_type TEXT NOT NULL,  -- SOURCE_CORRECTION, DB_UPDATE, GEOMETRY_OVERRIDE, etc.
    processing_stage TEXT NOT NULL,  -- S1-S8 where override applied
    trigger_condition TEXT NOT NULL,  -- What triggered the override need
    
    -- Content Before/After
    old_value TEXT,  -- Value before override (if applicable)
    new_value TEXT,  -- Value after override
    field_affected TEXT,  -- Which field/dimension changed
    
    -- Approval Details
    approval_role_primary TEXT NOT NULL,  -- Role that approved
    approval_person_primary TEXT NOT NULL,  -- Name of approver
    approval_timestamp_primary DATETIME NOT NULL,
    approval_notes_primary TEXT,
    
    approval_role_secondary TEXT,  -- If multi-role approval
    approval_person_secondary TEXT,
    approval_timestamp_secondary DATETIME,
    approval_notes_secondary TEXT,
    
    -- Justifications
    technical_justification TEXT,  -- Why technically necessary
    business_justification TEXT,  -- Why business requires it
    impact_assessment TEXT,  -- Assessed impact on downstream
    
    -- Risk Assessment
    risk_level TEXT NOT NULL CHECK (risk_level IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    risk_mitigation_actions TEXT,  -- Actions taken to mitigate
    
    -- Compensating Controls
    compensating_controls_applied TEXT,  -- Controls in place if override granted
    qa_revalidation_required BOOLEAN DEFAULT FALSE,
    qa_revalidation_completed BOOLEAN DEFAULT FALSE,
    qa_revalidation_timestamp DATETIME,
    
    -- Escalation (if any)
    required_escalation BOOLEAN DEFAULT FALSE,
    escalated_to_role TEXT,
    escalation_timestamp DATETIME,
    
    -- System Fields (Append-Only)
    created_timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT NOT NULL,
    
    -- Constraints
    FOREIGN KEY (validation_id) REFERENCES supervisory_validation_master(validation_id),
    FOREIGN KEY (bypass_rule_id) REFERENCES gate_bypass_control_master(bypass_rule_id)
);

-- Indexes
CREATE INDEX idx_oal_validation_id ON override_audit_log(validation_id);
CREATE INDEX idx_oal_override_type ON override_audit_log(override_type);
CREATE INDEX idx_oal_risk_level ON override_audit_log(risk_level);
CREATE INDEX idx_oal_timestamp ON override_audit_log(created_timestamp DESC);

-- ============================================================================
-- SAMPLE DATA: Populating approval_role_matrix
-- ============================================================================

-- S1: Design Input Review
INSERT INTO approval_role_matrix VALUES (
    'ARM-DQE-S1', 'DQE', 'Data Quality Engineer', 'S1',
    TRUE, TRUE, FALSE, TRUE, 'P2', 4, TRUE, 'P2', 8,
    NULL, FALSE, 1, 'LOW', NULL, 'reason,approver', TRUE, 'P2,P3',
    NULL, NULL, NULL,
    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'SYSTEM'
);

INSERT INTO approval_role_matrix VALUES (
    'ARM-P3-S1', 'P3', 'Principal Engineer', 'S1',
    TRUE, TRUE, TRUE, FALSE, NULL, 4, FALSE, NULL, NULL,
    NULL, FALSE, 3, 'CRITICAL', NULL, 'reason,approver,escalation_trigger', TRUE, 'ALL',
    NULL, NULL, NULL,
    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'SYSTEM'
);

-- S2: Source Integrity
INSERT INTO approval_role_matrix VALUES (
    'ARM-DQE-S2', 'DQE', 'Data Quality Engineer', 'S2',
    TRUE, TRUE, TRUE, TRUE, 'P2', 4, TRUE, 'P2', 8,
    NULL, FALSE, 1, 'MEDIUM', NULL, 'reason,parse_error', TRUE, 'P2',
    NULL, NULL, NULL,
    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'SYSTEM'
);

INSERT INTO approval_role_matrix VALUES (
    'ARM-P2-S2', 'P2', 'Structural Engineer', 'S2',
    TRUE, TRUE, FALSE, TRUE, 'P3', 24, TRUE, 'P3', 24,
    'DQE', FALSE, 2, 'HIGH', NULL, 'reason,confidence_justification', TRUE, 'P3',
    'severity=HIGH', NULL, NULL,
    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'SYSTEM'
);

-- S4: Geometry Validation (Integrated with Prompt D)
INSERT INTO approval_role_matrix VALUES (
    'ARM-P3-S4', 'P3', 'Principal Engineer', 'S4',
    TRUE, FALSE, TRUE, TRUE, 'PM', 4, FALSE, 'PM', 24,
    'P2', TRUE, 3, 'CRITICAL', NULL, 'reason,technical_justification,escalation_trigger', TRUE, 'ALL',
    'severity=CRITICAL', NULL, NULL,
    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'SYSTEM'
);

INSERT INTO approval_role_matrix VALUES (
    'ARM-P2-S4', 'P2', 'Structural Engineer', 'S4',
    TRUE, TRUE, FALSE, TRUE, 'P3', 24, TRUE, 'P3', 4,
    NULL, FALSE, 2, 'HIGH', NULL, 'reason,technical_basis', TRUE, 'P3',
    NULL, 'severity=CRITICAL', NULL,
    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'SYSTEM'
);

-- S8: Final Sign-Off (Release Authority)
INSERT INTO approval_role_matrix VALUES (
    'ARM-PM-S8', 'PM', 'Project Manager', 'S8',
    TRUE, FALSE, TRUE, FALSE, NULL, 24, FALSE, NULL, NULL,
    'P3', TRUE, 4, 'CRITICAL', NULL, 'reason,business_justification,release_conditions', TRUE, NULL,
    NULL, NULL, 'severity=CRITICAL OR has_overrides=TRUE',
    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'SYSTEM'
);

INSERT INTO approval_role_matrix VALUES (
    'ARM-P3-S8', 'P3', 'Principal Engineer', 'S8',
    TRUE, FALSE, TRUE, FALSE, NULL, 24, FALSE, NULL, NULL,
    'PM', TRUE, 3, 'CRITICAL', NULL, 'reason,technical_justification,compliance_confirmation', TRUE, 'PM',
    NULL, NULL, 'severity=CRITICAL OR has_overrides=TRUE',
    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'SYSTEM'
);

-- ============================================================================
-- SAMPLE DATA: release_authority_master
-- ============================================================================

INSERT INTO release_authority_master VALUES (
    'REL-STANDARD', 'STANDARD', 'PM', 'P3', NULL, 2, 2,
    FALSE, NULL, 0, TRUE, TRUE, 24, 'PM',
    'P2,P3,DQE,AUDIT', TRUE, FALSE, FALSE,
    FALSE, NULL, NULL, TRUE, 24,
    TRUE, 0.98,
    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'SYSTEM'
);

INSERT INTO release_authority_master VALUES (
    'REL-EMERGENCY', 'EMERGENCY', 'PM', 'P3', 'DQE', 1, 2,
    TRUE, 'MEDIUM,LOW', 5, TRUE, TRUE, 4, 'Program_Lead',
    'ALL', FALSE, TRUE, TRUE,
    TRUE, 'Program_Lead', 'Production_Outage, Client_Escalation, Safety_Issue', TRUE, 48,
    TRUE, 0.87,
    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'SYSTEM'
);

-- ============================================================================
-- SAMPLE DATA: manual_review_trigger_master
-- ============================================================================

INSERT INTO manual_review_trigger_master VALUES (
    'MRT-CRITICAL-GEOMETRY', 'GEOMETRY', 'Geometry CRITICAL Mismatch', 'CRITICAL',
    'S4', 'Grid spacing, column position, or building dimension exceeds tolerance by >10mm',
    'SELECT * FROM geometry_check_result_log WHERE severity=''CRITICAL'' AND job_id=? AND revision_number=?',
    'P3', 'P2', 4, 'PM', 24,
    'Approve_DXF, Update_DB, Request_CAD_Reparse, Approve_Override',
    'Must verify no assembly impact, no downstream fab issues',
    'technical_reason, engineering_justification, impact_assessment',
    'P2,PM', TRUE, 'S5,S6,S7,S8',
    TRUE, 'P3', 'P2,PM', 0.95, 2.5, 0,
    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'SYSTEM'
);

INSERT INTO manual_review_trigger_master VALUES (
    'MRT-HIGH-GATE_BLOCK', 'GATE_BLOCK', 'Unresolved Gate BLOCK', 'HIGH',
    'S2,S3,S4,S5,S6,S7,S8', 'Any processing stage gate is BLOCK and unresolved for >2 hours',
    'SELECT * FROM *_gate_log WHERE status=''BLOCK'' AND created_timestamp > datetime(now,''-2 hours'')',
    'P3', 'PM', 4, 'PM', 24,
    'Remediate_Root_Cause, Request_Exception, Escalate_to_Program_Lead',
    'Must document technical reason, verify no safety impact',
    'root_cause, technical_solution, escalation_justification',
    'PM,AUDIT', TRUE, 'S5,S6,S7,S8',
    FALSE, NULL, NULL, 0.92, 1.8, 3,
    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'SYSTEM'
);

-- ============================================================================
-- SAMPLE DATA: gate_bypass_control_master
-- ============================================================================

INSERT INTO gate_bypass_control_master VALUES (
    'GBY-S4-GEOMETRY_OVERRIDE', 'GEOMETRY_OVERRIDE', 'S4',
    'Geometry mismatch exists but acceptable due to manufacturing variation or as-built condition',
    'Accept DXF geometry despite mismatch to database expected values',
    'P3', 'P2,PM', 2, 24,
    'HIGH', 'Document_Reason, Log_Variance, Notify_Fab, Revalidate_Assembly_Sequence',
    TRUE, TRUE, TRUE, 'severity=CRITICAL',
    FALSE, TRUE, TRUE,
    'P2,PM,DQE', FALSE, FALSE, TRUE, 48,
    'Engineering_Review, Fab_Feasibility_Check', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'SYSTEM'
);

INSERT INTO gate_bypass_control_master VALUES (
    'GBY-S8-RELEASE_OVERRIDE', 'GATE_OVERRIDE', 'S8',
    'Request to release despite HOLD or BLOCK at S8',
    'Release production approval when gate is not PASS',
    'PM', 'P3,AUDIT', 2, 24,
    'CRITICAL', 'Approve_Deviation_Control, Document_Risk, Plan_Remediation, Post_Release_Monitoring',
    TRUE, TRUE, TRUE, 'critical_issues_count=0',
    TRUE, TRUE, TRUE,
    'ALL', TRUE, TRUE, TRUE, 24,
    'SLA_Tracking, Deviation_Closeout, Root_Cause_Analysis', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'SYSTEM'
);

-- ============================================================================
-- END OF SCHEMA
-- Status: PRODUCTION READY
-- Execute in order: Tables 1-7, then Sample Data sections
-- ============================================================================
