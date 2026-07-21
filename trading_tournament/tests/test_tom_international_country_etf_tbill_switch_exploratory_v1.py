from __future__ import annotations

import ast
import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from strategy_lab.research_os.research import tom_international_country_etf_tbill_switch_exploratory_v1 as tom


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = ROOT / "reports" / "strategy_research" / tom.ARTIFACT_ID


def read_csv_rows(name: str) -> list[dict[str, str]]:
    path = ARTIFACT_DIR / name
    assert path.exists(), f"missing artifact {path}"
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_json(name: str) -> dict:
    path = ARTIFACT_DIR / name
    assert path.exists(), f"missing artifact {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def synthetic_price_data(dates: pd.DatetimeIndex) -> tom.PriceData:
    symbols = ["EWA", "BIL"]
    open_prices = pd.DataFrame(
        {
            "EWA": np.linspace(100.0, 110.0, len(dates)),
            "BIL": np.linspace(50.0, 50.2, len(dates)),
        },
        index=dates,
    )
    close_prices = open_prices * pd.DataFrame({"EWA": [1.01] * len(dates), "BIL": [1.0001] * len(dates)}, index=dates)
    return tom.PriceData(
        open=open_prices,
        close=close_prices,
        coverage_rows=[],
        common_start=dates[0],
        common_end=dates[-1],
        calendar=dates,
        file_hashes={},
        acquisition_rows=[],
        failures=[],
    )


def label_by_date(rows: list[dict[str, object]]) -> dict[str, str]:
    return {str(row["date"]): str(row["tom_day_label"]) for row in rows}


def test_tom_calendar_labels_february_leap_year_and_holiday() -> None:
    dates = pd.DatetimeIndex(
        [
            "2024-02-01",
            "2024-02-02",
            "2024-02-05",
            "2024-02-06",
            "2024-02-07",
            "2024-02-08",
            "2024-02-09",
            "2024-02-12",
            "2024-02-13",
            "2024-02-14",
            "2024-02-15",
            "2024-02-16",
            "2024-02-20",
            "2024-02-21",
            "2024-02-22",
            "2024-02-23",
            "2024-02-26",
            "2024-02-27",
            "2024-02-28",
            "2024-02-29",
        ]
    )
    labels = label_by_date(tom.classify_tom_calendar(dates))

    assert labels["2024-02-01"] == tom.TOM_DAY_PLUS_1
    assert labels["2024-02-02"] == tom.TOM_DAY_PLUS_2
    assert labels["2024-02-05"] == tom.TOM_DAY_PLUS_3
    assert labels["2024-02-20"] == tom.NON_TOM
    assert labels["2024-02-29"] == tom.TOM_DAY_MINUS_1


def test_tom_calendar_labels_year_end_and_nontrading_month_end() -> None:
    dates = pd.DatetimeIndex(
        [
            "2024-12-27",
            "2024-12-30",
            "2024-12-31",
            "2025-01-02",
            "2025-01-03",
            "2025-01-06",
            "2025-01-07",
            "2025-01-08",
            "2025-06-26",
            "2025-06-27",
            "2025-06-30",
        ]
    )
    labels = label_by_date(tom.classify_tom_calendar(dates))

    assert labels["2024-12-31"] == tom.TOM_DAY_MINUS_1
    assert labels["2025-01-02"] == tom.TOM_DAY_PLUS_1
    assert labels["2025-01-03"] == tom.TOM_DAY_PLUS_2
    assert labels["2025-01-06"] == tom.TOM_DAY_PLUS_3
    assert labels["2025-06-30"] == tom.TOM_DAY_MINUS_1


def test_source_target_schedule_uses_only_tom_window() -> None:
    dates = pd.bdate_range("2024-01-02", "2024-02-07")
    calendar_rows = tom.classify_tom_calendar(dates)
    weights = tom.target_weights_for_method(tom.METHOD_TOM, "EWA", dates, calendar_rows)

    assert weights.loc[pd.Timestamp("2024-01-29"), "BIL"] == 1.0
    assert weights.loc[pd.Timestamp("2024-01-31"), "EWA"] == 1.0
    assert weights.loc[pd.Timestamp("2024-02-01"), "EWA"] == 1.0
    assert weights.loc[pd.Timestamp("2024-02-02"), "EWA"] == 1.0
    assert weights.loc[pd.Timestamp("2024-02-05"), "EWA"] == 1.0
    assert weights.loc[pd.Timestamp("2024-02-06"), "BIL"] == 1.0


def test_exposure_matched_control_monthly_weight_is_four_sessions_over_month_length() -> None:
    dates = pd.bdate_range("2024-02-01", "2024-02-29")
    calendar_rows = tom.classify_tom_calendar(dates)
    weights = tom.target_weights_for_method(tom.METHOD_EXPOSURE, "EWA", dates, calendar_rows)
    expected = 4.0 / len(dates)

    assert weights["EWA"].nunique() == 1
    assert weights["EWA"].iloc[0] == pytest.approx(expected)
    assert weights["BIL"].iloc[0] == pytest.approx(1.0 - expected)


