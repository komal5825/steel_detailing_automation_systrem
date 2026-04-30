# PROMPT F: REFERENCE MASTER & OPERATIONAL LOOKUP TABLES
## Complete Field Guide for Design Standard Governance

**Document:** PROMPT_F_Reference_Master  
**Status:** Production-Ready Lookup Reference  
**Date:** April 2026  
**Authority:** Engineering Standards & Design Control

---

## TABLE 1: DESIGN STANDARDS & SEISMIC CODES

### Overview
Three approved design standards govern all steel structure design in MasterDB:

| Design Standard | Design Code | Version | Seismic Code | Seismic Version | Design Method |
|---|---|---|---|---|---|
| **IS** | IS 800 | 2007 | IS 1893 | 2016 | Limit State Design (LSD) |
| **AISC** | AISC 360 | 2022 | AISC 341 + ASCE 7 | 2022 | Load & Resistance Factor Design (LRFD) |
| **EUROCODE** | EN 1993 | 2005 + A1:2013 | EN 1998 | 2004 + A1:2013 | Limit State Design (LSD) |

### Key Decision Points
**Point 1: Project Setup**  
Every project MUST declare ONE design standard at creation.  
**Consequence:** All section lookups, material grades, seismic provisions branch from this decision.

**Point 2: Seismic Requirement**  
IF project requires seismic design:  
- Declare seismic_required = TRUE
- Specify seismic_standard matching design_standard
- Enforce seismic-specific material & section requirements

**Point 3: Section Selection**  
Engineer selects section → system checks project.design_standard → routes to correct database.

**Point 4: Material Grade**  
Engineer specifies grade → system validates grade is valid for that standard.

---

## TABLE 2: SECTION ROUTING RULES (12 ROUTES PER STANDARD)

### IS (Indian Standards) — 12 Routes

| Section Type | Source Database | Lookup Table | Weight Method | Examples |
|---|---|---|---|---|
| Rolled I-Beam (Light) | ISC Catalog | isc_sections | CATALOG | ISC 75, ISC 100, ISC 125 |
| Rolled I-Beam (Medium) | ISC Catalog | isc_sections | CATALOG | ISC 150, ISC 200, ISC 250 |
| Rolled I-Beam (Heavy) | ISC Catalog | isc_sections | CATALOG | ISC 300, ISC 350, ISC 400 |
| Rolled H-Beam (Light) | ISMB Catalog | ismb_sections | CATALOG | ISMB 75, ISMB 100, ISMB 125 |
| Rolled H-Beam (Medium) | ISMB Catalog | ismb_sections | CATALOG | ISMB 150, ISMB 200, ISMB 250 |
| Rolled H-Beam (Heavy) | ISMB Catalog | ismb_sections | CATALOG | ISMB 300, ISMB 350, ISMB 400 |
| Channel (ISMC) | Channel Catalog | ismc_sections | CATALOG | ISMC 50, ISMC 75, ISMC 100 |
| Angle (ISA) | Angle Catalog | isa_sections | CATALOG | ISA 25×25, ISA 40×40, ISA 50×50 |
| Built-Up I-Section | Custom Geometry | builtup_geometry_master | GEOMETRY | BU-IS-250-200-10 |
| Built-Up Box Section | Custom Geometry | builtup_geometry_master | GEOMETRY | BU-BOX-200-200-8 |
| Built-Up Channel | Custom Geometry | builtup_geometry_master | GEOMETRY | BU-CHAN-150-75-6 |
| Other (Specialized) | Custom | Custom | FORMULA | Trusses, composite |

**Key Rule:** Built-up sections DO NOT use weight from rolled-section tables.  
Built-up weight = calculated from geometry: A × density (7850 kg/m³)

---

### AISC (American Standards) — 12 Routes

