# P7 — UI & CONTROL LAYER IMPLEMENTATION
## Infiniti Solutions Steel Detailing Automation — Phase 5 Desktop Build
**Document ID**: IFS-P7-UI-20260423  
**Authority Baseline**: IFS-RULE-REG-FINAL-20260423 · MasterDB v3+  
**Depends On**: P4, P5, P6  
**Status**: IMPLEMENTATION READY — UI Team Deliverable

---

## 1. ROLE-BASED SCREEN MAP

### 1.1 Role Definitions (from role_master)

| Role ID | Role Name | Override Authority | Gate Bypass | Release Authority |
|---|---|---|---|---|
| `drafter` | Drafter | Presentation-only | No | No |
| `checker` | Checker | Presentation + Review | No | No |
| `detailing_lead` | Detailing Lead | Review + Sequence | No | No |
| `design_engineer` | Design Engineer | With-Approval engineering | No | No |
| `pm` | Project Manager | Co-approval (quorum) | Co-approval with DE | Recommend only |
| `document_controller` | Document Controller | Metadata-only | No | No |
| `qc_lead` | QC Lead | QC status only | No | No |
| `it_admin` | IT Admin | System config only | No | No |

### 1.2 Screen Access Matrix

| Screen | Drafter | Checker | Det. Lead | Design Eng | PM | Doc. Ctrl | QC Lead | IT Admin |
|---|---|---|---|---|---|---|---|---|
| Project Dashboard | View | View | View+Edit | View | View | View | View | View |
| File Upload & Classification | View | View | Edit | View | View | View | — | Admin |
| Field Population Viewer | View | View | Edit (non-governing) | Edit | View | View | View | View |
| Validation Results | View | View | View | View+Act | View | View | View | View |
| Manual Review Queue | — | Resolve (minor) | Resolve | Resolve + Approve | View | — | View | View |
| Override Request | — | Submit (Review-only) | Submit + Approve (Review) | Submit + Approve | Co-approve | — | — | — |
| Approval Queue | — | — | — | Approve | Approve | — | — | — |
| Gate Status Panel | View | View | View | View+Act | View+Act | View | View | View |
| Stage Progress Tracker | View | View | View | View | View | View | View | View |
| Confidence Viewer | View | View | View | View | View | View | View | View |
| Audit Trail Viewer | View | View | View | View | View | View | View | Full |
| Benchmark Dashboard | — | View | View | View | View | — | View | Full |
| Defect Dashboard | View | View | View | View | View | — | View | Full |
| Release Control | — | — | — | Recommend | Recommend | Submit | Must pass QC | — |
| Rule Proposal Review | — | — | — | Approve/Reject | — | — | — | Notify |
| System Config | — | — | — | — | — | — | — | Full |

---

## 2. APPROVAL WORKFLOW SCREENS

### 2.1 Approval Queue Screen

**Who sees it**: Design Engineer, Project Manager (only see requests requiring their role)  
**Purpose**: Central queue for all pending approvals — overrides, gate bypasses, releases

**Layout**:
```
╔══════════════════════════════════════════════════════════╗
║  APPROVAL QUEUE                      [PROJECT: Q-157-Palghar]
║─────────────────────────────────────────────────────────
║  FILTER: [All Requests ▼]  [All Types ▼]  [PENDING ▼]
║─────────────────────────────────────────────────────────
║  ┌─────────────────────────────────────────────────────┐
║  │ 🔴 GATE BYPASS REQUEST — S4 (AB Hard Gate)          │
║  │  Requested by: PM (J. Sharma)  |  14:32 today       │
║  │  Reason: Client urgency — AB drawings needed in 2hr │
║  │  Required approvals: PM ✅  +  Design Engineer ⏳    │
║  │  [View Details] [APPROVE] [REJECT]                  │
║  └─────────────────────────────────────────────────────┘
║  ┌─────────────────────────────────────────────────────┐
║  │ 🟠 OVERRIDE REQUEST — member_section_size (F-063)   │
║  │  Member: C1 (Column) | Original: 200UC60            │
║  │  Proposed: 200UC52 | Reason: Stock availability     │
║  │  Required: Design Engineer approval + justification │
║  │  [View Details] [APPROVE WITH NOTES] [REJECT]       │
║  └─────────────────────────────────────────────────────┘
║  ┌─────────────────────────────────────────────────────┐
║  │ 🟡 RELEASE REQUEST — Final Drawing Package          │
║  │  S10 Gate: PASS | QC: PASS | All approvals complete │
║  │  Engineer final sign-off required for ZIP release   │
║  │  [Review Release Package] [APPROVE RELEASE] [HOLD]  │
║  └─────────────────────────────────────────────────────┘
║─────────────────────────────────────────────────────────
║  [3 pending approvals]  Last checked: 14:45
╚══════════════════════════════════════════════════════════╝
```

