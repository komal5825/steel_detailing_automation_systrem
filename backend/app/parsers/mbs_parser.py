from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ParsedField:
    field_code: str
    field_name: str
    raw_value: str
    normalized_value: str
    unit: str | None
    source_path: str
    confidence: int


# Month abbreviation → zero-padded number
_MONTH_MAP = {
    "JAN": "01", "FEB": "02", "MAR": "03", "APR": "04",
    "MAY": "05", "JUN": "06", "JUL": "07", "AUG": "08",
    "SEP": "09", "OCT": "10", "NOV": "11", "DEC": "12",
}

# Drawing description keywords → drawing_class value (F-020)
_DRAWING_CLASS_MAP = [
    ("ANCHOR BOLT",     "AB"),
    ("GENERAL ASSEMBLY","GA"),
    ("GENERAL ARRANGE", "GA"),
    ("SHOP DETAIL",     "DET"),
    ("COMPONENT DETAIL","DET"),
    ("ASSEMBLY",        "ASM"),
]

# Design code tokens from CompDes.in → project_design_standard (F-191)
_DESIGN_STD_MAP = {
    "AISC": "AISC-US",
    "IS800": "IS-Indian",
    "BS5950": "BS-UK",
    "BS EN": "Eurocode-EU",
    "EC3":   "Eurocode-EU",
    "MBMA":  "AISC-US",   # MBMA is AISC-based
    "AS4100":"AISC-US",
    "NAUS":  "AISC-US",
}