| Section Type | Source Database | Lookup Table | Weight Method | Examples |
|---|---|---|---|---|
| Wide Flange (W) — Light | W-Shape Catalog | w_shapes_light | CATALOG | W10, W12, W14 |
| Wide Flange (W) — Medium | W-Shape Catalog | w_shapes_medium | CATALOG | W16, W18, W21 |
| Wide Flange (W) — Heavy | W-Shape Catalog | w_shapes_heavy | CATALOG | W24, W27, W30, W36 |
| HP Pile (HP) | HP Catalog | hp_shapes | CATALOG | HP10×42, HP12×53, HP14×73 |
| Channel (C) | C-Shape Catalog | c_shapes | CATALOG | C3, C4, C5, C6, C7, C8, C9, C10, C12, C15 |
| Structural Angle (L) | Angle Catalog | l_shapes | CATALOG | L2×2, L3×3, L4×4 |
| Structural Tee (WT) | T-Section Catalog | wt_shapes | CATALOG | WT4, WT5, WT6 |
| Built-Up I-Section | Custom Geometry | builtup_geometry_master | GEOMETRY | BU-AIS-250-200-10 |
| Built-Up Box Section | Custom Geometry | builtup_geometry_master | GEOMETRY | BU-BOX-300-250-10 |
| Built-Up Channel | Custom Geometry | builtup_geometry_master | GEOMETRY | BU-CHAN-180-80-8 |
| Composite Beam (Deck) | Composite Catalog | composite_beams | FORMULA | CompositeW18+5 |
| Other (Cold-Formed) | Cold-Formed | cold_formed_shapes | CATALOG | C50×50×1.6 |

---

### EUROCODE — 12 Routes

| Section Type | Source Database | Lookup Table | Weight Method | Examples |
|---|---|---|---|---|
| UB (I-Beam) — Light | UB Catalog | ub_sections_light | CATALOG | 127×76, 152×89, 178×102 |
| UB (I-Beam) — Medium | UB Catalog | ub_sections_medium | CATALOG | 203×133, 254×146, 305×165 |
| UB (I-Beam) — Heavy | UB Catalog | ub_sections_heavy | CATALOG | 356×171, 406×178, 457×191 |
| UC (H-Beam) — Light | UC Catalog | uc_sections_light | CATALOG | 100×100, 120×120, 152×152 |
| UC (H-Beam) — Medium | UC Catalog | uc_sections_medium | CATALOG | 203×203, 254×254, 305×305 |
| UC (H-Beam) — Heavy | UC Catalog | uc_sections_heavy | CATALOG | 356×406, 406×406 |
| Channel (C) | C-Section Catalog | c_sections | CATALOG | 75×40, 100×50, 150×75 |
| Angle (L) | L-Section Catalog | l_sections | CATALOG | 40×40×4, 50×50×5, 100×100×10 |
| Built-Up I-Section | Custom Geometry | builtup_geometry_master | GEOMETRY | BU-EC-250-200-10 |
| Built-Up Box Section | Custom Geometry | builtup_geometry_master | GEOMETRY | BU-BOX-250-250-10 |
| Built-Up Truss | Custom Geometry | builtup_geometry_master | GEOMETRY | BU-TRUSS-6m-section |
| Other (Specialized) | Custom | Custom | FORMULA | Composite, CFS |

---

## TABLE 3: MATERIAL GRADE MAPPING MATRIX

### Grade Equivalences

| IS Grade | ASTM Grade | Eurocode Grade | fy (MPa) | fu (MPa) | Grade Group | Notes |
|---|---|---|---|---|---|---|
| IS 250B | ASTM A36 | S235 | 250 | 410 | **Economy** | Lowest cost; widely available |
| IS 250D | ASTM A50 | S275 | 250 | 400 | **General** | NDT-required; good ductility |
| IS 350A | ASTM A992 (Grade 50) | S355 | 350 | 450 | **High-Strength** | Most common in US; preferred seismic |
| IS 350C | ASTM A588 (Grade 50) | S355 | 350 | 450 | **Weathering** | For exposed steel; weathering protection |
| IS 500B | ASTM A514 (100 ksi) | S450 | 500 | 625 | **Very-High** | Heavy sections only; limited shapes available |