**Approval Detail Panel** (shown on click):
- Full field context: field name, field ID, current value, proposed value
- Source traceability: where current value came from (parser, file, confidence)
- Override rule reference: which override rule applies (R-228 to R-271)
- Evidence field (mandatory for engineering overrides): free text + file attachment
- Role confirmation: who else has approved (for quorum requirements)
- Audit preview: shows what will be written to audit_event_log on approve

### 2.2 Multi-Role Quorum Approval Screen

For S4/S5 gate bypass (requires simultaneous PM + Design Engineer per R-197):

```
╔══════════════════════════════════════════════════════════╗
║  GATE BYPASS APPROVAL — S4 (Anchor Bolt Gate)   🔴 HARD
║─────────────────────────────────────────────────────────
║  ⚠️  This is a HARD GATE. Both approvals required simultaneously.
║     Bypassing this gate carries engineering risk.
║─────────────────────────────────────────────────────────
║  GATE STATUS: FAIL (2 active blockers)
║  Blocker 1: R-123 — F-192 (bolt projection above FFL) UNRESOLVED
║  Blocker 2: RC-011 — Anchor bolt spacing X mismatch: DXF=150mm vs DB=175mm
║─────────────────────────────────────────────────────────
║  APPROVAL QUORUM REQUIRED:
║  [PM Approval]           ✅  J. Sharma — Approved 14:33
║  [Design Engineer]       ⏳  Awaiting — Not yet approved
║─────────────────────────────────────────────────────────
║  Engineering Justification (mandatory):
║  ┌──────────────────────────────────────────────────────┐
║  │ [Text field — minimum 50 characters required]       │
║  └──────────────────────────────────────────────────────┘
║  Supporting Evidence: [Attach File ▲]
║─────────────────────────────────────────────────────────
║  ⚠️  This approval will be permanently logged in audit trail.
║     It CANNOT be reversed. Downstream outputs will proceed with warnings.
║─────────────────────────────────────────────────────────
║  [APPROVE AS DESIGN ENGINEER]       [REJECT]
╚══════════════════════════════════════════════════════════╝
```

**UI Rules for Approval Screens**:
- `APPROVE` button is **disabled** until all required fields are filled
- For quorum approvals: `APPROVE` button remains **greyed** until the other role has also approved
- Approval confirmation modal: "This action is permanent and audit-logged. Confirm?"
- After approval: queue item shows green tick + who approved + timestamp
- No approval is hidden. All pending approvals visible to all roles (view access)

---

## 3. OVERRIDE REVIEW SCREENS

### 3.1 Override Request Submission Screen

**Triggered by**: Detailing Lead (review-only), Design Engineer (approval), or Drafter (presentation-only)

```
╔══════════════════════════════════════════════════════════╗
║  OVERRIDE REQUEST                    Field: F-063 member_section_size
║─────────────────────────────────────────────────────────
║  OVERRIDE STATUS: override-allowed-with-approval
║  Required role: Design Engineer (minimum)
║─────────────────────────────────────────────────────────
║  CURRENT VALUE                    SOURCE TRACEABILITY
║  200UC60                          Source: STAAD .std (P1)
║  Extracted: parser_P2-01          Confidence: 95%
║  File: Q157-Palghar-STAAD.std     Extracted: 14:10 today
║─────────────────────────────────────────────────────────
║  PROPOSED OVERRIDE
║  New Value: [200UC52          ]
║  Override Reason (mandatory):
║  [  Stock availability — 200UC60 not available. 200UC52 capacity verified.  ]
║
║  Supporting Evidence (mandatory for engineering override):
║  [Attach Calculation / Technical Memo ▲]  file.pdf ✅
║─────────────────────────────────────────────────────────
║  ⚠️  PROHIBITED FIELDS NEARBY (cannot be overridden):
║     F-067 member_mark — override-prohibited (for reference only)
║─────────────────────────────────────────────────────────
║  [SUBMIT FOR APPROVAL]   [CANCEL]
╚══════════════════════════════════════════════════════════╝
```

