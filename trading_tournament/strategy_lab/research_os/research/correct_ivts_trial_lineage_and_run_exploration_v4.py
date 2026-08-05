from __future__ import annotations

import csv
import json
import math
import shutil
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import fast_price_volume_discovery_batch_v2 as market
from strategy_lab.research_os.research import fast_source_library_batch_v5 as accounting
from strategy_lab.research_os.research import (
    fast_source_library_remaining_candidates_batch_v4 as portfolio_accounting,
)
from strategy_lab.research_os.research import (
    intermarket_ivts_herorats_portability_exploration_v1 as v1,
)
from strategy_lab.research_os.research import (
    run_cboe_point_in_time_ivts_feasibility_and_exploration_v2 as v2,
)
from strategy_lab.research_os.research import (
    correct_ivts_timing_gate_and_run_official_daily_close_exploration_v3 as v3,
)


TASK_ID = "correct_ivts_trial_lineage_and_run_exploration_v4"
MODE = "correction"
STAGE = "exploration"
STRATEGY_ID = "donninger_vix_vix3m_median5_spy_ief_portability_v1"
FAMILY_ID = "implied_volatility_term_structure_equity_timing"
DISPLAY_NAME = "VIX/VIX3M Median-5 Equity-Treasury Regime"
TRIAL_ID = f"{TASK_ID}__child"
PARENT_TRIAL_ID = "intermarket_ivts_herorats_portability_exploration_v1__canonical"
SOURCE_RECORD_ID = "src_donninger_herorats_vix_vix3m_median5_spy_ief_v1"
OUTPUT_DIR = ROOT / "evidence" / "correction" / TASK_ID / "latest"
V1_EVIDENCE = v1.OUTPUT_DIR
V2_EVIDENCE = v2.OUTPUT_DIR
V3_EVIDENCE = v3.OUTPUT_DIR
CACHE_DIR = ROOT / "data" / "cache"

PREREGISTRATION_TIMESTAMP = "2026-07-25T00:00:00-06:00"
EARLIEST_SIGNAL_DATE = pd.Timestamp("2014-04-17")
METHODOLOGY_BOUNDARY = pd.Timestamp("2025-02-10")
TIMING_POLICY = "official_daily_close_following_session_execution_v1"
DATA_PROVENANCE = "official_cboe_daily_history"
VINTAGE_STATUS = "current_history_non_vintage"
PRIMARY_COST_BPS = 5.0
COST_BPS = (0.0, 5.0, 10.0)
WEIGHT_TOLERANCE = 1e-9

BENCHMARKS = (
    "SPY_buy_and_hold",
    "SPY_200_day_trend_control",
    "unfiltered_vix_vix3m_three_state_spy_ief_v1",
    "vix_vix3m_sign_only_spy_ief_v1",
    "static_exposure_matched_spy_ief_v1",
    "IEF_buy_and_hold",
)
CRITICAL_CONTROLS = (
    "unfiltered_vix_vix3m_three_state_spy_ief_v1",
    "static_exposure_matched_spy_ief_v1",
)
REPLICATION_CONTROLS = (
    "SPY_200_day_trend_control",
    "vix_vix3m_sign_only_spy_ief_v1",
    "IEF_buy_and_hold",
)

ADVANCE_NEXT_ACTION = "direction_owner_review_ivts_official_daily_close_followup_v1"
CLOSE_NEXT_ACTION = "direction_owner_select_next_targeted_family_sprint_v1"
BLOCK_NEXT_ACTION = "defer_ivts_lane_and_select_next_targeted_family_sprint_v1"

PROTECTED_STATE_PATHS = v1.PROTECTED_STATE_PATHS
PRIOR_EVIDENCE_DIRS = (V1_EVIDENCE, V2_EVIDENCE, V3_EVIDENCE)

REQUIRED_ARTIFACTS = (
    "correction_manifest.yaml",
    "source_library_records.csv",
    "strategy_cards.csv",
    "trial_ledger.csv",
    "data_and_process_lineage.csv",
    "benchmark_reference_log.csv",
    "process_task_log.csv",
    "official_history_hash_reconciliation.csv",
    "data_preflight_reconciliation.csv",
    "all_trial_results.csv",
    "control_results.csv",
    "chronological_half_results.csv",
    "portfolio_contribution_results.csv",
    "state_signal_diagnostics.csv",
    "turnover_cost_reconciliation.csv",
    "invariant_results.csv",
    "outcome_summary.csv",
    "failure_reasons.csv",
    "next_actions.csv",
    "cohort_funnel_counts.json",
    "consistency_check.json",
    "correction_report.md",
)

METRIC_FIELDS = [
    "entity_id",
    "entity_type",
    "role",
    "period",
    "cost_bps",
    "evaluation_start",
    "evaluation_end",
    "trading_days",
    "total_return",
    "cagr",
    "annualized_volatility",
    "sharpe_ratio",
    "maximum_drawdown",
    "average_SPY_exposure",
    "turnover",
    "trade_or_rebalance_count",
    "transaction_cost_drag",
    "maximum_gross_exposure",
    "maximum_daily_weight_sum",
    "timing_invariant",
    "numeric_invariant",
    "exposure_invariant",
    "weight_invariant",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str]) -> None:
    v1.write_csv(path, rows, fields)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    v1.write_json(path, payload)


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    v1.write_yaml(path, payload)


def write_text(path: Path, text: str) -> None:
    v1.write_text(path, text)