### Seismic Suitability

| Grade | IS 1893 | AISC 341 | EN 1998 | Recommendation |
|---|---|---|---|---|
| IS 250B / A36 / S235 | ✅ YES | ✅ YES | ✅ YES | Suitable for all seismic codes |
| IS 250D / A50 / S275 | ✅ YES | ✅ YES | ✅ YES | Preferred for seismic (good ductility) |
| IS 350A / A992 / S355 | ✅ YES | ✅ YES | ✅ YES | Preferred for high seismic zones |
| IS 350C / A588 / S355 | ✅ YES | ✅ YES | ✅ YES | Weathering for exposed; ok for seismic |
| IS 500B / A514 / S450 | ⚠️ CHECK | ✅ YES | ✅ YES | **NOT recommended for IS 1893 (brittle)** |

### Usage Rules

**RULE:** Material grade MUST be explicitly mapped in material_grade_mapping_master.  
**NO pattern matching allowed.** Use only grades from this matrix.

**Example:** Engineer selects "IS 250B" → system looks up mapping → returns "ASTM A36, S235"  
Engineer can then use any of: IS 250B, ASTM A36, or S235 (they are equivalent)

---

## TABLE 4: BUILT-UP SECTION VALIDATION LIMITS

### Slenderness Limits by Design Standard

| Parameter | IS 800 | AISC 360 | Eurocode 3 | What It Means |
|---|---|---|---|---|
| **Max b/(2×tf)** Compact | 10.5 | 8.5 (fy=250) | 9 | Flange local buckling limit |
| **Max h/tw** Plastic | 84 | 90 | 72 | Web local buckling limit |
| **Min tf** (Flange thickness) | 6 mm | 1/4" (6.35 mm) | 6 mm | Practical minimum |
| **Min tw** (Web thickness) | 5 mm | 3/16" (4.76 mm) | 5 mm | Practical minimum |

### Decision Tree for Slenderness

```
IF section is ROLLED:
  THEN use catalog values (no slenderness check needed)
ELSE IF section is BUILT-UP:
  THEN calculate b/(2×tf) and h/tw
    IF b/(2×tf) ≤ standard_limit:
      THEN PASS (compact section)
    ELSE IF b/(2×tf) ≤ 1.5 × standard_limit:
      THEN HOLD (non-compact; requires P3 review)
    ELSE:
      THEN BLOCK (slender section; cannot use)
    ENDIF
  ENDIF
ENDIF
```

### Class Definitions (Eurocode Specific)

| Section Class | b/(2tf) Limit | h/tw Limit | Design Method | Uses |
|---|---|---|---|---|
| **Class 1 (Plastic)** | ≤9 | ≤72 | Plastic section design | Moment-resisting frames |
| **Class 2 (Compact)** | ≤10 | ≤83 | Compact section design | General bending |
| **Class 3 (Semi-compact)** | ≤15 | ≤124 | Elastic design | Tension members |
| **Class 4 (Slender)** | >15 | >124 | Effective width method | Not recommended |

---

## TABLE 5: NON-STANDARD SECTION APPROVAL WORKFLOW

### Workflow Gates (Sequential)

#### Gate 1: Data Quality (DQE or P2) — 4-HOUR SLA

**What:** Initial data completeness check  
**Who:** Data Quality Engineer or P2 Structural Engineer  
**Pass Condition:**
- [ ] All geometry dimensions specified (b, tf, h, tw, r if welded)
- [ ] Material grade specified (IS / ASTM / Eurocode)
- [ ] Design standard declared (matches project)
- [ ] Fabrication method specified (WELDED / BOLTED / RIVETED)
- [ ] Section description clear & unambiguous

**Block Condition:**
- ❌ Missing any critical dimension
- ❌ Unspecified material grade
- ❌ Design standard not declared
- ❌ Description unclear or incomplete