### 3.2 Override Registry View

Accessible by all roles (view). Shows all overrides for a project:

```
╔══════════════════════════════════════════════════════════╗
║  OVERRIDE REGISTRY — Q-157-Palghar
║─────────────────────────────────────────────────────────
║  FILTER: [All Types ▼] [All Fields ▼] [Date Range ▼]
║─────────────────────────────────────────────────────────
║  Field              | Original    | Override    | Status    | By
║  F-063 section_size | 200UC60     | 200UC52     | APPROVED  | DE: M.Patel
║  F-029 sheet_scale  | 1:100       | 1:50        | APPLIED   | Drafter: A.K
║  F-073 surface_trt  | Primer      | Galvanized  | APPROVED  | DE: M.Patel
║─────────────────────────────────────────────────────────
║  [3 approved overrides] [0 pending] [0 rejected]
║  [Export Override Log PDF]
╚══════════════════════════════════════════════════════════╝
```

### 3.3 Override-Prohibited Field Guard (UI Enforcement)

Fields with `override_status = 'override-prohibited'` must show a **red lock icon** and be non-editable in ALL views:

```
F-039 grid_spacing_x     🔒 [6000 mm]    [Override Prohibited — Cannot Edit]
F-067 member_mark        🔒 [C1A]        [Override Prohibited — Cannot Edit]
F-083 bolt_qty_per_col   🔒 [4]          [Override Prohibited — Cannot Edit]
```

Clicking the lock icon shows tooltip: "This field (F-039) is override-prohibited. It can only change by uploading a new design file and re-running ingestion."

---

## 4. CONFIDENCE AND SOURCE VISIBILITY DESIGN

### 4.1 Field Population Viewer

Shows all 196 fields with values, sources, and confidence for the current project:

```
╔══════════════════════════════════════════════════════════╗
║  FIELD POPULATION VIEWER — Q-157-Palghar        [Stage: S3]
║─────────────────────────────────────────────────────────
║  FILTER: [All Groups ▼] [All Statuses ▼] [Search field...]
║─────────────────────────────────────────────────────────
║  GROUP: GOVERNING ENGINEERING (28 fields)
║─────────────────────────────────────────────────────────
║  F-039  grid_spacing_x      🔒  6000 mm        STAAD P1   ██████████ 95%
║  F-040  grid_spacing_y      🔒  7500 mm        STAAD P1   ██████████ 95%
║  F-045  building_length     🔒  36000 mm       MBS P2     █████████░ 90%
║  F-046  building_width      🔒  22500 mm       MBS P2     █████████░ 90%
║  F-054  roof_slope_actual   🔒  1:10           STAAD P1   ██████████ 95%
║  F-063  member_section_size ⚠️  200UC52        STAAD P1   █████████░ 95%  [Override: Approved]
║  F-081  bolt_diameter       🔒  M20            STAAD P1   ██████████ 92%
║  F-082  bolt_grade          🔴  UNRESOLVED     —          ——————————  0%  [⚠ Review Required]
║─────────────────────────────────────────────────────────
║  GROUP: DERIVED (31 fields)
║─────────────────────────────────────────────────────────
║  F-070  weight_per_m        ✅  25.1 kg/m      Derived    ██████████ 98%
║  F-071  member_total_wt     ✅  628 kg         Derived    ██████████ 98%
║  F-057  roof_ridge_ht       ✅  7200 mm        Derived    ██████████ 98%
║─────────────────────────────────────────────────────────
║  GROUP: PRESENTATION (22 fields)
║─────────────────────────────────────────────────────────
║  F-028  sheet_size          ✅  A1             Template   ████████░░ 80%  [Editable: Drafter]
║  F-029  sheet_scale         ⚙️  1:50 (Override) Drafter   ——————————       [Override Applied]
║─────────────────────────────────────────────────────────
║  SUMMARY: 152/196 populated | 3 UNRESOLVED | 8 PENDING_REVIEW | 33 not-yet-extracted
╚══════════════════════════════════════════════════════════╝
```

**Confidence Colour Coding**:
- 🟢 90–100%: Green bar — high confidence
- 🟡 80–89%: Yellow bar — acceptable; no review required unless governing
- 🟠 70–79%: Orange bar — low confidence; review recommended
- 🔴 < 80% on governing field: Red bar + mandatory review badge
- ⬜ 0% / UNRESOLVED: Empty bar + red UNRESOLVED badge

