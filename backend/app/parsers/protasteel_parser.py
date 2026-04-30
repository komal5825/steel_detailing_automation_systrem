from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import ezdxf


@dataclass(frozen=True)
class ParsedField:
    field_code: str
    field_name: str
    raw_value: str
    normalized_value: str
    unit: str | None
    source_path: str
    confidence: int


class ProtaSteelParser:
    """Extract geometry-oriented summary fields from Prota/CAD DXF exports."""

    FIELD_CODES = {
        "dxf_entity_count": "PROTA-DXF-ENTITY-COUNT",
        "dxf_layer_count": "PROTA-DXF-LAYER-COUNT",
        "dxf_layers": "PROTA-DXF-LAYERS",
        "line_count": "PROTA-DXF-LINE-COUNT",
        "polyline_count": "PROTA-DXF-POLYLINE-COUNT",
        "dimension_count": "PROTA-DXF-DIMENSION-COUNT",
        "text_count": "PROTA-DXF-TEXT-COUNT",
    }

    def parse(self, file_path: str) -> dict:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(file_path)
        if path.suffix.lower() != ".dxf":
            raise ValueError("ProtaSteel parser currently expects DXF input")

        document = ezdxf.readfile(path)
        modelspace = document.modelspace()
        entities = list(modelspace)
        types = Counter(entity.dxftype() for entity in entities)
        layer_names = sorted({entity.dxf.layer for entity in entities if hasattr(entity.dxf, "layer")})

        fields = [
            self._field("dxf_entity_count", len(entities), str(path), "count", 90),
            self._field("dxf_layer_count", len(layer_names), str(path), "count", 90),
            self._field("dxf_layers", ", ".join(layer_names), str(path), None, 85),
            self._field("line_count", types.get("LINE", 0), str(path), "count", 85),
            self._field("polyline_count", types.get("LWPOLYLINE", 0) + types.get("POLYLINE", 0), str(path), "count", 85),
            self._field("dimension_count", types.get("DIMENSION", 0), str(path), "count", 85),
            self._field("text_count", types.get("TEXT", 0) + types.get("MTEXT", 0), str(path), "count", 85),
        ]

        fields = [field for field in fields if field.raw_value not in ("0", "")]
        return {
            "parser": "ProtaSteelParser",
            "source_path": str(path),
            "field_count": len(fields),
            "confidence": 85 if fields else 0,
            "fields": [field.__dict__ for field in fields],
        }

    def _field(self, field_name: str, value: object, source_path: str, unit: str | None, confidence: int) -> ParsedField:
        return ParsedField(
            field_code=self.FIELD_CODES[field_name],
            field_name=field_name,
            raw_value=str(value),
            normalized_value=str(value),
            unit=unit,
            source_path=source_path,
            confidence=confidence,
        )
