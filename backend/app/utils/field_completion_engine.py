"""
Field Completion Engine — Phase 2 Hard-Stop Gate.

Iterates EVERY field in the master field dictionary (F-001 → F-196).
For each field it attempts, in order:
  1. Extracted  — already in the resolved conflict map
  2. Calculated — derived field calculator
  3. Fallback   — system defaults / fallback_rule_master
  4. Failed     — explicit log entry with reason and remediation guidance

Hard-stop invariant: Extracted + Calculated + Failed = total_fields.
No field is ever silently skipped.

Public API
----------
FieldCompletionEngine(resolved_map, db, project_id).run()
    → FieldCompletionReport
"""
from __future__ import annotations

import datetime
import sqlite3
from dataclasses import dataclass, field as dc_field
from uuid import UUID

from sqlalchemy.orm import Session

from app.utils.audit_logger import get_logger
from app.utils.derived_field_calculator import DerivedFieldCalculator, DerivedResult
from app.utils.master_db import (
    fetch_fallback_rules,
    master_db_path,
)

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Built-in system defaults (must match fallback.py _SYSTEM_DEFAULTS)
# ---------------------------------------------------------------------------
_SYSTEM_DEFAULTS: dict[str, str] = {
    "F-030": "AUTO",
    "F-082": "4.6",
    "F-102": "AUTO",
    "F-193": "50",
    "F-194": "StrongAxisParallelX",
    "F-009": "CLIENT",
    "F-013": "DrawingSet",
    "F-014": "AB-001",
    "F-015": "Anchor Bolt Drawing",
    "F-016": "DXF",
    "F-019": "AB-001",
    "F-021": "ab_drawing.dxf",
    "F-023": "SYSTEM",
    "F-025": "1",
    "F-026": "S1",
    "F-027": "ANCHOR BOLT LAYOUT",
    "F-031": "R0",
    "F-032": "<TODAY>",
    "F-033": "Issued for Approval",
    "F-034": "SYSTEM",
    "F-035": "PENDING",
    "F-036": "<TODAY>",
    "F-037": "IFC",
    "F-132": "Pending",
    "F-133": "PENDING",
    "F-134": "<TODAY>",
    "F-135": "Y",
    "F-136": "Pending",
    "F-137": "<NOW>",
    "F-138": "P2-03",
    "F-139": "AnDwg.in",
    "F-140": "Parser",
    "F-141": "85",
    "F-142": "1",
    "F-143": "Pending",
    "F-144": "COMPLETENESS_CHECK",
    "F-145": "N",
    "F-147": "S3",
    "F-148": "Pending",
    "F-149": "Pending",          # ab_gate_passed — set by workflow after AB generation
    "F-150": "Pending",          # ga_gate_passed — set by workflow after GA generation
    "F-151": "AB_STANDARD",
    "F-152": "STANDARD_TITLE_BLOCK",
    "F-156": "A3_BORDER",
    "F-170": "Bolted",           # connection_source_type — default to bolted
}

# ---------------------------------------------------------------------------
# Remediation guidance per missing source category
# ---------------------------------------------------------------------------
_REMEDIATION: dict[str, str] = {
    "P1": "Re-run extraction from MBS/STAAD/ETABS source files; verify file is complete",
    "P2": "Run derived-field calculation pass; check dependency fields are populated",
    "P3": "Select correct drawing template and title-block configuration",
    "P5": "Engineer manual input required via Review API",
    "P6": "Workflow system must populate this field (approval/QC step)",
    "System": "System auto-generated at rendering time; no manual action needed",
}


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class FieldOutcome:
    field_code: str
    standard_name: str
    mandatory_status: str
    output_classes: str
    status: str          # EXTRACTED | CALCULATED | FALLBACK | FAILED
    value: str | None
    source: str | None
    method: str | None   # resolution strategy or formula
    note: str
    remediation: str | None = None


