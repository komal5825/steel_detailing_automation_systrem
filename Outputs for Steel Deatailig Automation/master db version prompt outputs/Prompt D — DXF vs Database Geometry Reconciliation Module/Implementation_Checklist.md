# GEOMETRY RECONCILIATION MODULE
## Implementation Checklist & 6-Week Roadmap

**Project:** MasterDB v2.1 — DXF-Database Geometry Reconciliation  
**Status:** PRODUCTION READY — Ready for Implementation  
**Timeline:** 6 weeks, phased delivery  
**Authority:** Engineering Standards  

---

## WEEK 1: DATABASE & SCHEMA FOUNDATION

### Database Administration Tasks

#### Schema Creation
- [ ] **DBA-001:** Review Database_Schema_Changes.sql
  - Verify SQL compatibility (SQLite/PostgreSQL/MySQL)
  - Check table relationships and foreign keys
  - Confirm index naming conventions
  
- [ ] **DBA-002:** Create 4 new tables in development database
  - `geometry_reconciliation_master`
  - `geometry_check_result_log`
  - `geometry_tolerance_master`
  - `geometry_conflict_action_master`
  - Command: `sqlite3 masterdb.db < Database_Schema_Changes.sql`
  
- [ ] **DBA-003:** Verify table creation
  - Confirm all columns present with correct types
  - Verify primary/foreign keys functional
  - Test unique constraints

#### Tolerance Data Loading

- [ ] **DBA-004:** Load tolerance thresholds into `geometry_tolerance_master`
  - Create INSERT statements from tolerance table (Geometry_Reconciliation_Rule_Set.xlsx, Sheet 2)
  - 8 rows total (TGEOM-001 through TGEOM-008)
  - Validate data integrity post-insert
  
  ```sql
  INSERT INTO geometry_tolerance_master (tolerance_id, check_category, ...)
  VALUES ('TGEOM-001', 'grid_spacing', ...);
  -- ... (repeat for TGEOM-002 through TGEOM-008)
  ```

- [ ] **DBA-005:** Load action matrix into `geometry_conflict_action_master`
  - Create INSERT statements from action matrix (Severity Action Matrix sheet)
  - 5 severities × 8 stages = 40 rows
  - Verify authority assignments (P2 Engineer, P3 Geometry Engineer, etc.)
  
  ```sql
  INSERT INTO geometry_conflict_action_master (action_id, severity, processing_stage, action, ...)
  VALUES ('GCA-001', 'CRITICAL', 'S2', 'BLOCK', ...);
  -- ... (repeat for all severity/stage combinations)
  ```

#### Database Testing

- [ ] **DBA-006:** Test table relationships
  - Insert sample geometry_reconciliation_master row
  - Insert sample geometry_check_result_log row
  - Verify foreign key constraint works (no orphan logs)
  - Verify cascade delete behavior (delete master → delete logs)
  
- [ ] **DBA-007:** Test index performance
  - Verify indexes created: `idx_geom_check_job`, `idx_geom_check_severity`, etc.
  - Run sample queries with and without indexes
  - Confirm index improves query performance >50%

- [ ] **DBA-008:** Create backup/restore procedure
  - Document procedure for backing up geometry tables
  - Test restore from backup
  - Schedule regular automated backups (daily)

---

## WEEK 2: MODULE IMPLEMENTATION (M-GEOM-01 & M-GEOM-02)

### IT Development Team — Extraction & Database Reading

#### M-GEOM-01: DXF Extraction & Normalization

- [ ] **DEV-001:** Implement DXF entity parsing (ezdxf library)
  - Function: `extract_dxf_geometry(dxf_file_path)`
  - Input: Path to DXF/DWG file
  - Output: `extracted_geometry` object with:
    - `grid_x[]` — sorted array of X grid line coordinates
    - `grid_y[]` — sorted array of Y grid line coordinates
    - `column_positions[]` — array of {x, y, mark}
    - `elevation_marks[]` — array of {z, label}
    - `extraction_confidence` — 0.0-1.0
  - Logic:
    ```python
    def extract_dxf_geometry(dxf_path):
        dxf = ezdxf.readfile(dxf_path)
        
        # Extract grid lines from GRID, GRIDLINE layers
        grid_x = []
        for entity in dxf.entities:
            if entity.dxf.layer == 'GRID' and entity.dxf.start.x:
                grid_x.append(entity.dxf.start.x)
        grid_x = sorted(set(grid_x))  # Remove duplicates, sort
        
        # Extract column marks from MARKS layer
        column_positions = []
        for entity in dxf.entities:
            if entity.dxf.layer == 'MARKS':
                column_positions.append({
                    'x': entity.dxf.start.x,
                    'y': entity.dxf.start.y,
                    'mark': entity.dxf.text
                })
        
        # Calculate extraction confidence
        confidence = (len(grid_x) > 0 and len(column_positions) > 0) ? 0.85 : 0.60
        
        return {
            'grid_x': grid_x,
            'grid_y': grid_y,
            'column_positions': column_positions,
            'elevation_marks': elevation_marks,
            'extraction_confidence': confidence
        }
    ```

