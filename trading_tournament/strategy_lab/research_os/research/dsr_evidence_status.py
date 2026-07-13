from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


DSR_ACTIVE_ID = "paper_forward_dsr_sector_equal_weight_defensive_filter_v1"
MISMATCH_REVIEW_DIR = Path("evidence") / "dsr_active_evidence_mismatch_review" / "latest"
MISMATCH_REVIEW_JSON = MISMATCH_REVIEW_DIR / "dsr_mismatch_review.json"
MISMATCH_CONSISTENCY_JSON = MISMATCH_REVIEW_DIR / "mismatch_review_consistency_check.json"
HISTORICAL_BEST_FINAL_EQUITY = 4071.04
CURRENT_DIAGNOSTIC_BEST_FINAL_EQUITY = 3481.6998


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _hash_file(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return "missing"
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _rel(path: Path) -> str:
    return str(path).replace("\\", "/")


def load_dsr_evidence_status(root: Path) -> dict[str, Any]:
    review_path = root / MISMATCH_REVIEW_JSON
    consistency_path = root / MISMATCH_CONSISTENCY_JSON
    review = _read_json(review_path)
    consistency = _read_json(consistency_path)
    target_valid = review.get("target_active_observation_id") == DSR_ACTIVE_ID
    consistency_passed = bool(consistency.get("consistency_passed"))
    current_reproducible = bool(review.get("current_3481_reproducible")) if target_valid else False
    packet_valid = target_valid and consistency_passed
    current_metric = review.get("current_best_final_equity", "unknown") if packet_valid else "unknown"

    return {
        "target_active_observation_id": DSR_ACTIVE_ID,
        "source_packet_valid": packet_valid,
        "source_packet_target_valid": target_valid,
        "source_packet_consistency_passed": consistency_passed,
        "canonical_lifecycle_status": "active",
        "rules_status": "frozen",
        "paper_demo_state": "unchanged",
        "highest_independent_sel_level": "E1",
        "evidence_chain_status": "incomplete",
        "historical_recovered_metrics": {"best_final_equity": HISTORICAL_BEST_FINAL_EQUITY},
        "historical_metric_role": "historical_recovered_claim",
        "historical_metric_evidence_status": "unverified_non_comparable",
        "historical_metric_reproducible": False,
        "historical_metric_eligible_for_e4": False,
        "historical_metric_reason": "required methodology, data, execution, and daily path evidence are missing",
        "current_diagnostic_metrics": {"best_final_equity": current_metric},
        "current_diagnostic_role": "current_sampled_window_diagnostic",
        "current_diagnostic_evidence_status": "reproducible_diagnostic_only" if current_reproducible else "unverified_diagnostic_only",
        "current_diagnostic_reproducible": current_reproducible,
        "current_diagnostic_eligible_for_e4": False,
        "current_diagnostic_scope": "best_of_five_sampled_180d_cached_data_windows",
        "current_diagnostic_limitation": "not proven equivalent to the historical activation methodology",
        "metric_comparability": "non_comparable",
        "metric_eligible_for_evidence_stage": {"E4": False, "E5": False, "E6": False, "E7": False},
        "missing_evidence_stages": ["E2", "E3", "E4", "E5", "E6"],
        "evidence_warning": "historical_unverified_non_comparable; current_diagnostic_only; not_qualifying_e4; lifecycle_active_state_unchanged",
        "source_artifact_provenance": [
            {
                "artifact_role": "dsr_active_evidence_mismatch_review",
                "source_path": _rel(MISMATCH_REVIEW_JSON),
                "sha256": _hash_file(review_path),
                "target_valid": target_valid,
            },
            {
                "artifact_role": "dsr_active_evidence_mismatch_review_consistency_check",
                "source_path": _rel(MISMATCH_CONSISTENCY_JSON),
                "sha256": _hash_file(consistency_path),
                "consistency_passed": consistency_passed,
            },
        ],
        "fallback_reason": "none" if packet_valid else "missing_or_inconsistent_mismatch_review_packet",
    }
