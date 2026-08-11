from __future__ import annotations

import csv
import json

import pandas as pd
import yaml

from strategy_lab.research_os.universe_expansion import phase2_bounded_multi_asset_research_universe_v1 as phase2


def read_csv(name: str) -> list[dict[str, str]]:
    with (phase2.OUTPUT_DIR / name).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_frozen_scope_and_prior_rules() -> None:
    assert phase2.TASK_ID == "phase2_bounded_multi_asset_research_universe_expansion_v1"
    assert phase2.UNIVERSE_ID == "phase2_bounded_multi_asset_research_universe_v1"
    assert len(phase2.CORE_SYMBOLS) == 47
    assert len(set(phase2.CORE_SYMBOLS)) == 47
    assert len(phase2.CANDIDATES) == 55
    assert not (set(phase2.CORE_SYMBOLS) & set(phase2.CANDIDATE_BY_SYMBOL))
    rules = phase2.prior_rules()
    assert rules["primary_cohort_min_valid_daily_adjusted_price_observations"] == 2000
    assert rules["latest_60_session_median_dollar_volume_minimum"] == 10_000_000
    assert rules["seasoning_sessions_before_strategy_eligibility"] == 504


def test_candidate_inventory_and_leverage_exclusions() -> None:
    inventory, by_symbol, prior_exclusions = phase2.load_inventory()
    assert len(inventory) >= 80
    assert set(phase2.CANDIDATE_BY_SYMBOL).issubset(by_symbol)
    assert not (set(phase2.CANDIDATE_BY_SYMBOL) & set(prior_exclusions))
    assert all(not item.product_structure.startswith("leveraged") for item in phase2.CANDIDATES)
    assert all("inverse" not in item.product_structure for item in phase2.CANDIDATES)


def test_structural_duplicate_decisions_are_nonperformance() -> None:
    rows = phase2.structural_rows()
    excluded = {row["excluded_symbol"] for row in rows if row["excluded_symbol"]}
    assert excluded == set(phase2.STRUCTURAL_EXCLUSIONS)
    assert all(row["return_correlation_used"] is False for row in rows)
    assert all(row["asset_performance_used"] is False for row in rows)


def test_ohlc_check_tolerates_adjustment_roundoff_but_rejects_real_errors() -> None:
    harmless = pd.DataFrame({"open": [10.0], "high": [10.0 - 1e-13], "low": [9.0], "close": [10.0]})
    broken = pd.DataFrame({"open": [10.0], "high": [9.0], "low": [8.0], "close": [10.0]})
    assert phase2.ohlc_invalid_count(harmless) == 0
    assert phase2.ohlc_invalid_count(broken) == 1


def test_run_packet_and_entity_contract() -> None:
    result = phase2.run()
    assert result["consistency_overall_pass"] is True
    assert {path.name for path in phase2.OUTPUT_DIR.iterdir() if path.is_file()} == phase2.REQUIRED_OUTPUTS
    counts = json.loads((phase2.OUTPUT_DIR / "universe_entity_count_reconciliation.json").read_text(encoding="utf-8"))
    assert counts["research_universe_versions"] == 1
    assert counts["strategy_configurations"] == 0
    assert counts["experiment_trials"] == 0
    assert counts["optimization_trials"] == 0
    assert counts["robustness_trials"] == 0
    assert counts["paper_demo_observations"] == 0


def test_ready_universe_is_bounded_and_data_valid() -> None:
    outcome = read_csv("outcome_summary.csv")[0]
    total = int(outcome["total_symbol_count"])
    if outcome["outcome"] in {phase2.READY, phase2.READY_DEFERRED}:
        assert 80 <= total <= 150
        frozen = read_csv("phase2_frozen_universe.csv")
        assert len(frozen) == total
        assert all(row["data_ready"] == "True" for row in frozen)
        validations = {row["symbol"]: row for row in read_csv("new_symbol_cache_validation.csv")}
        additions = [row for row in frozen if row["membership_source"] == "phase2_nonperformance_addition"]
        assert all(validations[row["symbol"]]["data_status"] == "eligible" for row in additions)


def test_no_performance_selection_or_strategy_results() -> None:
    audit = read_csv("nonperformance_selection_audit.csv")
    assert all(row["performance_used"] == "False" for row in audit)
    forbidden = {"cagr", "sharpe", "drawdown", "momentum", "strategy_return", "backtest_return"}
    for name in phase2.REQUIRED_OUTPUTS:
        path = phase2.OUTPUT_DIR / name
        if path.suffix == ".csv":
            header = path.read_text(encoding="utf-8-sig").splitlines()[0].lower()
            assert not any(token in header for token in forbidden)


def test_phase1_and_protected_state_preserved() -> None:
    rows = read_csv("phase1_cache_preservation.csv")
    assert rows[0]["unchanged"] == "True"
    assert rows[0]["historical_rows_rewritten"] == "False"
    consistency = json.loads((phase2.OUTPUT_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["checks"]["protected_state_unchanged"] is True
    assert consistency["forbidden_actions"]["strategy_backtest"] is False
    assert consistency["forbidden_actions"]["forward_observation_operation"] is False


def test_manifest_and_frozen_hash_reconcile() -> None:
    manifest = yaml.safe_load((phase2.OUTPUT_DIR / "expansion_manifest.yaml").read_text(encoding="utf-8"))
    frozen = read_csv("phase2_frozen_universe.csv")
    assert manifest["universe_id"] == phase2.UNIVERSE_ID
    assert manifest["total_symbol_count"] == len(frozen)
    assert {row["frozen_universe_hash"] for row in frozen} == {manifest["frozen_universe_hash"]}
    assert manifest["strategy_configurations_created"] == 0
    assert manifest["experiment_trials_created"] == 0


def test_deterministic_rerun() -> None:
    first = json.loads((phase2.OUTPUT_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    result = phase2.run()
    second = json.loads((phase2.OUTPUT_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    assert result["consistency_overall_pass"] is True
    assert first["deterministic_core_hash"] == second["deterministic_core_hash"]
    assert first["frozen_universe_hash"] == second["frozen_universe_hash"]
