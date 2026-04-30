from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import fitz
import pdfplumber
import pytesseract
from PIL import Image

from app.config.settings import settings


@dataclass(frozen=True)
class ParsedField:
    field_code: str
    field_name: str
    raw_value: str
    normalized_value: str
    unit: str | None
    source_path: str
    confidence: int


class PDFParser:
    """Extract text and page-level signals from text or scanned PDFs."""

    FIELD_CODES = {
        "page_count": "PDF-PAGE-COUNT",
        "text_character_count": "PDF-TEXT-CHARACTER-COUNT",
        "extraction_mode": "PDF-EXTRACTION-MODE",
        "text_preview": "PDF-TEXT-PREVIEW",
    }

    def parse(self, file_path: str) -> dict:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(file_path)
        if path.suffix.lower() != ".pdf":
            raise ValueError("PDF parser expects a PDF file")

        page_count, text = self._extract_text_pdf(path)
        extraction_mode = "text"
        confidence = 80

        if not text.strip():
            text = self._extract_scanned_pdf(path)
            extraction_mode = "ocr"
            confidence = 65 if text.strip() else 0

        fields = [
            self._field("page_count", page_count, str(path), "count", 90),
            self._field("text_character_count", len(text), str(path), "count", confidence),
            self._field("extraction_mode", extraction_mode, str(path), None, confidence),
            self._field("text_preview", self._preview(text), str(path), None, confidence),
        ]
        fields = [field for field in fields if field.raw_value not in ("", "0")]

        return {
            "parser": "PDFParser",
            "source_path": str(path),
            "field_count": len(fields),
            "confidence": confidence if fields else 0,
            "fields": [field.__dict__ for field in fields],
        }

    def _extract_text_pdf(self, path: Path) -> tuple[int, str]:
        page_texts = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                page_texts.append(page.extract_text() or "")
            return len(pdf.pages), "\n".join(page_texts)

    def _extract_scanned_pdf(self, path: Path) -> str:
        if settings.tesseract_path:
            pytesseract.pytesseract.tesseract_cmd = settings.tesseract_path

        document = fitz.open(path)
        page_texts = []
        try:
            for page in document:
                pixmap = page.get_pixmap(dpi=200)
                image = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
                page_texts.append(pytesseract.image_to_string(image))
        finally:
            document.close()
        return "\n".join(page_texts)

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

    def _preview(self, text: str) -> str:
        return " ".join(text.split())[:500]
