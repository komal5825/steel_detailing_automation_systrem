# GEOMETRY RECONCILIATION QUICK REFERENCE
## MasterDB v2.1 — Prompt D Delivery

---

## 8 CHECK CATEGORIES AT A GLANCE

| # | Check | Input | Tolerance | Failure = ? |
|---|-------|-------|-----------|-----------|
| **A** | Grid Spacing (per bay) | Extracted grid X vs DB spacing | ±2mm | MEDIUM if exceeds |
| **B** | Building Length (overall X) | MAX(extracted_X) - MIN(extracted_X) vs DB | ±5mm | HIGH if exceeds ±5mm; CRITICAL if ±10mm+ |
| **C** | Building Width (overall Y) | MAX(extracted_Y) - MIN(extracted_Y) vs DB | ±5mm | HIGH if exceeds ±5mm; CRITICAL if ±10mm+ |
| **D** | Column Coords (XY distance) | SQRT((ex-dbx)² + (ey-dby)²) per column | ±1.5mm | MEDIUM if exceeds; CRITICAL if >10mm |
| **E** | Elevation Schedule (Z) | Extracted level elevations vs DB levels | ±3mm | MEDIUM if 1-2 off; HIGH if 3+ off >5mm |
| **F** | AB Grid Spacing (foundation) | Anchor bolt grid spacing vs DB | ±2mm | CRITICAL if exceeds ±5mm (foundation risk!) |
| **G** | Member Marks (position XY) | Mark location distance from expected | ±3mm | LOW if within; MEDIUM if 3+ exceed |
| **H** | Drawing Scale | Scale ratio (extracted / db) | ±1% (0.99-1.01x) | CRITICAL if scale corrupted (>2% distortion) |

---

## 4 SEVERITY LEVELS

| Severity | Condition | Example | Authority | SLA | Action at S4 (AB Output) |
|----------|-----------|---------|-----------|-----|---------|
| **CRITICAL** | Blocks assembly/fit-up; foundation risk; topology error | Grid line count mismatch; building length off ±10mm; AB grid off >5mm | P3 Geometry Engineer (principal) | 4 hours | **BLOCK** — escalate immediately |
| **HIGH** | Requires rework or approval; affects sequence | 3+ column positions off by 5mm; elevation schedule multiple mismatches | P2 Structural Engineer | 24 hours | **BLOCK** — manual review required |
| **MEDIUM** | Minor variation; field-adjustable | 1-2 columns off 2-5mm; single elevation off 3mm | P2 Engineer or QA | 48 hours | **WARN** — log and proceed |
| **LOW** | Acceptable quality variation; rounding | Mark position off <1mm; dimension delta <1mm | Automatic/QA | N/A | **PASS** — automatic approval |

---

## TOLERANCE QUICK LOOKUP (TGEOM-001 through TGEOM-008)

```
Grid Spacing:         ±2mm nominal, ±10mm critical
Building Length:      ±5mm nominal, ±15mm critical
Building Width:       ±5mm nominal, ±15mm critical
Column Coords:        ±1.5mm nominal, ±5mm critical
Elevation:            ±3mm nominal, ±10mm critical
AB Grid (CRITICAL):   ±2mm nominal, ±5mm critical ⭐ TIGHTEST
Member Marks:         ±3mm nominal, ±10mm critical
Drawing Scale:        ±1% nominal, ±2% critical
```

---

## CRITICAL BLOCKING CONDITIONS (Always BLOCK Release)

🚫 **ALWAYS STOP if any of these occur:**

1. **Grid line count mismatch** (extracted bays ≠ db bays)
   - Topology error; grid broken
   - Action: Reparse DXF with correct layer config OR update database

2. **Building dimension delta ≥ ±10mm** (length or width)
   - Foundation anchor grid misalignment impossible
   - Action: Update DXF to correct dimension OR adjust database expected value

3. **Foundation AB grid offset ≥ ±5mm**
   - Anchor bolt holes cannot be drilled correctly
   - Action: P3 principal engineer review; foundation risk assessment required

4. **Column position offset >10mm from expected grid**
   - Assembly sequence jeopardized
   - Action: P3 review; may require field adjustment or rework

5. **Drawing scale ratio outside 0.98-1.02x**
   - Drawing geometry corrupted or wrong scale used
   - Action: Redraw from CAD OR re-export at correct scale

