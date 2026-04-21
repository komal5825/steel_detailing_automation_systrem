# PROMPT G: SOURCE-NEUTRAL MAPPING MATRIX
## Complete Source Path Mapping for 9 Critical Field Groups

**Project:** MasterDB v2.1 — Software-Agnostic Data Extraction  
**Status:** 🔴 ARCHITECTURE COMPLETE  
**Date:** April 2026  
**Authority:** Data Interoperability & Source Mapping Control

---

## CRITICAL FIELD GROUP 1: GEOMETRY

### Field: X, Y, Z Coordinates (Member Node Positions)

| Software | Source Field | Source Type | Extraction Path | Confidence | Notes |
|---|---|---|---|---|---|
| **MBS** | `member.nodes.coordinate_x/y/z` | Database columns | Direct SELECT from geometry table | 0.95 | BIM export guaranteed precision |
| **STAAD** | `JOINT id x y z` | Text file, 3D coordinate list | Parse .std file, extract JOINT lines | 0.92 | May have floating-point precision loss |
| **ETABS** | `PointCoordinates.X / Y / Z` | MySQL geometry columns | Query PointCoordinates table (UTM coords) | 0.90 | Verify against local coordinate system |
| **Prota** | `Member.XStart, YStart, ZStart / XEnd, YEnd, ZEnd` | Excel columns or JSON | Parse export; transform if local coords | 0.85 | May require coordinate system transformation |

**Normalized Target:**
```
geometry_normalized:
  - node_id (PK, software-agnostic)
  - source_software (MBS / STAAD / ETABS / PROTA)
  - x_coordinate_m (DECIMAL, global reference frame)
  - y_coordinate_m (DECIMAL, global reference frame)
  - z_coordinate_m (DECIMAL, global reference frame)
  - confidence_score (0.0–1.0)
  - source_record_id (trace back to original software record)
```

**Normalization Rule:**
```
IF coordinate_system_is_local:
  THEN transform to global (apply rotation matrix)
  AND verify transformation accuracy
  AND reduce confidence by 0.05
ELSE 
  USE coordinates directly
ENDIF

CONFIDENCE_ADJUSTMENT:
  - If missing any of X/Y/Z → confidence = 0.0 (block)
  - If coordinate precision < mm → confidence -0.05
  - If coordinate system transformation required → confidence -0.05
```

**Missing-Data Handling:**
- **MBS:** If missing → BLOCK (BIM should always have coordinates)
- **STAAD:** If missing → BLOCK (coordinates required for joints)
- **ETABS:** If missing → FALLBACK to grid-derived estimate (low confidence)
- **Prota:** If missing → FALLBACK to member start point (one node only)

---

### Field: Member Length (Calculated or Specified)

| Software | Source Field | Extraction | Confidence | Notes |
|---|---|---|---|---|
| **MBS** | `member.geometry.length_m` | Direct SELECT | 0.98 | Pre-calculated in BIM |
| **STAAD** | DISTANCE(node1, node2) | Calculated from coordinates | 0.95 | Calculate from JOINT coordinates |
| **ETABS** | `FrameElems.Length` | MySQL column | 0.93 | May be measured or input |
| **Prota** | Member.Length OR DISTANCE(start, end) | If provided, use; else calculate | 0.88 | Fallback to distance calculation |

**Normalization:**
```
normalized_member_length = SQRT((x2-x1)² + (y2-y1)² + (z2-z1)²)
IF provided_length ≠ calculated_length (within tolerance):
  THEN flag warning (provided length may be wrong)
  AND use calculated length
ENDIF
```

---

## CRITICAL FIELD GROUP 2: GRIDS

### Field: Grid Lines (Reference Lines for Layout)

| Software | Source Structure | Source Data | Extraction Logic | Confidence |
|---|---|---|---|---|
| **MBS** | `grid_master` table | grid_id, direction, value_along_axis, spacing | Direct table lookup | 0.96 |
| **STAAD** | DEFINE GRID command | Grid name, direction (X/Y/Z), values (list of coords) | Parse DEFINE GRID lines; extract coordinate array | 0.90 |
| **ETABS** | `GridDefinition` table | GridID, GridType (Column/Beam/Diaphragm), lines (X/Y/Z) | Query GridDefinition; extract line arrays | 0.88 |
| **Prota** | Grids worksheet/JSON | Grid name, type, X-coords (array), Y-coords (array) | Parse array; identify axes | 0.82 |

**Critical Issue: Orthogonal vs. Non-Orthogonal**

