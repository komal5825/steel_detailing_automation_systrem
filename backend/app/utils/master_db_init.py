"""
Phase 2 governance seed for master_db.db.

The schema for all four governance tables already exists (created during
Phase 1 DB consolidation).  This module only seeds missing rows —
INSERT OR IGNORE so it is fully idempotent.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from app.utils.master_db import master_db_path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# conflict_rule_master seed
# Schema: conflict_rule_id, field_code, source_pair, resolution_method,
#         approval_required, escalation_path, created_at
# ---------------------------------------------------------------------------

_CONFLICT_RULES = [
    ("CR-001", "F-001", "MBS|STAAD",    "HIGHEST_CONFIDENCE", 0, "P2-LEAD",   _now()),
    ("CR-002", "F-002", "MBS|ETABS",    "HIGHEST_CONFIDENCE", 0, "P2-LEAD",   _now()),
    ("CR-003", "F-003", "MBS|STAAD",    "HIGHEST_CONFIDENCE", 0, "P2-LEAD",   _now()),
    ("CR-004", "F-010", "MBS|STAAD",    "HUMAN_REVIEW",       1, "ENGINEER",  _now()),
    ("CR-005", "F-020", "MBS|PDF",      "HUMAN_REVIEW",       1, "ENGINEER",  _now()),
    ("CR-006", "F-039", "MBS|STAAD",    "HIGHEST_CONFIDENCE", 0, "P2-LEAD",   _now()),
    ("CR-007", "F-040", "MBS|STAAD",    "HIGHEST_CONFIDENCE", 0, "P2-LEAD",   _now()),
    ("CR-008", "F-081", "MBS|PDF",      "HUMAN_REVIEW",       1, "ENGINEER",  _now()),
    ("CR-009", "F-082", "MBS|PDF",      "HUMAN_REVIEW",       1, "ENGINEER",  _now()),
    ("CR-010", "F-050", "STAAD|PDF",    "HIGHEST_CONFIDENCE", 0, "P2-LEAD",   _now()),
]

# ---------------------------------------------------------------------------
# fallback_rule_master seed
# Schema: fallback_rule_id, source_map_id, field_code, fallback_priority,
#         fallback_source_category, fallback_condition, fallback_blocked_flag,
#         escalation_trigger, created_at
# ---------------------------------------------------------------------------

_FALLBACK_RULES = [
    ("FR-001", None, "F-001", 1, "HUMAN_INPUT",  "mandatory_missing", 1, "ENGINEER",  _now()),
    ("FR-002", None, "F-002", 2, "DEFAULT_VALUE", "missing_non_critical", 0, None,     _now()),
    ("FR-003", None, "F-003", 1, "HUMAN_INPUT",  "mandatory_missing", 1, "ENGINEER",  _now()),
    ("FR-004", None, "F-010", 1, "HUMAN_INPUT",  "mandatory_missing", 1, "ENGINEER",  _now()),
    ("FR-005", None, "F-020", 2, "DEFAULT_VALUE", "missing_non_critical", 0, None,     _now()),
    ("FR-006", None, "F-039", 1, "HUMAN_INPUT",  "mandatory_missing", 1, "ENGINEER",  _now()),
    ("FR-007", None, "F-040", 1, "HUMAN_INPUT",  "mandatory_missing", 1, "ENGINEER",  _now()),
    ("FR-008", None, "F-050", 2, "DEFAULT_VALUE", "missing_non_critical", 0, None,     _now()),
    ("FR-009", None, "F-081", 1, "HUMAN_INPUT",  "mandatory_missing", 1, "ENGINEER",  _now()),
    ("FR-010", None, "F-082", 1, "HUMAN_INPUT",  "mandatory_missing", 1, "ENGINEER",  _now()),
]

# ---------------------------------------------------------------------------
# source_fallback_chain seed
# Schema: chain_id, field_code, fallback_order, source_system,
#         fallback_condition, fallback_blocked_flag, escalation_trigger,
#         created_at
# field_code is NOT NULL — seed chains for the key mandatory structural fields.
# ---------------------------------------------------------------------------

_MANDATORY_FIELD_CODES_FOR_CHAIN = [
    "F-001", "F-002", "F-003", "F-010", "F-020",
    "F-039", "F-040", "F-050", "F-081", "F-082",
]

# Default ordered chain: MBS → STAAD → ETABS → PROTASTEEL → PDF
_DEFAULT_CHAIN = [
    (1, "MBS",         "primary_missing", 0, None),
    (2, "STAAD",       "primary_missing", 0, None),
    (3, "ETABS",       "primary_missing", 0, None),
    (4, "PROTASTEEL",  "primary_missing", 0, None),
    (5, "PDF",         "primary_missing", 0, "P2-LEAD"),
]


def _build_fallback_chain_rows() -> list[tuple]:
    rows = []
    seq = 1
    for fc in _MANDATORY_FIELD_CODES_FOR_CHAIN:
        for order, source, cond, blocked, trigger in _DEFAULT_CHAIN:
            chain_id = f"SFC-{seq:04d}"
            rows.append((chain_id, fc, order, source, cond, blocked, trigger, _now()))
            seq += 1
    return rows


_FALLBACK_CHAIN = _build_fallback_chain_rows()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def init_governance_tables() -> None:
    """Seed governance tables in master_db.db.  Idempotent via INSERT OR IGNORE."""
    db_path = master_db_path()
    with sqlite3.connect(db_path) as conn:
        conn.executemany(
            "INSERT OR IGNORE INTO conflict_rule_master "
            "(conflict_rule_id, field_code, source_pair, resolution_method, "
            " approval_required, escalation_path, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            _CONFLICT_RULES,
        )
        conn.executemany(
            "INSERT OR IGNORE INTO fallback_rule_master "
            "(fallback_rule_id, source_map_id, field_code, fallback_priority, "
            " fallback_source_category, fallback_condition, fallback_blocked_flag, "
            " escalation_trigger, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            _FALLBACK_RULES,
        )
        conn.executemany(
            "INSERT OR IGNORE INTO source_fallback_chain "
            "(chain_id, field_code, fallback_order, source_system, "
            " fallback_condition, fallback_blocked_flag, escalation_trigger, created_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            _FALLBACK_CHAIN,
        )
        conn.commit()
