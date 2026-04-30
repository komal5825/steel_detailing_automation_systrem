-- ============================================================================
-- MASTERDB v2.1 — GEOMETRY RECONCILIATION SCHEMA
-- DXF-DATABASE GEOMETRY RECONCILIATION MODULE
-- ============================================================================
-- 
-- Purpose: Define 4 new database tables for geometry reconciliation, validation,
--          tolerance management, and audit logging
--
-- Authority: Geometry Validation Engineering
-- Date: April 2026
-- Status: PRODUCTION READY
--
-- ============================================================================

-- ============================================================================
-- TABLE 1: GEOMETRY_RECONCILIATION_MASTER
-- ============================================================================
-- Purpose: Central repository of baseline geometry for all jobs
--          Serves as reference point for all reconciliation checks
--
-- Storage: One row per job per revision
-- Expected Rows: ~5000 (5 rows per major job revision)
-- ============================================================================

CREATE TABLE IF NOT EXISTS geometry_reconciliation_master (
  -- Primary Keys
  job_id TEXT NOT NULL,
  revision_number INTEGER NOT NULL,
  PRIMARY KEY (job_id, revision_number),

  -- ========== GEOMETRY SOURCE ==========
  geometry_source TEXT,
    -- 'DXF' = parsed from DXF/DWG file
    -- 'MANUAL' = engineer-entered coordinates
    -- 'HYBRID' = mix of DXF and manual overrides
    -- 'CALCULATED' = derived from grid_spacing and bay count
  
  geometry_source_file TEXT,
    -- File path or name of source DXF/drawing
    -- Example: "C:\CAD\Project_GA_Rev2.dwg"
  
  geometry_extraction_date TIMESTAMP,
    -- When geometry was last extracted from source
  
  geometry_extraction_method TEXT,
    -- 'ezdxf' = parsed with ezdxf library
    -- 'manual_input' = engineer-entered values
    -- 'CAD_export' = exported from CAD system
    -- 'calculation' = computed from grid spacing
  
  geometry_extraction_confidence REAL,
    -- 0.0 to 1.0, quality of extraction
    -- >= 0.85 = high confidence (DXF parsed cleanly)
    -- 0.70-0.84 = medium confidence (minor parsing issues)
    -- < 0.70 = low confidence (manual review required)

  -- ========== GRID GEOMETRY (PRIMARY) ==========
  grid_spacing_x REAL,
    -- Typical X-axis spacing (mm)
    -- Example: 6000 for 6m grid
    -- Source: DXF grid spacing or manual entry
  
  grid_spacing_y REAL,
    -- Typical Y-axis spacing (mm)
    -- Example: 9000 for 9m grid
  
  grid_origin_x REAL,
    -- X coordinate of grid origin (mm)
    -- Usually 0.0, but may be offset if CAD model offset
  
  grid_origin_y REAL,
    -- Y coordinate of grid origin (mm)
    -- Usually 0.0, but may be offset if CAD model offset
  
  bay_count_x INTEGER,
    -- Number of bays in X direction
    -- Example: 3 bays = 4 grid lines
  
  bay_count_y INTEGER,
    -- Number of bays in Y direction
    -- Example: 2 bays = 3 grid lines

  -- ========== BUILDING ENVELOPE ==========
  -- Derived from grid spacing * bay count, but may be overridden
  
  building_length REAL,
    -- Overall building length X-direction (mm)
    -- Example: 18000 for 3 bays of 6000mm
    -- Calculated: grid_spacing_x * bay_count_x (if uniform spacing)
    -- Or: MAX(grid_x) - MIN(grid_x) if variable spacing
  
  building_width REAL,
    -- Overall building width Y-direction (mm)
    -- Example: 18000 for 2 bays of 9000mm
  
  building_height REAL,
    -- Building height Z-direction (mm)
    -- Example: 8000 for single-story, eave height
    -- Source: roof_eave_height field
  
  -- ========== ELEVATION SCHEDULE ==========
  level_count INTEGER,
    -- Number of distinct floor/roof levels
    -- Example: 1 = single story, 2 = two-story, etc.
  
  first_level_elevation REAL,
    -- Z-elevation of foundation/first floor (mm)
    -- Typically 0 or reference datum
  
  typical_floor_height REAL,
    -- Typical floor-to-floor height (mm)
    -- Example: 4000 for office buildings
    -- Used to calculate intermediate level elevations
  
  roof_eave_elevation REAL,
    -- Z-elevation at roof eave (mm)
    -- Example: 8000 for single-story

  -- ========== COLUMN GRID & COORDINATES ==========
  -- Explicit overrides for non-grid column positions
  
  column_coords_json TEXT,
    -- JSON array of column positions at grid intersections
    -- Format: [
    --   {
    --     "grid_x_index": 0,
    --     "grid_y_index": 0,
    --     "x_actual": 0.0,
    --     "y_actual": 0.0,
    --     "mark": "A1",
    --     "is_override": false,
    --     "override_reason": null
    --   },
    --   {
    --     "grid_x_index": 1,
    --     "grid_y_index": 0,
    --     "x_actual": 6000.0,
    --     "y_actual": 0.0,
    --     "mark": "B1",
    --     "is_override": true,
    --     "override_reason": "Offset for crane clearance"
    --   }
    -- ]
    -- Null if all columns on regular grid
  
  -- ========== MEMBER MARKS REFERENCE ==========
  member_mark_count INTEGER,
    -- Count of distinct member marks on drawing
    -- Example: 45 for 45-member structure
  
  member_marks_json TEXT,
    -- JSON array of expected member mark positions
    -- Format: [
    --   {
    --     "member_id": "M1",
    --     "x": 3000.0,
    --     "y": 4500.0,
    --     "grid_x": 0.5,
    --     "grid_y": 0.5,
    --     "member_type": "column"
    --   },
    --   {
    --     "member_id": "M2",
    --     "x": 6000.0,
    --     "y": 0.0,
    --     "grid_x": 1.0,
    --     "grid_y": 0.0,
    --     "member_type": "column"
    --   }
    -- ]

  -- ========== ANCHOR BOLT (AB) GRID ==========
  ab_grid_spacing_x REAL,
    -- Anchor bolt spacing X direction (mm)
    -- May differ from structural grid
    -- Example: 5000 vs 6000 structural spacing
  
  ab_grid_spacing_y REAL,
    -- Anchor bolt spacing Y direction (mm)
  
  ab_grid_offset_x REAL,
    -- X offset of AB grid from structural origin (mm)
  
  ab_grid_offset_y REAL,
    -- Y offset of AB grid from structural origin (mm)
  
  ab_coords_json TEXT,
    -- JSON array of anchor bolt coordinates
    -- Format: [
    --   {"x": 0.0, "y": 0.0, "bolt_diameter": 20, "bolt_grade": "A325"},
    --   {"x": 5000.0, "y": 0.0, "bolt_diameter": 20, "bolt_grade": "A325"}
    -- ]

  -- ========== METADATA ==========
  confidence_score REAL,
    -- 0.0 to 1.0, overall geometry extraction quality
    -- Aggregate of all component confidences
    -- >= 0.80 = PASS (release-ready)
    -- 0.70-0.79 = CAUTION (review before release)
    -- < 0.70 = FLAG (must resolve before release)
  
  data_source_rank INTEGER,
    -- 1 = DXF (ezdxf parsing) — highest confidence
    -- 2 = STAAD extraction
    -- 3 = Manual engineer entry
    -- 4 = Calculation from grid spacing
    -- 5 = Template/default
  
  design_standard TEXT,
    -- Links to design_standard for tolerance lookup
    -- Example: "AWS D1.1", "AISC 360-22"
    -- Used by geometry_tolerance_master to select thresholds
  
  created_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- When record created
  
  updated_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- Last modification timestamp
  
  created_by TEXT,
    -- User ID who created geometry record
  
  updated_by TEXT,
    -- User ID who last modified record
  
  override_flag BOOLEAN DEFAULT FALSE,
    -- TRUE if any geometry values have been overridden after initial extraction
  
  override_notes TEXT,
    -- Documentation of overrides
    -- Example: "Column A3 offset 50mm for crane clearance per engineering approval"
  
  qa_verified BOOLEAN DEFAULT FALSE,
    -- QA sign-off on geometry accuracy
  
  qa_verified_by TEXT,
    -- QA engineer who verified
  
  qa_verification_date TIMESTAMP
    -- Date of QA verification

);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_geom_master_job 
  ON geometry_reconciliation_master(job_id);

