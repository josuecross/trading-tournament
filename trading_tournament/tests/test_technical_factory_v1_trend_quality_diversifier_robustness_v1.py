from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import technical_strategy_factory_v1 as factory
from strategy_lab.research_os.research import (
    technical_factory_v1_trend_quality_diversifier_robustness_v1 as subject,
)


OUTPUT = ROOT / "evidence" / "robustness" / subject.TASK_ID / "latest"


def rows(name: str) -> list[dict[str, str]]:
    with (OUTPUT / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_frozen_d1_contract() -> None:
    spec = subject.factory_spec()
    assert spec.strategy_id == subject.STRATEGY_ID
    assert spec.parameters == {"lookback_sessions": 60, "r2_threshold": 0.25}
    assert subject.STATIC_SPY_WEIGHT == 0.5391032325338895
    assert subject.STATIC_BIL_WEIGHT == 0.4608967674661105


def test_regression_formula_matches_direct_ols() -> None:
    x = np.arange(60, dtype=float)
    log_prices = 4.0 + 0.0015 * x + 0.01 * np.sin(x / 3.0)
    prices = np.exp(log_prices)
    annualized_slope, r_squared = factory.regression_state(prices)
    direct_slope, direct_intercept = np.polyfit(x, log_prices, 1)
    fitted = direct_intercept + direct_slope * x
    direct_r2 = 1.0 - float(np.square(log_prices - fitted).sum()) / float(
        np.square(log_prices - log_prices.mean()).sum()
    )
    assert math.isclose(annualized_slope, math.exp(direct_slope * 252.0) - 1.0, abs_tol=1e-12)
    assert math.isclose(r_squared, direct_r2, abs_tol=1e-12)


def test_required_output_set_is_exact() -> None:
    assert {path.name for path in OUTPUT.iterdir() if path.is_file()} == subject.REQUIRED_FILES


def test_exactly_one_robustness_child_trial() -> None:
    trial_rows = rows("trial_ledger.csv")
    assert len(trial_rows) == 1
    trial = trial_rows[0]
    assert trial["trial_id"] == subject.TRIAL_ID
    assert trial["parent_trial_id"] == subject.PARENT_TRIAL_ID
    assert trial["stage"] == "robustness"
    assert trial["adaptation_label"] == "robustness_variant"
    assert trial["unselected_variants_evaluated_on_final_segment"] == "false"


def test_parent_rows_and_route_booleans_reproduce() -> None:
    reproduction = rows("parent_reproduction_check.csv")
    assert reproduction
    assert {row["cost_bps_one_way"] for row in reproduction} == {"0.0", "5.0", "10.0"}
    assert all(row["pass"] == "true" for row in reproduction)


def test_original_fold_boundaries_and_final_access() -> None:
    fold_rows = rows("factory_fold_portfolio_results.csv")
    assert {row["period_id"] for row in fold_rows} == {"fold_1", "fold_2", "fold_3", "fold_4"}
    assert len(fold_rows) == 4 * len(subject.PORTFOLIO_IDS)
    final_rows = rows("development_final_segment_results.csv")
    assert {row["period_id"] for row in final_rows} == {
        "development_selection_period_intersection",
        "factory_final_evaluation_segment",
    }
    assert all(row["unselected_variant_access"] == "false" for row in final_rows)


def test_only_d1_strategy_identity_appears() -> None:
    forbidden = (
        "factory_v1_spy_trend_quality_state_d2",
        "factory_v1_spy_trend_quality_state_d3",
        "factory_v1_spy_trend_quality_state_d4",
    )
    payload = "\n".join(
        path.read_text(encoding="utf-8") for path in OUTPUT.iterdir() if path.suffix in {".csv", ".json", ".yaml", ".md"}
    )
    assert subject.STRATEGY_ID in payload
    assert not any(strategy_id in payload for strategy_id in forbidden)


def test_portfolio_definition_is_frozen() -> None:
    definition = rows("portfolio_definition_reconciliation.csv")
    assert len(definition) == 1
    row = definition[0]
    assert row["reference_weight"] == "0.8"
    assert row["sleeve_weight"] == "0.2"
    assert row["exposure_control_SPY_weight"] == "0.5391032325338895"
    assert row["exposure_weight_recalculated"] == "false"
    assert row["fixed_weight_daily_return_blend"] == "false"


def test_episode_inventory_is_ordered_nonoverlapping() -> None:
    inventory = rows("path_quality_filter_episode_inventory.csv")
    assert inventory
    prior_end: pd.Timestamp | None = None
    for row in inventory:
        start = pd.Timestamp(row["target_start_execution_date"])
        end = pd.Timestamp(row["target_end_date"])
        assert start <= end
        assert int(row["duration_sessions"]) >= 1
        if prior_end is not None:
            assert start > prior_end
        prior_end = end


def test_rolling_windows_retain_unfavorable_rows() -> None:
    for name, months in (("rolling_36_month_results.csv", "36"), ("rolling_60_month_results.csv", "60")):
        values = rows(name)
        assert values
        assert {row["window_months"] for row in values} == {months}
        assert all(row["unfavorable_window_retained"] == "true" for row in values)
        assert {row["comparison_portfolio_id"] for row in values} == {
            subject.REFERENCE_ID,
            subject.NAMED_ID,
            subject.STATIC_ID,
        }


def test_bootstrap_and_deterministic_invariants_pass() -> None:
    bootstrap = rows("paired_block_bootstrap_results.csv")
    assert len(bootstrap) == 3
    assert {row["resamples"] for row in bootstrap} == {"5000"}
    assert {row["deterministic_seed"] for row in bootstrap} == {"20260804"}
    invariants = {row["invariant_name"]: row["invariant_pass"] for row in rows("invariant_results.csv")}
    assert invariants["serial_path_rerun_deterministic"] == "true"
    assert invariants["paired_bootstrap_deterministic"] == "true"
    assert all(value == "true" for value in invariants.values())


def test_entity_counts_and_protected_state_reconcile() -> None:
    counts = json.loads((OUTPUT / "cohort_funnel_counts.json").read_text(encoding="utf-8"))
    assert counts["new_strategy_configurations"] == 0
    assert counts["new_robustness_trials"] == 1
    assert counts["paper_demo_observations"] == 0
    consistency = json.loads((OUTPUT / "consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["overall_pass"] is True
    assert consistency["protected_state_and_prior_evidence_unchanged"] is True
    assert consistency["D1_standalone_closure_changed"] is False


def test_outcome_and_next_action_are_allowed() -> None:
    manifest = yaml.safe_load((OUTPUT / "robustness_manifest.yaml").read_text(encoding="utf-8"))
    assert manifest["outcome"] in {
        "robustness_positive",
        "robustness_mixed",
        "robustness_failed",
        "robustness_blocked",
    }
    expected = {
        "robustness_positive": "onboard_technical_factory_v1_trend_quality_diversifier_paper_demo_v1",
        "robustness_mixed": "direction_owner_review_technical_factory_v1_after_d1_robustness_v1",
        "robustness_failed": "direction_owner_review_technical_factory_v1_after_d1_robustness_v1",
        "robustness_blocked": "direction_owner_review_technical_factory_v1_d1_robustness_block_v1",
    }
    assert manifest["exact_next_action"] == expected[manifest["outcome"]]
    report = (OUTPUT / "robustness_report.md").read_text(encoding="utf-8")
    assert "not independent validation" in report
    assert "No provider" in report
