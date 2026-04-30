import os
import zipfile
import shutil
import logging

# Note: rarfile requires unrar tool installed
try:
    import rarfile
except ImportError:
    rarfile = None

logger = logging.getLogger(__name__)

class ArchiveHandler:
    @classmethod
    def extract(cls, archive_path: str, extract_to: str) -> list[str]:
        """Extracts archive and returns list of extracted file paths."""
        if not os.path.exists(extract_to):
            os.makedirs(extract_to)

        extracted_files = []
        _, ext = os.path.splitext(archive_path.lower())

        if ext == '.zip':
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                zip_ref.extractall(extract_to)
                extracted_files = [os.path.join(extract_to, f) for f in zip_ref.namelist()]
        elif ext == '.rar':
            if rarfile:
                with rarfile.RarFile(archive_path, 'r') as rar_ref:
                    rar_ref.extractall(extract_to)
                    extracted_files = [os.path.join(extract_to, f) for f in rar_ref.namelist()]
            else:
                logger.error("rarfile package not installed. Cannot extract RAR.")
        
        return extracted_files