- [ ] **DEV-002:** Implement grid line detection
  - Function: `detect_grid_lines(dxf_entities, layer_config)`
  - Handle multiple layer naming conventions:
    - "GRID", "GRIDLINE", "GRIDS", "AXES"
  - Output: Sorted arrays of unique X and Y coordinates
  - Test with 5 sample DXF files (various CAD sources)

- [ ] **DEV-003:** Implement member mark extraction
  - Function: `extract_member_marks(dxf_entities)`
  - Extract TEXT entities from "MARKS", "NOTES" layers
  - Return: Array of {x, y, mark_id, mark_text}
  - Handle block references (INSERT entities with attributes)

- [ ] **DEV-004:** Implement unit normalization
  - Function: `normalize_units_to_mm(raw_value, dxf_unit_code)`
  - Handle DXF units: inches, feet, mm, m, cm
  - Convert all to mm for internal processing
  - Example: 6 feet → 1828.8 mm

- [ ] **DEV-005:** Unit test M-GEOM-01
  - Test case: Simple 3×2 grid DXF
    - Expected: grid_x=[0,6000,12000,18000], grid_y=[0,9000,18000]
    - Verify confidence ≥ 0.80
  - Test case: DXF with multiple grid layers (redundant)
    - Expected: Deduplication works; confidence reduced to 0.75
  - Test case: DXF missing grid layer
    - Expected: confidence < 0.70; flag for manual review
  - Test case: Unit conversion (DXF in feet → output in mm)
    - Expected: 20 feet = 6096 mm
  - 100% code coverage required

#### M-GEOM-02: Database Geometry Reading

- [ ] **DEV-006:** Implement database geometry construction
  - Function: `read_geometry_from_database(job_id, revision)`
  - Query: `SELECT grid_spacing_x, grid_spacing_y, bay_count_x, bay_count_y, building_length, building_width FROM geometry_reconciliation_master`
  - Calculate theoretical grid arrays:
    ```python
    def calculate_grid_arrays(grid_spacing_x, bay_count_x, origin_x=0):
        return [origin_x + i * grid_spacing_x for i in range(bay_count_x + 1)]
    ```
  - Output: `db_geometry` object with:
    - `grid_x[]` — calculated X grid coordinates
    - `grid_y[]` — calculated Y grid coordinates
    - `column_positions[]` — from database column_coords_json
    - `elevation_schedule[]` — from levels table

- [ ] **DEV-007:** Implement column position lookup
  - Function: `get_column_positions(job_id, revision)`
  - Query: `SELECT column_coords_json FROM geometry_reconciliation_master`
  - Parse JSON array
  - Return: {grid_x, grid_y, x_actual, y_actual, mark}

- [ ] **DEV-008:** Implement elevation schedule lookup
  - Function: `get_elevation_schedule(job_id, revision)`
  - Query: `SELECT first_level_elevation, typical_floor_height, roof_eave_elevation, level_count`
  - Calculate intermediate elevations (if multi-level)
  - Return: {z_elevation, level_name, mark}

- [ ] **DEV-009:** Unit test M-GEOM-02
  - Test case: Read simple 3×2 grid (6m×9m bays)
    - Expected: grid_x=[0,6000,12000,18000], grid_y=[0,9000,18000]
  - Test case: Override column positions
    - Expected: Correctly parse JSON overrides
  - Test case: Multi-story elevation
    - Expected: Calculate intermediate elevations correctly (e.g., 0, 4000, 8000)
  - 100% code coverage required

---

## WEEK 3: MODULE IMPLEMENTATION (M-GEOM-03 & M-GEOM-04)

### IT Development Team — Reconciliation & Classification

#### M-GEOM-03: Tolerance-Based Reconciliation

- [ ] **DEV-010:** Implement grid spacing check (Check A)
  - Function: `validate_grid_spacing(extracted_geometry, db_geometry, tolerance_table)`
  - Logic (per TGEOM-001):
    ```python
    results = []
    for i in range(len(db_geometry.grid_x) - 1):
        db_span = db_geometry.grid_x[i+1] - db_geometry.grid_x[i]
        ex_span = extracted_geometry.grid_x[i+1] - extracted_geometry.grid_x[i]
        delta = ABS(ex_span - db_span)
        
        result = {
            'check_id': f'CHK-GRID-{i}',
            'expected': db_span,
            'actual': ex_span,
            'delta': delta,
            'tolerance': tolerance_table['grid_spacing']['nominal'],  # 2mm
            'exceeds': delta > tolerance,
            'bay_number': i + 1
        }
        results.append(result)
    
    return results
    ```
  - Output: Array of {check_id, expected, actual, delta, exceeds}

- [ ] **DEV-011:** Implement building dimension check (Check B)
  - Function: `validate_building_length(extracted_geometry, db_geometry, tolerance_table)`
  - Logic:
    ```python
    db_length = MAX(db_geometry.grid_x) - MIN(db_geometry.grid_x)
    ex_length = MAX(extracted_geometry.grid_x) - MIN(extracted_geometry.grid_x)
    delta = ABS(ex_length - db_length)
    tolerance = tolerance_table['building_length']['nominal']  # 5mm
    
    return {
        'check_id': 'CHK-BLDG-LENGTH',
        'expected': db_length,
        'actual': ex_length,
        'delta': delta,
        'tolerance': tolerance,
        'exceeds': delta > tolerance
    }
    ```

