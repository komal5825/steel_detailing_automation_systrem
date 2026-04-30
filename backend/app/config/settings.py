from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    # Storage Paths
    project_data_root: str = "./data/projects"
    reference_jobs_path: str = "./data/reference_jobs"
    chroma_path: str = "./data/chromadb"
    temp_path: str = "./data/temp"
    log_base_path: str = "./data/logs"
    master_db_path: str = "../DB/master_db.db"

    # CAD Tools
    oda_path: str = r"C:\Program Files\ODA\ODAFileConverter\ODAFileConverter.exe"
    unrar_path: str = r"C:\Program Files\WinRAR\UnRAR.exe"
    tesseract_path: str = ""

    # Database
    database_url: str = "sqlite:///./app/db/steel_detailing.db"
    secret_key: str = "supersecretkey"

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"

    # LLM
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3"

    # Parser
    p2_parser_timeout: int = 120

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
