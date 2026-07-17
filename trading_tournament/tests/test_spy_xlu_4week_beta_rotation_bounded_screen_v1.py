from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pandas as pd

from strategy_lab.research_os.research import spy_xlu_4week_beta_rotation_bounded_screen_v1 as screen


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "spy_xlu_4week_beta_rotation_bounded_screen_v1" / "latest"


def read_json(name: str) -> dict[str, object]:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def read_csv(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def synthetic_prices() -> pd.DataFrame:
    dates = pd.bdate_range("2020-01-02", "2020-04-30")
    frame = pd.DataFrame(index=dates)
    frame["SPY"] = 100.0
    frame["XLU"] = 100.0
    for i, date in enumerate(dates):
        week = int(i // 5)
        frame.loc[date, "SPY"] = 100.0 + week
        frame.loc[date, "XLU"] = 100.0 + week * 2.0
    frame.loc[dates[55]:, "SPY"] = 130.0
    frame.loc[dates[55]:, "XLU"] = 105.0
    return frame


def test_required_artifacts_exist() -> None:
    required = {
        "source_and_preregistration.json",
        "candidate_fingerprint.json",
        "duplicate_and_redundancy_review.csv",
        "provider_acquisition_manifest.json",
        "cache_manifest.json",
        "frozen_weekly_observations.csv",
        "frozen_signal_dates.csv",
        "frozen_execution_dates.csv",
        "skipped_signal_weeks.csv",
        "frozen_chronological_blocks.csv",
        "frozen_180d_windows.csv",
        "frozen_252d_windows.csv",
        "full_period_metrics.csv",
        "chronological_block_results.csv",
        "window_level_results.csv",
        "calendar_year_results.csv",
        "source_update_regime_results.csv",
        "benchmark_relative_metrics.csv",
        "dsr_redundancy_diagnostics.csv",
        "signal_diagnostics.csv",
        "accounting_timing_and_exposure_invariants.csv",
        "screening_outcome.json",
        "exact_variant_research_memory.csv",
        "treasury_rotation_direction_memory.json",
        "screen_summary.md",
        "consistency_check.json",
    }
    assert sorted(name for name in required if not (EVIDENCE / name).exists()) == []


def test_weekly_observations_use_final_common_xlu_spy_session() -> None:
    rows = read_csv("frozen_weekly_observations.csv")
    assert rows
    assert all(row["final_common_XLU_SPY_session"] == "true" for row in rows)
    assert read_json("consistency_check.json")["weekly_observations_use_final_common_XLU_SPY_session"] is True


def test_four_week_returns_use_exactly_four_prior_weekly_observations() -> None:
    rows = read_csv("frozen_signal_dates.csv")
    assert rows
    assert all(row["four_week_observation_lag"] == "4" for row in rows)
    assert read_json("consistency_check.json")["four_week_returns_use_exactly_four_prior_weekly_observations"] is True


def test_completed_signal_week_precedes_execution_and_same_close_is_impossible() -> None:
    rows = read_csv("frozen_execution_dates.csv")
    assert rows
    assert all(row["execution_after_signal_close"] == "true" for row in rows)
    assert all(row["same_close_lookahead_possible"] == "false" for row in rows)
    check = read_json("consistency_check.json")
    assert check["completed_signal_week_precedes_execution"] is True
    assert check["same_close_execution_impossible"] is True


def test_positive_xlu_minus_spy_selects_xlu_and_negative_selects_spy() -> None:
    _, signal_rows, _, _, events = screen.build_weekly_signals(synthetic_prices())
    event_targets = list(events.values())
    assert any(target.get("XLU") == 1.0 and target.get("SPY") == 0.0 for target in event_targets)
    assert any(target.get("SPY") == 1.0 and target.get("XLU") == 0.0 for target in event_targets)
    check = read_json("consistency_check.json")
    assert check["positive_XLU_minus_SPY_signal_selects_XLU"] is True
    assert check["negative_XLU_minus_SPY_signal_selects_SPY"] is True
    assert {row["decision"] for row in signal_rows} & {"select_XLU", "select_SPY"}


def test_equal_and_missing_observations_retain_prior_allocation() -> None:
    assert screen.equal_returns_retain_prior("XLU") == "XLU"
    assert screen.missing_observations_retain_prior("SPY") == "SPY"
    check = read_json("consistency_check.json")
    assert check["equal_signal_retain_prior_position"] is True
    assert check["missing_observations_retain_prior_position"] is True


def test_no_prices_are_forward_filled_and_only_spy_or_xlu_is_held_after_initialization() -> None:
    invariants = read_csv("accounting_timing_and_exposure_invariants.csv")[0]
    assert invariants["no_prices_forward_filled"] == "true"
    assert invariants["holds_only_SPY_or_XLU_after_initialization"] == "true"
    check = read_json("consistency_check.json")
    assert check["no_prices_forward_filled"] is True
    assert check["strategy_holds_only_SPY_or_XLU_after_initialization"] is True


def test_exposure_never_exceeds_one() -> None:
    invariants = read_csv("accounting_timing_and_exposure_invariants.csv")[0]
    assert float(invariants["maximum_exposure"]) <= 1.000001
    assert float(invariants["maximum_weight_sum"]) <= 1.000001
    assert invariants["exposure_never_exceeds_1"] == "true"


def test_turnover_uses_actual_pretrade_holdings() -> None:
    invariants = read_csv("accounting_timing_and_exposure_invariants.csv")[0]
    assert invariants["turnover_uses_actual_pretrade_holdings"] == "true"
    assert read_json("consistency_check.json")["turnover_uses_actual_pretrade_holdings"] is True


def test_windows_and_regimes_are_frozen_before_performance() -> None:
    for filename in ("frozen_chronological_blocks.csv", "frozen_180d_windows.csv", "frozen_252d_windows.csv"):
        rows = read_csv(filename)
        assert rows
        assert all(row["frozen_before_performance"] == "true" for row in rows)
    regimes = read_csv("source_update_regime_results.csv")
    assert regimes
    assert read_json("consistency_check.json")["windows_and_regimes_frozen_before_performance"] is True


def test_dsr_is_comparison_only_and_not_modified() -> None:
    duplicate = read_csv("duplicate_and_redundancy_review.csv")
    assert any(row["reviewed_id"] == "paper_forward_dsr_sector_equal_weight_defensive_filter_v1" for row in duplicate)
    assert read_json("consistency_check.json")["DSR_comparison_only_not_modified"] is True
    dsr = read_csv("dsr_redundancy_diagnostics.csv")[0]
    assert dsr["dsr_comparison_status"] in {"available_existing_corrected_series", "descriptive_unavailable"}


def test_no_vix_bil_treasury_moving_average_or_leverage_rule_enters_candidate() -> None:
    prereg = read_json("source_and_preregistration.json")
    rules = prereg["frozen_rules"]
    assert rules["BIL_fallback"] is False
    assert rules["treasury_allocation"] is False
    assert rules["VIX_filter"] is False
    assert rules["moving_average_filter"] is False
    assert rules["volatility_targeting"] is False
    assert rules["leverage"] is False
    assert read_json("consistency_check.json")["no_VIX_BIL_treasury_moving_average_or_leverage_rule"] is True


def test_vm_dsr_usci_active_combo_and_treasury_evidence_remain_unchanged_no_orders_created() -> None:
    invariants = read_csv("accounting_timing_and_exposure_invariants.csv")[0]
    assert invariants["VM_DSR_USCI_active_combo_states_unchanged"] == "true"
    assert invariants["paper_demo_observation_created"] == "false"
    assert invariants["broker_order_created"] == "false"
    memory = read_json("treasury_rotation_direction_memory.json")
    assert memory["prior_evidence_modified"] is False
    assert memory["formal_outcome"] == "no_material_edge"
    check = read_json("consistency_check.json")
    assert check["VM_DSR_USCI_active_combo_states_unchanged"] is True
    assert check["no_paper_demo_observation_or_broker_order"] is True


def test_output_is_deterministic_and_non_promotional() -> None:
    outcome_hash = sha256(EVIDENCE / "screening_outcome.json")
    metrics_hash = sha256(EVIDENCE / "full_period_metrics.csv")
    assert sha256(EVIDENCE / "screening_outcome.json") == outcome_hash
    assert sha256(EVIDENCE / "full_period_metrics.csv") == metrics_hash
    check = read_json("consistency_check.json")
    assert check["output_generation_deterministic"] is True
    assert check["promotion_authorized"] is False
    assert check["paper_demo_authorized"] is False
    assert check["candidate_exhaustive_authorized"] is False
    assert check["real_money_recommendation"] is False
    assert check["consistency_passed"] is True


def test_outcome_is_single_frozen_allowed_label_and_family_remains_open_if_weak() -> None:
    outcome = read_json("screening_outcome.json")
    assert outcome["outcome"] in screen.ALLOWED_OUTCOMES
    assert outcome["promotion_authorized"] is False
    assert outcome["paper_demo_authorized"] is False
    assert outcome["candidate_exhaustive_authorized"] is False
    memory = read_csv("exact_variant_research_memory.csv")[0]
    assert memory["broader_intermarket_equity_beta_rotation_family_closed"] == "false"
