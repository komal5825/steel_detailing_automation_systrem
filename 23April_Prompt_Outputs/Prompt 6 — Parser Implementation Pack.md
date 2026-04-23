# P6 — PARSER IMPLEMENTATION
## Infiniti Solutions Steel Detailing Automation — Phase 5 Desktop Build
**Document ID**: IFS-P6-PARSER-20260423  
**Authority Baseline**: IFS-RULE-REG-FINAL-20260423 · MasterDB v3+  
**Depends On**: P4_SQLite_Schema_Implementation, P5_Rule_Engine_Implementation  
**Status**: IMPLEMENTATION READY — Parser Team Deliverable

---

## 1. PARSER ARCHITECTURE

### 1.1 Design Principles

- **Structured > PDF always.** P1 structured data (STAAD, MBS, ETABS) overrides P7 PDF for all governing fields.
- **No historical data override.** P8 historical source is PROHIBITED for governing, derived, control, and output-only fields.
- **Every field must track source.** `source_file_id`, `source_priority_rank`, `confidence_score`, and `extraction_method` are mandatory for every value written to `field_value_store`.
- **One parser output per field per source.** Conflicts resolved by `conflict_rule_master`, not by parser.
- **Partial extraction is valid.** Parser reports what it found; missing fields stay `UNRESOLVED` (never guessed).
- **OCR is last resort.** Image PDF extractions always flag confidence < 80% → mandatory manual review (R-027, R-168).

### 1.2 Parser Module Structure

```
parser_layer/
├── parser_router.py            — Identifies file type; dispatches to correct parser
├── archive_extractor.py        — ZIP/RAR recursive extraction
├── staad_parser/
│   ├── staad_main.py           — .std file main parser (HIGHEST PRIORITY)
│   ├── staad_member_table.py   — Member section/length extraction
│   ├── staad_bolt_table.py     — Bolt extraction (known incomplete — special handling)
│   ├── staad_load_extractor.py — Load cases and support reactions
│   └── staad_normaliser.py     — Normalise to field_master schema
├── mbs_parser/
│   ├── mbs_main.py             — MBS XML/text parser
│   ├── mbs_geometry.py         — Bay, grid, building dimensions
│   ├── mbs_sections.py         — Section schedules (triggers IS808 lookup if name-only)
│   ├── mbs_connection.py       — Connection data (often absent — triggers FB-RULE-016)
│   └── mbs_normaliser.py
├── etabs_parser/
│   ├── etabs_main.py           — Excel export parser (openpyxl + pandas)
│   ├── etabs_story.py          — Story levels and elevations
│   ├── etabs_sections.py       — Frame section data
│   ├── etabs_reactions.py      — Support reactions for AB design
│   ├── etabs_member_map.py     — Member-to-grid mapping (FB-RULE-018)
│   └── etabs_normaliser.py
├── prota_parser/
│   ├── prota_main.py           — Prota Steel DXF + PDF
│   ├── prota_dxf.py            — ezdxf geometry extraction
│   ├── prota_pdf.py            — pdfplumber load/reaction data
│   └── prota_normaliser.py
├── cad_parser/
│   ├── cad_main.py             — DWG/DXF via ezdxf + ODA
│   ├── cad_geometry.py         — Grid, member, text extraction
│   └── cad_normaliser.py
├── pdf_parser/
│   ├── pdf_text.py             — pdfplumber for text PDFs (P7 secondary)
│   ├── pdf_image.py            — PyMuPDF + Tesseract for image PDFs (lowest confidence)
│   └── pdf_normaliser.py
├── normaliser/
│   ├── unit_normaliser.py      — Unit conversion and suffix enforcement
│   ├── alias_resolver.py       — Resolves aliases via alias_master
│   ├── date_normaliser.py      — ISO date reformatting
│   └── case_normaliser.py      — Uppercase/trim
├── confidence_scorer.py        — Assigns confidence scores per extraction method
├── extraction_logger.py        — Writes to field_extraction_log (immutable)
├── conflict_resolver.py        — Applies conflict_rule_master on multi-source fields
└── parser_test_runner.py       — Runs parser test pack (Section 6)
```

### 1.3 Parser Priority Ladder

```
PRIORITY ORDER (high to low):
P1: STAAD .std    → Custom Python parser (HIGHEST — bolt table may be incomplete)
P2: MBS XML/text  → Custom XML/text parser (geometry + connection schedule)
P3: ETABS Excel   → openpyxl + pandas (structural data + support reactions)
P4: Prota Steel DXF → ezdxf (geometry layer; loads come from Prota PDF)
P5: Prota PDF Reports → pdfplumber (loads, reactions, specs)
P6: DWG/DXF (generic) → ODA File Converter + ezdxf
P7: PDF (text) → pdfplumber (SECONDARY — never overrides P1–P6 for engineering fields)
P8: Image PDF   → PyMuPDF + Tesseract (LOWEST — always confidence < 80%; manual review mandatory)
Historical → PROHIBITED for governing/derived/control fields (FB-RULE-009)
```

