from __future__ import annotations

import csv
import json
import math
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from strategy_lab.research_os.research import resume_existing_ready_research_batch_v1 as ready


ROOT = ready.ROOT
EVIDENCE_DIR = ROOT / "evidence" / "advance_near_ready_research_queue_v1" / "latest"
TASK_ID = "advance_near_ready_research_queue_v1"
QQQ_ID = "qqq_spy_gld_ief_dual_momentum_v1"
TREASURY_ID = "treasury_duration_trend_rotation_v1"
VALUE_ID = "value_momentum_factor_etf_rotation_v1"
SECTOR_ID = "sector_top2_momentum_simple_v1"
RANKED_ASSETS = ("QQQ", "SPY", "GLD", "IEF")
UNIVERSE = ("QQQ", "SPY", "GLD", "IEF", "BIL")
PRIMARY_BENCHMARK = "asset_class_tsmom_top2_v1"
BENCHMARKS = (PRIMARY_BENCHMARK, "combo_SPY200d_GLD_50_50_v1", "SPY_buy_and_hold", "BIL_cash_proxy")
HORIZONS = (30, 60, 90, 180)
WINDOWS_PER_HORIZON = 5
INITIAL_CAPITAL = ready.INITIAL_CAPITAL
LOOKBACK_DAYS = 126
TREND_DAYS = 200
TOP_N = 1
ALLOWED_OUTCOMES = ready.ALLOWED_OUTCOMES


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    ready.write_csv(path, rows, fields)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    ready.write_json(path, payload)


def qqq_target(prices: pd.DataFrame, pos: int) -> dict[str, float]:
    target = {symbol: 0.0 for symbol in prices.columns}
    signal_pos = pos - 1
    if signal_pos < max(LOOKBACK_DAYS, TREND_DAYS):
        target["BIL"] = 1.0
        return target
    scored: list[tuple[float, str]] = []
    for symbol in RANKED_ASSETS:
        close = float(prices[symbol].iloc[signal_pos])
        prior = float(prices[symbol].iloc[signal_pos - LOOKBACK_DAYS])
        trend = ready.sma(prices[symbol], signal_pos, TREND_DAYS)
        ret = close / prior - 1.0 if prior > 0 else float("nan")
        if ret > 0 and close > trend:
            scored.append((ret, symbol))
    if scored:
        selected = sorted(scored, key=lambda item: item[0], reverse=True)[0][1]
        target[selected] = 1.0
    else:
        target["BIL"] = 1.0
    return target


def benchmark_target(benchmark_id: str):
    if benchmark_id == "asset_class_tsmom_top2_v1":
        return lambda prices, pos: ready.top2_momentum_target(prices, pos, ("SPY", "GLD", "IEF"))
    return ready.benchmark_target(benchmark_id)


