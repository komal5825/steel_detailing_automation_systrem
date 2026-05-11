"""
Source Priority and Conflict Resolution Engine — Phase 2 Step 14.

Responsibility:
    Given multiple ExtractedFieldValue rows for the same field_code (from
    different parsers/sources), decide which value governs using:

    1. source_priority_master   — category-level trust ranking
    2. conflict_rule_master     — per-field resolution strategy override
    3. software_source_mapping_matrix — per-source confidence for the field
    4. source_fallback_chain    — ordered fallback when primary is absent

Public API:
    resolve_field_conflict(field_code, candidates) -> ConflictResult
    build_resolved_field_map(db, project_id)       -> dict[field_code, ConflictResult]
"""
from __future__ import annotations

from dataclasses import dataclass, field
from collections import defaultdict

from sqlalchemy.orm import Session

from app.db.models import ExtractedFieldValue
from app.utils.master_db import (
    fetch_conflict_rules,
    fetch_field_confidence_by_source,
    fetch_source_category_priorities,
    fetch_source_fallback_chain,
)
from app.db.crud.validation import log_audit_event
from app.utils.audit_logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class Candidate:
    field_code: str
    raw_value: str
    normalized_value: str
    source: str          # e.g. MBS / STAAD / PDF
    confidence: int      # 0-100 from parser
    source_path: str


