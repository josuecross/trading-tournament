from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from strategy_lab.research_os.research.direction_owner_single_source_intake_v1 import (
    ACTIVE_OBSERVATIONS_PATH,
    ANGL_ACQUISITION_METADATA,
    AUTHORIZED_PROVIDER_SYMBOLS,
    CACHE_DIR,
    OUTPUT_DIR,
    REGISTRY_PATH,
    ROOT,
    SOURCE_ID,
    provider_request,
    run,
)


EVIDENCE = ROOT / OUTPUT_DIR


def _json(name: str) -> dict:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def _csv(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def setup_module() -> None:
    run()
    manifest = _json("provider_acquisition_manifest.json")
    if manifest["provider_download_this_run"] and manifest["cache_status_after"] == "cache_ready":
        run()


def test_required_artifacts_exist_and_preregistration_is_ready_when_cache_resolved() -> None:
    required = {
        "provider_acquisition_manifest.json",
        "angl_cache_validation.csv",
        "decision.json",
        "decision.md",
        "source_identity.csv",
        "source_rule_extraction.csv",
        "source_support_trace.csv",
        "duplicate_gate.csv",
        "material_distinction_review.csv",
        "data_and_execution_feasibility.csv",
        "methodology_transition_review.csv",
        "missing_or_ambiguous_fields.csv",
        "consistency_check.json",
        "preregistration.yaml",
        "preregistration.md",
    }
    for name in required:
        assert (EVIDENCE / name).exists(), name
    assert _json("decision.json")["decision"] == "preregistration_ready"
    assert _csv("missing_or_ambiguous_fields.csv") == []


def test_exactly_one_selected_source_is_evaluated() -> None:
    decision = _json("decision.json")
    identity = _csv("source_identity.csv")
    assert decision["source_ids_evaluated"] == [SOURCE_ID]
    assert decision["selected_source_packet_count"] == 1
    assert identity[0]["source_id"] == SOURCE_ID
    assert identity[0]["direction_owner_selected"] == "true"
    assert identity[0]["current_input_gate_candidate"] == "true"
    assert identity[0]["external_source_discovery_pause_remains_active"] == "true"


def test_codex_does_not_choose_another_source() -> None:
    decision = _json("decision.json")
    check = _json("consistency_check.json")
    assert decision["source_ids_evaluated"] == [SOURCE_ID]
    assert check["codex_did_not_choose_another_source"] is True


def test_provider_allowlist_is_angl_only() -> None:
    decision = _json("decision.json")
    manifest = _json("provider_acquisition_manifest.json")
    assert AUTHORIZED_PROVIDER_SYMBOLS == ("ANGL",)
    assert manifest["authorized_provider_symbols"] == ["ANGL"]
    assert set(manifest["requested_symbols"]).issubset({"ANGL"})
    assert set(manifest["downloaded_symbols_this_run"]).issubset({"ANGL"})
    assert decision["provider_download_authorized_for_angl_only"] is True
    with pytest.raises(ValueError):
        provider_request("HYG", lambda symbol, settings: None)


def test_valid_existing_angl_cache_prevents_subsequent_provider_call() -> None:
    run()
    decision = _json("decision.json")
    manifest = _json("provider_acquisition_manifest.json")
    assert manifest["provider_download_this_run"] is False
    assert manifest["provider_api_called_this_run"] is False
    assert manifest["requested_symbols"] == []
    assert manifest["existing_valid_cache_prevented_provider_call"] is True
    assert decision["existing_valid_angl_cache_prevented_provider_call"] is True


def test_successful_acquisition_created_one_immutable_cache_snapshot_metadata() -> None:
    metadata_path = ROOT / ANGL_ACQUISITION_METADATA
    assert metadata_path.exists()
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    validation = _csv("angl_cache_validation.csv")[0]
    assert metadata["symbol"] == "ANGL"
    assert metadata["provider_downloaded_symbol"] == "ANGL"
    assert metadata["provider_allowlist"] == ["ANGL"]
    assert metadata["cache_hash"] == validation["cache_hash"]
    assert validation["cache_status"] == "cache_ready"


def test_hyg_bil_and_ief_caches_remain_byte_identical() -> None:
    manifest = _json("provider_acquisition_manifest.json")
    assert manifest["protected_existing_cache_symbols"] == ["HYG", "BIL", "IEF"]
    assert manifest["protected_cache_hashes_unchanged"] is True
    assert manifest["protected_cache_hashes_before"] == manifest["protected_cache_hashes_after"]
    for symbol in ("HYG", "BIL", "IEF"):
        assert manifest["protected_cache_hashes_after"][symbol] == _hash(ROOT / CACHE_DIR / f"{symbol}.csv")


def test_adjusted_close_and_symbol_identity_are_required_for_angl() -> None:
    validation = _csv("angl_cache_validation.csv")[0]
    assert validation["symbol"] == "ANGL"
    assert validation["cache_exists"] == "true"
    assert validation["adjusted_close_available"] == "true"
    assert validation["symbol_identity_valid"] == "true"
    assert validation["history_consistent_with_inception"] == "true"
    assert validation["missing_adj_close_count"] == "0"
    assert validation["duplicate_date_count"] == "0"
    assert validation["nonpositive_adj_close_count"] == "0"


def test_common_history_spans_2020_boundary_and_2023_amendment() -> None:
    feasibility = {row["symbol"]: row for row in _csv("data_and_execution_feasibility.csv")}
    angl = feasibility["ANGL"]
    assert angl["cache_status"] == "cache_ready"
    assert int(angl["common_angl_hyg_row_count"]) > 0
    assert angl["spans_feb_28_2020_boundary"] == "true"
    assert angl["first_common_session_on_or_after_2020_02_28"] >= "2020-02-28"
    assert angl["spans_dec_31_2023_amendment"] == "true"
    assert angl["first_common_session_on_or_after_2023_12_31"] >= "2023-12-31"


def test_all_three_methodology_regimes_are_explicit() -> None:
    transition = _csv("methodology_transition_review.csv")
    regimes = {row["regime_id"]: row for row in transition}
    assert set(regimes) == {
        "regime_1_prior_benchmark_methodology",
        "regime_2_initial_h0cf_methodology",
        "regime_3_amended_h0cf_methodology",
    }
    assert regimes["regime_1_prior_benchmark_methodology"]["benchmark"] == "ICE BofA US Fallen Angel High Yield Index"
    assert regimes["regime_2_initial_h0cf_methodology"]["effective_date"] == "2020-02-28"
    assert regimes["regime_3_amended_h0cf_methodology"]["effective_date"] == "2023-12-31"
    assert all(row["status"] == "ready" for row in transition)


def test_post_2023_caveat_does_not_claim_pure_fallen_angel_exposure() -> None:
    rules = {row["rule_id"]: row for row in _csv("source_rule_extraction.csv")}
    transition = {row["regime_id"]: row for row in _csv("methodology_transition_review.csv")}
    assert "not be described as consisting exclusively" in rules["post_2023_purity_caveat"]["normalized_value"]
    caveat = transition["regime_3_amended_h0cf_methodology"]["required_caveat"]
    assert "less pure fallen-angel exposure" in caveat
    assert "original-issue high-yield bonds" in caveat


def test_sponsor_performance_claims_are_excluded() -> None:
    decision = _json("decision.json")
    support = _csv("source_support_trace.csv")
    sponsor_rows = [row for row in support if row["rule_id"] == "sponsor_reported_performance_policy"]
    assert sponsor_rows
    assert sponsor_rows[0]["sponsor_performance_claim"] == "true"
    assert sponsor_rows[0]["source_reported_performance_excluded"] == "true"
    assert decision["sponsor_performance_claims_used_as_project_evidence"] is False


def test_duplicate_gate_does_not_reopen_closed_variants() -> None:
    duplicate = _csv("duplicate_gate.csv")[0]
    material = _csv("material_distinction_review.csv")
    assert duplicate["exact_valid_duplicate_found"] == "false"
    assert duplicate["duplicate_gate_decision"] == "no_exact_valid_duplicate_found"
    assert all(row["exact_closed_variant_reopened"] == "false" for row in material)


def test_no_trend_bil_rate_or_duration_overlay_is_added() -> None:
    rules = {row["rule_id"]: row for row in _csv("source_rule_extraction.csv")}
    decision = _json("decision.json")
    assert "No BIL switch" in rules["fallback"]["normalized_value"]
    assert "No trend" in rules["prohibited_overlays"]["normalized_value"]
    assert "rate" in rules["prohibited_overlays"]["normalized_value"]
    assert "duration hedge" in rules["prohibited_overlays"]["normalized_value"]
    assert decision["trend_bil_rate_duration_overlay_added"] is False


def test_no_performance_calculation_screen_or_backtest_occurs() -> None:
    decision = _json("decision.json")
    check = _json("consistency_check.json")
    assert decision["performance_calculation"] is False
    assert decision["screen_run"] is False
    assert decision["backtest_run"] is False
    assert decision["strategy_implementation"] is False
    assert decision["candidate_exhaustive_run"] is False
    assert check["no_performance_calculation"] is True
    assert check["no_screen_authorized"] is True


def test_registry_and_active_observations_remain_byte_identical() -> None:
    decision = _json("decision.json")
    assert decision["registry_hash_before"] == decision["registry_hash_after"]
    assert decision["active_observations_hash_before"] == decision["active_observations_hash_after"]
    assert decision["registry_hash_after"] == _hash(ROOT / REGISTRY_PATH)
    assert decision["active_observations_hash_after"] == _hash(ROOT / ACTIVE_OBSERVATIONS_PATH)


def test_external_discovery_pause_remains_active() -> None:
    decision = _json("decision.json")
    check = _json("consistency_check.json")
    assert decision["external_discovery_pause_remains_active"] is True
    assert decision["automatic_next_source_selection"] is False
    assert decision["new_external_screen_authorized"] is False
    assert check["external_discovery_pause_remains_active"] is True


def test_generation_is_deterministic_after_cache_resolution() -> None:
    before_decision = (EVIDENCE / "decision.json").read_bytes()
    before_consistency = (EVIDENCE / "consistency_check.json").read_bytes()
    run()
    assert (EVIDENCE / "decision.json").read_bytes() == before_decision
    assert (EVIDENCE / "consistency_check.json").read_bytes() == before_consistency
    assert _json("consistency_check.json")["consistency_passed"] is True