CREATE INDEX IF NOT EXISTS idx_geom_master_design_std 
  ON geometry_reconciliation_master(design_standard);

CREATE INDEX IF NOT EXISTS idx_geom_master_confidence 
  ON geometry_reconciliation_master(confidence_score);

CREATE INDEX IF NOT EXISTS idx_geom_master_source_rank 
  ON geometry_reconciliation_master(data_source_rank);

-- ============================================================================
-- TABLE 2: GEOMETRY_CHECK_RESULT_LOG
-- ============================================================================
-- Purpose: Permanent audit trail of all geometry reconciliation checks
--          One row per check executed per job
--
-- Storage: Append-only log; never delete
-- Expected Rows: ~30-50 per job revision (8 check categories × 4-6 issues avg)
-- Retention: Permanent (compliance & audit trail)
-- ============================================================================

CREATE TABLE IF NOT EXISTS geometry_check_result_log (
  -- Primary Key
  check_id TEXT PRIMARY KEY,
    -- Unique identifier: GR-{date}-{time}-{seq}
    -- Example: GR-2026-04-21-143022-001
    -- YYYYMMDD-HHMMSS format for sorting
  
  -- ========== JOB REFERENCE ==========
  job_id TEXT NOT NULL,
  revision_number INTEGER NOT NULL,
    -- Foreign key: links to geometry_reconciliation_master
    -- Composite unique constraint below
  
  FOREIGN KEY (job_id, revision_number)
    REFERENCES geometry_reconciliation_master(job_id, revision_number)
      ON UPDATE CASCADE
      ON DELETE RESTRICT,  -- Never delete master if checks exist

  -- ========== CHECK DETAILS ==========
  check_category TEXT NOT NULL,
    -- grid_spacing — bay-to-bay spacing consistency
    -- building_length — overall X dimension
    -- building_width — overall Y dimension
    -- column_coords — column position accuracy
    -- elevation_schedule — floor elevation consistency
    -- ab_grid — anchor bolt grid spacing
    -- member_marks — mark position consistency
    -- drawing_scale — detect corrupted/scaled drawings
  
  check_description TEXT,
    -- Human-readable description of what was checked
    -- Example: "Grid spacing validation for bay 2 (X-direction)"
  
  source_pair TEXT NOT NULL,
    -- Which values were compared
    -- Example: "DXF grid spacing vs Database spacing"
    -- Example: "Extracted building length vs Calculated from grid"
  
  expected_value REAL,
    -- Baseline value from database/calculation
    -- Example: 6000.0 (expected grid spacing)
  
  actual_extracted_value REAL,
    -- Value extracted from DXF or other source
    -- Example: 6100.0 (actual DXF spacing)
  
  delta REAL,
    -- Difference: ABS(actual - expected)
    -- Example: 100.0
    -- Always positive; sign lost
  
  tolerance REAL,
    -- Allowed delta for this check category
    -- Example: 2.0 for grid spacing
    -- Retrieved from geometry_tolerance_master
  
  exceeds_tolerance BOOLEAN,
    -- TRUE if delta > tolerance
    -- Determines if severity escalates
  
  percentage_error REAL,
    -- (delta / expected) * 100 for relative severity
    -- Example: (100 / 6000) * 100 = 1.67% error
    -- Null if expected_value is 0

  -- ========== SEVERITY & ACTION ==========
  severity TEXT NOT NULL,
    -- CRITICAL — jeopardizes safety/fit-up
    -- HIGH — requires rework or approval
    -- MEDIUM — minor variation; field-adjustable
    -- LOW — acceptable quality variation
  
  severity_rationale TEXT,
    -- Why classified this severity
    -- Example: "3+ column positions offset by 5mm; affects assembly sequence"
  
  action_determined TEXT NOT NULL,
    -- BLOCK — hard stop; escalate to principal engineer
    -- HOLD — pause workflow; queue for manual review
    -- WARN — log warning; proceed with notification
    -- PASS — no action; automatic approval
  
  action_stage TEXT,
    -- Processing stage where action applied (S1-S10)
    -- Example: "S2" for design parsing stage
    -- Example: "S4" for AB output stage
  
  blocks_downstream BOOLEAN,
    -- TRUE if action = BLOCK or HOLD
    -- Prevents downstream output generation
  
  -- ========== MANUAL REVIEW ==========
  manual_review_required BOOLEAN DEFAULT FALSE,
    -- TRUE if severity HIGH or mismatch critical
  
  review_authority TEXT,
    -- P2 Engineer, P3 Geometry Engineer, QA, etc.
    -- Determines who approves resolution
  
  review_queued_timestamp TIMESTAMP,
    -- When review was queued (for SLA tracking)
  
  reviewed_by TEXT,
    -- Engineer ID who performed review
  
  review_timestamp TIMESTAMP,
    -- When review was completed
  
  review_decision TEXT,
    -- APPROVED — engineer approves as-is
    -- APPROVED_WITH_NOTES — approved + documentation
    -- REJECTED — must resolve before release
    -- ESCALATED — forwarded to higher authority
    -- PENDING — awaiting review
  
  review_notes TEXT,
    -- Engineer comments on review decision
    -- Example: "Column offset acceptable per fit-up analysis; document as-built"

  -- ========== TRACEABILITY ==========
  linked_rule_id TEXT,
    -- Validation rule that triggered this check
    -- Example: VR-GEOM-02, VR-GEOM-03, etc.
    -- Links to geometry_conflict_action_master
  
  linked_field_id TEXT,
    -- Database field that triggered validation
    -- Example: F-039 (grid_spacing_x)
    -- Links to field master table (from Prompt B rules)
  
  validation_module TEXT,
    -- Which module executed this check
    -- M-GEOM-01 = DXF extraction
    -- M-GEOM-02 = Database geometry reading
    -- M-GEOM-03 = Tolerance-based reconciliation
    -- M-GEOM-04 = Severity classification
    -- M-GEOM-05 = Audit logging
  
  -- ========== METADATA ==========
  check_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- When check was executed
  
  check_execution_time_ms INTEGER,
    -- Elapsed time for this check (milliseconds)
    -- For performance monitoring
  
  confidence_score REAL,
    -- Confidence in the extraction/comparison
    -- May differ from master.confidence_score if partial data
  
  data_quality_notes TEXT,
    -- Any notes on data quality issues
    -- Example: "DXF layer configuration ambiguous; multiple grid layers detected"
  
  documentation_url TEXT
    -- Link to external documentation
    -- Example: URL to drawing PDF, variance approval document, etc.

);

