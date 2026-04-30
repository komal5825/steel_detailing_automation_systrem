from __future__ import annotations

import re
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


class StaadParser:
    """Extract a first-pass structural summary from STAAD `.std` files."""

    FIELD_CODES = {
        "node_count": "STAAD-NODE-COUNT",
        "member_count": "STAAD-MEMBER-COUNT",
        "support_count": "STAAD-SUPPORT-COUNT",
        "load_case_count": "STAAD-LOAD-CASE-COUNT",
        "section_property_count": "STAAD-SECTION-PROPERTY-COUNT",
        "material_constant_count": "STAAD-MATERIAL-CONSTANT-COUNT",
        "unit_system": "STAAD-UNIT-SYSTEM",
    }

    UNITS = {
        "node_count": "count",
        "member_count": "count",
        "support_count": "count",
        "load_case_count": "count",
        "section_property_count": "count",
        "material_constant_count": "count",
    }

    def parse(self, file_path: str) -> dict:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(file_path)

        text = path.read_text(encoding="utf-8", errors="ignore")
        lines = [line.strip() for line in text.splitlines()]
        sections = self._collect_sections(lines)

        values = {
            "node_count": self._count_joint_coordinates(sections.get("joint_coordinates", [])),
            "member_count": self._count_member_incidences(sections.get("member_incidences", [])),
            "support_count": self._count_supports(sections.get("supports", [])),
            "load_case_count": self._count_load_cases(lines),
            "section_property_count": self._count_section_properties(sections.get("member_properties", [])),
            "material_constant_count": self._count_material_constants(sections.get("constants", [])),
            "unit_system": self._extract_unit_system(lines),
        }

        fields = [
            ParsedField(
                field_code=self.FIELD_CODES[field_name],
                field_name=field_name,
                raw_value=str(raw_value),
                normalized_value=str(raw_value),
                unit=self.UNITS.get(field_name),
                source_path=str(path),
                confidence=85,
            )
            for field_name, raw_value in values.items()
            if raw_value not in (None, "", 0)
        ]

        return {
            "parser": "StaadParser",
            "source_path": str(path),
            "field_count": len(fields),
            "confidence": 85 if fields else 0,
            "fields": [field.__dict__ for field in fields],
        }

    def _collect_sections(self, lines: list[str]) -> dict[str, list[str]]:
        sections = {
            "joint_coordinates": [],
            "member_incidences": [],
            "member_properties": [],
            "constants": [],
            "supports": [],
        }
        current: str | None = None

        for line in lines:
            upper = line.upper()
            if not line or upper.startswith("*"):
                continue
            if upper.startswith("JOINT COORDINATES"):
                current = "joint_coordinates"
                continue
            if upper.startswith("MEMBER INCIDENCES"):
                current = "member_incidences"
                continue
            if upper.startswith("MEMBER PROPERTY"):
                current = "member_properties"
                continue
            if upper.startswith("CONSTANTS"):
                current = "constants"
                continue
            if upper.startswith("SUPPORTS"):
                current = "supports"
                continue
            if self._starts_new_section(upper):
                current = None
            if current:
                sections[current].append(line)

        return sections

    def _starts_new_section(self, upper_line: str) -> bool:
        section_prefixes = (
            "DEFINE ",
            "LOAD ",
            "PERFORM ",
            "FINISH",
            "START ",
            "END ",
            "PRINT ",
            "PARAMETER",
            "CHECK ",
            "STEEL ",
        )
        return upper_line.startswith(section_prefixes)

    def _count_joint_coordinates(self, lines: list[str]) -> int:
        return sum(1 for line in lines if re.match(r"^\d+\s+[-+0-9.]", line))

    def _count_member_incidences(self, lines: list[str]) -> int:
        return sum(1 for line in lines if re.match(r"^\d+\s+\d+\s+\d+", line))

    def _count_supports(self, lines: list[str]) -> int:
        return sum(1 for line in lines if re.match(r"^\d+(\s+\d+)*\s+(FIXED|PINNED|ENFORCED|SPRING)", line.upper()))

    def _count_load_cases(self, lines: list[str]) -> int:
        return sum(1 for line in lines if re.match(r"^LOAD\s+\d+", line.upper()))

    def _count_section_properties(self, lines: list[str]) -> int:
        return sum(1 for line in lines if re.match(r"^\d+(\s+TO\s+\d+|\s+\d+)*\s+", line.upper()))

    def _count_material_constants(self, lines: list[str]) -> int:
        return sum(1 for line in lines if re.match(r"^(E|POISSON|DENSITY|ALPHA)\s+", line.upper()))

    def _extract_unit_system(self, lines: list[str]) -> str | None:
        for line in lines:
            match = re.match(r"^UNIT\s+(.+)$", line.upper())
            if match:
                return match.group(1).strip()
        return None