### 4.2 Source Traceability Drill-Down

Clicking any field row opens the source traceability panel:

```
╔══════════════════════════════════════════════════════════╗
║  SOURCE TRACEABILITY — F-039 grid_spacing_x
║─────────────────────────────────────────────────────────
║  CURRENT VALUE: 6000 mm
║  STATUS: POPULATED  |  OVERRIDE PROHIBITED 🔒
║─────────────────────────────────────────────────────────
║  EXTRACTION HISTORY:
║  ┌───────────────────────────────────────────────────────┐
║  │ Source 1 (P1 — WINNER)                               │
║  │   Parser: STAAD .std Custom Parser                   │
║  │   File: Q157-Palghar-STAAD-Rev2.std                  │
║  │   Location: JOINT COORDINATES block, Line 47         │
║  │   Method: structured_keyword                         │
║  │   Raw value: "6000"  →  Normalised: "6000"           │
║  │   Confidence: 95%  |  Extracted: 14:10 today         │
║  ├───────────────────────────────────────────────────────┤
║  │ Source 2 (P2 — CONFLICT LOGGED, OVERRIDDEN BY P1)    │
║  │   Parser: MBS XML Parser                             │
║  │   File: Q157-MBS-Export.xml                          │
║  │   Location: /Building/GridSystem/XSpacing            │
║  │   Raw value: "6000"  →  Normalised: "6000"           │
║  │   Confidence: 90%  |  Agreement: ✅ MATCH with P1    │
║  └───────────────────────────────────────────────────────┘
║─────────────────────────────────────────────────────────
║  VALIDATION RESULT: PASS  |  Rule R-006 ✅  |  Rule RC-001 ✅ (DXF: 6001mm ±1mm)
║  [View Full Audit Trail]
╚══════════════════════════════════════════════════════════╝
```

### 4.3 UNRESOLVED Field Review Panel

For any field with status = UNRESOLVED:

```
╔══════════════════════════════════════════════════════════╗
║  ⚠️  UNRESOLVED FIELD — F-082 bolt_grade
║─────────────────────────────────────────────────────────
║  RULE TRIGGERED: FB-RULE-013 — STAAD Bolt Grade Missing
║  REASON: STAAD .std contains bolt diameter (M20) but no grade.
║          No other source has this value.
║─────────────────────────────────────────────────────────
║  PERMITTED ACTION:
║  This field is override-prohibited for auto-fill.
║  Manual input required from Design Engineer.
║─────────────────────────────────────────────────────────
║  ALLOWED VALUES: 4.6 | 5.6 | 8.8  (anchor bolt grades)
║  [  Select grade: ▼  ]
║
║  Source justification (mandatory):
║  [  Reference: STAAD design calculation sheet dated __  ]
║
║  ⚠️  Manual input will be logged as P5 (Manual) source.
║     Requires Design Engineer role to submit.
║─────────────────────────────────────────────────────────
║  [SUBMIT MANUAL INPUT]   [ESCALATE TO ENGINEER]   [CLOSE]
╚══════════════════════════════════════════════════════════╝
```

---

## 5. AUDIT VIEWER DESIGN

### 5.1 Audit Trail Viewer

**Access**: All roles (view). Full detail for IT Admin only.

```
╔══════════════════════════════════════════════════════════╗
║  AUDIT TRAIL — Q-157-Palghar          [IFS-AUDIT-VIEWER]
║─────────────────────────────────────────────────────────
║  FILTER: [Event Type ▼] [Field ▼] [Date Range ▼] [Agent ▼]
║─────────────────────────────────────────────────────────
║  14:45:22  GATE_STATUS_CHANGE   S4 (AB Gate)
║            Status: FAIL → PASS_WITH_BYPASS (PM+DE quorum)
║            Approvers: J.Sharma (PM), M.Patel (DE)
║            Blockers bypassed: R-123, RC-011
║            [VIEW FULL DETAIL ▸]
║
║  14:33:01  APPROVAL_GRANTED     Gate Bypass Request #007
║            Gate: S4 | Role: PM | J.Sharma
║            [VIEW FULL DETAIL ▸]
║
║  14:31:55  OVERRIDE_APPLIED     F-063 member_section_size
║            200UC60 → 200UC52 | DE: M.Patel | Justification attached
║            [VIEW FULL DETAIL ▸]
║
║  14:10:42  FIELD_POPULATED      F-039 grid_spacing_x
║            Value: 6000mm | Source: STAAD P1 | Conf: 95%
║            [VIEW FULL DETAIL ▸]
║
║  14:10:39  VALIDATION_RESULT    R-006 PASS — F-039
║            Stage: S3 | No blocker | [VIEW FULL DETAIL ▸]
║
║  14:09:55  AGENT_ACTION         P2-01 INGESTION Agent started
║            File: Q157-Palghar-STAAD-Rev2.std
║            [VIEW FULL DETAIL ▸]
║─────────────────────────────────────────────────────────
║  IMMUTABILITY NOTICE: This log is permanently stored and cannot
║  be modified or deleted. All events are timestamped and signed.
║─────────────────────────────────────────────────────────
║  [Export Audit PDF]   [Export CSV]   Total events: 847
╚══════════════════════════════════════════════════════════╝
```