**MBS Assumption:** All grids orthogonal (axes parallel to X/Y/Z)
**STAAD Reality:** Grids can be skewed, non-orthogonal, or rotated
**ETABS Reality:** Multiple grid systems; can have local coordinate systems
**Prota Reality:** Limited grid support; usually orthogonal

**Normalization Rule:**
```
IF grid_is_non_orthogonal:
  THEN decompose into orthogonal equivalents
  AND flag: "Non-orthogonal grid; decomposed for storage"
  AND reduce confidence -0.10
ELSE
  STORE as-is
ENDIF
```

**Normalized Target:**
```
grid_normalized:
  - grid_id (software-agnostic)
  - source_software
  - grid_direction (X / Y / Z / ROTATED)
  - grid_type (COLUMN / BEAM / STORY / PARKING / OTHER)
  - grid_coordinates (array of values along direction)
  - is_regular_spacing (TRUE / FALSE)
  - spacing_mm (if regular; NULL if irregular)
  - rotation_angle_degrees (if not aligned to X/Y/Z)
  - confidence_score
  - source_record_id
```

**Missing-Data Handling:**
- **MBS:** If missing grids → FALLBACK to estimated grid from member positions
- **STAAD:** If missing grids → FALLBACK (calculate from member endpoints)
- **ETABS:** If missing grids → FALLBACK (use story levels as implicit grid)
- **Prota:** If missing grids → FALLBACK to bounding box estimate

---

## CRITICAL FIELD GROUP 3: LEVELS (STORY DEFINITIONS)

### Field: Floor/Story Elevation & Properties

| Software | Source Field | Type | Extraction | Confidence |
|---|---|---|---|---|
| **MBS** | `level_master` table | level_id, elevation_m, level_name, floor_type | SELECT from level_master | 0.97 |
| **STAAD** | MASTER JOINT and story lines | Text file; story implied by Z-coordinate ranges | Parse Z-coordinates; cluster into stories | 0.85 |
| **ETABS** | `Story` table | StoryID, Height (relative), Elevation (absolute) | Query Story table; accumulate heights | 0.91 |
| **Prota** | Levels worksheet | Level, Elevation, Name, Type | Parse worksheet rows | 0.88 |

**Critical Issue: Relative vs. Absolute Elevation**

**MBS:** Absolute elevation (Z = height above datum)
**STAAD:** Z-coordinate (may be relative to project origin)
**ETABS:** Both relative (height between stories) and absolute
**Prota:** Usually absolute; may need transformation

**Normalization:**
```
IF elevation_is_relative:
  THEN convert to absolute (accumulate from base)
  AND verify base elevation specified
  AND reduce confidence -0.08
ELSE
  USE absolute elevation directly
ENDIF

CONSENSUS_FLOOR_HEIGHT = AVG(level_heights_in_project)
IF level_height deviates > 10% from consensus:
  THEN flag warning (unusual floor height)
  AND verify against source
ENDIF
```

**Normalized Target:**
```
level_normalized:
  - level_id (software-agnostic)
  - source_software
  - level_elevation_m_absolute (from datum)
  - level_name (story identification)
  - level_type (FLOOR / MEZZANINE / ROOF / BASEMENT / PENTHOUSE)
  - floor_height_m (distance from previous story)
  - slab_thickness_m (if available)
  - confidence_score
  - source_record_id
```

---

## CRITICAL FIELD GROUP 4: MEMBER SECTIONS

### Field: Cross-Section Profile (I-beam, Box, Built-Up, etc.)

| Software | Source Field | Structure | Extraction | Confidence |
|---|---|---|---|---|
| **MBS** | `section_master` table | section_id, profile_name, material_grade, properties (A, I, r) | SELECT from section_master; join with member.section_id | 0.96 |
| **STAAD** | MEMBER PROPERTY lines | Profile name, size (e.g., "ISC 250"), material | Parse MEMBER PROPERTY; lookup in standard database | 0.88 |
| **ETABS** | `FrameSecProps` table | SectionName, Material, Type (Steel/Composite), built-up flag | Query FrameSecProps; check built-up flag | 0.90 |
| **Prota** | Sections worksheet | Section, Type, Size, Grade, Custom (Y/N) | Parse rows; identify standard vs. custom | 0.85 |

**Critical Issue: Standard vs. Custom Built-Up Sections**

**MBS:** Stores all sections (standard + custom) in same table
**STAAD:** Standard sections referenced by name; custom sections defined inline
**ETABS:** Built-up sections stored as separate records
**Prota:** Limited built-up support; mostly standard shapes