-- Indexes for querying
CREATE INDEX IF NOT EXISTS idx_geom_check_job 
  ON geometry_check_result_log(job_id, revision_number);

CREATE INDEX IF NOT EXISTS idx_geom_check_severity 
  ON geometry_check_result_log(severity);

CREATE INDEX IF NOT EXISTS idx_geom_check_action 
  ON geometry_check_result_log(action_determined);

CREATE INDEX IF NOT EXISTS idx_geom_check_category 
  ON geometry_check_result_log(check_category);

CREATE INDEX IF NOT EXISTS idx_geom_check_timestamp 
  ON geometry_check_result_log(check_timestamp);

CREATE INDEX IF NOT EXISTS idx_geom_check_rule 
  ON geometry_check_result_log(linked_rule_id);

-- Unique constraint: One check per category per job per revision
-- (Multiple issues in same category allowed; constraint on category, not on condition)
-- Removed for flexibility — multiple checks per category/job/revision OK

-- ============================================================================
-- TABLE 3: GEOMETRY_TOLERANCE_MASTER
-- ============================================================================
-- Purpose: Central repository of tolerance rules
--          Used by M-GEOM-03 to validate geometry
--
-- Storage: Static lookup table; updated only by engineering
-- Expected Rows: 8-12 (one per check category, potentially multiple per standard)
-- Retention: Permanent (tolerance history for audit)
-- ============================================================================

