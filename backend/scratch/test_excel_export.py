import uuid
import json
from fastapi.testclient import TestClient
from main import app
from app.db.session import SessionLocal
from app.db.models import Project, ProjectStatus, ProjectFile, ParserRun, ExtractedFieldValue, ValidationResult, AuditEventLog

client = TestClient(app)

def test_excel_export():
    db = SessionLocal()
    pid = uuid.uuid4()
    project = Project(
        id=pid,
        proposal_id=f"XL-TEST-{pid.hex[:6]}",
        name="Excel Export Test",
        status=ProjectStatus.CREATED
    )
    db.add(project)
    db.commit()
    
    # Add various pieces of evidence
    f1 = ProjectFile(
        project_id=pid, original_filename="test.mbs", stored_path="test.mbs",
        file_type="MBS", file_category="DESIGN", source_application="MBS",
        likely_role="GOVERNING", classification_confidence=100
    )
    db.add(f1)
    db.flush()
    
    pr = ParserRun(
        project_id=pid, project_file_id=f1.id, parser_name="MBSParser",
        status="SUCCESS", confidence=100, message="Extracted 1 field"
    )
    db.add(pr)
    db.flush()
    
    val = ValidationResult(
        project_id=pid, stage_code="P2-01", field_code="F-081",
        status="PRESENT", severity="MINOR", note="Test value"
    )
    db.add(val)
    
    log = AuditEventLog(
        project_id=pid, event_type="TEST_EXPORT", detail=json.dumps({"test": "ok"})
    )
    db.add(log)
    db.commit()
    
    print(f"Testing Excel export for project {pid}")
    resp = client.get(f"/api/outputs/{pid}/export/excel")
    print(f"Excel Export Response: {resp.status_code}")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    
    # Basic size check (should be more than 1kb)
    assert len(resp.content) > 1000
    print("Excel evidence export verified successfully!")
    db.close()

if __name__ == "__main__":
    test_excel_export()
