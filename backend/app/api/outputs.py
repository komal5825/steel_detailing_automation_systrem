from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.agents.phase2.output_utils import project_output_dir
from app.config.settings import settings
from app.db.crud.projects import get_project, list_project_files
from app.db.crud.stages import list_project_stages
from app.db.session import get_db

router = APIRouter()


def _project_output_root(project_id: UUID) -> Path:
    return Path(settings.project_data_root) / str(project_id) / "outputs"


def _project_processed_root(project_id: UUID) -> Path:
    return Path(settings.project_data_root) / str(project_id) / "Processed"


def _as_download(path: Path) -> dict:
    rel = path.relative_to(path.parents[2]).as_posix() if len(path.parents) > 2 else path.name
    return {
        "name": path.name,
        "relative_path": rel,
        "extension": path.suffix.lower().lstrip(".") or "file",
        "size_bytes": path.stat().st_size,
        "modified_at": datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
    }


def _collect_report_data(db: Session, project_id: UUID) -> dict:
    project = get_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    stages = list_project_stages(db, project_id)
    files = list_project_files(db, project_id)
    output_root = _project_output_root(project_id)
    outputs = []
    if output_root.exists():
        outputs = [
            _as_download(path)
            for path in output_root.rglob("*")
            if path.is_file()
        ]

    return {
        "generated_at": datetime.utcnow().isoformat(),
        "project": {
            "id": str(project.id),
            "proposal_id": project.proposal_id,
            "name": project.name,
            "location": project.location,
            "project_type": project.project_type,
            "status": project.status.value,
        },
        "files": [
            {
                "id": str(file.id),
                "original_filename": file.original_filename,
                "file_type": file.file_type,
                "file_category": file.file_category,
                "source_application": file.source_application,
                "likely_role": file.likely_role,
                "classification_confidence": file.classification_confidence,
                "processing_status": file.processing_status.value,
            }
            for file in files
        ],
        "stages": [
            {
                "stage_code": stage.stage_code,
                "status": stage.status.value,
                "started_at": stage.started_at.isoformat() if stage.started_at else None,
                "completed_at": stage.completed_at.isoformat() if stage.completed_at else None,
                "error_message": stage.error_message,
                "result": json.loads(stage.result_json or "{}"),
            }
            for stage in stages
        ],
        "outputs": outputs,
    }


def _report_lines(data: dict) -> list[str]:
    project = data["project"]
    lines = [
        "Infiniti Steel Detailing Automation",
        "Phase 2 Project Status Report",
        "",
        f"Project: {project['name']}",
        f"Proposal ID: {project['proposal_id']}",
        f"Location: {project.get('location') or '-'}",
        f"Project type: {project.get('project_type') or '-'}",
        f"Generated at: {data['generated_at']}",
        "",
        "Stage Status",
    ]
    for stage in data["stages"]:
        lines.append(f"- {stage['stage_code']}: {stage['status']}")
    lines.extend(["", "File Inventory"])
    for file in data["files"]:
        lines.append(
            f"- {file['original_filename']} | {file['file_type']} | "
            f"{file['likely_role']} | {file['processing_status']} | "
            f"{file['classification_confidence']}%"
        )
    lines.extend(["", "Output Files"])
    if data["outputs"]:
        for output in data["outputs"]:
            lines.append(f"- {output['relative_path']} ({output['size_bytes']} bytes)")
    else:
        lines.append("- No generated output files yet.")
    return lines


