from __future__ import annotations

import csv
import json
from pathlib import Path

from strategy_lab.research_os.research.keller_keuning_vaa_g4_13612w_v1 import (
    DEFENSIVE_SYMBOLS,
    MOMENTUM_HORIZONS,
    MOMENTUM_WEIGHTS,
    OFFENSIVE_SYMBOLS,
    OUTPUT_DIR,
    PROJECT_STANDARD_COST_BPS_PER_TURNOVER,
    REQUIRED_SYMBOLS,
    SOURCE_COST_BPS_PER_TURNOVER,
    TASK_ID,
    TRIAL_ID,
    deterministic_core_hash,
    run,
    state_from_scores,
)


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / OUTPUT_DIR


def load_json(name: str) -> dict:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def csv_rows(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_required_artifacts_and_successful_contract() -> None:
    required = [
        "source_packet_used.yaml",
        "exact_duplicate_check.json",
        "repository_fit_check.json",
        "source_to_etf_mapping.csv",
        "frozen_trial_manifest.csv",
        "data_coverage.csv",
        "monthly_price_matrix.csv",
        "momentum_score_audit.csv",
        "breadth_state_audit.csv",
        "target_weights.csv",
        "transactions.csv",
        "baseline_metrics.csv",
        "control_metrics.csv",
        "baseline_vs_controls.csv",
        "timeframe_diagnostics.csv",
        "state_and_instrument_attribution.csv",
        "accounting_invariants.csv",
        "family_outcome.json",
        "family_followup_queue.csv",
        "command_validation_log.csv",
        "consistency_check.json",
        "implementation_summary.md",
    ]
    for name in required:
        assert (EVIDENCE / name).exists(), name
    check = load_json("consistency_check.json")
    assert check["task_id"] == TASK_ID
    assert check["task_outcome"] == "vaa_g4_fast_lane_complete"
    assert check["consistency_passed"] is True
    assert check["return_calculation_run"] is True


def test_frozen_universes_and_no_substitution() -> None:
    assert OFFENSIVE_SYMBOLS == ["SPY", "EFA", "EEM", "AGG"]
    assert DEFENSIVE_SYMBOLS == ["LQD", "IEF", "SHY"]
    mapping = {row["expected_symbol"]: row for row in csv_rows("source_to_etf_mapping.csv")}
    assert set(mapping) == set(REQUIRED_SYMBOLS)
    assert all(row["selected_symbol"] == symbol for symbol, row in mapping.items())
    assert all(row["substitution_allowed"] == "False" for row in mapping.values())
    assert all(row["substitution_used"] == "False" for row in mapping.values())
    assert "ACWX" not in mapping


def test_momentum_formula_is_exact_13612w() -> None:
    assert MOMENTUM_HORIZONS == [1, 3, 6, 12]
    assert MOMENTUM_WEIGHTS == {1: 12.0, 3: 4.0, 6: 2.0, 12: 1.0}
    score_rows = [row for row in csv_rows("momentum_score_audit.csv") if row["valid_13_month_history"] == "True"]
    assert score_rows
    sample = score_rows[0]
    expected = (
        12.0 * float(sample["R1"])
        + 4.0 * float(sample["R3"])
        + 2.0 * float(sample["R6"])
        + float(sample["R12"])
    )
    assert abs(float(sample["momentum_score"]) - expected) <= 1e-12
    assert {row["horizons_months"] for row in score_rows} == {"1|3|6|12"}
    assert {row["score_weights"] for row in score_rows} == {"12|4|2|1"}
    assert {row["latest_month_skipped"] for row in score_rows} == {"False"}


def test_breadth_gate_selects_offensive_or_defensive_correctly() -> None:
    breadth_rows = [row for row in csv_rows("breadth_state_audit.csv") if row["valid_common_signal_month"] == "True"]
    assert any(row["breadth_state"] == "offensive" for row in breadth_rows)
    assert any(row["breadth_state"] == "defensive" for row in breadth_rows)
    for row in breadth_rows:
        offensive_scores = [float(row[f"{symbol}_score"]) for symbol in OFFENSIVE_SYMBOLS]
        if row["breadth_state"] == "offensive":
            assert all(score > 0.0 for score in offensive_scores)
            assert row["ranking_universe_used"] == "offensive_only"
            assert row["selected_asset"] in OFFENSIVE_SYMBOLS
        else:
            assert any(score <= 0.0 for score in offensive_scores)
            assert row["ranking_universe_used"] == "defensive_only"
            assert row["selected_asset"] in DEFENSIVE_SYMBOLS
            assert row["defensive_momentum_positive_required"] == "False"


def test_defensive_momentum_need_not_be_positive_and_tie_order_is_frozen() -> None:
    negative_defensive = [
        row
        for row in csv_rows("breadth_state_audit.csv")
        if row["breadth_state"] == "defensive"
        and row["valid_common_signal_month"] == "True"
        and all(float(row[f"{symbol}_score"]) <= 0.0 for symbol in DEFENSIVE_SYMBOLS)
    ]
    assert negative_defensive
    import pandas as pd

    offensive_tie = pd.Series({"SPY": 1.0, "EFA": 1.0, "EEM": 0.5, "AGG": 0.2, "LQD": 0.0, "IEF": 0.0, "SHY": 0.0})
    defensive_tie = pd.Series({"SPY": -0.1, "EFA": 0.2, "EEM": 0.3, "AGG": 0.4, "LQD": 0.1, "IEF": 0.1, "SHY": -1.0})
    assert state_from_scores(offensive_tie)["selected_asset"] == "SPY"
    assert state_from_scores(defensive_tie)["selected_asset"] == "LQD"


def test_exactly_one_asset_held_and_no_same_period_execution() -> None:
    targets = csv_rows("target_weights.csv")
    assert targets
    for row in targets:
        held = [symbol for symbol in REQUIRED_SYMBOLS if abs(float(row[symbol]) - 1.0) <= 1e-12]
        assert held == [row["selected_asset"]]
        assert abs(float(row["weight_sum"]) - 1.0) <= 1e-12
        assert abs(float(row["gross_exposure"]) - 1.0) <= 1e-12
        assert abs(float(row["net_exposure"]) - 1.0) <= 1e-12
    baseline = csv_rows("baseline_metrics.csv")[0]
    assert baseline["first_signal_date"] < baseline["first_execution_date"]
    invariants = csv_rows("accounting_invariants.csv")[0]
    assert invariants["same_period_execution_impossible"] == "True"
    assert invariants["latest_month_not_skipped"] == "True"


def test_source_project_and_zero_cost_series_are_distinct_and_only_registered_costs() -> None:
    assert SOURCE_COST_BPS_PER_TURNOVER == 10.0
    assert PROJECT_STANDARD_COST_BPS_PER_TURNOVER == 5.0
    baseline = csv_rows("baseline_metrics.csv")[0]
    controls = {row["control_id"]: row for row in csv_rows("control_metrics.csv")}
    assert baseline["source_cost_bps_per_turnover"] == "10.0"
    assert baseline["project_cost_bps_per_turnover"] == "5.0"
    assert set(controls) == {
        "equal_weight_offensive_basket_monthly_rebalanced",
        "equal_weight_defensive_basket_monthly_rebalanced",
        "static_average_weight_seven_asset_control_ex_post_diagnostic",
        "zero_cost_vaa_g4",
        "source_aligned_10bps_vaa_g4",
        "project_5bps_vaa_g4",
    }
    assert float(controls["zero_cost_vaa_g4"]["total_return"]) >= float(controls["source_aligned_10bps_vaa_g4"]["total_return"])
    assert float(controls["project_5bps_vaa_g4"]["total_return"]) >= float(controls["source_aligned_10bps_vaa_g4"]["total_return"])


def test_one_canonical_trial_controls_same_calendar_and_no_overlay_state_changes() -> None:
    manifest = csv_rows("frozen_trial_manifest.csv")
    assert len(manifest) == 1
    assert manifest[0]["trial_id"] == TRIAL_ID
    assert manifest[0]["portfolio_trial_count"] == "1"
    assert manifest[0]["momentum_horizons_months"] == "1|3|6|12"
    controls = csv_rows("control_metrics.csv")
    assert {row["same_evaluation_calendar"] for row in controls} == {"True"}
    check = load_json("consistency_check.json")
    assert check["provider_download"] is False
    assert check["intraday_data_used"] is False
    assert check["no_overlay_output_generated"] is True
    assert check["registry_lifecycle_unchanged"] is True
    assert check["active_paper_demo_state_unchanged"] is True
    assert check["broker_or_order_path_touched"] is False
    assert check["paper_forward_activation"] is False
    assert check["promotion_candidates_created"] is False
    assert check["candidate_exhaustive_run"] is False
    assert check["real_money_recommendation"] is False
    assert all("overlay" not in path.name.lower() for path in EVIDENCE.iterdir())


def test_family_outcome_is_allowed_and_non_promotable() -> None:
    family = load_json("family_outcome.json")
    assert family["family_outcome"] in {
        "family_exploratory_followup_candidate",
        "family_timeframe_fragile",
        "family_control_weak",
        "family_cost_fragile",
    }
    assert family["promotion_eligibility"] is False
    assert family["paper_forward_eligibility"] is False
    assert family["candidate_exhaustive_eligibility"] is False
    queue = csv_rows("family_followup_queue.csv")
    gem_rows = [row for row in queue if row["strategy_id"] == "antonacci_gem_12m_global_equities_bond_v1"]
    assert gem_rows and gem_rows[0]["direction_decision"] == "NO_ADVANCEMENT"


def test_generation_is_deterministic() -> None:
    before = load_json("consistency_check.json")["deterministic_core_hash"]
    result = run(ROOT)
    after = load_json("consistency_check.json")["deterministic_core_hash"]
    assert result["consistency_passed"] is True
    assert before == after
    assert after == deterministic_core_hash(EVIDENCE)