---

## 2. SOURCE-BY-SOURCE PARSING PLAN

### 2A — STAAD PRO (.std) PARSER

**Priority**: P1 (Highest)  
**Known Risk**: Bolt table often incomplete. Special handling mandatory (FB-RULE-013, FB-RULE-014, FB-RULE-015).

**Fields Targeted**: Grid data, member sections, member lengths, member types, support reactions, load cases, connection type (when available), bolt data (when available).

**Parsing Logic**:

```python
class STAADParser:
    """
    Parses Tekla STAAD Pro .std files.
    File structure: keyword-delimited text blocks.
    """

    KEYWORD_BLOCKS = {
        'JOINT COORDINATES':    '_parse_joint_coordinates',
        'MEMBER INCIDENCES':    '_parse_member_incidences',
        'MEMBER PROPERTY':      '_parse_member_properties',
        'CONSTANTS':            '_parse_material_constants',
        'SUPPORT':              '_parse_supports',
        'LOAD LIST':            '_parse_load_cases',
        'JOINT LOADS':          '_parse_joint_loads',
        'MEMBER LOADS':         '_parse_member_loads',
        'BOLT TABLE':           '_parse_bolt_table',    # May be empty/absent
        'CONNECTION TABLE':     '_parse_connection_table',
    }

    def parse(self, file_path: str, project_uuid: str) -> ParserOutput:
        output = ParserOutput(source_type='STAAD', priority_rank=1)
        blocks = self._split_into_blocks(file_path)

        for block_name, parser_method in self.KEYWORD_BLOCKS.items():
            if block_name in blocks:
                getattr(self, parser_method)(blocks[block_name], output)

        # CRITICAL: Bolt table completeness check (FB-RULE-013, FB-RULE-014, FB-RULE-015)
        self._check_bolt_completeness(output)
        self._check_connection_type_completeness(output)

        return output

    def _parse_member_properties(self, block_text: str, output: ParserOutput):
        """
        Extracts: member_section_size (F-063), member_type (F-064),
                  member_length (F-066 — derived from joint coords)
        """
        for line in block_text.splitlines():
            if 'PRISMATIC' in line or 'TABLE' in line:
                # Extract section name; resolve against steel_section_master
                section = self._extract_section_name(line)
                member_ids = self._extract_member_ids(line)
                for mid in member_ids:
                    output.add_field('F-063', section, member_ref=mid,
                                     confidence=95, method='structured_keyword')

    def _parse_bolt_table(self, block_text: str, output: ParserOutput):
        """
        Bolt data extraction. STAAD bolt tables are frequently incomplete.
        Extract what exists; flag missing fields as UNRESOLVED — never default.
        """
        for line in block_text.splitlines():
            # Extract diameter (F-081) — often present
            diameter = self._extract_bolt_diameter(line)
            # Extract grade (F-082) — often ABSENT (FB-RULE-013)
            grade = self._extract_bolt_grade(line)
            # Extract spacing (F-084, F-085) — absent for moment connections (FB-RULE-014)
            spacing_x = self._extract_spacing_x(line)
            spacing_y = self._extract_spacing_y(line)

            if diameter:
                output.add_field('F-081', diameter, confidence=90, method='structured_keyword')
            if grade:
                output.add_field('F-082', grade, confidence=90, method='structured_keyword')
            else:
                output.add_unresolved('F-082', reason='FB-RULE-013: STAAD bolt grade absent — no default')

    def _check_bolt_completeness(self, output: ParserOutput):
        """Apply FB-RULE-013, FB-RULE-014, FB-RULE-015."""
        if output.has_field('F-081') and not output.has_field('F-082'):
            output.add_flag('FB-RULE-013', 'BOLT_GRADE_MISSING_STAAD')
        if not output.has_field('F-075'):
            output.add_flag('FB-RULE-015', 'CONNECTION_TYPE_UNDEFINED')
        if output.has_field('F-081') and not output.has_field('F-084'):
            output.add_flag('FB-RULE-014', 'BOLT_SPACING_MISSING_REVIEW_REQUIRED')
```

**STAAD Output Fields**:
- Grid/layout: F-039 to F-044 (from joint coordinates — derived as grid pattern)
- Building dims: F-045, F-046, F-047 (from joint extents)
- Member data: F-063, F-064, F-066, F-067 (member ID as mark), F-069
- Material: F-065 (from CONSTANTS block)
- Bolt: F-081, F-082, F-083, F-084, F-085, F-086, F-087 (when present)
- Reactions: F-192-equivalent data for AB design

