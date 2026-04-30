from enum import Enum

class FileType(str, Enum):
    STAAD = "STAAD"
    MBS = "MBS"
    ETABS = "ETABS"
    PROTASTEEL = "PROTASTEEL"
    DWG = "DWG"
    DXF = "DXF"
    PDF = "PDF"
    EXCEL = "EXCEL"
    ARCHIVE = "ARCHIVE"
    UNKNOWN = "UNKNOWN"

class StageCode(str, Enum):
    P2_01 = "P2-01"
    P2_02 = "P2-02"
    P2_03 = "P2-03"
    P2_04 = "P2-04"
    P2_05 = "P2-05"
    P3_01 = "P3-01"
    P3_02 = "P3-02"
    P3_03 = "P3-03"
    P3_04 = "P3-04"
    P3_05 = "P3-05"