def _write_docx_report(path: Path, data: dict) -> None:
    from docx import Document

    doc = Document()
    project = data["project"]
    doc.add_heading("Phase 2 Project Status Report", 0)
    doc.add_paragraph(f"Project: {project['name']}")
    doc.add_paragraph(f"Proposal ID: {project['proposal_id']}")
    doc.add_paragraph(f"Generated at: {data['generated_at']}")

    doc.add_heading("Stage Status", level=1)
    table = doc.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "Stage"
    table.rows[0].cells[1].text = "Status"
    for stage in data["stages"]:
        cells = table.add_row().cells
        cells[0].text = stage["stage_code"]
        cells[1].text = stage["status"]

    doc.add_heading("File Inventory", level=1)
    file_table = doc.add_table(rows=1, cols=5)
    headers = ["File", "Type", "Role", "Status", "Confidence"]
    for index, header in enumerate(headers):
        file_table.rows[0].cells[index].text = header
    for file in data["files"]:
        cells = file_table.add_row().cells
        cells[0].text = file["original_filename"]
        cells[1].text = file["file_type"]
        cells[2].text = file["likely_role"]
        cells[3].text = file["processing_status"]
        cells[4].text = f"{file['classification_confidence']}%"
    doc.save(path)


def _write_pdf_report(path: Path, data: dict) -> None:
    import fitz

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    text = "\n".join(_report_lines(data))
    rect = fitz.Rect(42, 42, 553, 800)
    page.insert_textbox(rect, text, fontsize=9, fontname="helv", lineheight=1.25)
    doc.save(path)
    doc.close()