---

### 2B — MBS PARSER

**Priority**: P2  
**Known Risk**: Often geometry-rich but loads/reactions absent (FB-RULE-016). Sections may be name-only requiring IS808 lookup (FB-RULE-017).

```python
class MBSParser:
    """
    Parses MBS (Metal Building Software) XML export or structured text reports.
    MBS typically provides: building geometry, frame types, purlins, girts,
    sheeting specs, connection schedules.
    """

    def parse(self, file_path: str, project_uuid: str) -> ParserOutput:
        output = ParserOutput(source_type='MBS', priority_rank=2)
        
        # Try XML first, fall back to structured text
        if self._is_xml(file_path):
            root = ET.parse(file_path).getroot()
            self._parse_xml(root, output)
        else:
            self._parse_text(file_path, output)

        # Check for loads (FB-RULE-016)
        if not output.has_any(['wind_speed', 'seismic_category', 'dead_load']):
            output.add_flag('FB-RULE-016', 'MBS_LOADS_ABSENT')

        # Check for section properties vs section names (FB-RULE-017)
        self._resolve_sections(output)
        return output

    def _resolve_sections(self, output: ParserOutput):
        """
        MBS may give section names (e.g. '200UB25.4') without dimensions.
        Trigger IS808 lookup for standard sections.
        Built-up sections MUST NOT be looked up (FB-RULE-021).
        """
        for section_field in output.get_fields('F-063'):
            section_name = section_field.value
            if self._is_standard_section(section_name):
                # Lookup from steel_section_master
                dims = self._lookup_section(section_name)
                if dims:
                    section_field.confidence = min(section_field.confidence, 85)
                    section_field.add_flag('SECTION_LOOKUP_APPLIED')
                    section_field.method = 'P2_LOOKUP'
            elif self._is_buildup_indicator(section_name):
                # Never lookup built-up — flag for engineer input
                section_field.status = 'UNRESOLVED'
                section_field.add_flag('FB-RULE-021: BUILDUP_NO_LOOKUP')
```

**MBS Output Fields**:
- Frame: F-060 (frame_type), F-059 (roof_span), F-054 (roof_slope), F-056 (eave_height)
- Grid: F-039, F-040, F-041, F-042, F-172 (bay geometry)
- Building: F-045, F-046, F-047, F-048
- Sections: F-063, F-064, F-070 (weight, via lookup)
- Sheeting: F-091 to F-100 (zone codes, gauge, fastener type)
- Purlins/Girts: F-122, F-123, F-124

---

### 2C — ETABS PARSER

**Priority**: P3  
**Known Risk**: Member-to-grid mapping may be incomplete for complex buildings (FB-RULE-018). Support reactions mandatory for AB design (FB-RULE-019).

```python
class ETABSParser:
    """
    Parses ETABS Excel export (.xlsx).
    Key sheets: 'Story Data', 'Frame Sections', 'Frame Assignments',
                'Joint Reactions', 'Frame Geometry'
    """

    REQUIRED_SHEETS = ['Story Data', 'Frame Sections', 'Joint Reactions']

    def parse(self, file_path: str, project_uuid: str) -> ParserOutput:
        output = ParserOutput(source_type='ETABS', priority_rank=3)
        wb = pd.read_excel(file_path, sheet_name=None, engine='openpyxl')

        self._check_required_sheets(wb, output)
        self._parse_story_data(wb.get('Story Data'), output)
        self._parse_frame_sections(wb.get('Frame Sections'), output)
        self._parse_joint_reactions(wb.get('Joint Reactions'), output)
        self._parse_member_grid_mapping(wb.get('Frame Assignments'), output)
        return output

    def _parse_joint_reactions(self, df, output: ParserOutput):
        """
        Support reactions mandatory before AB design (FB-RULE-019).
        Partial reactions = unsafe = treat as absent.
        """
        if df is None or df.empty:
            output.add_flag('FB-RULE-019', 'ETABS_REACTIONS_MISSING')
            output.add_unresolved('F-reaction_data',
                reason='Support reactions absent — AB design blocked until re-export')
            return

        # Check for partial data (some supports have no reactions)
        support_count = df['Joint'].nunique()
        reaction_count = df.dropna(subset=['FX', 'FY', 'FZ']).shape[0]
        if reaction_count < support_count:
            output.add_flag('FB-RULE-019', 'PARTIAL_REACTIONS_UNSAFE')
            output.add_unresolved('F-reaction_data',
                reason='Partial support reactions detected — all reactions required')

    def _parse_member_grid_mapping(self, df, output: ParserOutput):
        """
        FB-RULE-018: > 20% unmapped members → BLOCK; < 20% → WARN.
        """
        if df is None or df.empty:
            output.add_flag('FB-RULE-018', 'MEMBER_GRID_MAPPING_ABSENT')
            return

        total = len(df)
        unmapped = df[df['GridPoint'].isna()].shape[0]
        pct_unmapped = (unmapped / total * 100) if total > 0 else 100

        if pct_unmapped > 20:
            output.add_flag('FB-RULE-018', f'MEMBER_GRID_MAPPING_INCOMPLETE_{pct_unmapped:.1f}pct')
            output.set_blocking_flag('ETABS_MAPPING_BLOCK')
        elif pct_unmapped > 0:
            output.add_flag('FB-RULE-018_WARN', f'{pct_unmapped:.1f}% members unmapped — review')
```

