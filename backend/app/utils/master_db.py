from __future__ import annotations

import sqlite3
from pathlib import Path

from app.config.settings import settings


def master_db_path() -> Path:
    path = Path(settings.master_db_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def fetch_mandatory_field_codes() -> list[str]:
    with sqlite3.connect(master_db_path()) as connection:
        rows = connection.execute(
            """
            SELECT field_code
            FROM field_master
            WHERE lower(coalesce(mandatory_status, '')) = 'mandatory'
            ORDER BY field_code
            """
        ).fetchall()
    return [row[0] for row in rows]


# ---------------------------------------------------------------------------
# Source priority helpers (Step 14)
# ---------------------------------------------------------------------------

# Hardcoded fallback when master_db lookup returns nothing.
_DEFAULT_SOURCE_PRIORITY: dict[str, int] = {
    "MBS": 1,
    "STAAD": 2,
    "ETABS": 3,
    "PROTASTEEL": 4,
    "DXF": 5,
    "PDF": 6,
    "UNKNOWN": 99,
}


def fetch_source_category_priorities() -> dict[str, int]:
    """
    Returns {source_system_name: priority_rank} derived from
    source_priority_master categories.  Falls back to hardcoded defaults
    if the table is empty or inaccessible.
    """
    try:
        with sqlite3.connect(master_db_path()) as conn:
            rows = conn.execute(
                "SELECT category, priority FROM source_priority_master ORDER BY priority"
            ).fetchall()
        if rows:
            mapping: dict[str, int] = {}
            for category, prio in rows:
                # Category names contain the software names in applicable_parsers.
                # We map known tokens directly.
                for token in ("MBS", "STAAD", "ETABS", "PROTA", "DXF", "PDF"):
                    if token.upper() in (category or "").upper():
                        mapping.setdefault(token if token != "PROTA" else "PROTASTEEL", prio)
            if mapping:
                return mapping
    except Exception:
        pass
    return _DEFAULT_SOURCE_PRIORITY.copy()


def fetch_conflict_rules() -> dict[str, dict]:
    """
    Returns {field_code: {resolution_method, approval_required, escalation_path}}
    from conflict_rule_master.
    """
    try:
        with sqlite3.connect(master_db_path()) as conn:
            rows = conn.execute(
                "SELECT field_code, resolution_method, approval_required, escalation_path "
                "FROM conflict_rule_master"
            ).fetchall()
        return {
            row[0]: {
                "resolution_method": row[1],
                "approval_required": bool(row[2]),
                "escalation_path": row[3],
            }
            for row in rows
        }
    except Exception:
        return {}


def fetch_fallback_rules() -> dict[str, dict]:
    """
    Returns {field_code: {fallback_strategy, fallback_blocked, escalation_trigger}}
    from fallback_rule_master (one row per field_code, lowest priority wins).
    """
    try:
        with sqlite3.connect(master_db_path()) as conn:
            rows = conn.execute(
                "SELECT field_code, fallback_source_category, fallback_blocked_flag, "
                "       escalation_trigger "
                "FROM fallback_rule_master "
                "ORDER BY fallback_priority"
            ).fetchall()
        result: dict[str, dict] = {}
        for row in rows:
            result.setdefault(
                row[0],
                {
                    "fallback_strategy": row[1],
                    "fallback_blocked": bool(row[2]),
                    "escalation_trigger": row[3],
                },
            )
        return result
    except Exception:
        return {}


def fetch_source_fallback_chain(field_code: str) -> list[str]:
    """
    Returns ordered list of source_system names to try for a given field_code.
    Falls back to a hardcoded chain if no rows are found.
    """
    try:
        with sqlite3.connect(master_db_path()) as conn:
            rows = conn.execute(
                "SELECT source_system FROM source_fallback_chain "
                "WHERE field_code = ? AND fallback_blocked_flag = 0 "
                "ORDER BY fallback_order",
                (field_code,),
            ).fetchall()
        if rows:
            return [r[0] for r in rows]
    except Exception:
        pass
    return ["MBS", "STAAD", "ETABS", "PROTASTEEL", "PDF"]


def fetch_ab_required_field_codes() -> list[str]:
    """
    Returns mandatory field codes needed for AB generation.
    Includes fields whose output_classes is 'All' or contains 'AB'.
    """
    with sqlite3.connect(master_db_path()) as conn:
        rows = conn.execute(
            """
            SELECT field_code
            FROM field_master
            WHERE lower(coalesce(mandatory_status, '')) = 'mandatory'
              AND (
                output_classes = 'All'
                OR output_classes LIKE '%AB%'
              )
            ORDER BY field_code
            """
        ).fetchall()
    return [row[0] for row in rows]


def fetch_ga_required_field_codes() -> list[str]:
    """
    Returns mandatory field codes needed for GA generation.
    Includes fields whose output_classes is 'All' or contains 'GA'.
    """
    with sqlite3.connect(master_db_path()) as conn:
        rows = conn.execute(
            """
            SELECT field_code
            FROM field_master
            WHERE lower(coalesce(mandatory_status, '')) = 'mandatory'
              AND (
                output_classes = 'All'
                OR output_classes LIKE '%GA%'
              )
            ORDER BY field_code
            """
        ).fetchall()
    return [row[0] for row in rows]


def fetch_field_confidence_by_source(field_code: str) -> dict[str, float]:
    """
    Returns {software: confidence_level} from software_source_mapping_matrix
    for a specific field_code.  Used to break ties within same priority category.
    """
    try:
        with sqlite3.connect(master_db_path()) as conn:
            rows = conn.execute(
                "SELECT software, confidence_level FROM software_source_mapping_matrix "
                "WHERE normalized_field_id = ?",
                (field_code,),
            ).fetchall()
        return {r[0]: float(r[1]) for r in rows if r[1] is not None}
    except Exception:
        return {}