CREATE TABLE IF NOT EXISTS geometry_tolerance_master (
  -- Primary Key
  tolerance_id TEXT PRIMARY KEY,
    -- Unique ID: TGEOM-001, TGEOM-002, etc.
  
  -- ========== CHECK CATEGORY ==========
  check_category TEXT NOT NULL UNIQUE,
    -- grid_spacing
    -- building_length
    -- building_width
    -- column_coords
    -- elevation
    -- ab_grid (anchor bolt grid)
    -- member_marks
    -- drawing_scale
  
  check_description TEXT,
    -- Human-readable description
    -- Example: "Validate grid spacing consistency per bay"
  
  check_methodology TEXT,
    -- How tolerance is applied
    -- Example: "ABS(extracted_span - db_span) <= tolerance"
    -- Used by M-GEOM-03 logic

  -- ========== TOLERANCE THRESHOLDS (mm or %) ==========
  tolerance_unit TEXT DEFAULT 'mm',
    -- 'mm' for linear dimensions
    -- '%' for percentages/ratios
    -- 'count' for discrete (bay count)
  
  tolerance_nominal REAL NOT NULL,
    -- Standard acceptable delta
    -- Example: 2.0 mm for grid spacing
    -- PASS if delta <= this value
  
  tolerance_hold_low REAL,
    -- Lower bound for HOLD review threshold
    -- Example: -5.0 mm
    -- HOLD if exceeds this but below critical
  
  tolerance_hold_high REAL,
    -- Upper bound for HOLD review threshold
    -- Example: +5.0 mm
  
  tolerance_critical_low REAL,
    -- Lower bound for CRITICAL/BLOCK threshold
    -- Example: -10.0 mm
    -- BLOCK if exceeds this
  
  tolerance_critical_high REAL,
    -- Upper bound for CRITICAL/BLOCK threshold
    -- Example: +10.0 mm

  -- ========== SEVERITY LOGIC ==========
  severity_if_within_nominal TEXT DEFAULT 'LOW',
    -- Typically 'LOW' if within tolerance
  
  severity_if_exceeds_nominal TEXT DEFAULT 'MEDIUM',
    -- If between nominal and hold threshold
  
  severity_if_exceeds_hold TEXT DEFAULT 'HIGH',
    -- If between hold and critical threshold
  
  severity_if_exceeds_critical TEXT DEFAULT 'CRITICAL',
    -- If exceeds critical threshold

  -- ========== ACTION LOGIC ==========
  action_if_within_nominal TEXT DEFAULT 'PASS',
  action_if_exceeds_nominal TEXT DEFAULT 'WARN',
  action_if_exceeds_hold TEXT DEFAULT 'HOLD',
  action_if_exceeds_critical TEXT DEFAULT 'BLOCK',

  -- ========== APPLICABILITY ==========
  applicable_design_standards TEXT,
    -- JSON array or comma-separated
    -- Example: "AWS D1.1, AISC 360-22"
    -- Or: ["AWS D1.1", "AISC 360-22"]
    -- "ALL" means applies to all standards
  
  applicable_stages TEXT,
    -- JSON array or comma-separated: S1, S2, S3, etc.
    -- Example: "S2, S3, S4" (Design parsing through AB/GA output)
    -- Or: ["S2", "S3", "S4"]
  
  applicable_frame_types TEXT,
    -- JSON array or comma-separated
    -- Example: "Structural, Building, Industrial"
    -- Or: ["Structural", "Building"]
    -- "ALL" means applies to all types
  
  applicable_for_critical_connections BOOLEAN DEFAULT FALSE,
    -- TRUE if tolerance stricter for critical connections
    -- Example: AB grid tolerance tighter than standard grid
  
  -- ========== BASIS & DOCUMENTATION ==========
  basis_standard TEXT,
    -- Authority document
    -- Example: "AISC 360-22, Section J3.2"
    -- Example: "AWS D1.1:2020, Paragraph 4.3"
  
  basis_document TEXT,
    -- Internal document
    -- Example: "Fabrication Tolerance Guide v3"
    -- Example: "Foundation Design Standards"
  
  basis_url TEXT,
    -- URL to online document or reference
  
  notes TEXT,
    -- Additional notes
    -- Example: "Tightened for precision marine applications"
  
  -- ========== AUDIT ==========
  created_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  
  updated_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  
  created_by TEXT,
  
  approval_authority TEXT,
    -- P3 Geometry Engineer
    -- Engineering Director
  
  approval_date DATE,
  
  effective_date DATE,
    -- When tolerance becomes effective
    -- Allows historical tolerance tracking

);