6. **Unresolved multi-source conflict** (3+ sources disagree on critical dimension)
   - Ambiguous geometry; cannot proceed
   - Action: P3 engineer reconciles sources; documents resolution

---

## MANUAL REVIEW AUTHORITIES

| Authority | Reviews | SLA | Escalates To |
|-----------|---------|-----|--------------|
| **P3 Geometry Engineer** | CRITICAL mismatches; geometry conflicts; overrides | 4 hours | Engineering Director |
| **P2 Structural Engineer** | HIGH severity; column/elevation issues | 24 hours | P3 Geometry Engineer |
| **QA Lead** | MEDIUM severity; documentation; as-built notes | 48 hours | Project Manager |
| **Workflow** | LOW severity; automatic approvals | None | None |

---

## HOW GEOMETRY VALIDATION WORKS

### Step 1: DXF Extraction (M-GEOM-01)
```
Input:  DXF/DWG file
Process: Parse grid lines, column marks, elevations using ezdxf
Output: extracted_geometry { grid_x[], grid_y[], column_pos[], elevations[] }
Confidence: 0.85+ = HIGH; 0.70-0.84 = MEDIUM; <0.70 = LOW
Gate: Confidence >= 0.75 required
```

### Step 2: DB Geometry Reading (M-GEOM-02)
```
Input:  Job ID + revision from geometry_reconciliation_master table
Process: Read grid_spacing, bay_count; calculate expected grid arrays
Output: db_geometry { grid_x[], grid_y[], column_pos[], elevations[] }
Gate: All required fields present
```

### Step 3: Reconciliation Checks (M-GEOM-03)
```
For each of 8 checks (A-H):
  Compare extracted vs database value
  Calculate delta = ABS(extracted - database)
  Check if delta > tolerance
  Output: { expected, actual, delta, exceeds_tolerance }
```

### Step 4: Severity Classification (M-GEOM-04)
```
For each mismatch:
  If delta > critical_threshold → CRITICAL
  Else if delta > hold_threshold → HIGH
  Else if delta > nominal → MEDIUM
  Else → LOW
  
Determine action from action_matrix (severity × processing_stage)
Aggregate: Overall action = highest blocking action
```

### Step 5: Audit Logging (M-GEOM-05)
```
For each mismatch:
  Create geometry_check_result_log entry:
  - check_id (GR-{timestamp}-{seq})
  - job_id, revision
  - expected, actual, delta, tolerance
  - severity, action
  - linked rule (VR-GEOM-XX)
  - linked field (F-039, etc.)
  - manual_review_required?
  - review_authority (if required)
```

### Release Gate Decision
```
If overall_action == 'BLOCK':
  → STOP workflow; escalate to P3 Geometry Engineer
  
If overall_action == 'HOLD':
  → PAUSE workflow; queue for manual review (P2 or P3)
  → SLA tracking begins
  → If no decision within SLA → escalate to higher authority
  
If overall_action == 'WARN':
  → LOG warning; notify shop; proceed to next stage
  
If overall_action == 'PASS':
  → Automatic approval; proceed to next stage
```

---

## INTEGRATION WITH FALLBACK POLICY (Prompt C)

**When fallback chain selects DXF source:**

```
Fallback: field_id = grid_spacing_x, try sources [DWG, STAAD, PDF]

Source 1: DWG (confidence 0.80+)
  ├─ M-GEOM-01 extracts: 6100 mm
  ├─ M-GEOM-03 reconciles vs DB expected: 6000 mm
  ├─ Delta = 100 mm vs tolerance ±2mm → EXCEEDS
  ├─ M-GEOM-04 classify: severity = HIGH
  ├─ Decision: CRITICAL/HIGH mismatch → SKIP DXF source
  └─ Continue to next source

Source 2: STAAD (confidence 0.80+)
  ├─ Extract: 6000 mm
  ├─ M-GEOM-03 reconciles: delta = 0 mm → within tolerance
  ├─ Accept STAAD value
  └─ Proceed with 6000 mm

Result: DXF not used; STAAD used instead; mismatch logged in audit trail
```

---

## MODULES ARCHITECTURE