**Escalation:** If SLA exceeded (>4 hours), escalate to P2 Engineer

---

#### Gate 2: Geometry Validation (P2 Engineer) — 24-HOUR SLA

**What:** Technical engineering review of geometry & slenderness  
**Who:** P2 Structural Engineer  
**Pass Condition:**
- [ ] All dimensions valid (positive, realistic ranges)
- [ ] Material grade valid for design standard
- [ ] Slenderness ratios within limits for that standard (see Table 4)
- [ ] No geometric impossibilities (e.g., tf > b/2)
- [ ] Connection type feasible (welding access, bolting feasibility)

**Hold Condition:** (Send to P3 for higher-level review)
- ⚠️ Slenderness non-compliant but potentially acceptable with P3 justification
- ⚠️ Non-standard material or connection type
- ⚠️ Unusually large or small dimensions

**Block Condition:**
- ❌ Slenderness > 2× standard limit (unacceptable)
- ❌ Material grade unsuitable for this section type
- ❌ Geometric impossibility
- ❌ Fabrication physically impossible

**Escalation:** If SLA exceeded or HOLD flagged, escalate to P3

---

#### Gate 3: Feasibility Review (P3 Principal Engineer) — 24-HOUR SLA (4H IF CRITICAL)

**What:** High-level engineering & fabrication feasibility assessment  
**Who:** P3 Principal or Geometry Engineer  
**Pass Condition:**
- [ ] Technically sound per design standard
- [ ] Shop has capability to fabricate (or design shop detail requirements)
- [ ] Code compliance verified (IS 800 / AISC 360 / EN 1993)
- [ ] No red flags for safety, durability, or cost

**Conditional Approval:** (Approved with conditions)
- ✅ Approved IF [condition]: e.g., "approved if welded per AWS D1.1"
- Conditions must be documented & verified before use

**Block Condition:**
- ❌ Unsafe geometry (unstable, high buckling risk)
- ❌ Shop cannot fabricate
- ❌ Code non-compliant; cannot be remedied
- ❌ Cost/schedule implications unacceptable

**Escalation:** If SLA exceeded, escalate to PM

---

#### Gate 4: Final Approval (Project Manager) — 24-HOUR SLA

**What:** Final business & schedule sign-off  
**Who:** Project Manager or Release Authority  
**Pass Condition:**
- [ ] All P2 & P3 approvals received
- [ ] No blockers or unresolved holds
- [ ] Cost/schedule implications acceptable
- [ ] Ready for design use

**Block Condition:**
- ❌ Unresolved P2 or P3 blockers
- ❌ Cost or schedule unacceptable
- ❌ Client has not approved non-standard section

**Sign-Off:** PM approval marks section as "APPROVED for design use"

**Escalation:** If SLA exceeded, escalate to Program Lead

---

### SLA Summary

| Stage | Owner | SLA | Escalation Path | Documentation |
|---|---|---|---|---|
| **Gate 1** | DQE/P2 | 4 hours | → P2 if no response | Notes on completeness |
| **Gate 2** | P2 | 24 hours | → P3 if HOLD or overdue | Slenderness check, material validation |
| **Gate 3** | P3 | 24 hours (4h if CRITICAL) | → PM if overdue | Feasibility & code compliance assessment |
| **Gate 4** | PM | 24 hours | → Program Lead if overdue | Final approval, cost/schedule sign-off |

---

## TABLE 6: SEISMIC DESIGN REQUIREMENTS BY CODE

### IS 1893:2016 (Indian Standards)

| Parameter | Value | Notes |
|---|---|---|
| **Design Method** | Zone-Based, Equivalent Lateral Force | Seismic zones: Zone II, III, IV, V |
| **Response Factor (R)** | 5–8 | Depends on structure type & ductility |
| **Material Grades** | IS 250B/D, IS 350A/C | IS 500B NOT recommended (brittle) |
| **Section Class** | Compact required (b/(2tf) ≤ 10.5, h/tw ≤ 84) | Per IS 800 Clause 3.7.2 |
| **Ductility Requirement** | Yield before brittle failure | Connection detailing critical |
| **Damping** | 5% | Material damping |