**ETABS Output Fields**:
- Story levels: F-056 (eave_height), F-057 (ridge), F-129 (mezzanine level)
- Crane rail: F-128 (crane_rail_level)
- Sections: F-063, F-064, F-065
- Reactions: Support reaction data for AB calculation input
- Frame assignments: F-072 (member_location)

---

### 2D — PROTA STEEL PARSER

**Priority**: P4 (DXF geometry) + P5 (PDF loads)  
**Known Risk**: DXF has geometry; PDF has loads. If PDF absent, AB generation blocked (FB-RULE-022).

```python
class ProtaParser:

    def parse(self, dxf_path: str, pdf_path: str, project_uuid: str) -> ParserOutput:
        output = ParserOutput(source_type='Prota', priority_rank=4)

        if dxf_path:
            self._parse_dxf(dxf_path, output)
        
        if pdf_path:
            output.priority_rank = 5  # PDF elevates to P5 for load data
            self._parse_pdf(pdf_path, output)
        else:
            output.add_flag('FB-RULE-022', 'LOADS_PENDING: Prota PDF absent')
            output.add_unresolved('F-reaction_data',
                reason='Prota PDF not provided — loads/reactions unavailable')

        return output

    def _parse_dxf(self, dxf_path: str, output: ParserOutput):
        """Extract geometry from Prota DXF export via ezdxf."""
        doc = ezdxf.readfile(dxf_path)
        msp = doc.modelspace()
        self._extract_grid_lines(msp, output)
        self._extract_column_positions(msp, output)
        self._extract_member_lines(msp, output)
        self._extract_levels(msp, output)
        self._extract_section_annotations(msp, output)
```

---

### 2E — GENERIC CAD PARSER (DWG/DXF)

**Priority**: P6

```python
class CADParser:
    """
    Parses generic DWG/DXF files (not Prota-specific).
    DWG → converted to DXF via ODA File Converter (free tool) before parsing.
    """

    ODA_CONVERTER_PATH = '/usr/local/bin/ODAFileConverter'

    def parse(self, file_path: str, project_uuid: str) -> ParserOutput:
        output = ParserOutput(source_type='DXF_Generic', priority_rank=6)
        
        # Convert DWG to DXF if needed
        if file_path.endswith('.dwg'):
            dxf_path = self._convert_dwg_to_dxf(file_path)
        else:
            dxf_path = file_path

        doc = ezdxf.readfile(dxf_path)
        msp = doc.modelspace()

        self._extract_grid_lines(msp, output)
        self._extract_text_annotations(msp, output)
        self._extract_member_marks(msp, output)
        self._extract_dimensions(msp, output)
        return output

    def _convert_dwg_to_dxf(self, dwg_path: str) -> str:
        """Convert DWG to DXF using ODA File Converter."""
        out_dir = os.path.dirname(dwg_path)
        subprocess.run([self.ODA_CONVERTER_PATH, out_dir, out_dir,
                        'ACAD2018', 'DXF', '0', '1', dwg_path], check=True)
        return dwg_path.replace('.dwg', '.dxf')
```

---

### 2F — PDF PARSERS (TEXT AND IMAGE)

```python
class PDFTextParser:
    """Priority P7 — SECONDARY ONLY. Never overrides P1–P6 for engineering fields."""

    def parse(self, file_path: str, project_uuid: str) -> ParserOutput:
        output = ParserOutput(source_type='PDF_Text', priority_rank=7)
        output.add_flag('PDF_FALLBACK_APPLIED')  # Always flag PDF use
        
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                tables = page.extract_tables()
                self._parse_text_blocks(text, output)
                self._parse_tables(tables, output)

        # Set max confidence for PDF extraction
        output.cap_confidence(85)  # PDF text never > 85% confidence
        return output


class PDFImageParser:
    """Priority P8 equivalent — image PDFs via OCR. Lowest confidence. Always flags review."""

    def parse(self, file_path: str, project_uuid: str) -> ParserOutput:
        output = ParserOutput(source_type='PDF_Image', priority_rank=8)
        output.add_flag('OCR_USED_MANDATORY_REVIEW')

        doc = fitz.open(file_path)
        for page_num in range(len(doc)):
            page = doc[page_num]
            pix = page.get_pixmap(dpi=300)
            img = Image.open(io.BytesIO(pix.tobytes()))
            ocr_text = pytesseract.image_to_string(img)
            self._parse_ocr_text(ocr_text, output, page_num)

        # OCR confidence is always capped below 80% → triggers R-027
        output.cap_confidence(75)  # Always triggers mandatory manual review
        return output
```