-- Sample insert statements (examples):
/*
INSERT INTO geometry_tolerance_master VALUES (
  'TGEOM-001',
  'grid_spacing',
  'Validate grid spacing consistency per bay',
  'ABS(extracted_span - db_span) <= tolerance',
  'mm',
  2.0,           -- nominal
  -5.0, 5.0,     -- hold
  -10.0, 10.0,   -- critical
  'LOW', 'MEDIUM', 'HIGH', 'CRITICAL',
  'PASS', 'WARN', 'HOLD', 'BLOCK',
  'ALL',
  'S2, S3, S4, S5',
  'ALL',
  FALSE,
  'AISC 360-22, Section J3.2',
  'Fabrication Tolerance Guide v3',
  'https://internal.wiki/standards/fab-tolerance-v3',
  'Per-bay consistency critical for assembly sequence',
  CURRENT_TIMESTAMP, CURRENT_TIMESTAMP,
  'engineer_id',
  'P3 Geometry Engineer',
  CURRENT_DATE,
  CURRENT_DATE
);
*/

-- ============================================================================
-- TABLE 4: GEOMETRY_CONFLICT_ACTION_MASTER
-- ============================================================================
-- Purpose: Define mandatory actions for each severity/stage combination
--          Determines how workflow responds to geometry conflicts
--
-- Storage: Reference table; updated by engineering
-- Expected Rows: ~40 (5 severities × 8 stages)
-- Retention: Permanent (action history for audit)
-- ============================================================================

