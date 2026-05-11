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

# Maps MBS internal extracted-field names to canonical F-codes.
# Fields not listed here fall back to the RAW-MBS-<KEY> code and are
# normalized later by FieldDictionary if an alias exists.
_MBS_FIELD_CODE_MAP: dict[str, str] = {
    # Document metadata
    "draw_date":               "F-024",
    "created_date":            "F-017",
    "drawing_class":           "F-020",
    "size":                    "F-028",
    "scale":                   "F-029",
    # Project identity
    "project_code":            "F-001",
    "project_name":            "F-002",
    "company_name":            "F-010",
    "project_design_standard": "F-191",
    # Building layout
    "bldg_type":               "F-048",
    "building_width_mm":       "F-046",
    "building_length_mm":      "F-045",
    # Horizontal grid (bay spacings along building length)
    "col_label_x":             "F-041",
    "bay_spacing_x":           "F-039",
    "origin_x":                "F-043",
    "bay_seq":                 "F-171",
    "bay_dim":                 "F-172",
    # Vertical grid (bay spacings across building width)
    "col_label_y":             "F-042",
    "bay_spacing_y":           "F-040",
    "origin_y":                "F-044",
    # Anchor bolt details (section 20)
    "bolt_dia":                "F-081",
    "bolt_qty":                "F-083",
    "bolt_sp_x":               "F-084",
    "bolt_sp_y":               "F-085",
    "embed_depth":             "F-086",
    "bolt_proj":               "F-087",
    "bolt_orient":             "F-088",
    "ab_code":                 "F-089",
    # Base plate
    "bp_size":                 "F-080",
    "bp_thick":                "F-090",
    # Connection
    "conn_type":               "F-075",
    "conn_bolt_qty":           "F-078",
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
            elif "JOBID" in sec_name and sec_num == 1:
                self._parse_jobid(body, extracted)
            elif sec_num == 20 and (
                "DETAILS" in sec_name
                or "BOLT" in sec_name
                or "ANCHOR" in sec_name
                or not any(k in sec_name for k in (
                    "TITLE", "DRAWING", "BUILDING", "DESIGN",
                    "JOBID", "HORIZONTAL", "VERTICAL",
                ))
            ):
                self._parse_details_section(body, extracted)
            elif "HORIZONTAL GRID" in sec_name:
                self._parse_horizontal_grid(body, extracted)
            elif "VERTICAL GRID" in sec_name:
                self._parse_vertical_grid(body, extracted)

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
                extracted.setdefault("bldg_type",            btype)       # F-048
                extracted.setdefault("building_width_mm",    str(width))  # F-046
                extracted.setdefault("building_length_mm",   str(length)) # F-045
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

        extracted.setdefault("bolt_dia",     str(dia_int))                           # F-081
        extracted.setdefault("bolt_qty",     str(bolt_qty))                          # F-083
        extracted.setdefault("bolt_sp_x",    det["a"])                               # F-084
        extracted.setdefault("bolt_sp_y",    det["b"])                               # F-085
        extracted.setdefault("embed_depth",  det["d"])                               # F-086
        extracted.setdefault("bolt_proj",    det["e"])                               # F-087
        extracted.setdefault("bolt_orient",  orient)                                 # F-088
        extracted.setdefault("ab_code",      det["id"])                              # F-089
        extracted.setdefault("bp_size",
                             f"{det['bp_width']} x {det['bp_length']}")              # F-080
        extracted.setdefault("bp_thick",     det["bp_thick"])                        # F-090
        extracted.setdefault("conn_type",    "Bolted")                               # F-075
        extracted.setdefault("conn_bolt_qty", str(bolt_qty))                         # F-078

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

    # ---------------------------------------------------------------------------
    # Shared helpers
    # ---------------------------------------------------------------------------

    def _clean_key(self, key: str) -> str:
        return re.sub(r"[^a-z0-9]", "", key.lower())

    def _normalize_value(self, value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()