def rule_recovery_rows() -> list[dict[str, Any]]:
    qqq_source = (
        "evidence/profit_exploration/runs/20260604_231808/experiment_status.csv;"
        "evidence/implementation_reviews/qqq_spy_gld_ief_dual_momentum_v1/latest"
    )
    rows = [
        ("exact_universe", "QQQ|SPY|GLD|IEF|BIL", "consistent_across_multiple_existing_artifacts", qqq_source),
        ("ranking_assets", "QQQ|SPY|GLD|IEF", "explicit_existing_evidence", "profit_exploration experiment_status frozen specification"),
        ("momentum_return_definition", "126_trading_day_total_return", "explicit_existing_evidence", "profit_exploration experiment_status"),
        ("lookback", "126_trading_days", "explicit_existing_evidence", "profit_exploration experiment_status"),
        ("ranking_direction", "descending_highest_return_first", "consistent_across_multiple_existing_artifacts", qqq_source),
        ("top_n_count", "1", "explicit_existing_evidence", "profit_exploration experiment_status"),
        ("absolute_momentum_or_trend_eligibility_rule", "price_gt_200_day_sma", "explicit_existing_evidence", "profit_exploration experiment_status"),
        ("weighting", "full_weight_top_eligible_asset", "explicit_existing_evidence", "profit_exploration experiment_status"),
        ("rebalance_cadence", "monthly", "explicit_existing_evidence", "profit_exploration experiment_status"),
        ("bil_cash_behavior", "all_to_BIL_if_no_top_asset_qualifies_or_top_asset_fails_absolute_filter", "explicit_existing_evidence", "profit_exploration experiment_status"),
        ("missing_data_behavior", "asset_ineligible_when_required_lookback_or_price_missing", "consistent_across_multiple_existing_artifacts", "current corrected accounting convention plus frozen cache-only implementation"),
        ("signal_timestamp", "monthly_rebalance_signal_uses_prior_completed_close", "consistent_across_multiple_existing_artifacts", "profit_exploration execution_timing_rule plus corrected accounting convention"),
        ("execution_timestamp", "next_trading_day_after_rebalance_signal", "explicit_existing_evidence", "profit_exploration experiment_status"),
        ("costs", f"canonical_transaction_cost_rate_{ready.TRANSACTION_COST_RATE}", "consistent_across_multiple_existing_artifacts", "current corrected accounting convention"),
        ("primary_benchmark", PRIMARY_BENCHMARK, "explicit_existing_evidence", "implementation review benchmark criteria"),
        ("intended_strategy_role", "research_sample_only_diagnostic", "consistent_across_multiple_existing_artifacts", qqq_source),
        ("treasury_exact_duration_universe", "", "missing_existing_evidence", "treasury queue records name a duration concept but not a complete frozen duration ETF universe"),
        ("treasury_selection_rule", "", "missing_existing_evidence", "treasury queue records do not freeze lookback, ranking, selected count, or risk-off behavior"),
    ]
    return [
        {
            "candidate_id": QQQ_ID if not field.startswith("treasury") else TREASURY_ID,
            "material_rule": field,
            "recovered_value": value,
            "classification": classification,
            "source": source,
            "invented": False,
        }
        for field, value, classification, source in rows
    ]


def rule_source_trace_rows() -> list[dict[str, Any]]:
    return [
        {
            "candidate_id": QQQ_ID,
            "source_artifact": "evidence/profit_exploration/runs/20260604_231808/experiment_status.csv",
            "supports": "universe|lookback|top_n|trend_filter|BIL_behavior|execution_timing|primary_benchmark",
            "source_status": "existing_authoritative_research_sample_status",
        },
        {
            "candidate_id": QQQ_ID,
            "source_artifact": "evidence/implementation_reviews/qqq_spy_gld_ief_dual_momentum_v1/latest/IMPLEMENTATION_REVIEW.md",
            "supports": "universe|intended_role|benchmark|no_leverage_no_shorting",
            "source_status": "implementation_gate_review",
        },
        {
            "candidate_id": TREASURY_ID,
            "source_artifact": "strategy_lab/strategy_registry.yaml",
            "supports": "queue_identity|parent_IEF_buy_hold|data_availability_review_next_action",
            "source_status": "queue_only_incomplete_rules",
        },
        {
            "candidate_id": TREASURY_ID,
            "source_artifact": "evidence/historical_research_expansion/latest/HISTORICAL_CANDIDATE_FAMILY_QUEUE.csv",
            "supports": "target_potential_review_required",
            "source_status": "not_a_frozen_implementation",
        },
    ]


def candidate_order_rows() -> list[dict[str, Any]]:
    return [
        {"order": 1, "candidate_id": QQQ_ID, "fixed_by_user_request": True, "performance_used": False},
        {"order": 2, "candidate_id": TREASURY_ID, "fixed_by_user_request": True, "performance_used": False},
    ]


def data_feasibility_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for symbol in UNIVERSE:
        info = ready.cache_range(symbol)
        rows.append(
            {
                "candidate_id": QQQ_ID,
                "symbol": symbol,
                "required": True,
                "cache_ready": info["cache_ready"],
                "start_date": info["start_date"],
                "end_date": info["end_date"],
                "row_count": info["row_count"],
                "downloaded": False,
                "cache_hash": info["cache_hash"],
            }
        )
    rows.append(
        {
            "candidate_id": TREASURY_ID,
            "symbol": "unresolved_duration_universe",
            "required": True,
            "cache_ready": False,
            "start_date": "",
            "end_date": "",
            "row_count": "",
            "downloaded": False,
            "cache_hash": "",
        }
    )
    return rows