CREATE TABLE IF NOT EXISTS geometry_conflict_action_master (
  -- Primary Key
  action_id TEXT PRIMARY KEY,
    -- Unique ID: GCA-001, GCA-002, etc.
  
  -- ========== SEVERITY & STAGE ==========
  severity TEXT NOT NULL,
    -- CRITICAL, HIGH, MEDIUM, LOW
  
  processing_stage TEXT NOT NULL,
    -- S1 = Intake
    -- S2 = Design Parsing
    -- S3 = Field Population
    -- S4 = AB Output
    -- S5 = GA Output
    -- S6 = Validation
    -- S7 = Shop Detailing
    -- S8 = Installation Planning
    -- S9 = Release
    -- S10 = Post-Release
  
  UNIQUE(severity, processing_stage),

  -- ========== MANDATORY ACTION ==========
  action TEXT NOT NULL,
    -- BLOCK — hard stop; escalate immediately
    -- HOLD — pause; queue for manual review
    -- WARN — log warning; proceed with notification
    -- PASS — no action; automatic approval
  
  action_description TEXT,
    -- Why this action for this severity/stage combo
    -- Example: "Grid mismatch at design stage must be resolved before proceeding"
  
  -- ========== AUTHORITY & ESCALATION ==========
  decision_authority TEXT,
    -- Who makes the decision
    -- 'Workflow' = automatic by system
    -- 'P2 Engineer' = P2 Structural Engineer
    -- 'P3 Geometry Engineer' = Principal geometry authority
    -- 'QA Lead' = Quality assurance authority
    -- 'Project Manager' = PM approval (for schedule impact)
  
  escalation_authority TEXT,
    -- Who escalates if no decision made in time
    -- Usually one level above decision_authority
  
  escalation_sla_hours INTEGER,
    -- Hours allowed before escalation
    -- Example: 4 hours for CRITICAL
    -- Example: 24 hours for HIGH
  
  escalation_notification TEXT,
    -- Who gets notified on escalation
    -- Example: "P3 Geometry Engineer, Project Manager, Engineering Director"
  
  -- ========== CONSEQUENCES ==========
  blocks_downstream_output BOOLEAN,
    -- TRUE if BLOCK or HOLD
    -- Prevents AB, GA, shop drawing generation
  
  requires_manual_review BOOLEAN,
    -- TRUE for HOLD and WARN
  
  requires_client_approval BOOLEAN,
    -- TRUE if design change must be approved by client
    -- Rare; only for major geometry changes
  
  requires_cad_resubmission BOOLEAN,
    -- TRUE if DXF/CAD must be resubmitted
    -- FALSE if DB can be updated instead
  
  -- ========== NOTIFICATIONS ==========
  notify_p2_engineer BOOLEAN,
  notify_p3_geometry_engineer BOOLEAN,
  notify_project_manager BOOLEAN,
  notify_shop BOOLEAN,
  notify_client BOOLEAN,
  
  -- ========== DOCUMENTATION ==========
  rule_rationale TEXT,
    -- Why this action for this severity/stage combo
    -- Example: "Grid count mismatch at S2 is topology error; must be resolved before generating GA"
  
  approval_authority TEXT,
    -- Who approved this action matrix row
    -- Example: "P3 Geometry Engineer"
  
  approval_date DATE,
  
  effective_date DATE
    -- When action matrix row becomes effective

);