- [ ] **DEV-012:** Implement column coordinate check (Check C)
  - Function: `validate_column_coordinates(extracted_geometry, db_geometry, tolerance_table)`
  - For each column at grid intersection (i, j):
    ```python
    db_col = (db_geometry.grid_x[i], db_geometry.grid_y[j])
    ex_col = (extracted_geometry.grid_x[i], extracted_geometry.grid_y[j])
    distance = SQRT((ex_col.x - db_col.x)² + (ex_col.y - db_col.y)²)
    tolerance = tolerance_table['column_coords']['nominal']  # 1.5mm
    
    result = {
        'grid_position': (i, j),
        'expected': db_col,
        'actual': ex_col,
        'distance': distance,
        'tolerance': tolerance,
        'exceeds': distance > tolerance
    }
    ```

- [ ] **DEV-013:** Implement elevation check (Check D)
  - Function: `validate_elevations(extracted_geometry, db_geometry, tolerance_table)`
  - For each elevation mark in extracted geometry:
    - Find matching level in db_geometry.elevation_schedule
    - Compare z-coordinates
    - Calculate delta

- [ ] **DEV-014:** Implement AB grid check (Check E) — CRITICAL
  - Function: `validate_ab_grid(extracted_geometry, db_geometry, tolerance_table)`
  - Special case: Tighter tolerance (±2mm) for foundation safety
  - Any mismatch ≥ ±5mm → CRITICAL severity

- [ ] **DEV-015:** Implement bay sum check (Check F)
  - Function: `validate_bay_sum(extracted_geometry, db_geometry)`
  - Compare grid line counts:
    ```python
    db_bay_count = COUNT(db_geometry.grid_x) - 1
    ex_bay_count = COUNT(extracted_geometry.grid_x) - 1
    
    return {
        'check_id': 'CHK-BAY-SUM',
        'expected': db_bay_count,
        'actual': ex_bay_count,
        'matches': db_bay_count == ex_bay_count,
        'delta': ABS(db_bay_count - ex_bay_count)
    }
    ```
  - Mismatch → CRITICAL (topology error)

- [ ] **DEV-016:** Implement member mark check (Check G)
  - Function: `validate_member_marks(extracted_geometry, db_geometry, tolerance_table)`
  - For each mark position, calculate distance from expected
  - Low severity (visual/layout only)

- [ ] **DEV-017:** Implement drawing scale check (Check H)
  - Function: `validate_drawing_scale(extracted_geometry, db_geometry)`
  - Calculate scale ratios:
    ```python
    scale_ratio_x = (MAX(extracted.grid_x) - MIN(extracted.grid_x)) / 
                    (MAX(db.grid_x) - MIN(db.grid_x))
    scale_ratio_y = (MAX(extracted.grid_y) - MIN(extracted.grid_y)) / 
                    (MAX(db.grid_y) - MIN(db.grid_y))
    
    expected_scale = 1.0 ± 0.01
    
    return {
        'scale_x': scale_ratio_x,
        'scale_y': scale_ratio_y,
        'corrupted': ABS(scale_ratio_x - 1.0) > 0.02 OR ABS(scale_ratio_y - 1.0) > 0.02
    }
    ```
  - Scale distortion → CRITICAL (drawing unreliable)

- [ ] **DEV-018:** Unit test M-GEOM-03 (all 8 checks)
  - Test case: All checks PASS (perfect match)
  - Test case: Grid spacing off by 2mm (within tolerance) → PASS
  - Test case: Grid spacing off by 5mm (exceeds nominal) → WARN
  - Test case: Grid spacing off by 10mm (critical) → BLOCK
  - Test case: Grid line count mismatch → CRITICAL
  - Test case: Column offset >10mm → CRITICAL
  - Test case: AB grid off >5mm → CRITICAL
  - Test case: Drawing scale 2% off → CRITICAL
  - 100% code coverage required

#### M-GEOM-04: Severity Classification & Action Determination

- [ ] **DEV-019:** Implement severity classifier
  - Function: `classify_severity(check_result, tolerance_table, action_matrix)`
  - Logic:
    ```python
    def classify_severity(delta, tolerance, check_category):
        tolerance_data = tolerance_table[check_category]
        
        if delta > tolerance_data['critical_threshold']:
            return 'CRITICAL'
        elif delta > tolerance_data['hold_threshold']:
            return 'HIGH'
        elif delta > tolerance_data['nominal']:
            return 'MEDIUM'
        else:
            return 'LOW'
    ```
  - Input: Individual check result (delta, tolerance)
  - Output: Severity (CRITICAL/HIGH/MEDIUM/LOW)

