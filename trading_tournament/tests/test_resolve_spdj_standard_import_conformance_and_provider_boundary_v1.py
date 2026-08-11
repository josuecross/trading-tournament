from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

import jsonschema
import pytest

from contracts.forward_observation.forward_observation_conformance_input_bundle_v1 import validate_bundle
from execution_lab.alpaca_micro_live_v1.standard_handoff.resolve_spdj_conformance_provider_boundary import (
    BUNDLE_DIR,
    HANDOFF_ID,
    IMPORTED_ROOT,
    OUTCOME_SUCCESS,
    OUTPUT_DIR,
    PACKAGE_HASH,
    PRIOR_EVIDENCE_HASH,
    PRIOR_DIR,
    SOURCE_PACKAGE,
    WEIGHT_TOLERANCE,
    FORMULA_TOLERANCE,
    load_receiver_contract,
    reconcile_prior_fixtures,
    run_frozen_golden_fixtures,
    verify_prior_pilot,
)


def read_json(name: str) -> dict:
    return json.loads((OUTPUT_DIR / name).read_text(encoding="utf-8"))


def read_csv(name: str) -> list[dict[str, str]]:
    return list(csv.DictReader((OUTPUT_DIR / name).open(newline="", encoding="utf-8")))


def test_prior_blocked_pilot_is_reconciled_and_immutable() -> None:
    result = verify_prior_pilot()
    assert result["status"] == "pass"
    assert result["observed_hash"] == PRIOR_EVIDENCE_HASH
    prior = json.loads((PRIOR_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    assert prior["outcome"] == "spdj_standard_handoff_import_blocked"


def test_prior_failures_are_coverage_not_same_window_semantics() -> None:
    rows, counts = reconcile_prior_fixtures()
    assert len(rows) == 15
    assert counts == {
        "failed_total": 13,
        "pre_provider_coverage": 12,
        "incomplete_lookback": 1,
        "same_window_semantic_failures": 0,
    }
    assert not any(row["valid_adjustment_semantics_diagnosis"] for row in rows)


def test_companion_schema_validates_manifest() -> None:
    schema_path = Path("contracts/forward_observation/forward_observation_conformance_input_bundle_v1/conformance_input_bundle.schema.json")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    manifest = json.loads((BUNDLE_DIR / "conformance_bundle_manifest.json").read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(manifest)
    assert manifest["software_conformance_reference"] is True
    assert manifest["operational_market_data"] is False


def test_conformance_bundle_hash_and_parent_links_validate() -> None:
    result = validate_bundle(BUNDLE_DIR)
    manifest = result["manifest"]
    assert result["status"] == "pass"
    assert result["observed_bundle_hash"] == manifest["conformance_bundle_hash"]
    assert manifest["parent_handoff_id"] == HANDOFF_ID
    assert manifest["parent_package_hash"] == PACKAGE_HASH
    assert manifest["source_research_evidence_hash"] == "sha256:86f55d845af1b4aac643dd076c46873e13e976db04b13b09264bd69cacb96599"
    assert manifest["fixture_count"] == 15


def test_conformance_bundle_tampering_is_rejected(tmp_path: Path) -> None:
    copied = tmp_path / "bundle"
    shutil.copytree(BUNDLE_DIR, copied)
    with (copied / "monthly_return_input.csv").open("a", encoding="utf-8") as handle:
        handle.write("tampered\n")
    with pytest.raises(ValueError, match="integrity failure"):
        validate_bundle(copied)


def test_all_frozen_input_fixtures_pass_at_exact_tolerances() -> None:
    _, _, calculator = load_receiver_contract()
    rows, _, summary, _ = run_frozen_golden_fixtures(calculator)
    assert len(rows) == 15
    assert summary["exact_target_pass_count"] == 13
    assert summary["pre_warmup_count"] == 1
    assert summary["no_event_count"] == 1
    assert summary["failed_count"] == 0
    assert summary["maximum_target_error"] <= 1e-8
    assert WEIGHT_TOLERANCE == 1e-8
    assert FORMULA_TOLERANCE == 1e-10


def test_proib_pair_counts_match_source_contract() -> None:
    summary = read_json("golden_intermediate_calculations.json")["fixture_summary"]
    assert summary["first_ProIB_pair_count"] == 25
    assert summary["all_120m_high_pair_counts_source_compliant"] is True


def test_operational_alpaca_window_is_complete_through_cutoff() -> None:
    coverage = read_json("operational_provider_coverage.json")
    assert coverage["actual_common_start"] == "2016-01-04"
    assert coverage["actual_common_end"] == "2026-07-31"
    assert coverage["operational_common_monthly_return_count"] == 126
    assert coverage["operational_120m_window_available"] is True
    assert coverage["operational_provider_status"] == "operational_history_ready"
    assert coverage["candidate_120m_return_start"] == "2016-08"
    assert coverage["candidate_120m_return_end"] == "2026-07"


def test_xnys_month_ends_are_complete_and_no_august_was_requested() -> None:
    rows = read_csv("operational_month_end_coverage.csv")
    july = next(row for row in rows if row["reference_month"] == "2026-07")
    assert july["expected_final_XNYS_session"] == "2026-07-31"
    assert july["complete_endpoint"] == "true"
    assert all(row["reference_month"] <= "2026-07" for row in rows)
    coverage = read_json("operational_provider_coverage.json")
    assert coverage["requested_end_exclusive"] == "2026-08-01T00:00:00Z"


def test_operational_adjustment_contract_is_structurally_supported() -> None:
    semantics = read_json("operational_price_semantics.json")
    assert semantics["provider"] == "Alpaca official market data API"
    assert semantics["feed"] == "sip"
    assert semantics["adjustment"] == "all"
    assert semantics["structural_adjustment_semantics_status"] == "supported"
    assert semantics["prior_adjustment_incompatibility_demonstrated"] is False
    assert semantics["bitwise_cross_provider_equality_required"] is False


def test_same_window_diagnostic_is_separate_and_nonblocking() -> None:
    consistency = read_json("consistency_check.json")
    diagnostic = consistency["same_window_provider_diagnostic"]
    rows = read_csv("same_window_provider_diagnostic.csv")
    assert diagnostic["status"] == "provider_portability_diagnostic_completed_review_needed"
    assert diagnostic["window_start"] == "2016-07"
    assert diagnostic["window_end"] == "2026-06"
    assert diagnostic["maximum_target_difference"] == pytest.approx(1.273994322600891e-05)
    assert diagnostic["regime_changed"] is False
    assert diagnostic["formal_blocking_tolerance_defined"] is False
    assert len(rows) == 6
    assert all(row["golden_tolerance_applied"] == "false" for row in rows)


def test_existing_import_reassessed_without_duplicate_or_activation() -> None:
    reassessment = read_json("receiver_acceptance_reassessment.json")
    assert reassessment["acceptance_status"] == "validated_not_active"
    assert reassessment["persistent_standardized_imports_before"] == 1
    assert reassessment["persistent_standardized_imports_after"] == 1
    assert reassessment["validation_attempts_before"] == 0
    assert reassessment["validation_attempts_after"] == 1
    assert reassessment["active_SPDJ_observations_before"] == 0
    assert reassessment["active_SPDJ_observations_after"] == 0
    assert (IMPORTED_ROOT / "resolution_v1.json").is_file()


def test_state_idempotency_and_legacy_regressions_pass() -> None:
    consistency = read_json("consistency_check.json")
    checks = consistency["checks"]
    assert checks["state_persistence_pass"] is True
    assert checks["idempotency_pass"] is True
    assert checks["target_version_pass"] is True
    assert checks["VM_DSR_unchanged"] is True
    assert checks["protected_state_unchanged"] is True


def test_no_current_or_broker_operations_occurred() -> None:
    consistency = read_json("consistency_check.json")
    counts = consistency["counts"]
    assert counts["historical_Alpaca_calls"] == 2
    assert counts["current_target_calculations"] == 0
    assert counts["current_CPI_calls"] == 0
    assert counts["account_calls"] == 0
    assert counts["position_calls"] == 0
    assert counts["order_calls"] == 0
    assert counts["fill_calls"] == 0


def test_final_outcome_and_next_action_are_exact() -> None:
    consistency = read_json("consistency_check.json")
    assert consistency["outcome"] == OUTCOME_SUCCESS
    assert consistency["acceptance_status"] == "validated_not_active"
    assert consistency["calculator_conformance_status"] == "pass"
    assert consistency["operational_provider_status"] == "operational_history_ready"
    assert consistency["next_action"] == "initialize_spdj_dynamic_inflation_paper_demo_observation_v1"
    assert consistency["next_action_executed"] is False
    assert consistency["all_checks_pass"] is True


def test_no_secrets_were_persisted_in_receiver_evidence() -> None:
    evidence_text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in OUTPUT_DIR.rglob("*")
        if path.is_file()
    )
    assert "APCA-API-SECRET-KEY" not in evidence_text
    assert "microtrading_promotion_not_authorized" in evidence_text
    assert SOURCE_PACKAGE.is_dir()
