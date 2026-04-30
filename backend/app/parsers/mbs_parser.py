from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ParsedField:
    field_code: str
    field_name: str
    raw_value: str
    normalized_value: str
    unit: str | None
    source_path: str
    confidence: int


class MBSParser:
    """Extract a practical first pass of project facts from MBS exports.

    MBS exports may arrive as XML or text-like reports. This adapter focuses on
    stable Phase 2 inputs first: project metadata, grid/bay dimensions, eave
    height, roof slope, and frame/member counts where discoverable.
    """

    def parse(self, file_path: str) -> dict:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(file_path)

        text = path.read_text(encoding="utf-8", errors="ignore")
        values = self._parse_xml(text) if self._looks_like_xml(text) else {}
        values.update(self._parse_key_value_text(text))

        fields = [
            ParsedField(
                field_code=f"RAW-MBS-{self._clean_key(field_name).upper()}",
                field_name=field_name,
                raw_value=raw_value,
                normalized_value=self._normalize_value(raw_value),
                unit=None,
                source_path=str(path),
                confidence=90 if self._looks_like_xml(text) else 75,
            )
            for field_name, raw_value in values.items()
            if raw_value not in (None, "")
        ]

        return {
            "parser": "MBSParser",
            "source_path": str(path),
            "field_count": len(fields),
            "confidence": 90 if fields and self._looks_like_xml(text) else 75 if fields else 0,
            "fields": [field.__dict__ for field in fields],
        }

    def _looks_like_xml(self, text: str) -> bool:
        return text.lstrip().startswith("<")

    def _parse_xml(self, text: str) -> dict[str, str]:
        try:
            root = ET.fromstring(text)
        except ET.ParseError:
            return {}

        extracted: dict[str, str] = {}
        for element in root.iter():
            key = self._clean_key(element.tag)
            value = (element.text or "").strip()
            if not value:
                continue
            extracted.setdefault(key, value)
            for attr_key, attr_value in element.attrib.items():
                extracted.setdefault(self._clean_key(attr_key), attr_value.strip())
        return extracted

    def _parse_key_value_text(self, text: str) -> dict[str, str]:
        extracted: dict[str, str] = {}
        for line in text.splitlines():
            match = re.match(r"^\s*([A-Za-z0-9 _/-]+)\s*[:=]\s*(.+?)\s*$", line)
            if not match:
                continue
            key = self._clean_key(match.group(1))
            value = match.group(2).strip()
            extracted.setdefault(key, value)
        return extracted

    def _clean_key(self, key: str) -> str:
        return re.sub(r"[^a-z0-9]", "", key.lower())

    def _normalize_value(self, value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()
