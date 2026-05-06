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
        "job_engineer": "STAAD-JOB-ENGINEER",
        "job_date": "STAAD-JOB-DATE",
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
        
        # Pre-process continuation lines (ending with -)
        processed_lines = self._preprocess_continuation(lines)
        
        sections = self._collect_sections(processed_lines)
        job_info = self._extract_job_info(processed_lines)

        values = {
            "node_count": self._count_joints(sections.get("joint_coordinates", [])),
            "member_count": self._count_members(sections.get("member_incidences", [])),
            "support_count": self._count_supports(sections.get("supports", [])),
            "load_case_count": self._count_load_cases(processed_lines),
            "section_property_count": self._count_section_properties(sections.get("member_properties", [])),
            "material_constant_count": self._count_material_constants(sections.get("constants", [])),
            "unit_system": self._extract_unit_system(processed_lines),
            "job_engineer": job_info.get("engineer"),
            "job_date": job_info.get("date"),
        }

        fields = [
            ParsedField(
                field_code=self.FIELD_CODES[field_name],
                field_name=field_name,
                raw_value=str(raw_value),
                normalized_value=str(raw_value),
                unit=self.UNITS.get(field_name),
                source_path=str(path),
                confidence=90,
            )
            for field_name, raw_value in values.items()
            if raw_value not in (None, "", 0)
        ]

        return {
            "parser": "StaadParser",
            "source_path": str(path),
            "field_count": len(fields),
            "confidence": 90 if fields else 0,
            "fields": [field.__dict__ for field in fields],
        }

    def _preprocess_continuation(self, lines: list[str]) -> list[str]:
        new_lines = []
        current_line = ""
        for line in lines:
            if line.endswith("-"):
                current_line += line[:-1] + " "
            else:
                new_lines.append(current_line + line)
                current_line = ""
        if current_line:
            new_lines.append(current_line)
        return new_lines

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
            upper = line.upper().strip()
            if not line or upper.startswith("*"):
                continue
            
            # Section detection
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
            
            # End section if another major keyword starts
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
            "UNIT ",
        )
        return upper_line.startswith(section_prefixes)

    def _count_joints(self, lines: list[str]) -> int:
        count = 0
        for line in lines:
            # Split by ; for multiple coordinates on one line
            entries = line.split(";")
            for entry in entries:
                if re.search(r"^\d+\s+", entry.strip()):
                    count += 1
        return count

    def _count_members(self, lines: list[str]) -> int:
        count = 0
        for line in lines:
            entries = line.split(";")
            for entry in entries:
                if re.match(r"^\d+\s+\d+\s+\d+", entry.strip()):
                    count += 1
        return count

    def _expand_ids(self, id_string: str, stop_words: list[str] | None = None) -> set[int]:
        if stop_words is None:
            stop_words = ["TAPERED", "TABLE", "FIXED", "PINNED", "ENFORCED", "SPRING", "START", "END"]
            
        ids = set()
        tokens = id_string.split()
        
        filtered_tokens = []
        for token in tokens:
            if token.upper() in stop_words:
                break
            filtered_tokens.append(token)
            
        i = 0
        while i < len(filtered_tokens):
            token = filtered_tokens[i].upper()
            if token == "TO":
                if i > 0 and i + 1 < len(filtered_tokens):
                    try:
                        start = int(filtered_tokens[i-1])
                        end = int(filtered_tokens[i+1])
                        for val in range(start + 1, end + 1):
                            ids.add(val)
                        i += 2
                    except ValueError:
                        i += 1
                else:
                    i += 1
            else:
                try:
                    ids.add(int(filtered_tokens[i]))
                except ValueError:
                    pass
                i += 1
        return ids

    def _count_supports(self, lines: list[str]) -> int:
        all_node_ids = set()
        for line in lines:
            # We only care about the part before the support type
            ids = self._expand_ids(line)
            all_node_ids.update(ids)
        return len(all_node_ids)

    def _count_section_properties(self, lines: list[str]) -> int:
        all_member_ids = set()
        for line in lines:
            ids = self._expand_ids(line)
            all_member_ids.update(ids)
        return len(all_member_ids)

    def _count_load_cases(self, lines: list[str]) -> int:
        return sum(1 for line in lines if re.match(r"^LOAD\s+\d+", line.upper()))

    def _count_material_constants(self, lines: list[str]) -> int:
        return sum(1 for line in lines if re.match(r"^(E|POISSON|DENSITY|ALPHA)\s+", line.upper()))

    def _extract_unit_system(self, lines: list[str]) -> str | None:
        for line in lines:
            match = re.match(r"^UNIT\s+(.+)$", line.upper())
            if match:
                return match.group(1).strip()
        return None

    def _extract_job_info(self, lines: list[str]) -> dict[str, str]:
        info = {}
        in_job_info = False
        for line in lines:
            upper = line.upper()
            if "START JOB INFORMATION" in upper:
                in_job_info = True
                continue
            if "END JOB INFORMATION" in upper:
                in_job_info = False
                continue
            if in_job_info:
                if upper.startswith("ENGINEER DATE"):
                    parts = line.split()
                    if len(parts) >= 3:
                        info["date"] = parts[2]
                elif upper.startswith("ENGINEER"):
                    info["engineer"] = line[8:].strip()
                elif upper.startswith("DATE"):
                    info["date"] = line[4:].strip()
        return info

