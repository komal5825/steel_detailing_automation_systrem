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


class InParser:
    """Robust parser for MBS .in files with sectioned *(n) structure."""

    def parse(self, file_path: str) -> dict:
        """Parses MBS .in files which have a sectioned structure *(n) or line-based."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(file_path)
            
        content = path.read_text(encoding="utf-8", errors="ignore")
        
        sections = {}
        section_pattern = re.compile(r"^\*\(\s*(\d+)\)(.*?):?\s*$")
        data_pattern = r"'([^']*)'|(\S+)"
        
        lines = content.splitlines()
        current_section_num = None
        
        has_sections = any(section_pattern.match(line.strip()) for line in lines)
        
        if not has_sections:
            # Fallback for files like MBS.IN with no sections
            fields = []
            for idx, line in enumerate(lines):
                stripped = line.strip()
                if stripped:
                    fields.append(ParsedField(
                        field_code=f"MBS-LINE-{idx+1}",
                        field_name=f"Line {idx+1}",
                        raw_value=stripped,
                        normalized_value=stripped,
                        unit=None,
                        source_path=str(path),
                        confidence=70
                    ))
            return {
                "parser": "InParser-LineBased",
                "source_path": str(path),
                "field_count": len(fields),
                "confidence": 70 if fields else 0,
                "fields": [field.__dict__ for field in fields],
            }

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
                
            section_match = section_pattern.match(stripped)
            if section_match:
                current_section_num = section_match.group(1)
                current_section_name = section_match.group(2).strip()
                sections[current_section_num] = {
                    "name": current_section_name,
                    "data": []
                }
                continue
            
            if current_section_num and not stripped.startswith("*"):
                # Data line
                matches = re.findall(data_pattern, line)
                fields = [m[0] if m[0] else m[1] for m in matches]
                if fields:
                    sections[current_section_num]["data"].append(fields)

        # Flatten into ParsedField format for compatibility
        all_fields = []
        for sec_num, sec_info in sections.items():
            sec_name = sec_info["name"]
            for idx, row in enumerate(sec_info["data"]):
                raw_val = " | ".join(row)
                all_fields.append(ParsedField(
                    field_code=f"MBS-SEC-{sec_num}-{idx}",
                    field_name=f"{sec_name} Row {idx+1}",
                    raw_value=raw_val,
                    normalized_value=raw_val,
                    unit=None,
                    source_path=str(path),
                    confidence=85
                ))

        return {
            "parser": "InParser",
            "source_path": str(path),
            "field_count": len(all_fields),
            "confidence": 85 if all_fields else 0,
            "sections": sections,
            "fields": [field.__dict__ for field in all_fields],
        }
