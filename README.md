# Infiniti Solutions — Steel Detailing Multi-Agent System

> **Local-First Desktop Automation | Design File is the Base Source of Truth | No API Dependency**

[![Status](https://img.shields.io/badge/Status-Architecture%20Approved-green)]()
[![Version](https://img.shields.io/badge/Version-v1.0%20April%202026-blue)]()
[![Stack](https://img.shields.io/badge/Stack-Python%20·%20LangGraph%20·%20FastAPI%20·%20React-navy)]()

---

## What This System Does

A desktop-based multi-agent automation system that reads engineering design files (MBS, STAAD Pro, ETABS, Prota Steel) and generates, validates, and packages the complete steel detailing drawing set:

- **AB Drawings** — Anchor Bolt plans (Plan + Section + Detail views)
- **GA Drawings** — General Arrangement (Plan + Elevations + Sections)
- **Shop/Detail Drawings** — Fabrication-ready member drawings
- **Sheeting & BOQ** — Roof and wall sheeting output
- **Shipping List** — Mark-wise dispatch control
- **Installation Drawings** — Erection sequence and placement
- **Release Package** — Full ZIP with DWG + PDF outputs

All outputs are generated **only after** a gated, validated, traceable pipeline completes and the engineer approves the final release.

---

## Governing Principle

> **The design file is the absolute source of truth for all engineering values.**
> Historical job data is used only for template learning, field mapping conventions, and pattern recognition.
> Historical data must never override live design file values.

---

## Architecture Overview

### Three-Phase Structure

```
PHASE 1 (One-time + Periodic)
  Master Database Creation from 50 reference jobs
  └── P1-01: Template Extraction
  └── P1-02: Field Dictionary
  └── P1-03: Source Mapping Rules
  └── P1-04: Validation & Override Rules
  └── P1-05: Master DB Consolidator
      ↓ PostgreSQL + ChromaDB (Shared Memory)

PHASE 2 (Per Project — Sequential Gate-by-Gate)
  └── P2-01: Design File Ingestion
  └── P2-02: Design Completeness Check
  └── P2-03: AB Generation          ← 3 views: Plan, Section, Detail
  └── P2-04: GA Generation          ← ONLY after AB approved (sequential)
  └── P2-05: AB/GA Validation Gate  ← HARD GATE: all Phase 3 blocked on fail

PHASE 3 (Per Project — Only after P2-05 PASS)
  └── P3-01: Sheeting Generation
  └── P3-02: Shop/Detail Drawing Generation
  └── P3-03: Shipping List Generation
  └── P3-04: Installation/Erection Drawing Generation
  └── P3-05: Final End-to-End Checking (Supervisor)
      ↓
  Engineer Final Approval
      ↓
  OUTPUT GENERATION (DXF → DWG → PDF → ZIP)
```

### Why AB → GA Sequential (Not Parallel)?

AB drawing contains the bolt layout, grid positions, and base plate references.
GA plan view **directly inherits** the AB grid as fixed references.
If AB changes after GA is generated, GA must regenerate from scratch.
Running them in parallel would risk GA using a grid that doesn't match the approved AB.

---

## Technology Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| Backend API | FastAPI (Python) | REST + WebSocket |
| Agent Orchestration | LangGraph | State machine, node = agent |
| LLM Engine | Ollama + Llama 3 / Mistral | Local, no API key |
| Structured DB | PostgreSQL | All project data, rules, learning |
| Vector DB | ChromaDB (local) | Project profile embeddings |
| DXF Generation | ezdxf | Programmatic DXF from structured data |
| DWG Export | ODA File Converter (free) | DXF → DWG R2018 |
| PDF Generation | ezdxf + matplotlib | No extra license |
| DWG/DXF Reading | ezdxf + ODA | Read existing CAD files |
| PDF Parsing | pdfplumber + PyMuPDF | Text + image PDFs |
| OCR | Tesseract | Image-only PDFs (lowest confidence) |
| Archive Handling | zipfile + rarfile | ZIP + RAR recursive extraction |
| Frontend | React + TailwindCSS | Live tracking dashboard |
| Live Updates | WebSocket (FastAPI → React) | Real-time stage status |
| Background Jobs | Celery + Redis (local) | Async execution + retry queue |
| STAAD Parser | Custom Python | .std format (highest priority) |
| ETABS Parser | openpyxl + pandas | Excel export format |
| MBS Parser | Custom XML/text | MBS export format |
| Prota Steel Parser | ezdxf + pdfplumber | DXF exports + PDF reports |

---

## Database Structure

### PostgreSQL Tables

**Project Management**
```
projects           — project_uuid (PK), proposal_id (e.g. Q-157), name, location, type, status
files              — file_internal_id (PK), project_uuid (FK), filename, type, classification, revision
project_stages     — stage_id, project_uuid, stage_code (P2-01 etc.), status, start/end time
stage_checkpoints  — checkpoint_id, stage_id, state_snapshot_json, rollback_available
handoff_packages   — package_id, stage_id, output_summary, status, downstream_eligible
validation_results — result_id, stage_id, field_code, design_value, generated_value, status
escalations        — escalation_id, stage_id, type (engineering/IT), reason, severity, status
correction_events  — event_id, project_uuid, stage_id, field_code, original_value, corrected_value
output_packages    — output_id, project_uuid, output_type, file_paths_json, release_status
```

**Master DB (Phase 1 Outputs)**
```
template_library      — template families, output class mapping, title blocks, layout rules
field_dictionary      — all fields with type, unit, source, mandatory/optional, validation refs
source_mapping_rules  — per-field extraction logic, authority hierarchy, fallback/block rules
validation_rules      — rule ID, category, severity, pass/fail/warn logic, block decisions
override_rules        — conflict resolution hierarchy, source precedence, mandatory review
rule_proposals        — proposed rule changes from Level 1 learning, status, approved_by
```

### File Storage
```
/Project_UUID/
  Raw_Inputs/    ← All uploaded files, preserved as-is
  Processed/     ← Parsed/normalized intermediate data files
  Outputs/
    AB/           ← ab.dxf, ab.dwg, ab.pdf
    GA/           ← ga.dxf, ga.dwg, ga.pdf
    SHOP/         ← shop.dxf, shop.dwg, shop.pdf
    SHEETING/     ← sheeting.dxf, sheeting_list.pdf
    SHIPPING/     ← shipping.xlsx, shipping.pdf
    INSTALLATION/ ← install.dxf, install.dwg, install.pdf
    REPORTS/      ← validation_report.pdf, audit_trail.pdf
    PACKAGE.zip   ← Full release package
  Logs/           ← Stage logs, audit trail, error reports
```

### ChromaDB (Vector DB — local)
Stores project profile embeddings for Level 2/3 learning.
Linked to PostgreSQL via `project_uuid`.
Updated only when a project receives FINAL APPROVED status.

---

## Three-Level Learning System

### Level 1 — Rule Refinement *(Automatic detection, Human approval)*
1. Fallback agent activates → event logged to `correction_events`
2. Learning Agent reads events periodically → groups by `field_code`
3. When count >= 5 → proposes rule update → writes to `rule_proposals`
4. UI notification → Engineer reviews diff (old rule vs proposed)
5. Engineer approves → rule updates `validation_rules` | Rejects → archived

**HARD RULE: No rule changes without engineering sign-off.**

### Level 2 — Smart Suggestions *(AI suggests, Human always decides)*
1. Missing field detected during completeness check or generation
2. ChromaDB similarity search → top-3 similar approved projects
3. LLM generates suggestion with confidence score
4. UI popup: *"Missing: Bolt Size. Suggested: M20 (12 similar jobs, 87% confidence). [Accept] [Reject]"*
5. Accepted value flagged in traceability as "Level 2 suggestion — engineer approved"

### Level 3 — Pattern Learning *(Layout/template guidance only)*
1. Project receives FINAL APPROVED status
2. Learning Agent extracts project profile → ChromaDB vector embedding
3. New project → similarity search → template family suggestions in UI
4. Engineer reviews and selects template

**HARD RULE: Level 3 never overrides template_library standards or design file values.**

---

## Validator & Fallback Agent Pattern

Every stage has a **Validator Agent** immediately after it:

```
Stage Agent runs
    ↓
Validator Agent checks all field values vs validation_rules
    ↓
PASS  → Stage status = PASS, handoff created, downstream proceeds
    ↓
FAIL  → Fallback Agent triggered (ONE attempt)
          ↓
          Targeted re-extraction/regeneration of failed fields only
          ↓
          Validator re-runs
          ↓
          PASS → Stage status = PASS (logged as corrected)
          FAIL → ESCALATE to engineer (no further auto-retry)
```

**Why only one attempt?** Unlimited retries loop on bad inputs instead of surfacing the real problem. One attempt catches extraction artifacts. A second failure means the root cause requires human judgment.

---

## Stage Status Model

| Status | Meaning |
|--------|---------|
| **PASS** | Stage complete. Handoff approved. Downstream may proceed. |
| **PASS WITH WARNINGS** | Complete with non-critical issues. Warnings carried forward and tracked. |
| **FAIL** | Invalid output. Downstream blocked. Fallback triggered. |
| **BLOCKED** | Stage did not execute — prerequisite inputs missing. |
| **ESCALATE — ENGINEERING** | Domain ambiguity, missing governing field, conflicting engineering interpretation. |
| **ESCALATE — IT/DATA** | Parsing failure, file classification error, source mapping failure. |
| **RE-RUN REQUIRED** | Must re-execute after correction. Clean inputs verified. |
| **REJECTED** | Package unacceptable. Full correction required. |

---

## Human Interaction Points

| Point | Trigger | Action Required |
|-------|---------|----------------|
| Project Creation | Always | Enter project details, upload files |
| P2-01 Revision Conflict | Multiple design candidates | Select governing design file from ranked list |
| P2-02 Missing Fields | Critical field absent | Provide value or confirm alternate source |
| Level 2 Suggestions | Missing field has similar-project match | Accept or Reject suggested value per field |
| Fallback Escalation | Two consecutive agent failures | Review failure report, provide correction |
| Phase 1 Rule Update | 10+ new approved projects | Review rule diff, approve or reject |
| Final Release Gate | P3-05 PASS | Review output summary, approve release, select formats |

---

## Data Extraction — Parser Priority

```
Priority: Design file structured data > CAD data > Text PDF > Image PDF

STAAD Pro (.std)  → Custom Python parser (HIGHEST PRIORITY — bolt table often incomplete)
MBS               → Custom XML/text parser
ETABS             → openpyxl + pandas (Excel export)
Prota Steel       → ezdxf (DXF) + pdfplumber (PDF reports)
DWG/DXF           → ODA File Converter + ezdxf
PDF (text)        → pdfplumber (SECONDARY only)
PDF (image)       → PyMuPDF + Tesseract OCR (LOWEST confidence — always flagged)
ZIP/RAR           → zipfile + rarfile (recursive extraction)
```

---

## Re-Run Cascade Rules

When an upstream stage is corrected or re-opened:

```
P2-01 changes governing source → P2-02 onward re-evaluated
P2-02 changes completeness     → P2-03, P2-04, P2-05 re-run
P2-03 AB changes               → P2-04 (GA regenerate), P2-05, ALL Phase 3
P2-04 GA changes               → P2-05, all geometry-dependent Phase 3
P2-05 fails / re-opened        → ALL Phase 3 blocked
P3-02 shop/detail changes      → P3-03, P3-04, P3-05 re-run
P3-03 shipping changes         → P3-04 (if seq-linked), P3-05
P3-04 installation changes     → P3-05
```

---

## Accuracy Expectations

| Stage | Expected Accuracy | Primary Risk |
|-------|-----------------|--------------|
| Phase 1 (DB creation) | 90–95% | Inconsistency in historical jobs |
| P2-01 Ingestion | 90–96% | Revision confusion |
| P2-02 Completeness | 85–93% | Incomplete design files |
| P2-03 AB Generation | 78–90% | STAAD bolt table completeness |
| P2-04 GA Generation | 75–88% | Geometry extraction |
| P3-01 Sheeting | 75–88% | Opening/interruption data |
| P3-02 Shop Drawings | 65–82% | Connection data complexity |
| P3-03 Shipping | 85–94% | Mark consistency |
| P3-04 Installation | 70–85% | Sequence logic |
| P3-05 Final Check | 80–90% | Upstream warning accumulation |
| **First Rollout** | **70–80%** | Combined input quality + parsers |
| **After Tuning** | **80–88%** | Standardized jobs improve faster |

---

## Immediate Next Steps for IT Team

1. Set up PostgreSQL with full schema
2. Install ChromaDB locally
3. Install ODA File Converter (free — opendesign.com)
4. Set up Ollama with Llama 3 / Mistral
5. **Build STAAD .std parser (highest priority)**
6. Build MBS XML/text parser
7. Build ETABS Excel export parser
8. Compile 50 reference jobs into controlled source folder
9. Run Phase 1 prompt pack → populate master DB → engineering validates
10. Build P2-01 Ingestion Agent
11. Build FastAPI backend + LangGraph orchestration
12. Build React frontend with WebSocket live tracking
13. Build P2-02 → P2-05 sequentially with validators and fallbacks
14. Test on 3 benchmark projects
15. Build Phase 3 agents: P3-01 → P3-02 → P3-03 → P3-04 → P3-05
16. Build Output Generator Agent (ezdxf → ODA → PDF)
17. Integrate Learning Agent (Level 1 first, then 2, then 3)
18. Full end-to-end test on 5 diverse project types
19. Deploy to production desktop

---

## Project ID Convention

Projects are stored as: `proposal_id-location` (e.g., `Q-157-Palghar`)

Every project gets a system-generated **internal UUID** as the immutable primary key for all database relationships. The proposal ID and location are user-entered display fields.

---

## Document Files

| File | Description |
|------|-------------|
| `Infiniti_Steel_Agent_Architecture_v1.0.docx` | Full formal architecture document (Word) |
| `Infiniti_Steel_Agent_System.html` | Interactive HTML version with SVG diagrams |
| `README.md` | This file — developer reference |
| `steel_agent_workflow_it_team.docx` | Original senior engineer workflow document |

---

## System Principles Checklist

- [x] Design file is the base source of truth
- [x] Historical data for templates and logic only — never overrides engineering values
- [x] No downstream generation on failed upstream
- [x] Validator at every critical stage
- [x] Fallback → one auto-retry → escalate on second fail
- [x] Local-first, no API dependency
- [x] Full traceability: every output traceable to input file, extraction rule, agent, stage, timestamp
- [x] Human approval required for all rule changes
- [x] AB must be approved before GA generation begins
- [x] Output files generated only after P3-05 PASS + engineer final approval

---

*Infiniti Solutions — Steel Detailing Automation Program | System Architecture Document v1.0 | April 2026 | CONFIDENTIAL — Internal Use Only*