# Maps MBS internal extracted-field names to canonical F-codes (F-001 – F-196).
# Aliases (short internal names) are listed alongside their standard-name variants
# so both paths resolve correctly. Fields absent from MBS outputs are included so
# that any downstream code that sets them by standard name is also routed correctly.
_MBS_FIELD_CODE_MAP: dict[str, str] = {
    # ── Project identity ───────────────────────────────────────────────────────
    "project_code":               "F-001",
    "project_name":               "F-002",
    "project_location":           "F-003",
    "project_address":            "F-004",
    "project_engineer_name":      "F-005",
    "units":                      "F-006",   # short alias used by parser
    "project_unit_system":        "F-006",
    "project_seismic_category":   "F-007",
    "project_wind_speed":         "F-008",
    "client_code":                "F-009",
    "company_name":               "F-010",   # title-block alias for client_name
    "client_name":                "F-010",
    "client_contact_person":      "F-011",
    "client_phone":               "F-012",
    "project_design_standard":    "F-191",
    # ── Document / revision metadata ──────────────────────────────────────────
    "document_type":              "F-013",
    "document_code":              "F-014",
    "document_title":             "F-015",
    "document_file_format":       "F-016",
    "created_date":               "F-017",   # short alias for document_creation_date
    "document_creation_date":     "F-017",
    "document_sheet_count":       "F-018",
    "drawing_code":               "F-019",
    "drawing_class":              "F-020",
    "drawing_filename":           "F-021",
    "drawing_file_location":      "F-022",
    "drawing_created_by":         "F-023",
    "draw_date":                  "F-024",   # short alias for drawing_creation_date
    "drawing_creation_date":      "F-024",
    "sheet_sequence_number":      "F-025",
    "sheet_code":                 "F-026",
    "sheet_title":                "F-027",
    "size":                       "F-028",   # short alias for sheet_size_code
    "sheet_size_code":            "F-028",
    "scale":                      "F-029",   # short alias for sheet_scale
    "sheet_scale":                "F-029",
    "sheet_page_number":          "F-030",
    "sheet_page_number_for_pdf":  "F-030",
    "revision_code":              "F-031",
    "revision_date":              "F-032",
    "revision_description":       "F-033",
    "revision_initiated_by":      "F-034",
    "approved_by":                "F-035",
    "approval_date":              "F-036",
    "document_release_status":    "F-037",
    "revision_display_style":     "F-038",
    # ── Horizontal grid (bay spacings along building length) ──────────────────
    "bay_spacing_x":              "F-039",
    "grid_spacing_x":             "F-039",
    "bay_spacing_y":              "F-040",
    "grid_spacing_y":             "F-040",
    "col_label_x":                "F-041",
    "grid_label_x":               "F-041",
    "col_label_y":                "F-042",
    "grid_label_y":               "F-042",
    "origin_x":                   "F-043",
    "grid_origin_x":              "F-043",
    "origin_y":                   "F-044",
    "grid_origin_y":              "F-044",
    # ── Building layout ────────────────────────────────────────────────────────
    "building_length":            "F-045",
    "building_width":             "F-046",
    "building_height":            "F-047",
    "bldg_type":                  "F-048",   # short alias for building_type
    "building_type":              "F-048",
    "number_of_bays_x":           "F-049",
    "number_of_bays_y":           "F-050",
    "level_elevation":            "F-051",
    "level_code":                 "F-052",
    "level_description":          "F-053",
    "roof_slope_actual":          "F-054",
    "roof_slope_display":         "F-055",
    "roof_eave_height":           "F-056",
    "roof_ridge_height":          "F-057",
    "roof_eave_overhang":         "F-058",
    "roof_span_length":           "F-059",
    "frame_type":                 "F-060",
    "frame_bay_number":           "F-061",
    "frame_zone_code":            "F-062",
    "expansion_joint_location":   "F-195",
    # ── Member data ────────────────────────────────────────────────────────────
    "member_section_size":        "F-063",
    "member_type":                "F-064",
    "member_material_grade":      "F-065",
    "member_length":              "F-066",
    "member_mark":                "F-067",
    "member_full_mark":           "F-068",
    "member_quantity":            "F-069",
    "member_weight_per_unit_length": "F-070",
    "member_weight_total":        "F-071",
    "member_location_ref":        "F-072",   # short alias
    "member_location_reference":  "F-072",
    "member_surface_treat":       "F-073",   # short alias
    "member_surface_treatment":   "F-073",
    "member_camber":              "F-074",
    # ── Connection ─────────────────────────────────────────────────────────────
    "connection_type":            "F-075",
    "connection_bolt_size":       "F-076",
    "bolt_grade":                 "F-077",   # short alias for connection_bolt_grade
    "connection_bolt_grade":      "F-077",
    "connection_bolt_quantity":   "F-078",
    "weld_size":                  "F-079",
    "connection_source_type":     "F-170",
    "connection_web_plate_thickness":   "F-157",
    "connection_flange_plate_thickness":"F-158",
    "connection_bolt_rows":       "F-159",
    "connection_bolt_columns":    "F-160",
    "connection_gauge_distance":  "F-161",
    "connection_end_distance":    "F-162",
    "connection_edge_distance":   "F-163",
    "connection_bolt_pitch":      "F-164",
    "connection_weld_type":       "F-165",
    "connection_backing_bar_flag":"F-166",
    "connection_stiffener_required":    "F-167",
    "connection_stiffener_thickness":   "F-168",
    "connection_detail_ref":      "F-105",
    # ── Anchor bolt and base plate ─────────────────────────────────────────────
    "base_plate_size":            "F-080",
    "bolt_diameter":              "F-081",
    "bolt_grade_anchor":          "F-082",
    "bolt_quantity_per_column":   "F-083",
    "bolt_spacing_x":             "F-084",
    "bolt_spacing_y":             "F-085",
    "bolt_embedment_depth":       "F-086",
    "bolt_projection":            "F-087",
    "bolt_pattern_orientation":   "F-088",
    "anchor_bolt_code":           "F-089",
    "base_plate_thickness":       "F-090",
    "bolt_group_eccentricity":    "F-169",
    "bolt_projection_above_ffl":  "F-192",
    "grout_pad_thickness":        "F-193",
    "column_base_axis_orientation":"F-194",
    # ── Sheeting ───────────────────────────────────────────────────────────────
    "sheeting_zone_code":         "F-091",
    "sheeting_material_type":     "F-092",
    "sheeting_gauge":             "F-093",
    "sheeting_color":             "F-094",
    "sheeting_fastener_type":     "F-095",
    "sheeting_zone_area":         "F-096",
    "sheeting_sheet_count":       "F-097",
    "sheeting_support_ref":       "F-098",
    "sheeting_opening_ref":       "F-099",
    "sheeting_lapping_direction": "F-100",
    "sheeting_panel_run_length":  "F-196",
    # ── Detail and drawing references ──────────────────────────────────────────
    "detail_reference":           "F-101",
    "detail_mark_position":       "F-102",
    "member_mark_auto_generated": "F-103",
    "shop_drawing_file_ref":      "F-104",
    "hole_diameter":              "F-106",
    "plate_thickness":            "F-107",
    # ── Secondary members ──────────────────────────────────────────────────────
    "purlin_girt_section_size":   "F-121",
    "purlin_spacing":             "F-122",
    "girt_spacing":               "F-123",
    "purlin_laps":                "F-124",
    # ── Crane ──────────────────────────────────────────────────────────────────
    "crane_capacity_required":    "F-118",
    "crane_type":                 "F-125",
    "crane_capacity":             "F-126",
    "crane_span":                 "F-127",
    "crane_rail_level":           "F-128",
    "crane_runway_beam_section":  "F-176",
    "crane_rail_section":         "F-177",
    "crane_bracket_plate_size":   "F-178",
    "crane_bracket_bolt_size":    "F-179",
    "crane_end_stop_type":        "F-180",
    "crane_gantry_girder_flag":   "F-181",
    "crane_minimum_clearance":    "F-182",
    # ── Mezzanine / staircase ──────────────────────────────────────────────────
    "mezzanine_level_elevation":  "F-129",
    "mezzanine_area":             "F-130",
    "staircase_type":             "F-131",
    # ── Shipping ───────────────────────────────────────────────────────────────
    "shipping_bundle_code":       "F-108",
    "bundle_member_list":         "F-109",
    "bundle_total_weight":        "F-110",
    "bundle_sequence_number":     "F-111",
    "bundle_destination":         "F-112",
    "bundle_truck_load":          "F-113",
    # ── Installation / erection ────────────────────────────────────────────────
    "installation_package_code":  "F-114",
    "installation_sequence_number":"F-115",
    "assembly_code":              "F-116",
    "assembly_weight":            "F-117",
    "temporary_bracing_required": "F-119",
    "erection_setup_time":        "F-120",
    # ── Bay / frame metadata ───────────────────────────────────────────────────
    "bay_seq":                    "F-171",   # short alias
    "bay_sequence_number":        "F-171",
    "bay_dim":                    "F-172",   # short alias
    "bay_dimension_mm":           "F-172",
    "bay_type_code":              "F-173",
    "number_of_bays_x_verified":  "F-174",
    "bay_sum_check_x":            "F-175",
    # ── Built-up section dimensions ────────────────────────────────────────────
    "section_type_flag":          "F-183",
    "buildup_web_plate_thickness":"F-184",
    "buildup_web_plate_height":   "F-185",
    "buildup_top_flange_width":   "F-186",
    "buildup_top_flange_thickness":"F-187",
    "buildup_bot_flange_width":   "F-188",
    "buildup_bot_flange_thickness":"F-189",
    "buildup_weight_per_metre":   "F-190",
    # ── QC and workflow ────────────────────────────────────────────────────────
    "qc_check_status":            "F-132",
    "qc_checked_by":              "F-133",
    "qc_date":                    "F-134",
    "approval_required_flag":     "F-135",
    "approval_status":            "F-136",
    "audit_timestamp":            "F-137",
    "created_by_agent":           "F-138",
    "source_file_reference":      "F-139",
    "extraction_method":          "F-140",
    "extraction_confidence":      "F-141",
    "source_priority_used":       "F-142",
    "validation_result":          "F-143",
    "validation_rule_applied":    "F-144",
    "override_event_flag":        "F-145",
    "override_reason":            "F-146",
    "stage_gate_id":              "F-147",
    "stage_gate_status":          "F-148",
    "ab_gate_passed":             "F-149",
    "ga_gate_passed":             "F-150",
    # ── Drawing template and presentation ──────────────────────────────────────
    "template_family_ref":        "F-151",
    "title_block_ref":            "F-152",
    "dimension_text_height":      "F-153",
    "revision_history_display":   "F-154",
    "north_arrow_position":       "F-155",
    "drawing_border_ref":         "F-156",
}