**Normalization Rule:**
```
IF section_is_built_up:
  THEN extract geometry (b, tf, h, tw, r)
  AND route to builtup_section_geometry_master (from Prompt F)
  AND reduce confidence -0.05 (custom sections less certain)
ELSE IF section_is_standard:
  THEN lookup in section_standard_route_master (from Prompt F)
  AND verify section exists in approved catalog
ELSE
  THEN confidence = 0.0 (unrecognized section type)
ENDIF
```

**Normalized Target:**
```
section_normalized:
  - member_id (references member)
  - source_software
  - section_type (STANDARD / BUILT_UP / COMPOSITE / SPECIAL)
  - section_name (software-provided name)
  - section_category (I_BEAM / H_BEAM / CHANNEL / ANGLE / BOX / CUSTOM)
  - material_grade (IS 250B / ASTM A36 / S235 / etc.)
  - confidence_score
  - source_section_id (trace to original)
```

---

## CRITICAL FIELD GROUP 5: ANCHOR BOLTS / BASE REFERENCES

### Field: Foundation Connection Details

| Software | Source Field | Type | Extraction | Confidence |
|---|---|---|---|---|
| **MBS** | `anchor_bolt_master`, `base_plate_master` | Database tables | SELECT from anchor/base tables; join to support node | 0.92 |
| **STAAD** | SUPPORT command (if modeled) + custom properties | Text file; SUPPORT lines indicate fixity; bolt details in notes | Parse SUPPORT lines; extract bolt count/size from notes | 0.70 |
| **ETABS** | `Support` table (fixity only); bolt data in notes | MySQL; limited bolt modeling | Query Support table; parse notes field (unstructured) | 0.65 |
| **Prota** | Base worksheet; anchor worksheet | Excel; separate sheets for base plates, anchor bolts | Parse worksheets; cross-reference | 0.78 |

**Critical Issue: Fixity vs. Actual Bolts**

**MBS:** Explicit anchor bolt records (bolt size, count, grade, pattern)
**STAAD:** Fixity only (FIXED, PINNED, FREE); bolt details not captured
**ETABS:** Fixity only; bolt modeling limited
**Prota:** Anchor records present but not always complete

**Normalized Rule:**
```
IF anchor_bolts_explicitly_defined:
  THEN extract bolt_size, bolt_count, bolt_grade, bolt_pattern
  AND confidence ≥ 0.85
ELSE IF only_fixity_defined:
  THEN estimate anchor configuration from fixity + geometry
  AND confidence ≤ 0.70 (estimated; requires verification)
  AND flag for manual review
ELSE
  THEN confidence = 0.0 (block; requires input)
ENDIF
```

**Normalized Target:**
```
anchor_bolt_normalized:
  - support_node_id
  - source_software
  - bolt_size_mm
  - bolt_count
  - bolt_grade (Grade 8.8, ASTM A325, etc.)
  - bolt_pattern (SQUARE / RECTANGULAR / CIRCLE / LINEAR)
  - base_plate_size_mm (width × length)
  - base_plate_thickness_mm
  - foundation_type (CONCRETE / STEEL / OTHER)
  - fixity_xx / fixity_yy / fixity_zz (0=free, 1=pinned, 2=fixed)
  - confidence_score
  - source_record_id
```

**Missing-Data Handling:**
- **MBS:** If missing → BLOCK (BIM should have anchors)
- **STAAD:** If missing → FALLBACK to fixity-based estimate (low confidence)
- **ETABS:** If missing → FALLBACK to fixity (requires manual design)
- **Prota:** If missing → FALLBACK to base design from fixity

---

## CRITICAL FIELD GROUP 6: CONNECTION DETAILS

### Field: Bolted / Welded / Riveted Joints

| Software | Source Field | Extraction | Confidence |
|---|---|---|---|---|
| **MBS** | `connection_master` table | connection_id, connection_type, bolt/weld details | SELECT from connection_master | 0.94 |
| **STAAD** | MEMBER RELEASE lines (pinned/fixed ends) | Parse RELEASE lines; bolt details in custom properties | 0.75 |
| **ETABS** | `ConnProperties` table + `RigidLink` settings | Query tables; note limited connection modeling | 0.78 |
| **Prota** | Connections worksheet | Explicit connection records (limited) | Parse worksheet | 0.72 |

**Critical Issue: Connection Modeling Depth**

**MBS:** Full connection details (angle, gusset, bolt layout, welds)
**STAAD:** Limited connection definition (mostly releases); bolt details external
**ETABS:** Connection modeling basic (rigid/pinned); full details external
**Prota:** Limited connection support