**Key Rule:** If IS 1893 seismic design required:  
- Material must be IS 250B/D or IS 350A/C (ductile)
- Section must be compact (not slender)
- Connection details must ensure ductile failure mode

---

### AISC 341 + ASCE 7-22 (American Standards)

| Parameter | Value | Notes |
|---|---|---|
| **Design Method** | Equivalent Lateral Force or Response Spectrum | Ground motion category based on site hazard |
| **Response Modification (R)** | 8–12 | Depends on SMRF, IMRF, CBF, or other system |
| **Material Grades** | ASTM A36, A50, A992 (Grade 50), A588 | A992 preferred; A36 allowed with limits |
| **Section Classes** | "Special" (very compact for SMRF); other for IMRF/CBF | Per AISC 341 Table C1.1 |
| **Ductility Requirement** | Full moment resistance in plastic hinge | Connection must achieve M = 1.25×Mp |
| **Damping** | 5% | Material damping |

**Key Rule:** If AISC 341 seismic design required:  
- SMRF (Special Moment Resisting Frame): A992 Grade 50, very compact sections
- IMRF (Intermediate MRF): A36 or A992 allowed
- CBF (Concentrically Braced): A992 or A588, compact sections

---

### EN 1998:2004 + A1:2013 (Eurocode 8)

| Parameter | Value | Notes |
|---|---|---|
| **Design Method** | Elastic spectrum, inelastic spectrum | Ground type A–E; damping 5% |
| **Behavior Factor (q)** | 4–8 | Depends on ductility class & system |
| **Ductility Classes** | **M (Moderate):** Class 2 sections; **H (High):** Class 1 sections | Per EN 1993-1-1 |
| **Material Grades** | S235, S275, S355, S450 | S355 recommended for high seismic |
| **Section Class** | Class 1 (plastic) for High Ductility; Class 2 for Moderate | h/tw & b/(2tf) limits per EN 1993 |
| **Importance Factor** | γI = 0.8–1.4 | Category I–IV depending on use |
| **Damping** | 5% | Material damping |

**Key Rule:** If EN 1998 seismic design required:  
- Ductility Class H: use Class 1 (plastic) sections, S355 or higher
- Ductility Class M: use Class 2 (compact) sections, S235 OK but S355 preferred
- Ground type (A–E) affects acceleration spectrum

---

## TABLE 7: QUICK DECISION MATRIX

### "Which Standard Should I Use?"

**Question 1: Where is the project located?**
- India → **IS 800** (mandatory)
- United States → **AISC 360** (mandatory)
- Europe / UK → **EN 1993 / BS 5950** (Eurocode) (mandatory)

**Question 2: Is the project in a seismic zone?**
- Yes, India → **IS 1893** (mandatory with IS 800)
- Yes, USA → **AISC 341 + ASCE 7** (mandatory with AISC 360)
- Yes, Europe → **EN 1998** (mandatory with EN 1993)
- No → No seismic design needed; skip this question

**Question 3: What type of steel section?**
- Rolled I-beam → Use rolled section catalog for selected standard
- Built-up section → Submit geometry for P2/P3 approval
- Non-standard → Follow non-standard approval workflow (4-gate process)

**Question 4: What material grade?**
- Select from approved grades (Table 3)
- System will validate grade is compatible with selected standard
- If grade appears in multiple standards, system will confirm you selected the right one

**Question 5: Is this a complex seismic design?**
- High seismic zone (Zone V / ASCE 7 D+ / EN 1998 Zone 4) → Involve P3 engineer early
- Connection details will be critical → Shop must be capable of special detailing
- Use moment-resisting frame (MRF) or special-strength considerations → Extra review

---

