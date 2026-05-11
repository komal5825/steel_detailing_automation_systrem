"""
Fallback Policy Agent — Phase 2 Step 15.

For each missing mandatory field the FallbackManager consults:
  1. source_fallback_chain  — look for the field in other already-extracted sources
  2. fallback_rule_master   — strategy: DEFAULT_VALUE | HUMAN_INPUT | SKIP
  3. _SYSTEM_DEFAULTS       — built-in sensible defaults for well-known fields
                              (used when DB has no rule or rule carries no value)

Returns a FallbackReport with per-field outcomes and a list of fields
that still require human input after fallback is exhausted.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass, field as dc_field
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import ExtractedFieldValue
from app.utils.master_db import fetch_fallback_rules, fetch_source_fallback_chain
from app.utils.audit_logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Built-in system defaults
# ---------------------------------------------------------------------------
# These cover fields that either have a well-known standard value, can be
# derived from context, or need a placeholder to allow the pipeline to
# proceed.  Engineers can override any of these via the review workflow.
#
# Date-valued fields use the sentinel "<TODAY>" which is resolved at runtime.
# ---------------------------------------------------------------------------
_SYSTEM_DEFAULTS: dict[str, str] = {
    # ── Technical / derivable ─────────────────────────────────────────────
    "F-082": "4.6",                    # standard IS-1367 anchor bolt grade
    # F-192 intentionally omitted: it is derived in P2-03 as F-087 + F-193.
    # Providing an empty-string default here caused it to appear as PRESENT
    # in validation results while carrying no real value.
    "F-193": "50",                     # 50 mm standard non-shrink grout pad
    "F-194": "StrongAxisParallelX",    # default column orientation
    # ── Document metadata placeholders ───────────────────────────────────
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
    # ── QC / audit / validation (pipeline-generated placeholders) ─────────
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
    "F-151": "AB_STANDARD",
    "F-152": "STANDARD_TITLE_BLOCK",
    "F-156": "A3_BORDER",
}

_DATE_FIELDS = {"F-032", "F-036", "F-134"}
_DATETIME_FIELDS = {"F-137"}


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class FallbackOutcome:
    field_code: str
    strategy: str               # DEFAULT_VALUE | HUMAN_INPUT | SKIP | RESOLVED_FROM_CHAIN
    resolved: bool              # True if a value was found
    resolved_value: str | None = None
    resolved_source: str | None = None
    requires_human: bool = False
    note: str | None = None


@dataclass
class FallbackReport:
    project_id: str
    applied: list[FallbackOutcome] = dc_field(default_factory=list)
    unresolved_human_fields: list[str] = dc_field(default_factory=list)
    unresolved_skip_fields: list[str] = dc_field(default_factory=list)

    @property
    def all_resolved(self) -> bool:
        return len(self.unresolved_human_fields) == 0

    def summary(self) -> dict:
        return {
            "project_id": self.project_id,
            "applied_count": len(self.applied),
            "resolved_count": sum(1 for o in self.applied if o.resolved),
            "human_input_required": self.unresolved_human_fields,
            "skipped_fields": self.unresolved_skip_fields,
            "all_resolved": self.all_resolved,
        }


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------

class FallbackManager:
    """
    Apply fallback strategies for missing mandatory fields.

    Usage::

        mgr = FallbackManager()
        report = mgr.apply_fallbacks(
            project_id=uuid_obj,
            missing_codes=["F-002", "F-050"],
            db=session,
        )
    """

    def apply_fallbacks(
        self,
        project_id: UUID,
        missing_codes: list[str],
        db: Session,
    ) -> FallbackReport:
        """
        For each missing field_code attempt:
        1. source_fallback_chain — look for the field in alternative sources
           already extracted for this project.
        2. fallback_rule_master  — apply strategy (DEFAULT_VALUE / HUMAN_INPUT / SKIP).
        """
        rules = fetch_fallback_rules()
        report = FallbackReport(project_id=str(project_id))

        for fc in missing_codes:
            outcome = self._apply_one(fc, project_id, rules, db)
            report.applied.append(outcome)

            if not outcome.resolved:
                if outcome.strategy == "SKIP":
                    report.unresolved_skip_fields.append(fc)
                else:
                    report.unresolved_human_fields.append(fc)

        return report

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _apply_one(
        self,
        field_code: str,
        project_id: UUID,
        rules: dict,
        db: Session,
    ) -> FallbackOutcome:
        # Step 1 — try alternative sources from the chain
        chain = fetch_source_fallback_chain(field_code)
        chain_result = self._try_chain(field_code, project_id, chain, db)
        if chain_result:
            return FallbackOutcome(
                field_code=field_code,
                strategy="RESOLVED_FROM_CHAIN",
                resolved=True,
                resolved_value=chain_result["value"],
                resolved_source=chain_result["source"],
                note=f"Found in fallback source {chain_result['source']}",
            )

        # Step 2 — consult fallback_rule_master
        rule = rules.get(field_code, {})
        strategy = rule.get("fallback_strategy", "HUMAN_INPUT")
        blocked = rule.get("fallback_blocked", False)

        if strategy == "DEFAULT_VALUE" and not blocked:
            # DB rule says DEFAULT_VALUE — resolve via system defaults
            default_val = self._resolve_default(field_code)
            if default_val is not None:
                logger.info("Applying default value for %s: %r", field_code, default_val)
                return FallbackOutcome(
                    field_code=field_code,
                    strategy="DEFAULT_VALUE",
                    resolved=True,
                    resolved_value=default_val,
                    resolved_source="SYSTEM_DEFAULT",
                    note="Default value applied from fallback_rule_master",
                )

        if strategy == "SKIP":
            return FallbackOutcome(
                field_code=field_code,
                strategy="SKIP",
                resolved=False,
                note="Field skipped — non-mandatory in current context",
            )

        # Step 3 — no DB rule or HUMAN_INPUT strategy: try _SYSTEM_DEFAULTS
        sys_val = self._resolve_default(field_code)
        if sys_val is not None:
            logger.info("Applying system default for %s: %r", field_code, sys_val)
            return FallbackOutcome(
                field_code=field_code,
                strategy="DEFAULT_VALUE",
                resolved=True,
                resolved_value=sys_val,
                resolved_source="SYSTEM_DEFAULT",
                note="Default value applied from built-in system defaults",
            )

        # HUMAN_INPUT — no default available
        return FallbackOutcome(
            field_code=field_code,
            strategy="HUMAN_INPUT",
            resolved=False,
            requires_human=True,
            note=f"Engineer must supply {field_code} — no automated fallback available",
        )

    @staticmethod
    def _try_chain(
        field_code: str,
        project_id: UUID,
        chain: list[str],
        db: Session,
    ) -> dict | None:
        """
        Look for an already-extracted value for *field_code* from any source
        in the fallback chain, in priority order.
        """
        rows: list[ExtractedFieldValue] = (
            db.query(ExtractedFieldValue)
            .filter(
                ExtractedFieldValue.project_id == project_id,
                ExtractedFieldValue.field_code == field_code,
            )
            .all()
        )
        if not rows:
            return None

        # Build a quick lookup: source_token → row
        source_map: dict[str, ExtractedFieldValue] = {}
        for row in rows:
            path_upper = (row.source_path or "").upper()
            for token in ("MBS", "STAAD", "ETABS", "PROTASTEEL", "PDF"):
                if token in path_upper:
                    source_map.setdefault(token, row)

        for source in chain:
            row = source_map.get(source.upper())
            if row:
                return {"value": row.normalized_value, "source": source}

        return None

    @staticmethod
    def _resolve_default(field_code: str) -> str | None:
        """
        Return the system default value for *field_code*, or None if not known.

        Special sentinels:
          <TODAY>  →  today's date as YYYY-MM-DD
          <NOW>    →  current UTC timestamp as ISO-8601
          ""       →  empty string (field is derivable downstream; treated as resolved)
        """
        if field_code not in _SYSTEM_DEFAULTS:
            return None
        raw = _SYSTEM_DEFAULTS[field_code]
        if raw == "<TODAY>":
            return datetime.date.today().isoformat()
        if raw == "<NOW>":
            return datetime.datetime.now(datetime.timezone.utc).isoformat()
        return raw  # may be "" for compute-later fields — still counts as resolved

    # Legacy stub signature — kept for backwards compatibility
    def execute_fallback(self, error: Exception) -> None:
        logger.warning("Legacy execute_fallback called: %s", error)