**Normalized Rule:**
```
IF connection_data_comprehensive:
  THEN extract all bolt/weld specifications
  AND confidence ≥ 0.85
ELSE IF connection_data_partial:
  THEN extract what available (joint angle, fixity)
  AND flag: "Partial connection data; design details required"
  AND confidence ≤ 0.75
ELSE
  THEN confidence = 0.0 (block; requires structural design)
ENDIF
```

**Normalized Target:**
```
connection_normalized:
  - connection_id (software-agnostic)
  - source_software
  - member1_id / member2_id (connected elements)
  - connection_type (BOLTED / WELDED / RIVETED / PINNED / MOMENT_RIGID)
  - bolt_size_mm (if bolted)
  - bolt_count
  - bolt_grade
  - weld_size_mm (if welded)
  - weld_type (FILLET / GROOVE / etc.)
  - gusset_thickness_mm (if applicable)
  - design_status (DESIGNED / PRELIMINARY / ESTIMATED / REQUIRED)
  - confidence_score
  - source_record_id
```

**Missing-Data Handling:**
- **MBS:** If missing → BLOCK (BIM provides connections)
- **STAAD:** If missing → FALLBACK to release type (estimate fixity)
- **ETABS:** If missing → FALLBACK to rigid/pinned assumption
- **Prota:** If missing → FALLBACK to pinned assumption

---

## CRITICAL FIELD GROUP 7: BUILT-UP MEMBERS

### Field: Custom Geometry (Dimensions, Material, Splices)

| Software | Source Field | Type | Extraction | Confidence |
|---|---|---|---|---|
| **MBS** | `builtup_section_geometry_master` (Prompt F) | Table reference | SELECT geometry + properties | 0.96 |
| **STAAD** | MEMBER PROPERTY + NONPRISMATIC (if used) | Text; custom shapes defined with NONPRISMATIC or custom property lines | Parse NONPRISMATIC; extract geometry | 0.80 |
| **ETABS** | Built-up section type; general section properties | MySQL; limited built-up modeling | Query FrameSecProps; extract custom flag | 0.75 |
| **Prota** | Custom member data (if present) | Excel; custom sections optional | Parse section definition; extract dimensions | 0.70 |

**Critical Issue: MBS Built-Up Data vs. STAAD/ETABS**

**MBS:** Full geometry (b, tf, h, tw, r, weight, properties stored)
**STAAD:** Can model non-prismatic; dimensions must be extracted from properties
**ETABS:** Limited built-up support; relies on general section with custom properties
**Prota:** Limited; mostly standard shapes

**Normalization:**
```
IF built_up_section_is_standard_catalog:
  THEN reference section_standard_route_master (Prompt F)
ELSE IF built_up_section_is_custom_geometry:
  THEN extract geometry (b, tf, h, tw, r)
  AND route to builtup_section_geometry_master (Prompt F)
  AND apply P2/P3 approval gates (Prompt F)
  AND confidence -0.10 if not yet approved
ELSE
  THEN confidence = 0.0 (unrecognized)
ENDIF
```

**Normalized Target:**
```
buildup_normalized:
  - member_id
  - source_software
  - flange_width_mm
  - flange_thickness_mm
  - web_height_mm
  - web_thickness_mm
  - fillet_radius_mm
  - material_grade
  - splice_count (if applicable)
  - splice_details (array of splice info)
  - approval_status (from Prompt F: PENDING / APPROVED / REJECTED)
  - confidence_score
  - source_record_id
```

**Missing-Data Handling:**
- **MBS:** If missing geometry → BLOCK (BIM should have full geometry)
- **STAAD:** If missing → FALLBACK to properties-derived estimate (low confidence)
- **ETABS:** If missing → FALLBACK to general section properties
- **Prota:** If missing → BLOCK or manual input required

---

## CRITICAL FIELD GROUP 8: CRANE DATA

### Field: Monorail / Overhead Crane Support, Hooks, Rails

| Software | Source Field | Extraction | Confidence | Notes |
|---|---|---|---|---|
| **MBS** | `crane_data_master` table | crane_id, rail_beam_id, hook_capacity_kN, load_case_id | SELECT crane table; join to rail members | 0.93 |
| **STAAD** | Custom properties + LOAD commands | Parse LOAD case definitions; extract crane hook coordinates & capacity | 0.75 |
| **ETABS** | Load tables + custom properties | Query Load tables; crane data in notes/properties | 0.70 |
| **Prota** | Crane worksheet (if present) | Parse worksheet; limited crane modeling | 0.65 |

