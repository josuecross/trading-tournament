from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from strategy_lab.research_os.universe_expansion import paired_switching_13w_risky_tlt_portability_v1 as paired


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "paired_switching_13w_risky_tlt_portability_v1" / "latest"
REGISTRY = ROOT / "strategy_lab" / "strategy_registry.yaml"
ACTIVE_OBSERVATIONS = ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml"


@pytest.fixture(scope="module", autouse=True)
def generated_paired_switching() -> dict[str, object]:
    return paired.run()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def to_float(value: str) -> float:
    return float(value)


def synthetic_weekly(risky: list[float], tlt: list[float]) -> pd.DataFrame:
    index = pd.date_range("2020-01-03", periods=len(risky), freq="W-FRI")
    return pd.DataFrame({"risky": risky, paired.DEFENSIVE_ANCHOR: tlt, "anchor": tlt}, index=index)


def synthetic_common_index() -> pd.DatetimeIndex:
    return pd.bdate_range("2020-01-01", "2020-08-31")


def test_required_outputs_exist() -> None:
    for name in paired.OUTPUT_FILES:
        assert (EVIDENCE / name).exists(), name


def test_prior_universe_and_faber_packets_remain_byte_identical() -> None:
    payload = read_json(EVIDENCE / "pilot_universe_hash_verification.json")
    assert payload["protected_packets_byte_identical"] is True
    assert payload["protected_before"] == payload["protected_after"]
    assert read_json(EVIDENCE / "consistency_check.json")["protected_packets_byte_identical"] is True


def test_only_frozen_29_risky_tlt_pairs_are_used() -> None:
    inventory = read_csv(EVIDENCE / "frozen_pair_inventory.csv")
    assert len(inventory) == 29
    assert [row["risky_symbol"] for row in inventory] == list(paired.RISKY_INSTRUMENTS)
    assert {row["anchor_symbol"] for row in inventory} == {"TLT"}
    assert read_json(EVIDENCE / "consistency_check.json")["only_frozen_29_risky_tlt_pairs_used"] is True


def test_tlt_is_only_defensive_anchor() -> None:
    for name in [
        "frozen_pair_inventory.csv",
        "exact_pair_trial_ledger.csv",
        "formation_pair_results.csv",
        "validation_pair_results.csv",
        "frozen_signal_cycles.csv",
    ]:
        rows = read_csv(EVIDENCE / name)
        assert {row["anchor_symbol"] for row in rows if "anchor_symbol" in row} == {"TLT"}
    assert read_json(EVIDENCE / "consistency_check.json")["defensive_anchor"] == "TLT"


def test_no_correlation_or_performance_field_selects_pair() -> None:
    inventory = read_csv(EVIDENCE / "frozen_pair_inventory.csv")
    corr = read_csv(EVIDENCE / "correlation_diagnostics.csv")
    assert {row["correlation_screen_used_for_inclusion"] for row in inventory} == {"false"}
    assert {row["performance_screen_used_for_inclusion"] for row in inventory} == {"false"}
    assert {row["used_for_pair_inclusion"] for row in corr} == {"false"}
    assert {row["used_for_family_outcome"] for row in corr} == {"false"}


def test_source_example_anchors_tagged() -> None:
    anchors = read_csv(EVIDENCE / "source_example_anchor_review.csv")
    assert {row["risky_symbol"] for row in anchors} == {"SPY", "EFA"}
    assert {row["source_example_anchor"] for row in anchors} == {"true"}
    assert {row["retained_in_exact_trial_ledger"] for row in anchors} == {"true"}


def test_source_anchors_recorded_but_excluded_from_independent_aggregates() -> None:
    classes = read_csv(EVIDENCE / "pair_classifications.csv")
    for symbol in ("SPY", "EFA"):
        row = [item for item in classes if item["risky_symbol"] == symbol][0]
        assert row["source_example_anchor"] == "true"
        assert row["counts_as_independent_family_evidence"] == "false"
    assert len([row for row in classes if row["counts_as_independent_family_evidence"] == "true"]) == 27
    assert read_json(EVIDENCE / "family_outcome.json")["independent_decision_pair_count"] == 27