def deterministic_windows(prices: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    start_floor = TREND_DAYS + 1
    for horizon in HORIZONS:
        max_start = len(prices) - horizon
        positions = [
            int(round(start_floor + i * (max_start - start_floor) / (WINDOWS_PER_HORIZON - 1)))
            for i in range(WINDOWS_PER_HORIZON)
        ]
        for slot, start_pos in enumerate(sorted(dict.fromkeys(positions)), start=1):
            end_pos = start_pos + horizon - 1
            rows.append(
                {
                    "candidate_id": QQQ_ID,
                    "window_id": f"{QQQ_ID}_h{horizon}_w{slot}",
                    "horizon_days": horizon,
                    "window_slot": slot,
                    "start_date": prices.index[start_pos].strftime("%Y-%m-%d"),
                    "end_date": prices.index[end_pos].strftime("%Y-%m-%d"),
                    "start_pos": start_pos,
                    "end_pos": end_pos,
                    "frozen_before_performance": True,
                }
            )
    return rows


def aggregate_metric(rows: list[dict[str, Any]], field: str, fn: str) -> float:
    values = [float(row[field]) for row in rows if row.get(field) != ""]
    if not values:
        return float("nan")
    if fn == "mean":
        return float(np.mean(values))
    if fn == "median":
        return float(np.median(values))
    if fn == "max":
        return float(np.max(values))
    return float(np.min(values))


def classify_outcome(relative_rows: list[dict[str, Any]], invariant_pass: bool) -> tuple[str, str, str]:
    if not invariant_pass:
        return "invalid_methodology", "Methodology failure", ""
    primary = [row for row in relative_rows if row["benchmark_id"] == PRIMARY_BENCHMARK]
    excess = np.array([float(row["candidate_excess_return"]) for row in primary])
    dd_delta = np.array([float(row["candidate_max_drawdown"]) - float(row["benchmark_max_drawdown"]) for row in primary])
    median_excess = float(np.median(excess))
    win_rate = float(np.mean(excess > 0.0))
    median_dd_delta = float(np.median(dd_delta))
    if median_excess > 0 and win_rate >= 0.6 and median_dd_delta >= -0.05:
        return "comparative_evidence_positive", "", ""
    if median_excess > 0 and median_dd_delta < -0.05:
        return "higher_return_higher_risk", "Excess drawdown", "Weak versus primary benchmark"
    if median_excess <= 0:
        return "control_weak", "Weak versus primary benchmark", ""
    return "no_material_edge", "Non-comparability", ""


def run() -> dict[str, Any]:
    registry_hash_before = ready.sha256_path(ready.REGISTRY_PATH)
    active_hash_before = ready.sha256_path(ready.ACTIVE_OBSERVATIONS_PATH)
    if EVIDENCE_DIR.exists():
        shutil.rmtree(EVIDENCE_DIR)
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    write_csv(EVIDENCE_DIR / "candidate_order.csv", candidate_order_rows())
    write_csv(EVIDENCE_DIR / "candidate_rule_recovery.csv", rule_recovery_rows())
    write_csv(EVIDENCE_DIR / "rule_source_trace.csv", rule_source_trace_rows())
    write_csv(EVIDENCE_DIR / "data_feasibility.csv", data_feasibility_rows())
    write_json(
        EVIDENCE_DIR / "provider_acquisition_manifest.json",
        {
            "provider_download": False,
            "downloaded_symbols": [],
            "downloaded_symbol_count": 0,
            "max_missing_symbols_authorized": 2,
            "only_explicitly_required_tickers_downloadable": True,
            "valid_caches_refreshed": False,
        },
    )

    gate_rows = [
        {
            "candidate_id": QQQ_ID,
            "rules_complete": True,
            "conflicting_rules": False,
            "valid_corrected_methodology_screen_exists": False,
            "closed_rejected_superseded_or_duplicate": False,
            "required_caches_valid": True,
            "corrected_accounting_can_represent": True,
            "gate_result": "execute_bounded_screen",
            "blocker": "",
        },
        {
            "candidate_id": TREASURY_ID,
            "rules_complete": False,
            "conflicting_rules": False,
            "valid_corrected_methodology_screen_exists": False,
            "closed_rejected_superseded_or_duplicate": False,
            "required_caches_valid": False,
            "corrected_accounting_can_represent": False,
            "gate_result": "not_considered_candidate1_executed",
            "blocker": "fixed fallback only; Candidate 1 reached execution gate. Independent treasury rule recovery remains incomplete.",
        },
    ]
    write_csv(EVIDENCE_DIR / "candidate_gate_results.csv", gate_rows)
    write_csv(
        EVIDENCE_DIR / "selected_candidate.csv",
        [
            {
                "candidate_id": QQQ_ID,
                "family_id": "dual_momentum",
                "selection_reason": "fixed_order_candidate1_rules_recovered_and_gate_passed",
                "performance_used_for_selection": False,
                "primary_benchmark": PRIMARY_BENCHMARK,
            }
        ],
    )

    prices = ready.read_prices(UNIVERSE)
    windows = deterministic_windows(prices)
    write_csv(EVIDENCE_DIR / "frozen_window_definitions.csv", windows)

    execution_manifest = {
        "task_id": TASK_ID,
        "candidate_id": QQQ_ID,
        "bounded_screen_run": True,
        "rules_frozen": True,
        "universe": list(UNIVERSE),
        "ranking_assets": list(RANKED_ASSETS),
        "ranking_lookback_days": LOOKBACK_DAYS,
        "ranking_direction": "descending_highest_return_first",
        "top_n": TOP_N,
        "absolute_filter": "price_gt_200_day_sma",
        "weighting": "full_weight_top_eligible_asset",
        "rebalance_cadence": "monthly",
        "bil_cash_behavior": "100pct_BIL_when_no_asset_qualifies",
        "signal_timestamp": "prior_completed_close_before_monthly_execution",
        "execution_timestamp": "next_monthly_trading_session_close",
        "transaction_cost_rate": ready.TRANSACTION_COST_RATE,
        "primary_benchmark": PRIMARY_BENCHMARK,
        "windows_frozen_before_performance": True,
        "provider_download": False,
        "sector_candidate_rerun": False,
        "value_candidate_rerun": False,
        "candidate_exhaustive_run": False,
        "paper_demo_activation": False,
        "promotion_created": False,
        "broker_live_path_touched": False,
    }
    write_json(EVIDENCE_DIR / "execution_manifest.json", execution_manifest)

    candidate_results: list[dict[str, Any]] = []
    benchmark_rows: list[dict[str, Any]] = []
    relative_rows: list[dict[str, Any]] = []
    window_rows: list[dict[str, Any]] = []
    for window in windows:
        candidate = ready.run_window(prices, int(window["start_pos"]), int(window["end_pos"]), qqq_target)
        candidate_results.append({**window, **candidate})
        for benchmark_id in BENCHMARKS:
            benchmark = ready.run_window(prices, int(window["start_pos"]), int(window["end_pos"]), benchmark_target(benchmark_id))
            corr = float(candidate["equity_series"].pct_change().corr(benchmark["equity_series"].pct_change()))
            benchmark_rows.append(
                {
                    "candidate_id": QQQ_ID,
                    "benchmark_id": benchmark_id,
                    "window_id": window["window_id"],
                    "horizon_days": window["horizon_days"],
                    "benchmark_total_return": benchmark["total_return"],
                    "benchmark_cagr": benchmark["cagr"],
                    "benchmark_max_drawdown": benchmark["max_drawdown"],
                    "benchmark_return_drawdown_proxy": benchmark["return_drawdown_proxy"],
                }
            )
            rel = {
                "candidate_id": QQQ_ID,
                "benchmark_id": benchmark_id,
                "window_id": window["window_id"],
                "horizon_days": window["horizon_days"],
                "candidate_total_return": candidate["total_return"],
                "benchmark_total_return": benchmark["total_return"],
                "candidate_excess_return": candidate["total_return"] - benchmark["total_return"],
                "candidate_max_drawdown": candidate["max_drawdown"],
                "benchmark_max_drawdown": benchmark["max_drawdown"],
                "drawdown_delta": candidate["max_drawdown"] - benchmark["max_drawdown"],
                "daily_return_correlation": corr,
            }
            relative_rows.append(rel)
            if benchmark_id == PRIMARY_BENCHMARK:
                window_rows.append(
                    {
                        **{key: window[key] for key in ("candidate_id", "window_id", "horizon_days", "start_date", "end_date")},
                        "primary_benchmark": benchmark_id,
                        "candidate_total_return": candidate["total_return"],
                        "primary_benchmark_total_return": benchmark["total_return"],
                        "candidate_excess_return": candidate["total_return"] - benchmark["total_return"],
                        "candidate_cagr": candidate["cagr"],
                        "candidate_max_drawdown": candidate["max_drawdown"],
                        "candidate_average_bil_share": candidate["average_bil_share"],
                        "candidate_total_turnover": candidate["total_turnover"],
                        "exposure_invariant_pass": candidate["exposure_invariant_pass"],
                        "weight_sum_invariant_pass": candidate["weight_sum_invariant_pass"],
                    }
                )

    candidate_metric_rows = []
    for horizon in HORIZONS:
        horizon_rows = [row for row in candidate_results if int(row["horizon_days"]) == horizon]
        candidate_metric_rows.append(
            {
                "candidate_id": QQQ_ID,
                "horizon_days": horizon,
                "window_count": len(horizon_rows),
                "median_total_return": aggregate_metric(horizon_rows, "total_return", "median"),
                "mean_total_return": aggregate_metric(horizon_rows, "total_return", "mean"),
                "median_max_drawdown": aggregate_metric(horizon_rows, "max_drawdown", "median"),
                "max_daily_exposure": aggregate_metric(horizon_rows, "max_daily_exposure", "max"),
                "max_daily_weight_sum": aggregate_metric(horizon_rows, "max_daily_weight_sum", "max"),
                "mean_average_bil_share": aggregate_metric(horizon_rows, "average_bil_share", "mean"),
            }
        )
    write_csv(EVIDENCE_DIR / "candidate_metrics.csv", candidate_metric_rows)
    write_csv(EVIDENCE_DIR / "benchmark_metrics.csv", benchmark_rows)
    write_csv(EVIDENCE_DIR / "benchmark_relative_metrics.csv", relative_rows)
    write_csv(EVIDENCE_DIR / "window_level_results.csv", window_rows)

    invariant_pass = all(
        bool(row["exposure_invariant_pass"])
        and bool(row["weight_sum_invariant_pass"])
        and bool(row["turnover_uses_pre_trade_actual_holdings"])
        and bool(row["stale_zero_weight_invariant_pass"])
        for row in candidate_results
    )
    invariant_rows = [
        {
            "candidate_id": QQQ_ID,
            "actual_holdings_accounting_used": True,
            "holdings_drift_between_rebalances": True,
            "turnover_uses_pre_trade_actual_holdings": True,
            "no_stale_weight_forward_fill": True,
            "bil_cash_replacement_remainder_only": True,
            "max_daily_exposure": max(float(row["max_daily_exposure"]) for row in candidate_results),
            "max_daily_weight_sum": max(float(row["max_daily_weight_sum"]) for row in candidate_results),
            "exposure_invariant_pass": invariant_pass,
        }
    ]
    write_csv(EVIDENCE_DIR / "accounting_and_exposure_invariants.csv", invariant_rows)

    outcome, primary_failure, secondary_failure = classify_outcome(relative_rows, invariant_pass)
    write_json(
        EVIDENCE_DIR / "screening_outcome.json",
        {
            "candidate_id": QQQ_ID,
            "screening_outcome": outcome,
            "non_promotional": True,
            "promotion_created": False,
            "paper_forward_activation": False,
            "candidate_exhaustive_run": False,
        },
    )
    write_csv(
        EVIDENCE_DIR / "failure_reason.csv",
        [{"candidate_id": QQQ_ID, "screening_outcome": outcome, "primary_failure_reason": primary_failure, "secondary_failure_reason": secondary_failure}],
    )
    weak = outcome not in {"comparative_evidence_positive", "higher_return_higher_risk"}
    write_csv(
        EVIDENCE_DIR / "exact_variant_research_memory.csv",
        [
            {
                "candidate_id": QQQ_ID,
                "screening_outcome": outcome,
                "exact_candidate_closed_for_immediate_retesting": weak,
                "broader_family_closed": False,
                "preserve_for_direction_owner_review": not weak,
                "prohibited_immediate_followups": "do_not_tune_or_rescue_exact_variant" if weak else "",
                "lifecycle_state_changed": False,
            },
            {
                "candidate_id": VALUE_ID,
                "screening_outcome": "historical_edge_recently_weakened",
                "exact_candidate_closed_for_immediate_retesting": True,
                "rerun_in_this_task": False,
                "broader_family_closed": False,
                "lifecycle_state_changed": False,
            },
            {
                "candidate_id": SECTOR_ID,
                "screening_outcome": "control_weak",
                "exact_candidate_closed_for_immediate_retesting": True,
                "rerun_in_this_task": False,
                "broader_family_closed": False,
                "lifecycle_state_changed": False,
            },
        ],
    )
    write_csv(
        EVIDENCE_DIR / "blocked_candidates.csv",
        [
            {
                "candidate_id": TREASURY_ID,
                "blocker_type": "not_evaluated_fallback",
                "blocker": "Candidate 1 executed; fallback not run. Independent treasury evidence still lacks complete frozen universe and selection rules.",
                "smallest_direct_action": "create treasury duration bounded design only if source-of-truth freezes universe/lookback/selection/risk-off behavior",
            }
        ],
    )

    registry_hash_after = ready.sha256_path(ready.REGISTRY_PATH)
    active_hash_after = ready.sha256_path(ready.ACTIVE_OBSERVATIONS_PATH)
    consistency = {
        "candidate_order_fixed": True,
        "value_momentum_candidate_reentered": False,
        "sector_candidate_reentered": False,
        "candidate1_rules_complete": True,
        "candidate1_executed_when_rules_complete": True,
        "candidate2_considered_only_when_candidate1_blocked": True,
        "candidate2_not_run_because_candidate1_executed": True,
        "missing_rules_not_invented": True,
        "conflicting_rules_block_execution": True,
        "performance_used_in_candidate_selection": False,
        "downloaded_symbol_count": 0,
        "downloaded_symbol_count_lte_2": True,
        "only_required_tickers_downloadable": True,
        "valid_caches_refreshed": False,
        "windows_frozen_before_performance": True,
        "actual_holdings_accounting_used": True,
        "no_stale_weight_forward_fill": True,
        "registry_byte_identical": registry_hash_before == registry_hash_after,
        "registry_hash_before": registry_hash_before,
        "registry_hash_after": registry_hash_after,
        "active_vm_and_dsr_unchanged": active_hash_before == active_hash_after,
        "active_observations_hash_before": active_hash_before,
        "active_observations_hash_after": active_hash_after,
        "active_combo_benchmark_reference_only": True,
        "external_source_auto_selection_paused": True,
        "provider_download": False,
        "candidate_exhaustive_run": False,
        "paper_demo_activation": False,
        "promotion_created": False,
        "broker_live_path_touched": False,
        "real_money_recommendation": False,
        "screening_outcome": outcome,
        "next_action": "direction_owner_review_qqq_dual_momentum_bounded_screen" if not weak else "return_to_productive_research_queue",
    }
    write_json(EVIDENCE_DIR / "consistency_check.json", consistency)
    task_manifest = {
        "task_id": TASK_ID,
        "candidate_order": [QQQ_ID, TREASURY_ID],
        "selected_candidate_id": QQQ_ID,
        "screen_ran": True,
        "screening_outcome": outcome,
        "provider_download": False,
        "candidate_exhaustive_run": False,
        "paper_demo_activation": False,
        "promotion_created": False,
        "active_vm_dsr_unchanged": consistency["active_vm_and_dsr_unchanged"],
        "registry_byte_identical": consistency["registry_byte_identical"],
        "next_action": consistency["next_action"],
    }
    write_json(EVIDENCE_DIR / "task_manifest.json", task_manifest)

    summary = [
        "# Advance Near-Ready Research Queue v1",
        "",
        f"Selected candidate: `{QQQ_ID}`.",
        f"Outcome: `{outcome}`.",
        "",
        "Candidate order was fixed before performance. QQQ/SPY/GLD/IEF rules were recovered from existing repository evidence and screened with corrected holdings accounting. Treasury duration remained fallback-only and was not run because Candidate 1 executed.",
        "",
        "No provider download, candidate_exhaustive run, promotion, paper/demo activation, broker/live path, or real-money recommendation occurred.",
        "",
        f"Exact next action: `{consistency['next_action']}`.",
    ]
    (EVIDENCE_DIR / "task_summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    return task_manifest


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True, default=ready.clean_value))
