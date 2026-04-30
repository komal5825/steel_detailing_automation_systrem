from .celery_app import celery_app

@celery_app.task
def phase2_ingestion_task(project_id: str):
    print(f"Task: Phase 2 Ingestion for {project_id}")
    return True

@celery_app.task
def phase2_generation_task(project_id: str):
    print(f"Task: Phase 2 Generation for {project_id}")
    return True
