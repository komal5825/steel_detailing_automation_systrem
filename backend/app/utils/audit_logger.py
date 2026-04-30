import logging
import os
from app.config.settings import settings

log_file_path = os.path.join(settings.log_base_path, "audit.log")
os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

logging.basicConfig(
    filename=log_file_path,
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def get_logger(name):
    return logging.getLogger(name)