```
┌──────────────────────────────────────────────────────┐
│  DXF-DATABASE GEOMETRY RECONCILIATION (M-GEOM-01-05) │
└──────────────────────────────────────────────────────┘

M-GEOM-01: DXF Extraction & Normalization
├─ Input: DXF/DWG file
├─ Process: Parse with ezdxf; extract grid lines, marks, elevations
├─ Output: extracted_geometry object with confidence score
└─ Gate: Confidence >= 0.75

M-GEOM-02: Database Geometry Reading
├─ Input: geometry_reconciliation_master table
├─ Process: Read grid_spacing, bay_count; calculate expected arrays
├─ Output: db_geometry object with all expected values
└─ Gate: Required fields present

M-GEOM-03: Tolerance-Based Reconciliation (8 Checks)
├─ Check A: Grid Spacing (per span)
├─ Check B: Building Length
├─ Check C: Building Width
├─ Check D: Column Coordinates
├─ Check E: Elevation Schedule
├─ Check F: AB Grid Spacing
├─ Check G: Member Marks
├─ Check H: Drawing Scale
└─ Output: Array of check results with deltas

M-GEOM-04: Severity Classification & Action Determination
├─ Classify each mismatch (CRITICAL/HIGH/MEDIUM/LOW)
├─ Determine action from action_matrix (severity × stage)
├─ Aggregate all mismatches → overall action
└─ Output: {severity, action, authority, requires_review, sla_hours}

M-GEOM-05: Audit & Logging
├─ Create geometry_check_result_log entries
├─ Build traceability chain (field → module → rule → decision)
├─ Track manual review status & SLA
└─ Output: Permanent audit trail for compliance
```

---

## 10 VALIDATION RULES (VR-GEOM-01 through VR-GEOM-10)

| Rule | Category | Trigger | Action |
|------|----------|---------|--------|
| VR-GEOM-01 | Grid Geometry | Grid spacing missing all sources | BLOCK (S2) |
| VR-GEOM-02 | Grid Count | Bay count mismatch | BLOCK (S2) |
| VR-GEOM-03 | Dimension | Building length delta ≥±10mm | BLOCK (S3) |
| VR-GEOM-04 | Column Position | Column offset >10mm | BLOCK (S4) |
| VR-GEOM-05 | Elevation | 3+ elevations off >5mm | HOLD (S5) |
| VR-GEOM-06 | AB Grid | Anchor bolt grid delta ≥±5mm | BLOCK (S4) |
| VR-GEOM-07 | Scale | Drawing scale >±2% distortion | BLOCK (S2) |
| VR-GEOM-08 | Conflict | Multi-source disagreement | HOLD (S3) |
| VR-GEOM-09 | Review | HIGH severity or >5 mismatches | HOLD (S4) |
| VR-GEOM-10 | Audit | Reconciliation audit trail failed | BLOCK (S9) |

---

## DATABASE TABLES (4 NEW)

### geometry_reconciliation_master
- Stores baseline geometry per job/revision
- Primary key: (job_id, revision_number)
- ~40 columns: grid spacing, building dims, column coords, AB grid, elevations, metadata
- Referenced by geometry_check_result_log (foreign key)

### geometry_check_result_log
- Permanent audit trail; append-only log
- Primary key: check_id (GR-{timestamp}-{seq})
- ~30 columns: check details, expected/actual/delta/tolerance, severity, action, review status
- Foreign key: (job_id, revision_number) → geometry_reconciliation_master
- Indexes: job_id, severity, action_determined, category, timestamp

### geometry_tolerance_master
- Reference table for all 8 check categories
- Primary key: tolerance_id (TGEOM-001 through TGEOM-008)
- Unique constraint: check_category (one row per category)
- ~20 columns: nominal/hold/critical thresholds, severity mapping, basis standards

### geometry_conflict_action_master
- Action matrix: what to do for each severity/stage combo
- Primary key: action_id (GCA-001 through GCA-040)
- Unique constraint: (severity, processing_stage)
- ~20 columns: action (BLOCK/HOLD/WARN/PASS), authority, SLA, escalation, notifications

---

## PROCESSING STAGES WHERE GEOMETRY VALIDATES