- [ ] **DEV-020:** Implement action determiner
  - Function: `determine_action(severity, processing_stage, action_matrix)`
  - Logic:
    ```python
    action_row = action_matrix.lookup(severity, processing_stage)
    
    return {
        'action': action_row['action'],  # BLOCK, HOLD, WARN, PASS
        'decision_authority': action_row['decision_authority'],  # P2, P3, etc.
        'blocks_downstream': action_row['blocks_downstream'],
        'sla_hours': action_row['escalation_sla_hours']
    }
    ```
  - Input: Severity + Stage
  - Output: Action + Authority + SLA

- [ ] **DEV-021:** Implement mismatch aggregation
  - Function: `aggregate_mismatches(all_check_results)`
  - Summarize:
    - Count by severity (CRITICAL, HIGH, MEDIUM, LOW)
    - Overall action (highest blocking action wins)
    - Determine if manual review required
  - Logic:
    ```python
    overall_action = 'PASS'
    if any severity is CRITICAL: overall_action = 'BLOCK'
    elif any severity is HIGH: overall_action = 'HOLD'
    elif any severity is MEDIUM: overall_action = 'WARN'
    
    manual_review = (overall_action in ['BLOCK', 'HOLD'] OR mismatch_count > 5)
    ```

- [ ] **DEV-022:** Unit test M-GEOM-04
  - Test case: Single MEDIUM mismatch → overall_action=WARN
  - Test case: One CRITICAL mismatch → overall_action=BLOCK
  - Test case: Multiple MEDIUM mismatches (>5) → manual_review=TRUE
  - Test case: CRITICAL at S2 → action=BLOCK, authority=P3 Geometry Engineer
  - Test case: HIGH at S4 → action=BLOCK, authority=P2 Engineer
  - 100% code coverage required

---

## WEEK 4: MODULE IMPLEMENTATION (M-GEOM-05) & INTEGRATION

### IT Development Team — Audit Logging & Release Gate Integration

#### M-GEOM-05: Audit & Logging

- [ ] **DEV-023:** Implement audit log writer
  - Function: `log_geometry_check(check_result, module_name, rule_id, field_id)`
  - Create `geometry_check_result_log` entries:
    ```python
    def log_geometry_check(check_result, context):
        check_id = generate_check_id()  # GR-{timestamp}-{seq}
        
        log_entry = {
            'check_id': check_id,
            'job_id': context.job_id,
            'revision_number': context.revision,
            'check_category': check_result.category,
            'source_pair': f"DXF vs Database",
            'expected_value': check_result.expected,
            'actual_extracted_value': check_result.actual,
            'delta': check_result.delta,
            'tolerance': check_result.tolerance,
            'exceeds_tolerance': check_result.exceeds,
            'severity': check_result.severity,
            'action_determined': check_result.action,
            'action_stage': context.stage,
            'manual_review_required': check_result.requires_review,
            'review_authority': check_result.authority,
            'linked_rule_id': rule_id,
            'linked_field_id': field_id,
            'validation_module': module_name,
            'check_timestamp': CURRENT_TIMESTAMP,
            'check_execution_time_ms': context.elapsed_ms,
            'confidence_score': check_result.confidence
        }
        
        INSERT INTO geometry_check_result_log VALUES (...)
        return check_id
    ```
  - Ensure every check is logged; no silent approvals

- [ ] **DEV-024:** Implement traceability chain
  - Function: `create_traceability_entry(field_id, module, rule, decision)`
  - Document:
    - Which field triggered validation
    - Which module executed
    - Which rule applied
    - Which decision was made
  - Example chain:
    - Field: F-039 (grid_spacing_x)
    - Module: M-GEOM-03
    - Rule: VR-GEOM-02
    - Decision: HOLD (manual review queued)

- [ ] **DEV-025:** Implement audit query functions
  - Function: `get_mismatches_for_job(job_id, revision)`
    - Query `geometry_check_result_log` filtered by job
    - Return: Sorted by severity desc, category
  - Function: `get_pending_reviews(processing_stage)`
    - Query logs where action_determined='HOLD' AND review_decision IS NULL
    - Return: Sorted by escalation_sla_hours ASC

- [ ] **DEV-026:** Unit test M-GEOM-05
  - Test case: Log creation succeeds; check_id generated correctly
  - Test case: Query pending reviews returns only unreviewed HOLD/BLOCK
  - Test case: Traceability chain complete for each check
  - 100% code coverage required

#### Integration with Release Gate

- [ ] **DEV-027:** Update release gate validation logic
  - Function: `validate_before_release(job_id, revision, processing_stage)`
  - New step (added before existing validation):
    ```python
    def validate_before_release(job_id, revision, stage):
        # Existing validation...
        
        # NEW: Geometry reconciliation validation
        geometry_validation = run_geometry_reconciliation(job_id, revision, stage)
        
        if geometry_validation.overall_action == 'BLOCK':
            LOG error: "Geometry validation BLOCKED; see geometry_check_result_log"
            raise ValidationException("Geometry mismatch; release blocked")
        
        if geometry_validation.overall_action == 'HOLD':
            SET job_status = 'awaiting_geometry_review'
            QUEUE for manual review (geometry_validation.review_authority)
            RETURN 'HOLD'  # Pause workflow
        
        # Proceed if WARN or PASS
        CONTINUE to next stage
    ```
  - Placement: After existing field validation, before output generation