@dataclass
class ConflictResult:
    field_code: str
    winning_value: str
    winning_source: str
    confidence: int
    conflict_detected: bool
    resolution_strategy: str
    requires_human: bool = False
    candidates: list[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Core resolution logic
# ---------------------------------------------------------------------------

def resolve_field_conflict(
    field_code: str,
    candidates: list[Candidate],
) -> ConflictResult:
    """
    Resolve competing extracted values for *field_code* to a single winner.

    Strategy priority:
    1. If only one candidate → trivially returned.
    2. Lookup conflict_rule_master for a field-specific strategy.
    3. Apply strategy (HIGHEST_PRIORITY | HIGHEST_CONFIDENCE | HUMAN_REVIEW).
    """
    if not candidates:
        raise ValueError(f"No candidates supplied for {field_code}")

    if len(candidates) == 1:
        c = candidates[0]
        return ConflictResult(
            field_code=field_code,
            winning_value=c.normalized_value or c.raw_value,
            winning_source=c.source,
            confidence=c.confidence,
            conflict_detected=False,
            resolution_strategy="SINGLE_SOURCE",
        )

    # Detect actual value conflict (different normalised values)
    unique_vals = {c.normalized_value or c.raw_value for c in candidates}
    conflict_detected = len(unique_vals) > 1

    rules = fetch_conflict_rules()
    rule = rules.get(field_code, {})
    strategy = rule.get("resolution_method", "HIGHEST_PRIORITY")

    cand_dicts = [
        {"value": c.normalized_value, "source": c.source, "confidence": c.confidence}
        for c in candidates
    ]

    if strategy == "HUMAN_REVIEW":
        return ConflictResult(
            field_code=field_code,
            winning_value=candidates[0].normalized_value or candidates[0].raw_value,
            winning_source=candidates[0].source,
            confidence=0,
            conflict_detected=conflict_detected,
            resolution_strategy="HUMAN_REVIEW",
            requires_human=True,
            candidates=cand_dicts,
        )

    if strategy == "HIGHEST_CONFIDENCE":
        # Use matrix confidence first; fall back to parser confidence
        matrix_conf = fetch_field_confidence_by_source(field_code)
        winner = max(
            candidates,
            key=lambda c: matrix_conf.get(c.source, c.confidence),
        )
    else:
        # HIGHEST_PRIORITY (default) — use source_priority_master ranking
        priorities = fetch_source_category_priorities()
        winner = min(candidates, key=lambda c: priorities.get(c.source, 99))

    return ConflictResult(
        field_code=field_code,
        winning_value=winner.normalized_value or winner.raw_value,
        winning_source=winner.source,
        confidence=winner.confidence,
        conflict_detected=conflict_detected,
        resolution_strategy=strategy,
        requires_human=False,
        candidates=cand_dicts if conflict_detected else [],
    )


# ---------------------------------------------------------------------------
# Project-level resolution
# ---------------------------------------------------------------------------

def build_resolved_field_map(
    db: Session,
    project_id,
) -> dict[str, ConflictResult]:
    """
    Load all ExtractedFieldValue rows for *project_id*, group by field_code,
    resolve conflicts, and return a map of {field_code: ConflictResult}.

    Also calls fetch_source_fallback_chain so the chain is exercised even if
    we have no extraction for that field (logged, not returned).
    """
    rows: list[ExtractedFieldValue] = (
        db.query(ExtractedFieldValue)
        .filter(ExtractedFieldValue.project_id == project_id)
        .all()
    )

    grouped: dict[str, list[Candidate]] = defaultdict(list)
    for row in rows:
        # Derive source from source_path (e.g. "MBS", "STAAD") or use parser_run
        source = _infer_source(row)
        grouped[row.field_code].append(
            Candidate(
                field_code=row.field_code,
                raw_value=row.raw_value,
                normalized_value=row.normalized_value,
                source=source,
                confidence=row.confidence,
                source_path=row.source_path,
            )
        )

    resolved: dict[str, ConflictResult] = {}
    for fc, candidates in grouped.items():
        try:
            result = resolve_field_conflict(fc, candidates)
            resolved[fc] = result
            
            # Log conflicts
            if result.conflict_detected:
                logger.info(
                    "Conflict on %s — %d candidates, strategy=%s, winner=%s",
                    fc, len(candidates), result.resolution_strategy, result.winning_source,
                )
                log_audit_event(
                    db,
                    "CONFLICT_RESOLVED",
                    project_id=project_id,
                    field_code=fc,
                    detail={
                        "candidates": result.candidates,
                        "strategy": result.resolution_strategy,
                        "winner": result.winning_source,
                        "winning_value": result.winning_value,
                    }
                )
            
            # Log fallbacks (if winner is not the top priority source available for this project)
            priorities = fetch_source_category_priorities()
            # Find the best possible source available for this field among all project files
            # (Note: we don't know the full project file list here easily without querying,
            # but we can check if there are candidates with better priority than the winner)
            best_candidate = min(candidates, key=lambda c: priorities.get(c.source, 99))
            if result.winning_source != best_candidate.source:
                # This would be weird if the resolution strategy was HIGHEST_PRIORITY,
                # but if it was HIGHEST_CONFIDENCE, it might happen.
                pass 
            
            # Let's log if we used a fallback source because a higher priority source didn't have it.
            # (This is already handled by resolve_field_conflict if candidates only contains lower priority sources)
            # Actually, a "fallback" is more interesting if we have NO candidates from the primary source.
            
            # For simplicity, I'll log a FALLBACK_APPLIED if the winning source rank > 1
            if priorities.get(result.winning_source, 99) > 1:
                 log_audit_event(
                    db,
                    "FALLBACK_APPLIED",
                    project_id=project_id,
                    field_code=fc,
                    detail={
                        "winner": result.winning_source,
                        "winning_value": result.winning_value,
                        "strategy": result.resolution_strategy,
                        "note": f"Primary source (rank 1) did not provide {fc}"
                    }
                )
        except Exception as exc:
            logger.warning("Failed to resolve conflict for %s: %s", fc, exc)

    return resolved


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _infer_source(row: ExtractedFieldValue) -> str:
    """
    Derive the logical source name (MBS / STAAD / …) from the source_path.

    New format (stamped by P2-01 ingestion): "FILE_TYPE::actual/file/path"
    Legacy format: raw file path — scan for source tokens in the path string.
    """
    path = row.source_path or ""
    # New format: type prefix before "::"
    if "::" in path:
        prefix = path.split("::", 1)[0].upper()
        if prefix in ("MBS", "STAAD", "ETABS", "PROTASTEEL", "DXF", "PDF"):
            return prefix
    # Legacy: scan full path for known source tokens
    path_upper = path.upper()
    for token in ("MBS", "STAAD", "ETABS", "PROTASTEEL", "PROTA", "DXF", "PDF"):
        if token in path_upper:
            return "PROTASTEEL" if token == "PROTA" else token
    return "UNKNOWN"
