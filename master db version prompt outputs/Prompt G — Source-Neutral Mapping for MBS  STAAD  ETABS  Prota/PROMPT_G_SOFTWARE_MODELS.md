# PROMPT G: PER-SOFTWARE SOURCE MODELS & EXTRACTION LOGIC
## Software-Specific Data Structures & Normalization Paths

**Status:** Architecture Complete | Date: April 2026

---

## SOFTWARE 1: MBS (TRADOSOFT BIM)

### Data Model Overview
**Source:** Structured database export (XML or SQL)
**Structure:** Relational with BIM hierarchy (Project → Building → Levels → Members)
**Availability:** All fields typically present (BIM-native)
**Confidence:** Generally high (0.90–0.98)

### Core Tables (MBS Source Model)
```
projects
├── project_id (PK)
├── project_name
└── export_date

levels
├── level_id (PK)
├── project_id (FK)
├── level_elevation_m
├── level_name
└── floor_type (FLOOR / ROOF / MEZZANINE)

grids
├── grid_id (PK)
├── project_id (FK)
├── grid_direction (X / Y / Z)
├── grid_values (coordinates along direction)
└── grid_spacing_m

members
├── member_id (PK)
├── level_id (FK)
├── node_start_id, node_end_id
├── section_id (FK to sections table)
├── member_type (COLUMN / BEAM / BRACE)
├── material_grade
├── length_m
└── member_properties (A, I, r, weight)

nodes
├── node_id (PK)
├── x_global, y_global, z_global
├── grid_intersections (which grid lines pass through)
└── member_connectivity

sections
├── section_id (PK)
├── section_name
├── section_type (STANDARD / BUILT_UP)
├── profile_category (I_BEAM / H_BEAM / BOX / ANGLE / CHANNEL / CUSTOM)
├── material_grade
├── area_cm2, ixx_cm4, iyy_cm4, radius_gyr_cm, weight_kg_m
└── built_up_geometry_id (FK if custom)

builtup_geometry
├── buildup_id (PK)
├── flange_width_mm, flange_thickness_mm
├── web_height_mm, web_thickness_mm
├── fillet_radius_mm
└── calculated_properties

anchor_bolts
├── anchor_id (PK)
├── support_node_id (FK)
├── bolt_size_mm, bolt_count, bolt_grade
├── bolt_pattern
├── base_plate_size_mm, base_plate_thickness_mm
└── foundation_type

connections
├── connection_id (PK)
├── member1_id (FK), member2_id (FK)
├── connection_type (BOLTED / WELDED / RIVETED)
├── bolt_size_mm, bolt_count, bolt_grade
├── weld_size_mm, weld_type
└── gusset_thickness_mm

crane_data
├── crane_id (PK)
├── rail_beam_member_id (FK)
├── hook_capacity_kn
├── load_case_id
└── mono_vs_double_rail

sheeting_support
├── sheeting_id (PK)
├── purlin_member_id (FK)
├── span_mm, spacing_mm
├── load_case_id
└── design_load_kpa
```

### MBS Extraction Logic (M-MAP-01)
```sql
-- Example: Extract members with sections & properties
SELECT 
  m.member_id, m.member_name, m.level_id,
  n_s.x_global, n_s.y_global, n_s.z_global,  -- Start node
  n_e.x_global, n_e.y_global, n_e.z_global,  -- End node
  s.section_id, s.section_name, s.material_grade,
  s.area_cm2, s.ixx_cm4, s.radius_gyr_cm, s.weight_kg_m
FROM members m
JOIN nodes n_s ON m.node_start_id = n_s.node_id
JOIN nodes n_e ON m.node_end_id = n_e.node_id
JOIN sections s ON m.section_id = s.section_id
WHERE m.project_id = ?
```

### MBS Confidence Rules
- **Coordinates:** 0.95–0.98 (BIM typically precise)
- **Sections:** 0.96–0.98 (database stored values)
- **Connections:** 0.93–0.96 (explicit connection records)
- **Crane/Sheeting:** 0.90–0.94 (optional, may be incomplete)

---

## SOFTWARE 2: STAAD PRO

### Data Model Overview
**Source:** Text file (.std) + binary database
**Structure:** Sequential text commands; members by ID; properties by MEMBER PROPERTY commands
**Availability:** Often incomplete (basic structural model)
**Confidence:** Medium (0.75–0.92)