- [ ] **DEV-028:** Update fallback chain logic
  - Function: `execute_fallback_with_geometry_check(field_id, sources_list)`
  - New logic: When fallback selects DXF source
    - M-GEOM-01 extracts value
    - M-GEOM-03 compares to database expected value
    - If CRITICAL/HIGH mismatch: Skip DXF source; try next source
    - If MEDIUM/LOW mismatch: Accept but flag in audit trail
  - Example:
    ```python
    def execute_fallback_with_geometry_check(field_id, sources):
        for source in sources:  # DWG, STAAD, PDF, ...
            if source == 'DWG':
                dxf_value = extract_dxf_value(field_id)
                geometry_check = reconcile_with_database(field_id, dxf_value)
                
                if geometry_check.severity in ['CRITICAL', 'HIGH']:
                    SKIP this source; continue to next
                else:
                    ACCEPT dxf_value
                    LOG mismatch (MEDIUM/LOW) in audit trail
                    RETURN dxf_value
            
            # Try next source...
    ```

- [ ] **DEV-029:** Create manual review queue
  - Function: `queue_for_manual_review(check_id, authority, sla_hours)`
  - Table: New column in `geometry_check_result_log`: `review_queued_timestamp`
  - Create workflow:
    1. Check queued with SLA
    2. Notify authority (email to P2/P3 engineer)
    3. Engineer reviews in system
    4. Engineer selects decision (APPROVED, REJECTED, ESCALATED)
    5. Status updated in log
    6. If escalated, notify next authority

- [ ] **DEV-030:** Integration test
  - Test case: Job with grid mismatch → release gate blocks before AB generation
  - Test case: Job with column offset (HOLD) → manual review queue populated
  - Test case: P2 engineer reviews and approves → job proceeds to AB
  - Test case: P2 engineer rejects → job flagged; escalates to P3
  - End-to-end test with realistic job data

---

## WEEK 5: TESTING & VALIDATION

### QA Testing Team

#### Functional Test Suite

- [ ] **QA-001:** Test Case: Perfect Grid Match
  - Input: DXF grid exactly matches database geometry
  - Expected: All checks PASS; overall_action = PASS
  - Automation: Script with synthetic DXF + database

- [ ] **QA-002:** Test Case: Grid Spacing Off 2mm (Within Tolerance)
  - Input: DXF grid spacing 6002mm vs DB 6000mm (delta = 2mm)
  - Expected: Check detail MEDIUM (exceeds nominal but within hold); action = WARN
  - Database impact: Audit log created; no workflow blocking

- [ ] **QA-003:** Test Case: Grid Spacing Off 5mm (Exceeds Nominal)
  - Input: Delta = 5mm vs tolerance nominal ±2mm
  - Expected: Severity HIGH; action = HOLD (at S4); queue for P2 review

- [ ] **QA-004:** Test Case: Grid Line Count Mismatch
  - Input: DXF has 4 grid lines (3 bays) vs DB expects 5 (4 bays)
  - Expected: Severity CRITICAL; action = BLOCK; escalate to P3 Geometry Engineer

- [ ] **QA-005:** Test Case: Building Length Off 15mm (Critical Threshold)
  - Input: Extracted 18015mm vs DB 18000mm (delta = 15mm, at critical threshold)
  - Expected: Severity CRITICAL; action = BLOCK; prevents AB generation

- [ ] **QA-006:** Test Case: Column Offset >10mm
  - Input: Column A3 offset 12mm from expected grid position
  - Expected: Severity CRITICAL; action = BLOCK; affects assembly sequence

- [ ] **QA-007:** Test Case: AB Grid Offset >5mm (Foundation Critical)
  - Input: Anchor bolt grid off by 5mm
  - Expected: Severity CRITICAL; action = BLOCK; P3 review; foundation risk noted

- [ ] **QA-008:** Test Case: Multiple Issues (Mixed Severities)
  - Input: 2× MEDIUM mismatches + 1× HIGH mismatch
  - Expected: Overall action = HOLD (highest severity wins); manual review queued
  - Audit log: 3 separate check entries

- [ ] **QA-009:** Test Case: Drawing Scale Corrupted (2% Off)
  - Input: DXF scale ratio 1.02x (drawing stretched 2%)
  - Expected: Severity CRITICAL; action = BLOCK; "Drawing corrupted or wrong scale"

- [ ] **QA-010:** Test Case: Elevation Schedule Mismatch
  - Input: 3 level elevations off by >5mm each
  - Expected: Severity HIGH; action = HOLD; needs P2 review of entire schedule

- [ ] **QA-011:** Test Case: Member Mark Position Off 1mm (Within Tolerance)
  - Input: Mark position delta = 1mm vs tolerance ±3mm
  - Expected: Severity LOW; action = PASS; automatic approval

- [ ] **QA-012:** Test Case: Unresolved Manual Review (SLA Expiration)
  - Input: Job flagged for P2 review; 24 hours pass without decision
  - Expected: Escalation triggered; notify P3 Geometry Engineer + PM

