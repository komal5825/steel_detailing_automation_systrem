-- PROMPT F: DESIGN STANDARD ROUTING & SECTION GOVERNANCE
-- Database Schema (Production-Ready DDL)
-- Date: April 2026
-- Authority: Engineering Standards & Design Control
-- Status: READY FOR DEPLOYMENT

-- ============================================================================
-- TABLE 1: project_design_standard_master
-- Purpose: Declare which design standard governs each project (immutable)
-- Scope: One row per project; set at project creation
-- ============================================================================

CREATE TABLE project_design_standard_master (
    -- Identity & Reference Keys
    project_id TEXT PRIMARY KEY,  -- Foreign key to projects table
    
    -- Design Standard Declaration
    design_standard TEXT NOT NULL CHECK (design_standard IN ('IS', 'AISC', 'EUROCODE')),
    design_code_version TEXT NOT NULL,  -- e.g., "IS 800:2007", "AISC 360-22", "EN 1993-1-1:2005"
    design_code_effective_date DATETIME NOT NULL,
    
    -- Seismic Design (if applicable)
    seismic_required BOOLEAN NOT NULL DEFAULT FALSE,
    seismic_standard TEXT CHECK (seismic_standard IN ('IS 1893', 'AISC 341', 'EN 1998', NULL)),
    seismic_code_version TEXT,  -- e.g., "IS 1893:2016", "ASCE 7-22", "EN 1998-1:2004+A1:2013"
    seismic_code_effective_date DATETIME,
    seismic_site_classification TEXT,  -- e.g., "Zone II", "D (ASCE 7)", "B (Eurocode)"
    
    -- Approval & Governance
    declared_by_role TEXT NOT NULL CHECK (declared_by_role IN ('P3', 'PM')),
    declared_by_user_name TEXT NOT NULL,
    approved_by_p3_name TEXT,  -- P3 principal engineer approval
    approved_by_p3_timestamp DATETIME,
    
    -- Status & Control
    is_active BOOLEAN NOT NULL DEFAULT TRUE,  -- Can be deactivated for archived projects
    is_locked BOOLEAN NOT NULL DEFAULT TRUE,  -- Immutable after lock
    lock_timestamp DATETIME,
    
    -- Audit Trail
    created_timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_timestamp DATETIME,
    change_log TEXT,  -- JSON: list of changes made
    
    -- Constraints
    CONSTRAINT seismic_logic CHECK (
        (seismic_required = FALSE AND seismic_standard IS NULL)
        OR
        (seismic_required = TRUE AND seismic_standard IS NOT NULL)
    ),
    
    CONSTRAINT valid_seismic_standard_per_design CHECK (
        (design_standard = 'IS' AND seismic_standard IN ('IS 1893', NULL))
        OR
        (design_standard = 'AISC' AND seismic_standard IN ('AISC 341', NULL))
        OR
        (design_standard = 'EUROCODE' AND seismic_standard IN ('EN 1998', NULL))
    )
);

CREATE INDEX idx_project_design_standard ON project_design_standard_master(design_standard);
CREATE INDEX idx_project_seismic_required ON project_design_standard_master(seismic_required);

-- ============================================================================
-- TABLE 2: section_standard_route_master
-- Purpose: Route section lookups to correct database per design standard
-- Scope: Defines routing rules for all section types across all standards
-- ============================================================================