**Critical Issue: Crane Path vs. Hook Capacity vs. Load Distribution**

**MBS:** Explicit crane record → rail beam → hook capacity → load case
**STAAD:** Hook capacity as load case; rail beam inferred
**ETABS:** Limited crane support; capacity in loads
**Prota:** Minimal crane modeling

**Normalized Rule:**
```
IF crane_data_present:
  THEN extract: rail_beam, hook_capacity, load_cases
  AND verify rail member can support hook + load
  AND assign to appropriate load case
  AND confidence ≥ 0.80
ELSE IF crane_implied_by_loads:
  THEN estimate from load cases
  AND flag: "Crane inferred from load cases; verify design intent"
  AND confidence ≤ 0.70
ELSE
  THEN skip (no crane data)
ENDIF
```

**Normalized Target:**
```
crane_normalized:
  - crane_id
  - source_software
  - rail_beam_member_id
  - rail_span_m
  - hook_capacity_kn
  - hook_offset_mm (from beam centerline)
  - load_case_id (which case applies)
  - mono_vs_double_rail (MONO / DOUBLE)
  - confidence_score
  - source_record_id
```

---

## CRITICAL FIELD GROUP 9: SHEETING-SUPPORT DATA

### Field: Purlins, Bracing, Roof/Wall Decking Support

| Software | Source Field | Extraction | Confidence |
|---|---|---|---|---|
| **MBS** | `sheeting_support_master` table | support_type, span, spacing, load_path | SELECT from sheeting table | 0.91 |
| **STAAD** | Member groups/custom properties | Parse member names (e.g., "PUR-1-001") or custom properties | 0.75 |
| **ETABS** | Load assignment + frame element properties | Infer from load assignments; identify purlins by pattern | 0.72 |
| **Prota** | Purlin/bracing worksheet | Parse worksheet; cross-reference with members | 0.70 |

**Critical Issue: Sheeting Load Path Not Always Modeled in Analysis**

**MBS:** Explicit sheeting support record → load transfer path clear
**STAAD:** Purlins modeled; sheeting deck may not be
**ETABS:** Loads applied; deck representation limited
**Prota:** Purlins present; sheeting abstracted

**Normalized Rule:**
```
IF sheeting_support_explicitly_defined:
  THEN extract: support_type, span, spacing, design_load
  AND confidence ≥ 0.85
ELSE IF sheeting_inferred_from_load_pattern:
  THEN estimate support configuration from member spacing & loads
  AND flag: "Sheeting support inferred; verify design intent"
  AND confidence ≤ 0.70
ELSE
  THEN skip (no sheeting data available)
ENDIF
```

**Normalized Target:**
```
sheeting_normalized:
  - sheeting_id
  - source_software
  - support_type (PURLIN / BRACING / DECKING / COMPOSITE_BEAM)
  - member_id (purlin/bracing reference)
  - span_mm
  - spacing_mm (between supports)
  - load_case_id
  - design_load_kpa
  - confidence_score
  - source_record_id
```

---

## COMMON NORMALIZATION RULES (APPLY TO ALL FIELDS)

### Confidence Scoring

```
CONFIDENCE FACTORS:
  - Data present & complete: +0.95–1.0
  - Data present & complete, requires transformation: +0.85–0.95
  - Data estimated from partial information: +0.70–0.85
  - Data inferred; not explicitly present: +0.50–0.70
  - Data block (required but missing): 0.0

ADJUSTMENTS (CUMULATIVE):
  - Floating-point precision loss: -0.02 to -0.05
  - Coordinate system transformation required: -0.05
  - Data interpolation: -0.05 to -0.10
  - Unstructured text parsing: -0.05 to -0.15
  - Custom/non-standard interpretation: -0.10
  - Multiple inference steps: -0.05 per step

FINAL_CONFIDENCE = BASE_CONFIDENCE + ADJUSTMENTS
CONFIDENCE_RANGE = [0.0, 1.0]
```

### Data Quality Rules

```
IF confidence_score ≥ 0.85:
  THEN data acceptable for automatic processing
  AND no manual review required
ELSE IF confidence_score 0.70–0.85:
  THEN flag for review (check confidence factors)
  AND allow with engineer sign-off
ELSE IF confidence_score 0.50–0.70:
  THEN flag for manual verification
  AND require design engineer review before use
ELSE IF confidence_score < 0.50:
  THEN BLOCK field
  AND require manual input or fallback rule
ENDIF
```

---

**Prepared by:** Source Mapping & Interoperability Agent  
**Status:** 🔴 ARCHITECTURE COMPLETE  

---