## TABLE 8: COMMON ERRORS & HOW TO FIX THEM

### Error 1: "Cannot find this material grade"
**Cause:** Grade name may be misspelled or use non-standard format  
**Fix:**
1. Check Table 3 (Material Grade Mapping)
2. Use EXACT grade name (e.g., "ASTM A36", not "A36" or "American A36")
3. Confirm grade is valid for your project's design standard

### Error 2: "Standard mismatch: grade is AISC but project is IS"
**Cause:** You selected a grade from the wrong standard family  
**Fix:**
1. If you want the equivalent grade in your standard, use Table 3
2. Example: Want ASTM A36 in an IS project? Use "IS 250B" (equivalent)

### Error 3: "Built-up section weight doesn't match my calculation"
**Cause:** Built-up weight is calculated from geometry, not from a table  
**Fix:**
1. Verify your geometry submission (b, tf, h, tw, r) is accurate
2. Calculation: A = 2×b×tf + (h-2×r)×tw, then weight = A × 7.85 kg/cm²
3. Hand-calculate and compare; they should match exactly

### Error 4: "Slenderness non-compliant — section blocked"
**Cause:** Your built-up section has h/tw or b/(2tf) > standard limit  
**Fix:**
1. Check Table 4 for your design standard's limits
2. EITHER increase thickness (tf or tw) OR reduce dimensions (b or h)
3. If marginal, submit with P3 concurrence (he can approve conditional exception)

### Error 5: "IS 500B not allowed for IS 1893 seismic design"
**Cause:** IS 500B is too brittle for seismic; only ductile grades approved  
**Fix:**
1. Switch to IS 250D or IS 350A (ductile grades)
2. Verify Table 6 for your seismic code's material restrictions

### Error 6: "Non-standard section rejected: missing P3 approval"
**Cause:** Your section went through all 4 gates but P3 had concerns  
**Fix:**
1. Contact P3 engineer; understand his specific concern
2. Address concern (geometry, material, fabrication) and resubmit
3. If concern is unresolvable, use a standard catalog section instead

---

## TABLE 9: APPROVAL ROLE AUTHORITY MATRIX

### Who Can Approve What?

| Decision | DQE | P2 | P3 | PM |
|---|---|---|---|---|
| **Source data quality** | ✅ Yes | ⚠️ Escalate to P2 | — | — |
| **Geometry validation** | — | ✅ Yes | ⚠️ Escalate if slender | — |
| **Non-standard geometry** | — | ✅ Review | ✅ Final approval | — |
| **Slender section exception** | — | — | ✅ Yes (with conditions) | — |
| **Material grade equivalence** | — | ✅ Yes | — | — |
| **Seismic code requirements** | — | — | ✅ Yes | — |
| **Final non-standard approval** | — | — | — | ✅ Yes |

### SLA by Role

| Role | SLA | Escalation If Exceeded |
|---|---|---|
| **DQE** | 4 hours | → P2 |
| **P2** | 24 hours | → P3 |
| **P3** | 24 hours (4h if CRITICAL) | → PM |
| **PM** | 24 hours | → Program Lead |

---

## TABLE 10: TROUBLESHOOTING & SUPPORT

### Issue: Can't find my section in the database

**Diagnose:**
1. Confirm design standard is correctly set (IS / AISC / EUROCODE)
2. Confirm section type is in the routing table for that standard
3. Check if section name matches catalog exactly (ISC 250 vs ISC-250 vs ISC250)

**Solution:**
- Try alternate section naming (with/without hyphens, abbreviations)
- If section truly unavailable: submit as non-standard section & go through approval workflow
- Contact support: provide section type, catalog source, properties

### Issue: Material grade not in equivalent mapping

**Diagnose:**
1. Grade may not be ISO standard or may be obsolete
2. Grade may be proprietary to specific mills

**Solution:**
- Use closest standard equivalent from Table 3
- Request P3 engineer to add new grade mapping (with mill certification)
- Alternatively, use a standard approved grade

