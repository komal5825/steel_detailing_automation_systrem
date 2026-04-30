import os
from dataclasses import dataclass
from app.config.constants import FileType


@dataclass(frozen=True)
class FileClassification:
    file_type: FileType
    file_category: str
    source_application: str
    likely_role: str
    confidence: int


class SourceClassifier:
    EXTENSION_MAP = {
        '.std': FileType.STAAD,
        '.mbs': FileType.MBS,
        '.xml': FileType.MBS,  # MBS also uses XML
        '.edb': FileType.ETABS,
        '.dwg': FileType.DWG,
        '.dxf': FileType.DXF,
        '.pdf': FileType.PDF,
        '.xlsx': FileType.EXCEL,
        '.xls': FileType.EXCEL,
        '.zip': FileType.ARCHIVE,
        '.rar': FileType.ARCHIVE,
        '.7z': FileType.ARCHIVE
    }

    @classmethod
    def classify(cls, file_path: str) -> FileType:
        _, ext = os.path.splitext(file_path.lower())
        return cls.EXTENSION_MAP.get(ext, FileType.UNKNOWN)

    @classmethod
    def classify_details(cls, file_path: str) -> FileClassification:
        file_type = cls.classify(file_path)
        filename = os.path.basename(file_path).lower()

        if file_type == FileType.ARCHIVE:
            category = "archive"
        elif cls.is_design_file(file_type):
            category = "design_file"
        elif cls.is_drawing_file(file_type):
            category = "drawing"
        elif file_type == FileType.EXCEL:
            category = "spreadsheet"
        else:
            category = "unsupported"

        source_application = {
            FileType.STAAD: "STAAD",
            FileType.MBS: "MBS",
            FileType.ETABS: "ETABS",
            FileType.PROTASTEEL: "PROTASTEEL",
            FileType.DWG: "CAD",
            FileType.DXF: "CAD",
            FileType.PDF: "PDF",
            FileType.EXCEL: "EXCEL",
            FileType.ARCHIVE: "ARCHIVE",
        }.get(file_type, "UNKNOWN")

        likely_role = "supporting"
        if file_type in [FileType.STAAD, FileType.MBS, FileType.ETABS]:
            likely_role = "governing"
        elif "template" in filename or "title" in filename:
            likely_role = "template"
        elif file_type == FileType.UNKNOWN:
            likely_role = "irrelevant"

        confidence = 90 if file_type != FileType.UNKNOWN else 0
        return FileClassification(
            file_type=file_type,
            file_category=category,
            source_application=source_application,
            likely_role=likely_role,
            confidence=confidence,
        )

    @classmethod
    def is_design_file(cls, file_type: FileType) -> bool:
        return file_type in [FileType.STAAD, FileType.MBS, FileType.ETABS, FileType.PROTASTEEL]

    @classmethod
    def is_drawing_file(cls, file_type: FileType) -> bool:
        return file_type in [FileType.DWG, FileType.DXF, FileType.PDF]