### STAAD File Format (Text Representation)
```
PROJECT NAME MYPROJECT
DEFINE GRID ID 1 X COORDINATES 0 5 10 15 20
DEFINE GRID ID 2 Y COORDINATES 0 6 12 18
DEFINE GRID ID 3 Z COORDINATES 0 3.6 7.2 10.8

JOINT 101 0 0 0
JOINT 102 5 0 0
JOINT 103 10 0 0

MEMBER 1 JOINT 101 102
MEMBER 2 JOINT 102 103

MEMBER PROPERTY CONSTANTS
MATERIAL STEEL
MEMBER 1 SECTION ISC 200
MEMBER 2 SECTION ISC 250

SUPPORT 101 FIXED
SUPPORT 103 FIXED

PRINT MEMBER PROPERTIES
```

### STAAD Extraction Logic (M-MAP-02)
```python
def extract_staad_members():
    """Parse STAAD .std file"""
    members = {}
    with open('model.std') as f:
        for line in f:
            if line.startswith('JOINT'):
                parts = line.split()
                joint_id = parts[1]
                x, y, z = float(parts[2]), float(parts[3]), float(parts[4])
                joints[joint_id] = {'x': x, 'y': y, 'z': z}
                
            elif line.startswith('MEMBER ') and 'JOINT' in line:
                parts = line.split()
                member_id = parts[1]
                joint_start = parts[3]
                joint_end = parts[4]
                members[member_id] = {
                    'node_start': joint_start,
                    'node_end': joint_end
                }
                
            elif 'SECTION' in line:
                parts = line.split()
                if parts[0] == 'MEMBER' and len(parts) > 2:
                    member_id = parts[1]
                    section_name = parts[3]  # e.g., "ISC 200"
                    members[member_id]['section'] = section_name
    
    return members, joints
```

### STAAD Data Gaps
- ❌ No explicit crane modeling (load cases only)
- ❌ Limited built-up section support
- ❌ Connection details external (not in .std file)
- ❌ Sheeting/purlins implicit (member naming only)
- ❌ Anchor bolt details absent (SUPPORT lines only)

### STAAD Confidence Rules
- **Coordinates:** 0.92 (from JOINT commands; precision OK)
- **Grids:** 0.90 (from DEFINE GRID; may be incomplete)
- **Sections:** 0.88–0.92 (section names parsed; verify in database)
- **Connections:** 0.70–0.75 (RELEASE lines only; no bolt details)
- **Crane/Sheeting:** 0.50–0.65 (inferred; not modeled)

---

## SOFTWARE 3: ETABS (COMPUTER & STRUCTURES, INC.)

### Data Model Overview
**Source:** MySQL database + XML export
**Structure:** Relational with hierarchical stories, frames
**Availability:** Medium-high (more complete than STAAD)
**Confidence:** Medium-high (0.78–0.93)

### ETABS Database Tables (Query from MySQL)
```sql
-- Story/Level Information
SELECT StoryID, StoryName, Elevation, Height FROM Story;

-- Grid Definition
SELECT GridID, GridType, GridLine, Ordinate FROM GridData;

-- Members (Frame Elements)
SELECT FrameID, Story, GridPoint1, GridPoint2, Section FROM FrameElems;

-- Section Properties
SELECT SectionName, Material, Type FROM SectionProps;

-- Point Coordinates
SELECT PointID, X, Y, Z FROM PointCoordinates;

-- Supports
SELECT PointID, U1, U2, U3, R1, R2, R3 FROM Support;
```

### ETABS Extraction Logic (M-MAP-03)
```sql
-- Example: Get all members with coordinates
SELECT 
  fe.FrameID, fe.Story, fe.Section,
  pc1.X as X_start, pc1.Y as Y_start, pc1.Z as Z_start,
  pc2.X as X_end, pc2.Y as Y_end, pc2.Z as Z_end,
  sp.SectionName, sp.Material
FROM FrameElems fe
JOIN PointCoordinates pc1 ON fe.GridPoint1 = pc1.PointID
JOIN PointCoordinates pc2 ON fe.GridPoint2 = pc2.PointID
JOIN SectionProps sp ON fe.Section = sp.SectionID
ORDER BY fe.Story, fe.FrameID;
```

### ETABS Data Gaps
- ❌ Limited built-up section modeling
- ❌ Connection details minimal (rigid/pinned only)
- ❌ Crane modeling basic
- ❌ Anchor bolt data incomplete
- ⚠️ Some properties in unstructured notes field

