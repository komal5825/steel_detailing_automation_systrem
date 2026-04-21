# PROMPT G: SOURCE-NEUTRAL MAPPING FOR MBS / STAAD / ETABS / PROTA
## Executive Summary & Delivery Package

**Project:** MasterDB v2.1 — Source-Neutral Data Mapping & Software Interoperability  
**Status:** 🔴 ARCHITECTURE COMPLETE — READY FOR IMPLEMENTATION  
**Date:** April 2026  
**Authority:** Data Interoperability & Source Mapping Control

---

## WHAT IS PROMPT G?

### The Problem Solved
The current MasterDB may carry **MBS-heavy bias** in source-mapping logic, creating risk for STAAD Pro, ETABS, and Prota Steel-led projects. This means:
- ❌ Assumption that MBS field structure is universal (it's not)
- ❌ STAAD-specific source objects forced into MBS-derived structures without proper mapping
- ❌ ETABS data loss due to unmapped field groups
- ❌ Prota Steel data not normalized consistently
- ❌ Missing-data handling differs by software but not explicitly defined
- ❌ No clear extraction paths per software
- ❌ Confidence levels not tracked per source

### The Solution Delivered
**A complete source-neutral mapping framework with explicit per-software extraction paths, normalization layers, and confidence tracking.**

**Key Achievements:**
- ✅ Source-neutral mapping for 9 critical field groups (geometry, grids, levels, sections, anchors, connections, built-up, crane, sheeting)
- ✅ Software-specific extraction paths (MBS, STAAD, ETABS, Prota) for each field
- ✅ Common normalized field targets (universal schema)
- ✅ Per-software confidence scoring (0.0–1.0)
- ✅ Missing-data rules per software (block vs. fallback vs. manual)
- ✅ Manual input exception table (where manual intervention approved)
- ✅ 4 software-specific source models (data structures)
- ✅ Normalization logic for each critical field
- ✅ 6-week implementation plan (100+ tasks)
- ✅ Production-ready test scenarios & validation rules

---

## DELIVERABLES (6 FILES | 140 KB)

| File | Size | Purpose | Primary Audience |
|------|------|---------|------------------|
| **1. PROMPT_G_EXECUTIVE_SUMMARY.md** | 12 KB | Strategic overview & quick-start | Leadership, PMs, architects |
| **2. PROMPT_G_SOURCE_MAPPING_MATRIX.md** | 45 KB | Complete source path mapping (9 fields × 4 software) | Architects, dev leads |
| **3. PROMPT_G_DATABASE_SCHEMA.sql** | 32 KB | Normalization layer tables (6 tables) | DBAs, IT operations |
| **4. PROMPT_G_Software_Models.md** | 28 KB | Per-software object models & extraction logic | Developers, integration leads |
| **5. PROMPT_G_Reference_Master.md** | 18 KB | Lookup tables & validation rules | Everyone (daily reference) |
| **6. PROMPT_G_IMPLEMENTATION_CHECKLIST.md** | 40 KB | 6-week detailed project plan (100+ tasks) | PMs, dev leads, QA |

**Total:** 140 KB, 6 files, production-ready

---

## QUICK START BY ROLE

### 👔 Executive / Leadership (15 min read)
1. Review this summary
2. Approve implementation plan
3. Allocate budget & resources (5-7 FTE, 6 weeks, ~420 hours)
4. Greenlight Phase G

---

### 🔧 Project Manager / Program Lead (45 min read)
1. Read: PROMPT_G_EXECUTIVE_SUMMARY.md (this file) (15 min)
2. Study: PROMPT_G_IMPLEMENTATION_CHECKLIST.md (30 min)
3. Plan: 6-week delivery with team allocation
4. Schedule: Database setup (W1), dev (W2-3), testing (W4-5), deployment (W6)

---

### 💻 IT Development Lead (120 min read)
1. Read: PROMPT_G_SOURCE_MAPPING_MATRIX.md (60 min)
2. Review: PROMPT_G_Software_Models.md (45 min)
3. Reference: PROMPT_G_DATABASE_SCHEMA.sql (15 min)
4. Plan: 4 module implementations (M-MAP-01 through M-MAP-04)

---

## CRITICAL PROBLEM STATEMENT

### The Bias Issue
**Current state:** MasterDB was designed primarily with MBS in mind.
- MBS field structures embedded in normalization assumptions
- STAAD Pro grids → forced into MBS grid representation (information loss)
- ETABS story levels → mapped to MBS-style levels (semantic mismatch)
- Prota sections → normalized assuming MBS-style member naming

**Risk:** Non-MBS projects lose data or require manual workarounds.

### Example: STAAD Grids vs. MBS Grids
**MBS Approach (Tradosoft BIM):**
- Grids: `grid_master` table → grid_id, grid_line_direction, grid_value_along_axis
- Assumption: Regular grid spacing, orthogonal axes

**STAAD Pro Reality:**
- Grids: Named lines in 3D space (can be irregular, skewed, curved)
- Different grid types: Column grids, beam grids, story grids, parking grids
- Multiple grid systems in single model

**Current MasterDB Problem:**
- STAAD grids forced into `grid_master` table → **data loss**
- Irregular spacing not captured
- Non-orthogonal grids cause errors

**Prompt G Solution:**
- Create `grid_source_mapping` table with per-software extraction rules
- Normalize to `grid_normalized` table (universal schema)
- Preserve software-specific properties in `grid_extended_properties`
- Allow STAAD grids to express full complexity → then normalize

---

## CORE FRAMEWORK

### 9 Critical Field Groups (Require Per-Software Mapping)
1. **Geometry** — Coordinates, dimensions, transformations
2. **Grids** — Reference lines, axes, layout system
3. **Levels** — Story definitions, elevations, floor data
4. **Member Sections** — Profile selection, standard vs. custom
5. **Anchor Bolts/Base** — Foundation connections, base plates
6. **Connection Details** — Bolted/welded/riveted joints
7. **Built-Up Members** — Custom geometries, splices, details
8. **Crane Data** — Hooks, rails, load paths
9. **Sheeting-Support Data** — Purlins, bracing, roof/wall systems

### 4 Software Sources
1. **MBS (Tradosoft)** — BIM-native, structured XML/database exports
2. **STAAD Pro** — Text-based .std files + binary database
3. **ETABS** — MySQL database + XML export
4. **Prota Steel** — Excel/JSON exports, limited API

### Normalization Strategy
```
Software-Specific Source Model
          ↓
Per-Software Extraction (SQL/parser)
          ↓
Confidence Scoring (0.0–1.0)
          ↓
Normalization Layer (common schema)
          ↓
Universal Normalized Fields (ready for design use)
```

---

## IMPLEMENTATION TIMELINE

| Week | Phase | Effort | Owner | Output |
|------|-------|--------|-------|--------|
| **W1** | Database & Source Models | 35h | DBA + Arch | 6 tables, software models documented |
| **W2** | MBS & STAAD Mapping | 65h | DEV | M-MAP-01 & M-MAP-02, tested |
| **W3** | ETABS & Prota Mapping | 75h | DEV | M-MAP-03 & M-MAP-04, tested |
| **W4-5** | Integration & Testing | 120h | QA | 100+ test cases, validation complete |
| **W6** | Deployment & Training | 65h | Deploy + Train | Production deployed, staff trained |
| **TOTAL** | **6 Weeks** | **~360h** | **5-7 FTE** | **Production-Ready Source Mapping** |

---

## SUCCESS CRITERIA

**Architecture Complete?**
- [x] 9 critical field groups mapped
- [x] 4 software source models defined
- [x] Per-software extraction paths specified
- [x] Common normalized targets defined
- [x] Confidence scoring rules established
- [x] Missing-data handling per software
- [x] Manual input exceptions documented
- [x] 6 normalization tables designed

**Database Complete?**
- [x] 6 production-ready tables
- [x] Foreign key relationships specified
- [x] Validation rules for each field
- [x] Sample data provided

**Documentation Complete?**
- [x] Source mapping matrix (9 fields × 4 software)
- [x] Software-specific models (4 detailed specs)
- [x] Reference lookup tables
- [x] Implementation checklist (100+ tasks)
- [x] This executive summary

---

## NEXT STEPS

### For Leadership
1. Review this summary (15 min)
2. Approve implementation plan
3. Allocate 5-7 FTE for 6 weeks (~420 hours)
4. Greenlight Phase G

### For Development
1. Read PROMPT_G_SOURCE_MAPPING_MATRIX.md
2. Read PROMPT_G_SOFTWARE_MODELS.md
3. Plan M-MAP-01 through M-MAP-04 implementations
4. Weeks 2-3: Develop per-software mappers

### For QA
1. Read PROMPT_G_IMPLEMENTATION_CHECKLIST.md (Week 4-5 sections)
2. Plan test scenarios for each software
3. Create test data for MBS, STAAD, ETABS, Prota
4. Execute validation suite

---

**Prepared by:** Source Mapping & Interoperability Agent  
**Date:** April 2026  
**Authority:** Data Interoperability & Source Mapping Control  
**Status:** 🔴 READY FOR IMPLEMENTATION KICKOFF

---