### 5.2 Audit Event Detail View

```
╔══════════════════════════════════════════════════════════╗
║  AUDIT EVENT DETAIL  #1247
║─────────────────────────────────────────────────────────
║  Event Type:    OVERRIDE_APPLIED
║  Timestamp:     2026-04-23T14:31:55.441Z
║  Project:       Q-157-Palghar
║  Field:         F-063 member_section_size
║─────────────────────────────────────────────────────────
║  MANDATORY ATTRIBUTES (10/10 present ✅)
║  1. Field code:          F-063
║  2. Value:               200UC52
║  3. Source system:       STAAD P1 (original), DE Manual (override)
║  4. Source priority:     Override-with-approval
║  5. Extraction method:   manual_override
║  6. Transformation:      None
║  7. Validation result:   APPROVED by Design Engineer
║  8. Population timestamp: 2026-04-23T14:31:55Z
║  9. User/agent:          design_engineer:M.Patel
║  10. Traceability path:  STAAD→F-063→Override→DE-approval#006
║─────────────────────────────────────────────────────────
║  DATA SNAPSHOT: { original: "200UC60", overridden: "200UC52",
║    rule_applied: "R-228", approval_id: 6, evidence: "calc.pdf" }
║─────────────────────────────────────────────────────────
║  [Close]   [Share Event Link]
╚══════════════════════════════════════════════════════════╝
```

### 5.3 Validation Result Panel

Accessible from the Gate Status screen or directly from audit trail:

```
╔══════════════════════════════════════════════════════════╗
║  VALIDATION RESULTS — Gate S3 — Q-157-Palghar
║─────────────────────────────────────────────────────────
║  GATE STATUS: PASS WITH WARNINGS
║  Total Rules Checked: 180  |  Pass: 175  |  Warn: 4  |  Fail: 1
║─────────────────────────────────────────────────────────
║  🔴 BLOCKERS (0) — None
║─────────────────────────────────────────────────────────
║  🟠 ERRORS (1):
║     R-027  F-082 bolt_grade — Confidence 0% (UNRESOLVED)
║            Manual review required → T-015 triggered
║            [Open Review Panel ▸]
║─────────────────────────────────────────────────────────
║  🟡 WARNINGS (4):
║     R-089  F-041 grid_x_labels — Mixed alpha/numeric format
║     R-141  F-122 purlin_spacing — Near max allowable span
║     R-142  F-123 girt_spacing   — Within limits; wind load review
║     R-092  F-025 sheet_sequence — Gap at sheet 3; auto-resequence?
║            [Approve Auto-Resequence]
║─────────────────────────────────────────────────────────
║  🟢 PASS (175) — All other rules passed
║─────────────────────────────────────────────────────────
║  [Export Validation Report PDF]   [Re-Run Gate]
╚══════════════════════════════════════════════════════════╝
```

---

## 6. BENCHMARK / DEFECT DASHBOARD DESIGN

### 6.1 Project Benchmark Dashboard

**Access**: Detailing Lead, Design Engineer, PM, IT Admin