### ETABS Confidence Rules
- **Coordinates:** 0.90–0.93 (MySQL stored; generally reliable)
- **Grids:** 0.88–0.91 (GridData table present)
- **Levels/Stories:** 0.91–0.93 (Story table explicit)
- **Sections:** 0.85–0.90 (SectionProps table; verify references)
- **Supports:** 0.80–0.85 (Support table; only fixity defined)
- **Connections:** 0.70–0.78 (rigid link or notes; limited modeling)

---

## SOFTWARE 4: PROTA STEEL

### Data Model Overview
**Source:** Excel (.xlsx) export or JSON
**Structure:** Tabular worksheets; limited relational structure
**Availability:** Limited (basic structural data)
**Confidence:** Low-medium (0.65–0.88)

### Prota Worksheet Structure
```
Worksheet: Levels
  Level | Elevation (m) | Name | Type | Notes

Worksheet: Grids
  Grid | Direction | Coordinates | Spacing | Type

Worksheet: Members
  ID | Member Type | Section | Material | Start (X,Y,Z) | End (X,Y,Z)
  | Connection Type | Splice | Notes

Worksheet: Sections
  Section | Type | Size | Grade | Custom(Y/N) | Built-up Details

Worksheet: Anchor Bolts
  Node | Bolt Size | Bolt Count | Grade | Pattern | Base Plate Size

Worksheet: Connections
  Member1 | Member2 | Type | Bolt/Weld Details | Gusset Thickness
```

### Prota Extraction Logic (M-MAP-04)
```python
import openpyxl

def extract_prota_members():
    wb = openpyxl.load_workbook('prota_model.xlsx')
    
    members = {}
    ws = wb['Members']
    for row in ws.iter_rows(min_row=2, values_only=True):
        member_id, member_type, section, material, x_start, y_start, z_start = row[:7]
        members[member_id] = {
            'type': member_type,
            'section': section,
            'material': material,
            'start': (x_start, y_start, z_start)
        }
    
    return members
```

### Prota Data Gaps
- ❌ Limited coordinate system support (may use local coords)
- ❌ Minimal connection modeling
- ❌ Built-up sections rare
- ❌ Crane modeling absent
- ❌ Sheeting/bracing limited
- ⚠️ Bolt/weld details in text notes (unstructured)

### Prota Confidence Rules
- **Coordinates:** 0.82–0.88 (Excel input; verify system)
- **Sections:** 0.80–0.85 (predefined catalog)
- **Members:** 0.78–0.85 (basic geometry)
- **Anchors:** 0.70–0.78 (if defined; often incomplete)
- **Connections:** 0.65–0.72 (text notes; unstructured)
- **Crane/Sheeting:** 0.50–0.65 (rarely present)

---

## NORMALIZATION FLOW DIAGRAM

```
MBS Export (SQL/XML)     STAAD File (.std)     ETABS DB (MySQL)     Prota Export (.xlsx)
    ↓                          ↓                      ↓                        ↓
[M-MAP-01]              [M-MAP-02]            [M-MAP-03]            [M-MAP-04]
MBS Parser              STAAD Parser          ETABS Query           Prota Parser
(confidence 0.95)       (confidence 0.88)     (confidence 0.90)     (confidence 0.78)
    ↓                          ↓                      ↓                        ↓
Extraction w/           Extraction w/         Extraction w/         Extraction w/
Confidence Scoring      Confidence Scoring    Confidence Scoring    Confidence Scoring
    ↓                          ↓                      ↓                        ↓
┌───────────────────────────────────────────────────────────────┐
│  NORMALIZATION LAYER (Common Schema)                          │
│  ├─ geometry_normalized                                       │
│  ├─ grid_normalized                                           │
│  ├─ level_normalized                                          │
│  ├─ section_normalized                                        │
│  ├─ anchor_bolt_normalized                                    │
│  ├─ connection_normalized                                     │
│  ├─ buildup_normalized                                        │
│  ├─ crane_normalized                                          │
│  └─ sheeting_normalized                                       │
│                                                               │
│  Each record: [field_value, confidence_score, source_id]     │
└───────────────────────────────────────────────────────────────┘
    ↓
[Design Use: Prompts A–F + Supervisory Validation (E)]
```

---

**Prepared by:** Data Interoperability Agent | Status: ARCHITECTURE COMPLETE

---
