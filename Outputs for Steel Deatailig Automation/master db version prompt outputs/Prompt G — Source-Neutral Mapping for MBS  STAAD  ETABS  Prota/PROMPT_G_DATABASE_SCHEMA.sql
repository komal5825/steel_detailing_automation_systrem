-- PROMPT G: SOURCE-NEUTRAL MAPPING NORMALIZATION LAYER
-- Database Schema (Production-Ready DDL)
-- Date: April 2026
-- Authority: Data Interoperability & Source Mapping Control

-- ============================================================================
-- TABLE 1: source_mapping_registry
-- Purpose: Track which source software & version was used for this data
-- ============================================================================

CREATE TABLE source_mapping_registry (
    mapping_id TEXT PRIMARY KEY,  -- Format: MAP-{timestamp}-{source_software}
    job_id TEXT NOT NULL,
    source_software TEXT NOT NULL CHECK (source_software IN ('MBS', 'STAAD', 'ETABS', 'PROTA')),
    source_file_name TEXT,
    source_export_date DATETIME,
    mapping_timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    mapper_version TEXT,  -- Version of M-MAP-01 through M-MAP-04 that ran
    
    -- Quality Metrics
    total_fields_extracted INTEGER,
    fields_with_high_confidence INTEGER,  -- confidence >= 0.85
    fields_with_medium_confidence INTEGER,  -- 0.70–0.85
    fields_requiring_review INTEGER,  -- < 0.70
    fields_blocked INTEGER,  -- confidence = 0.0
    
    -- Status & Control
    mapping_status TEXT CHECK (mapping_status IN ('SUCCESS', 'PARTIAL', 'FAILED')),
    mapping_notes TEXT,
    approved_by_p3_name TEXT,
    approved_timestamp DATETIME,
    is_locked BOOLEAN DEFAULT FALSE,
    
    created_timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_mapping_job_software ON source_mapping_registry(job_id, source_software);

-- ============================================================================
-- TABLE 2: geometry_normalized
-- Purpose: Software-agnostic member node coordinates
-- ============================================================================

CREATE TABLE geometry_normalized (
    geometry_id TEXT PRIMARY KEY,  -- GEO-{job}-{node_num}
    job_id TEXT NOT NULL,
    mapping_id TEXT NOT NULL,  -- Reference to source_mapping_registry
    source_software TEXT NOT NULL,
    source_node_id TEXT,  -- Original ID from source file
    
    -- Coordinates (Global Reference Frame)
    x_coordinate_m DECIMAL(10,3) NOT NULL,
    y_coordinate_m DECIMAL(10,3) NOT NULL,
    z_coordinate_m DECIMAL(10,3) NOT NULL,
    
    -- Source Tracking
    source_record_id TEXT,
    coordinate_system_is_local BOOLEAN,  -- Did we transform from local?
    coordinate_system_notes TEXT,
    
    -- Quality
    confidence_score DECIMAL(3,2),  -- 0.00–1.00
    extraction_notes TEXT,
    
    created_timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (mapping_id) REFERENCES source_mapping_registry(mapping_id)
);

CREATE INDEX idx_geometry_job_software ON geometry_normalized(job_id, source_software);
CREATE INDEX idx_geometry_confidence ON geometry_normalized(confidence_score);

-- ============================================================================
-- TABLE 3: grid_normalized
-- Purpose: Software-agnostic grid lines (reference axes)
-- ============================================================================

CREATE TABLE grid_normalized (
    grid_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    mapping_id TEXT NOT NULL,
    source_software TEXT NOT NULL,
    source_grid_id TEXT,
    
    -- Grid Definition
    grid_direction TEXT CHECK (grid_direction IN ('X', 'Y', 'Z', 'ROTATED')),
    grid_type TEXT,  -- COLUMN / BEAM / STORY / PARKING / etc.
    grid_coordinates TEXT,  -- JSON array of coordinate values
    
    -- Spacing & Pattern
    is_regular_spacing BOOLEAN,
    spacing_mm DECIMAL(8,2),  -- If regular
    rotation_angle_degrees DECIMAL(5,1),  -- If rotated
    
    -- Quality
    confidence_score DECIMAL(3,2),
    source_record_id TEXT,
    
    created_timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (mapping_id) REFERENCES source_mapping_registry(mapping_id)
);

CREATE INDEX idx_grid_job_type ON grid_normalized(job_id, grid_type);

-- ============================================================================
-- TABLE 4: level_normalized
-- Purpose: Software-agnostic floor/story definitions
-- ============================================================================

CREATE TABLE level_normalized (
    level_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    mapping_id TEXT NOT NULL,
    source_software TEXT NOT NULL,
    source_level_id TEXT,
    
    -- Elevation (Absolute from Datum)
    level_elevation_m DECIMAL(10,3) NOT NULL,
    level_name TEXT,
    level_type TEXT CHECK (level_type IN ('FLOOR', 'MEZZANINE', 'ROOF', 'BASEMENT', 'PENTHOUSE')),
    
    -- Spacing
    floor_height_m DECIMAL(7,3),  -- Distance from previous story
    slab_thickness_m DECIMAL(5,2),
    
    -- Quality
    confidence_score DECIMAL(3,2),
    source_record_id TEXT,
    
    created_timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (mapping_id) REFERENCES source_mapping_registry(mapping_id)
);

CREATE INDEX idx_level_job_elevation ON level_normalized(job_id, level_elevation_m);

-- ============================================================================
-- TABLE 5: section_normalized
-- Purpose: Software-agnostic member cross-section definitions
-- ============================================================================

CREATE TABLE section_normalized (
    section_norm_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    mapping_id TEXT NOT NULL,
    source_software TEXT NOT NULL,
    source_section_id TEXT,
    
    -- Section Identity
    section_type TEXT CHECK (section_type IN ('STANDARD', 'BUILT_UP', 'COMPOSITE', 'SPECIAL')),
    section_name TEXT,
    section_category TEXT,  -- I_BEAM / H_BEAM / CHANNEL / ANGLE / BOX / CUSTOM
    material_grade TEXT,
    
    -- Link to Prompt F
    design_standard_id TEXT,  -- Reference to project_design_standard_master (Prompt F)
    is_approved_nonstandard BOOLEAN,  -- Has this passed Prompt F non-standard approval?
    nonstandard_approval_id TEXT,  -- Reference to nonstandard_section_review_master
    
    -- Quality
    confidence_score DECIMAL(3,2),
    source_record_id TEXT,
    
    created_timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_section_job_category ON section_normalized(job_id, section_category);
CREATE INDEX idx_section_approval ON section_normalized(is_approved_nonstandard);

-- ============================================================================
-- TABLE 6: source_mapping_exceptions
-- Purpose: Track fields that required manual intervention or fallback logic
-- ============================================================================

CREATE TABLE source_mapping_exceptions (
    exception_id TEXT PRIMARY KEY,  -- EXC-{timestamp}-{seq}
    job_id TEXT NOT NULL,
    mapping_id TEXT NOT NULL,
    source_software TEXT NOT NULL,
    
    -- What Was Missing
    field_group TEXT,  -- geometry / grids / levels / sections / anchors / connections / etc.
    field_name TEXT,
    source_record_id TEXT,
    
    -- Why It Happened
    exception_reason TEXT CHECK (exception_reason IN (
        'DATA_MISSING', 'DATA_INCOMPLETE', 'TRANSFORMATION_REQUIRED',
        'CONFIDENCE_TOO_LOW', 'UNSTRUCTURED_TEXT', 'SOFTWARE_LIMITATION'
    )),
    
    -- How It Was Handled
    resolution_method TEXT CHECK (resolution_method IN (
        'BLOCKED', 'FALLBACK_RULE', 'MANUAL_INPUT', 'ESTIMATED', 'INFERRED'
    )),
    resolution_details TEXT,  -- What value was used? Who entered it?
    resolved_by_role TEXT,  -- Engineer, DQE, etc.
    resolved_by_user TEXT,
    resolved_timestamp DATETIME,
    
    -- Quality Impact
    final_confidence_score DECIMAL(3,2),  -- Confidence after resolution
    audit_trail TEXT,  -- JSON: trace of how exception was resolved
    
    created_timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (mapping_id) REFERENCES source_mapping_registry(mapping_id)
);

CREATE INDEX idx_exception_job_field ON source_mapping_exceptions(job_id, field_group);
CREATE INDEX idx_exception_resolved ON source_mapping_exceptions(resolved_timestamp);

-- ============================================================================
-- SAMPLE QUERIES FOR NORMALIZATION VALIDATION
-- ============================================================================

-- Query: Check data quality after normalization
-- SELECT 
--   source_software,
--   COUNT(*) as total_records,
--   COUNT(CASE WHEN confidence_score >= 0.85 THEN 1 END) as high_confidence,
--   COUNT(CASE WHEN confidence_score >= 0.70 AND confidence_score < 0.85 THEN 1 END) as medium_confidence,
--   COUNT(CASE WHEN confidence_score < 0.70 THEN 1 END) as low_confidence,
--   AVG(confidence_score) as avg_confidence
-- FROM geometry_normalized
-- WHERE job_id = ?
-- GROUP BY source_software;

-- Query: Find all fields requiring review
-- SELECT *
-- FROM source_mapping_exceptions
-- WHERE job_id = ? AND resolution_method IN ('MANUAL_INPUT', 'ESTIMATED', 'FALLBACK_RULE')
-- ORDER BY created_timestamp DESC;