```
╔══════════════════════════════════════════════════════════╗
║  BENCHMARK DASHBOARD — Infiniti Solutions Steel System
║─────────────────────────────────────────────────────────
║  ACCURACY OVERVIEW (Last 30 completed projects)
║─────────────────────────────────────────────────────────
║  Overall Accuracy:   ████████░░  82.4%  (Target: 80-88%)
║  AB Drawings:        █████████░  88.1%  (Target: 78-90%) ✅
║  GA Drawings:        ████████░░  81.3%  (Target: 75-88%) ✅
║  Shop Drawings:      ███████░░░  74.2%  (Target: 65-82%) ✅
║  Sheeting:           ████████░░  83.7%  (Target: 75-88%) ✅
║  Shipping:           █████████░  89.4%  (Target: 85-94%) ✅
║─────────────────────────────────────────────────────────
║  STAGE PERFORMANCE
║  S1 Intake:      PASS rate: 98.2%   Avg blockers: 0.1
║  S2 Template:    PASS rate: 94.7%   Avg blockers: 0.3
║  S3 Fields:      PASS rate: 78.3%   Avg blockers: 2.1  ← Review
║  S4 AB Gate:     PASS rate: 88.4%   Avg blockers: 0.8
║  S5 GA Gate:     PASS rate: 85.1%   Avg blockers: 1.1
║─────────────────────────────────────────────────────────
║  TOP DEFECT FIELDS (Last 30 projects)
║  1. F-082 bolt_grade          18 defects — STAAD incomplete
║  2. F-084 bolt_spacing_x      12 defects — STAAD incomplete
║  3. F-063 member_section (BuiltUp) 9 defects — plate data absent
║  4. F-054 roof_slope_actual    7 defects — format violations
║─────────────────────────────────────────────────────────
║  ROLLOUT STATUS: Phase 5 build | Projects completed: 7/50 reference jobs
║─────────────────────────────────────────────────────────
║  [View All Projects]  [Export Report]  [Compare vs Targets]
╚══════════════════════════════════════════════════════════╝
```

### 6.2 Defect Dashboard

```
╔══════════════════════════════════════════════════════════╗
║  DEFECT DASHBOARD                          [All Projects]
║─────────────────────────────────────────────────────────
║  FILTER: [Project ▼] [Stage ▼] [Defect Type ▼] [Severity ▼]
║─────────────────────────────────────────────────────────
║  DEFECT LIST:
║  Q-157-Palghar  S4  F-082 UNRESOLVED   EXTRACTION_ERROR    🔴
║  Q-157-Palghar  S3  F-054 format       FORMAT_VIOLATION     🟡
║  Q-144-Mumbai   S5  F-063 mismatch     SECTION_LOOKUP_ERROR 🟠
║  Q-144-Mumbai   S3  F-082 UNRESOLVED   EXTRACTION_ERROR     🔴
║  Q-138-Pune     S7  F-159 violation    BOLT_PITCH_FAIL      🟠
║─────────────────────────────────────────────────────────
║  PATTERN DETECTION:
║  ⚠️  F-082 UNRESOLVED appears in 5 projects this month.
║     Rule Proposal Candidate: Review STAAD bolt table handling.
║     [View Rule Proposal Queue]
║─────────────────────────────────────────────────────────
║  RESOLUTION STATUS:
║  Open: 3  |  In Review: 2  |  Resolved: 47  |  Escalated: 1
║─────────────────────────────────────────────────────────
║  [Export Defect Log]   [Create Rule Proposal]
╚══════════════════════════════════════════════════════════╝
```

### 6.3 Rule Proposal Review Screen

For Level 1 Learning — Engineering sign-off required before any rule activates:

```
╔══════════════════════════════════════════════════════════╗
║  RULE PROPOSAL REVIEW                    PENDING SIGN-OFF
║─────────────────────────────────────────────────────────
║  PROPOSAL #003  |  Triggered by: 6 F-082 correction events
║─────────────────────────────────────────────────────────
║  FIELD: F-082 bolt_grade
║  TRIGGER: STAAD bolt grade absent in 6 projects this month.
║           Pattern: grade always 8.8 when diameter = M24 in similar AB drawings.
║─────────────────────────────────────────────────────────
║  CURRENT RULE: FB-RULE-013
║    "If STAAD has diameter but no grade → UNRESOLVED; BLOCK AB drawing"
║
║  PROPOSED CHANGE (NOT YET ACTIVE):
║    "If STAAD has diameter but no grade AND similar projects (ChromaDB similarity > 85%)
║     → Suggest grade as Level 2 suggestion with confidence score.
║     Grade still requires manual engineer confirmation."
║─────────────────────────────────────────────────────────
║  ⚠️  HARD RULE: This rule will NOT change until approved.
║     FB-RULE-013 remains active until engineering sign-off.
║─────────────────────────────────────────────────────────
║  Engineering Review Notes:
║  [                                                      ]
║─────────────────────────────────────────────────────────
║  [APPROVE RULE CHANGE]   [REJECT]   [DEFER — NEED MORE DATA]
╚══════════════════════════════════════════════════════════╝
```

