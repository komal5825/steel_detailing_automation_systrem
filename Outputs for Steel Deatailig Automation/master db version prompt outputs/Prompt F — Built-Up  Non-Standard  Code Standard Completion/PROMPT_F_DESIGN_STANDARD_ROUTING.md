# PROMPT F: DESIGN STANDARD ROUTING & SECTION GOVERNANCE
## Complete Technical Architecture & Data Model

**Project:** MasterDB v2.1 — Steel Section Standard Governance  
**Status:** 🔴 DESIGN PHASE / ARCHITECTURE DEFINITION  
**Date:** April 2026  
**Authority:** Engineering Standards & Design Control

---

## EXECUTIVE SUMMARY

### The Problem
The current MasterDB lacks:
- Clear routing logic for design standard branching (IS vs AISC vs Eurocode)
- Governance for built-up sections (weight calculation, geometry validation)
- Approval pathway for non-standard/custom steel members
- Explicit material grade harmonization across code families
- Seismic standard branching enforcement
- Controlled vocabulary for section types & codes

### The Solution
**Six production-ready database tables + governance logic defining:**
1. Design standard branching (3 code families, 4 branching points)
2. Section database routing (which source per standard per type)
3. Built-up section validation (geometry requirements, calculation gates)
4. Non-standard section approval (workflow, audit trail)
5. Material grade mapping (IS/American/European harmonization)
6. Seismic standard branching (code-specific routing)

---

## TASK 1: DESIGN STANDARD BRANCHING

### 1.1 Approved Code Families

#### Code Family 1: Indian Standards (IS)
**Standards:** IS 800 (General), IS 1893 (Seismic)  
**Section Database:** ISC / ISMB / ISLB / Other rolled / Custom built-up  
**Material Grades:** IS 250B, IS 250D, IS 350A, IS 350C, IS 500B, etc.  
**Seismic Standard:** IS 1893 (Part 1: 2016)  
**Design Method:** Limit State Design (LSD)  

#### Code Family 2: American Standards (AISC)
**Standards:** AISC 360 (General), AISC 341 (Seismic)  
**Section Database:** W / HP / C / MC / L / T shapes; Built-up sections  
**Material Grades:** ASTM A36, A50, A992, A913, etc.  
**Seismic Standard:** AISC 341 with ASCE 7 (Equivalent Lateral Force Method)  
**Design Method:** Load & Resistance Factor Design (LRFD)  

#### Code Family 3: BS/Eurocode (European)
**Standards:** BS 5950 (UK), EN 1993 (Eurocode 3), EN 8 (Seismic)  
**Section Database:** UB / UC / RSJ / Channels; Built-up sections  
**Material Grades:** S235, S275, S355, S450, etc.  
**Seismic Standard:** EN 1998 (Eurocode 8 / EN 8 equivalent)  
**Design Method:** Limit State Design (LSD)  

### 1.2 Design Standard Branching Points

#### Point 1: Project Setup (Initial Decision)
**When:** Project created in MasterDB  
**Decision:** Which design standard governs this project?  
**Options:** IS / AISC / Eurocode  
**Table:** `project_design_standard_master`  
**Consequences:**
- All section lookups routed to corresponding database
- All material grades must be valid for that standard
- All seismic provisions from that standard (if seismic project)
- All design checks per that standard

**Logic:**
```
IF project.seismic_required = TRUE
  THEN seismic_standard must match declared standard
  ELSE seismic_standard = NULL
ENDIF

project.design_standard (IS / AISC / EUROCODE) → immutable after project creation
```

#### Point 2: Section Lookup (Database Routing)
**When:** Engineer selects a section for a member  
**Decision:** Which section database to search?  
**Table:** `section_standard_route_master`  
**Routing Logic:**