@dataclass
class FieldCompletionReport:
    project_id: str
    total_fields: int
    extracted_count: int
    calculated_count: int
    fallback_count: int
    failed_count: int
    outcomes: list[FieldOutcome] = dc_field(default_factory=list)

    # Hard-stop invariant check
    @property
    def invariant_holds(self) -> bool:
        accounted = self.extracted_count + self.calculated_count + self.fallback_count + self.failed_count
        return accounted == self.total_fields

    def summary_table(self) -> dict:
        return {
            "Field Status": {
                "Extracted":  self.extracted_count,
                "Calculated": self.calculated_count,
                "Fallback":   self.fallback_count,
                "Failed":     self.failed_count,
                "Total":      self.total_fields,
            },
            "invariant_holds": self.invariant_holds,
            "hard_stop_satisfied": self.invariant_holds,
        }

    def failed_field_ids(self) -> list[str]:
        return [o.field_code for o in self.outcomes if o.status == "FAILED"]

    def to_dict(self) -> dict:
        return {
            "project_id": self.project_id,
            "summary": self.summary_table(),
            "hard_stop_rule": (
                "SATISFIED — all fields accounted for"
                if self.invariant_holds
                else f"VIOLATED — {self.total_fields} fields declared but only "
                     f"{self.extracted_count + self.calculated_count + self.fallback_count + self.failed_count} accounted"
            ),
            "failed_field_ids": self.failed_field_ids(),
            "outcomes": [
                {
                    "field_code": o.field_code,
                    "name": o.standard_name,
                    "mandatory": o.mandatory_status,
                    "output_classes": o.output_classes,
                    "status": o.status,
                    "value": o.value,
                    "source": o.source,
                    "method": o.method,
                    "note": o.note,
                    "remediation": o.remediation,
                }
                for o in self.outcomes
            ],
        }


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class FieldCompletionEngine:
    """
    Process every field in the master dictionary.
    Raises RuntimeError if the hard-stop invariant is violated after all fields
    are processed (should never happen, but enforced explicitly).
    """

    def __init__(
        self,
        resolved_map: dict,
        db: Session,
        project_id: UUID,
    ) -> None:
        self._resolved_map = resolved_map
        self._db = db
        self._project_id = project_id

    def run(self) -> FieldCompletionReport:
        all_fields = self._load_all_fields()
        fallback_rules = fetch_fallback_rules()

        # Pre-compute derived fields for all Derived-type entries
        derived_results: dict[str, DerivedResult] = {}
        if any(r[4] in ("calculated", "lookup", "auto-generated") for r in all_fields):
            calc = DerivedFieldCalculator(self._resolved_map, self._db, self._project_id)
            derived_results = calc.calculate_all()

        outcomes: list[FieldOutcome] = []
        extracted_count = 0
        calculated_count = 0
        fallback_count = 0
        failed_count = 0

        for (fc, name, mandatory, output_cls, derived_type, primary_src) in all_fields:
            outcome = self._process_field(
                fc, name, mandatory, output_cls, derived_type, primary_src,
                fallback_rules, derived_results,
            )
            outcomes.append(outcome)
            if outcome.status == "EXTRACTED":
                extracted_count += 1
            elif outcome.status == "CALCULATED":
                calculated_count += 1
            elif outcome.status == "FALLBACK":
                fallback_count += 1
            else:
                failed_count += 1

        report = FieldCompletionReport(
            project_id=str(self._project_id),
            total_fields=len(all_fields),
            extracted_count=extracted_count,
            calculated_count=calculated_count,
            fallback_count=fallback_count,
            failed_count=failed_count,
            outcomes=outcomes,
        )

        # Hard-stop invariant — must hold or pipeline is corrupt
        if not report.invariant_holds:
            raise RuntimeError(
                f"Hard-stop invariant violated: {len(all_fields)} fields declared but "
                f"{extracted_count + calculated_count + fallback_count + failed_count} accounted. "
                "This is a pipeline bug — investigate immediately."
            )

        logger.info(
            "Field completion: total=%d extracted=%d calculated=%d fallback=%d failed=%d",
            len(all_fields), extracted_count, calculated_count, fallback_count, failed_count,
        )
        return report

    # ------------------------------------------------------------------
    # Per-field resolution
    # ------------------------------------------------------------------

    def _process_field(
        self,
        fc: str,
        name: str,
        mandatory: str,
        output_cls: str,
        derived_type: str | None,
        primary_src: str | None,
        fallback_rules: dict,
        derived_results: dict[str, DerivedResult],
    ) -> FieldOutcome:

        # ── Step 1: Extracted from source files ──────────────────────────
        cr = self._resolved_map.get(fc)
        if cr and cr.winning_value:
            return FieldOutcome(
                field_code=fc, standard_name=name,
                mandatory_status=mandatory, output_classes=output_cls,
                status="EXTRACTED",
                value=cr.winning_value,
                source=cr.winning_source,
                method=f"source_priority/{cr.resolution_strategy}",
                note=f"Extracted from {cr.winning_source} (confidence={cr.confidence})",
            )

        # ── Step 2: Derived / calculated ─────────────────────────────────
        dr = derived_results.get(fc)
        if dr and dr.resolved and dr.value is not None:
            return FieldOutcome(
                field_code=fc, standard_name=name,
                mandatory_status=mandatory, output_classes=output_cls,
                status="CALCULATED",
                value=dr.value,
                source="DERIVED",
                method=dr.method or dr.note,
                note=dr.note,
            )

        # ── Step 3: System defaults / fallback ───────────────────────────
        fb_val = self._resolve_fallback(fc, fallback_rules)
        if fb_val is not None:
            return FieldOutcome(
                field_code=fc, standard_name=name,
                mandatory_status=mandatory, output_classes=output_cls,
                status="FALLBACK",
                value=fb_val,
                source="SYSTEM_DEFAULT",
                method="system_default",
                note="Applied built-in system default or fallback rule",
            )

        # ── Step 4: Failed — explicit log with remediation ───────────────
        remediation = _REMEDIATION.get(
            (primary_src or "").strip().split()[0] if primary_src else "",
            "Check source file availability and re-run extraction",
        )
        reason = self._failure_reason(fc, mandatory, derived_type, dr)
        return FieldOutcome(
            field_code=fc, standard_name=name,
            mandatory_status=mandatory, output_classes=output_cls,
            status="FAILED",
            value=None,
            source=None,
            method=None,
            note=reason,
            remediation=remediation,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _load_all_fields(self) -> list[tuple]:
        """Return all 196 fields from master DB, ordered by F-code."""
        with sqlite3.connect(master_db_path()) as conn:
            rows = conn.execute(
                """
                SELECT field_code, standard_field_name, mandatory_status,
                       output_classes, derived_type, primary_source
                FROM field_master
                ORDER BY field_code
                """
            ).fetchall()
        if not rows:
            raise RuntimeError("field_master is empty — master DB may be corrupt")
        return rows

    def _resolve_fallback(self, fc: str, rules: dict) -> str | None:
        """Try system defaults first, then fallback_rule_master DEFAULT_VALUE entries."""
        raw = _SYSTEM_DEFAULTS.get(fc)
        if raw is not None:
            if raw == "<TODAY>":
                return datetime.date.today().isoformat()
            if raw == "<NOW>":
                return datetime.datetime.now(datetime.timezone.utc).isoformat()
            return raw
        rule = rules.get(fc, {})
        if rule.get("fallback_strategy") == "DEFAULT_VALUE" and not rule.get("fallback_blocked"):
            return rule.get("default_value") or None
        return None

    @staticmethod
    def _failure_reason(
        fc: str,
        mandatory: str,
        derived_type: str | None,
        dr: DerivedResult | None,
    ) -> str:
        parts = [f"Field {fc} could not be resolved."]
        if mandatory == "Mandatory":
            parts.append("BLOCKING: this field is mandatory.")
        elif mandatory == "Conditional":
            parts.append("May be non-blocking if condition is not met for this project.")
        elif mandatory == "Optional":
            parts.append("Non-blocking: optional field.")
        elif mandatory == "Derived":
            parts.append("Derived field — dependency fields may be missing.")
        if derived_type:
            parts.append(f"Derived type: {derived_type}.")
        if dr and not dr.resolved:
            parts.append(f"Calculation failed: {dr.note}")
        parts.append("Missing source dependency. Engineer review required.")
        return " ".join(parts)


# ---------------------------------------------------------------------------
# Report generators (called by P2-02)
# ---------------------------------------------------------------------------

def build_missing_field_report(report: FieldCompletionReport) -> dict:
    failed = [o for o in report.outcomes if o.status == "FAILED"]
    mandatory_failed = [o for o in failed if o.mandatory_status == "Mandatory"]
    conditional_failed = [o for o in failed if o.mandatory_status == "Conditional"]
    optional_failed = [o for o in failed if o.mandatory_status in ("Optional", "Derived")]

    def _fmt(outcomes: list[FieldOutcome]) -> list[dict]:
        return [
            {
                "field_code": o.field_code,
                "name": o.standard_name,
                "output_classes": o.output_classes,
                "note": o.note,
                "remediation": o.remediation,
            }
            for o in outcomes
        ]

    return {
        "total_failed": len(failed),
        "mandatory_failed": len(mandatory_failed),
        "conditional_failed": len(conditional_failed),
        "optional_or_derived_failed": len(optional_failed),
        "mandatory_missing": _fmt(mandatory_failed),
        "conditional_missing": _fmt(conditional_failed),
        "optional_missing": _fmt(optional_failed),
    }


def build_fallback_invocation_log(report: FieldCompletionReport) -> dict:
    fallback_entries = [o for o in report.outcomes if o.status == "FALLBACK"]
    return {
        "total_fallback_applied": len(fallback_entries),
        "entries": [
            {
                "field_code": o.field_code,
                "name": o.standard_name,
                "value_applied": o.value,
                "source": o.source,
                "note": o.note,
            }
            for o in fallback_entries
        ],
    }


def build_extraction_readiness_report(report: FieldCompletionReport) -> dict:
    """Final readiness report — the authoritative pipeline exit document."""
    counts = report.summary_table()["Field Status"]
    failed_ids = report.failed_field_ids()
    mandatory_failed = [
        o for o in report.outcomes
        if o.status == "FAILED" and o.mandatory_status == "Mandatory"
    ]
    gate = "PASS" if not mandatory_failed else "BLOCKED"

    return {
        "project_id": report.project_id,
        "gate_status": gate,
        "hard_stop_rule": (
            "SATISFIED — all fields accounted for"
            if report.invariant_holds
            else f"VIOLATED — {report.total_fields} declared but only "
                 f"{counts['Extracted'] + counts['Calculated'] + counts['Fallback'] + counts['Failed']} accounted"
        ),
        "field_counts": counts,
        "mandatory_blockers": [
            {
                "field_code": o.field_code,
                "name": o.standard_name,
                "output_classes": o.output_classes,
                "remediation": o.remediation,
            }
            for o in mandatory_failed
        ],
        "failed_field_ids": failed_ids,
        "process_complete": (
            "YES — all F-001 through F-196 accounted for"
            if report.invariant_holds
            else "NO — invariant violated"
        ),
        "pipeline_verdict": (
            "PASS — no mandatory fields failed"
            if gate == "PASS"
            else f"BLOCKED — {len(mandatory_failed)} mandatory field(s) unresolved"
        ),
    }