CREATE TABLE section_standard_route_master (
    -- Identity & Keys
    route_id TEXT PRIMARY KEY,  -- Format: ROUTE-{design_standard}-{section_type}
    
    -- Routing Definition
    design_standard TEXT NOT NULL CHECK (design_standard IN ('IS', 'AISC', 'EUROCODE')),
    section_type TEXT NOT NULL CHECK (section_type IN (
        'ROLLED_I_BEAM', 'ROLLED_H_BEAM', 'ROLLED_CHANNEL', 'ROLLED_ANGLE',
        'ROLLED_T_SECTION', 'ROLLED_FLAT_BAR',
        'BUILT_UP_I_SECTION', 'BUILT_UP_BOX_SECTION', 'BUILT_UP_CHANNEL', 'BUILT_UP_TRUSS',
        'COMPOSITE_SECTION', 'COLD_FORMED_SECTION'
    )),
    
    -- Source Database Definition
    source_database TEXT NOT NULL,  -- e.g., "ISC", "ISMB", "W_SHAPE", "UB_EUROCODE"
    lookup_table_name TEXT NOT NULL,  -- Actual table containing section properties
    section_property_keys TEXT NOT NULL,  -- JSON: column names in lookup table
    
    -- Validation Rules
    validation_rule_set_id TEXT,  -- Reference to rules for this route
    max_slenderness_btf DECIMAL(5,2),  -- Maximum b/2tf ratio (compact limit)
    max_slenderness_hw DECIMAL(5,2),  -- Maximum h/tw ratio (plastic limit)
    
    -- Weight Calculation Method
    weight_calculation_method TEXT CHECK (weight_calculation_method IN ('CATALOG', 'GEOMETRY', 'FORMULA')),
    -- CATALOG: Use weight from lookup table
    -- GEOMETRY: Calculate from dimensions (A × density)
    -- FORMULA: Use proprietary formula
    
    -- Special Constraints
    min_flange_thickness_mm DECIMAL(5,2),
    min_web_thickness_mm DECIMAL(5,2),
    material_grade_constraint TEXT,  -- JSON: list of allowed grades for this route
    
    -- Seismic Notes
    seismic_design_notes TEXT,  -- Special requirements if seismic project
    seismic_ductility_class TEXT CHECK (seismic_ductility_class IN ('M', 'H', NULL)),  -- Moderate / High
    
    -- Status
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    effective_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    obsolete_date DATETIME,  -- When this route was retired
    
    -- Approval
    approved_by_p3_name TEXT NOT NULL,
    approved_by_p3_timestamp DATETIME NOT NULL,
    
    -- Documentation
    reference_standard TEXT,  -- e.g., "ISC Catalog 2023", "AISC Steel Manual 16th Ed"
    notes TEXT,
    created_timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_section_route_standard_type ON section_standard_route_master(design_standard, section_type);
CREATE INDEX idx_section_route_active ON section_standard_route_master(is_active);

-- ============================================================================
-- TABLE 3: builtup_section_geometry_master
-- Purpose: Store & validate custom built-up section geometries
-- Scope: Registry of all custom/non-catalog built-up sections
-- ============================================================================

CREATE TABLE builtup_section_geometry_master (
    -- Identity
    buildup_id TEXT PRIMARY KEY,  -- Format: BU-{design_standard}-{hash-of-dims}
    
    -- Basic Properties
    design_standard TEXT NOT NULL CHECK (design_standard IN ('IS', 'AISC', 'EUROCODE')),
    section_type TEXT NOT NULL CHECK (section_type IN (
        'BUILT_UP_I_SECTION', 'BUILT_UP_BOX_SECTION', 'BUILT_UP_CHANNEL', 'BUILT_UP_TRUSS', 'OTHER'
    )),
    section_description TEXT NOT NULL,  -- Human-readable description
    
    -- Flanges
    flange_width_mm DECIMAL(7,1) NOT NULL,  -- b (both flanges assumed equal width)
    flange_thickness_mm DECIMAL(5,2) NOT NULL,  -- tf
    flange_material_grade TEXT NOT NULL,  -- e.g., "IS 250B", "ASTM A36", "S275"
    flange_yield_strength_mpa DECIMAL(5,1) NOT NULL,
    
    -- Web
    web_height_mm DECIMAL(7,1) NOT NULL,  -- h (clear height between flange inner surfaces)
    web_thickness_mm DECIMAL(5,2) NOT NULL,  -- tw
    web_material_grade TEXT NOT NULL,
    web_yield_strength_mpa DECIMAL(5,1) NOT NULL,
    
    -- Fillet (if welded)
    fillet_radius_mm DECIMAL(5,2),  -- r (for welded sections; NULL if bolted/riveted)
    
    -- Connection Details
    connection_type TEXT NOT NULL CHECK (connection_type IN ('WELDED', 'BOLTED', 'RIVETED', 'HYBRID')),
    weld_type TEXT,  -- e.g., "SAW", "GMAW", "E70", "E100" (if welded)
    bolt_type TEXT,  -- e.g., "Grade 8.8", "ASTM F1852" (if bolted)
    bolt_pitch_mm DECIMAL(5,1),  -- (if bolted)
    
    -- Symmetry & Orientation
    is_symmetric BOOLEAN NOT NULL DEFAULT TRUE,  -- Symmetrical about XX and YY axes?
    
    -- Calculated Properties (computed from dimensions)
    calculated_area_cm2 DECIMAL(7,2),  -- A = 2×b×tf + (h-2×r)×tw
    calculated_ixx_cm4 DECIMAL(10,2),  -- Moment of inertia about X-X axis
    calculated_iyy_cm4 DECIMAL(10,2),  -- Moment of inertia about Y-Y axis
    calculated_rxx_mm DECIMAL(5,1),  -- Radius of gyration: √(Ixx/A)
    calculated_ryy_mm DECIMAL(5,1),
    calculated_sx_cm3 DECIMAL(8,2),  -- Section modulus X-X (elastic)
    calculated_sy_cm3 DECIMAL(8,2),
    calculated_weight_kg_per_m DECIMAL(6,2),  -- W = A × 7850 / 1000
    
    -- Slenderness Ratios (critical for design standard compliance)
    btf_ratio DECIMAL(5,2),  -- b/(2×tf) — flange slenderness
    hw_ratio DECIMAL(5,2),  -- h/tw — web slenderness
    
    -- Design Standard Compliance Checks
    is_compact_is BOOLEAN,  -- Per IS 800 compact limits
    is_plastic_is BOOLEAN,  -- Per IS 800 plastic limits
    is_compact_aisc BOOLEAN,  -- Per AISC 360 compact limits
    is_class1_eurocode BOOLEAN,  -- Per Eurocode Class 1 (plastic) limits
    is_class2_eurocode BOOLEAN,  -- Per Eurocode Class 2 (compact) limits
    
    -- Fabrication & Access
    fabrication_notes TEXT,  -- Welding sequence, hole access, tolerances
    access_hole_diameter_mm DECIMAL(5,1),  -- For bolting (if applicable)
    requires_stress_relief BOOLEAN,  -- If welded
    requires_ultrasonic_test BOOLEAN,  -- If high-strength welds
    
    -- Approval Gate
    p2_review_completed DATETIME,  -- P2 geometry validation timestamp
    p2_reviewer_name TEXT,  -- Which P2 engineer reviewed
    p2_approval_notes TEXT,
    
    p3_approval_completed DATETIME,  -- P3 feasibility approval
    p3_approver_name TEXT,
    p3_fabrication_approval_notes TEXT,
    
    pm_final_approval DATETIME,  -- PM sign-off to use in design
    pm_approver_name TEXT,
    
    -- Status & Control
    approval_status TEXT NOT NULL CHECK (approval_status IN ('PENDING', 'APPROVED', 'REJECTED', 'CONDITIONAL')) DEFAULT 'PENDING',
    approval_conditions_text TEXT,  -- If approved conditionally
    is_locked BOOLEAN NOT NULL DEFAULT FALSE,  -- Can't modify after approval
    
    -- Audit Trail
    submitted_by_role TEXT NOT NULL,
    submitted_by_user_name TEXT NOT NULL,
    submitted_timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_timestamp DATETIME,
    
    CONSTRAINT flange_material_must_match_standard CHECK (
        (design_standard = 'IS' AND flange_material_grade LIKE 'IS%')
        OR
        (design_standard = 'AISC' AND flange_material_grade LIKE 'ASTM%')
        OR
        (design_standard = 'EUROCODE' AND flange_material_grade LIKE 'S%')
    )
);

CREATE INDEX idx_buildup_standard ON builtup_section_geometry_master(design_standard);
CREATE INDEX idx_buildup_approval_status ON builtup_section_geometry_master(approval_status);
CREATE INDEX idx_buildup_is_compact_is ON builtup_section_geometry_master(is_compact_is);

-- ============================================================================
-- TABLE 4: nonstandard_section_review_master
-- Purpose: Approval registry for non-standard sections (not in catalogs)
-- Scope: Workflow & audit trail for non-standard section approvals
-- ============================================================================

CREATE TABLE nonstandard_section_review_master (
    -- Identity
    nonstandard_id TEXT PRIMARY KEY,  -- Format: NS-{timestamp}-{seq}
    
    -- Section Definition
    design_standard TEXT NOT NULL CHECK (design_standard IN ('IS', 'AISC', 'EUROCODE')),
    section_description TEXT NOT NULL,  -- Detailed geometry description
    section_category TEXT NOT NULL CHECK (section_category IN (
        'CUSTOM_BUILT_UP', 'COMPOSITE', 'COLD_FORMED', 'HERITAGE', 'ADAPTIVE_REUSE', 'OTHER'
    )),
    
    -- Submission
    submitted_by_role TEXT NOT NULL,
    submitted_by_user_name TEXT NOT NULL,
    submitted_timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    submission_notes TEXT,  -- Why is this non-standard section needed?
    
    -- Workflow Gate 1: Data Quality (DQE/P2)
    dqe_review_completed DATETIME,
    dqe_reviewer_name TEXT,
    dqe_review_notes TEXT,
    dqe_status TEXT CHECK (dqe_status IN ('PENDING', 'PASS', 'BLOCK', NULL)),
    dqe_block_reason TEXT,  -- If blocked
    
    -- Workflow Gate 2: Geometry Validation (P2)
    p2_review_completed DATETIME,
    p2_reviewer_name TEXT NOT NULL,
    p2_approval_status TEXT NOT NULL CHECK (p2_approval_status IN ('PENDING', 'APPROVED', 'HOLD', 'REJECTED')),
    p2_geometry_validated BOOLEAN DEFAULT FALSE,
    p2_slenderness_compliant BOOLEAN,  -- Is it within standard limits?
    p2_notes TEXT,
    p2_review_hours INTEGER,  -- SLA tracking
    
    -- Workflow Gate 3: Feasibility Review (P3)
    p3_review_completed DATETIME,
    p3_reviewer_name TEXT NOT NULL,
    p3_approval_status TEXT NOT NULL CHECK (p3_approval_status IN ('PENDING', 'APPROVED', 'HOLD', 'REJECTED')),
    p3_fabrication_feasible BOOLEAN DEFAULT FALSE,
    p3_code_compliant BOOLEAN DEFAULT FALSE,
    p3_notes TEXT,
    p3_conditions_text TEXT,  -- If approved with conditions
    p3_review_hours INTEGER,
    
    -- Workflow Gate 4: Release Authority (PM)
    pm_approval_completed DATETIME,
    pm_approver_name TEXT,
    pm_approval_status TEXT CHECK (pm_approval_status IN ('PENDING', 'APPROVED', 'REJECTED', NULL)),
    pm_notes TEXT,
    pm_review_hours INTEGER,
    
    -- Overall Status
    overall_approval_status TEXT NOT NULL CHECK (overall_approval_status IN ('PENDING', 'APPROVED', 'REJECTED', 'CONDITIONAL')),
    approval_conditions_text TEXT,  -- If approved conditionally
    rejection_reason TEXT,  -- If rejected
    
    -- SLA & Escalation
    submitted_date_only DATE NOT NULL,  -- For SLA tracking
    dqe_sla_hours INTEGER DEFAULT 4,
    p2_sla_hours INTEGER DEFAULT 24,
    p3_sla_hours INTEGER DEFAULT 24,
    pm_sla_hours INTEGER DEFAULT 24,
    total_review_hours INTEGER,  -- Calculated: sum of all stage hours
    escalated_to_program_lead BOOLEAN DEFAULT FALSE,  -- If SLA exceeded
    escalation_notes TEXT,
    
    -- Storage & Tracking
    section_catalog_entry_id TEXT,  -- If later added to catalog
    storage_location TEXT,  -- Where design documentation stored
    
    -- Audit Trail
    created_timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_timestamp DATETIME,
    change_log TEXT  -- JSON: list of status changes with timestamps
);

CREATE INDEX idx_nonstandard_status ON nonstandard_section_review_master(overall_approval_status);
CREATE INDEX idx_nonstandard_standard ON nonstandard_section_review_master(design_standard);
CREATE INDEX idx_nonstandard_submitted ON nonstandard_section_review_master(submitted_timestamp);

-- ============================================================================
-- TABLE 5: material_grade_mapping_master
-- Purpose: Explicit 1:1 material grade mapping across IS/ASTM/Eurocode
-- Scope: Harmonization table; NO pattern matching allowed
-- ============================================================================

CREATE TABLE material_grade_mapping_master (
    -- Identity
    mapping_id TEXT PRIMARY KEY,  -- Format: MATMAP-{is_grade}-{astm_grade}-{eurocode}
    
    -- Grade Names (exact from standards)
    is_grade TEXT NOT NULL,  -- e.g., "IS 250B", "IS 350A", "IS 500B"
    astm_grade TEXT NOT NULL,  -- e.g., "ASTM A36", "ASTM A992 Grade 50", "ASTM A588 Grade 50"
    eurocode_grade TEXT NOT NULL,  -- e.g., "S235", "S275", "S355", "S450"
    
    -- Material Properties
    yield_strength_mpa DECIMAL(5,1) NOT NULL,  -- fy (MPa)
    tensile_strength_mpa DECIMAL(5,1) NOT NULL,  -- fu (MPa)
    elongation_percent DECIMAL(4,1),  -- Minimum elongation on gauge length
    modulus_of_elasticity_gpa DECIMAL(4,1) NOT NULL DEFAULT 200,  -- E value
    
    -- Equivalence Confidence
    confidence_level TEXT NOT NULL CHECK (confidence_level IN ('EXACT', 'EQUIVALENT', 'APPROXIMATE')),
    -- EXACT: identical mechanical properties
    -- EQUIVALENT: standard industry equivalence
    -- APPROXIMATE: similar but not exact; use with caution
    equivalence_notes TEXT,
    
    -- Application & Grouping
    grade_group TEXT NOT NULL CHECK (grade_group IN ('ECONOMY', 'GENERAL', 'HIGH_STRENGTH', 'VERY_HIGH', 'WEATHERING', 'OTHER')),
    typical_application TEXT,  -- e.g., "General structural", "Seismic design", "Composite decking"
    
    -- Standards Reference
    is_standard_reference TEXT,  -- e.g., "IS 2062:2011"
    astm_standard_reference TEXT,  -- e.g., "ASTM A36/A36M"
    eurocode_standard_reference TEXT,  -- e.g., "EN 10025-2:2004"
    
    -- Approval & Governance
    approved_by_p3_name TEXT NOT NULL,
    approved_by_p3_timestamp DATETIME NOT NULL,
    
    -- Seismic Suitability
    suitable_for_seismic_is BOOLEAN DEFAULT FALSE,  -- Can use in IS 1893 seismic design?
    suitable_for_seismic_aisc BOOLEAN DEFAULT FALSE,  -- Can use in AISC 341 seismic design?
    suitable_for_seismic_eurocode BOOLEAN DEFAULT FALSE,  -- Can use in EN 1998 seismic design?
    
    -- Restrictions
    restrictions_text TEXT,  -- e.g., "Not recommended for cold working", "Limited shape availability"
    availability_note TEXT,  -- Market availability notes
    
    -- Status
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    obsolete_date DATETIME,  -- When this grade was retired
    
    -- Audit Trail
    created_timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_timestamp DATETIME,
    notes TEXT
);

CREATE INDEX idx_material_is_grade ON material_grade_mapping_master(is_grade);
CREATE INDEX idx_material_astm_grade ON material_grade_mapping_master(astm_grade);
CREATE INDEX idx_material_eurocode_grade ON material_grade_mapping_master(eurocode_grade);
CREATE INDEX idx_material_fy ON material_grade_mapping_master(yield_strength_mpa);

-- ============================================================================
-- TABLE 6: seismic_standard_mapping_master
-- Purpose: Seismic code branching & design consequence mapping
-- Scope: Defines seismic design requirements per design standard
-- ============================================================================

CREATE TABLE seismic_standard_mapping_master (
    -- Identity
    seismic_map_id TEXT PRIMARY KEY,  -- Format: SEISMIC-{design_standard}-{seismic_code}
    
    -- Code Declaration
    design_standard TEXT NOT NULL CHECK (design_standard IN ('IS', 'AISC', 'EUROCODE')),
    seismic_code_standard TEXT NOT NULL CHECK (seismic_code_standard IN ('IS 1893', 'AISC 341', 'EN 1998')),
    seismic_code_version TEXT NOT NULL,  -- e.g., "IS 1893:2016", "ASCE 7-22", "EN 1998-1:2004+A1:2013"
    
    -- Response/Behavior Factors
    response_factor_field_name TEXT NOT NULL,  -- "R" (IS), "R or Cd" (AISC), "q" (Eurocode)
    response_factor_default_value DECIMAL(4,1),  -- Typical value (may vary by system)
    response_factor_min DECIMAL(4,1),
    response_factor_max DECIMAL(4,1),
    response_factor_definition TEXT,  -- Explanation of what this factor means
    
    -- Design Method
    design_method TEXT NOT NULL CHECK (design_method IN ('ZONE_BASED', 'ELF', 'RESPONSE_SPECTRUM', 'TIME_HISTORY')),
    -- ZONE_BASED: IS 1893 (zone + importance)
    -- ELF: Equivalent Lateral Force (AISC/ASCE 7)
    -- RESPONSE_SPECTRUM: Elastic/Inelastic spectrum (Eurocode)
    -- TIME_HISTORY: Advanced method (all codes)
    
    -- Ductility & Capacity Design
    ductility_class_required TEXT CHECK (ductility_class_required IN ('M', 'H', 'UNRESTRICTED', NULL)),
    -- M = Moderate (IS 1893 ductility), H = High (Eurocode Class H)
    capacity_design_required BOOLEAN DEFAULT FALSE,  -- Beam-column overstrength?
    
    -- Site-Specific Parameters
    accidental_eccentricity_percent DECIMAL(4,1) DEFAULT 5,  -- Torsional effects
    damping_ratio_percent DECIMAL(4,1) DEFAULT 5,  -- Material damping
    importance_factor_field_name TEXT,  -- "I" (IS), "I" (AISC), "γI" (Eurocode)
    soil_factor_field_name TEXT,  -- "G" (IS), "S" (ASCE 7), "S" (Eurocode)
    
    -- Material Grade Requirements
    material_grade_requirements TEXT,  -- JSON: grades required/restricted for seismic design
    -- Example: {"RESTRICTED": ["IS 500B"], "RECOMMENDED": ["IS 250D", "IS 350A"]}
    material_yield_strength_min_mpa DECIMAL(5,1),  -- Minimum fy for seismic design
    material_yield_strength_max_mpa DECIMAL(5,1),  -- Maximum fy for seismic design
    
    -- Section Class & Slenderness
    section_class_required TEXT,  -- "Compact" (IS), "Special Moment Frame" (AISC), "Class 1-2" (Eurocode)
    max_btf_ratio_seismic DECIMAL(5,2),  -- Maximum flange slenderness for seismic
    max_hw_ratio_seismic DECIMAL(5,2),  -- Maximum web slenderness for seismic
    
    -- Connection & Details
    connection_ductility_requirement TEXT,  -- e.g., "Full Strength", "Partial Strength", "Pinned"
    minimum_bolt_grade_seismic TEXT,  -- e.g., "Grade 8.8", "ASTM F1852"
    weld_requirements_seismic TEXT,  -- e.g., "Complete Joint Penetration", "Fillet weld limits"
    
    -- Gravity Load Factor (Seismic)
    gravity_load_factor DECIMAL(3,2) DEFAULT 1.0,  -- Usually 1.0 (self-weight included)
    
    -- Documentation & Notes
    reference_section_is_1893 TEXT,  -- e.g., "Clause 5.2: Response Reduction Factor"
    reference_section_aisc_341 TEXT,  -- e.g., "Chapter C: Seismic Design Requirements"
    reference_section_en_1998 TEXT,  -- e.g., "Section 6.2: Ductility Classes"
    seismic_design_notes TEXT,  -- Special considerations or gotchas
    
    -- Approval & Status
    approved_by_p3_name TEXT NOT NULL,
    approved_by_p3_timestamp DATETIME NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    
    -- Audit Trail
    created_timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_timestamp DATETIME,
    notes TEXT
);

CREATE INDEX idx_seismic_design_standard ON seismic_standard_mapping_master(design_standard);
CREATE INDEX idx_seismic_code_standard ON seismic_standard_mapping_master(seismic_code_standard);

-- ============================================================================
-- TRIGGERS & VALIDATION
-- ============================================================================

-- TRIGGER: Ensure project_design_standard cannot be modified after lock
-- (Implement in application or via update constraint)

-- TRIGGER: Calculate buildup slenderness ratios automatically
-- TRIGGER: Auto-set buildup approval_status to PENDING on new submission

-- ============================================================================
-- SAMPLE REFERENCE DATA INSERTS
-- ============================================================================

INSERT INTO project_design_standard_master VALUES (
    'PROJ-2026-001', 'IS', 'IS 800:2007', '2026-01-01', 
    FALSE, NULL, NULL, NULL, NULL,
    'P3', 'John Smith', 'John Smith', '2026-01-15',
    TRUE, TRUE, '2026-01-15', CURRENT_TIMESTAMP, NULL, NULL
);

INSERT INTO material_grade_mapping_master VALUES (
    'MATMAP-IS250B-A36-S235', 'IS 250B', 'ASTM A36', 'S235',
    250, 410, 23, 200,
    'EQUIVALENT', 'Same yield strength and tensile ranges',
    'ECONOMY', 'General structural steel', 'IS 2062:2011', 'ASTM A36/A36M', 'EN 10025-2:2004',
    'John Smith', '2026-01-10',
    TRUE, TRUE, TRUE,
    NULL, 'Widely available in all three markets', 
    TRUE, NULL, CURRENT_TIMESTAMP, NULL, NULL
);

-- ============================================================================
-- END OF SCHEMA DEFINITION
-- ============================================================================