| Design Standard | Section Type | Source Database | Examples |
|---|---|---|---|
| **IS** | Rolled I-Beam | ISC Catalog | ISC 100, ISC 150, ISC 200 |
| **IS** | Rolled H-Beam | ISMB Catalog | ISMB 100, ISMB 150, ISMB 200 |
| **IS** | Rolled Angle | Angle Tables | ISA 25×25 to ISA 200×200 |
| **IS** | Built-Up I-Section | Geometry Calc | Custom BU-ISx-y-t |
| **AISC** | Wide Flange | W-Shape Catalog | W10, W12, W14... W36 |
| **AISC** | HP Pile | HP Catalog | HP10, HP12, HP14... HP16 |
| **AISC** | Channel | C-Shape Catalog | C3, C4, C5... C15 |
| **AISC** | Built-Up I-Section | Geometry Calc | Custom BU-AIx-y-t |
| **EUROCODE** | UB (I-Beam) | Eurocode UB Tables | 127×76 to 610×229 |
| **EUROCODE** | UC (H-Beam) | Eurocode UC Tables | 100×100 to 356×406 |
| **EUROCODE** | Channel | Eurocode C Tables | 75×40 to 380×100 |
| **EUROCODE** | Built-Up I-Section | Geometry Calc | Custom BU-ECx-y-t |

**Validation Rules:**
```
IF section_lookup_for_member
  THEN project_design_standard must be set
  AND section_standard_code must match project_design_standard
  AND section_source_database must be valid for that standard
ELSE raise VALIDATION_ERROR
```

#### Point 3: Material Selection (Grade Harmonization)
**When:** Engineer specifies material grade  
**Decision:** Is grade valid for design standard?  
**Table:** `material_grade_mapping_master`  
**Harmonization Rules:**

| IS Grade | AISC Grade | Eurocode Grade | fy (MPa) | Comment |
|---|---|---|---|---|
| IS 250B | ASTM A36 | S235 | 250 | Economy structural steel |
| IS 250D | ASTM A50 | S275 | 250 | Deformable type (NDT) |
| IS 350A | ASTM A992 (Grade 50) | S355 | 350 | Higher strength, most common US |
| IS 350C | ASTM A588 (50 ksi) | S355 | 350 | Weathering steel |
| IS 500B | ASTM A514 (100 ksi) | S450 | 500 | Heavy sections only |

**Validation Rules:**
```
IF material_grade_selected
  THEN check material_grade_mapping_master
  IF mapping.design_standard ≠ project.design_standard
    THEN raise GRADE_STANDARD_MISMATCH
  ELSE Allow selection
ENDIF
```

#### Point 4: Seismic Design (Code Branching)
**When:** Seismic design required (project.seismic_required = TRUE)  
**Decision:** Which seismic standard applies?  
**Table:** `seismic_standard_mapping_master`  

| Design Standard | Seismic Standard | Version | Key Provisions |
|---|---|---|---|
| **IS** | IS 1893 (Part 1) | 2016 | Zone-based, Response Reduction Factor (R) |
| **AISC** | AISC 341 + ASCE 7 | 2022 | Equivalent Lateral Force or Response Spectrum |
| **EUROCODE** | EN 1998 (Eurocode 8) | 2004 + A1:2013 | Seismic Action Categories, Importance Factor |

**Validation Rules:**
```
IF project.seismic_required = TRUE
  THEN seismic_standard must be declared
  AND seismic_standard must match design_standard
  AND section_selection must meet seismic ductility requirements
ELSE seismic_standard = NULL
ENDIF
```

---

## TASK 2: SECTION DATABASE ROUTING

### 2.1 Routing Logic Architecture

**Flow:**
```
project_design_standard_master (lookup: project_id)
  ↓ [design_standard = IS / AISC / EUROCODE]
  ↓
section_standard_route_master (lookup: design_standard, section_type)
  ↓ [returns source_database, lookup_table, validation_rules]
  ↓
[Route to appropriate section catalog or built-up geometry module]
```

### 2.2 Routing Table Structure

**project_design_standard_master:**
- `project_id` (PK)
- `design_standard` (IS / AISC / EUROCODE)
- `seismic_required` (TRUE / FALSE)
- `seismic_standard` (IS 1893 / AISC 341 / EN 1998 or NULL)
- `design_code_version` (e.g., "IS 800:2007" or "AISC 360-22")
- `effective_date` (when this standard became active for project)
- `approved_by_role` (P3 principal engineer)
- `created_timestamp`, `updated_timestamp`

