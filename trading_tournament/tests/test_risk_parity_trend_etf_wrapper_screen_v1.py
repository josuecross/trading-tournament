from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd
import pytest

from strategy_lab.research_os.research import risk_parity_trend_etf_wrapper_screen_v1 as screen


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "risk_parity_trend_etf_wrapper_screen_v1" / "latest"


@pytest.fixture(scope="module", autouse=True)
def generated_screen_evidence() -> dict[str, object]:
    return screen.run()


def read_json(name: str) -> dict[str, object]:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def read_csv(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_required_artifacts_exist() -> None:
    required = {
        "execution_manifest.json",
        "screening_summary.md",
        "candidate_metrics.csv",
        "benchmark_metrics.csv",
        "benchmark_relative_deltas.csv",
        "window_level_results.csv",
        "daily_path_and_weights.csv",
        "monthly_signal_and_weight_audit.csv",
        "exposure_and_weight_invariants.csv",
        "source_adaptation_caveats.md",
        "screening_outcome.json",
        "exact_variant_research_memory.csv",
        "artifact_lineage.csv",
        "screening_consistency_check.json",
    }
    missing = sorted(name for name in required if not (EVIDENCE / name).exists())
    assert missing == []


def test_manifest_freezes_preregistered_scope_and_guardrails() -> None:
    manifest = read_json("execution_manifest.json")
    assert manifest["candidate_id"] == screen.CANDIDATE_ID
    assert manifest["source_id"] == screen.SOURCE_ID
    assert manifest["family_id"] == screen.FAMILY_ID
    assert manifest["risky_assets"] == list(screen.RISKY_ASSETS)
    assert manifest["risk_off_asset"] == screen.RISK_OFF_ASSET
    assert manifest["no_provider_calls"] is True
    assert manifest["no_parameter_wrapper_universe_or_window_search"] is True
    assert manifest["no_robustness_run"] is True
    assert manifest["no_candidate_exhaustive_run"] is True
    assert manifest["no_promotion_or_paper_demo_state_change"] is True
    assert manifest["no_lifecycle_or_paper_demo_state_change"] is True
    assert manifest["initial_capital"] == pytest.approx(3000.0)
    assert manifest["stop_threshold_dollars"] == pytest.approx(-600.0)
    assert manifest["target_300_dollars"] == pytest.approx(300.0)
    assert manifest["target_400_dollars"] == pytest.approx(400.0)
    assert manifest["slippage_assumption"] == pytest.approx(0.0005)
    assert manifest["volatility_window_months"] == 12
    assert manifest["volatility_ddof"] == 1
    assert manifest["trend_window_months"] == 10


def test_cache_hash_lineage_matches_preregistration() -> None:
    rows = read_csv("artifact_lineage.csv")
    cache_rows = [row for row in rows if row["artifact_type"] == "cache_file"]
    assert {row["artifact_id"] for row in cache_rows} == set(screen.FROZEN_UNIVERSE)
    assert all(row["hash_match"] == "true" for row in cache_rows)
    assert all(row["path"].startswith("data/cache/") for row in cache_rows)


def test_inverse_volatility_weights_are_deterministic_and_normalized() -> None:
    monthly_returns = pd.DataFrame(
        {
            "URTH": [0.01, 0.02, -0.01, 0.015, 0.004, -0.006, 0.012, 0.018, -0.004, 0.01, 0.02, 0.003],
            "EEM": [0.02, -0.01, 0.01, 0.025, -0.014, 0.016, 0.02, -0.018, 0.024, 0.01, -0.02, 0.013],
            "IGOV": [0.003, 0.001, -0.002, 0.004, 0.002, -0.001, 0.003, 0.002, -0.004, 0.001, 0.002, 0.003],
            "DBC": [0.03, -0.02, 0.04, -0.025, 0.02, -0.015, 0.018, 0.022, -0.03, 0.011, -0.01, 0.02],
            "REET": [0.012, -0.009, 0.016, 0.004, -0.005, 0.011, -0.003, 0.014, 0.006, -0.002, 0.008, 0.015],
        }
    )
    weights = screen.inverse_volatility_weights(monthly_returns)
    assert list(weights) == list(screen.RISKY_ASSETS)
    assert sum(weights.values()) == pytest.approx(1.0)
    assert all(weight > 0 for weight in weights.values())


def test_inverse_volatility_rejects_zero_volatility() -> None:
    monthly_returns = pd.DataFrame({asset: [0.01] * 12 for asset in screen.RISKY_ASSETS})
    with pytest.raises(ValueError):
        screen.inverse_volatility_weights(monthly_returns)


def test_trend_filter_is_strict_and_equality_is_risk_off() -> None:
    closes = pd.Series([10.0] * 10)
    assert screen.strict_trend_on(10.0, closes) is False
    assert screen.strict_trend_on(10.01, closes) is True


def test_monthly_signal_audit_proves_rule_components() -> None:
    rows = read_csv("monthly_signal_and_weight_audit.csv")
    assert rows
    assert all(row["volatility_return_count"] == "12" for row in rows)
    assert all(row["volatility_ddof"] == "1" for row in rows)
    assert all(row["trend_price_count"] == "10" for row in rows)
    assert all(float(row["pre_filter_weight_sum"]) == pytest.approx(1.0) for row in rows)
    assert all(float(row["post_filter_weight_sum"]) == pytest.approx(1.0) for row in rows)
    assert all(float(row["bil_weight"]) == pytest.approx(float(row["bil_transfer_weight"])) for row in rows)
    assert any(row["mixed_risky_bil_allocation"] == "true" for row in rows)
    assert all(pd.Timestamp(row["signal_date"]) < pd.Timestamp(row["execution_date"]) for row in rows)


def test_daily_path_weight_invariants_and_zero_weights() -> None:
    rows = read_csv("daily_path_and_weights.csv")
    assert rows
    assert max(abs(float(row["weight_sum"]) - 1.0) for row in rows) <= 1e-8
    assert max(float(row["gross_exposure"]) for row in rows) <= 1.000001
    assert min(min(float(row[f"{asset}_weight"]) for asset in screen.FROZEN_UNIVERSE) for row in rows) >= -1e-12
    assert any(float(row[f"{asset}_weight"]) == pytest.approx(0.0) for row in rows for asset in screen.RISKY_ASSETS)
    assert any(float(row["BIL_weight"]) > 0.0 and float(row["risky_exposure"]) > 0.0 for row in rows)


def test_execution_dates_match_audit_weights_without_stale_fill() -> None:
    daily = {row["date"]: row for row in read_csv("daily_path_and_weights.csv")}
    for row in read_csv("monthly_signal_and_weight_audit.csv")[:12]:
        daily_row = daily[row["execution_date"]]
        for asset in screen.FROZEN_UNIVERSE:
            assert float(daily_row[f"{asset}_target_weight"]) == pytest.approx(float(row[f"{asset}_final_weight"]))
            assert float(daily_row[f"{asset}_post_trade_weight"]) == pytest.approx(float(row[f"{asset}_final_weight"]))


def test_frozen_sampled_windows_are_exact_and_valid() -> None:
    windows = read_csv("window_level_results.csv")
    candidate = [row for row in windows if row["strategy_id"] == screen.CANDIDATE_ID]
    assert len(candidate) == 10
    expected = {
        ("90", "2016-07-11", "2016-11-15"),
        ("90", "2018-11-28", "2019-04-10"),
        ("90", "2021-04-22", "2021-08-30"),
        ("90", "2023-09-13", "2024-01-23"),
        ("90", "2026-02-09", "2026-06-18"),
        ("180", "2016-07-11", "2017-03-28"),
        ("180", "2018-10-25", "2019-07-17"),
        ("180", "2021-02-17", "2021-11-02"),
        ("180", "2023-06-07", "2024-02-26"),
        ("180", "2025-09-30", "2026-06-18"),
    }
    actual = {(row["horizon_days"], row["window_start"], row["window_end"]) for row in candidate}
    assert actual == expected
    assert all(row["window_valid"] == "true" for row in candidate)


def test_all_required_benchmarks_are_present() -> None:
    rows = read_csv("benchmark_metrics.csv")
    assert {row["strategy_id"] for row in rows} == set(screen.BENCHMARK_IDS)
    assert all(row["benchmark_reference_only"] == "true" for row in rows)


def test_screening_outcome_is_diagnostic_not_promotional() -> None:
    outcome = read_json("screening_outcome.json")
    assert outcome["candidate_id"] == screen.CANDIDATE_ID
    assert outcome["promotion_authorized"] is False
    assert outcome["paper_demo_authorized"] is False
    assert outcome["candidate_exhaustive_authorized"] is False
    assert outcome["next_action"] in {
        "audit_risk_parity_trend_etf_wrapper_screen_v1",
        "mark_risk_parity_trend_etf_wrapper_screen_v1_control_weak",
        "fix_risk_parity_trend_etf_wrapper_screen_v1_methodology_issue",
        "manual_review_required_after_risk_parity_trend_screen",
        "direction_owner_decide_focus_robustness_or_close_exact_variant",
    }


def test_consistency_check_passes() -> None:
    check = read_json("screening_consistency_check.json")
    assert check["consistency_passed"] is True
    assert check["cache_hashes_match_preregistration"] is True
    assert check["all_invariants_passed"] is True
    assert check["candidate_windows_valid"] is True


def test_generation_is_deterministic() -> None:
    first = read_json("screening_outcome.json")
    rerun = screen.run()
    second = read_json("screening_outcome.json")
    assert rerun["consistency_passed"] is True
    assert second == first
