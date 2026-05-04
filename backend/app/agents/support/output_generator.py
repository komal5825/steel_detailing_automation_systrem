"""
Output Generator — Phase 2 Step 19.

Generates DXF drawings for AB (Anchor Bolt) and GA (General Arrangement)
using ezdxf, then optionally converts to DWG via ODA File Converter.

Also writes a plain-text summary report alongside the JSON output.

Output layout (per project):
  data/projects/{id}/outputs/cad/
    ab_layout.dxf
    ab_layout.dwg          (if ODA available)
    ga_layout.dxf
    ga_layout.dwg          (if ODA available)
    drawing_summary.txt
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from uuid import UUID

import ezdxf

from app.agents.phase2.output_utils import project_output_dir, write_json_output
from app.config.settings import settings
from app.db.crud.stages import update_stage_result
from app.db.crud.validation import log_audit_event
from app.db.models import StageStatus
from app.db.session import SessionLocal
from app.utils.audit_logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate_cad_outputs(project_id: str, db=None) -> dict:
    """
    Generate DXF (and optionally DWG) outputs for a project.
    Can be called standalone or from the orchestrator.
    """
    owns_session = db is None
    session = db or SessionLocal()
    try:
        result = _generate(UUID(str(project_id)), session)
        session.commit()
        return result
    finally:
        if owns_session:
            session.close()


class OutputGenerator:
    """Backwards-compatible class interface."""

    def generate_output(self, project_id: str, output_type: str = "ALL") -> dict:  # noqa: ARG002
        return generate_cad_outputs(project_id)


# ---------------------------------------------------------------------------
# Core implementation
# ---------------------------------------------------------------------------

def _generate(project_id: UUID, db) -> dict:
    log_audit_event(db, "STAGE_STARTED", project_id=project_id, stage_code="P2-19")
    update_stage_result(db, project_id=project_id, stage_code="P2-19",
                        status=StageStatus.RUNNING)

    cad_dir = project_output_dir(project_id, "cad")

    # Load AB and GA JSON payloads written by P2-03 / P2-04
    ab_payload = _load_json(project_output_dir(project_id, "ab") / "anchor_bolt_layout.json")
    ga_payload = _load_json(project_output_dir(project_id, "ga") / "general_arrangement.json")

    outputs: list[dict] = []

    # --- AB DXF ---
    if ab_payload:
        ab_dxf_path = cad_dir / "ab_layout.dxf"
        _write_ab_dxf(ab_payload, ab_dxf_path)
        ab_dwg = _oda_convert(ab_dxf_path, cad_dir)
        outputs.append({
            "type": "AB",
            "dxf": str(ab_dxf_path),
            "dwg": str(ab_dwg) if ab_dwg else None,
        })

    # --- GA DXF ---
    if ga_payload:
        ga_dxf_path = cad_dir / "ga_layout.dxf"
        _write_ga_dxf(ga_payload, ga_dxf_path)
        ga_dwg = _oda_convert(ga_dxf_path, cad_dir)
        outputs.append({
            "type": "GA",
            "dxf": str(ga_dxf_path),
            "dwg": str(ga_dwg) if ga_dwg else None,
        })

    # --- Text summary ---
    summary_path = cad_dir / "drawing_summary.txt"
    _write_summary(project_id, ab_payload, ga_payload, outputs, summary_path)

    result = {
        "project_id": str(project_id),
        "outputs": outputs,
        "cad_dir": str(cad_dir),
        "summary": str(summary_path),
        "overall": "PASS" if outputs else "FAIL",
    }
    write_json_output(project_id, "cad", "output_manifest.json", result)
    update_stage_result(db, project_id=project_id, stage_code="P2-19",
                        status=StageStatus.PASSED if result["overall"] == "PASS" else StageStatus.FAILED,
                        result=result)
    log_audit_event(db, "STAGE_PASSED" if result["overall"] == "PASS" else "STAGE_FAILED",
                    project_id=project_id, stage_code="P2-19",
                    detail={"outputs_count": len(outputs)})
    return result


# ---------------------------------------------------------------------------
# AB DXF drawing
# ---------------------------------------------------------------------------

def _write_ab_dxf(payload: dict, path: Path) -> None:
    """
    Generate a schematic Anchor Bolt layout DXF.

    Layout: title block + table of AB fields, basic bolt circle geometry
    if bolt diameter and projection are available.
    """
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 6   # millimetres
    msp = doc.modelspace()

    fields: dict = payload.get("anchor_bolt_fields", {})

    # Title block
    _add_title_block(msp, "ANCHOR BOLT LAYOUT", str(payload.get("project_id", "")))

    # Field table
    y = 230.0
    msp.add_text("ANCHOR BOLT FIELDS", dxfattribs={"height": 5, "insert": (10, y)})
    y -= 10
    for code, val in fields.items():
        if val and str(val).strip():
            msp.add_text(f"{code}: {val}", dxfattribs={"height": 3.5, "insert": (12, y)})
            y -= 7

    # Simple bolt circle if diameter is available
    diam_raw = fields.get("F-081") or fields.get("F-083")
    if diam_raw:
        try:
            diam = float(str(diam_raw).replace("mm", "").strip())
            cx, cy = 180.0, 150.0
            msp.add_circle((cx, cy), diam / 2, dxfattribs={"layer": "BOLTS"})
            msp.add_text(f"⌀{diam:.0f}", dxfattribs={"height": 4, "insert": (cx - 8, cy - diam / 2 - 8)})
            # Cross-hairs
            msp.add_line((cx - diam * 0.8, cy), (cx + diam * 0.8, cy), dxfattribs={"layer": "CENTRE"})
            msp.add_line((cx, cy - diam * 0.8), (cx, cy + diam * 0.8), dxfattribs={"layer": "CENTRE"})
        except (ValueError, TypeError):
            pass

    doc.saveas(path)
    logger.info("AB DXF written: %s", path)


# ---------------------------------------------------------------------------
# GA DXF drawing
# ---------------------------------------------------------------------------

def _write_ga_dxf(payload: dict, path: Path) -> None:
    """
    Generate a schematic General Arrangement DXF.

    Draws a simple frame outline using bay spacing / frame span if available.
    """
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 6
    msp = doc.modelspace()

    fields: dict = payload.get("general_arrangement_fields", {})

    _add_title_block(msp, "GENERAL ARRANGEMENT", str(payload.get("project_id", "")))

    # Field table
    y = 230.0
    msp.add_text("GA FIELDS", dxfattribs={"height": 5, "insert": (10, y)})
    y -= 10
    for code, val in fields.items():
        if val and str(val).strip():
            msp.add_text(f"{code}: {val}", dxfattribs={"height": 3.5, "insert": (12, y)})
            y -= 7

    # Simple frame outline using span & height if available
    span_raw = fields.get("F-040") or fields.get("F-039")
    height_raw = fields.get("F-042") or fields.get("F-041")

    span = _to_float(span_raw, 20000)
    height = _to_float(height_raw, 8000)

    scale = 200.0   # 1:200 approximate
    w = span / scale
    h = height / scale

    ox, oy = 160.0, 80.0
    msp.add_lwpolyline(
        [(ox, oy), (ox + w, oy), (ox + w, oy + h), (ox, oy + h), (ox, oy)],
        dxfattribs={"layer": "FRAME", "closed": True},
    )
    # Dimension annotations
    msp.add_text(f"SPAN {span:.0f}mm", dxfattribs={"height": 3.5, "insert": (ox + w / 2 - 10, oy - 8)})
    msp.add_text(f"HT {height:.0f}mm", dxfattribs={"height": 3.5, "insert": (ox + w + 3, oy + h / 2)})

    doc.saveas(path)
    logger.info("GA DXF written: %s", path)


# ---------------------------------------------------------------------------
# ODA DXF → DWG conversion
# ---------------------------------------------------------------------------

def _oda_convert(dxf_path: Path, output_dir: Path) -> Path | None:
    """
    Call ODA File Converter to convert *dxf_path* to DWG in *output_dir*.
    Returns the DWG Path on success, None otherwise.
    """
    oda_exe = Path(settings.oda_path)
    if not oda_exe.exists():
        logger.warning("ODA File Converter not found at %s — skipping DWG conversion", oda_exe)
        return None

    dwg_name = dxf_path.with_suffix(".dwg").name

    try:
        # ODA CLI: ODAFileConverter <input_dir> <output_dir> <version> <format> <recurse> <audit> [filter]
        # version=ACAD2018, format=DWG
        cmd = [
            str(oda_exe),
            str(dxf_path.parent),
            str(output_dir),
            "ACAD2018",
            "DWG",
            "0",   # no recursion
            "1",   # audit
            dxf_path.name,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        dwg_path = output_dir / dwg_name
        if dwg_path.exists():
            logger.info("DWG written: %s", dwg_path)
            return dwg_path
        logger.warning("ODA ran but DWG not found.  stdout=%s  stderr=%s",
                       result.stdout[:300], result.stderr[:300])
    except Exception as exc:
        logger.warning("ODA conversion failed: %s", exc)

    return None


# ---------------------------------------------------------------------------
# Summary report
# ---------------------------------------------------------------------------

def _write_summary(
    project_id: UUID,
    ab_payload: dict | None,
    ga_payload: dict | None,
    outputs: list[dict],
    path: Path,
) -> None:
    lines = [
        "=" * 60,
        "PHASE 2 DRAWING OUTPUT SUMMARY",
        f"Project: {project_id}",
        "=" * 60,
        "",
    ]
    for out in outputs:
        lines += [
            f"Output type : {out['type']}",
            f"  DXF       : {out['dxf']}",
            f"  DWG       : {out.get('dwg') or 'Not generated (ODA unavailable)'}",
            "",
        ]
    if ab_payload:
        lines += ["ANCHOR BOLT FIELDS:"]
        for k, v in ab_payload.get("anchor_bolt_fields", {}).items():
            lines.append(f"  {k}: {v}")
        lines.append("")
    if ga_payload:
        lines += ["GENERAL ARRANGEMENT FIELDS:"]
        for k, v in ga_payload.get("general_arrangement_fields", {}).items():
            lines.append(f"  {k}: {v}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _to_float(value, default: float) -> float:
    if not value:
        return default
    try:
        return float(str(value).replace("mm", "").replace("m", "").strip())
    except (ValueError, TypeError):
        return default


def _add_title_block(msp, title: str, project_id: str) -> None:
    msp.add_text(title, dxfattribs={"height": 7, "insert": (10, 275)})
    msp.add_text(f"Project: {project_id[:36]}", dxfattribs={"height": 3.5, "insert": (10, 265)})
    msp.add_text("Infiniti Steel Detailing Automation — Phase 2",
                 dxfattribs={"height": 3, "insert": (10, 258)})
    # Border
    msp.add_lwpolyline(
        [(5, 5), (295, 5), (295, 205), (5, 205), (5, 5)],
        dxfattribs={"layer": "BORDER", "closed": True},
    )