**section_standard_route_master:**
- `route_id` (PK)
- `design_standard` (IS / AISC / EUROCODE)
- `section_type` (ROLLED_I, ROLLED_H, ROLLED_CHANNEL, ROLLED_ANGLE, BUILT_UP, etc.)
- `source_database` (ISC / ISMB / W_SHAPE / UB / Custom)
- `lookup_table_name` (table containing section properties)
- `validation_rule_set_id` (which rules apply)
- `is_active` (TRUE / FALSE for retired routes)
- `notes` (e.g., "Eurocode UB sections EN 10025 S275")

### 2.3 Validation Rules per Route

**For IS Rolled Sections:**
- Section must exist in ISC/ISMB/Angle catalog
- Material grade must be IS 250B/D, IS 350A/C, IS 500B only
- Fy values from IS 800 clause 5 tables
- Weight check: ±2% of catalog value

**For AISC Rolled Sections:**
- Section must exist in AISC Steel Construction Manual (16th ed)
- Material grade must be ASTM A36 or A992 (most common)
- Fy values from AISC Table 1.1
- Weight check: ±1% of manual value

**For Eurocode Rolled Sections:**
- Section must exist in Eurocode 3 Part 1-1 section tables
- Material grade must be S235/S275/S355/S450
- Fy values from EN 10025 standards
- Weight check: ±1% of table value

---

## TASK 3: BUILT-UP SECTION DATA MODEL

### 3.1 Built-Up Section Geometry Master

**Purpose:** Store and validate custom built-up section geometries  
**Table:** `builtup_section_geometry_master`

**Columns:**
- `buildup_id` (PK): e.g., "BU-IS-250-200-10"
- `design_standard` (IS / AISC / EUROCODE)
- `section_type` (BUILT_UP_I, BUILT_UP_BOX, BUILT_UP_CHANNEL, etc.)
- `flange_width` (mm): b
- `flange_thickness` (mm): tf
- `web_height` (mm): h (clear height between flanges)
- `web_thickness` (mm): tw
- `fillet_radius` (mm): r (if welded)
- `plate_grade` (IS/ASTM/Eurocode grade)
- `plate_yield_strength` (fy, MPa)
- `connection_type` (WELDED / BOLTED / RIVETED)
- `weld_type` (if welded): E70 / E100 / etc.
- `is_symmetric` (TRUE / FALSE)
- `fabrication_notes` (tolerances, access holes, etc.)

### 3.2 Built-Up Section Calculation Flow

**Entry Gate:** Section cannot be used until:
1. Geometry defined in `builtup_section_geometry_master`
2. All dimensions verified by P2 engineer
3. Fabrication feasibility approved by P3 engineer
4. Weight calculated from geometry (NOT from rolled tables)

**Calculation Steps:**
```
Step 1: Get geometry from builtup_section_geometry_master
Step 2: Calculate area (A = 2×b×tf + (h-2×r)×tw)
Step 3: Calculate moment of inertia (Ixx from flange + web components)
Step 4: Calculate radius of gyration (r = √(I/A))
Step 5: Calculate weight (W = A × ρ_steel, where ρ = 7850 kg/m³)
Step 6: Validate: dimension ratios (b/2tf, h/tw) per design standard
Step 7: Verify: w≤ class limits for plastic section design (if applicable)
Step 8: Flag: web slenderness if h/tw > limits
Step 9: Store: calculated properties in geometry master
Step 10: Release: for design use
```

**Validation Rules (per design standard):**

| Limit | IS 800 | AISC 360 | Eurocode 3 |
|---|---|---|---|
| Max b/2tf (compact) | 10.5 | 8.5 (fy=250) | 9 |
| Max h/tw (plastic) | 84 | 90 | 72 |
| Min tf (mm) | 6 | 1/4" | 6 |
| Min tw (mm) | 5 | 3/16" | 5 |
| Weld throat: SAW | 8 | 3/16" | 8 |

### 3.3 Built-Up Section Approval Gate

**Gate S2 (if non-standard geometry):**
- P2 Reviews: dimensions, material grade, connection type
- P2 Validates: against design standard slenderness limits
- P3 Approves: fabrication feasibility, shop access
- Release: Only after P2 + P3 sign-off