# Sheet size from width × height (mm) → ISO code
_SHEET_SIZE_MAP = [
    ((1189, 841), "A0"),
    (( 841, 594), "A1"),
    (( 594, 420), "A2"),
    (( 420, 297), "A3"),
    (( 297, 210), "A4"),
]


class MBSParser:
    """Extract project facts from MBS exports.

    Handles three formats in priority order:
      1. MBS structured .in files  (AnDwg, CompDes, EwDes, …) — highest fidelity
      2. XML exports
      3. Generic key-value text
    """

    # ---------------------------------------------------------------------------
    # Public entry point
    # ---------------------------------------------------------------------------

    def parse(self, file_path: str) -> dict:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(file_path)

        text = path.read_text(encoding="utf-8", errors="ignore")

        if self._looks_like_mbs_in_file(text):
            fields = self._parse_mbs_in_file(text, str(path))
            confidence = 85 if fields else 0
        else:
            values = self._parse_xml(text) if self._looks_like_xml(text) else {}
            values.update(self._parse_key_value_text(text))
            is_xml = self._looks_like_xml(text)
            confidence = 90 if is_xml and values else 75 if values else 0
            fields = [
                ParsedField(
                    field_code=f"RAW-MBS-{self._clean_key(k).upper()}",
                    field_name=k,
                    raw_value=v,
                    normalized_value=self._normalize_value(v),
                    unit=None,
                    source_path=str(path),
                    confidence=confidence,
                )
                for k, v in values.items()
                if v not in (None, "")
            ]

        return {
            "parser": "MBSParser",
            "source_path": str(path),
            "field_count": len(fields),
            "confidence": confidence,
            "fields": [f.__dict__ for f in fields],
        }

    # ---------------------------------------------------------------------------
    # MBS .in structured file parser
    # ---------------------------------------------------------------------------

    def _looks_like_mbs_in_file(self, text: str) -> bool:
        """True when the file contains MBS section markers like *( 1)TITLE BLOCK."""
        return bool(re.search(r"^\*\(\s*\d", text, re.MULTILINE))

    def _parse_mbs_in_file(self, text: str, source_path: str) -> list[ParsedField]:
        """Parse an MBS .in file and return ParsedField objects."""
        extracted: dict[str, str] = {}

        # ── Step 1: header line (second non-separator comment line) ─────────
        self._parse_header_line(text, extracted)

        # ── Step 2: first-line FILE header (DE_COL style: *FILE:... UNITS:...) ─
        first_line = text.splitlines()[0] if text.strip() else ""
        if first_line.startswith("*FILE:") and "UNITS:" in first_line.upper():
            m = re.search(r"UNITS\s*:\s*(\w+)", first_line, re.IGNORECASE)
            if m:
                extracted.setdefault("units", m.group(1).upper())

        # All MBS files that reach here are metric (MBS India always uses mm)
        extracted.setdefault("units", "METRIC")

        # ── Step 3: sections ────────────────────────────────────────────────
        # Regex captures: (1) section number, (2) section name
        section_re = re.compile(
            r"^\*\(\s*(\d+)\)\s*([^:\n]+):[^\n]*\n",
            re.MULTILINE,
        )
        matches = list(section_re.finditer(text))

        for i, m in enumerate(matches):
            sec_num = int(m.group(1))
            sec_name = m.group(2).strip().upper()
            body_start = m.end()
            body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            body = text[body_start:body_end]

            if "TITLE BLOCK" in sec_name:
                self._parse_title_block(body, extracted)
            elif "DRAWING SIZE" in sec_name:
                self._parse_drawing_size(body, extracted)
            elif "BUILDING LAYOUT" in sec_name:
                self._parse_building_layout(body, extracted)
            elif "DESIGN CODE" in sec_name:
                self._parse_design_code(body, extracted)
            elif "DESIGN CONSTANTS" in sec_name:
                self._parse_design_constants(body, extracted)
            elif "ROOF PANELS" in sec_name:
                self._parse_roof_panels(body, extracted)
            elif "WALL PANELS" in sec_name:
                self._parse_wall_panels(body, extracted)
            elif "JOBID" in sec_name and sec_num == 1:
                self._parse_jobid(body, extracted)
            elif "WALL COLUMNS" in sec_name:
                self._parse_wall_columns(body, extracted)
            elif "RIGID FRAMES" in sec_name:
                self._parse_rigid_frames(body, extracted)
            elif "PURLIN LOCATION" in sec_name:
                self._parse_purlin_location(body, extracted)
            elif "COLUMN BASE/CAP PLATES" in sec_name:
                self._parse_column_plates(body, extracted)
            elif "SPECIAL GIRT" in sec_name:
                self._parse_special_girt(body, extracted)
            elif "EXTENSION PURLINS" in sec_name:
                self._parse_extension_purlins(body, extracted)
            elif sec_num == 20 and (
                "DETAILS" in sec_name
                or "BOLT" in sec_name
                or "ANCHOR" in sec_name
                or not any(k in sec_name for k in (
                    "TITLE", "DRAWING", "BUILDING", "DESIGN",
                    "JOBID", "HORIZONTAL", "VERTICAL", "SURFACE",
                ))
            ):
                self._parse_details_section(body, extracted)
            elif "HORIZONTAL GRID" in sec_name:
                self._parse_horizontal_grid(body, extracted)
            elif "VERTICAL GRID" in sec_name:
                self._parse_vertical_grid(body, extracted)
            elif "SURFACE SHAPE" in sec_name:
                self._parse_surface_shape(body, extracted)
            elif "DESIGN PLATES" in sec_name:
                self._parse_design_plates(body, extracted)

        return [
            ParsedField(
                field_code=_MBS_FIELD_CODE_MAP.get(
                    name, f"RAW-MBS-{self._clean_key(name).upper()}"
                ),
                field_name=name,
                raw_value=value,
                normalized_value=self._normalize_value(value),
                unit=None,
                source_path=source_path,
                confidence=85,
            )
            for name, value in extracted.items()
            if value not in (None, "")
        ]

    # ---------------------------------------------------------------------------
    # Section parsers
    # ---------------------------------------------------------------------------

    def _parse_header_line(self, text: str, extracted: dict) -> None:
        """Extract date and drawing class from the descriptive comment header line.

        Example: *C323-153  Anchor Bolt Drawing Input  23/JUL/2025 11:28am
        """
        for line in text.splitlines()[:8]:
            stripped = line.strip()
            if not stripped.startswith("*") or "===" in stripped:
                continue
            content = stripped[1:].strip()
            if not content:
                continue

            # Date: DD/MON/YYYY
            dm = re.search(r"(\d{1,2})/([A-Z]{3})/(\d{4})", content, re.IGNORECASE)
            if dm:
                day, mon, year = dm.groups()
                mon_num = _MONTH_MAP.get(mon.upper(), "01")
                iso_date = f"{year}-{mon_num}-{day.zfill(2)}"
                extracted.setdefault("draw_date", iso_date)    # F-024
                extracted.setdefault("created_date", iso_date) # F-017

            # Drawing class from description text
            content_upper = content.upper()
            for keyword, cls in _DRAWING_CLASS_MAP:
                if keyword in content_upper:
                    extracted.setdefault("drawing_class", cls)  # F-020
                    break

            if dm:  # found the info line, stop
                break

    def _parse_title_block(self, body: str, extracted: dict) -> None:
        """Section (1) TITLE BLOCK — quoted strings with .. Label comments."""
        _TB_MAP = {
            "manufacturer": "company_name",   # F-010
            "project":      "project_name",   # F-002
            "project id":   "project_code",   # F-001
        }
        for line in body.splitlines():
            m = re.match(r"\s*'([^']*)'\s+\.\.\s*(.+)", line)
            if not m:
                continue
            value = m.group(1).strip()
            label = m.group(2).strip().lower()
            if not value:
                continue
            key = _TB_MAP.get(label)
            if key:
                extracted.setdefault(key, value)
            elif "project site" in label:
                # Accumulate site lines for location
                current = extracted.get("project_location", "")
                if current:
                    extracted["project_location"] = f"{current}, {value}"
                else:
                    extracted["project_location"] = value

    def _parse_jobid(self, body: str, extracted: dict) -> None:
        """Section (1) JOBID (CompDes style) — single quoted project code."""
        for line in body.splitlines():
            m = re.match(r"\s*'([^']+)'", line)
            if m:
                extracted.setdefault("project_code", m.group(1).strip())  # F-001
                break

    def _parse_drawing_size(self, body: str, extracted: dict) -> None:
        """Section (2) DRAWING SIZE FACTORS — Width Height … Scale …

        Column layout (from comment header):
          Width Height  Lt  Rt  Top  Bot  Text Table  Dim  Bolt  Build  Title  Size Loc
          420.0  297.0  …               …              0.35   0.6  -1.000  0.70  35.0 'B '

        Scale index 10 (0-based): -1.000 = NTS (auto-scale); positive = explicit scale.
        """
        for line in body.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("*"):
                continue
            parts = stripped.split()
            if len(parts) < 2:
                continue
            try:
                width_mm = float(parts[0])
                height_mm = float(parts[1])
            except ValueError:
                continue

            # Sheet size code from dimensions
            for (w, h), code in _SHEET_SIZE_MAP:
                if abs(width_mm - w) < 5 and abs(height_mm - h) < 5:
                    extracted.setdefault("size", code)          # F-028
                    break
                if abs(width_mm - h) < 5 and abs(height_mm - w) < 5:
                    extracted.setdefault("size", code)          # F-028 (landscape)
                    break

            # Scale: column index 10 (0-based), may not always be present
            if len(parts) > 10:
                try:
                    scale_val = float(parts[10])
                    if scale_val < 0:
                        extracted.setdefault("scale", "NTS")    # F-029
                    else:
                        # E.g. 0.35 → approx 1:285 — just store raw decimal
                        extracted.setdefault("scale", str(scale_val))
                except ValueError:
                    pass

            break  # only one data line expected

    def _parse_building_layout(self, body: str, extracted: dict) -> None:
        """Section (5/6) BUILDING LAYOUT — 'Type' Width Length …"""
        for line in body.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("*"):
                continue
            parts = stripped.split()
            if not parts[0].startswith("'"):
                continue
            try:
                btype = parts[0].strip("'- ") or "FF"
                width = float(parts[1])
                length = float(parts[2])
                extracted.setdefault("bldg_type",        btype)       # F-048
                extracted.setdefault("building_width",   str(width))  # F-046
                extracted.setdefault("building_length",  str(length)) # F-045
                extracted.setdefault("roof_span_length", str(width))  # F-059 (Span = Width for basic types)
                extracted.setdefault("level_code",       "GL")        # F-052 (ground level default)
                # Derive frame_type from building type code
                _FRAME_TYPE_MAP = {
                    "FF": "Rigid Frame", "RF": "Rigid Frame",
                    "LT": "Lean-to", "MS": "Multi-span",
                    "SM": "Single-span Mono-slope",
                }
                extracted.setdefault(
                    "frame_type",
                    _FRAME_TYPE_MAP.get(btype.upper(), "Rigid Frame"),
                )  # F-060
                
                if len(parts) > 3:
                    try:
                        height = float(parts[3])
                        extracted.setdefault("building_height", str(height)) # F-047
                    except ValueError:
                        pass
                
                # Floor elevation usually at end of line in Section (5)
                # Example: 'FF-'  22470.0  36285.0 'Y ' 'E'   0.00 440.00 'Y ' 'E'   0.00 440.00     0         0.0      0.0
                if len(parts) >= 15: # AnDwg format
                    try:
                        floor_elev = float(parts[-2])
                        extracted.setdefault("level_elevation", str(floor_elev)) # F-051
                    except ValueError:
                        pass

            except (ValueError, IndexError):
                pass
            break

    def _parse_design_code(self, body: str, extracted: dict) -> None:
        """Section (2) DESIGN CODE (CompDes) — 'Code' 'ColdCode' 'HotCode' …

        Example: 'WS'  'NAUS07  ' 'AISC05'  '    '  'MBMA'  '10' …
        We scan all quoted tokens for known design standard keywords.
        """
        quoted_re = re.compile(r"'([^']+)'")
        for line in body.splitlines():
            if line.strip().startswith("*") or not line.strip():
                continue
            tokens = [t.strip() for t in quoted_re.findall(line)]
            combined = " ".join(tokens).upper()
            for keyword, std in _DESIGN_STD_MAP.items():
                if keyword in combined:
                    extracted.setdefault("project_design_standard", std)  # F-191
                    break
            if "project_design_standard" in extracted:
                break

    def _parse_details_section(self, body: str, extracted: dict) -> None:
        """Section (20) DETAILS — bolt dimensions and base plate geometry.

        Column order (from comment header):
          [No.] Id  Dia  In  Out  A  B  C  D  E  F  BpWidth  BpLength  BpThick  Opt  ColDepth  ColWidth

        Parameter mapping:
          A = bolt spacing X (longitudinal)   → F-084
          B = bolt spacing Y (transverse)     → F-085
          C = edge distance
          D = embedment depth                 → F-086
          E = projection above base plate     → F-087
          F = hook / total extension
          BpOpt 'G' = grouted, '-' = ungrouted

        Primary detail = 'm1' (standard interior column); fallback to first found.
        End-wall detail = 'e1'; emitted with 'ew_' prefix for traceability.
        """
        detail_re = re.compile(
            r"'([^']+)'"                           # Id          (1)
            r"\s+([\d.]+)"                         # Dia         (2)
            r"\s+([\d.]+)\s+([\d.]+)"             # In  Out     (3,4) — allow floats e.g. "2.0"
            r"\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)"  # A  B  C    (5,6,7)
            r"\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)"  # D  E  F    (8,9,10)
            r"\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)"  # BpW BpL BpT (11,12,13)
            r"(?:\s+'([^']*)')?"                   # Opt         (14, optional)
            r"(?:\s+([\d.]+)\s+([\d.]+))?"         # ColD ColW   (15,16, optional)
        )

        primary: dict | None = None
        first:   dict | None = None

        for line in body.splitlines():
            if not line.strip() or line.strip().startswith("*"):
                continue
            m = detail_re.search(line)
            if not m:
                continue
            det: dict = {
                "id":       m.group(1).strip(),
                "dia":      m.group(2),
                "rows_in":  int(float(m.group(3))),
                "rows_out": int(float(m.group(4))),
                "a": m.group(5),  "b": m.group(6),  "c": m.group(7),
                "d": m.group(8),  "e": m.group(9),  "f": m.group(10),
                "bp_width":  m.group(11),
                "bp_length": m.group(12),
                "bp_thick":  m.group(13),
                "bp_opt":    (m.group(14) or "").strip(),
                "col_depth": m.group(15),   # may be None
                "col_width": m.group(16),   # may be None
            }
            if first is None:
                first = det
            if det["id"] == "m1":
                primary = det

        det = primary or first
        if not det:
            return

        bolt_qty   = det["rows_in"] + det["rows_out"]
        dia_int    = int(float(det["dia"]))
        orient     = "Symmetric" if det["rows_in"] == det["rows_out"] else "Custom"

        extracted.setdefault("bolt_diameter",     str(dia_int))                      # F-081
        extracted.setdefault("bolt_grade",        "8.8")                             # F-077
        extracted.setdefault("bolt_grade_anchor", "8.8")                             # F-082 anchor bolt grade
        extracted.setdefault("bolt_quantity_per_column", str(bolt_qty))              # F-083
        extracted.setdefault("bolt_spacing_x",    det["a"])                          # F-084
        extracted.setdefault("bolt_spacing_y",    det["b"])                          # F-085
        extracted.setdefault("bolt_embedment_depth", det["d"])                       # F-086
        extracted.setdefault("bolt_projection",    det["e"])                         # F-087
        extracted.setdefault("bolt_projection_above_ffl", det["e"])                  # F-192
        extracted.setdefault("bolt_pattern_orientation", orient)                     # F-088
        extracted.setdefault("anchor_bolt_code",      det["id"])                     # F-089
        extracted.setdefault("base_plate_size",
                             f"{det['bp_width']} x {det['bp_length']}")              # F-080
        extracted.setdefault("base_plate_thickness",     det["bp_thick"])            # F-090
        extracted.setdefault("connection_type",    "Bolted")                         # F-075
        extracted.setdefault("connection_bolt_size", f"M{dia_int}")                  # F-076
        extracted.setdefault("connection_bolt_quantity", str(bolt_qty))              # F-078
        
        # New connection fields
        extracted.setdefault("connection_bolt_rows",    str(bolt_qty // 2))          # F-159 (Heuristic: 2 columns)
        extracted.setdefault("connection_bolt_columns", "2")                         # F-160 (Standard)
        extracted.setdefault("connection_gauge_distance", det["b"])                  # F-161
        extracted.setdefault("connection_end_distance",   det["a"])                  # F-162
        extracted.setdefault("connection_edge_distance",  det["c"])                  # F-163

        # End-wall detail (usually 'e1') — emitted alongside primary for traceability
        ew = None
        if primary and first and primary["id"] != first["id"]:
            ew = first if primary["id"] == "m1" else primary
        if ew:
            ew_qty = ew["rows_in"] + ew["rows_out"]
            extracted.setdefault("ew_detail_id",  ew["id"])
            extracted.setdefault("ew_bolt_dia",   str(int(float(ew["dia"]))))
            extracted.setdefault("ew_bolt_qty",   str(ew_qty))
            extracted.setdefault("ew_bp_size",
                                 f"{ew['bp_width']} x {ew['bp_length']}")
            extracted.setdefault("ew_bp_thick",   ew["bp_thick"])

    def _parse_horizontal_grid(self, body: str, extracted: dict) -> None:
        """Section (24) HORIZONTAL GRID LINE — numbered lines along building length.

        Format:
          count  offset  'label'     ← first data line includes count
                 offset  'label'     ← subsequent lines
        """
        line_re = re.compile(r"^\s*(?:\d+\s+)?([\d.]+)\s+'([^']*)'", re.MULTILINE)

        offsets: list[float] = []
        labels:  list[str]   = []
        for m in line_re.finditer(body):
            offsets.append(float(m.group(1)))
            labels.append(m.group(2).strip())

        if not offsets:
            return

        spacings = [offsets[j + 1] - offsets[j] for j in range(len(offsets) - 1)]

        extracted.setdefault("col_label_x",  ",".join(labels))                        # F-041
        extracted.setdefault("bay_spacing_x",
                             ",".join(f"{s:.1f}" for s in spacings))                  # F-039
        extracted.setdefault("origin_x",     f"{offsets[0]:.1f}")                    # F-043
        extracted.setdefault("bay_seq",      str(len(spacings)))                      # F-171
        if spacings:
            extracted.setdefault("bay_dim",  f"{spacings[0]:.1f}")                   # F-172

    def _parse_vertical_grid(self, body: str, extracted: dict) -> None:
        """Section (25) VERTICAL GRID LINE — lettered lines across building width."""
        line_re = re.compile(r"^\s*(?:\d+\s+)?([\d.]+)\s+'([^']*)'", re.MULTILINE)

        offsets: list[float] = []
        labels:  list[str]   = []
        for m in line_re.finditer(body):
            offsets.append(float(m.group(1)))
            labels.append(m.group(2).strip())

        if not offsets:
            return

        spacings = [offsets[j + 1] - offsets[j] for j in range(len(offsets) - 1)]

        extracted.setdefault("col_label_y",  ",".join(labels))                        # F-042
        extracted.setdefault("bay_spacing_y",
                             ",".join(f"{s:.1f}" for s in spacings))                  # F-040
        extracted.setdefault("origin_y",     f"{offsets[0]:.1f}")                    # F-044
        
    def _parse_surface_shape(self, body: str, extracted: dict) -> None:
        """Section (7) SURFACE SHAPE — coordinates of the building cross-section.
        
        Extracts eave height, ridge height and calculates roof slope.
        """
        line_re = re.compile(r"^\s*(?:\d+\s+)?([\d.]+)\s+([\d.]+)", re.MULTILINE)
        
        coords: list[tuple[float, float]] = []
        for m in line_re.finditer(body):
            coords.append((float(m.group(1)), float(m.group(2))))
            
        if not coords:
            return
            
        # Building Width (max X)
        width = max(c[0] for c in coords)
        # Ridge Height (max Y)
        ridge_height = max(c[1] for c in coords)
        # Eave Height (Y at X=0 or X=width)
        eave_heights = [c[1] for c in coords if abs(c[0]) < 1 or abs(c[0] - width) < 1]
        eave_height = eave_heights[0] if eave_heights else coords[0][1]
        
        extracted.setdefault("building_height",   str(eave_height))  # F-047
        extracted.setdefault("roof_eave_height",  str(eave_height))  # F-056
        extracted.setdefault("roof_ridge_height", str(ridge_height)) # F-057

        if ridge_height > eave_height and width > 0:
            # Slope = (Ridge - Eave) / (Width / 2)
            slope = (ridge_height - eave_height) / (width / 2.0)
            extracted.setdefault("roof_slope_display", f"{slope:.4f}") # F-055
            extracted.setdefault("roof_slope_actual",  f"{slope:.4f}") # F-054

    # ---------------------------------------------------------------------------
    # Generic format parsers (XML and key-value text)
    # ---------------------------------------------------------------------------

    def _looks_like_xml(self, text: str) -> bool:
        return text.lstrip().startswith("<")

    def _parse_xml(self, text: str) -> dict[str, str]:
        try:
            root = ET.fromstring(text)
        except ET.ParseError:
            return {}

        extracted: dict[str, str] = {}
        for element in root.iter():
            key = self._clean_key(element.tag)
            value = (element.text or "").strip()
            if not value:
                continue
            extracted.setdefault(key, value)
            for attr_key, attr_value in element.attrib.items():
                extracted.setdefault(self._clean_key(attr_key), attr_value.strip())
        return extracted

    def _parse_key_value_text(self, text: str) -> dict[str, str]:
        extracted: dict[str, str] = {}
        for line in text.splitlines():
            match = re.match(r"^\s*([A-Za-z0-9 _/-]+)\s*[:=]\s*(.+?)\s*$", line)
            if not match:
                continue
            key = self._clean_key(match.group(1))
            value = match.group(2).strip()
            extracted.setdefault(key, value)
        return extracted

    def _parse_design_constants(self, body: str, extracted: dict) -> None:
        """Section (3) DESIGN CONSTANTS — Web Flg C_Sec W_Sec ..."""
        for line in body.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("*"):
                continue
            parts = stripped.split()
            if not parts: continue
            # Primary yield usually first column
            try:
                yield_val = parts[0]
                extracted.setdefault("member_material_grade", f"Fe{yield_val}") # F-065
            except (IndexError, ValueError):
                pass
            break

    def _parse_wall_columns(self, body: str, extracted: dict) -> None:
        """Section (11) WALL COLUMNS — Id ColId ColType ... Part."""
        # ColMark and Part are at the end
        # Example: 1 3 1 '-' 'N' '-' 'C ' '--' 0.00 '--------' '--------'
        #          1 3 2 'W' 'N' 'I' 'B ' 'e1' 0.00 'EC-1 ' 'W40b155 '
        for line in body.splitlines():
            if not line.strip() or line.strip().startswith("*"):
                continue
            # Look for quoted parts at the end
            quoted = re.findall(r"'([^']*)'", line)
            if len(quoted) >= 3:
                mark = quoted[-2].strip()
                part = quoted[-1].strip()
                if part and part != "--------":
                    extracted.setdefault("member_section_size", part)  # F-063
                    extracted.setdefault("member_mark", mark)          # F-067
                    extracted.setdefault("section_type_flag", "BuiltUp" if "b" in part.lower() else "Rolled") # F-183
                
                # Location Ref (Line Id)
                if len(quoted) >= 5:
                    loc_ref = quoted[3].strip()
                    if loc_ref:
                        extracted.setdefault("member_location_ref", loc_ref) # F-072
                
            # Column type and height
            parts = line.split()
            if len(parts) > 9:
                try:
                    height = parts[9].strip("'")
                    extracted.setdefault("member_length", height)     # F-066
                except (ValueError, IndexError):
                    pass
            
            if len(parts) > 3:
                col_type = parts[3].strip("'")
                if col_type != '-':
                    extracted.setdefault("member_type", "Column")      # F-064

    def _parse_rigid_frames(self, body: str, extracted: dict) -> None:
        """Section (12) RIGID FRAMES — Line Id Type ... Part."""
        for line in body.splitlines():
            if not line.strip() or line.strip().startswith("*"):
                continue
            quoted = re.findall(r"'([^']*)'", line)
            if len(quoted) >= 2:
                frame_type = quoted[0].strip()
                part = quoted[-1].strip()
                extracted.setdefault("bay_type_code", frame_type)      # F-173
                if part and part != "--------":
                    extracted.setdefault("member_section_size", part)  # F-063
            
            parts = line.split()
            if len(parts) > 2:
                line_id = parts[1]
                extracted.setdefault("frame_bay_number", line_id)      # F-061

    def _parse_purlin_location(self, body: str, extracted: dict) -> None:
        """Section (12) PURLIN LOCATION (CompDes) — Type Space No. Locate."""
        for line in body.splitlines():
            if not line.strip() or line.strip().startswith("*"):
                continue
            quoted = re.findall(r"'([^']*)'", line)
            if quoted:
                extracted.setdefault("purlin_laps", "Double" if "ZB" in quoted[0] else "Single") # F-124
            
            parts = line.split()
            # Example: 2 'ZB' 300.0 8 1373.9 ...
            for p in parts:
                try:
                    val = float(p)
                    if 100 < val < 2000: # Heuristic for spacing
                        extracted.setdefault("purlin_spacing", str(val)) # F-122
                        break
                except ValueError:
                    continue

    def _parse_extension_purlins(self, body: str, extracted: dict) -> None:
        """Section (18) EXTENSION PURLINS — Part."""
        for line in body.splitlines():
            if not line.strip() or line.strip().startswith("*"):
                continue
            quoted = re.findall(r"'([^']*)'", line)
            if quoted:
                for q in quoted:
                    if re.search(r"\d+[Z|C]\d+", q):
                        extracted.setdefault("purlin_girt_section_size", q.strip()) # F-121
                        break

    def _parse_design_plates(self, body: str, extracted: dict) -> None:
        """Section (28) DESIGN PLATES — Width Thick Dia Gage Row."""
        for line in body.splitlines():
            if not line.strip() or line.strip().startswith("*"):
                continue
            parts = line.split()
            if len(parts) >= 8:
                try:
                    # AnDwg format: [No.] Id Width Thick Dia Gage Row
                    # CompDes format might differ. Let's handle both.
                    if "'" in parts[0]: # CompDes style has quoted ID first
                        thick = parts[2]
                        dia = parts[3]
                        gage = parts[4]
                    else:
                        thick = parts[5]
                        dia = parts[6]
                        gage = parts[7]
                    
                    extracted.setdefault("connection_web_plate_thickness", thick) # F-157
                    extracted.setdefault("connection_bolt_size", f"M{int(float(dia))}") # F-076
                    extracted.setdefault("connection_gauge_distance", gage)       # F-161
                except (ValueError, IndexError):
                    pass

    def _parse_special_girt(self, body: str, extracted: dict) -> None:
        """Section (14) SPECIAL GIRT — Height Type."""
        for line in body.splitlines():
            if not line.strip() or line.strip().startswith("*"):
                continue
            parts = line.split()
            if len(parts) >= 5:
                try:
                    height = parts[4].strip("'")
                    extracted.setdefault("girt_spacing", height) # F-123
                except (ValueError, IndexError):
                    pass

    def _parse_roof_panels(self, body: str, extracted: dict) -> None:
        """Section (24) ROOF PANELS — Part Color."""
        for line in body.splitlines():
            if not line.strip() or line.strip().startswith("*"):
                continue
            quoted = re.findall(r"'([^']*)'", line)
            if quoted:
                extracted.setdefault("sheeting_material_type", quoted[0].strip()) # F-092
                # Gauge often part of the name like 45250 .5 -> 0.5mm
                match = re.search(r"\d+\.\d+|\.\d+", quoted[0])
                if match:
                    extracted.setdefault("sheeting_gauge", match.group()) # F-093
                break

    def _parse_wall_panels(self, body: str, extracted: dict) -> None:
        """Section (25) WALL PANELS — Part Color."""
        for line in body.splitlines():
            if not line.strip() or line.strip().startswith("*"):
                continue
            quoted = re.findall(r"'([^']*)'", line)
            if quoted:
                # Use as fallback for F-092/F-093 if roof panel missing
                extracted.setdefault("sheeting_material_type", quoted[0].strip())
                match = re.search(r"\d+\.\d+|\.\d+", quoted[0])
                if match:
                    extracted.setdefault("sheeting_gauge", match.group())
                break

    def _parse_column_plates(self, body: str, extracted: dict) -> None:
        """Section (12) COLUMN BASE/CAP PLATES — Bolt Type Dia."""
        for line in body.splitlines():
            if not line.strip() or line.strip().startswith("*"):
                continue
            quoted = re.findall(r"'([^']*)'", line)
            # Example: 1 1 2 'S3' 200.00 16.00 20.00 2 100.00 100.00 'P-' ... 'Gr8.8' 20.00
            if len(quoted) >= 3:
                for q in quoted:
                    if "Gr" in q:
                        grade = q.replace("Gr", "").strip()
                        extracted.setdefault("bolt_grade",        grade)  # F-077
                        extracted.setdefault("bolt_grade_anchor", grade)  # F-082
                        extracted.setdefault("connection_bolt_grade", grade)
                        break

    # ---------------------------------------------------------------------------
    # Shared helpers
    # ---------------------------------------------------------------------------

    def _clean_key(self, key: str) -> str:
        return re.sub(r"[^a-z0-9]", "", key.lower())

    def _normalize_value(self, value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()
