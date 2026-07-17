from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from strategy_lab.research_os.research import spy_tlt_ief_tlt_prior_month_risk_rotation_bounded_screen_v1 as screen


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "spy_tlt_ief_tlt_prior_month_risk_rotation_bounded_screen_v1" / "latest"


def read_json(name: str) -> dict[str, object]:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def read_csv(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def synthetic_prices() -> pd.DataFrame:
    dates = pd.bdate_range("2020-01-02", "2020-04-10")
    frame = pd.DataFrame(index=dates)
    frame["SPY"] = 100.0
    frame["TLT"] = 100.0
    frame["IEF"] = 100.0
    frame["BIL"] = 100.0
    frame.loc[frame.index.month == 2, "IEF"] = 102.0
    frame.loc[frame.index.month == 2, "TLT"] = 101.0
    frame.loc[frame.index.month == 3, "IEF"] = 100.0
    frame.loc[frame.index.month == 3, "TLT"] = 105.0
    return frame


def test_required_artifacts_exist() -> None:
    required = {
        "source_and_preregistration.json",
        "candidate_fingerprint.json",
        "duplicate_review.csv",
        "provider_acquisition_manifest.json",
        "cache_manifest.json",
        "frozen_monthly_signal_dates.csv",
        "frozen_execution_dates.csv",
        "skipped_signal_months.csv",
        "frozen_chronological_blocks.csv",
        "frozen_180d_windows.csv",
        "frozen_252d_windows.csv",
        "full_period_metrics.csv",
        "chronological_block_results.csv",
        "window_level_results.csv",
        "calendar_year_results.csv",
        "regime_results.csv",
        "benchmark_relative_metrics.csv",
        "signal_diagnostics.csv",
        "accounting_timing_and_exposure_invariants.csv",
        "screening_outcome.json",
        "exact_variant_research_memory.csv",
        "screen_summary.md",
        "consistency_check.json",
    }
    assert sorted(name for name in required if not (EVIDENCE / name).exists()) == []


def test_monthly_ief_and_tlt_returns_use_matching_dates() -> None:
    rows = read_csv("frozen_monthly_signal_dates.csv")
    assert rows
    for row in rows[:25]:
        assert row["signal_month_start_reference_date"]
        assert row["signal_month_end"]
        assert row["signal_precedes_execution"] == "true"
    assert read_json("consistency_check.json")["monthly_IEF_TLT_returns_use_matching_dates"] is True


def test_completed_signal_month_precedes_execution_and_same_close_lookahead_is_impossible() -> None:
    rows = read_csv("frozen_execution_dates.csv")
    assert rows
    assert all(row["execution_after_signal_close"] == "true" for row in rows)
    assert all(row["same_close_lookahead_possible"] == "false" for row in rows)
    check = read_json("consistency_check.json")
    assert check["completed_signal_month_precedes_execution"] is True
    assert check["same_close_lookahead_impossible"] is True


def test_ief_gt_tlt_produces_spy_and_tlt_gt_ief_produces_tlt() -> None:
    _, _, _, events = screen.build_monthly_signals(synthetic_prices())
    event_targets = list(events.values())
    assert any(target.get("SPY") == 1.0 and target.get("TLT") == 0.0 for target in event_targets)
    assert any(target.get("TLT") == 1.0 and target.get("SPY") == 0.0 for target in event_targets)
    check = read_json("consistency_check.json")
    assert check["IEF_gt_TLT_produces_SPY"] is True
    assert check["TLT_gt_IEF_produces_TLT"] is True


def test_equal_returns_and_missing_signal_data_retain_prior_position() -> None:
    assert screen.equal_returns_retain_prior("SPY") == "SPY"
    assert screen.missing_signal_retain_prior("TLT") == "TLT"
    check = read_json("consistency_check.json")
    assert check["equal_returns_retain_prior_position"] is True
    assert check["missing_signal_data_retain_prior_position"] is True


def test_no_prices_are_forward_filled_and_strategy_holds_only_spy_or_tlt_after_initialization() -> None:
    invariants = read_csv("accounting_timing_and_exposure_invariants.csv")[0]
    assert invariants["no_prices_forward_filled"] == "true"
    assert invariants["holds_only_SPY_or_TLT_after_initialization"] == "true"
    assert read_json("consistency_check.json")["no_prices_forward_filled"] is True
    assert read_json("consistency_check.json")["strategy_holds_only_SPY_or_TLT_after_initialization"] is True


def test_exposure_never_exceeds_1() -> None:
    invariants = read_csv("accounting_timing_and_exposure_invariants.csv")[0]
    assert float(invariants["maximum_exposure"]) <= 1.000001
    assert float(invariants["maximum_weight_sum"]) <= 1.000001
    assert invariants["exposure_never_exceeds_1"] == "true"


def test_turnover_uses_actual_pretrade_holdings() -> None:
    invariants = read_csv("accounting_timing_and_exposure_invariants.csv")[0]
    assert invariants["turnover_uses_actual_pretrade_holdings"] == "true"
    assert read_json("consistency_check.json")["turnover_uses_actual_pretrade_holdings"] is True


def test_windows_are_frozen_before_performance() -> None:
    for filename in ("frozen_chronological_blocks.csv", "frozen_180d_windows.csv", "frozen_252d_windows.csv"):
        rows = read_csv(filename)
        assert rows
        assert all(row["frozen_before_performance"] == "true" for row in rows)
    assert read_json("consistency_check.json")["windows_frozen_before_performance"] is True


def test_spy200d_is_control_not_signal_and_no_bil_or_gold_overlay() -> None:
    prereg = read_json("source_and_preregistration.json")
    assert prereg["frozen_rules"]["BIL_fallback"] is False
    assert prereg["frozen_rules"]["gold_overlay"] is False
    check = read_json("consistency_check.json")
    assert check["SPY_200d_control_not_signal"] is True
    assert check["no_BIL_fallback_or_gold_overlay"] is True


def test_vm_dsr_usci_and_active_combo_remain_unchanged_no_orders_created() -> None:
    invariants = read_csv("accounting_timing_and_exposure_invariants.csv")[0]
    assert invariants["VM_DSR_USCI_active_combo_states_unchanged"] == "true"
    assert invariants["paper_demo_observation_created"] == "false"
    assert invariants["broker_order_created"] == "false"
    assert read_json("consistency_check.json")["VM_DSR_USCI_active_combo_states_unchanged"] is True
    assert read_json("consistency_check.json")["no_paper_demo_observation_or_broker_order"] is True


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


def test_outcome_is_single_frozen_allowed_label() -> None:
    outcome = read_json("screening_outcome.json")
    assert outcome["outcome"] in screen.ALLOWED_OUTCOMES
    assert outcome["promotion_authorized"] is False
    assert outcome["paper_demo_authorized"] is False
    assert outcome["candidate_exhaustive_authorized"] is False
    memory = read_csv("exact_variant_research_memory.csv")[0]
    assert memory["broader_macro_duration_risk_off_rotation_family_closed"] == "false"
