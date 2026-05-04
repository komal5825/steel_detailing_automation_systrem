"""
P2-03 Anchor Bolt Generation Agent — Phase 2 Step 17.

Workflow:
  1. Load conflict-resolved field map from DB (build_resolved_field_map).
  2. Extract bolt specification, pattern, base plate, grid references,
     and column locations from resolved field values.
  3. Build ab_structured_package.json with full traceability matrix.
  4. Generate three DXF views: Plan, Section, Detail (via ezdxf).
  5. Generate a multi-page PDF drawing (via fitz/PyMuPDF).
  6. Write all outputs to outputs/ab/ and Processed/.
  7. Record hard-gate checkpoint and update Stage record.

AB field codes used (from field_master):
  Grid/Geometry : F-039, F-040, F-041, F-042, F-043, F-044, F-171, F-172
  Bolt spec     : F-081, F-082, F-083, F-084, F-085, F-086, F-087,
                  F-088, F-089, F-192, F-193
  Base plate    : F-080, F-090
  Connection    : F-075, F-078, F-194
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import ezdxf
from sqlalchemy.orm import Session

from app.agents.phase2.output_utils import (
    project_output_dir,
    write_json_output,
    write_processed_json,
)
from app.agents.support.checkpoint import CheckpointManager
from app.db.crud.stages import update_stage_result
from app.db.crud.validation import log_audit_event
from app.db.models import ExtractedFieldValue, StageStatus
from app.db.session import SessionLocal
from app.utils.audit_logger import get_logger
from app.utils.master_db import fetch_ab_required_field_codes
from app.utils.source_priority import build_resolved_field_map

logger = get_logger(__name__)
_CHECKPOINT_MGR = CheckpointManager()

# ---------------------------------------------------------------------------
# AB-specific field code registry
# ---------------------------------------------------------------------------
_GRID_FIELDS = {
    "F-039": ("grid_spacing_x", "mm"),
    "F-040": ("grid_spacing_y", "mm"),
    "F-041": ("grid_label_x", None),
    "F-042": ("grid_label_y", None),
    "F-043": ("grid_origin_x", "mm"),
    "F-044": ("grid_origin_y", "mm"),
    "F-171": ("bay_sequence_number", None),
    "F-172": ("bay_dimension_mm", "mm"),
}
_BOLT_FIELDS = {
    "F-081": ("bolt_diameter", "mm"),
    "F-082": ("bolt_grade", None),
    "F-083": ("bolt_quantity_per_column", "count"),
    "F-084": ("bolt_spacing_x", "mm"),
    "F-085": ("bolt_spacing_y", "mm"),
    "F-086": ("bolt_embedment_depth", "mm"),
    "F-087": ("bolt_projection", "mm"),
    "F-088": ("bolt_pattern_orientation", None),
    "F-089": ("anchor_bolt_code", None),
    "F-192": ("bolt_projection_above_ffl", "mm"),
    "F-193": ("grout_pad_thickness", "mm"),
}
_PLATE_FIELDS = {
    "F-080": ("base_plate_size", "mm×mm"),
    "F-090": ("base_plate_thickness", "mm"),
}
_CONN_FIELDS = {
    "F-075": ("connection_type", None),
    "F-078": ("connection_bolt_quantity", "count"),
    "F-194": ("column_base_axis_orientation", None),
}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate_ab_drawings(project_id: str, db: Session | None = None) -> dict:
    owns_session = db is None
    session = db or SessionLocal()
    try:
        result = _generate_ab(UUID(str(project_id)), session)
        session.commit()
        return result
    finally:
        if owns_session:
            session.close()


# ---------------------------------------------------------------------------
# Core implementation
# ---------------------------------------------------------------------------

def _generate_ab(project_id: UUID, db: Session) -> dict:
    log_audit_event(db, "STAGE_STARTED", project_id=project_id, stage_code="P2-03")
    update_stage_result(db, project_id=project_id, stage_code="P2-03",
                        status=StageStatus.RUNNING)

    # 1. Resolved field map
    resolved_map = build_resolved_field_map(db, project_id)
    field_map: dict[str, str] = {
        fc: str(cr.winning_value)
        for fc, cr in resolved_map.items()
        if cr.winning_value is not None
    }

    ab_codes = set(fetch_ab_required_field_codes())

    # 2. Build structured sections
    grid_refs = _build_grid_references(field_map)
    col_locs = _build_column_locations(grid_refs)
    bolt_spec = _build_bolt_specification(field_map)
    bolt_pat = _build_bolt_pattern(field_map)
    base_plate = _build_base_plate(field_map)
    template_map = _build_template_population_map(field_map, resolved_map)
    traceability = _build_traceability_matrix(db, project_id, ab_codes, resolved_map)

    present_ab = [fc for fc in ab_codes if fc in field_map]
    missing_ab = sorted(fc for fc in ab_codes if fc not in field_map)

    ab_package: dict = {
        "project_id": str(project_id),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "GENERATED",
        "grid_references": grid_refs,
        "column_locations": col_locs,
        "bolt_specification": bolt_spec,
        "bolt_pattern": bolt_pat,
        "base_plate": base_plate,
        "grout_pad": {
            "thickness_mm": _to_float(
                field_map.get("F-193") or field_map.get("F-087"), 25
            )
        },
        "template_population_map": template_map,
        "traceability_matrix": traceability,
        "field_summary": {
            "total_ab_required": len(ab_codes),
            "resolved_count": len(present_ab),
            "missing_count": len(missing_ab),
            "missing_codes": missing_ab,
        },
    }

    # 3. Write JSON outputs
    write_json_output(project_id, "ab", "ab_structured_package.json", ab_package)
    # Legacy file the orchestrator gate expects
    write_json_output(project_id, "ab", "anchor_bolt_layout.json", {
        "project_id": str(project_id),
        "output_type": "AB",
        "anchor_bolt_fields": {
            fc: field_map.get(fc)
            for fc in sorted(ab_codes)
            if fc in field_map
        },
        "source_field_count": len(field_map),
        "status": "generated",
    })
    # Processed/ copy for audit trail
    write_processed_json(project_id, "ab_structured_package.json", ab_package)

    # 4. Generate DXF drawings
    cad_dir = project_output_dir(project_id, "ab")
    dxf_plan = cad_dir / "ab_plan_view.dxf"
    dxf_section = cad_dir / "ab_section_view.dxf"
    dxf_detail = cad_dir / "ab_detail_view.dxf"
    _write_plan_view_dxf(ab_package, dxf_plan)
    _write_section_view_dxf(ab_package, dxf_section)
    _write_detail_view_dxf(ab_package, dxf_detail)

    # 5. Generate PDF drawing
    pdf_path = cad_dir / "ab_drawing.pdf"
    _write_pdf_drawing(ab_package, pdf_path)

    # 6. Checkpoint
    gate_status = "PASS" if not missing_ab else "PASS_WITH_WARNINGS"
    _CHECKPOINT_MGR.record(
        db,
        project_id=project_id,
        stage_code="P2-03",
        label="AB Generation Gate",
        gate_status=gate_status,
        gate_data=ab_package["field_summary"],
    )

    result = {
        "project_id": str(project_id),
        "status": "GENERATED",
        "gate_status": gate_status,
        "outputs": {
            "ab_structured_package": str(cad_dir / "ab_structured_package.json"),
            "dxf_plan": str(dxf_plan),
            "dxf_section": str(dxf_section),
            "dxf_detail": str(dxf_detail),
            "pdf": str(pdf_path),
        },
        "field_summary": ab_package["field_summary"],
        "overall": "PASS",
    }
    update_stage_result(db, project_id=project_id, stage_code="P2-03",
                        status=StageStatus.PASSED, result=result)
    log_audit_event(db, "STAGE_PASSED", project_id=project_id, stage_code="P2-03",
                    detail={"field_summary": ab_package["field_summary"],
                            "gate_status": gate_status})
    logger.info("P2-03 AB generation complete: resolved=%d missing=%d gate=%s",
                len(present_ab), len(missing_ab), gate_status)
    return result


# ---------------------------------------------------------------------------
# Data extraction helpers
# ---------------------------------------------------------------------------

def _build_grid_references(fm: dict[str, str]) -> dict:
    labels_x = _split_labels(fm.get("F-041"), default=["A", "B"])
    labels_y = _split_labels(fm.get("F-042"), default=["1", "2"])
    spacing_x = _to_float(fm.get("F-039"), 6000.0)
    spacing_y = _to_float(fm.get("F-040"), 6000.0)
    origin_x = _to_float(fm.get("F-043"), 0.0)
    origin_y = _to_float(fm.get("F-044"), 0.0)
    bay_dim = _to_float(fm.get("F-172"), spacing_x)

    return {
        "grid_lines_x": labels_x,
        "grid_lines_y": labels_y,
        "grid_spacing_x_mm": spacing_x,
        "grid_spacing_y_mm": spacing_y,
        "grid_origin_x_mm": origin_x,
        "grid_origin_y_mm": origin_y,
        "total_span_x_mm": spacing_x * max(len(labels_x) - 1, 1),
        "total_span_y_mm": spacing_y * max(len(labels_y) - 1, 1),
        "bay_dimension_mm": bay_dim,
    }


def _build_column_locations(grid: dict) -> list[dict]:
    labels_x = grid["grid_lines_x"]
    labels_y = grid["grid_lines_y"]
    sx = grid["grid_spacing_x_mm"]
    sy = grid["grid_spacing_y_mm"]
    ox = grid["grid_origin_x_mm"]
    oy = grid["grid_origin_y_mm"]
    nx, ny = len(labels_x), len(labels_y)

    locations = []
    for i, lx in enumerate(labels_x):
        for j, ly in enumerate(labels_y):
            is_corner = (i in (0, nx - 1)) and (j in (0, ny - 1))
            is_edge = not is_corner and (i in (0, nx - 1) or j in (0, ny - 1))
            locations.append({
                "grid_ref": f"{lx}{ly}",
                "x_mm": ox + i * sx,
                "y_mm": oy + j * sy,
                "column_type": "CORNER" if is_corner else ("EDGE" if is_edge else "INTERNAL"),
            })
    return locations


def _build_bolt_specification(fm: dict[str, str]) -> dict:
    diam = fm.get("F-081", "M20")
    grade = fm.get("F-082", "8.8")
    embedment = _to_float(fm.get("F-086"), 450.0)
    projection = _to_float(fm.get("F-087") or fm.get("F-192"), 75.0)
    return {
        "diameter": diam,
        "diameter_mm": _parse_bolt_mm(diam),
        "grade": grade,
        "standard": "AS 1252 / ISO 4016",
        "anchor_code": fm.get("F-089", ""),
        "embedment_depth_mm": embedment,
        "projection_mm": projection,
        "total_length_mm": embedment + projection,
        "connection_type": fm.get("F-075", "Bolted"),
        "base_axis_orientation": fm.get("F-194", "StrongAxisParallelX"),
    }


def _build_bolt_pattern(fm: dict[str, str]) -> dict:
    qty = int(_to_float(fm.get("F-083") or fm.get("F-078"), 4))
    sx = _to_float(fm.get("F-084"), 85.0)
    sy = _to_float(fm.get("F-085"), 85.0)
    orient = fm.get("F-088", "Symmetric")
    return {
        "bolts_per_column": qty,
        "spacing_x_mm": sx,
        "spacing_y_mm": sy,
        "pattern_orientation": orient,
        "pattern_type": "SQUARE" if orient != "Circular" else "CIRCULAR",
    }


def _build_base_plate(fm: dict[str, str]) -> dict:
    size_str = fm.get("F-080", "")
    thick = _to_float(fm.get("F-090"), 20.0)
    w, d = _parse_plate_size(size_str)
    return {
        "size_string": size_str or f"{w}×{d}",
        "width_mm": w,
        "depth_mm": d,
        "thickness_mm": thick,
        "hole_diameter_mm": _nearest_hole(fm.get("F-081", "M20")),
        "material": "Grade 250 / S275",
    }


def _build_template_population_map(
    fm: dict[str, str], resolved_map: dict
) -> dict:
    all_bolt_fc = {**_GRID_FIELDS, **_BOLT_FIELDS, **_PLATE_FIELDS, **_CONN_FIELDS}
    mappings: dict[str, dict] = {}
    for fc, (name, unit) in all_bolt_fc.items():
        if fc in fm:
            cr = resolved_map.get(fc)
            mappings[fc] = {
                "template_variable": name,
                "value": fm[fc],
                "unit": unit or "",
                "source": cr.winning_source if cr else "UNKNOWN",
                "confidence": getattr(cr, "confidence", None),
            }
    return {
        "template_family": "AB_STANDARD_AU",
        "revision": "Rev01",
        "populated_count": len(mappings),
        "field_mappings": mappings,
    }


def _build_traceability_matrix(
    db: Session,
    project_id: UUID,
    ab_codes: set[str],
    resolved_map: dict,
) -> list[dict]:
    rows = (
        db.query(ExtractedFieldValue)
        .filter(ExtractedFieldValue.project_id == project_id)
        .filter(ExtractedFieldValue.field_code.in_(ab_codes))
        .order_by(ExtractedFieldValue.field_code,
                  ExtractedFieldValue.confidence.desc())
        .all()
    )
    seen: set[str] = set()
    matrix: list[dict] = []
    for r in rows:
        if r.field_code in seen:
            continue
        seen.add(r.field_code)
        cr = resolved_map.get(r.field_code)
        matrix.append({
            "field_code": r.field_code,
            "field_name": r.field_name or "",
            "raw_value": r.raw_value,
            "normalized_value": r.normalized_value,
            "unit": r.unit or "",
            "source_file": r.source_path or "",
            "winning_source": cr.winning_source if cr else "",
            "resolution_strategy": cr.resolution_strategy if cr else "SINGLE_SOURCE",
            "conflict_detected": cr.conflict_detected if cr else False,
            "extraction_confidence": r.confidence,
            "extracted_at": r.created_at.isoformat() if r.created_at else "",
        })
    # Add entries for fields not in extracted values but in resolved_map
    for fc, cr in resolved_map.items():
        if fc in ab_codes and fc not in seen:
            matrix.append({
                "field_code": fc,
                "field_name": "",
                "raw_value": None,
                "normalized_value": cr.winning_value,
                "unit": "",
                "source_file": "",
                "winning_source": cr.winning_source,
                "resolution_strategy": cr.resolution_strategy,
                "conflict_detected": cr.conflict_detected,
                "extraction_confidence": None,
                "extracted_at": "",
            })
    return sorted(matrix, key=lambda x: x["field_code"])


# ---------------------------------------------------------------------------
# DXF: Plan View
# ---------------------------------------------------------------------------

def _write_plan_view_dxf(pkg: dict, path: Path) -> None:
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 6
    _ensure_layers(doc, ["GRID", "CENTRE", "BASE_PLATE", "BOLTS", "DIM", "TEXT", "BORDER"])
    _add_linetype(doc, "DASHED2")
    msp = doc.modelspace()

    grid = pkg["grid_references"]
    cols = pkg["column_locations"]
    bolt_pat = pkg["bolt_pattern"]
    base_plate = pkg["base_plate"]

    sx = grid["grid_spacing_x_mm"]
    sy = grid["grid_spacing_y_mm"]
    lx = grid["grid_lines_x"]
    ly = grid["grid_lines_y"]
    total_x = sx * max(len(lx) - 1, 1)
    total_y = sy * max(len(ly) - 1, 1)
    ext = 800.0

    # Grid lines
    for i, label in enumerate(lx):
        x = i * sx
        msp.add_line((x, -ext), (x, total_y + ext),
                     dxfattribs={"layer": "GRID"})
        msp.add_text(label, dxfattribs={"height": 200, "layer": "TEXT",
                                         "insert": (x - 100, -ext - 300)})
        msp.add_text(label, dxfattribs={"height": 200, "layer": "TEXT",
                                         "insert": (x - 100, total_y + ext + 100)})

    for j, label in enumerate(ly):
        y = j * sy
        msp.add_line((-ext, y), (total_x + ext, y),
                     dxfattribs={"layer": "GRID"})
        msp.add_text(label, dxfattribs={"height": 200, "layer": "TEXT",
                                         "insert": (-ext - 400, y - 100)})
        msp.add_text(label, dxfattribs={"height": 200, "layer": "TEXT",
                                         "insert": (total_x + ext + 100, y - 100)})

    # Bay spacing dimensions
    for i in range(len(lx) - 1):
        x1, x2 = i * sx, (i + 1) * sx
        dy = -ext - 600
        msp.add_line((x1, dy), (x2, dy), dxfattribs={"layer": "DIM"})
        msp.add_line((x1, dy - 100), (x1, dy + 100), dxfattribs={"layer": "DIM"})
        msp.add_line((x2, dy - 100), (x2, dy + 100), dxfattribs={"layer": "DIM"})
        msp.add_text(f"{sx:.0f}", dxfattribs={"height": 150, "layer": "DIM",
                                               "insert": ((x1 + x2) / 2 - 100, dy - 250)})

    for j in range(len(ly) - 1):
        y1, y2 = j * sy, (j + 1) * sy
        dx = total_x + ext + 600
        msp.add_line((dx, y1), (dx, y2), dxfattribs={"layer": "DIM"})
        msp.add_line((dx - 100, y1), (dx + 100, y1), dxfattribs={"layer": "DIM"})
        msp.add_line((dx - 100, y2), (dx + 100, y2), dxfattribs={"layer": "DIM"})
        msp.add_text(f"{sy:.0f}", dxfattribs={"height": 150, "layer": "DIM",
                                               "insert": (dx + 50, (y1 + y2) / 2 - 75)})

    # Columns: base plate + bolt pattern
    bp_w = base_plate["width_mm"]
    bp_d = base_plate["depth_mm"]
    bolt_sx = bolt_pat["spacing_x_mm"]
    bolt_sy = bolt_pat["spacing_y_mm"]
    bolt_count = bolt_pat["bolts_per_column"]
    hole_r = base_plate["hole_diameter_mm"] / 2

    for col in cols:
        cx, cy = col["x_mm"], col["y_mm"]
        # Base plate outline
        msp.add_lwpolyline([
            (cx - bp_w / 2, cy - bp_d / 2),
            (cx + bp_w / 2, cy - bp_d / 2),
            (cx + bp_w / 2, cy + bp_d / 2),
            (cx - bp_w / 2, cy + bp_d / 2),
        ], dxfattribs={"layer": "BASE_PLATE", "closed": True})
        # Centreline crosshair
        msp.add_line((cx - 400, cy), (cx + 400, cy),
                     dxfattribs={"layer": "CENTRE"})
        msp.add_line((cx, cy - 400), (cx, cy + 400),
                     dxfattribs={"layer": "CENTRE"})
        # Grid ref label
        msp.add_text(col["grid_ref"], dxfattribs={
            "height": 120, "layer": "TEXT",
            "insert": (cx + bp_w / 2 + 60, cy + bp_d / 2 + 60)
        })
        # Bolt positions
        offsets = [
            (-bolt_sx / 2, -bolt_sy / 2),
            ( bolt_sx / 2, -bolt_sy / 2),
            ( bolt_sx / 2,  bolt_sy / 2),
            (-bolt_sx / 2,  bolt_sy / 2),
        ]
        for bx, by in offsets[:bolt_count]:
            msp.add_circle((cx + bx, cy + by), hole_r,
                           dxfattribs={"layer": "BOLTS"})

    # Title block
    _dxf_title_block(msp, "ANCHOR BOLT — PLAN VIEW",
                     str(pkg["project_id"]),
                     f"Scale 1:100   Sheet size A1",
                     total_x, total_y)
    doc.saveas(path)
    logger.info("Plan DXF: %s", path)


# ---------------------------------------------------------------------------
# DXF: Section View
# ---------------------------------------------------------------------------

def _write_section_view_dxf(pkg: dict, path: Path) -> None:
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 6
    _ensure_layers(doc, ["CONCRETE", "BOLT", "BASE_PLATE", "GROUT", "COLUMN", "DIM", "TEXT"])
    msp = doc.modelspace()

    b = pkg["bolt_specification"]
    bp = pkg["base_plate"]
    grout = pkg["grout_pad"]["thickness_mm"]
    bolt_diam_mm = b["diameter_mm"]
    embedment = b["embedment_depth_mm"]
    projection = b["projection_mm"]
    total_len = b["total_length_mm"]
    bp_w = bp["width_mm"]
    bp_thick = bp["thickness_mm"]

    # Layout origin at top of concrete = y=0
    conc_w = bp_w * 3
    conc_h = embedment + 200

    # Concrete block
    msp.add_lwpolyline([
        (-conc_w / 2, -conc_h),
        ( conc_w / 2, -conc_h),
        ( conc_w / 2, 0),
        (-conc_w / 2, 0),
    ], dxfattribs={"layer": "CONCRETE", "closed": True})
    # Hatch lines (diagonal) in concrete
    for i in range(0, int(conc_h), 200):
        y = -i
        msp.add_line((-conc_w / 2, y - 100), (-conc_w / 2 + 200, y),
                     dxfattribs={"layer": "CONCRETE"})

    # Grout pad (between concrete surface y=0 and base plate y=grout)
    msp.add_lwpolyline([
        (-bp_w / 2, 0),
        ( bp_w / 2, 0),
        ( bp_w / 2, grout),
        (-bp_w / 2, grout),
    ], dxfattribs={"layer": "GROUT", "closed": True})
    msp.add_text("GROUT PAD", dxfattribs={
        "height": 60, "layer": "TEXT",
        "insert": (-bp_w / 2 - 200, grout / 2 - 30)
    })

    # Base plate
    y_bp_bot = grout
    y_bp_top = grout + bp_thick
    msp.add_lwpolyline([
        (-bp_w / 2, y_bp_bot),
        ( bp_w / 2, y_bp_bot),
        ( bp_w / 2, y_bp_top),
        (-bp_w / 2, y_bp_top),
    ], dxfattribs={"layer": "BASE_PLATE", "closed": True})

    # Column stub above base plate (100mm tall)
    col_w = bolt_diam_mm * 6
    msp.add_lwpolyline([
        (-col_w / 2, y_bp_top),
        ( col_w / 2, y_bp_top),
        ( col_w / 2, y_bp_top + 600),
        (-col_w / 2, y_bp_top + 600),
    ], dxfattribs={"layer": "COLUMN", "closed": True})

    # Anchor bolt (2 bolts shown in section)
    bolt_r = bolt_diam_mm / 2
    hole_offset = pkg["bolt_pattern"]["spacing_x_mm"] / 2
    for sign in (-1, 1):
        bx = sign * hole_offset
        # Embedded portion (below concrete surface, y=0 downward)
        msp.add_line((bx - bolt_r, 0), (bx - bolt_r, -embedment), dxfattribs={"layer": "BOLT"})
        msp.add_line((bx + bolt_r, 0), (bx + bolt_r, -embedment), dxfattribs={"layer": "BOLT"})
        # Bottom hook
        msp.add_line((bx - bolt_r, -embedment), (bx + bolt_r * 3, -embedment),
                     dxfattribs={"layer": "BOLT"})
        # Projection above base plate
        y_proj_top = y_bp_top + projection
        msp.add_line((bx - bolt_r, y_bp_top), (bx - bolt_r, y_proj_top),
                     dxfattribs={"layer": "BOLT"})
        msp.add_line((bx + bolt_r, y_bp_top), (bx + bolt_r, y_proj_top),
                     dxfattribs={"layer": "BOLT"})
        # Nut at top
        nut_s = bolt_r * 2.5
        msp.add_lwpolyline([
            (bx - nut_s, y_proj_top),
            (bx + nut_s, y_proj_top),
            (bx + nut_s, y_proj_top + bolt_diam_mm),
            (bx - nut_s, y_proj_top + bolt_diam_mm),
        ], dxfattribs={"layer": "BOLT", "closed": True})

    # Dimension: embedment depth
    dx = conc_w / 2 + 200
    msp.add_line((dx, 0), (dx, -embedment), dxfattribs={"layer": "DIM"})
    msp.add_line((dx - 100, 0), (dx + 100, 0), dxfattribs={"layer": "DIM"})
    msp.add_line((dx - 100, -embedment), (dx + 100, -embedment), dxfattribs={"layer": "DIM"})
    msp.add_text(f"EMBD.={embedment:.0f}", dxfattribs={
        "height": 80, "layer": "DIM", "insert": (dx + 50, -embedment / 2 - 40)
    })

    # Dimension: projection
    dx2 = conc_w / 2 + 400
    msp.add_line((dx2, y_bp_top), (dx2, y_bp_top + projection), dxfattribs={"layer": "DIM"})
    msp.add_line((dx2 - 100, y_bp_top), (dx2 + 100, y_bp_top), dxfattribs={"layer": "DIM"})
    msp.add_line((dx2 - 100, y_bp_top + projection),
                 (dx2 + 100, y_bp_top + projection), dxfattribs={"layer": "DIM"})
    msp.add_text(f"PROJ.={projection:.0f}", dxfattribs={
        "height": 80, "layer": "DIM",
        "insert": (dx2 + 50, y_bp_top + projection / 2 - 40)
    })

    # Bolt specification text
    spec_lines = [
        f"BOLT: {b['diameter']} GRADE {b['grade']}",
        f"CODE: {b['anchor_code'] or '-'}",
        f"TOTAL L={total_len:.0f}mm",
        f"GROUT={grout:.0f}mm",
    ]
    y_text = y_bp_top + projection + 200
    for i, line in enumerate(spec_lines):
        msp.add_text(line, dxfattribs={"height": 80, "layer": "TEXT",
                                        "insert": (-conc_w / 2, y_text + i * 120)})

    _dxf_title_block(msp, "ANCHOR BOLT — SECTION VIEW",
                     str(pkg["project_id"]),
                     "Scale 1:20   Sheet size A2",
                     conc_w, conc_h)
    doc.saveas(path)
    logger.info("Section DXF: %s", path)


# ---------------------------------------------------------------------------
# DXF: Detail View
# ---------------------------------------------------------------------------

def _write_detail_view_dxf(pkg: dict, path: Path) -> None:
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 6
    _ensure_layers(doc, ["BOLT", "NUT", "WASHER", "DIM", "TEXT", "LEADER"])
    msp = doc.modelspace()

    b = pkg["bolt_specification"]
    bolt_diam_mm = b["diameter_mm"]
    projection = b["projection_mm"]
    br = bolt_diam_mm / 2

    # Draw single bolt in detail at 2:1
    scale = 2.0
    # Bolt shank
    shank_h = projection * scale
    msp.add_lwpolyline([
        (-br * scale, 0), (br * scale, 0),
        (br * scale, shank_h), (-br * scale, shank_h),
    ], dxfattribs={"layer": "BOLT", "closed": True})

    # Thread representation (zigzag lines on shank)
    pitch = bolt_diam_mm * 1.5 * scale
    y = 0.0
    while y < shank_h:
        msp.add_line((-br * scale, y), (br * scale, y + pitch / 2),
                     dxfattribs={"layer": "BOLT"})
        msp.add_line((br * scale, y + pitch / 2), (-br * scale, y + pitch),
                     dxfattribs={"layer": "BOLT"})
        y += pitch

    # Washer
    washer_or = br * 2.5 * scale
    washer_ir = br * scale + 1
    washer_h = bolt_diam_mm * 0.3 * scale
    msp.add_lwpolyline([
        (-washer_or, shank_h), (washer_or, shank_h),
        (washer_or, shank_h + washer_h), (-washer_or, shank_h + washer_h),
    ], dxfattribs={"layer": "WASHER", "closed": True})
    # Hole in washer
    msp.add_line((-washer_ir, shank_h), (-washer_ir, shank_h + washer_h),
                 dxfattribs={"layer": "WASHER"})
    msp.add_line((washer_ir, shank_h), (washer_ir, shank_h + washer_h),
                 dxfattribs={"layer": "WASHER"})

    # Nut (hexagonal representation as rectangle in section)
    nut_w = br * 2.2 * scale
    nut_h = bolt_diam_mm * 0.8 * scale
    y_nut = shank_h + washer_h
    msp.add_lwpolyline([
        (-nut_w, y_nut), (nut_w, y_nut),
        (nut_w, y_nut + nut_h), (-nut_w, y_nut + nut_h),
    ], dxfattribs={"layer": "NUT", "closed": True})

    total_h = y_nut + nut_h

    # Leaders + callouts
    cx_right = br * scale + 200
    callouts = [
        (shank_h / 2, f"{b['diameter']} GRADE {b['grade']}"),
        (shank_h + washer_h / 2, "WASHER PLATE"),
        (y_nut + nut_h / 2, "HEX NUT"),
        (0, f"EMBD={b['embedment_depth_mm']:.0f}mm"),
    ]
    for y_c, text in callouts:
        msp.add_line((br * scale, y_c), (cx_right + 50, y_c), dxfattribs={"layer": "LEADER"})
        msp.add_text(text, dxfattribs={"height": 60 * scale, "layer": "TEXT",
                                        "insert": (cx_right + 80, y_c - 30 * scale)})

    # Diameter dimension
    dx = -br * scale - 200
    msp.add_line((dx, shank_h * 0.3), (dx, shank_h * 0.7), dxfattribs={"layer": "DIM"})
    msp.add_line((dx, shank_h * 0.5), (-br * scale, shank_h * 0.5), dxfattribs={"layer": "DIM"})
    msp.add_line((dx, shank_h * 0.5), (br * scale, shank_h * 0.5), dxfattribs={"layer": "DIM"})
    msp.add_text(f"⌀{bolt_diam_mm:.0f}", dxfattribs={
        "height": 70 * scale, "layer": "DIM",
        "insert": (dx - 300, shank_h * 0.5 + 30)
    })

    _dxf_title_block(msp, "ANCHOR BOLT — DETAIL VIEW",
                     str(pkg["project_id"]),
                     "Scale 2:1   Sheet size A3",
                     washer_or * 2, total_h)
    doc.saveas(path)
    logger.info("Detail DXF: %s", path)


# ---------------------------------------------------------------------------
# PDF drawing using fitz (PyMuPDF) — multi-page A2 landscape
# ---------------------------------------------------------------------------

def _write_pdf_drawing(pkg: dict, path: Path) -> None:
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.warning("fitz not available — skipping PDF generation")
        return

    # A2 landscape in points (594mm × 420mm → 1684 × 1191 pt at 2.835pt/mm)
    PT = 2.835  # points per mm
    W = 841 * PT   # A1 landscape width  ≈ 2384 pt
    H = 594 * PT   # A1 landscape height ≈ 1684 pt

    doc = fitz.open()

    # ---------- PAGE 1: Plan View + Data Table ----------
    page = doc.new_page(width=W, height=H)
    _pdf_border(page, W, H)
    _pdf_title_block(page, W, H, pkg,
                     "ANCHOR BOLT — PLAN VIEW",
                     "Scale 1:100  |  Sheet 1 of 2")
    _pdf_draw_plan(page, pkg, W, H)

    # ---------- PAGE 2: Section + Detail + Traceability ----------
    page2 = doc.new_page(width=W, height=H)
    _pdf_border(page2, W, H)
    _pdf_title_block(page2, W, H, pkg,
                     "ANCHOR BOLT — SECTION & DETAIL",
                     "Scale 1:20 / 2:1  |  Sheet 2 of 2")
    _pdf_draw_section(page2, pkg, W, H)
    _pdf_draw_data_table(page2, pkg, W, H)

    doc.save(str(path))
    doc.close()
    logger.info("AB PDF written: %s", path)


def _pdf_border(page, W: float, H: float) -> None:
    import fitz
    page.draw_rect(fitz.Rect(20, 20, W - 20, H - 20), color=(0, 0, 0), width=1.5)


def _pdf_title_block(page, W: float, H: float, pkg: dict,
                     title: str, subtitle: str) -> None:
    import fitz
    tb_h = 60.0
    tb_y = H - tb_h - 20
    page.draw_rect(fitz.Rect(20, tb_y, W - 20, H - 20),
                   color=(0, 0, 0), width=1)
    page.draw_line(fitz.Point(20, tb_y), fitz.Point(W - 20, tb_y),
                   color=(0, 0, 0), width=1)
    page.insert_text(fitz.Point(30, tb_y + 18), title,
                     fontsize=14, fontname="helv", color=(0, 0, 0))
    page.insert_text(fitz.Point(30, tb_y + 36), subtitle,
                     fontsize=9, fontname="helv", color=(0.3, 0.3, 0.3))
    page.insert_text(fitz.Point(30, tb_y + 50),
                     f"Project: {pkg['project_id']}  |  "
                     f"Generated: {pkg['generated_at'][:19]}  |  "
                     "Infiniti Steel Detailing Automation",
                     fontsize=7, fontname="helv", color=(0.4, 0.4, 0.4))


def _pdf_draw_plan(page, pkg: dict, W: float, H: float) -> None:
    import fitz
    grid = pkg["grid_references"]
    cols = pkg["column_locations"]
    bolt_pat = pkg["bolt_pattern"]
    base_plate = pkg["base_plate"]
    bolt_spec = pkg["bolt_specification"]

    # Drawing area (leave title block space)
    draw_x0, draw_y0 = 40.0, 40.0
    draw_w = W - 80
    draw_h = H - 150

    sx_mm = grid["grid_spacing_x_mm"]
    sy_mm = grid["grid_spacing_y_mm"]
    lx = grid["grid_lines_x"]
    ly = grid["grid_lines_y"]
    total_x_mm = sx_mm * max(len(lx) - 1, 1)
    total_y_mm = sy_mm * max(len(ly) - 1, 1)

    # Scale to fit drawing area
    scale = min(draw_w / max(total_x_mm, 1) * 0.75,
                draw_h / max(total_y_mm, 1) * 0.75)
    off_x = draw_x0 + (draw_w - total_x_mm * scale) / 2
    off_y = draw_y0 + draw_h * 0.1

    def mm2pt(x_mm: float, y_mm: float):
        return (off_x + x_mm * scale, off_y + y_mm * scale)

    # Grid lines
    for i, label in enumerate(lx):
        x_mm = i * sx_mm
        p1 = mm2pt(x_mm, -sy_mm * 0.1)
        p2 = mm2pt(x_mm, total_y_mm + sy_mm * 0.1)
        page.draw_line(fitz.Point(*p1), fitz.Point(*p2),
                       color=(0.6, 0.6, 0.6), width=0.5, dashes="[4 2]")
        page.insert_text(fitz.Point(p2[0] - 5, p2[1] + 12),
                         label, fontsize=8, color=(0, 0, 0.6))

    for j, label in enumerate(ly):
        y_mm = j * sy_mm
        p1 = mm2pt(-sx_mm * 0.1, y_mm)
        p2 = mm2pt(total_x_mm + sx_mm * 0.1, y_mm)
        page.draw_line(fitz.Point(*p1), fitz.Point(*p2),
                       color=(0.6, 0.6, 0.6), width=0.5, dashes="[4 2]")
        page.insert_text(fitz.Point(p1[0] - 14, p1[1] + 3),
                         label, fontsize=8, color=(0, 0, 0.6))

    # Base plate + bolts
    bp_w = base_plate["width_mm"] * scale
    bp_d = base_plate["depth_mm"] * scale
    bolt_sx = bolt_pat["spacing_x_mm"] * scale
    bolt_sy = bolt_pat["spacing_y_mm"] * scale
    bolt_count = bolt_pat["bolts_per_column"]
    hole_r = base_plate["hole_diameter_mm"] * scale / 2

    for col in cols:
        cx, cy = mm2pt(col["x_mm"], col["y_mm"])
        # Base plate
        page.draw_rect(
            fitz.Rect(cx - bp_w / 2, cy - bp_d / 2,
                      cx + bp_w / 2, cy + bp_d / 2),
            color=(0, 0, 0), fill=(0.9, 0.9, 0.9), width=0.8
        )
        # Bolts
        offsets = [
            (-bolt_sx / 2, -bolt_sy / 2),
            ( bolt_sx / 2, -bolt_sy / 2),
            ( bolt_sx / 2,  bolt_sy / 2),
            (-bolt_sx / 2,  bolt_sy / 2),
        ]
        for bx, by in offsets[:bolt_count]:
            page.draw_circle(fitz.Point(cx + bx, cy + by), hole_r,
                             color=(0, 0, 0), fill=(1, 1, 1), width=0.8)
        # Grid ref
        page.insert_text(fitz.Point(cx + bp_w / 2 + 3, cy - 4),
                         col["grid_ref"], fontsize=6, color=(0.2, 0.2, 0.2))

    # Legend
    lx0, ly0 = 40.0, H - 100
    page.draw_rect(fitz.Rect(lx0, ly0, lx0 + 14, ly0 + 10),
                   color=(0, 0, 0), fill=(0.9, 0.9, 0.9), width=0.6)
    page.insert_text(fitz.Point(lx0 + 18, ly0 + 8), "Base Plate", fontsize=7)
    page.draw_circle(fitz.Point(lx0 + 7, ly0 + 25), 4,
                     color=(0, 0, 0), fill=(1, 1, 1), width=0.6)
    page.insert_text(fitz.Point(lx0 + 18, ly0 + 28), "Anchor Bolt", fontsize=7)


def _pdf_draw_section(page, pkg: dict, W: float, H: float) -> None:
    import fitz
    b = pkg["bolt_specification"]
    bp = pkg["base_plate"]
    grout = pkg["grout_pad"]["thickness_mm"]
    bolt_diam_mm = b["diameter_mm"]
    embedment = b["embedment_depth_mm"]
    projection = b["projection_mm"]
    bp_w = bp["width_mm"]
    bp_thick = bp["thickness_mm"]
    # Drawing area — left half
    ax0, ay0 = 40.0, 50.0
    aW = W / 2 - 60

    # Scale to fit
    total_h_mm = embedment + grout + bp_thick + projection + 200
    scale = min(aW / (bp_w * 2.5), (H - 200) / total_h_mm * 0.5)

    ox = ax0 + aW / 2
    oy = ay0 + 50 + embedment * scale  # concrete surface y

    def pt(x_mm, y_mm):
        return fitz.Point(ox + x_mm * scale, oy - y_mm * scale)

    conc_w_mm = bp_w * 2.5
    # Concrete
    page.draw_rect(
        fitz.Rect(ox - conc_w_mm * scale / 2, oy,
                  ox + conc_w_mm * scale / 2, oy + embedment * scale),
        color=(0.3, 0.3, 0.3), fill=(0.85, 0.85, 0.85), width=1
    )
    page.insert_text(fitz.Point(ox - 30, oy + embedment * scale / 2),
                     "CONCRETE", fontsize=7, color=(0.3, 0.3, 0.3))

    # Grout
    page.draw_rect(
        fitz.Rect(ox - bp_w * scale / 2, oy - grout * scale,
                  ox + bp_w * scale / 2, oy),
        color=(0.5, 0.4, 0.2), fill=(0.95, 0.9, 0.75), width=0.8
    )
    page.insert_text(fitz.Point(ox + bp_w * scale / 2 + 4, oy - grout * scale / 2),
                     f"GROUT {grout:.0f}", fontsize=6, color=(0.5, 0.3, 0))

    # Base plate
    y_bp = grout + bp_thick
    page.draw_rect(
        fitz.Rect(ox - bp_w * scale / 2, oy - y_bp * scale,
                  ox + bp_w * scale / 2, oy - grout * scale),
        color=(0, 0, 0), fill=(0.7, 0.7, 0.8), width=1
    )
    page.insert_text(fitz.Point(ox + bp_w * scale / 2 + 4, oy - y_bp * scale + 4),
                     f"BP {bp_w:.0f}×{bp['depth_mm']:.0f}×{bp_thick:.0f}T",
                     fontsize=6, color=(0, 0, 0.6))

    # Bolts (2 shown in section)
    br = bolt_diam_mm * scale / 2
    hole_offset = pkg["bolt_pattern"]["spacing_x_mm"] * scale / 2
    for sign in (-1, 1):
        bx = sign * hole_offset
        # Embedded portion
        page.draw_rect(
            fitz.Rect(ox + bx - br, oy, ox + bx + br, oy + embedment * scale),
            color=(0.2, 0.2, 0.2), fill=(0.4, 0.4, 0.4), width=0.5
        )
        # Projection
        y_proj_top = oy - y_bp * scale - projection * scale
        page.draw_rect(
            fitz.Rect(ox + bx - br, y_proj_top,
                      ox + bx + br, oy - y_bp * scale),
            color=(0.2, 0.2, 0.2), fill=(0.4, 0.4, 0.4), width=0.5
        )

    # Dimension annotations
    dim_x = ox + conc_w_mm * scale / 2 + 20
    # Embedment
    page.draw_line(fitz.Point(dim_x, oy), fitz.Point(dim_x, oy + embedment * scale),
                   color=(0.8, 0, 0), width=0.6)
    page.insert_text(fitz.Point(dim_x + 4, oy + embedment * scale / 2),
                     f"EMBD\n{embedment:.0f}", fontsize=7, color=(0.8, 0, 0))
    # Projection
    page.draw_line(
        fitz.Point(dim_x + 30, oy - y_bp * scale),
        fitz.Point(dim_x + 30, oy - y_bp * scale - projection * scale),
        color=(0, 0.5, 0), width=0.6
    )
    page.insert_text(
        fitz.Point(dim_x + 34, oy - y_bp * scale - projection * scale / 2),
        f"PROJ\n{projection:.0f}", fontsize=7, color=(0, 0.5, 0)
    )

    page.insert_text(
        fitz.Point(ax0, ay0 + 10),
        f"BOLT: {b['diameter']} GRADE {b['grade']}  |  "
        f"CODE: {b['anchor_code'] or '-'}  |  "
        f"TOTAL L = {b['total_length_mm']:.0f}mm",
        fontsize=8, color=(0, 0, 0)
    )


def _pdf_draw_data_table(page, pkg: dict, W: float, _H: float) -> None:
    import fitz
    b = pkg["bolt_specification"]
    bp = pkg["base_plate"]
    pat = pkg["bolt_pattern"]
    grid = pkg["grid_references"]
    fs = pkg["field_summary"]

    rows = [
        ("Bolt Diameter", b["diameter"]),
        ("Bolt Grade", b["grade"]),
        ("Bolt Standard", b["standard"]),
        ("Embedment Depth", f"{b['embedment_depth_mm']:.0f} mm"),
        ("Projection", f"{b['projection_mm']:.0f} mm"),
        ("Total Bolt Length", f"{b['total_length_mm']:.0f} mm"),
        ("Bolts per Column", str(pat["bolts_per_column"])),
        ("Bolt Spacing X", f"{pat['spacing_x_mm']:.0f} mm"),
        ("Bolt Spacing Y", f"{pat['spacing_y_mm']:.0f} mm"),
        ("Pattern Type", pat["pattern_type"]),
        ("Base Plate", f"{bp['width_mm']:.0f}×{bp['depth_mm']:.0f}×{bp['thickness_mm']:.0f}T mm"),
        ("Grout Pad", f"{pkg['grout_pad']['thickness_mm']:.0f} mm"),
        ("Grid Spacing X", f"{grid['grid_spacing_x_mm']:.0f} mm"),
        ("Grid Spacing Y", f"{grid['grid_spacing_y_mm']:.0f} mm"),
        ("Fields Resolved", f"{fs['resolved_count']} / {fs['total_ab_required']}"),
    ]

    tx0 = W / 2 + 20
    ty0 = 50.0
    col1_w = 160.0
    col2_w = 140.0
    row_h = 16.0

    page.draw_rect(
        fitz.Rect(tx0, ty0, tx0 + col1_w + col2_w, ty0 + 18),
        color=(0, 0, 0.5), fill=(0.1, 0.2, 0.5), width=0
    )
    page.insert_text(fitz.Point(tx0 + 4, ty0 + 13),
                     "ANCHOR BOLT — DATA SUMMARY",
                     fontsize=9, fontname="helv-bold", color=(1, 1, 1))

    for i, (label, value) in enumerate(rows):
        y = ty0 + 18 + i * row_h
        fill = (0.96, 0.96, 0.98) if i % 2 == 0 else (1, 1, 1)
        page.draw_rect(fitz.Rect(tx0, y, tx0 + col1_w, y + row_h),
                       color=(0.8, 0.8, 0.8), fill=fill, width=0.3)
        page.draw_rect(fitz.Rect(tx0 + col1_w, y, tx0 + col1_w + col2_w, y + row_h),
                       color=(0.8, 0.8, 0.8), fill=fill, width=0.3)
        page.insert_text(fitz.Point(tx0 + 4, y + 11), label, fontsize=7, color=(0, 0, 0))
        page.insert_text(fitz.Point(tx0 + col1_w + 4, y + 11), value,
                         fontsize=7, color=(0, 0, 0.6))


# ---------------------------------------------------------------------------
# DXF shared helpers
# ---------------------------------------------------------------------------

def _ensure_layers(doc, layer_names: list[str]) -> None:
    for name in layer_names:
        if name not in doc.layers:
            doc.layers.new(name, dxfattribs={"color": 7})


def _add_linetype(doc, name: str) -> None:
    try:
        if name not in doc.linetypes:
            doc.linetypes.new(name, dxfattribs={"pattern": [0.0]})
    except Exception:
        pass


def _dxf_title_block(msp, title: str, project_id: str, scale_note: str,
                     content_w: float, content_h: float) -> None:
    margin = 500.0
    # Border
    msp.add_lwpolyline([
        (-margin, -content_h - margin),
        (content_w + margin, -content_h - margin),
        (content_w + margin, content_h + margin * 2),
        (-margin, content_h + margin * 2),
    ], dxfattribs={"closed": True})
    # Title
    msp.add_text(title, dxfattribs={"height": 180, "insert": (-margin + 50, content_h + margin + 100)})
    msp.add_text(f"Project: {project_id[:36]}", dxfattribs={"height": 100, "insert": (-margin + 50, content_h + margin - 50)})
    msp.add_text(scale_note, dxfattribs={"height": 100, "insert": (-margin + 50, content_h + margin - 170)})
    msp.add_text("Infiniti Steel Detailing Automation — Phase 2 — P2-03",
                 dxfattribs={"height": 80, "insert": (-margin + 50, content_h + margin - 280)})


# ---------------------------------------------------------------------------
# Numeric / parsing helpers
# ---------------------------------------------------------------------------

def _to_float(value, default: float) -> float:
    if not value:
        return default
    try:
        return float(str(value).replace("mm", "").replace("m", "").strip())
    except (ValueError, TypeError):
        return default


def _parse_bolt_mm(diam_str: str) -> float:
    """'M24' → 24.0, '24' → 24.0, '24mm' → 24.0"""
    s = str(diam_str).upper().replace("M", "").replace("MM", "").strip()
    try:
        return float(s)
    except ValueError:
        return 20.0


def _parse_plate_size(size_str: str) -> tuple[float, float]:
    """'250x250' or '250×250' or '250 x 250' → (250.0, 250.0)"""
    if not size_str:
        return 250.0, 250.0
    for sep in ("×", "x", "X", "*"):
        if sep in str(size_str):
            parts = str(size_str).split(sep)
            if len(parts) >= 2:
                try:
                    return float(parts[0].strip()), float(parts[1].strip())
                except ValueError:
                    pass
    return 250.0, 250.0


def _nearest_hole(diam_str: str) -> float:
    """Return standard hole diameter for given bolt (M-size + 4mm)."""
    bolt_mm = _parse_bolt_mm(diam_str)
    return bolt_mm + 4.0


def _split_labels(label_str: str | None, default: list[str]) -> list[str]:
    """Parse comma/semicolon-separated grid label string."""
    if not label_str:
        return default
    parts = [p.strip() for p in str(label_str).replace(";", ",").split(",")]
    return [p for p in parts if p] or default