---

### 2G — ARCHIVE EXTRACTOR

```python
class ArchiveExtractor:
    """Handles ZIP and RAR files. Extracts recursively. Returns list of file paths."""

    def extract(self, archive_path: str, project_uuid: str) -> List[str]:
        extracted = []
        extract_dir = f'/projects/{project_uuid}/Raw_Inputs/extracted/'
        os.makedirs(extract_dir, exist_ok=True)

        if archive_path.endswith('.zip'):
            with zipfile.ZipFile(archive_path) as zf:
                zf.extractall(extract_dir)
        elif archive_path.endswith('.rar'):
            with rarfile.RarFile(archive_path) as rf:
                rf.extractall(extract_dir)

        for root, _, files in os.walk(extract_dir):
            for f in files:
                full_path = os.path.join(root, f)
                extracted.append(full_path)
                # Recurse into nested archives
                if f.endswith('.zip') or f.endswith('.rar'):
                    extracted.extend(self.extract(full_path, project_uuid))

        return extracted
```

---

## 3. NORMALIZED OUTPUT MAP

### 3.1 ParserOutput Schema

All parsers produce a `ParserOutput` object normalised to `field_master` field IDs:

```python
@dataclass
class FieldExtraction:
    field_id: str           # F-001 to F-196
    value: str              # Normalised string value
    raw_value: str          # Original raw string before normalisation
    confidence_score: int   # 0–100
    source_type: str        # STAAD, MBS, ETABS, etc.
    priority_rank: int      # 1–8
    extraction_method: str  # structured_keyword, table_lookup, text_regex, OCR, derived
    member_ref: str = None  # member ID if member-scoped
    page_ref: str = None    # page/section reference in source file
    flags: List[str] = None # Warning/error flags applied
    status: str = 'POPULATED'  # POPULATED, UNRESOLVED, DERIVED_BROKEN

@dataclass
class ParserOutput:
    source_type: str
    priority_rank: int
    extractions: List[FieldExtraction]
    blocking_flags: List[str]         # Flags that must block generation
    warning_flags: List[str]          # Non-blocking flags
    parse_errors: List[str]           # Technical parse failures
```

### 3.2 Field-to-Source Mapping Summary

| Field Group | Primary Parser | Fallback | Notes |
|---|---|---|---|
| Grid spacing (F-039/F-040/F-172) | MBS (P2) / STAAD (P1 derived) | ETABS (P3) / Prota DXF (P4) | Override prohibited |
| Building dims (F-045/F-046/F-047) | STAAD joint extents (P1) | MBS (P2) | Override prohibited |
| Roof params (F-054/F-056/F-059) | MBS (P2) / STAAD (P1) | Prota DXF (P4) | Override prohibited |
| Member section (F-063) | STAAD MEMBER PROPERTY (P1) | MBS (P2, with lookup) | Override with DE approval only |
| Member mark (F-067) | STAAD member ID (P1) | MBS schedule (P2) | Override prohibited once assigned |
| Bolt data (F-081–F-089) | STAAD BOLT TABLE (P1, often incomplete) | MBS connection sched (P2) → P5 Manual | Override prohibited; FB-RULE-013/014 |
| Base plate (F-080/F-090) | STAAD / MBS | Prota PDF (P5) | Override prohibited (size); approval (thickness) |
| Support reactions | ETABS (P3) / STAAD (P1) | Prota PDF (P5) | FB-RULE-019: all required |
| Sheeting (F-091–F-100) | MBS (P2) | Prota PDF (P5) | Zone mandatory |
| Connection type (F-075) | STAAD (P1) / MBS (P2) | Manual (P5) | Override prohibited; never inferred |
| Shipping/Install (F-108–F-120) | Manual (P5) | — | System-populated from member_registry |
| Metadata (F-001/F-010 etc.) | Project intake (P5) | — | DC controlled |

---

## 4. CONFIDENCE AND TRACEABILITY MAPPING

### 4.1 Confidence Score Assignment