def test_parameter_is_exactly_thirteen_weekly_observations() -> None:
    source = read_json(EVIDENCE / "source_and_preregistration.json")
    assert source["frozen_rule"]["ranking_period_weeks"] == 13
    assert source["frozen_rule"]["repositioning_frequency_weeks"] == 13
    assert {row["lookback_gap_weekly_observations"] for row in read_csv(EVIDENCE / "frozen_signal_cycles.csv")} == {"13"}
    assert read_json(EVIDENCE / "consistency_check.json")["lookback_weeks"] == 13


def test_signals_occur_only_every_thirteen_weeks() -> None:
    rows = read_csv(EVIDENCE / "frozen_signal_cycles.csv")
    by_pair: dict[str, list[int]] = {}
    for row in rows:
        by_pair.setdefault(row["pair_id"], []).append(int(row["signal_weekly_observation_ordinal"]))
    for positions in by_pair.values():
        assert min(positions) >= 13
        assert set(np.diff(sorted(positions))) <= {13}


def test_preceding_thirteen_week_return_is_used() -> None:
    signals = read_csv(EVIDENCE / "frozen_signal_cycles.csv")
    weekly = read_csv(EVIDENCE / "frozen_weekly_observations.csv")
    sample = [row for row in signals if row["pair_id"] == "QQQ_TLT_13w_pair_switch"][0]
    current = [
        row for row in weekly
        if row["pair_id"] == sample["pair_id"]
        and row["weekly_observation_ordinal"] == sample["signal_weekly_observation_ordinal"]
    ][0]
    lag = [
        row for row in weekly
        if row["pair_id"] == sample["pair_id"]
        and row["weekly_observation_ordinal"] == sample["lookback_weekly_observation_ordinal"]
    ][0]
    expected_risky = to_float(current["risky_adjusted_close"]) / to_float(lag["risky_adjusted_close"]) - 1.0
    expected_tlt = to_float(current["tlt_adjusted_close"]) / to_float(lag["tlt_adjusted_close"]) - 1.0
    assert to_float(sample["risky_return_13w"]) == pytest.approx(expected_risky)
    assert to_float(sample["tlt_return_13w"]) == pytest.approx(expected_tlt)


def test_signal_week_ends_before_execution_and_same_close_impossible() -> None:
    rows = read_csv(EVIDENCE / "frozen_execution_dates.csv")
    assert rows
    assert all(pd.Timestamp(row["signal_week_end_date"]) < pd.Timestamp(row["execution_date"]) for row in rows)
    assert {row["same_close_execution"] for row in rows} == {"false"}


def test_higher_risky_return_selects_risky() -> None:
    weekly = synthetic_weekly([100.0] * 13 + [120.0], [100.0] * 14)
    schedule = paired.build_pair_schedule("TEST", weekly, synthetic_common_index(), weekly.index[13])
    assert schedule.signal_rows[0]["signal_status"] == "risky_higher_13w_return_select_risky"
    assert schedule.signal_rows[0]["target_risky_weight"] == 1.0
    assert schedule.signal_rows[0]["target_tlt_weight"] == 0.0


def test_higher_tlt_return_selects_tlt() -> None:
    weekly = synthetic_weekly([100.0] * 14, [100.0] * 13 + [120.0])
    schedule = paired.build_pair_schedule("TEST", weekly, synthetic_common_index(), weekly.index[13])
    assert schedule.signal_rows[0]["signal_status"] == "tlt_higher_13w_return_select_tlt"
    assert schedule.signal_rows[0]["target_risky_weight"] == 0.0
    assert schedule.signal_rows[0]["target_tlt_weight"] == 1.0


