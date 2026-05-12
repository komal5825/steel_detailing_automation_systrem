"""
Derived Field Calculator — Phase 2 Field Completion Engine.

Computes fields whose derived_type is 'calculated', 'lookup', or 'auto-generated'
from already-resolved extraction values.  Every field attempted is logged;
no silent skips are permitted.

Public API
----------
DerivedFieldCalculator(resolved_map, db, project_id).calculate_all()
    → dict[field_code, DerivedResult]
"""
from __future__ import annotations

import datetime
import sqlite3
from dataclasses import dataclass, field as dc_field
from uuid import UUID

from sqlalchemy.orm import Session

from app.utils.audit_logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class DerivedResult:
    field_code: str
    value: str | None
    method: str          # formula used
    resolved: bool
    note: str


# ---------------------------------------------------------------------------
# Derived field catalogue
# Field code → (method_name, description)
# ---------------------------------------------------------------------------
_DERIVED_CATALOGUE: dict[str, str] = {
    "F-018": "document_sheet_count",
    "F-030": "sheet_page_number",        # system auto-generated
    "F-049": "number_of_bays_x",
    "F-050": "number_of_bays_y",
    "F-057": "roof_ridge_height",        # extracted; recalculate if missing
    "F-068": "member_full_mark",
    "F-070": "member_weight_per_unit",
    "F-071": "member_weight_total",
    "F-096": "sheeting_zone_area",
    "F-097": "sheeting_sheet_count",
    "F-102": "detail_mark_position",
    "F-103": "member_mark_auto",
    "F-106": "hole_diameter",
    "F-110": "bundle_total_weight",
    "F-117": "assembly_weight",
    "F-130": "mezzanine_area",
    "F-154": "revision_history_display",
    "F-164": "connection_bolt_pitch",
    "F-169": "bolt_group_eccentricity",
    "F-174": "number_of_bays_x_verified",
    "F-175": "bay_sum_check_x",
    "F-182": "crane_minimum_clearance",
    "F-190": "buildup_weight_per_metre",
    "F-196": "sheeting_panel_run_length",
}