def test_next_open_fill_prices_and_signal_dates_are_explicit() -> None:
    dates = pd.bdate_range("2024-01-02", "2024-02-07")
    prices = synthetic_price_data(dates)
    calendar_rows = tom.classify_tom_calendar(dates)
    weights = tom.target_weights_for_method(tom.METHOD_TOM, "EWA", dates, calendar_rows)
    path = tom.simulate_trial("unit", tom.METHOD_TOM, "EWA", 5, weights, prices, calendar_rows)
    fills = path.fills

    entry = fills[
        (fills["symbol"] == "EWA")
        & (fills["side"] == "BUY")
        & (fills["signal_date"] != "PRE_EVALUATION_START")
    ].iloc[0]
    exit_fill = fills[(fills["symbol"] == "EWA") & (fills["side"] == "SELL")].iloc[-1]

    assert entry["fill_date"] == "2024-01-31"
    assert entry["signal_date"] == "2024-01-30"
    assert entry["fill_price"] == pytest.approx(prices.open.loc[pd.Timestamp("2024-01-31"), "EWA"])
    assert entry["price_source"] == "next_open"
    assert exit_fill["fill_date"] == "2024-02-06"
    assert exit_fill["signal_date"] == "2024-02-05"
    assert exit_fill["price_source"] == "next_open"


def test_identity_path_matches_source_path_on_complete_state() -> None:
    dates = pd.bdate_range("2024-01-29", "2024-03-08")
    prices = synthetic_price_data(dates)
    calendar_rows = tom.classify_tom_calendar(dates)
    source = tom.simulate_trial(
        tom.trial_id(tom.METHOD_TOM, "EWA", 10),
        tom.METHOD_TOM,
        "EWA",
        10,
        tom.target_weights_for_method(tom.METHOD_TOM, "EWA", dates, calendar_rows),
        prices,
        calendar_rows,
    )
    identity = tom.simulate_trial(
        tom.trial_id(tom.METHOD_IDENTITY, "EWA", 10),
        tom.METHOD_IDENTITY,
        "EWA",
        10,
        tom.target_weights_for_method(tom.METHOD_IDENTITY, "EWA", dates, calendar_rows),
        prices,
        calendar_rows,
    )

    rows, failures = tom.identity_equivalence_rows(
        {
            tom.trial_id(tom.METHOD_TOM, country, cost): source
            for cost in tom.COST_LEVELS_BPS
            for country in tom.COUNTRY_ETFS
        }
        | {
            tom.trial_id(tom.METHOD_IDENTITY, country, cost): identity
            for cost in tom.COST_LEVELS_BPS
            for country in tom.COUNTRY_ETFS
        }
    )

    assert failures == []
    assert {row["equivalence_status"] for row in rows} == {"PASS"}


def test_registered_trial_count_and_overlay_count_are_fixed() -> None:
    rows = tom.registered_trials()

    assert len(rows) == 111
    assert sum(1 for row in rows if row["method_id"] == tom.METHOD_BIL) == 3
    assert {row["optional_management_overlay_count"] for row in rows} == {0}


def test_run_artifacts_manifest_and_identity_results() -> None:
    manifest = read_json("manifest.json")
    identities = read_csv_rows("identity_equivalence.csv")
    trials = read_csv_rows("trial_registry.csv")

    assert manifest["registered_trial_count"] == 111
    assert manifest["completed_trial_count"] == 111
    assert manifest["optional_management_overlay_used"] is False
    assert manifest["next_open_execution"] is True
    assert len(identities) == 27
    assert {row["equivalence_status"] for row in identities} == {"PASS"}
    assert {row["status"] for row in trials} == {"COMPLETED"}


def test_close_to_close_source_diagnostic_is_not_executable() -> None:
    rows = read_csv_rows("close_to_close_source_diagnostic.csv")

    assert rows
    assert {row["diagnostic_only"] for row in rows} == {"True"}
    assert {row["used_as_executable_fill"] for row in rows} == {"False"}


def test_metrics_include_reporting_aggregate_without_extra_registered_trials() -> None:
    metrics = read_csv_rows("metrics.csv")
    aggregates = [row for row in metrics if row["row_type"] == "aggregate_reporting"]
    trials = [row for row in metrics if row["row_type"] == "trial"]

    assert len(trials) == 111
    assert len(aggregates) == 6
    assert all(row["aggregate_component_count"] == "9" for row in aggregates)


def test_cost_rows_apply_costs_from_gross_traded_notional() -> None:
    rows = read_csv_rows("turnover_and_costs.csv")
    execution_rows = [row for row in rows if row["is_execution_date"] == "True"]

    assert execution_rows
    for row in execution_rows[:500]:
        assert float(row["transaction_cost_return"]) == pytest.approx(float(row["expected_transaction_cost_return"]))
    assert all(float(row["transaction_cost_return"]) == 0.0 for row in execution_rows if row["cost_bps_per_side"] == "0")


def test_calendar_artifact_has_only_stable_labels() -> None:
    rows = read_csv_rows("calendar_classification.csv")
    labels = {row["tom_day_label"] for row in rows}

    assert labels <= {tom.TOM_DAY_MINUS_1, tom.TOM_DAY_PLUS_1, tom.TOM_DAY_PLUS_2, tom.TOM_DAY_PLUS_3, tom.NON_TOM}
    assert {tom.TOM_DAY_MINUS_1, tom.TOM_DAY_PLUS_1, tom.TOM_DAY_PLUS_2, tom.TOM_DAY_PLUS_3}.issubset(labels)


def test_no_execution_connected_imports_in_exploratory_runner() -> None:
    tree = ast.parse(Path(tom.__file__).read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)

    forbidden = {"alpaca", "broker", "brokers", "live", "paper", "demo"}
    assert not any(module.split(".")[0] in forbidden for module in imported)