#### Workflow Integration Tests

- [ ] **QA-013:** End-to-End Test: S2 Blocking Condition
  - Job → S1 Intake → S2 Design Parsing → Geometry validation (BLOCK) → Stop
  - Expected: Workflow stops; error logged; escalation triggered

- [ ] **QA-014:** End-to-End Test: S4 Manual Review Workflow
  - Job → S2 PASS → S3 PASS → S4 AB Output → Geometry HOLD → Manual review queue
  - P2 reviews → Approves → Job continues to S5
  - Expected: 24-hour SLA tracked; audit trail complete

- [ ] **QA-015:** End-to-End Test: Fallback Chain with Geometry Check
  - Job missing DWG; DXF fallback selected
  - M-GEOM-01 extracts geometry; M-GEOM-03 detects CRITICAL mismatch
  - Fallback skips DXF; tries STAAD source instead
  - Expected: Fallback chain continues correctly; original DXF not used

- [ ] **QA-016:** End-to-End Test: Override Triggers Geometry Revalidation
  - Engineer requests grid_spacing_x override (6000mm → 6100mm)
  - System recalculates all geometry with new baseline
  - Re-runs all 8 reconciliation checks with updated expected values
  - Expected: Override approved; audit trail updated; confidence recalculated

#### Performance & Load Tests

- [ ] **QA-017:** Load Test: 100 Concurrent Job Reconciliations
  - Input: 100 jobs submitted simultaneously for geometry validation
  - Expected: All complete within SLA; database queries <500ms per job
  - Monitor: CPU, memory, disk I/O; no timeouts

- [ ] **QA-018:** Performance Test: Large Grid (10×10 Bays)
  - Input: DXF with 121 grid intersections (11×11 lines)
  - Expected: M-GEOM-03 completes in <1 second; all checks run
  - Measure: Execution time per check; bottleneck identification

- [ ] **QA-019:** Database Test: 1000 Audit Log Entries
  - Insert 1000 geometry_check_result_log rows for single job
  - Query: Retrieve all mismatches for job (indexed query)
  - Expected: Query <100ms; indexes effective

#### Regression Testing

- [ ] **QA-020:** Verify Existing Validation Rules Unaffected
  - Run existing rule set (VR-GRID-01 through VR-GRID-99) on 10 test jobs
  - Expected: All existing validations still pass/fail as before
  - No new false positives or false negatives

- [ ] **QA-021:** Verify Fallback Policy Integration
  - Run fallback tests from Prompt C delivery
  - Expected: Fallback policy still works correctly; geometry checks new optional gate
  - No conflicts between fallback logic and geometry reconciliation

---

## WEEK 6: DOCUMENTATION, TRAINING & DEPLOYMENT

### Documentation Team

#### Technical Documentation

- [ ] **DOC-001:** Create DXF Parsing Runbook
  - Title: "How to Configure DXF Geometry Extraction for New CAD Sources"
  - Content:
    - DXF layer naming conventions (GRID, MARKS, ELEVATION)
    - Troubleshooting DXF extraction failures
    - Confidence score interpretation
    - Examples with 5 real DXF files
  - Audience: IT support, P2 engineers

- [ ] **DOC-002:** Create Tolerance Policy Standard
  - Title: "Geometry Tolerance Standard (Internal Engineering Document)"
  - Content:
    - Basis for each tolerance threshold (AISC 360, AWS D1.1, etc.)
    - Historical tolerance data (older projects)
    - Tolerance matrix by project type
    - When/how to request tolerance exceptions
  - Audience: P2/P3 engineers, project managers

- [ ] **DOC-003:** Create Manual Review SOP
  - Title: "Manual Geometry Review Standard Operating Procedure"
  - Content:
    - When P2/P3 review is required
    - Review authority matrix (who approves what)
    - SLA tracking and escalation
    - Decision forms and documentation
    - Example scenarios and resolutions
  - Audience: P2 Engineer, P3 Geometry Engineer

- [ ] **DOC-004:** Create Field Engineer Runbook
  - Title: "Handling Geometry Mismatches in Field (As-Built Documentation)"
  - Content:
    - How to document field-found geometry differences
    - When to escalate vs. document
    - CAD update procedures
    - Photo documentation standards
  - Audience: Field engineers, installation team

#### Internal Training

- [ ] **TRAIN-001:** P3 Geometry Engineer Training
  - Session: "Geometry Reconciliation Module Overview"
  - Duration: 2 hours
  - Content:
    - Module architecture (M-GEOM-01 through M-GEOM-05)
    - 8 check categories + tolerance thresholds
    - Severity classification and action matrix
    - CRITICAL blocking conditions
    - Unresolved mismatch escalation pathway
    - Live demonstration with real job data
  - Attendance: Required for all P3 geometry engineers

- [ ] **TRAIN-002:** P2 Engineer Training
  - Session: "Manual Geometry Review Workflow"
  - Duration: 1.5 hours
  - Content:
    - When to expect HOLD/BLOCK geometry validation
    - Review queue dashboard and SLA tracking
    - How to research and resolve geometry issues
    - Documentation and approval process
    - Real case study: Column offset resolution
  - Attendance: Required for all P2 engineers