```python
CONFIDENCE_BASELINE = {
    'STAAD_structured_keyword':    95,  # Direct keyword parse — very reliable
    'MBS_xml_structured':          90,  # MBS XML well-structured
    'MBS_text_structured':         85,
    'MBS_P2_LOOKUP':               82,  # Section name resolved via IS808
    'ETABS_excel_structured':      88,
    'Prota_dxf_ezdxf':             85,
    'Prota_pdf_pdfplumber':        78,
    'DXF_generic_ezdxf':           75,
    'PDF_text_pdfplumber':         72,
    'PDF_image_tesseract_OCR':     60,  # Always below 80% → mandatory review
    'Manual_P5_input':             100, # Manual is trusted (validation enforced)
    'Derived_calculation':         98,  # Calculation from trusted inputs
}

def assign_confidence(method: str, context_bonus: int = 0) -> int:
    base = CONFIDENCE_BASELINE.get(method, 70)
    return min(100, base + context_bonus)
```

**Rules applied to confidence**:
- Any OCR extraction: confidence capped at 75 (always triggers R-027 → T-015 manual review)
- PDF text extraction for governing fields: confidence capped at 80 (R-165 applies)
- Missing bolt grade from STAAD (FB-RULE-013): field set to UNRESOLVED (not a confidence number)
- Section lookup applied (FB-RULE-017): confidence reduced by 8 points

### 4.2 Mandatory Traceability Fields

Every row written to `field_population_event` must carry:

| Attribute | Source |
|---|---|
| `project_uuid` | Project context |
| `field_id` | F-001 to F-196 |
| `value_populated` | Normalised value |
| `source_priority_rank` | P1–P8 integer |
| `source_file_id` | FK to `project_file_registry` |
| `source_path` | Line number, sheet name, XML XPath, or DXF layer name |
| `extraction_method` | From CONFIDENCE_BASELINE keys above |
| `transformation_applied` | Normalisation steps (alias, unit, case, date) |
| `confidence_score` | 0–100 |
| `agent_id` | Parser agent ID (e.g. P2-01-STAAD) |
| `event_timestamp` | Auto |

### 4.3 Source Conflict Resolution

When two parsers extract different values for the same field:

```python
class ConflictResolver:

    def resolve(self, extractions: List[FieldExtraction], field_id: str, db_conn) -> FieldExtraction:
        """
        Apply conflict_rule_master logic.
        Default: higher priority_rank wins (lower number = higher priority).
        Structured always beats PDF.
        """
        if len(extractions) <= 1:
            return extractions[0] if extractions else None

        # Sort by priority rank ascending (P1 < P2 < ... < P8)
        sorted_ext = sorted(extractions, key=lambda x: x.priority_rank)
        winner = sorted_ext[0]
        losers = sorted_ext[1:]

        # Log conflict for all non-winning extractions
        for loser in losers:
            if loser.value != winner.value:
                self._log_conflict(field_id, winner, loser, db_conn)

        # Check conflict_rule_master for any special resolution rules
        rule = db_conn.execute("""
            SELECT * FROM conflict_rule_master
            WHERE field_id = ? AND source_a_rank = ? AND source_b_rank = ?
        """, (field_id, winner.priority_rank, losers[0].priority_rank if losers else 0)).fetchone()

        if rule and rule['resolution'] == 'MANUAL_REVIEW':
            # Flag for manual review regardless of priority winner
            winner.flags.append('CONFLICT_MANUAL_REVIEW_REQUIRED')

        return winner
```

---

## 5. FAILURE AND ESCALATION LOGIC

### 5.1 Parser Failure Categories

| Failure Type | Code | Action |
|---|---|---|
| File unreadable (corrupt, wrong format) | `PARSE_UNREADABLE` | Log to `benchmark_defect_log`; escalate IT |
| File type misidentified | `PARSE_MISCLASSIFIED` | Re-classify; re-route; log warning |
| Required block absent (e.g. BOLT TABLE missing) | `PARSE_BLOCK_ABSENT` | Apply fallback chain; log flag |
| OCR failure (image quality too low) | `PARSE_OCR_FAIL` | Set confidence=0; UNRESOLVED; escalate Engineering |
| Archive password-protected | `PARSE_ENCRYPTED` | Log error; escalate IT for extraction |
| DWG conversion failure (ODA) | `PARSE_DWG_CONVERT_FAIL` | Try alternate DXF; escalate IT |
| Partial extraction (some fields found, others not) | `PARSE_PARTIAL` | Populate found fields; UNRESOLVED for missing |
| Zero fields extracted | `PARSE_EMPTY_RESULT` | Full UNRESOLVED for all target fields; escalate Engineering |

### 5.2 Escalation Decision Tree