@router.get("/{project_id}/files")
async def list_output_files(project_id: str):
    try:
        pid = UUID(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid project_id") from exc

    output_root = _project_output_root(pid)
    files = []
    if output_root.exists():
        files = [
            {
                **_as_download(path),
                "relative_path": path.relative_to(output_root).as_posix(),
            }
            for path in output_root.rglob("*")
            if path.is_file()
        ]
    return {"project_id": project_id, "files": files}


@router.get("/{project_id}/download/{file_path:path}")
async def download_output_file(project_id: str, file_path: str):
    try:
        pid = UUID(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid project_id") from exc

    output_root = _project_output_root(pid).resolve()
    target = (output_root / file_path).resolve()
    try:
        target.relative_to(output_root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid output path") from exc
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="Output file not found")
    return FileResponse(target, filename=target.name)


@router.get("/{project_id}/report/{format_name}")
async def download_phase_report(
    project_id: str,
    format_name: str,
    db: Session = Depends(get_db),
):
    try:
        pid = UUID(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid project_id") from exc

    fmt = format_name.lower()
    if fmt not in {"json", "txt", "docx", "pdf"}:
        raise HTTPException(status_code=400, detail="Supported formats: json, txt, docx, pdf")

    data = _collect_report_data(db, pid)
    reports_dir = project_output_dir(pid, "reports")
    report_path = reports_dir / f"phase2_status_report.{fmt}"

    if fmt == "json":
        report_path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        media_type = "application/json"
    elif fmt == "txt":
        report_path.write_text("\n".join(_report_lines(data)), encoding="utf-8")
        media_type = "text/plain"
    elif fmt == "docx":
        _write_docx_report(report_path, data)
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    else:
        _write_pdf_report(report_path, data)
        media_type = "application/pdf"

    return FileResponse(report_path, filename=report_path.name, media_type=media_type)


# ---------------------------------------------------------------------------
# Processed/ file helpers
# ---------------------------------------------------------------------------

def _load_processed_json(project_id: UUID, filename: str) -> dict:
    path = _project_processed_root(project_id) / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Processed file '{filename}' not found")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read '{filename}': {exc}") from exc


def _processed_export_dir(project_id: UUID) -> Path:
    path = Path(settings.project_data_root) / str(project_id) / "outputs" / "processed_exports"
    path.mkdir(parents=True, exist_ok=True)
    return path


# --- PDF builders ---

def _write_file_inventory_pdf(path: Path, data: dict) -> None:
    import fitz
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    y = 42.0

    def _line(text: str, size: float = 9, bold: bool = False, indent: float = 0) -> None:
        nonlocal y
        font = "helv-bold" if bold else "helv"
        page.insert_text(fitz.Point(42 + indent, y), text, fontsize=size, fontname=font)
        y += size * 1.6

    _line("File Inventory Report", 14, bold=True)
    _line(f"Project: {data.get('project_id', '-')}", 9)
    _line(f"Total files: {data.get('total_files', 0)}   Parsed: {data.get('parsed_files', 0)}"
          f"   Failed: {data.get('failed_files', 0)}", 9)
    y += 8

    for f in data.get("files", []):
        if y > 790:
            page = doc.new_page(width=595, height=842)
            y = 42.0
        _line(f"• {f.get('original_filename', '-')}", 9, bold=True)
        _line(f"  Type: {f.get('file_type', '-')}  |  Category: {f.get('file_category', '-')}"
              f"  |  Role: {f.get('likely_role', '-')}", 8, indent=8)
        _line(f"  Source: {f.get('source_application', '-')}"
              f"  |  Status: {f.get('processing_status', '-')}"
              f"  |  Confidence: {f.get('classification_confidence', '-')}", 8, indent=8)
        y += 4

    doc.save(path)
    doc.close()


def _write_governing_source_pdf(path: Path, data: dict) -> None:
    import fitz
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    y = 42.0

    def _line(text: str, size: float = 9, bold: bool = False) -> None:
        nonlocal y
        font = "helv-bold" if bold else "helv"
        page.insert_text(fitz.Point(42, y), text, fontsize=size, fontname=font)
        y += size * 1.6

    _line("Governing Source Report", 14, bold=True)
    _line(f"Project: {data.get('project_id', '-')}", 9)
    _line(f"Selection method: {data.get('selection_method', '-')}", 9)
    _line(f"Rationale: {data.get('rationale', '-')}", 9)
    y += 8

    gf = data.get("governing_file") or {}
    if gf:
        _line("Governing File", 11, bold=True)
        for key, val in gf.items():
            _line(f"  {key}: {val}", 9)
    y += 6

    candidates = data.get("candidates", [])
    if candidates:
        _line("All Candidates (ranked)", 11, bold=True)
        for c in candidates:
            _line(f"  • {c.get('original_filename', '-')}  [{c.get('file_type', '-')}]"
                  f"  confidence={c.get('classification_confidence', '-')}", 9)

    doc.save(path)
    doc.close()


def _write_completeness_matrix_pdf(path: Path, data: dict) -> None:
    import fitz
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    y = 42.0

    def _line(text: str, size: float = 9, bold: bool = False, color=(0, 0, 0)) -> None:
        nonlocal y
        font = "helv-bold" if bold else "helv"
        page.insert_text(fitz.Point(42, y), text, fontsize=size, fontname=font, color=color)
        y += size * 1.6

    gate = data.get("gate_status", "?")
    gate_color = (0, 0.5, 0) if gate == "PASS" else (0.8, 0, 0)
    _line("Completeness Matrix Report", 14, bold=True)
    _line(f"Gate: {gate}  |  Overall: {data.get('overall', '-')}", 11, bold=True, color=gate_color)
    y += 6

    for label, key in (("AB Readiness", "ab_readiness"), ("GA Readiness", "ga_readiness")):
        rd = data.get(key, {})
        status = rd.get("status", "-")
        clr = (0, 0.5, 0) if status == "READY" else (0.8, 0, 0)
        _line(f"{label} — {status}", 11, bold=True, color=clr)
        _line(f"  Required: {rd.get('required_count', 0)}   Present: {rd.get('present_count', 0)}"
              f"   Missing: {rd.get('missing_count', 0)}", 9)
        if rd.get("missing_codes"):
            _line(f"  Missing: {', '.join(rd['missing_codes'])}", 8, color=(0.7, 0, 0))
        y += 4

    blockers = data.get("blocking_issues", [])
    if blockers:
        _line("Blocking Issues", 11, bold=True, color=(0.8, 0, 0))
        for b in blockers:
            affects = "/".join(b.get("affects", []))
            _line(f"  • {b['field_code']}  [{affects}]  — {b.get('note', '')}", 8)

    warnings = data.get("non_blocking_warnings", [])
    if warnings:
        y += 4
        _line("Non-Blocking Warnings", 10, bold=True, color=(0.6, 0.4, 0))
        for w in warnings:
            _line(f"  • {w.get('field_code', '-')}  — {w.get('note', '')}", 8)

    hr = data.get("human_review_required", [])
    if hr:
        y += 4
        _line("Human Review Required", 10, bold=True)
        _line("  " + ", ".join(hr), 8)

    doc.save(path)
    doc.close()


# --- DOCX builders ---

def _write_file_inventory_docx(path: Path, data: dict) -> None:
    from docx import Document
    doc = Document()
    doc.add_heading("File Inventory Report", 0)
    doc.add_paragraph(f"Project: {data.get('project_id', '-')}")
    doc.add_paragraph(
        f"Total: {data.get('total_files', 0)}  Parsed: {data.get('parsed_files', 0)}"
        f"  Failed: {data.get('failed_files', 0)}"
    )
    doc.add_heading("Files", level=1)
    table = doc.add_table(rows=1, cols=6)
    headers = ["Filename", "Type", "Category", "Source", "Role", "Status"]
    for i, h in enumerate(headers):
        table.rows[0].cells[i].text = h
    for f in data.get("files", []):
        cells = table.add_row().cells
        cells[0].text = f.get("original_filename", "-")
        cells[1].text = f.get("file_type", "-")
        cells[2].text = f.get("file_category", "-")
        cells[3].text = f.get("source_application", "-")
        cells[4].text = f.get("likely_role", "-")
        cells[5].text = f.get("processing_status", "-")
    doc.save(path)


def _write_governing_source_docx(path: Path, data: dict) -> None:
    from docx import Document
    doc = Document()
    doc.add_heading("Governing Source Report", 0)
    doc.add_paragraph(f"Project: {data.get('project_id', '-')}")
    doc.add_paragraph(f"Method: {data.get('selection_method', '-')}")
    doc.add_paragraph(f"Rationale: {data.get('rationale', '-')}")
    gf = data.get("governing_file") or {}
    if gf:
        doc.add_heading("Governing File", level=1)
        for key, val in gf.items():
            doc.add_paragraph(f"{key}: {val}")
    candidates = data.get("candidates", [])
    if candidates:
        doc.add_heading("All Candidates", level=1)
        table = doc.add_table(rows=1, cols=3)
        for i, h in enumerate(["Filename", "Type", "Confidence"]):
            table.rows[0].cells[i].text = h
        for c in candidates:
            cells = table.add_row().cells
            cells[0].text = c.get("original_filename", "-")
            cells[1].text = c.get("file_type", "-")
            cells[2].text = str(c.get("classification_confidence", "-"))
    doc.save(path)


def _write_completeness_matrix_docx(path: Path, data: dict) -> None:
    from docx import Document
    doc = Document()
    doc.add_heading("Completeness Matrix Report", 0)
    doc.add_paragraph(f"Gate: {data.get('gate_status', '-')}  |  Overall: {data.get('overall', '-')}")
    for label, key in (("AB Readiness", "ab_readiness"), ("GA Readiness", "ga_readiness")):
        rd = data.get(key, {})
        doc.add_heading(label, level=1)
        doc.add_paragraph(
            f"Status: {rd.get('status', '-')}  Required: {rd.get('required_count', 0)}"
            f"  Present: {rd.get('present_count', 0)}  Missing: {rd.get('missing_count', 0)}"
        )
        if rd.get("missing_codes"):
            doc.add_paragraph("Missing: " + ", ".join(rd["missing_codes"]))
    blockers = data.get("blocking_issues", [])
    if blockers:
        doc.add_heading("Blocking Issues", level=1)
        table = doc.add_table(rows=1, cols=3)
        for i, h in enumerate(["Field Code", "Affects", "Note"]):
            table.rows[0].cells[i].text = h
        for b in blockers:
            cells = table.add_row().cells
            cells[0].text = b.get("field_code", "-")
            cells[1].text = "/".join(b.get("affects", []))
            cells[2].text = b.get("note", "")
    doc.save(path)


_PDF_BUILDERS = {
    "file_inventory.json": _write_file_inventory_pdf,
    "governing_source.json": _write_governing_source_pdf,
    "completeness_matrix.json": _write_completeness_matrix_pdf,
}

_DOCX_BUILDERS = {
    "file_inventory.json": _write_file_inventory_docx,
    "governing_source.json": _write_governing_source_docx,
    "completeness_matrix.json": _write_completeness_matrix_docx,
}


def _pdf_to_png(pdf_path: Path, png_path: Path) -> None:
    import fitz
    doc = fitz.open(str(pdf_path))
    page = doc[0]
    pix = page.get_pixmap(dpi=150)
    pix.save(str(png_path))
    doc.close()


# ---------------------------------------------------------------------------
# Processed/ endpoints
# ---------------------------------------------------------------------------

@router.get("/{project_id}/processed/files")
async def list_processed_files(project_id: str):
    try:
        pid = UUID(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid project_id") from exc

    processed_root = _project_processed_root(pid)
    files = []
    if processed_root.exists():
        files = [
            {
                "name": path.name,
                "size_bytes": path.stat().st_size,
                "modified_at": datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
            }
            for path in sorted(processed_root.iterdir())
            if path.is_file() and path.suffix == ".json"
        ]
    return {"project_id": project_id, "files": files}


@router.get("/{project_id}/processed/download/{filename}")
async def download_processed_file(project_id: str, filename: str):
    try:
        pid = UUID(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid project_id") from exc

    processed_root = _project_processed_root(pid).resolve()
    target = (processed_root / filename).resolve()
    try:
        target.relative_to(processed_root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid filename") from exc
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail=f"File '{filename}' not found")
    return FileResponse(target, filename=target.name, media_type="application/json")


@router.get("/{project_id}/processed/export/{filename}/{format_name}")
async def export_processed_file(project_id: str, filename: str, format_name: str):
    try:
        pid = UUID(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid project_id") from exc

    fmt = format_name.lower()
    if fmt not in {"json", "pdf", "docx", "png"}:
        raise HTTPException(status_code=400, detail="Supported formats: json, pdf, docx, png")

    data = _load_processed_json(pid, filename)
    stem = Path(filename).stem
    export_dir = _processed_export_dir(pid)

    if fmt == "json":
        out = export_dir / f"{stem}.json"
        out.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        return FileResponse(out, filename=out.name, media_type="application/json")

    if fmt == "pdf":
        builder = _PDF_BUILDERS.get(filename)
        if builder is None:
            out = export_dir / f"{stem}.pdf"
            import fitz
            doc = fitz.open()
            page = doc.new_page(width=595, height=842)
            text = json.dumps(data, indent=2, default=str)
            page.insert_textbox(fitz.Rect(42, 42, 553, 800), text,
                                fontsize=8, fontname="helv", lineheight=1.3)
            doc.save(str(out))
            doc.close()
        else:
            out = export_dir / f"{stem}.pdf"
            builder(out, data)
        return FileResponse(out, filename=out.name, media_type="application/pdf")

    if fmt == "docx":
        builder = _DOCX_BUILDERS.get(filename)
        if builder is None:
            raise HTTPException(
                status_code=400,
                detail=f"DOCX export not supported for '{filename}'. "
                       "Supported files: file_inventory.json, governing_source.json, "
                       "completeness_matrix.json"
            )
        out = export_dir / f"{stem}.docx"
        builder(out, data)
        media = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        return FileResponse(out, filename=out.name, media_type=media)

    # PNG — render PDF page 1 to image
    pdf_builder = _PDF_BUILDERS.get(filename)
    pdf_out = export_dir / f"{stem}_tmp.pdf"
    if pdf_builder is None:
        import fitz as _fitz
        doc = _fitz.open()
        page = doc.new_page(width=595, height=842)
        text = json.dumps(data, indent=2, default=str)
        page.insert_textbox(_fitz.Rect(42, 42, 553, 800), text,
                            fontsize=8, fontname="helv", lineheight=1.3)
        doc.save(str(pdf_out))
        doc.close()
    else:
        pdf_builder(pdf_out, data)
    png_out = export_dir / f"{stem}.png"
    _pdf_to_png(pdf_out, png_out)
    return FileResponse(png_out, filename=png_out.name, media_type="image/png")