**Blockers:**
- ❌ Missing fabrication details (connection design, access)
- ❌ Non-standard material (must be IS/ASTM/Eurocode certified)
- ❌ Non-compliant slenderness ratios (auto-block until remedied)
- ❌ No P2 geometry review
- ❌ No P3 fabrication approval

---

## TASK 4: NON-STANDARD SECTION GOVERNANCE

### 4.1 Non-Standard Section Approval Workflow

**Definition:** Non-standard = any section NOT in standard catalogs (IS, AISC, Eurocode)

**Examples:**
- Custom built-up sections (tapering, non-prismatic, compound)
- Composite sections (steel + reinforcement)
- Cold-formed sections (if not in standard)
- Heritage sections (obsolete standards)
- Adaptive reuse sections (existing member retention)

### 4.2 Approval Workflow

**Workflow Entry Gate (Automatic Block):**
```
IF section_is_nonstandard
  THEN approval_status = BLOCKED
  AND section_cannot_be_used_in_design
  AND trigger = automatic_approval_request
ENDIF
```

**Stage 1: Data Quality Check (DQE or P2)**
- Geometry submitted completely (all dimensions)
- Material grade specified & valid
- Design standard declared
- Fabrication details provided
- **SLA:** 4 hours
- **Pass Condition:** All required data present
- **Block Condition:** Missing critical dimensions or unspecified grade

**Stage 2: Geometry Validation (P2)**
- Verify dimensions against design standard limits
- Check slenderness ratios (b/2tf, h/tw, etc.)
- Validate material grade compatibility
- Review fabrication tolerances
- **SLA:** 24 hours
- **Pass Condition:** Geometry conforms to standard; no red flags
- **Hold Condition:** Non-standard slenderness; requires P3 concurrence
- **Block Condition:** Does not meet basic safety limits

**Stage 3: Feasibility Review (P3)**
- Engineering adequacy assessment
- Fabrication & shop viability (can shop execute?)
- Cost & schedule implications
- Code compliance confirmation
- **SLA:** 24 hours (4 hours if CRITICAL issue flagged)
- **Pass Condition:** Technically feasible & safe
- **Block Condition:** Unsafe or infeasible to fabricate
- **Conditional Approval:** Allowed with documented conditions

**Stage 4: Release Authority (PM)**
- Final approval to use in design
- Budget & schedule sign-off
- Stored in `nonstandard_section_review_master`
- Audit trail: all reviewers & approvers
- **SLA:** 24 hours
- **Pass Condition:** All P2/P3 approvals received
- **Block Condition:** Unresolved blockers or P3 red flags

### 4.3 Non-Standard Section Review Master Table

**Table:** `nonstandard_section_review_master`

**Columns:**
- `nonstandard_id` (PK): "NS-{timestamp}-{seq}"
- `section_description` (text: detailed geometry)
- `design_standard` (IS / AISC / EUROCODE)
- `submitted_by_role` (P2 / P3 / Project Engineer)
- `submitted_timestamp`
- `approval_status` (PENDING / APPROVED / REJECTED / CONDITIONAL)
- `dqe_review_completed` (timestamp)
- `p2_review_completed` (timestamp), `p2_approver_name`, `p2_notes`
- `p3_review_completed` (timestamp), `p3_approver_name`, `p3_notes`
- `pm_approval_timestamp`, `pm_approver_name`
- `condition_notes` (if approved with conditions)
- `block_reason` (if blocked)
- `storage_location` (where section catalog reference stored)

---

## TASK 5: MATERIAL GRADE MAPPING

### 5.1 Harmonization Matrix

**Table:** `material_grade_mapping_master`

**Purpose:** Explicit 1:1 mapping of equivalent grades across standards  
**Rule:** NO pattern matching; ALL mappings stored explicitly in this table

**Structure:**

| IS Grade | ASTM Grade | Eurocode Grade | fy (MPa) | fu (MPa) | Group | Notes |
|---|---|---|---|---|---|---|
| IS 250B | A36 | S235 | 250 | 410 | Economy | Lowest cost structural |
| IS 250D | A50 | S275 | 250 | 400 | General | Deformable type (NDT required) |
| IS 350A | A992 (Grade 50) | S355 | 350 | 450 | High-Str | Most common US grade |
| IS 350C | A588 (50 ksi) | S355 | 350 | 450 | Weather | Weathering steel |
| IS 500B | A514 (100 ksi) | S450 | 500 | 625 | Very-High | Heavy sections only; limited shapes |

