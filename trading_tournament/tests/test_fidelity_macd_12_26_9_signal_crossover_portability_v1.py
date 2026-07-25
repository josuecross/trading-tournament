from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd

from strategy_lab.research_os.research.fidelity_macd_12_26_9_signal_crossover_portability_v1 import (
    FAST_EMA_PERIOD,
    FAMILY_ID,
    MAX_TRIALS,
    NEXT_ACTION,
    OUTPUT_DIR,
    SIGNAL_EMA_PERIOD,
    SLOW_EMA_PERIOD,
    STRATEGY_ID,
    crossover_events,
    deterministic_core_hash,
    macd_components,
    run,
    sma_seeded_ema,
    targets_from_events,
)


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / OUTPUT_DIR


def load_json(name: str) -> dict:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def csv_rows(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def bool_text(value: str) -> bool:
    return value == "True"


def unique_in_order(values: list[str]) -> list[str]:
    out: list[str] = []
    for value in values:
        if value not in out:
            out.append(value)
    return out


def test_required_artifacts_and_task_contract() -> None:
    required = [
        "source_packet_used.yaml",
        "repository_fit_check.json",
        "frozen_universe_reference.json",
        "frozen_trial_manifest.csv",
        "canonical_family_representative.json",
        "trial_registry.csv",
        "data_coverage.csv",
        "ema_initialization_audit.csv",
        "signal_calculation_audit.csv",
        "target_weights.csv",
        "transactions.csv",
        "baseline_metrics.csv",
        "control_metrics.csv",
        "baseline_vs_controls.csv",
        "timeframe_diagnostics.csv",
        "accounting_invariants.csv",
        "row_outcomes.csv",
        "family_outcome.json",
        "family_followup_queue.csv",
        "command_validation_log.csv",
        "consistency_check.json",
        "implementation_summary.md",
    ]
    for name in required:
        assert (EVIDENCE / name).exists(), name
    consistency = load_json("consistency_check.json")
    assert consistency["task_outcome"] == "macd_fast_lane_batch_complete"
    assert consistency["strategy_id"] == STRATEGY_ID
    assert consistency["family_id"] == FAMILY_ID
    assert consistency["consistency_passed"] is True
    assert consistency["next_action"] == NEXT_ACTION


def test_ema_periods_and_sma_seed_initialization() -> None:
    assert (FAST_EMA_PERIOD, SLOW_EMA_PERIOD, SIGNAL_EMA_PERIOD) == (12, 26, 9)
    index = pd.date_range("2020-01-01", periods=60, freq="D")
    close = pd.Series([float(i) for i in range(1, 61)], index=index)
    fast = sma_seeded_ema(close, FAST_EMA_PERIOD)
    slow = sma_seeded_ema(close, SLOW_EMA_PERIOD)
    components = macd_components(close)

    assert fast.first_valid_index() == index[FAST_EMA_PERIOD - 1]
    assert slow.first_valid_index() == index[SLOW_EMA_PERIOD - 1]
    assert fast.loc[index[FAST_EMA_PERIOD - 1]] == close.iloc[:FAST_EMA_PERIOD].mean()
    assert slow.loc[index[SLOW_EMA_PERIOD - 1]] == close.iloc[:SLOW_EMA_PERIOD].mean()
    macd_valid = components["macd"].dropna()
    first_signal_date = components["signal"].first_valid_index()
    assert first_signal_date == macd_valid.index[SIGNAL_EMA_PERIOD - 1]
    assert components.loc[first_signal_date, "signal"] == macd_valid.iloc[:SIGNAL_EMA_PERIOD].mean()


def test_bullish_bearish_crossovers_and_state_persistence() -> None:
    index = pd.date_range("2020-01-01", periods=6, freq="D")
    macd = pd.Series([float("nan"), 0.5, 1.2, 1.1, 0.4, 0.7], index=index)
    signal = pd.Series([float("nan"), 1.0, 1.0, 1.0, 0.8, 0.8], index=index)
    events = crossover_events(macd, signal)
    weights = targets_from_events("SPY", events)

    assert bool(events.loc[index[2], "bullish_cross"]) is True
    assert bool(events.loc[index[4], "bearish_cross"]) is True
    assert bool(events["bullish_cross"].sum() == 1)
    assert bool(events["bearish_cross"].sum() == 1)
    assert weights.loc[index[0], ["SPY", "BIL"]].sum() == 0.0
    assert weights.loc[index[1], ["SPY", "BIL"]].sum() == 0.0
    assert weights.loc[index[2], "SPY"] == 1.0
    assert weights.loc[index[3], "SPY"] == 1.0
    assert weights.loc[index[4], "BIL"] == 1.0
    assert weights.loc[index[5], "BIL"] == 1.0


def test_selection_is_performance_independent_and_capped() -> None:
    manifest = csv_rows("frozen_trial_manifest.csv")
    representative = load_json("canonical_family_representative.json")
    selected_symbols = unique_in_order([row["symbol"] for row in manifest])
    group_counts: dict[str, int] = {}
    for row in manifest:
        group_counts[row["candidate_group"]] = group_counts.get(row["candidate_group"], 0) + 1

    assert selected_symbols == ["SPY", "XLK", "EFA", "SHY", "GLD", "IYR"]
    assert len(manifest) <= MAX_TRIALS
    assert all(count <= 1 for count in group_counts.values())
    assert all(row["performance_used_for_selection"] == "False" for row in manifest)
    assert representative["canonical_representative_symbol"] == "SPY"
    assert representative["performance_used_for_selection"] is False


def test_every_trial_registered_once_and_no_alternative_parameters() -> None:
    manifest = csv_rows("frozen_trial_manifest.csv")
    registry = csv_rows("trial_registry.csv")
    outcomes = csv_rows("row_outcomes.csv")

    assert {row["trial_id"] for row in manifest} == {row["trial_id"] for row in registry} == {row["trial_id"] for row in outcomes}
    assert len(manifest) == len(registry) == len(outcomes) == 6
    assert all(row["fast_ema_period"] == "12" for row in manifest)
    assert all(row["slow_ema_period"] == "26" for row in manifest)
    assert all(row["signal_ema_period"] == "9" for row in manifest)
    assert all(row["frozen_before_return_calculation"] == "True" for row in manifest)
    assert all(row["trial_registered_before_returns"] == "True" for row in registry)


def test_weight_exclusivity_no_pre_crossover_target_and_shifted_execution() -> None:
    invariants = csv_rows("accounting_invariants.csv")
    ema = csv_rows("ema_initialization_audit.csv")
    sample_targets = csv_rows("target_weights.csv")

    assert all(row["pre_first_crossover_no_position"] == "True" for row in invariants)
    assert all(abs(float(row["pre_first_crossover_target_weight_sum"])) <= 1e-12 for row in ema)
    assert all(row["same_bar_execution_impossible"] == "True" for row in invariants)
    assert all(row["post_initialization_weight_sum_exact_1"] == "True" for row in invariants)
    assert all(row["only_risky_or_bil_held"] == "True" for row in invariants)
    assert all(row["no_lookahead_status"] == "shifted_weight_returns_from_completed_daily_bars" for row in invariants)
    for row in sample_targets[:1000]:
        risky = float(row["risky_weight"])
        bil = float(row["bil_weight"])
        assert not (risky > 0.0 and bil > 0.0)
        assert abs((risky + bil) - float(row["weight_sum"])) <= 1e-12


def test_costs_are_recorded_only_on_state_changes() -> None:
    transactions = csv_rows("transactions.csv")
    baselines = {row["trial_id"]: row for row in csv_rows("baseline_metrics.csv")}
    counts: dict[str, int] = {}
    for row in transactions:
        counts[row["trial_id"]] = counts.get(row["trial_id"], 0) + 1
        assert row["cost_applied_once_for_state_change"] == "True"
        assert float(row["turnover_proxy"]) > 0.0
        assert float(row["cost_return_deduction"]) == float(row["turnover_proxy"]) * float(row["cost_rate"])
    for trial_id, baseline in baselines.items():
        assert counts.get(trial_id, 0) == int(baseline["trade_count"])


def test_static_controls_calendar_outcomes_and_non_promotional_flags() -> None:
    controls = csv_rows("control_metrics.csv")
    invariants = csv_rows("accounting_invariants.csv")
    rows = csv_rows("row_outcomes.csv")
    family = load_json("family_outcome.json")
    control_ids_by_trial: dict[str, set[str]] = {}
    for row in controls:
        control_ids_by_trial.setdefault(row["trial_id"], set()).add(row["control_id"])

    assert all(row["static_control_same_calendar"] == "True" for row in invariants)
    assert all(ids == {"risky_buy_hold", "BIL_buy_hold", "static_average_exposure_control", "macd_zero_cost_accounting_diagnostic"} for ids in control_ids_by_trial.values())
    assert all(row["row_outcome_allowed"] == "True" for row in rows)
    assert all(row["promotion_eligibility"] == "False" for row in rows)
    assert all(row["paper_forward_eligibility"] == "False" for row in rows)
    assert all(row["candidate_exhaustive_eligibility"] == "False" for row in rows)
    assert family["family_outcome_allowed"] is True
    assert family["promotion_eligibility"] is False
    assert family["paper_forward_eligibility"] is False
    assert family["candidate_exhaustive_eligibility"] is False


def test_no_overlay_registry_paper_broker_or_provider_state_changes() -> None:
    consistency = load_json("consistency_check.json")
    artifact_names = {path.name.lower() for path in EVIDENCE.iterdir()}

    assert consistency["no_alternative_parameters_generated"] is True
    assert consistency["no_overlay_output_produced"] is True
    assert all("overlay" not in name for name in artifact_names)
    assert consistency["registry_lifecycle_unchanged"] is True
    assert consistency["active_paper_demo_state_unchanged"] is True
    assert consistency["broker_or_order_path_touched"] is False
    assert consistency["provider_download"] is False
    assert consistency["intraday_data_used"] is False
    assert consistency["paper_forward_activation"] is False
    assert consistency["promotion_candidates_created"] is False
    assert consistency["candidate_exhaustive_run"] is False
    assert consistency["real_money_recommendation"] is False


def test_generation_is_deterministic_for_core_outputs() -> None:
    before = load_json("consistency_check.json")["deterministic_core_hash"]
    result = run(ROOT)
    after = load_json("consistency_check.json")["deterministic_core_hash"]
    assert result["consistency_passed"] is True
    assert before == after
    assert after == deterministic_core_hash(EVIDENCE)
