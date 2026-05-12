import sys
import os

# Add backend to path
sys.path.append(os.getcwd())

from app.orchestrator.controller import OrchestrationController

project_id = '1dac5ce2-0cea-452f-9fcd-bf915390e78e'
controller = OrchestrationController()
result = controller.run(project_id, to_stage='P2-01')

print(f"Ingestion result: {result['stages'][0]['status']}")
print(f"Extracted fields: {result['stages'][0]['result'].get('extracted_fields')}")
print(f"Governing file: {result['stages'][0]['result'].get('governing_file', {}).get('original_filename')}")