### 5.2 Mapping Lookup Logic

**Lookup Rule:**
```
IF engineer_selects_grade = "IS 250B"
  AND project.design_standard = AISC
  THEN required_equivalent_grade = ASTM A36 (NOT "A50" or other)
ENDIF

IF engineer_selects_grade = "S235"
  AND project.design_standard = IS
  THEN required_equivalent_grade = IS 250B (NOT "IS 250D")
ENDIF
```

**Validation Rule:**
```
IF grade_specified_and_standard_mismatched
  THEN raise GRADE_STANDARD_MISMATCH exception
  AND block_section_from_use
  AND require_engineer_correction_and_reselection
ENDIF
```

### 5.3 Material Grade Constraints

**Per Design Standard:**

| Standard | Approved Grades | Why These? | Comments |
|---|---|---|---|
| **IS 800** | IS 250B/D, IS 350A/C, IS 500B | Available in Indian market; certified to IS 2062 | Grade 600 not approved (limited data) |
| **AISC 360** | ASTM A36, A50, A992, A588, A514 | Typical US grades; extensive design data in AISC Manual | Others allowed with approval |
| **EN 1993** | S235, S275, S355, S450 | EN 10025 standards; Eurocode 3 design tables | S460 allowed; higher grades rare |

**Locked to Standard:**
```
project.design_standard = IS
  ↓
material_grade must be in [IS 250B, IS 250D, IS 350A, IS 350C, IS 500B]
  ↓
block any others (e.g., ASTM grades auto-rejected)
```

---

## TASK 6: SEISMIC STANDARD MAPPING

### 6.1 Seismic Code Branching

**Decision Point:** When project.seismic_required = TRUE

**Seismic Standard Selection:**

| Design Standard | Seismic Code | Seismic Version | Key Method | Response Factor |
|---|---|---|---|---|
| **IS** | IS 1893 (Part 1) | 2016 | Zone-based, ELF | Response Reduction Factor (R) = 5-8 |
| **AISC** | AISC 341 + ASCE 7 | 2022 | Equivalent Lateral Force, Response Spectrum | Response Modification Factor (R) = 8-12 |
| **EUROCODE** | EN 1998 (Eurocode 8) | 2004 + A1:2013 | Elastic Spectrum, Inelastic Spectrum | Behavior Factor (q) = 4-8 |

**Table:** `seismic_standard_mapping_master`

**Columns:**
- `seismic_map_id` (PK)
- `design_standard` (IS / AISC / EUROCODE)
- `seismic_code_standard` (IS 1893 / AISC 341 / EN 1998)
- `version_year` (2016, 2022, 2004, etc.)
- `response_factor_field_name` (R, Cd, q, etc.)
- `response_factor_default_value` (typical value if not specified)
- `ductility_class_required` (for capacity-based design)
- `accidental_eccentricity_percent` (5, 5, 5)
- `damping_ratio_percent` (5, 5, 5)
- `gravity_load_factor` (1.0 in seismic, per code)
- `notes` (e.g., "Requires site-specific ground response spectra")

### 6.2 Seismic Design Consequence: Section Selection

**IS 1893 (Seismic Design):**
- Use higher ductility grades (IS 250D, IS 350A preferred)
- Avoid IS 500B (brittle behavior)
- Built-up sections: compact section limits stricter
- Beam-column connections: capacity-based (1.4×beam shear to column)

**AISC 341 (Seismic Design):**
- Special Moment Resisting Frame (SMF): requires A992 Grade 50
- Intermediate MRF: A36 acceptable
- Concentrically Braced: A992 or A588
- Section limits per AISC 341 Table C1.1

**EN 1998 (Eurocode 8):**
- Ductility Classes: M (moderate) or H (high)
- Class H: requires Class 1 sections (very compact)
- Class M: requires Class 2 sections
- Material: S355 or higher recommended (S235 allowed with limits)