### Issue: Slenderness exceeded, section blocked

**Diagnose:**
1. Verify slenderness calculation: b/(2×tf) and h/tw
2. Check standard limit in Table 4

**Solution:**
- Increase thickness (easier fix): increase tf or tw
- Reduce dimension: smaller b or h
- Request P3 exception (needs documentation of why exception is needed)

### Contact Information

**For Technical Questions:**  
Contact P3 Principal Engineer (check approval database for assigned contact)

**For Non-Standard Submission Issues:**  
Contact your project's Design Lead; escalate to PM if stuck

**For Database Lookup Issues:**  
Contact IT support; include exact error message & section details

---

## APPENDIX: EXAMPLE WORKFLOWS

### Example 1: Simple IS Project, Rolled I-Beam

**Inputs:**
- Project: PROJ-2026-001 (IS standard, no seismic)
- Section: ISC 200

**Workflow:**
```
1. Project standard = IS ✅
2. Section lookup → Design standard IS + Section type "Rolled I-Beam"
3. Route to: ISC Catalog (isc_sections table)
4. Find: ISC 200 properties (A, Ixx, weight, etc.)
5. Material: IS 250B (use CATALOG lookup)
6. Weight: from isc_sections table (no calculation needed)
7. Result: Section approved for design use ✅
```

---

### Example 2: AISC Project, Custom Built-Up Section

**Inputs:**
- Project: PROJ-2026-002 (AISC standard, no seismic)
- Custom built-up: b=250mm, tf=12mm, h=400mm, tw=8mm, fy=Grade 50 (A992)

**Workflow:**
```
1. Project standard = AISC ✅
2. Section lookup → "Built-Up I-Section"
3. Route to: Geometry Calculator (builtup_geometry_master)
4. Submit geometry:
   - Flange: 250×12 mm
   - Web: 400×8 mm (clear height)
   - Material: ASTM A992 (fy=350 MPa)
5. Gate 1 (DQE): All dimensions present, grade valid → PASS ✅
6. Gate 2 (P2): 
   - b/(2×tf) = 250/(2×12) = 10.4 < 8.5 limit → COMPACT ✅
   - h/tw = 400/8 = 50 < 90 limit → PASS ✅
   - Weight calculated: A=2×250×12+(400-0)×8=8400 mm²; W=8400×7.85/1000=65.9 kg/m ✅
7. Gate 3 (P3): Feasibility review → shop can weld, code compliant → APPROVED ✅
8. Gate 4 (PM): Final sign-off → APPROVED for design use ✅
```

---

### Example 3: Eurocode Project, Seismic Design, Non-Standard Section

**Inputs:**
- Project: PROJ-2026-003 (Eurocode, IS 1998 seismic, Ductility Class H)
- Trying to use: IS 500B (high strength)

**Workflow:**
```
1. Project standard = EUROCODE ✅
2. Seismic required = YES, code = EN 1998 ✅
3. Material check: IS 500B selected
   - But project uses Eurocode (not IS)
   - Need Eurocode equivalent: S450
   - S450 for EN 1998 Ductility Class H? ✅ (S355 or S450 OK)
   - Convert to S450 for Eurocode project
4. Section lookup → "Built-Up I-Section"
5. Geometry submitted; goes through 4-gate approval process
6. Gate 2 (P2): Check Class 1 (plastic) limits for H-ductility
   - EN 1993 Class 1: b/(2tf) ≤ 9, h/tw ≤ 72
   - Must verify built-up section meets these (tighter than for non-seismic)
7. Gate 3 (P3): High-ductility seismic → confirm ductility achieved by connection design
8. Approval: CONDITIONAL — "Approved if welded connections designed per EN 1998 Annex J"
9. Result: Section OK for use WITH documented connection design ✓
```

---

**Prepared by:** Engineering Standards & Design Control Agent  
**Status:** 🔴 PRODUCTION-READY REFERENCE  

---
