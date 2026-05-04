"""
Rule-based Field Validator — Phase 2 Step 20.

Loads validation_rule_master from master_db and evaluates each active rule
against the resolved field map for a project.  Returns a list of
ValidationItem-compatible dicts and an overall PASS / FAIL verdict.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field as dc_field

from app.utils.master_db import master_db_path
from app.utils.audit_logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class RuleResult:
    rule_id: str
    rule_name: str
    field_codes: list[str]
    severity: str           # Release-Blocker | Warning | Info
    blocking: bool
    passed: bool
    missing_fields: list[str] = dc_field(default_factory=list)
    note: str = ""


@dataclass
class ValidationReport:
    overall: str            # PASS | FAIL
    blocking_failures: int
    results: list[RuleResult] = dc_field(default_factory=list)

    def to_items(self) -> list[dict]:
        """Convert to ValidationItem-compatible dicts for CRUD persistence."""
        items: list[dict] = []
        for r in self.results:
            for fc in r.field_codes:
                items.append({
                    "field_code": fc,
                    "status": "PRESENT" if r.passed else "MISSING",
                    "severity": "CRITICAL" if r.blocking and not r.passed else "MINOR",
                    "source": "validation_rule_master",
                    "value": None,
                    "note": f"{r.rule_id}: {r.rule_name} — {r.note}",
                })
        return items


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------

class Validator:
    """
    Evaluate active validation rules against a project's resolved field map.

    Usage::

        v = Validator()
        report = v.validate_project(field_map, stage="P2-05")
    """

    def validate_project(
        self,
        field_map: dict[str, str],
        stage: str = "P2-05",
    ) -> ValidationReport:
        """
        field_map: {field_code: resolved_value}
        stage:     filter rules to those applicable at this stage.
        """
        rules = _load_rules(stage)
        results: list[RuleResult] = []

        for rule in rules:
            field_codes = [fc.strip() for fc in rule["applies_to"].split(",") if fc.strip()]
            missing = [fc for fc in field_codes if not field_map.get(fc)]
            passed = len(missing) == 0
            blocking = rule["blocking_flag"].lower() in ("yes", "true", "1")

            results.append(RuleResult(
                rule_id=rule["rule_id"],
                rule_name=rule["rule_name"],
                field_codes=field_codes,
                severity=rule["severity"],
                blocking=blocking,
                passed=passed,
                missing_fields=missing,
                note=f"{len(missing)} missing: {missing}" if missing else "All fields present",
            ))

        blocking_failures = sum(1 for r in results if not r.passed and r.blocking)
        return ValidationReport(
            overall="PASS" if blocking_failures == 0 else "FAIL",
            blocking_failures=blocking_failures,
            results=results,
        )

    # Legacy stub signature kept for backwards compatibility
    def validate(self, data: dict, rules: list) -> bool:
        if not data or not rules:
            return True
        report = self.validate_project(data)
        return report.overall == "PASS"


# ---------------------------------------------------------------------------
# Master DB helpers
# ---------------------------------------------------------------------------

def _load_rules(stage: str) -> list[dict]:
    """
    Load active validation rules from master_db.
    Returns rules applicable to the given stage (or all stages if no match).
    """
    try:
        with sqlite3.connect(master_db_path()) as conn:
            rows = conn.execute(
                """
                SELECT rule_id, rule_name, applies_to, severity,
                       blocking_flag, stage, description
                FROM   validation_rule_master
                WHERE  lower(status) = 'active'
                ORDER  BY rule_id
                """
            ).fetchall()
    except Exception as exc:
        logger.warning("Could not load validation rules: %s", exc)
        return []

    all_rules = [
        {
            "rule_id": r[0],
            "rule_name": r[1],
            "applies_to": r[2] or "",
            "severity": r[3] or "Warning",
            "blocking_flag": r[4] or "No",
            "stage": r[5] or "",
            "description": r[6] or "",
        }
        for r in rows
        if r[2]   # skip rules with no field mapping
    ]

    # Filter to current stage where specified; fall back to all
    stage_rules = [r for r in all_rules if not r["stage"] or stage in r["stage"]]
    return stage_rules if stage_rules else all_rules