| Stage | Name | Geometry Checks | Blocking |
|-------|------|---|---|
| **S1** | Intake | None (at this stage) | - |
| **S2** | Design Parsing | Grid spacing, grid count, drawing scale | VR-GEOM-01, VR-GEOM-02, VR-GEOM-07 |
| **S3** | Field Population | Building dimensions, multi-source conflicts | VR-GEOM-03, VR-GEOM-08 |
| **S4** | AB Output | Column positions, AB grid, manual review trigger | VR-GEOM-04, VR-GEOM-06, VR-GEOM-09 |
| **S5** | GA Output | Elevation schedule | VR-GEOM-05 |
| **S6** | Validation | Summary validation | - |
| **S7** | Shop Detailing | Reconciliation validated | - |
| **S8** | Installation | Reconciliation validated | - |
| **S9** | Release | Audit trail verification | VR-GEOM-10 |
| **S10** | Post-Release | None | - |

---

## ESCALATION FLOWS

### CRITICAL Mismatch (e.g., grid count error)
```
Mismatch detected (M-GEOM-03)
  ↓
Classify CRITICAL (M-GEOM-04)
  ↓
Action = BLOCK; Authority = P3 Geometry Engineer
  ↓
Create escalation ticket (GC-{timestamp})
  ↓
Notify P3 + Engineering Director
  ↓
SLA = 4 hours
  ↓
P3 reviews options:
  ├─ Re-parse DXF with correct layer config → resolve
  ├─ Update database geometry → confirm and proceed
  ├─ Request CAD resubmission → escalate to client
  └─ Approve override in writing → document exception
```

### HIGH Mismatch (e.g., column offset 5mm)
```
Mismatch detected
  ↓
Classify HIGH
  ↓
Action = HOLD; Authority = P2 Structural Engineer
  ↓
Queue for manual review
  ↓
SLA = 24 hours
  ↓
P2 reviews:
  ├─ Approve as-is with notes → proceed
  ├─ Request CAD correction → pause until resubmitted
  ├─ Document as acceptable variation → proceed with note
  └─ Escalate to P3 → forward if judgment unclear
```

---

## COMMON TROUBLESHOOTING

**Q: Why is my DXF geometry being BLOCKED?**
A: Check geometry_check_result_log for your job. Find the row with severity=CRITICAL. Read the check_category and delta. Examples:
- Grid line count mismatch → Reparse DXF; verify layer config
- Building length off ±10mm+ → Update DXF or database
- AB grid off >5mm → Foundation risk; escalate to P3

**Q: How long does geometry review take?**
A: CRITICAL = 4 hours (P3 engineer). HIGH = 24 hours (P2 engineer). MEDIUM = 48 hours. LOW = automatic (no review).

**Q: Can I override geometry validation?**
A: Yes, with P3 principal engineer approval and documented exception record.

**Q: Which tolerance applies to my project?**
A: Look up your design_standard in geometry_tolerance_master. All tolerances tied to AISC 360, AWS D1.1, or internal standard.

**Q: What if engineering confirms the DXF is correct and database is wrong?**
A: Update geometry_reconciliation_master with corrected values. Add note: "CAD confirmed; updated database baseline per P3 approval." Re-run reconciliation.

---

## SAMPLE AUDIT LOG QUERY

```sql
-- Find all CRITICAL geometry mismatches for a job
SELECT check_id, check_category, expected_value, actual_extracted_value, delta, 
       severity, action_determined, review_authority, reviewed_by, review_decision
FROM geometry_check_result_log
WHERE job_id = 'JOB-2026-12345' 
  AND revision_number = 1
  AND severity = 'CRITICAL'
ORDER BY check_timestamp DESC;

-- Result Example:
-- GR-2026-04-21-143022-001 | grid_spacing | 6000 | 6100 | 100 | CRITICAL | BLOCK | P3 Geometry Engineer | pending | NULL
```

---

## CONFIDENCE SCORING

```
Extraction Confidence (0.0-1.0):
  >= 0.85  → HIGH (DXF parsed cleanly; all layers found)
  0.70-0.84 → MEDIUM (minor parsing issues; manual review recommended)
  < 0.70   → LOW (must resolve before release)

Confidence affects:
  ✓ Fallback source ranking (DXF confidence 0.85+ preferred over STAAD 0.80)
  ✓ Manual review threshold (LOW confidence → automatic review queue)
  ✓ Audit trail notation (flagged for QA if <0.80)
```

---

**Last Updated:** April 2026  
**Version:** v1.0 (Production Ready)  
**Authority:** Geometry Validation Engineering

---