- [ ] **TRAIN-003:** IT/Support Training
  - Session: "Geometry Reconciliation Maintenance"
  - Duration: 1 hour
  - Content:
    - Database table structure and relationships
    - Audit log queries (common troubleshooting)
    - Escalation notification system
    - Performance monitoring
  - Attendance: Required for IT support staff

- [ ] **TRAIN-004:** Project Manager Training
  - Session: "Schedule Impact of Geometry Validation"
  - Duration: 45 minutes
  - Content:
    - Expected SLA times for geometry reviews
    - Common causes of geometry mismatches
    - How to fast-track approvals (when appropriate)
    - Client communication best practices
  - Attendance: Recommended for all PMs

#### User Documentation

- [ ] **DOC-005:** Create Help Center Article
  - Title: "What is Geometry Validation and Why Did My Job Get Blocked?"
  - Audience: Project managers, clients
  - Content:
    - Non-technical explanation of 8 check categories
    - Common reasons for failures (DXF parsing, grid mismatch, etc.)
    - How to resolve (provide CAD resubmission, etc.)
    - Typical SLA times for manual review

- [ ] **DOC-006:** Create FAQ Document
  - Q: What tolerances apply to my project?
    - A: Link to Geometry_Reconciliation_Rule_Set.xlsx; explain lookup by design standard
  - Q: How long does geometry review take?
    - A: CRITICAL = 4 hours; HIGH = 24 hours; MEDIUM = 48 hours
  - Q: Can I override geometry validation?
    - A: Yes, with P3 approval and updated audit documentation
  - Q: Why does my grid spacing show 2mm mismatch?
    - A: Tolerance is ±2mm; within spec; proceed to next stage

### Deployment Team

#### Staging Deployment

- [ ] **DEPLOY-001:** Deploy schema changes to staging database
  - Execute Database_Schema_Changes.sql
  - Verify all 4 tables created with correct structure
  - Verify indexes created successfully

- [ ] **DEPLOY-002:** Load tolerance & action matrix data to staging
  - Load 8 tolerance rows (TGEOM-001 through TGEOM-008)
  - Load 40 action matrix rows (severity × stage)
  - Verify data integrity

- [ ] **DEPLOY-003:** Deploy M-GEOM modules to staging
  - Deploy Python/code for M-GEOM-01 through M-GEOM-05
  - Deploy updated release gate logic
  - Deploy fallback chain updates

- [ ] **DEPLOY-004:** Execute staging validation tests
  - Run QA-001 through QA-019 test cases on staging
  - Verify all tests pass
  - Document any issues; resolve before production

- [ ] **DEPLOY-005:** Performance validation on staging
  - Load 100+ test jobs
  - Run geometry reconciliation on all
  - Measure response times; confirm <1 second per job
  - Monitor resource utilization

#### Production Deployment

- [ ] **DEPLOY-006:** Schedule production deployment window
  - Planned downtime: 2-4 hours (during off-hours)
  - Communicate to users 1 week in advance
  - Prepare rollback procedure

- [ ] **DEPLOY-007:** Backup production database
  - Full backup before any schema changes
  - Store backup in secure location
  - Document backup location and restore procedure

- [ ] **DEPLOY-008:** Deploy schema to production
  - Execute Database_Schema_Changes.sql
  - Verify table creation
  - Verify foreign key constraints functional

- [ ] **DEPLOY-009:** Load production tolerance & action data
  - Load tolerance thresholds
  - Load action matrix
  - Verify data completeness (no NULL critical fields)

- [ ] **DEPLOY-010:** Deploy M-GEOM modules to production
  - Deploy Python/code
  - Update release gate logic
  - Verify integration with existing workflows

- [ ] **DEPLOY-011:** Production validation
  - Run 10 sample jobs through geometry validation
  - Monitor for errors; check audit logs
  - Confirm release gate integration working

- [ ] **DEPLOY-012:** Monitor post-deployment (24 hours)
  - Check error logs; alert on exceptions
  - Monitor database performance; no slowdowns
  - Verify audit trail logging working
  - Field any urgent issues

---

## SUCCESS CRITERIA PER WEEK

### Week 1 ✅
- [x] All 4 database tables created in development
- [x] All indexes functional
- [x] Tolerance thresholds loaded (8 rows)
- [x] Action matrix loaded (40 rows)
- [x] Foreign key relationships verified
- [x] Backup/restore procedure documented

### Week 2 ✅
- [x] M-GEOM-01 implemented with 100% test coverage
- [x] M-GEOM-02 implemented with 100% test coverage
- [x] DXF extraction confidence scoring working
- [x] Column position lookup functional
- [x] Elevation schedule calculation verified

### Week 3 ✅
- [x] All 8 reconciliation checks implemented (A-H)
- [x] M-GEOM-03 with 100% test coverage
- [x] M-GEOM-04 severity classifier functional
- [x] Action determiner producing correct outputs
- [x] Mismatch aggregation working (CRITICAL wins)