---

## 7. RELEASE CONTROL VIEW

### 7.1 Gate Status Pipeline Panel

The primary project tracking view — visible to all roles:

```
╔══════════════════════════════════════════════════════════╗
║  PIPELINE STATUS — Q-157-Palghar         [Live Updates via WebSocket]
║─────────────────────────────────────────────────────────
║  PHASE 2 — PER PROJECT PIPELINE
║
║  S1 Intake Readiness         ✅ PASS           14:05
║  S2 Template Applicability   ✅ PASS           14:08
║  S3 Field Population         ⚠️ PASS+WARN (4)  14:45  [Review Warnings]
║       ↓
║  S4 AB Output Readiness      🔴 FAIL           14:47  [View Blockers]
║       ★ HARD GATE — All downstream blocked until PASS
║
║  S5 GA Output Readiness      🚫 BLOCKED (by S4)
║  S6 Sheeting Readiness       🚫 BLOCKED (by S4)
║  S7 Shop Output Readiness    🚫 BLOCKED (by S4)
║  S8 Shipping Readiness       🚫 BLOCKED (by S4)
║  S9 Installation Readiness   🚫 BLOCKED (by S4)
║
║  S10 Release Readiness       🚫 BLOCKED (by S4)
║─────────────────────────────────────────────────────────
║  CURRENT BLOCKERS AT S4:
║  🔴 R-123: F-192 (bolt_projection_above_FFL) — UNRESOLVED
║  🔴 RC-011: Anchor bolt spacing X mismatch (DXF=150mm vs DB=175mm)
║─────────────────────────────────────────────────────────
║  ACTIONS:
║  [Resolve F-192 → Open Field Review]
║  [Resolve RC-011 → Open DXF Comparison Viewer]
║  [Request Gate Bypass (PM+DE quorum required)]
║─────────────────────────────────────────────────────────
║  AUTO-REFRESH: ON  |  Last updated: 14:47:33
╚══════════════════════════════════════════════════════════╝
```

### 7.2 Final Release Gate Screen (S10)

**Access**: Design Engineer (recommend) + PM (recommend) + Document Controller (submit) + QC Lead (QC confirmation)

```
╔══════════════════════════════════════════════════════════╗
║  FINAL RELEASE GATE — S10                Q-157-Palghar
║─────────────────────────────────────────────────────────
║  PRE-RELEASE CHECKLIST (All must be ✅ before release)
║─────────────────────────────────────────────────────────
║  ✅ S7 Shop Drawing Gate:        PASS
║  ✅ S8 Shipping Gate:            PASS
║  ✅ S9 Installation Gate:        PASS
║  ✅ P3-05 Supervisor Agent:      PASS (all cross-output checks)
║  ✅ QC Status:                   PASS — QC Lead: R.Nair 14:52
║  ✅ Approved By (F-035):         M.Patel (Design Engineer)
║  ✅ Approval Date (F-036):       2026-04-23
║  ✅ No Active Release-Blockers:  0 blockers
║  ✅ All Override Approvals:      Complete (3 overrides documented)
║  ✅ Audit Trail Complete:        847 events / All 10 attributes
║  ✅ Release Authority Confirmed: J.Sharma (PM) + M.Patel (DE) confirmed
║─────────────────────────────────────────────────────────
║  OUTPUT FORMAT SELECTION:
║  ☑ DWG files       ☑ PDF files      ☑ DXF files
║  ☑ Shipping XLSX   ☑ Validation Report PDF
║  ☑ Audit Trail PDF ☑ Full ZIP package
║─────────────────────────────────────────────────────────
║  DRAWING COUNT:
║  AB: 3 sheets | GA: 6 sheets | Shop: 24 sheets | Sheeting: 2 | Install: 4
║  Total: 39 drawings | Est. ZIP size: 145 MB
║─────────────────────────────────────────────────────────
║  ⚠️  RELEASE IS PERMANENT. Once issued, this revision is LOCKED.
║     A new revision must be raised to make further changes.
║─────────────────────────────────────────────────────────
║  FINAL APPROVAL:
║  Design Engineer: M.Patel  ✅ Approved 14:52
║  PM: J.Sharma              ✅ Approved 14:53
║─────────────────────────────────────────────────────────
║                    [🔓 APPROVE RELEASE — GENERATE OUTPUT]
║  [HOLD — Raise Query]                          [REJECT]
╚══════════════════════════════════════════════════════════╝
```