def test_equal_returns_retain_current_holding() -> None:
    risky = [100.0] * 13 + [120.0] + [120.0] * 12 + [132.0]
    tlt = [100.0] * 14 + [100.0] * 12 + [110.0]
    weekly = synthetic_weekly(risky, tlt)
    schedule = paired.build_pair_schedule("TEST", weekly, synthetic_common_index(), weekly.index[13])
    assert schedule.signal_rows[1]["signal_status"] == "equal_returns_retain_current_holding"
    assert schedule.execution_rows[-1]["target_unchanged_no_trade"] is True
    assert schedule.execution_rows[-1]["trade_required"] is False


def test_missing_data_retain_current_holding() -> None:
    risky = [100.0] * 13 + [120.0] + [120.0] * 12 + [float("nan")]
    tlt = [100.0] * 27
    weekly = synthetic_weekly(risky, tlt)
    schedule = paired.build_pair_schedule("TEST", weekly, synthetic_common_index(), weekly.index[13])
    assert schedule.signal_rows[1]["signal_status"] == "invalid_cycle_retain_current_holding"
    assert schedule.skipped_rows[-1]["retained_current_holding"] is True
    assert schedule.skipped_rows[-1]["trade_generated"] is False


def test_no_prices_forward_filled_or_pre_inception_used() -> None:
    weekly = read_csv(EVIDENCE / "frozen_weekly_observations.csv")
    invariants = read_csv(EVIDENCE / "accounting_timing_data_and_exposure_invariants.csv")
    assert {row["forward_filled"] for row in weekly} == {"false"}
    assert {row["pre_inception_backfill"] for row in weekly} == {"false"}
    assert {row["no_forward_filled_prices"] for row in invariants} == {"true"}
    assert {row["no_pre_inception_data_used"] for row in invariants} == {"true"}


def test_candidate_holds_only_one_pair_member_after_initialization() -> None:
    invariants = read_csv(EVIDENCE / "accounting_timing_data_and_exposure_invariants.csv")
    assert {row["candidate_holds_exactly_one_member_after_initialization"] for row in invariants} == {"true"}


def test_exposure_never_exceeds_one() -> None:
    check = read_json(EVIDENCE / "consistency_check.json")
    invariants = read_csv(EVIDENCE / "accounting_timing_data_and_exposure_invariants.csv")
    assert check["max_exposure"] <= 1.000001
    assert check["max_weight_sum"] <= 1.000001
    assert check["exposure_invariants_passed"] is True
    assert all(to_float(row["max_exposure"]) <= 1.000001 for row in invariants)
    assert all(to_float(row["max_weight_sum"]) <= 1.000001 for row in invariants)


def test_static_50_50_benchmark_weights_drift_between_rebalances() -> None:
    invariants = read_csv(EVIDENCE / "accounting_timing_data_and_exposure_invariants.csv")
    assert {row["static_50_50_benchmark_weights_drift_between_rebalances"] for row in invariants} == {"true"}


def test_benchmark_turnover_uses_actual_pre_rebalance_holdings() -> None:
    invariants = read_csv(EVIDENCE / "accounting_timing_data_and_exposure_invariants.csv")
    costs = read_csv(EVIDENCE / "cost_and_turnover_metrics.csv")
    assert {row["benchmark_turnover_uses_actual_pre_rebalance_holdings"] for row in invariants} == {"true"}
    assert {row["turnover_basis"] for row in costs} == {"0.5 * abs(new target - pre-trade actual holdings)"}


def test_every_pair_remains_in_trial_ledger() -> None:
    ledger = read_csv(EVIDENCE / "exact_pair_trial_ledger.csv")
    assert len(ledger) == 29
    assert [row["risky_symbol"] for row in ledger] == list(paired.RISKY_INSTRUMENTS)
    assert {row["record_retained_even_if_success_fail_error_or_excluded"] for row in ledger} == {"true"}