```
Parser runs on file
    ↓
Extract fields
    ↓
IF PARSE_UNREADABLE or PARSE_DWG_CONVERT_FAIL:
    → Escalate IT immediately
    → Try next parser in priority ladder (if available)
    ↓
IF PARSE_EMPTY_RESULT:
    → Escalate Engineering
    → All target fields = UNRESOLVED
    ↓
IF governing engineering fields = UNRESOLVED:
    → Rule R-166: field must stay UNRESOLVED (never guess)
    → Rule R-196: source priority check triggers Release-Blocker at gate
    → Generate manual_review_event (T-001)
    ↓
IF confidence < 80% on any field:
    → Rule R-027: mandatory manual review triggered (T-015)
    → Field value stored but flagged PENDING_REVIEW
    ↓
IF FB-RULE special cases triggered (013/014/015/016/019/021/022):
    → Apply specific escalation per FB-RULE (see P5 Fallback Enforcement Logic)
    → Generation blocked per rule severity
```

### 5.3 Fallback Trigger Per Parser

```python
PARSER_FALLBACK_ORDER = {
    # If STAAD bolt grade absent (FB-RULE-013):
    'F-082': ['STAAD(P1)', 'MBS_connection_schedule(P2)', 'Manual_P5_input'],
    # If STAAD connection type absent (FB-RULE-015):
    'F-075': ['STAAD(P1)', 'MBS_connection_schedule(P2)', 'BLOCK_DO_NOT_INFER'],
    # If MBS loads absent (FB-RULE-016):
    'F-wind_data': ['MBS(P2)', 'ETABS(P3)', 'Manual_P5+DE_signoff'],
    # If ETABS reactions partial/absent (FB-RULE-019):
    'F-reactions': ['ETABS(P3)', 'STAAD(P1)', 'Prota_PDF(P5)', 'Manual_P5+DE_signoff'],
}
```

---

## 6. PARSER TEST PACK

### 6.1 Test Categories

| Category | Test Count | Description |
|---|---|---|
| STAAD completeness | 12 tests | Full file, bolt-only partial, no bolt table, no connection |
| MBS parsing | 8 tests | XML full, text partial, no loads, section names only |
| ETABS parsing | 6 tests | Full Excel, partial reactions, no member mapping |
| Prota parsing | 6 tests | DXF + PDF, DXF only, PDF only |
| PDF text parsing | 4 tests | Text extraction, table extraction, mixed |
| OCR/image | 3 tests | High quality, low quality, unreadable |
| Archive handling | 4 tests | ZIP flat, ZIP nested, RAR, mixed |
| Conflict resolution | 8 tests | P1 vs P2 agree, P1 vs P2 disagree, P7 vs P1 |
| Normalisation | 10 tests | Dates, units, aliases, case, null strings |
| Fallback chains | 12 tests | FB-RULE-013 to FB-RULE-022 |
| **TOTAL** | **73 tests** | |

### 6.2 Representative Test Cases