-- Sample insert statements (examples):
/*
INSERT INTO geometry_conflict_action_master VALUES (
  'GCA-001',
  'CRITICAL', 'S2',
  'BLOCK',
  'Grid line count mismatch at design stage; must resolve before proceeding',
  'P3 Geometry Engineer',
  'Engineering Director',
  4,
  'P3 Geometry Engineer, Engineering Director',
  TRUE,
  TRUE,
  FALSE,
  TRUE,
  TRUE, TRUE, TRUE, FALSE, FALSE,
  'Grid topology error prevents any downstream calculation; must identify cause (DXF parse error, incorrect layer config, or drawing geometry error) and resolve',
  'P3 Geometry Engineer',
  CURRENT_DATE,
  CURRENT_DATE
);

INSERT INTO geometry_conflict_action_master VALUES (
  'GCA-002',
  'HIGH', 'S4',
  'BLOCK',
  'Column position error at AB output stage blocks foundation design',
  'P2 Structural Engineer',
  'P3 Geometry Engineer',
  24,
  'P2 Engineer, P3 Geometry Engineer, Shop Lead',
  TRUE,
  TRUE,
  FALSE,
  FALSE,
  TRUE, TRUE, TRUE, TRUE, FALSE,
  'Anchor bolt grid must be accurate for foundation drilling; column position error affects bolt hole coordinates',
  'P3 Geometry Engineer',
  CURRENT_DATE,
  CURRENT_DATE
);
*/

-- ============================================================================
-- SUPPORTING INDEXES
-- ============================================================================

-- Composite indexes for common queries
CREATE INDEX IF NOT EXISTS idx_tol_standard_stage 
  ON geometry_tolerance_master(applicable_design_standards, applicable_stages);

CREATE INDEX IF NOT EXISTS idx_action_sev_stage 
  ON geometry_conflict_action_master(severity, processing_stage);

-- ============================================================================
-- END OF SCHEMA DEFINITION
-- ============================================================================