def test_secondary_benchmark_rows_cannot_alter_family_outcome() -> None:
    primary = [
        row for row in read_csv(EVIDENCE / "primary_benchmark_relative_metrics.csv")
        if row["period"] == "validation" and row["benchmark"] == paired.PRIMARY_BENCHMARK and row["counts_as_independent_family_evidence"] == "true"
    ]
    secondary = read_csv(EVIDENCE / "secondary_benchmark_diagnostics.csv")
    outcome = read_json(EVIDENCE / "family_outcome.json")
    assert len(primary) == 27
    assert {row["benchmark_population_role"] for row in secondary} == {"secondary_diagnostic_only"}
    assert outcome["median_validation_excess_total_return"] == pytest.approx(float(np.median([to_float(row["excess_total_return"]) for row in primary])))
    assert outcome["median_validation_canonical_drawdown_improvement"] == pytest.approx(float(np.median([to_float(row["canonical_drawdown_improvement"]) for row in primary])))


def test_no_alternative_lookback_or_anchor_calculated() -> None:
    check = read_json(EVIDENCE / "consistency_check.json")
    signals = read_csv(EVIDENCE / "frozen_signal_cycles.csv")
    assert check["no_alternative_lookback_or_anchor_calculated"] is True
    assert {row["no_parameter_alternative"] for row in signals} == {"true"}


def test_no_winning_pair_or_group_selected() -> None:
    check = read_json(EVIDENCE / "consistency_check.json")
    outcome = read_json(EVIDENCE / "family_outcome.json")
    assert check["winning_pair_selected"] is False
    assert check["winning_group_selected"] is False
    assert outcome["winning_pair_selected"] is False
    assert outcome["winning_group_selected"] is False


def test_holdout_dates_frozen_but_holdout_performance_not_calculated() -> None:
    sealed = read_json(EVIDENCE / "sealed_holdout_manifest.json")
    outcome = read_json(EVIDENCE / "family_outcome.json")
    assert sealed["holdout_start"] == "2022-01-03"
    assert sealed["holdout_end"] == "2026-07-16"
    assert sealed["holdout_performance_calculated"] is False
    assert outcome["holdout_performance_calculated"] is False


def test_no_holdout_result_file_exists() -> None:
    names = {path.name for path in EVIDENCE.iterdir() if path.is_file()}
    assert not any(name.startswith("holdout_") for name in names)
    assert "sealed_holdout_manifest.json" in names


def test_active_observations_and_registry_remain_unchanged() -> None:
    before = {REGISTRY: sha256(REGISTRY), ACTIVE_OBSERVATIONS: sha256(ACTIVE_OBSERVATIONS)}
    result = paired.run()
    after = {REGISTRY: sha256(REGISTRY), ACTIVE_OBSERVATIONS: sha256(ACTIVE_OBSERVATIONS)}
    assert result["consistency_passed"] is True
    assert before == after
    check = read_json(EVIDENCE / "consistency_check.json")
    assert check["registry_byte_identical"] is True
    assert check["active_observations_byte_identical"] is True


def test_output_generation_is_deterministic() -> None:
    before = {path.name: sha256(path) for path in sorted(EVIDENCE.iterdir()) if path.is_file()}
    paired.run()
    after = {path.name: sha256(path) for path in sorted(EVIDENCE.iterdir()) if path.is_file()}
    assert before == after


def test_family_outcome_and_next_action_are_exact() -> None:
    outcome = read_json(EVIDENCE / "family_outcome.json")
    memory = read_csv(EVIDENCE / "exact_family_trial_research_memory.csv")[0]
    assert outcome["primary_outcome"] == "failed_distribution"
    assert outcome["next_action"] == "direction_owner_review_second_portability_batch_v1"
    assert outcome["recorded_pair_trials"] == 29
    assert outcome["independent_decision_pair_count"] == 27
    assert outcome["groups_passed_validation"] == 0
    assert outcome["median_validation_excess_total_return"] == pytest.approx(-0.1540820730917012)
    assert outcome["median_validation_canonical_drawdown_improvement"] == pytest.approx(-0.2164746702454743)
    assert memory["broader_family_preserved"] == "true"
    assert memory["exact_source_rule_closed_if_failed"] == "true"