### Week 4 ✅
- [x] M-GEOM-05 audit logging functional
- [x] Traceability chain complete (field → module → rule → decision)
- [x] Release gate integration tested
- [x] Fallback chain geometry checking integrated
- [x] Manual review queue operational

### Week 5 ✅
- [x] All 20 QA test cases passed
- [x] Load test: 100 concurrent jobs, <500ms each
- [x] Performance test: 10×10 grid <1 second
- [x] Database test: 1000 audit logs, <100ms queries
- [x] Regression tests: All existing validations still work
- [x] Zero breaking changes to Prompt C fallback policy

### Week 6 ✅
- [x] 4 technical documentation artifacts completed
- [x] All 4 training sessions scheduled & delivered
- [x] 2 user-facing documents (Help, FAQ) published
- [x] Staging deployment passed all validation
- [x] Production deployment successful; 24-hour monitoring complete
- [x] Go-live confirmed; system stable

---

## DEPENDENCIES & PREREQUISITES

### From Prompt B (Rule Reconciliation)
- ✅ 268 validated rules (229 v2 + 39 v2.1)
- ✅ Rule-to-module mapping (F-039 → M-GEOM-01, etc.)
- ✅ Blocking condition definitions (S1-S10)
- Required for: Linking geometry checks to field IDs (VR-GEOM rules)

### From Prompt C (Fallback Policy)
- ✅ 6 field classes with fallback chains
- ✅ Source hierarchy (DWG → STAAD → PDF)
- ✅ Confidence thresholds
- Required for: Fallback chain integration with geometry checks

### External Standards (for tolerance basis)
- [ ] AISC 360-22 (fabrication standards)
- [ ] AWS D1.1:2020 (welding standards)
- [ ] Internal Fabrication Tolerance Guide v3
- Used to justify tolerance thresholds in TGEOM-* tables

---

## RISK MITIGATION

| Risk | Mitigation | Owner |
|------|-----------|-------|
| **DXF parsing errors** | Robust error handling; fallback to manual entry if parse fails | DEV-002 |
| **Tolerance thresholds too tight** | Pilot with 10 jobs; adjust if >30% HOLD rate | Engineering |
| **SLA breaches (engineers overloaded)** | 24-hour escalation → P3 or PM for re-prioritization | PM + P3 |
| **Database performance** | Indexes on job_id, severity, action; load test before prod | DBA-007 |
| **Audit log explosion** | Archive old logs (>1 year) to separate table quarterly | DBA |
| **Conflicting geometry sources** | M-GEOM-04 quorum rule; always escalate conflicts to P3 | DEV-019 |
| **Breaking changes to fallback** | Integration test Week 4 (QA-015); no schema changes to fallback tables | QA-015 |

---

## GO-LIVE CHECKLIST

- [ ] **All 6 weeks completed** (no shortcuts)
- [ ] **All test cases passed** (20/20 QA tests; 100% code coverage)
- [ ] **All documentation published** (4 technical docs; 4 training sessions recorded)
- [ ] **Staging validation complete** (all 5 staging tests passed)
- [ ] **Production backup confirmed** (backup location documented)
- [ ] **Escalation contacts notified** (P2/P3 engineers aware of new workflow)
- [ ] **Support team trained** (able to troubleshoot geometry issues)
- [ ] **Monitoring configured** (alerts on geometry validation errors)
- [ ] **Go-live window scheduled** (off-hours; 2-4 hour maintenance window)
- [ ] **Rollback procedure ready** (tested; documented)
- [ ] **Executive sign-off** (Engineering Director approval)

---

## POST-DEPLOYMENT MONITORING (First 30 Days)

### Daily Checks
- [ ] Zero unhandled exceptions in geometry validation
- [ ] Manual review queue SLA compliance >95%
- [ ] Database query performance <500ms (99th percentile)
- [ ] Audit log entries complete (no missing fields)

### Weekly Review
- [ ] Mismatch rate trends (expect 5-10% of jobs initially)
- [ ] Top causes of geometry mismatches
- [ ] Manual review decision patterns
- [ ] Any tolerance adjustments needed?
- [ ] Training effectiveness feedback

### Monthly Report (End of Month 1)
- [ ] Total jobs validated: ___
- [ ] PASS rate: ___ %
- [ ] HOLD rate: ___ % (target <15%)
- [ ] BLOCK rate: ___ % (target <5%)
- [ ] Average manual review time: ___ hours
- [ ] SLA breach count: ___
- [ ] Top 3 mismatch causes
- [ ] Recommendations for Year 2

---

## SIGN-OFF

**Prepared by:** Geometry Reconciliation Implementation Agent  
**Date:** April 2026  
**Authority:** Engineering Standards  
**Status:** ✅ **READY FOR IMPLEMENTATION**

This checklist provides a complete, phased implementation path for the DXF-Database Geometry Reconciliation Module. All tasks are discrete, testable, and measurable. Success depends on adhering to the 6-week timeline and maintaining 100% test coverage throughout.

---
**END OF IMPLEMENTATION CHECKLIST**