### 7.3 Output Generation Status Screen

After release is approved:

```
╔══════════════════════════════════════════════════════════╗
║  OUTPUT GENERATION IN PROGRESS — Q-157-Palghar
║─────────────────────────────────────────────────────────
║  DXF Generation (ezdxf)        ████████████████░░░ 82%  Running
║  DWG Export (ODA Converter)    ██████░░░░░░░░░░░░░ 32%  Running
║  PDF Generation                ░░░░░░░░░░░░░░░░░░░  0%  Waiting
║  Shipping XLSX                 ████████████████████100% ✅ Complete
║  Validation Report PDF         ████████████████████100% ✅ Complete
║  Audit Trail PDF               ████████████████████100% ✅ Complete
║  ZIP Packaging                 ░░░░░░░░░░░░░░░░░░░  0%  Waiting
║─────────────────────────────────────────────────────────
║  Output Location: /Q-157-Palghar/Outputs/PACKAGE.zip
║  Estimated completion: ~3 minutes
║─────────────────────────────────────────────────────────
║  [Cancel — HOLD generation]
╚══════════════════════════════════════════════════════════╝
```

### 7.4 Project Creation Screen

**First human interaction point** — creates project, uploads files, triggers ingestion:

```
╔══════════════════════════════════════════════════════════╗
║  NEW PROJECT — Infiniti Solutions Steel Detailing
║─────────────────────────────────────────────────────────
║  Proposal ID:      [Q-157        ]   (e.g. Q-157)
║  Project Location: [Palghar      ]   (e.g. Palghar)
║  Project Name:     [ABC Warehouse]
║  Client Code:      [CLI-042      ]
║  Building Type:    [Warehouse ▼  ]
║  Design Standard:  [IS-Indian ▼  ]   ← Sets section DB and bolt specs
║  Unit System:      [Metric ▼     ]   ← IMMUTABLE ONCE SET ⚠️
║  Wind Speed:       [120 km/h     ]
║  Seismic Category: [Zone II ▼    ]
║─────────────────────────────────────────────────────────
║  ⚠️  Unit System cannot be changed after project creation.
║─────────────────────────────────────────────────────────
║  UPLOAD DESIGN FILES:
║  [+ Add Files ▲]
║  Q157-STAAD-Rev2.std     ✅  STAAD Pro      P1  [Remove]
║  Q157-MBS-Export.xml     ✅  MBS Export     P2  [Remove]
║  Q157-ETABS-Reactions.xlsx ✅ ETABS Excel  P3  [Remove]
║  Q157-Prota-DXF.dxf      ✅  Prota DXF     P4  [Remove]
║  Q157-Prota-Loads.pdf    ✅  Prota PDF      P5  [Remove]
║  Q157-Archive.zip        ⏳  Extracting...     [Remove]
║─────────────────────────────────────────────────────────
║  [CREATE PROJECT & START INGESTION]   [Cancel]
╚══════════════════════════════════════════════════════════╝
```

---

## UI GLOBAL RULES

**No hidden approvals**: Every approval request, decision, and override is visible to all roles (at minimum view access). Nothing is processed invisibly.

**Immediate blocker visibility**: Active Release-Blockers display as RED badges in the header bar of every screen within a project — not just the gate screen.

**Full visibility of source and confidence**: No field value is shown without its source, priority rank, and confidence percentage. Every user can always see WHERE a value came from.

**Blocker badge in header** (appears on all project screens when blockers are active):
```
╔══╗  Q-157-Palghar  |  S4 BLOCKED  🔴 2 RELEASE BLOCKERS  [View ▸]
```

**WebSocket live updates**: Gate status, approval queue, and pipeline progress update in real time via FastAPI WebSocket connection. No page refresh required.

**Audit trail entry on every UI action**: Every click on APPROVE, REJECT, SUBMIT, OVERRIDE generates an audit event before the action is applied. UI shows "Logging to permanent audit trail..." confirmation before finalization.

---

*P7 — UI & Control Layer Implementation | IFS-P7-UI-20260423 | UI Team Deliverable | Phase 5 Desktop Build*