```python
# TEST 1: STAAD bolt grade missing (FB-RULE-013)
def test_staad_bolt_grade_missing():
    # Input: STAAD .std file with BOLT TABLE containing diameter only (no grade)
    output = STAADParser().parse('test_files/staad_no_bolt_grade.std', 'TEST-001')
    assert output.has_field('F-081')  # diameter extracted
    assert not output.has_field('F-082')  # grade absent
    assert 'FB-RULE-013' in output.blocking_flags
    assert output.get_field_status('F-082') == 'UNRESOLVED'
    # Validate that no default (e.g. 8.8) was inserted
    assert output.get_field_value('F-082') is None

# TEST 2: ETABS member-grid mapping > 20% unmapped (FB-RULE-018)
def test_etabs_mapping_threshold():
    output = ETABSParser().parse('test_files/etabs_25pct_unmapped.xlsx', 'TEST-002')
    assert 'FB-RULE-018' in output.blocking_flags
    assert output.has_flag('MEMBER_GRID_MAPPING_INCOMPLETE')
    assert output.blocking_flag_active('ETABS_MAPPING_BLOCK')

# TEST 3: PDF vs STAAD conflict on grid spacing (R-165)
def test_pdf_cannot_override_structured():
    staad_out = STAADParser().parse('test_files/staad_6m_grid.std', 'TEST-003')
    pdf_out = PDFTextParser().parse('test_files/pdf_7m_grid.pdf', 'TEST-003')
    combined = ConflictResolver().resolve(
        [staad_out.get('F-039'), pdf_out.get('F-039')], 'F-039', db_conn)
    # STAAD (P1) must win; PDF (P7) must lose
    assert combined.value == '6000'  # STAAD value
    assert combined.priority_rank == 1
    assert 'CONFLICT_LOGGED' in combined.flags

# TEST 4: OCR confidence cap (R-027)
def test_ocr_always_below_80():
    output = PDFImageParser().parse('test_files/image_pdf_quality_poor.pdf', 'TEST-004')
    for extraction in output.extractions:
        assert extraction.confidence_score <= 75
    assert output.has_flag('OCR_USED_MANDATORY_REVIEW')

# TEST 5: Historical data hard block (FB-RULE-009)
def test_historical_data_prohibited_for_governing():
    # Simulate attempt to populate F-039 (grid_spacing — override prohibited) from P8 source
    extraction = FieldExtraction(field_id='F-039', value='6000',
                                  source_type='Historical', priority_rank=8,
                                  confidence_score=95, extraction_method='historical_job_lookup')
    result = populate_field('TEST-005', extraction, db_conn)
    assert result.status == 'BLOCKED'
    assert 'FB-RULE-009' in result.flags
    assert 'HISTORICAL_DATA_PROHIBITED' in result.error_flags

# TEST 6: MBS section name resolved via IS808 lookup (FB-RULE-017)
def test_mbs_section_lookup_flagged():
    output = MBSParser().parse('test_files/mbs_section_names_only.xml', 'TEST-006')
    for ext in output.extractions:
        if ext.field_id == 'F-063':
            assert ext.method == 'P2_LOOKUP'
            assert 'SECTION_LOOKUP_APPLIED' in ext.flags
            assert ext.confidence_score <= 85  # Reduced by lookup

# TEST 7: Archive recursive extraction
def test_zip_nested_extraction():
    extractor = ArchiveExtractor()
    files = extractor.extract('test_files/nested_archive.zip', 'TEST-007')
    staad_files = [f for f in files if f.endswith('.std')]
    assert len(staad_files) >= 1  # Must find nested STAAD file

# TEST 8: Built-up section no lookup (FB-RULE-021)
def test_buildup_never_lookup():
    output = MBSParser().parse('test_files/mbs_buildup_section.xml', 'TEST-008')
    for ext in output.extractions:
        if ext.field_id == 'F-063' and 'BUILDUP' in str(ext.value):
            assert ext.status == 'UNRESOLVED'
            assert 'FB-RULE-021' in ext.flags
            assert ext.method != 'P2_LOOKUP'  # Must NOT have attempted lookup

# TEST 9: Prota DXF without PDF (FB-RULE-022)
def test_prota_dxf_no_pdf_blocks_ab():
    output = ProtaParser().parse('test_files/prota_geometry.dxf', None, 'TEST-009')
    assert 'FB-RULE-022' in output.warning_flags
    assert 'LOADS_PENDING' in output.warning_flags
    assert output.has_unresolved('F-reaction_data')

# TEST 10: Unit normalisation
def test_unit_normalisation():
    raw_values = ['1234mm.', '1.234M', 'KG 500', 'M20 bolt']
    normalised = [UnitNormaliser().normalise(v) for v in raw_values]
    assert normalised[0] == '1234'   # mm suffix stripped for numeric storage
    assert normalised[1] == '1234'   # 1.234M → 1234mm → 1234 numeric
    assert normalised[2] == '500'    # KG prefix stripped
    assert normalised[3] == '20'     # M prefix stripped for bolt diameter
```

---

## 7. KNOWN SOURCE RISKS

| Source | Risk | Severity | Mitigation |
|---|---|---|---|
| STAAD .std bolt table | Frequently incomplete — grade and spacing often absent | HIGH | FB-RULE-013/014/015 mandatory escalation; never default |
| MBS loads/reactions | Geometry-rich but load data often absent in export | HIGH | FB-RULE-016: ETABS fallback; else Manual+DE |
| ETABS member-grid mapping | Complex buildings: > 20% unmapped common | MEDIUM | FB-RULE-018 threshold check; Detailing Lead reconciliation |
| Prota PDF loads | PDF may not be exported along with DXF | MEDIUM | FB-RULE-022: AB blocked; warn on project creation |
| Image PDFs (scanned drawings) | OCR errors, rotated text, low DPI | HIGH | Hard confidence cap 75%; always manual review |
| DWG ODA conversion | ODA converter may fail on very old R14 format files | LOW | Detect version; escalate IT if R14 or older |
| ZIP with password | Encrypted archives block all extraction | MEDIUM | Detect; escalate IT immediately |
| Built-up sections in MBS | Name-only: never has plate dims | HIGH | FB-RULE-021: plate schedule from DE mandatory |
| Multi-revision uploads | Multiple versions of same file → revision confusion | MEDIUM | P2-01 revision ranking logic selects governing file |
| STAAD connection type inference | Engineers sometimes rely on end-condition inference | HIGH | FB-RULE-015: hard prohibition on inference; explicit only |

---

*P6 — Parser Implementation | IFS-P6-PARSER-20260423 | Parser Team Deliverable | Phase 5 Desktop Build*
