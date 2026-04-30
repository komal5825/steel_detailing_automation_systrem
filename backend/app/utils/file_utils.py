import os
from uuid import UUID

class FileUtils:
    @staticmethod
    def get_project_dir(base_path: str, project_uuid: UUID) -> str:
        return os.path.join(base_path, str(project_uuid))

    @staticmethod
    def get_raw_inputs_dir(project_dir: str) -> str:
        return os.path.join(project_dir, "Raw_Inputs")

    @staticmethod
    def get_processed_dir(project_dir: str) -> str:
        return os.path.join(project_dir, "Processed")

    @staticmethod
    def get_logs_dir(project_dir: str) -> str:
        return os.path.join(project_dir, "Logs")