class DerivedFieldCalculator:
    """
    Compute derived fields from the resolved extraction map.

    Parameters
    ----------
    resolved_map : dict[str, ConflictResult]
        Output of build_resolved_field_map().  Used as source for all
        calculation inputs.
    db : Session
        SQLAlchemy session (used for master-DB lookups).
    project_id : UUID
        For logging context.
    """

    def __init__(self, resolved_map: dict, db: Session, project_id: UUID) -> None:
        self._r = resolved_map          # field_code → ConflictResult
        self._db = db
        self._project_id = project_id
        self._results: dict[str, DerivedResult] = {}

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def calculate_all(self) -> dict[str, DerivedResult]:
        """Attempt every derived field.  Always returns an entry for each."""
        for fc, method in _DERIVED_CATALOGUE.items():
            try:
                result = self._dispatch(fc, method)
            except Exception as exc:
                logger.warning("Derived calc failed for %s (%s): %s", fc, method, exc)
                result = DerivedResult(
                    field_code=fc,
                    value=None,
                    method=method,
                    resolved=False,
                    note=f"Exception during calculation: {exc}",
                )
            self._results[fc] = result
        return self._results

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def _dispatch(self, fc: str, method: str) -> DerivedResult:
        dispatch_map = {
            "document_sheet_count":    self._document_sheet_count,
            "sheet_page_number":       self._sheet_page_number,
            "number_of_bays_x":        self._number_of_bays_x,
            "number_of_bays_y":        self._number_of_bays_y,
            "roof_ridge_height":       self._roof_ridge_height,
            "member_full_mark":        self._member_full_mark,
            "member_weight_per_unit":  self._member_weight_per_unit,
            "member_weight_total":     self._member_weight_total,
            "sheeting_zone_area":      self._sheeting_zone_area,
            "sheeting_sheet_count":    self._sheeting_sheet_count,
            "detail_mark_position":    self._detail_mark_position,
            "member_mark_auto":        self._member_mark_auto,
            "hole_diameter":           self._hole_diameter,
            "bundle_total_weight":     self._bundle_total_weight,
            "assembly_weight":         self._assembly_weight,
            "mezzanine_area":          self._mezzanine_area,
            "revision_history_display":self._revision_history_display,
            "connection_bolt_pitch":   self._connection_bolt_pitch,
            "bolt_group_eccentricity": self._bolt_group_eccentricity,
            "number_of_bays_x_verified": self._number_of_bays_x_verified,
            "bay_sum_check_x":         self._bay_sum_check_x,
            "crane_minimum_clearance": self._crane_minimum_clearance,
            "buildup_weight_per_metre":self._buildup_weight_per_metre,
            "sheeting_panel_run_length":self._sheeting_panel_run_length,
        }
        fn = dispatch_map.get(method)
        if fn is None:
            return DerivedResult(
                field_code=fc, value=None, method=method, resolved=False,
                note="No calculation method registered",
            )
        return fn(fc)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get(self, fc: str) -> str | None:
        """Return the winning value for a field code, or None."""
        cr = self._r.get(fc)
        return (cr.winning_value or "").strip() if cr else None

    def _float(self, fc: str) -> float | None:
        v = self._get(fc)
        try:
            return float(v) if v else None
        except (ValueError, TypeError):
            return None

    def _ok(self, fc: str, value: str, note: str) -> DerivedResult:
        return DerivedResult(field_code=fc, value=value, method="", resolved=True, note=note)

    def _fail(self, fc: str, method: str, note: str) -> DerivedResult:
        return DerivedResult(field_code=fc, value=None, method=method, resolved=False, note=note)

    # ------------------------------------------------------------------
    # Individual calculators
    # ------------------------------------------------------------------

    def _document_sheet_count(self, fc: str) -> DerivedResult:
        """F-018: number of drawing sheets = number of distinct drawing_class values extracted."""
        from app.db.models import ExtractedFieldValue
        count = (
            self._db.query(ExtractedFieldValue)
            .filter(
                ExtractedFieldValue.project_id == self._project_id,
                ExtractedFieldValue.field_code == "F-020",
            )
            .count()
        )
        if count > 0:
            return self._ok(fc, str(count), f"Counted {count} F-020 (drawing_class) extractions")
        # fallback: report 1 sheet
        return self._ok(fc, "1", "Defaulting to 1 sheet (no drawing class records found)")

    def _sheet_page_number(self, fc: str) -> DerivedResult:
        """F-030: auto-generated by system at rendering time."""
        return self._ok(fc, "AUTO", "System-generated page number — assigned at PDF render time")

    def _number_of_bays_x(self, fc: str) -> DerivedResult:
        """F-049: count of bay spacings along X from F-039."""
        v = self._get("F-039")
        if not v:
            return self._fail(fc, "count(F-039)", "F-039 (bay_spacing_x) not available")
        bays = [x for x in v.split(",") if x.strip()]
        return self._ok(fc, str(len(bays)), f"Counted {len(bays)} bay spacings in F-039")

    def _number_of_bays_y(self, fc: str) -> DerivedResult:
        """F-050: count of bay spacings along Y from F-040."""
        v = self._get("F-040")
        if not v:
            return self._fail(fc, "count(F-040)", "F-040 (bay_spacing_y) not available")
        bays = [x for x in v.split(",") if x.strip()]
        return self._ok(fc, str(len(bays)), f"Counted {len(bays)} bay spacings in F-040")

    def _roof_ridge_height(self, fc: str) -> DerivedResult:
        """F-057: roof_ridge_height = eave_height + (slope * half_span)."""
        v = self._get("F-057")
        if v:
            return self._ok(fc, v, "Directly extracted from surface shape section")
        eave = self._float("F-056")
        slope = self._float("F-054")
        span = self._float("F-059")
        if eave is not None and slope is not None and span is not None:
            ridge = eave + slope * (span / 2.0)
            return self._ok(fc, f"{ridge:.1f}", "Calculated: eave + slope × (span/2)")
        return self._fail(fc, "eave + slope × half_span",
                          "Missing F-056 (eave_height), F-054 (slope), or F-059 (span)")

    def _member_full_mark(self, fc: str) -> DerivedResult:
        """F-068: project_code + '-' + member_mark."""
        proj = self._get("F-001")
        mark = self._get("F-067")
        if proj and mark:
            return self._ok(fc, f"{proj}-{mark}", "Concatenated F-001 + F-067")
        if mark:
            return self._ok(fc, mark, "F-001 missing; using F-067 alone")
        return self._fail(fc, "F-001+F-067", "F-067 (member_mark) not available")

    def _member_weight_per_unit(self, fc: str) -> DerivedResult:
        """F-070: lookup kg/m from steel_section_master by section size."""
        section = self._get("F-063")
        if not section:
            return self._fail(fc, "steel_section_lookup(F-063)",
                              "F-063 (member_section_size) not available")
        try:
            from app.config.settings import settings
            from pathlib import Path
            master_path = Path(settings.master_db_path)
            if not master_path.is_absolute():
                master_path = Path.cwd() / master_path
            with sqlite3.connect(str(master_path)) as conn:
                row = conn.execute(
                    "SELECT weight_per_metre FROM steel_section_master WHERE section_name = ?",
                    (section.strip(),),
                ).fetchone()
            if row and row[0]:
                return self._ok(fc, str(row[0]),
                                f"Lookup steel_section_master for '{section}'")
        except Exception as exc:
            logger.debug("steel_section_master lookup failed: %s", exc)
        return self._fail(fc, "steel_section_lookup",
                          f"Section '{section}' not found in steel_section_master")

    def _member_weight_total(self, fc: str) -> DerivedResult:
        """F-071: weight_per_unit × length × quantity."""
        wpu = self._float("F-070")
        length_mm = self._float("F-066")
        qty = self._float("F-069")
        if wpu and length_mm and qty:
            total_kg = wpu * (length_mm / 1000.0) * qty
            return self._ok(fc, f"{total_kg:.2f}",
                            "F-070 × (F-066/1000) × F-069 [kg]")
        return self._fail(fc, "F-070 × F-066 × F-069",
                          f"Missing: F-070={wpu}, F-066={length_mm}, F-069={qty}")

    def _sheeting_zone_area(self, fc: str) -> DerivedResult:
        """F-096: building_length × building_width [m²]."""
        length = self._float("F-045")
        width = self._float("F-046")
        if length and width:
            area_m2 = (length * width) / 1_000_000.0  # mm² → m²
            return self._ok(fc, f"{area_m2:.2f}", "F-045 × F-046 [m²]")
        return self._fail(fc, "F-045 × F-046", "F-045 or F-046 not available")

    def _sheeting_sheet_count(self, fc: str) -> DerivedResult:
        """F-097: zone_area / 3.0 m² nominal sheet (placeholder heuristic)."""
        area_str = self._get("F-096")
        if not area_str:
            area_m2 = None
        else:
            try:
                area_m2 = float(area_str)
            except ValueError:
                area_m2 = None
        if area_m2 is None:
            # Try direct calculation
            length = self._float("F-045")
            width = self._float("F-046")
            if length and width:
                area_m2 = (length * width) / 1_000_000.0
        if area_m2:
            sheets = max(1, round(area_m2 / 3.0))  # 3 m² per sheet heuristic
            return self._ok(fc, str(sheets), f"Estimated {sheets} sheets from {area_m2:.1f} m²")
        return self._fail(fc, "zone_area / sheet_area", "Cannot determine building area")

    def _detail_mark_position(self, fc: str) -> DerivedResult:
        """F-102: system-assigned at drawing generation time."""
        return self._ok(fc, "AUTO", "Position assigned by drawing engine at generation time")

    def _member_mark_auto(self, fc: str) -> DerivedResult:
        """F-103: same as F-067 member_mark."""
        v = self._get("F-067")
        if v:
            return self._ok(fc, v, "Auto-assigned from F-067 (member_mark)")
        return self._fail(fc, "F-067", "F-067 (member_mark) not available")

    def _hole_diameter(self, fc: str) -> DerivedResult:
        """F-106: bolt_diameter + standard 2 mm clearance."""
        dia = self._float("F-081")
        if dia:
            hole = dia + 2.0
            return self._ok(fc, f"{hole:.1f}", "F-081 + 2 mm clearance [mm]")
        # Try connection bolt size (F-076)
        cbs = self._get("F-076")
        if cbs:
            try:
                dia = float(cbs.replace("M", "").strip())
                return self._ok(fc, f"{dia + 2:.1f}", "F-076 (M-size) + 2 mm clearance [mm]")
            except ValueError:
                pass
        return self._fail(fc, "F-081 + 2", "F-081 (bolt_diameter) not available")

    def _bundle_total_weight(self, fc: str) -> DerivedResult:
        """F-110: total member weight × member count (heuristic)."""
        total = self._get("F-071")
        qty = self._float("F-069")
        if total and qty:
            try:
                val = float(total) * qty
                return self._ok(fc, f"{val:.2f}", "F-071 × F-069 [kg]")
            except ValueError:
                pass
        if total:
            return self._ok(fc, total, "Using F-071 as bundle weight proxy")
        return self._fail(fc, "F-071 × F-069", "F-071 (member_weight_total) not available")

    def _assembly_weight(self, fc: str) -> DerivedResult:
        """F-117: same as member_weight_total for single-member assemblies."""
        v = self._get("F-071")
        if v:
            return self._ok(fc, v, "Assembly weight = F-071 (member_weight_total)")
        return self._fail(fc, "F-071", "F-071 (member_weight_total) not available")

    def _mezzanine_area(self, fc: str) -> DerivedResult:
        """F-130: conditional — not applicable unless mezzanine level present."""
        mez_elev = self._get("F-129")
        if mez_elev:
            length = self._float("F-045")
            width = self._float("F-046")
            if length and width:
                area = (length * width) / 1_000_000.0 * 0.5  # 50% heuristic
                return self._ok(fc, f"{area:.2f}", "50% of floor area heuristic [m²]")
        return self._fail(fc, "conditional", "No mezzanine level detected (F-129 absent)")

    def _revision_history_display(self, fc: str) -> DerivedResult:
        """F-154: auto-generated revision table rendered from revision fields."""
        rev_code = self._get("F-031") or "R0"
        rev_date = self._get("F-032") or datetime.date.today().isoformat()
        rev_desc = self._get("F-033") or "Issued for Approval"
        return self._ok(
            fc,
            f"{rev_code} | {rev_date} | {rev_desc}",
            "Composed from F-031, F-032, F-033",
        )

    def _connection_bolt_pitch(self, fc: str) -> DerivedResult:
        """F-164: bolt pitch = gauge distance (F-161) as primary reference."""
        v = self._get("F-161")
        if v:
            return self._ok(fc, v, "Using F-161 (connection_gauge_distance) as bolt pitch")
        v = self._get("F-085")   # bolt_spacing_y
        if v:
            return self._ok(fc, v, "Using F-085 (bolt_spacing_y) as bolt pitch")
        return self._fail(fc, "F-161 or F-085", "Neither gauge distance nor bolt spacing available")

    def _bolt_group_eccentricity(self, fc: str) -> DerivedResult:
        """F-169: bolt group eccentricity from spacing × quantity / 2 (simplified)."""
        sx = self._float("F-084")
        sy = self._float("F-085")
        qty = self._float("F-083") or self._float("F-078")
        if sx and sy and qty:
            rows = max(1, int(qty) // 2)
            ecc = ((rows - 1) * sy) / 2.0
            return self._ok(fc, f"{ecc:.1f}", "Simplified: ((rows-1) × F-085) / 2 [mm]")
        return self._fail(fc, "(rows×F-085)/2", "Missing bolt spacing or quantity")

    def _number_of_bays_x_verified(self, fc: str) -> DerivedResult:
        """F-174: verified bay count from F-039 spacings."""
        v = self._get("F-039")
        if not v:
            return self._fail(fc, "count(F-039)", "F-039 (bay_spacing_x) not available")
        bays = [x for x in v.split(",") if x.strip()]
        return self._ok(fc, str(len(bays)), f"Verified {len(bays)} bay spacings from F-039")

    def _bay_sum_check_x(self, fc: str) -> DerivedResult:
        """F-175: sum of bay spacings must equal building_length (F-045)."""
        v = self._get("F-039")
        building_length = self._float("F-045")
        if not v:
            return self._fail(fc, "sum(F-039)", "F-039 (bay_spacing_x) not available")
        try:
            parts = [float(x.strip()) for x in v.split(",") if x.strip()]
            bay_sum = sum(parts)
            if building_length:
                delta = abs(bay_sum - building_length)
                status = "OK" if delta < 1.0 else f"MISMATCH (delta={delta:.1f} mm)"
                return self._ok(fc, f"{bay_sum:.1f} [{status}]",
                                f"Sum(F-039)={bay_sum:.1f}, F-045={building_length:.1f}")
            return self._ok(fc, f"{bay_sum:.1f}", f"Sum of {len(parts)} bay spacings [mm]")
        except ValueError as exc:
            return self._fail(fc, "sum(F-039)", f"Could not parse bay spacings: {exc}")

    def _crane_minimum_clearance(self, fc: str) -> DerivedResult:
        """F-182: crane_minimum_clearance = ridge_height - crane_rail_level - 200mm hook."""
        ridge = self._float("F-057")
        rail = self._float("F-128")
        if ridge and rail:
            clearance = ridge - rail - 200.0
            return self._ok(fc, f"{clearance:.1f}",
                            "F-057 − F-128 − 200 mm hook allowance [mm]")
        return self._fail(fc, "F-057 − F-128 − 200", "Missing F-057 or F-128 for crane clearance")

    def _buildup_weight_per_metre(self, fc: str) -> DerivedResult:
        """F-190: web + 2×top_flange + 2×bot_flange weight per metre [kg/m]."""
        web_t = self._float("F-184")
        web_h = self._float("F-185")
        tf_w = self._float("F-186")
        tf_t = self._float("F-187")
        bf_w = self._float("F-188")
        bf_t = self._float("F-189")
        STEEL_DENSITY = 7850e-9  # kg/mm³

        if all(v is not None for v in [web_t, web_h, tf_w, tf_t, bf_w, bf_t]):
            web_area = web_t * web_h
            tf_area = tf_w * tf_t
            bf_area = bf_w * bf_t
            total_area_mm2 = web_area + 2 * tf_area + 2 * bf_area
            kg_per_m = total_area_mm2 * 1000.0 * STEEL_DENSITY
            return self._ok(fc, f"{kg_per_m:.2f}",
                            "Steel density × cross-section area [kg/m]")
        return self._fail(fc, "web+flange×density",
                          "One or more built-up section dimensions (F-184..F-189) not available")

    def _sheeting_panel_run_length(self, fc: str) -> DerivedResult:
        """F-196: effective panel run = rafter length ≈ roof_span_length / cos(slope)."""
        span = self._float("F-059")
        slope = self._float("F-054")
        if span and slope is not None:
            import math
            try:
                rafter = span / (2.0 * math.cos(math.atan(slope)))
                return self._ok(fc, f"{rafter:.1f}",
                                "span/(2×cos(atan(slope))) [mm]")
            except (ZeroDivisionError, ValueError):
                pass
        if span:
            return self._ok(fc, f"{span / 2:.1f}",
                            "Approximated as span/2 (no slope available) [mm]")
        return self._fail(fc, "span/cos(slope)", "F-059 (roof_span_length) not available")