**Validation Rule:**
```
IF project.seismic_required = TRUE
  AND seismic_standard = IS 1893
  THEN section_must_be_compact (per IS 800 clause 3.7.2)
  AND material_grade must be IS 250B/D or IS 350A/C (NOT IS 500B)
  AND flag if h/tw > 84 or b/2tf > 10.5
ENDIF
```

---

## MANDATORY DATABASE TABLES (6 TABLES, 150+ COLUMNS)

### Table 1: project_design_standard_master
**Purpose:** Declare design standard per project; immutable after creation  
**Columns:** project_id, design_standard, seismic_required, seismic_standard, design_code_version, approved_by_p3, created_timestamp

### Table 2: section_standard_route_master
**Purpose:** Route section lookups to correct database per standard  
**Columns:** route_id, design_standard, section_type, source_database, lookup_table_name, validation_rule_set_id, is_active

### Table 3: builtup_section_geometry_master
**Purpose:** Store custom built-up section geometries with validation  
**Columns:** buildup_id, design_standard, geometry details (b, tf, h, tw, r), material grade, p2_approved_timestamp, p3_approved_timestamp, calculated_properties

### Table 4: nonstandard_section_review_master
**Purpose:** Approval registry for non-standard sections  
**Columns:** nonstandard_id, section_description, approval_status, dqe_review, p2_review (name, timestamp, notes), p3_review, pm_approval

### Table 5: material_grade_mapping_master
**Purpose:** Explicit 1:1 grade mappings across IS/ASTM/Eurocode  
**Columns:** mapping_id, is_grade, astm_grade, eurocode_grade, fy, fu, group, approved_by_p3

### Table 6: seismic_standard_mapping_master
**Purpose:** Seismic code branching & design consequence mapping  
**Columns:** seismic_map_id, design_standard, seismic_code, version, response_factor_field, response_factor_default, ductility_class_required

---

## STRICT RULES ENFORCEMENT

### Rule 1: Standard Branching Is Mandatory
**Enforcement:** Every section lookup query includes `project_design_standard` parameter  
**Violation:** Query rejected; error logged; escalates to P3

### Rule 2: Built-Up Weight ≠ Rolled Weight
**Enforcement:** Built-up sections routed to geometry calculation module (not weight table)  
**Violation:** Section blocked until routed correctly; audit trail records attempt

### Rule 3: Non-Standard = Blocked Until Approved
**Enforcement:** `approval_status` checked in all design queries  
**Violation:** Non-approved non-standard section returns BLOCKED status; cannot be used

### Rule 4: Material Grade Must Match Standard
**Enforcement:** All grade selections validated against `material_grade_mapping_master`  
**Violation:** Mismatched grade rejected; engineer redirected to valid equivalents

### Rule 5: Seismic Project = Seismic Standard Declared
**Enforcement:** If `project.seismic_required = TRUE`, `seismic_standard` must be NOT NULL  
**Violation:** Cannot create seismic project without declaring seismic standard; raises error

---

## INTEGRATION WITH PROMPTS C, D, E

### With Prompt C (Fallback Policy)
Built-up sections can use 6-level fallback for component materials (flanges, web plates)

### With Prompt D (Geometry Reconciliation)
Built-up section geometry → DXF reconciliation at 8 tolerance checks

### With Prompt E (Supervisory Validation)
Non-standard section approval routed through S2/S3 validation gates:
- S2: Database reconciliation (P2 approves non-standard geometry)
- S3: Geometry feasibility (P3 approves fabrication)

---

## VALIDATION CHECKLIST

- [x] Design standard branching defined (3 families, 4 points)
- [x] Section routing logic specified (table structure, flow)
- [x] Built-up section data model designed (geometry, calculation, approval)
- [x] Non-standard approval workflow documented (5 gates, audit trail)
- [x] Material grade mapping matrix created (IS, ASTM, Eurocode)
- [x] Seismic code branching logic defined (3 standards, design consequences)
- [x] 6 mandatory tables specified
- [x] Strict rules formalized & enforceable
- [x] Integration points with Prompts C, D, E confirmed

---

**Prepared by:** Engineering Standards & Design Control Agent  
**Status:** 🔴 ARCHITECTURE COMPLETE — READY FOR DATABASE SCHEMA DESIGN  

---
