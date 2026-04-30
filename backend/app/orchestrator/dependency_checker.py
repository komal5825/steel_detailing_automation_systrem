from __future__ import annotations

import json
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

from app.config.settings import settings


class DependencyChecker:
    def check_dependencies(self, stage: str | None = None) -> dict:
        return {
            "unrar": self._check_executable("UnRAR", settings.unrar_path, "unrar"),
            "oda": self._check_executable("ODA File Converter", settings.oda_path, "ODAFileConverter"),
            "ollama": self._check_ollama(),
            "tesseract": self._check_executable("Tesseract OCR", settings.tesseract_path, "tesseract"),
        }

    def _check_executable(self, name: str, configured_path: str | None, fallback_command: str) -> dict:
        configured_path = (configured_path or "").strip()
        resolved_path = configured_path if configured_path and Path(configured_path).exists() else shutil.which(fallback_command)
        available = bool(resolved_path)

        version = None
        if available:
            version = self._read_version(str(resolved_path))

        return {
            "name": name,
            "available": available,
            "path": str(resolved_path) if resolved_path else None,
            "version": version,
        }

    def _read_version(self, executable_path: str) -> str | None:
        commands = [
            [executable_path, "--version"],
            [executable_path, "-version"],
            [executable_path],
        ]
        for command in commands:
            try:
                result = subprocess.run(command, capture_output=True, text=True, timeout=5)
            except Exception:
                continue
            output = (result.stdout or result.stderr).strip()
            if output and not output.upper().startswith("ERROR"):
                return output.splitlines()[0]
        return None

    def _check_ollama(self) -> dict:
        url = settings.ollama_base_url.rstrip("/") + "/api/tags"
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            return {
                "name": "Ollama",
                "available": False,
                "running": False,
                "base_url": settings.ollama_base_url,
                "model_configured": settings.ollama_model,
                "models": [],
                "error": str(exc),
            }

        models = [model.get("name") for model in payload.get("models", []) if model.get("name")]
        configured = settings.ollama_model
        configured_available = configured in models or f"{configured}:latest" in models
        return {
            "name": "Ollama",
            "available": True,
            "running": True,
            "base_url": settings.ollama_base_url,
            "model_configured": configured,
            "model_available": configured_available,
            "models": models,
        }
