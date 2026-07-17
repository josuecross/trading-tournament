from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import yaml

from strategy_lab.research_os.research import usci_paper_forward_eligibility_review_v1 as review


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "usci_paper_forward_eligibility_review_v1" / "latest"
BOUNDED = ROOT / "evidence" / "usci_dynamic_commodity_curve_selection_bounded_screen_v1" / "latest"
VALIDATION = ROOT / "evidence" / "usci_current_methodology_validation_v1" / "latest"
OBS_YAML = ROOT / "paper_forward_observations" / review.OBSERVATION_ID / "active_observation.yaml"
ACTIVE_OBSERVATIONS = ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml"
REGISTRY = ROOT / "strategy_lab" / "strategy_registry.yaml"


def read_json(name: str) -> dict[str, object]:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def read_csv(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def test_required_artifacts_exist() -> None:
    required = {
        "review_manifest.json",
        "authoritative_evidence_lineage.json",
        "evidence_integrity_gate.csv",
        "historical_evidence_gate.csv",
        "recent_weakness_disclosure.json",
        "diversification_and_redundancy.csv",
        "operational_eligibility.csv",
        "paper_forward_decision.json",
        "direction_owner_override.json",
        "observation_configuration.json",
        "observation_initialization.json",
        "protected_state_verification.json",
        "source_of_truth_changes.csv",
        "review_summary.md",
        "consistency_check.json",
    }
    assert sorted(name for name in required if not (EVIDENCE / name).exists()) == []


def test_both_historical_evidence_packets_remain_byte_identical() -> None:
    lineage = read_json("authoritative_evidence_lineage.json")
    assert lineage["historical_packets_byte_identical_after_review"] is True
    for relative_path, expected in lineage["bounded_screen_hashes_before"].items():
        assert sha256(ROOT / str(relative_path)) == expected
        assert lineage["bounded_screen_hashes_after"][relative_path] == expected
    for relative_path, expected in lineage["current_validation_hashes_before"].items():
        assert sha256(ROOT / str(relative_path)) == expected
        assert lineage["current_validation_hashes_after"][relative_path] == expected
    assert read_json("consistency_check.json")["historical_packets_byte_identical"] is True


def test_formal_historical_outcome_labels_remain_unchanged() -> None:
    bounded_outcome = json.loads((BOUNDED / "screening_outcome.json").read_text(encoding="utf-8"))
    validation_outcome = json.loads((VALIDATION / "validation_outcome.json").read_text(encoding="utf-8"))
    integrity = {row["gate"]: row for row in read_csv("evidence_integrity_gate.csv")}
    assert bounded_outcome["outcome"] == "methodology_regime_instability"
    assert validation_outcome["outcome"] == "historical_edge_recently_weakened"
    assert integrity["formal_bounded_outcome_preserved"]["passed"] == "true"
    assert integrity["formal_validation_outcome_preserved"]["passed"] == "true"
    assert read_json("direction_owner_override.json")["formal_validation_label_remains_unchanged"] == "historical_edge_recently_weakened"


def test_candidate_closure_is_overridden_only_in_new_direction_record() -> None:
    validation_outcome = json.loads((VALIDATION / "validation_outcome.json").read_text(encoding="utf-8"))
    override = read_json("direction_owner_override.json")
    decision = read_json("paper_forward_decision.json")
    assert validation_outcome["exact_candidate_closed_for_immediate_retesting"] is True
    assert override["automatic_exact_candidate_closure_overridden"] is True
    assert override["candidate_current_handling"] == "paper_forward_review_candidate"
    assert decision["decision"] == "approve_usci_paper_forward_observation"
    assert read_json("consistency_check.json")["candidate_closure_overridden_only_in_new_direction_record"] is True


def test_historical_gates_use_frozen_conditions_and_pass() -> None:
    rows = read_csv("historical_evidence_gate.csv")
    by_gate = {row["gate"]: row for row in rows}
    assert all(row["passed"] == "true" for row in rows)
    assert by_gate["full_current_excess_positive"]["observed"] == "0.651704719714"
    assert by_gate["annualized_excess_positive"]["observed"] == "0.0568778546847"
    assert by_gate["at_least_two_chronological_thirds_beat_DBC"]["observed"] == "2"
    assert by_gate["at_least_three_complete_calendar_years_beat_DBC"]["observed"] == "4 of 5"
    assert read_json("consistency_check.json")["historical_gate_passed"] is True


def test_negative_latest_252_day_value_alone_cannot_force_closure() -> None:
    weakness = read_json("recent_weakness_disclosure.json")
    gate = {row["gate"]: row for row in read_csv("historical_evidence_gate.csv")}
    assert weakness["risk_label"] == "current_short_horizon_relative_weakness"
    assert weakness["negative_latest_horizons"]["latest_252d_excess"] < 0
    assert weakness["latest_504d_excess"] > 0
    assert gate["at_least_one_latest_252_or_504_positive"]["passed"] == "true"
    assert read_json("paper_forward_decision.json")["decision"] == "approve_usci_paper_forward_observation"
    assert read_json("consistency_check.json")["negative_latest_252_alone_did_not_force_closure"] is True


def test_usci_rules_and_fingerprint_remain_unchanged() -> None:
    prior_fingerprint = json.loads((BOUNDED / "candidate_fingerprint.json").read_text(encoding="utf-8"))
    config = read_json("observation_configuration.json")
    assert prior_fingerprint["strategy_fingerprint"] == "2748AB65A5290C55FBDA12300C0C0601A9B7B90FEAAAC38A2F9E30240B7A213B"
    assert prior_fingerprint["weighting_method"] == "100pct_USCI"
    assert config["source_candidate"] == review.CANDIDATE_ID
    assert config["target"] == "100% USCI"
    assert config["rebalance"] == "none after observation initialization"
    assert config["timing_signal"] == "none"
    assert config["BIL_switch"] == "none"
    assert config["futures_reconstruction"] is False
    assert read_json("consistency_check.json")["usci_rules_and_fingerprint_unchanged"] is True


def test_no_historical_backtest_or_cache_refresh_or_blend() -> None:
    manifest = read_json("review_manifest.json")
    check = read_json("consistency_check.json")
    assert manifest["historical_backtest_run"] is False
    assert manifest["historical_validation_run"] is False
    assert manifest["candidate_exhaustive_run"] is False
    assert manifest["provider_download"] is False
    assert manifest["cache_refresh"] is False
    assert manifest["blended_portfolio_constructed"] is False
    assert check["no_historical_backtest_rerun"] is True
    assert check["no_research_cache_refreshed_or_rewritten"] is True
    assert check["no_blended_portfolio_constructed"] is True


def test_diversification_gate_uses_existing_daily_series_and_passes() -> None:
    rows = {row["reference_id"]: row for row in read_csv("diversification_and_redundancy.csv")}
    assert set(rows) == {
        review.ACTIVE_VM_ID,
        review.ACTIVE_DSR_ID,
        review.ACTIVE_COMBO_ID,
        "SPY",
    }
    assert float(rows[review.ACTIVE_VM_ID]["daily_return_correlation"]) < 0.90
    assert float(rows[review.ACTIVE_DSR_ID]["daily_return_correlation"]) < 0.90
    assert rows[review.ACTIVE_VM_ID]["clear_operational_redundancy"] == "false"
    assert rows[review.ACTIVE_DSR_ID]["clear_operational_redundancy"] == "false"
    assert rows[review.ACTIVE_VM_ID]["gate_passed_for_reference"] == "true"
    assert rows[review.ACTIVE_DSR_ID]["gate_passed_for_reference"] == "true"


def test_vm_dsr_active_combo_remain_unchanged_and_existing_capital_not_changed() -> None:
    protected = read_json("protected_state_verification.json")
    assert protected["existing_vm_dsr_active_combo_unchanged"] is True
    assert protected["existing_observation_capital_changed"] is False
    assert protected["protected_hashes_before"] == protected["protected_hashes_after"]
    assert read_json("consistency_check.json")["vm_dsr_active_combo_unchanged"] is True
    assert read_json("consistency_check.json")["no_existing_observation_capital_changes"] is True


def test_usci_observation_uses_dbc_as_primary_benchmark() -> None:
    config = read_json("observation_configuration.json")
    obs = yaml.safe_load(OBS_YAML.read_text(encoding="utf-8"))
    assert config["primary_benchmark"] == "DBC"
    assert config["secondary_references"] == ["BIL", "SPY"]
    assert obs["primary_benchmark"] == "DBC"
    assert obs["candidate_instrument"] == "USCI"
    assert read_json("consistency_check.json")["dbc_primary_benchmark"] is True


def test_no_broker_order_or_real_money_flags_are_enabled() -> None:
    decision = read_json("paper_forward_decision.json")
    config = read_json("observation_configuration.json")
    init = read_json("observation_initialization.json")
    obs = yaml.safe_load(OBS_YAML.read_text(encoding="utf-8"))
    for payload in (decision, config, init, obs):
        assert payload.get("broker_integration", False) is False
        assert payload.get("live_orders", False) is False
        assert payload.get("order_placement", False) is False
        assert payload.get("real_money_recommendation", False) is False
    assert init["broker_order_placed"] is False
    assert init["paper_order_placed"] is False
    assert init["live_order_placed"] is False
    assert read_json("consistency_check.json")["no_broker_integration_or_order_placement"] is True
    assert read_json("consistency_check.json")["no_real_money_flag_true"] is True


def test_observation_initialization_does_not_alter_historical_evidence() -> None:
    init = read_json("observation_initialization.json")
    assert init["snapshot_data_source"] == "existing_local_adjusted_close_cache"
    assert init["snapshot_common_date"] == "2026-06-18"
    assert init["provider_download"] is False
    assert init["initial_virtual_capital"] == 3000.0
    assert init["initial_virtual_cash"] == 0.0
    assert read_json("consistency_check.json")["observation_initialization_does_not_alter_historical_evidence"] is True


def test_source_of_truth_records_include_usci_without_altering_existing_observations() -> None:
    active = yaml.safe_load(ACTIVE_OBSERVATIONS.read_text(encoding="utf-8"))
    active_ids = {row["strategy_id"] for row in active["active_observations"]}
    registry = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    row_ids = {row["id"] for row in registry["strategies"]}
    changes = read_csv("source_of_truth_changes.csv")
    assert review.OBSERVATION_ID in active_ids
    assert review.OBSERVATION_ID in row_ids
    assert active["latest_usci_paper_forward_eligibility_review"]["direction_owner_override"] is True
    assert registry["registry"]["active_observations_count"] >= 3
    assert all(row["changes_existing_vm_dsr_or_combo"] == "false" for row in changes)


def test_output_generation_is_deterministic_except_snapshot_timestamp() -> None:
    comparable = [
        path
        for path in sorted(EVIDENCE.iterdir())
        if path.is_file() and path.name != "observation_initialization.json"
    ]
    before = {path.name: sha256(path) for path in comparable}
    result = review.run()
    after = {path.name: sha256(path) for path in comparable}
    assert result["decision"] == "approve_usci_paper_forward_observation"
    assert result["consistency_passed"] is True
    assert before == after
    assert read_json("observation_initialization.json")["snapshot_timestamp_utc"]


def test_consistency_check_passes() -> None:
    assert read_json("consistency_check.json")["consistency_passed"] is True
