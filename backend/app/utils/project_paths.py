from __future__ import annotations

from pathlib import Path

from app.config.settings import settings


def get_writable_project_data_root() -> Path:
    """
    Return a writable project-data root.

    Primary: configured `settings.project_data_root`.
    Fallback: `<backend>/data/projects` when the configured location is not writable.
    """
    configured_root = Path(settings.project_data_root)
    if _is_writable_dir(configured_root):
        return configured_root

    backend_root = Path(__file__).resolve().parents[2]
    fallback_root = backend_root / "data" / "projects"
    fallback_root.mkdir(parents=True, exist_ok=True)
    return fallback_root


def _is_writable_dir(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except Exception:
        return False