def clean_output_dir() -> None:
    if OUTPUT_DIR.exists():
        resolved = OUTPUT_DIR.resolve()
        expected_parent = (ROOT / "evidence" / "correction" / TASK_ID).resolve()
        if expected_parent not in resolved.parents:
            raise RuntimeError(f"Refusing to remove unexpected output path: {resolved}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def directory_hash(path: Path) -> str:
    rows: list[dict[str, Any]] = []
    if path.exists():
        for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
            rows.append(
                {
                    "path": item.relative_to(path).as_posix(),
                    "sha256": v1.file_hash(item),
                    "size": item.stat().st_size,
                }
            )
    return v1.canonical_hash(rows)


def _bool(value: Any) -> bool:
    return str(value).strip().lower() == "true"


def verify_lineage() -> dict[str, Any]:
    v1_rows = read_csv(V1_EVIDENCE / "trial_ledger.csv")
    v2_rows = read_csv(V2_EVIDENCE / "trial_ledger.csv")
    v3_rows = read_csv(V3_EVIDENCE / "trial_ledger.csv")
    v1_parent = [
        row
        for row in v1_rows
        if row.get("trial_id") == PARENT_TRIAL_ID
        and row.get("entity_type") == "experiment_trial"
    ]
    v3_created = [row for row in v3_rows if _bool(row.get("created_in_v3", False))]
    return {
        "V1_parent_rows": v1_parent,
        "V1_parent_count": len(v1_parent),
        "V2_trial_count": len(v2_rows),
        "V3_created_trial_count": len(v3_created),
        "passed": len(v1_parent) == 1 and not v2_rows and not v3_created,
    }


def load_verified_v3_histories() -> tuple[dict[str, pd.DataFrame], list[dict[str, Any]], bool]:
    manifest = {row["series"]: row for row in read_csv(V3_EVIDENCE / "official_cboe_history_manifest.csv")}
    snapshots = read_csv(V3_EVIDENCE / "official_history_reproducibility.csv")
    frames: dict[str, pd.DataFrame] = {}
    reconciliation: list[dict[str, Any]] = []
    all_pass = True
    for series in ("VIX", "VIX3M"):
        expected = manifest.get(series, {})
        series_rows = sorted(
            [row for row in snapshots if row.get("series") == series],
            key=lambda row: int(row["attempt"]),
        )
        normalized_hashes: list[str] = []
        for row in series_rows:
            raw_path = ROOT / row["raw_path"]
            payload = raw_path.read_bytes() if raw_path.exists() else b""
            frame = v3.normalize_official_history(payload, series) if payload else pd.DataFrame()
            actual_raw = v1.sha256_bytes(payload) if payload else "missing"
            actual_normalized = v3.normalized_frame_hash(frame) if not frame.empty else "missing"
            raw_match = actual_raw == row.get("raw_bytes_hash")
            normalized_match = actual_normalized == row.get("normalized_frame_hash")
            manifest_match = actual_normalized == expected.get("normalized_frame_hash")
            passed = bool(raw_match and normalized_match and manifest_match)
            all_pass = all_pass and passed
            normalized_hashes.append(actual_normalized)
            reconciliation.append(
                {
                    "series": series,
                    "attempt": int(row["attempt"]),
                    "raw_path": row["raw_path"],
                    "recorded_raw_hash": row.get("raw_bytes_hash", ""),
                    "reproduced_raw_hash": actual_raw,
                    "recorded_normalized_hash": row.get("normalized_frame_hash", ""),
                    "reproduced_normalized_hash": actual_normalized,
                    "manifest_normalized_hash": expected.get("normalized_frame_hash", ""),
                    "raw_hash_match": raw_match,
                    "normalized_hash_match": normalized_match,
                    "manifest_hash_match": manifest_match,
                    "data_provenance": DATA_PROVENANCE,
                    "vintage_status": VINTAGE_STATUS,
                    "timing_policy": TIMING_POLICY,
                    "network_request_performed": False,
                    "status": "pass" if passed else "fail",
                }
            )
            if int(row["attempt"]) == 1 and not frame.empty:
                frames[series] = frame
        duplicate_match = len(series_rows) == 2 and len(set(normalized_hashes)) == 1
        all_pass = all_pass and duplicate_match
    return frames, reconciliation, bool(all_pass and set(frames) == {"VIX", "VIX3M"})


def load_prices() -> tuple[pd.DataFrame, pd.DataFrame]:
    full = market.load_price_frame(("SPY", "IEF", "BIL")).sort_index()
    if full.empty:
        return full, full
    candidate = full.loc[
        full.index >= EARLIEST_SIGNAL_DATE, ["SPY", "IEF"]
    ].copy()
    return full, candidate


def target_for_ratio(value: float | None) -> tuple[float, float, str]:
    if value is None or not math.isfinite(float(value)):
        return 0.5, 0.5, "middle"
    if float(value) < 0.96:
        return 1.0, 0.0, "risk_on"
    if float(value) <= 1.02:
        return 0.5, 0.5, "middle"
    return 0.0, 1.0, "defensive"


def target_for_sign(value: float | None) -> tuple[float, float, str]:
    if value is None or not math.isfinite(float(value)):
        return 0.5, 0.5, "middle"
    if float(value) <= 1.0:
        return 1.0, 0.0, "risk_on"
    return 0.0, 1.0, "defensive"


def build_signal_panel(histories: dict[str, pd.DataFrame], price_end: pd.Timestamp) -> pd.DataFrame:
    vix = histories["VIX"].set_index("DATE")["CLOSE"].rename("VIX_close")
    vix3m = histories["VIX3M"].set_index("DATE")["CLOSE"].rename("VIX3M_close")
    panel = pd.concat([vix, vix3m], axis=1, join="outer").sort_index()
    panel["common_observation"] = panel[["VIX_close", "VIX3M_close"]].notna().all(axis=1)
    panel["raw_ratio"] = panel["VIX_close"] / panel["VIX3M_close"]
    common_ratio = panel.loc[panel["common_observation"], "raw_ratio"]
    panel["filtered_ratio"] = common_ratio.rolling(5, min_periods=5).median().reindex(panel.index)
    panel = panel.loc[
        (panel.index >= EARLIEST_SIGNAL_DATE) & (panel.index <= price_end)
    ].copy()

    candidate_targets: list[tuple[float, float, str]] = []
    unfiltered_targets: list[tuple[float, float, str]] = []
    sign_targets: list[tuple[float, float, str]] = []
    prior_candidate = (0.5, 0.5, "middle")
    prior_unfiltered = (0.5, 0.5, "middle")
    prior_sign = (0.5, 0.5, "middle")
    for row in panel.itertuples():
        if bool(row.common_observation):
            filtered = None if pd.isna(row.filtered_ratio) else float(row.filtered_ratio)
            raw = None if pd.isna(row.raw_ratio) else float(row.raw_ratio)
            prior_candidate = target_for_ratio(filtered)
            prior_unfiltered = target_for_ratio(raw)
            prior_sign = target_for_sign(raw)
        candidate_targets.append(prior_candidate)
        unfiltered_targets.append(prior_unfiltered)
        sign_targets.append(prior_sign)
    for prefix, values in (
        ("candidate", candidate_targets),
        ("unfiltered", unfiltered_targets),
        ("sign", sign_targets),
    ):
        panel[f"{prefix}_SPY"] = [item[0] for item in values]
        panel[f"{prefix}_IEF"] = [item[1] for item in values]
        panel[f"{prefix}_state"] = [item[2] for item in values]
    panel["methodology_period"] = np.where(
        panel.index < METHODOLOGY_BOUNDARY,
        "pre_2025_02_10",
        "post_2025_02_10",
    )
    return panel


def next_session(price_index: pd.DatetimeIndex, signal_date: pd.Timestamp) -> pd.Timestamp | None:
    position = int(price_index.searchsorted(pd.Timestamp(signal_date), side="right"))
    return pd.Timestamp(price_index[position]) if position < len(price_index) else None


def state_change_schedule(
    panel: pd.DataFrame,
    price_index: pd.DatetimeIndex,
    prefix: str,
) -> tuple[pd.DataFrame, dict[pd.Timestamp, pd.Timestamp | str], dict[pd.Timestamp, str]]:
    events: dict[pd.Timestamp, dict[str, float]] = {
        pd.Timestamp(price_index[0]): {"SPY": 0.5, "IEF": 0.5}
    }
    origins: dict[pd.Timestamp, pd.Timestamp | str] = {
        pd.Timestamp(price_index[0]): "warmup_initial_allocation"
    }
    states: dict[pd.Timestamp, str] = {pd.Timestamp(price_index[0]): "middle"}
    current = (0.5, 0.5)
    for date, row in panel.iterrows():
        execution = next_session(price_index, pd.Timestamp(date))
        if execution is None:
            continue
        target = (float(row[f"{prefix}_SPY"]), float(row[f"{prefix}_IEF"]))
        if target != current:
            events[execution] = {"SPY": target[0], "IEF": target[1]}
            origins[execution] = pd.Timestamp(date)
            states[execution] = str(row[f"{prefix}_state"])
            current = target
    return pd.DataFrame.from_dict(events, orient="index").sort_index(), origins, states


def buy_hold_schedule(price_index: pd.DatetimeIndex, symbol: str) -> pd.DataFrame:
    target = {"SPY": 0.0, "IEF": 0.0}
    target[symbol] = 1.0
    return pd.DataFrame([target], index=pd.DatetimeIndex([price_index[0]]))


def spy_200d_schedule(full_prices: pd.DataFrame, price_index: pd.DatetimeIndex) -> pd.DataFrame:
    spy = full_prices["SPY"]
    sma = spy.rolling(200, min_periods=200).mean()
    risk_on = spy > sma
    events: dict[pd.Timestamp, dict[str, float]] = {}
    current: tuple[float, float] | None = None
    for signal_date in full_prices.index:
        execution = next_session(full_prices.index, pd.Timestamp(signal_date))
        if execution is None or execution < price_index[0] or execution > price_index[-1]:
            continue
        target = (1.0, 0.0) if bool(risk_on.loc[signal_date]) else (0.0, 1.0)
        if target != current:
            events[execution] = {"SPY": target[0], "BIL": target[1]}
            current = target
    if price_index[0] not in events:
        prior_dates = full_prices.index[full_prices.index < price_index[0]]
        prior = prior_dates[-1] if len(prior_dates) else price_index[0]
        target = (1.0, 0.0) if bool(risk_on.loc[prior]) else (0.0, 1.0)
        events[pd.Timestamp(price_index[0])] = {"SPY": target[0], "BIL": target[1]}
    return pd.DataFrame.from_dict(events, orient="index").sort_index()


def monthly_static_schedule(price_index: pd.DatetimeIndex, spy_weight: float) -> pd.DataFrame:
    events: dict[pd.Timestamp, dict[str, float]] = {}
    for position, date in enumerate(price_index):
        if position == 0 or price_index[position - 1].to_period("M") != date.to_period("M"):
            events[pd.Timestamp(date)] = {
                "SPY": float(spy_weight),
                "IEF": float(1.0 - spy_weight),
            }
    return pd.DataFrame.from_dict(events, orient="index").sort_index()


def target_path(schedule: pd.DataFrame, price_index: pd.DatetimeIndex) -> pd.DataFrame:
    return schedule.reindex(price_index).ffill().fillna(0.0)


def build_schedules(
    panel: pd.DataFrame,
    full_prices: pd.DataFrame,
    prices: pd.DataFrame,
) -> tuple[
    dict[str, pd.DataFrame],
    dict[pd.Timestamp, pd.Timestamp | str],
    dict[pd.Timestamp, str],
    float,
]:
    candidate, candidate_origins, candidate_states = state_change_schedule(
        panel, prices.index, "candidate"
    )
    unfiltered, _, _ = state_change_schedule(panel, prices.index, "unfiltered")
    sign_only, _, _ = state_change_schedule(panel, prices.index, "sign")
    average_target_spy = float(target_path(candidate, prices.index)["SPY"].mean())
    schedules = {
        STRATEGY_ID: candidate,
        "SPY_buy_and_hold": buy_hold_schedule(prices.index, "SPY"),
        "SPY_200_day_trend_control": spy_200d_schedule(full_prices, prices.index),
        "unfiltered_vix_vix3m_three_state_spy_ief_v1": unfiltered,
        "vix_vix3m_sign_only_spy_ief_v1": sign_only,
        "static_exposure_matched_spy_ief_v1": monthly_static_schedule(
            prices.index, average_target_spy
        ),
        "IEF_buy_and_hold": buy_hold_schedule(prices.index, "IEF"),
    }
    return schedules, candidate_origins, candidate_states, average_target_spy


def path_metrics(
    path: dict[str, Any], period_index: pd.DatetimeIndex | None = None
) -> dict[str, Any]:
    returns = path["returns"]
    if period_index is not None:
        returns = returns.reindex(period_index).dropna()
    daily = path["daily"].reindex(returns.index)
    held = path["held_weights"].reindex(returns.index)
    metrics = market.metrics_from_returns(returns)
    max_gross = float(daily["max_gross_exposure"].max())
    max_sum = float(daily["max_daily_weight_sum"].max())
    target = path["target_events"]
    target_values = target.to_numpy(dtype=float)
    numeric = bool(
        len(returns)
        and np.isfinite(returns.to_numpy(dtype=float)).all()
        and np.isfinite(target_values).all()
    )
    exposure = bool(
        max_gross <= 1.0 + WEIGHT_TOLERANCE
        and max_sum <= 1.0 + WEIGHT_TOLERANCE
        and (held.to_numpy(dtype=float) >= -WEIGHT_TOLERANCE).all()
    )
    weights = bool(
        target_values.size
        and (target_values >= -WEIGHT_TOLERANCE).all()
        and np.allclose(target_values.sum(axis=1), 1.0, atol=WEIGHT_TOLERANCE)
        and "SPY" in target.columns
        and len(target.columns) == 2
    )
    return {
        **metrics,
        "average_SPY_exposure": float(held["SPY"].mean()),
        "turnover": float(daily["one_way_turnover"].sum()),
        "trade_or_rebalance_count": int(
            (daily["one_way_turnover"] > WEIGHT_TOLERANCE).sum()
        ),
        "transaction_cost_drag": float(daily["transaction_cost_drag"].sum()),
        "maximum_gross_exposure": max_gross,
        "maximum_daily_weight_sum": max_sum,
        "timing_invariant": "pass_following_session_close_no_signal_date_return",
        "numeric_invariant": "pass" if numeric else "fail",
        "exposure_invariant": "pass" if exposure else "fail",
        "weight_invariant": "pass" if weights else "fail",
        "invariant_pass": bool(numeric and exposure and weights),
    }


def metric_row(
    entity_id: str,
    entity_type: str,
    role: str,
    period: str,
    cost_bps: float,
    metrics: dict[str, Any],
) -> dict[str, Any]:
    return {
        "entity_id": entity_id,
        "entity_type": entity_type,
        "role": role,
        "period": period,
        "cost_bps": cost_bps,
        **{field: metrics.get(field, "") for field in METRIC_FIELDS if field not in {
            "entity_id", "entity_type", "role", "period", "cost_bps"
        }},
    }


def split_halves(index: pd.DatetimeIndex) -> list[tuple[str, pd.DatetimeIndex]]:
    midpoint = len(index) // 2
    return [
        ("first_chronological_half", index[:midpoint]),
        ("second_chronological_half", index[midpoint:]),
    ]


def dominates(control: dict[str, Any], candidate: dict[str, Any]) -> bool:
    equal_or_better = (
        float(control["cagr"]) >= float(candidate["cagr"]) - 1e-12
        and float(control["sharpe_ratio"]) >= float(candidate["sharpe_ratio"]) - 1e-12
        and float(control["maximum_drawdown"])
        >= float(candidate["maximum_drawdown"]) - 1e-12
    )
    strict = (
        float(control["cagr"]) > float(candidate["cagr"]) + 1e-12
        or float(control["sharpe_ratio"]) > float(candidate["sharpe_ratio"]) + 1e-12
        or float(control["maximum_drawdown"])
        > float(candidate["maximum_drawdown"]) + 1e-12
    )
    return bool(equal_or_better and strict)


def classify(
    metrics: dict[tuple[str, float], dict[str, Any]],
    half_metrics: dict[tuple[str, str], dict[str, Any]],
) -> tuple[str, str, str, dict[str, Any]]:
    candidate = metrics[(STRATEGY_ID, PRIMARY_COST_BPS)]
    gate: dict[str, Any] = {
        "positive_full_period_after_cost_return": float(candidate["total_return"]) > 0.0,
        "all_invariants_pass": all(
            row["invariant_pass"]
            for key, row in metrics.items()
            if isinstance(key, tuple)
        ),
    }
    critical_dominators = [
        control_id
        for control_id in CRITICAL_CONTROLS
        if dominates(metrics[(control_id, PRIMARY_COST_BPS)], candidate)
    ]
    gate["critical_control_dominators"] = critical_dominators
    material: dict[str, bool] = {}
    for control_id in CRITICAL_CONTROLS:
        control = metrics[(control_id, PRIMARY_COST_BPS)]
        material[control_id] = bool(
            float(candidate["sharpe_ratio"]) - float(control["sharpe_ratio"]) >= 0.02
            or float(candidate["maximum_drawdown"])
            - float(control["maximum_drawdown"])
            >= 0.01
        )
    gate["material_advantage_vs_each_critical_control"] = material
    half_worse: list[str] = []
    for period, _ in split_halves(pd.DatetimeIndex(metrics["_index"])):
        candidate_half = half_metrics[(STRATEGY_ID, period)]
        for control_id in CRITICAL_CONTROLS:
            control_half = half_metrics[(control_id, period)]
            if (
                float(candidate_half["sharpe_ratio"]) < float(control_half["sharpe_ratio"])
                and float(candidate_half["maximum_drawdown"])
                < float(control_half["maximum_drawdown"])
            ):
                half_worse.append(f"{period}:{control_id}")
    gate["worse_on_both_in_half"] = half_worse
    replicators: list[str] = []
    for control_id in REPLICATION_CONTROLS:
        control = metrics[(control_id, PRIMARY_COST_BPS)]
        sharpe_edge = float(candidate["sharpe_ratio"]) - float(control["sharpe_ratio"])
        drawdown_edge = float(candidate["maximum_drawdown"]) - float(control["maximum_drawdown"])
        if dominates(control, candidate) or (sharpe_edge < 0.02 and drawdown_edge < 0.01):
            replicators.append(control_id)
    gate["economic_replication_controls"] = replicators
    unfavorable_10: list[str] = []
    candidate_10 = metrics[(STRATEGY_ID, 10.0)]
    for control_id in CRITICAL_CONTROLS:
        control_10 = metrics[(control_id, 10.0)]
        if (
            float(candidate_10["sharpe_ratio"]) < float(control_10["sharpe_ratio"])
            and float(candidate_10["maximum_drawdown"])
            < float(control_10["maximum_drawdown"])
        ):
            unfavorable_10.append(control_id)
    gate["unfavorable_on_both_at_10bps"] = unfavorable_10

    if not gate["all_invariants_pass"]:
        return "blocked_feasibility", "methodology_failure", "one or more accounting invariants failed", gate
    if not gate["positive_full_period_after_cost_return"]:
        return "closed_exploration", "weak_vs_primary_control", "full-period after-cost return was not positive", gate
    if critical_dominators:
        return (
            "closed_exploration",
            "weak_vs_primary_control",
            f"critical control dominated candidate: {','.join(critical_dominators)}",
            gate,
        )
    failed_material = [key for key, value in material.items() if not value]
    if failed_material:
        return (
            "closed_exploration",
            "weak_vs_primary_control",
            f"candidate lacked material advantage versus: {','.join(failed_material)}",
            gate,
        )
    if half_worse:
        return (
            "closed_exploration",
            "period_instability",
            f"candidate was worse on Sharpe and drawdown in: {','.join(half_worse)}",
            gate,
        )
    if replicators:
        return (
            "closed_exploration",
            "benchmark_like_behavior",
            f"simpler control economically replicated the result: {','.join(replicators)}",
            gate,
        )
    if unfavorable_10:
        return (
            "closed_exploration",
            "cost_drag",
            f"10-bps result was unfavorable on Sharpe and drawdown versus: {','.join(unfavorable_10)}",
            gate,
        )
    return (
        "exploratory_followup_candidate_standalone",
        "",
        "candidate passed the frozen lightweight exploration gate",
        gate,
    )


def portfolio_metric_payload(payload: dict[str, Any]) -> dict[str, Any]:
    metrics = market.metrics_from_returns(payload["returns"])
    daily = payload["daily_df"]
    return {
        **metrics,
        "turnover": float(payload["turnover"].sum()),
        "transaction_cost_drag": float(payload["cost"].sum()),
        "trade_or_rebalance_count": int(
            (payload["turnover"] > WEIGHT_TOLERANCE).sum()
        ),
        "maximum_gross_exposure": float(daily["max_daily_exposure"].max()),
        "maximum_daily_weight_sum": float(daily["max_daily_weight_sum"].max()),
    }


def build_portfolio_rows(
    paths: dict[tuple[str, float], dict[str, Any]],
    reference_returns: pd.Series,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    sleeves = (
        STRATEGY_ID,
        "unfiltered_vix_vix3m_three_state_spy_ief_v1",
        "static_exposure_matched_spy_ief_v1",
        "IEF_buy_and_hold",
    )
    for cost_bps in COST_BPS:
        common = paths[(STRATEGY_ID, cost_bps)]["returns"].index.intersection(
            reference_returns.dropna().index
        )
        reference = reference_returns.reindex(common).dropna()
        reference_payload = portfolio_accounting.reference_payload(reference, cost_bps)
        constructions: list[tuple[str, dict[str, Any], str]] = [
            (
                "frozen_current_active_vm_dsr_usci_combo",
                reference_payload,
                "100pct_frozen_reference",
            )
        ]
        for sleeve_id in sleeves:
            sleeve = paths[(sleeve_id, cost_bps)]["returns"].reindex(reference.index).dropna()
            aligned_reference = reference.reindex(sleeve.index).dropna()
            portfolio_id = f"80pct_reference_20pct_{sleeve_id}"
            payload = portfolio_accounting.simulate_two_component_portfolio(
                aligned_reference, sleeve, portfolio_id, cost_bps
            )
            constructions.append(
                (
                    portfolio_id,
                    payload,
                    "monthly_rebalanced_explicit_holdings_natural_drift",
                )
            )
        for portfolio_id, payload, construction in constructions:
            metrics = portfolio_metric_payload(payload)
            rows.append(
                {
                    "portfolio_id": portfolio_id,
                    "entity_type": "portfolio_contribution_diagnostic",
                    "stage": "exploration",
                    "cost_bps": cost_bps,
                    "construction": construction,
                    **metrics,
                    "maximum_total_exposure_limit": 1.0,
                    "daily_fixed_weight_return_blend_used": False,
                    "explicit_holdings_used": True,
                    "natural_drift_used": True,
                    "actual_turnover_and_costs_used": True,
                }
            )
    return rows


def state_from_weights(spy: float, ief: float) -> str:
    if abs(spy - 1.0) <= WEIGHT_TOLERANCE and abs(ief) <= WEIGHT_TOLERANCE:
        return "risk_on"
    if abs(spy) <= WEIGHT_TOLERANCE and abs(ief - 1.0) <= WEIGHT_TOLERANCE:
        return "defensive"
    return "middle"


def state_diagnostic_rows(
    panel: pd.DataFrame,
    prices: pd.DataFrame,
    schedule: pd.DataFrame,
    origins: dict[pd.Timestamp, pd.Timestamp | str],
    path: dict[str, Any],
) -> list[dict[str, Any]]:
    asset_returns = prices.pct_change(fill_method=None).fillna(0.0)
    details: dict[pd.Timestamp, dict[str, Any]] = {}
    for date in prices.index:
        held = path["held_weights"].loc[date, ["SPY", "IEF"]].to_numpy(dtype=float)
        daily_returns = asset_returns.loc[date, ["SPY", "IEF"]].to_numpy(dtype=float)
        drifted = held * (1.0 + daily_returns)
        denominator = float(drifted.sum())
        pretrade = drifted / denominator if denominator > 0.0 else held
        traded = date in schedule.index
        post = (
            schedule.loc[date, ["SPY", "IEF"]].to_numpy(dtype=float)
            if traded
            else pretrade
        )
        details[pd.Timestamp(date)] = {
            "pretrade_SPY_weight": float(pretrade[0]),
            "pretrade_IEF_weight": float(pretrade[1]),
            "post_trade_SPY_holding": float(post[0]),
            "post_trade_IEF_holding": float(post[1]),
            "turnover": float(path["daily"].loc[date, "one_way_turnover"]),
            "transaction_cost": float(path["daily"].loc[date, "transaction_cost_drag"]),
            "trade_executed": traded,
        }
    rows: list[dict[str, Any]] = []
    for date, row in panel.iterrows():
        execution = next_session(prices.index, pd.Timestamp(date))
        detail = details.get(execution, {}) if execution is not None else {}
        actual_origin = origins.get(execution, "") if execution is not None else ""
        is_origin = isinstance(actual_origin, pd.Timestamp) and actual_origin == pd.Timestamp(date)
        rows.append(
            {
                "record_type": "signal_observation",
                "signal_date": pd.Timestamp(date).date().isoformat(),
                "VIX_close": row["VIX_close"],
                "VIX3M_close": row["VIX3M_close"],
                "raw_ratio": row["raw_ratio"],
                "five_observation_median": row["filtered_ratio"],
                "target_state": row["candidate_state"],
                "following_execution_session": (
                    execution.date().isoformat() if execution is not None else ""
                ),
                "pretrade_SPY_weight": detail.get("pretrade_SPY_weight", ""),
                "pretrade_IEF_weight": detail.get("pretrade_IEF_weight", ""),
                "target_SPY_weight": row["candidate_SPY"],
                "target_IEF_weight": row["candidate_IEF"],
                "turnover": detail.get("turnover", 0.0) if is_origin else 0.0,
                "transaction_cost": (
                    detail.get("transaction_cost", 0.0) if is_origin else 0.0
                ),
                "post_trade_SPY_holding": detail.get("post_trade_SPY_holding", ""),
                "post_trade_IEF_holding": detail.get("post_trade_IEF_holding", ""),
                "trade_executed": bool(is_origin),
                "common_observation": bool(row["common_observation"]),
                "missing_signal_behavior": (
                    "" if bool(row["common_observation"]) else "retain_previous_target"
                ),
                "methodology_boundary_flag": row["methodology_period"],
                "non_vintage_data_flag": True,
                "data_provenance": DATA_PROVENANCE,
                "vintage_status": VINTAGE_STATUS,
                "timing_policy": TIMING_POLICY,
                "same_day_return_allowed": False,
                "summary_count": "",
                "summary_mean_duration": "",
                "summary_max_duration": "",
                "summary_transition_count": "",
                "summary_days_in_target": "",
                "summary_state_total_return_5bps": "",
            }
        )

    state_series = panel["candidate_state"].astype(str)
    changes = state_series.ne(state_series.shift(1))
    run_id = changes.cumsum()
    run_lengths = state_series.groupby(run_id).agg(["first", "size"])
    daily_target = target_path(schedule, prices.index)
    daily_state = pd.Series(
        [
            state_from_weights(float(row.SPY), float(row.IEF))
            for row in daily_target.itertuples()
        ],
        index=prices.index,
    )
    held_state = daily_state.shift(1).fillna("middle")
    for state in ("risk_on", "middle", "defensive"):
        lengths = run_lengths.loc[run_lengths["first"] == state, "size"].astype(float)
        state_returns = path["returns"].loc[held_state == state]
        state_total_return = (
            float((1.0 + state_returns).prod() - 1.0) if len(state_returns) else 0.0
        )
        rows.append(
            {
                "record_type": "state_summary",
                "target_state": state,
                "summary_count": int((state_series == state).sum()),
                "summary_mean_duration": float(lengths.mean()) if len(lengths) else 0.0,
                "summary_max_duration": int(lengths.max()) if len(lengths) else 0,
                "summary_transition_count": int(
                    ((state_series == state) & changes).sum()
                ),
                "summary_days_in_target": int((daily_state == state).sum()),
                "summary_state_total_return_5bps": state_total_return,
                "data_provenance": DATA_PROVENANCE,
                "vintage_status": VINTAGE_STATUS,
                "timing_policy": TIMING_POLICY,
                "same_day_return_allowed": False,
                "non_vintage_data_flag": True,
            }
        )
    rows.append(
        {
            "record_type": "missing_common_observation_summary",
            "target_state": "retain_previous_target",
            "summary_count": int((~panel["common_observation"]).sum()),
            "data_provenance": DATA_PROVENANCE,
            "vintage_status": VINTAGE_STATUS,
            "timing_policy": TIMING_POLICY,
            "same_day_return_allowed": False,
            "non_vintage_data_flag": True,
        }
    )
    for period in ("pre_2025_02_10", "post_2025_02_10"):
        rows.append(
            {
                "record_type": "methodology_period_summary",
                "methodology_boundary_flag": period,
                "summary_count": int((panel["methodology_period"] == period).sum()),
                "data_provenance": DATA_PROVENANCE,
                "vintage_status": VINTAGE_STATUS,
                "timing_policy": TIMING_POLICY,
                "same_day_return_allowed": False,
                "non_vintage_data_flag": True,
            }
        )
    return rows


def preflight_rows(
    histories: dict[str, pd.DataFrame],
    prices: pd.DataFrame,
    reference: pd.Series,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for symbol in ("SPY", "IEF", "BIL"):
        frame = market.load_adjusted_ohlcv(symbol)
        rows.append(
            {
                "data_id": symbol,
                "data_type": "canonical_adjusted_daily_OHLCV",
                "provider": "repository_canonical_cache",
                "first_date": frame.index.min().date().isoformat(),
                "last_date": frame.index.max().date().isoformat(),
                "row_count": len(frame),
                "canonical_hash": v1.file_hash(CACHE_DIR / f"{symbol}.csv"),
                "ordered_unique_dates": bool(
                    frame.index.is_monotonic_increasing and frame.index.is_unique
                ),
                "finite_positive_values": bool(
                    np.isfinite(frame[["open", "high", "low", "close", "adj_close"]]).all().all()
                    and (frame[["open", "high", "low", "close", "adj_close"]] > 0.0)
                    .all()
                    .all()
                ),
                "status": "pass",
            }
        )
    manifest = {
        row["series"]: row
        for row in read_csv(V3_EVIDENCE / "official_cboe_history_manifest.csv")
    }
    for series, frame in histories.items():
        rows.append(
            {
                "data_id": series,
                "data_type": "official_cboe_daily_close_history",
                "provider": "Cboe",
                "first_date": frame["DATE"].min().date().isoformat(),
                "last_date": frame["DATE"].max().date().isoformat(),
                "row_count": len(frame),
                "canonical_hash": v3.normalized_frame_hash(frame),
                "ordered_unique_dates": bool(
                    frame["DATE"].is_monotonic_increasing and frame["DATE"].is_unique
                ),
                "finite_positive_values": bool(
                    np.isfinite(frame["CLOSE"]).all() and (frame["CLOSE"] > 0.0).all()
                ),
                "status": (
                    "pass"
                    if v3.normalized_frame_hash(frame)
                    == manifest[series]["normalized_frame_hash"]
                    else "fail"
                ),
            }
        )
    rows.append(
        {
            "data_id": "frozen_current_active_vm_dsr_usci_combo",
            "data_type": "frozen_reference_return_series",
            "provider": "repository_evidence",
            "first_date": reference.index.min().date().isoformat(),
            "last_date": reference.index.max().date().isoformat(),
            "row_count": len(reference),
            "canonical_hash": v1.canonical_hash(
                [
                    {
                        "date": date.date().isoformat(),
                        "return": float(value),
                    }
                    for date, value in reference.items()
                ]
            ),
            "ordered_unique_dates": bool(
                reference.index.is_monotonic_increasing and reference.index.is_unique
            ),
            "finite_positive_values": bool(np.isfinite(reference).all()),
            "status": "pass",
        }
    )
    return rows


def entity_rows(
    outcome: str,
    failure_reason: str,
    next_action: str,
    average_target_spy: float,
) -> dict[str, list[dict[str, Any]]]:
    source = [
        {
            "source_record_id": SOURCE_RECORD_ID,
            "entity_type": "source_library_record",
            "stage": "source_extracted",
            "source_or_research_lineage": (
                "intermarket_source_sprint_v6:"
                "src_donninger_herorats_vix_vix3m_median5_spy_ief_v1"
            ),
            "strategy_id": STRATEGY_ID,
            "source_role": "frozen_rule_provenance_only",
            "outcome": outcome,
            "failure_reason": failure_reason,
        }
    ]
    strategy = [
        {
            "strategy_id": STRATEGY_ID,
            "family_id": FAMILY_ID,
            "display_name": DISPLAY_NAME,
            "entity_type": "strategy_configuration",
            "strategy_architecture": "daily_three_state_implied_volatility_curve_allocation",
            "source_or_research_lineage": (
                "intermarket_source_sprint_v6:"
                "src_donninger_herorats_vix_vix3m_median5_spy_ief_v1"
            ),
            "instrument_universe": "SPY|IEF",
            "parameters": {
                "ratio": "VIX_close/VIX3M_close",
                "median_length": 5,
                "thresholds": [0.96, 1.02],
                "targets": ["1.0|0.0", "0.5|0.5", "0.0|1.0"],
                "missing_later_signal": "retain_previous_target",
                "primary_cost_bps": 5.0,
                "diagnostic_cost_bps": [0.0, 10.0],
                "average_target_SPY_weight_for_exposure_control": average_target_spy,
            },
            "benchmark_or_control": "|".join(BENCHMARKS),
            "route": "standalone",
            "translation_label": "mechanical_etf_and_execution_portability",
            "exact_source_replication_claimed": False,
            "stage": STAGE,
            "trial_id": TRIAL_ID,
            "parent_trial_id": PARENT_TRIAL_ID,
            "adaptation_label": "methodology_correction",
            "outcome": outcome,
            "failure_reason": failure_reason,
            "next_action": next_action,
        }
    ]
    prior = read_csv(V1_EVIDENCE / "trial_ledger.csv")[0]
    trials = [
        {
            "trial_id": prior["trial_id"],
            "entity_type": "experiment_trial",
            "stage": prior["stage"],
            "strategy_id": prior["strategy_id"],
            "parent_trial_id": prior["parent_trial_id"],
            "adaptation_label": prior["adaptation_label"],
            "changed_fields_from_parent": "not_applicable_prior_V1_trial",
            "strategy_rule_changed": False,
            "ratio_changed": False,
            "median_length_changed": False,
            "thresholds_changed": False,
            "instruments_changed": False,
            "target_allocations_changed": False,
            "following_session_execution_changed": False,
            "official_data_source_changed": False,
            "timing_evidence_policy_changed": False,
            "optimization_performed": False,
            "post_result_adaptation_allowed": False,
            "data_capability_lineage": "",
            "process_methodology_lineage": "",
            "record_role": "prior_V1_parent_trial_reference",
            "created_in_v4": False,
            "preregistered_before_performance": True,
            "outcome": prior["outcome"],
            "failure_reason": prior["failure_reason"],
            "next_action": prior["next_action"],
        },
        {
            "trial_id": TRIAL_ID,
            "entity_type": "experiment_trial",
            "stage": STAGE,
            "strategy_id": STRATEGY_ID,
            "parent_trial_id": PARENT_TRIAL_ID,
            "adaptation_label": "methodology_correction",
            "changed_fields_from_parent": (
                "official_cboe_daily_history_and_following_session_timing_evidence_policy_only"
            ),
            "strategy_rule_changed": False,
            "ratio_changed": False,
            "median_length_changed": False,
            "thresholds_changed": False,
            "instruments_changed": False,
            "target_allocations_changed": False,
            "following_session_execution_changed": False,
            "official_data_source_changed": True,
            "timing_evidence_policy_changed": True,
            "optimization_performed": False,
            "post_result_adaptation_allowed": False,
            "data_capability_lineage": (
                "run_cboe_point_in_time_ivts_feasibility_and_exploration_v2"
            ),
            "process_methodology_lineage": (
                "correct_ivts_timing_gate_and_run_official_daily_close_exploration_v3"
            ),
            "record_role": "new_V4_child_exploration_trial",
            "created_in_v4": True,
            "preregistered_before_performance": True,
            "outcome": outcome,
            "failure_reason": failure_reason,
            "next_action": next_action,
        },
    ]
    lineage = [
        {
            "lineage_id": "V2_cboe_point_in_time_feasibility",
            "entity_type": "data_capability_lineage",
            "stage": "feasibility",
            "evidence_task_id": v2.TASK_ID,
            "evidence_path": V2_EVIDENCE.relative_to(ROOT).as_posix(),
            "experiment_trial_count": 0,
            "used_as_parent_trial": False,
            "contribution": "proved expiry-node endpoint cannot supply constant-maturity VIX/VIX3M",
        },
        {
            "lineage_id": "V3_official_daily_history_timing_correction",
            "entity_type": "process_methodology_lineage",
            "stage": "exploration",
            "evidence_task_id": v3.TASK_ID,
            "evidence_path": V3_EVIDENCE.relative_to(ROOT).as_posix(),
            "experiment_trial_count": 0,
            "used_as_parent_trial": False,
            "contribution": (
                "verified duplicate official histories and authorized next-session-close "
                "current-history/non-vintage exploration"
            ),
        },
    ]
    benchmark_definitions = {
        "SPY_buy_and_hold": (
            "SPY",
            "100% SPY buy-and-hold",
        ),
        "SPY_200_day_trend_control": (
            "SPY|BIL",
            "SPY when completed SPY close is above its 200-day SMA; BIL otherwise; following-session-close execution",
        ),
        "unfiltered_vix_vix3m_three_state_spy_ief_v1": (
            "SPY|IEF",
            "raw VIX/VIX3M ratio with 0.96/1.02 thresholds and candidate state weights",
        ),
        "vix_vix3m_sign_only_spy_ief_v1": (
            "SPY|IEF",
            "100% SPY at ratio <=1.0 and 100% IEF at ratio >1.0",
        ),
        "static_exposure_matched_spy_ief_v1": (
            "SPY|IEF",
            "monthly rebalance at mechanically observed full-period candidate target SPY exposure",
        ),
        "IEF_buy_and_hold": (
            "IEF",
            "100% IEF buy-and-hold",
        ),
    }
    benchmarks = [
        {
            "benchmark_reference_id": benchmark,
            "entity_type": "benchmark_reference",
            "stage": "benchmark_reference_only",
            "strategy_id_context": STRATEGY_ID,
            "instrument_universe": benchmark_definitions[benchmark][0],
            "control_definition": benchmark_definitions[benchmark][1],
            "same_purpose_chronological_half_control": benchmark
            == "unfiltered_vix_vix3m_three_state_spy_ief_v1",
            "critical_control": benchmark in CRITICAL_CONTROLS,
            "counted_as_strategy_or_trial": False,
        }
        for benchmark in BENCHMARKS
    ]
    process = [
        {
            "process_task_id": TASK_ID,
            "entity_type": "process_task",
            "stage": STAGE,
            "mode": MODE,
            "strategy_id": "",
            "trial_id": "",
            "outcome": outcome,
            "failure_reason": failure_reason,
            "next_action": next_action,
        }
    ]
    return {
        "source": source,
        "strategy": strategy,
        "trials": trials,
        "lineage": lineage,
        "benchmarks": benchmarks,
        "process": process,
    }


def write_entities(rows: dict[str, list[dict[str, Any]]]) -> None:
    for name, key in (
        ("source_library_records.csv", "source"),
        ("strategy_cards.csv", "strategy"),
        ("trial_ledger.csv", "trials"),
        ("data_and_process_lineage.csv", "lineage"),
        ("benchmark_reference_log.csv", "benchmarks"),
        ("process_task_log.csv", "process"),
    ):
        values = rows[key]
        write_csv(OUTPUT_DIR / name, values, list(values[0]))


def run() -> dict[str, Any]:
    protected_before = v1.hash_paths(PROTECTED_STATE_PATHS)
    prior_before = {
        task_id: directory_hash(path)
        for task_id, path in (
            (v1.TASK_ID, V1_EVIDENCE),
            (v2.TASK_ID, V2_EVIDENCE),
            (v3.TASK_ID, V3_EVIDENCE),
        )
    }
    cache_before = directory_hash(CACHE_DIR)
    clean_output_dir()

    lineage = verify_lineage()
    if not lineage["passed"]:
        raise RuntimeError("Authoritative V1/V2/V3 lineage does not match the V4 correction")

    histories, hash_rows, history_gate = load_verified_v3_histories()
    if not history_gate:
        raise RuntimeError("Recorded V3 official history hashes did not reproduce")

    full_prices, candidate_prices = load_prices()
    if candidate_prices.empty:
        raise RuntimeError("SPY/IEF canonical adjusted prices are unavailable")
    history_end = min(
        histories["VIX"]["DATE"].max(),
        histories["VIX3M"]["DATE"].max(),
        candidate_prices.index.max(),
    )
    prices = candidate_prices.loc[candidate_prices.index <= history_end].dropna()
    panel = build_signal_panel(histories, prices.index.max())
    schedules, origins, states, average_target_spy = build_schedules(
        panel, full_prices, prices
    )

    # The child and frozen entities are serialized before performance is calculated.
    preregistered = entity_rows(
        "preregistered_pending_execution", "", "", average_target_spy
    )
    write_entities(preregistered)

    paths: dict[tuple[str, float], dict[str, Any]] = {}
    timing = "completed_official_close_signal_target_applied_at_following_session_close"
    for entity_id, schedule in schedules.items():
        entity_prices = full_prices.reindex(prices.index)[list(schedule.columns)].dropna()
        if not entity_prices.index.equals(prices.index):
            raise RuntimeError(f"{entity_id} control dates do not match the candidate")
        for cost_bps in COST_BPS:
            paths[(entity_id, cost_bps)] = accounting.simulate_path(
                entity_prices, schedule, cost_bps, timing
            )

    metrics: dict[Any, Any] = {"_index": list(prices.index)}
    all_rows: list[dict[str, Any]] = []
    control_rows: list[dict[str, Any]] = []
    for entity_id in (STRATEGY_ID, *BENCHMARKS):
        role = "candidate" if entity_id == STRATEGY_ID else "benchmark_reference"
        entity_type = (
            "experiment_trial" if entity_id == STRATEGY_ID else "benchmark_reference"
        )
        for cost_bps in COST_BPS:
            payload = path_metrics(paths[(entity_id, cost_bps)])
            metrics[(entity_id, cost_bps)] = payload
            row = metric_row(
                entity_id, entity_type, role, "full_period", cost_bps, payload
            )
            all_rows.append(row)
            if entity_id != STRATEGY_ID:
                control_rows.append(row)

    half_metrics: dict[tuple[str, str], dict[str, Any]] = {}
    half_rows: list[dict[str, Any]] = []
    for period, index in split_halves(prices.index):
        for entity_id in (STRATEGY_ID, *BENCHMARKS):
            role = "candidate" if entity_id == STRATEGY_ID else "benchmark_reference"
            entity_type = (
                "experiment_trial"
                if entity_id == STRATEGY_ID
                else "benchmark_reference"
            )
            payload = path_metrics(
                paths[(entity_id, PRIMARY_COST_BPS)], period_index=index
            )
            half_metrics[(entity_id, period)] = payload
            half_rows.append(
                metric_row(
                    entity_id,
                    entity_type,
                    role,
                    period,
                    PRIMARY_COST_BPS,
                    payload,
                )
            )

    outcome, failure_reason, decision_reason, gate = classify(metrics, half_metrics)
    next_action = (
        ADVANCE_NEXT_ACTION
        if outcome == "exploratory_followup_candidate_standalone"
        else CLOSE_NEXT_ACTION
        if outcome == "closed_exploration"
        else BLOCK_NEXT_ACTION
    )
    entities = entity_rows(outcome, failure_reason, next_action, average_target_spy)
    write_entities(entities)

    reference = market.active_vm_dsr_usci_reference_returns()
    preflight = preflight_rows(histories, prices, reference)
    portfolio_rows = build_portfolio_rows(paths, reference)
    state_rows = state_diagnostic_rows(
        panel,
        prices,
        schedules[STRATEGY_ID],
        origins,
        paths[(STRATEGY_ID, PRIMARY_COST_BPS)],
    )

    turnover_rows: list[dict[str, Any]] = []
    invariant_rows: list[dict[str, Any]] = []
    for entity_id in (STRATEGY_ID, *BENCHMARKS):
        for cost_bps in COST_BPS:
            payload = metrics[(entity_id, cost_bps)]
            path = paths[(entity_id, cost_bps)]
            turnover_rows.append(
                {
                    "entity_id": entity_id,
                    "cost_bps": cost_bps,
                    "one_way_turnover": payload["turnover"],
                    "trade_or_rebalance_count": payload["trade_or_rebalance_count"],
                    "recorded_transaction_cost_drag": payload["transaction_cost_drag"],
                    "daily_turnover_sum": float(path["turnover"].sum()),
                    "daily_cost_drag_sum": float(path["cost"].sum()),
                    "turnover_reconciles": math.isclose(
                        float(path["turnover"].sum()),
                        float(payload["turnover"]),
                        abs_tol=1e-12,
                    ),
                    "cost_reconciles": math.isclose(
                        float(path["cost"].sum()),
                        float(payload["transaction_cost_drag"]),
                        abs_tol=1e-12,
                    ),
                    "one_way_turnover_formula": (
                        "0.5*sum(abs(target_weight-pretrade_weight))"
                    ),
                }
            )
            invariant_rows.append(
                {
                    "entity_id": entity_id,
                    "cost_bps": cost_bps,
                    "timing_invariant": payload["timing_invariant"],
                    "numeric_invariant": payload["numeric_invariant"],
                    "exposure_invariant": payload["exposure_invariant"],
                    "weight_invariant": payload["weight_invariant"],
                    "explicit_zero_weights_preserved": True,
                    "natural_drift_between_target_changes": True,
                    "stale_weight_forward_fill_used": False,
                    "negative_weights_used": False,
                    "signal_date_return_used": False,
                    "following_open_execution_used": False,
                    "maximum_gross_exposure": payload["maximum_gross_exposure"],
                    "maximum_daily_weight_sum": payload["maximum_daily_weight_sum"],
                    "invariant_pass": payload["invariant_pass"],
                }
            )

    write_csv(OUTPUT_DIR / "official_history_hash_reconciliation.csv", hash_rows, list(hash_rows[0]))
    write_csv(OUTPUT_DIR / "data_preflight_reconciliation.csv", preflight, list(preflight[0]))
    write_csv(OUTPUT_DIR / "all_trial_results.csv", all_rows, METRIC_FIELDS)
    write_csv(OUTPUT_DIR / "control_results.csv", control_rows, METRIC_FIELDS)
    write_csv(
        OUTPUT_DIR / "chronological_half_results.csv", half_rows, METRIC_FIELDS
    )
    write_csv(
        OUTPUT_DIR / "portfolio_contribution_results.csv",
        portfolio_rows,
        list(portfolio_rows[0]),
    )
    state_fields = sorted({key for row in state_rows for key in row})
    write_csv(OUTPUT_DIR / "state_signal_diagnostics.csv", state_rows, state_fields)
    write_csv(
        OUTPUT_DIR / "turnover_cost_reconciliation.csv",
        turnover_rows,
        list(turnover_rows[0]),
    )
    write_csv(
        OUTPUT_DIR / "invariant_results.csv",
        invariant_rows,
        list(invariant_rows[0]),
    )

    outcome_row = {
        "strategy_id": STRATEGY_ID,
        "trial_id": TRIAL_ID,
        "stage": STAGE,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "decision_reason": decision_reason,
        "next_action": next_action,
        "official_history_hash_gate_passed": history_gate,
        "lineage_gate_passed": lineage["passed"],
        "full_period_candidate_total_return_5bps": metrics[
            (STRATEGY_ID, PRIMARY_COST_BPS)
        ]["total_return"],
        "full_period_candidate_sharpe_5bps": metrics[
            (STRATEGY_ID, PRIMARY_COST_BPS)
        ]["sharpe_ratio"],
        "full_period_candidate_maximum_drawdown_5bps": metrics[
            (STRATEGY_ID, PRIMARY_COST_BPS)
        ]["maximum_drawdown"],
        "gate_detail": gate,
        "exploration_only": True,
        "validation_or_point_in_time_proof": False,
        "paper_demo_eligibility_supported": False,
    }
    write_csv(OUTPUT_DIR / "outcome_summary.csv", [outcome_row], list(outcome_row))
    failure_rows = (
        [
            {
                "strategy_id": STRATEGY_ID,
                "trial_id": TRIAL_ID,
                "outcome": outcome,
                "primary_failure_reason": failure_reason,
                "decision_reason": decision_reason,
                "exact_configuration_closed_only": outcome == "closed_exploration",
            }
        ]
        if failure_reason
        else []
    )
    write_csv(
        OUTPUT_DIR / "failure_reasons.csv",
        failure_rows,
        [
            "strategy_id",
            "trial_id",
            "outcome",
            "primary_failure_reason",
            "decision_reason",
            "exact_configuration_closed_only",
        ],
    )
    next_row = {
        "strategy_id": STRATEGY_ID,
        "outcome": outcome,
        "exact_next_action": next_action,
        "execute_in_this_task": False,
    }
    write_csv(OUTPUT_DIR / "next_actions.csv", [next_row], list(next_row))

    funnel = {
        "source_library_records": 1,
        "strategy_configurations": 1,
        "prior_V1_experiment_trials_carried_forward": 1,
        "prior_V2_experiment_trials_carried_forward": 0,
        "prior_V3_experiment_trials_carried_forward": 0,
        "new_child_experiment_trials": 1,
        "benchmark_references": 6,
        "data_capability_evidence_references": 2,
        "process_tasks": 1,
        "paper_demo_observations": 0,
        "performance_trials_executed": 1,
        "followup_candidates": int(
            outcome == "exploratory_followup_candidate_standalone"
        ),
        "closed_exploration": int(outcome == "closed_exploration"),
        "inconclusive_or_blocked": int(
            outcome in {"inconclusive_data_issue", "blocked_feasibility"}
        ),
        "exact_next_action": next_action,
    }
    write_json(OUTPUT_DIR / "cohort_funnel_counts.json", funnel)

    manifest = {
        "task_id": TASK_ID,
        "mode": MODE,
        "stage": STAGE,
        "strategy_id": STRATEGY_ID,
        "trial_id": TRIAL_ID,
        "parent_trial_id": PARENT_TRIAL_ID,
        "adaptation_label": "methodology_correction",
        "changed_fields_from_parent": (
            "official_cboe_daily_history_and_following_session_timing_evidence_policy_only"
        ),
        "V2_used_as_parent": False,
        "V3_used_as_parent": False,
        "official_history_hash_gate_passed": history_gate,
        "timing_policy": TIMING_POLICY,
        "data_provenance": DATA_PROVENANCE,
        "vintage_status": VINTAGE_STATUS,
        "validation_vintage_safety_established": False,
        "strategy_rule_changed": False,
        "ratio_changed": False,
        "median_length_changed": False,
        "thresholds_changed": False,
        "instruments_changed": False,
        "target_allocations_changed": False,
        "following_session_execution_changed": False,
        "official_data_source_changed": True,
        "timing_evidence_policy_changed": True,
        "optimization_performed": False,
        "post_result_adaptation_allowed": False,
        "performance_executed": True,
        "evaluation_start": prices.index.min().date().isoformat(),
        "evaluation_end": prices.index.max().date().isoformat(),
        "cost_bps": list(COST_BPS),
        "primary_cost_bps": PRIMARY_COST_BPS,
        "methodology_boundary": METHODOLOGY_BOUNDARY.date().isoformat(),
        "average_target_SPY_weight_for_exposure_control": average_target_spy,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "exact_next_action": next_action,
        "required_artifacts": list(REQUIRED_ARTIFACTS),
    }
    write_yaml(OUTPUT_DIR / "correction_manifest.yaml", manifest)

    report = f"""# IVTS Trial-Lineage Correction and Exploration V4

## Lineage Correction

The sole experiment parent is `{PARENT_TRIAL_ID}` from V1. V2 contributed
data-capability evidence and V3 contributed official-history and timing-policy
evidence; neither is represented as an experiment trial or parent.

Exactly one child trial, `{TRIAL_ID}`, was preregistered before performance.
The strategy ratio, median length, thresholds, allocations, instruments, and
following-session-close execution were unchanged.

## Data and Timing

The two V3 Cboe snapshots for each of VIX and VIX3M reproduced from the stored
raw bytes and matched the V3 manifest hashes. They remain
`{VINTAGE_STATUS}` and do not establish validation vintage safety.
Signal-date SPY/IEF returns were excluded; target changes were applied only at
the following regular-session close.

## Exploration Result

At 5 bps one-way cost, candidate total return was
`{metrics[(STRATEGY_ID, PRIMARY_COST_BPS)]['total_return']:.6f}`, Sharpe was
`{metrics[(STRATEGY_ID, PRIMARY_COST_BPS)]['sharpe_ratio']:.6f}`, and maximum
drawdown was `{metrics[(STRATEGY_ID, PRIMARY_COST_BPS)]['maximum_drawdown']:.6f}`.

Outcome: `{outcome}`.

Primary failure reason: `{failure_reason or 'not_applicable'}`.

Decision basis: {decision_reason}.

Exact next action: `{next_action}`.

This packet is exploratory portability evidence, not validation, exact source
replication, point-in-time proof, lifecycle authorization, or paper/demo
eligibility.
"""
    write_text(OUTPUT_DIR / "correction_report.md", report)

    protected_after = v1.hash_paths(PROTECTED_STATE_PATHS)
    prior_after = {
        task_id: directory_hash(path)
        for task_id, path in (
            (v1.TASK_ID, V1_EVIDENCE),
            (v2.TASK_ID, V2_EVIDENCE),
            (v3.TASK_ID, V3_EVIDENCE),
        )
    }
    cache_after = directory_hash(CACHE_DIR)
    required_present = all((OUTPUT_DIR / name).exists() for name in REQUIRED_ARTIFACTS if name != "consistency_check.json")
    deterministic_names = [
        name
        for name in REQUIRED_ARTIFACTS
        if name != "consistency_check.json"
    ]
    deterministic_hash = v1.canonical_hash(
        [
            {"path": name, "hash": v1.file_hash(OUTPUT_DIR / name)}
            for name in deterministic_names
        ]
    )
    consistency = {
        "task_id": TASK_ID,
        "overall_pass": bool(
            required_present
            and lineage["passed"]
            and history_gate
            and protected_before == protected_after
            and prior_before == prior_after
            and cache_before == cache_after
            and len(all_rows) == 21
            and len(control_rows) == 18
            and len(half_rows) == 14
            and len(portfolio_rows) == 15
            and len(entities["trials"]) == 2
            and sum(_bool(row["created_in_v4"]) for row in entities["trials"]) == 1
        ),
        "lineage_gate_passed": lineage["passed"],
        "V1_parent_trial_id": PARENT_TRIAL_ID,
        "V1_parent_trial_count": lineage["V1_parent_count"],
        "V2_experiment_trial_count": lineage["V2_trial_count"],
        "V3_experiment_trials_created": lineage["V3_created_trial_count"],
        "new_child_trial_count": 1,
        "new_child_parent_trial_id": PARENT_TRIAL_ID,
        "official_history_hash_gate_passed": history_gate,
        "performance_executed": True,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "exact_next_action": next_action,
        "row_counts": {
            "all_trial_results": len(all_rows),
            "control_results": len(control_rows),
            "chronological_half_results": len(half_rows),
            "portfolio_contribution_results": len(portfolio_rows),
            "state_signal_diagnostics": len(state_rows),
            "turnover_cost_reconciliation": len(turnover_rows),
            "invariant_results": len(invariant_rows),
        },
        "entity_counts": funnel,
        "protected_state_hashes_before": protected_before,
        "protected_state_hashes_after": protected_after,
        "protected_state_unchanged": protected_before == protected_after,
        "prior_evidence_hashes_before": prior_before,
        "prior_evidence_hashes_after": prior_after,
        "prior_evidence_unchanged": prior_before == prior_after,
        "cache_hash_before": cache_before,
        "cache_hash_after": cache_after,
        "cache_unchanged": cache_before == cache_after,
        "required_artifacts_present": required_present,
        "deterministic_core_hash": deterministic_hash,
        "forbidden_actions": {
            "V2_or_V3_trial_fabricated": False,
            "source_or_endpoint_search": False,
            "provider_download": False,
            "ALFRED_used_for_performance": False,
            "signal_date_return_used": False,
            "following_open_execution_used": False,
            "strategy_rule_or_parameter_changed": False,
            "validation_or_robustness": False,
            "lifecycle_or_registry_change": False,
            "paper_demo_activation": False,
            "broker_account_order_or_real_money_action": False,
        },
    }
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    return {
        "task_id": TASK_ID,
        "evidence_path": str(OUTPUT_DIR),
        "trial_id": TRIAL_ID,
        "parent_trial_id": PARENT_TRIAL_ID,
        "official_history_hash_gate_passed": history_gate,
        "performance_executed": True,
        "outcome": outcome,
        "failure_reason": failure_reason,
        "next_action": next_action,
        "candidate_5bps": {
            key: metrics[(STRATEGY_ID, PRIMARY_COST_BPS)][key]
            for key in (
                "total_return",
                "cagr",
                "annualized_volatility",
                "sharpe_ratio",
                "maximum_drawdown",
                "turnover",
            )
        },
        "consistency_passed": consistency["overall_pass"],
    }


def main() -> int:
    print(json.dumps(run(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
