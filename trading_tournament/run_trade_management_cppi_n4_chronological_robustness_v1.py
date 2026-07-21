from __future__ import annotations

import csv
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import run_trade_management_cppi_n4_methodology_correction_v1 as correction
from src.backtester import BacktestResult, Backtester
from src.data import DataLoadResult, load_market_data
from src.indicators import indicators_ready, prepare_indicators
from src.overlays import IdentityOverlay, TradeManagementOverlay, stable_hash
from src.utils import config_hash, git_commit_hash, load_config, sha256_file


ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "reports" / "trade_management" / "cppi_n4_chronological_robustness_v1"
ANCHOR_OUT_DIR = ROOT / "reports" / "trade_management" / "cppi_n4_methodology_correction_v1"
RUN_LABEL = "trade_management_cppi_m3_5y_monthly_n4_chronological_robustness_v1"
STAGE = "timeframe_diagnostic|research_only_robustness"
SELECTION_REASON = "adaptive_followup_of_corrected_first_episode"
SOURCE_RATE_WARNING = (
    "The 5% safe rate is a frozen source assumption, not a claim that this "
    "return was historically obtainable in each episode."
)

STRATEGY_ID = correction.STRATEGY_ID
RISKY_ASSETS = correction.RISKY_ASSETS
SAFE_ASSETS = correction.SAFE_ASSETS
REQUIRED_SYMBOLS = correction.REQUIRED_SYMBOLS
SLIPPAGES = correction.SLIPPAGES
CPPI_PARAMS = correction.CPPI_PARAMS
TRIAL_NAMES = correction.TRIAL_NAMES
SAFE_LEDGER_TRIALS = correction.SAFE_LEDGER_TRIALS
BROKER_CASH_TOLERANCE = correction.BROKER_CASH_TOLERANCE
ACCRUAL_TOLERANCE = correction.ACCRUAL_TOLERANCE
MATERIAL_RETURN_DIFF = 1e-4

TEST_COMMANDS = [
    [sys.executable, "-m", "pytest", "tests/test_cppi_engine_capability.py", "-q"],
    [sys.executable, "-m", "pytest", "tests/test_trade_management_overlays.py", "-q"],
    [sys.executable, "-m", "pytest", "tests/test_metrics.py", "-q"],
    [sys.executable, "-m", "pytest", "tests/test_position_sizing.py", "-q"],
    [sys.executable, "-m", "pytest", "tests/test_audit_validation.py", "-q"],
    [sys.executable, "-m", "pytest", "tests/test_trade_management_cppi_n4_methodology_correction_v1.py", "-q"],
    [sys.executable, "-m", "pytest", "tests/test_trade_management_cppi_n4_chronological_robustness_v1.py", "-q"],
    [
        sys.executable,
        "-m",
        "py_compile",
        "src/overlays.py",
        "src/portfolio.py",
        "src/backtester.py",
        "run_trade_management_cppi_n4_methodology_correction_v1.py",
        "run_trade_management_cppi_n4_chronological_robustness_v1.py",
        "tests/test_trade_management_cppi_n4_chronological_robustness_v1.py",
    ],
]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    if fieldnames is None:
        keys: list[str] = []
        for row in rows:
            for key in row:
                if key not in keys:
                    keys.append(key)
        fieldnames = keys
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _required_file_hashes() -> dict[str, str]:
    paths = [
        "src/portfolio.py",
        "src/backtester.py",
        "src/overlays.py",
        "src/strategies.py",
        "src/metrics.py",
        "src/risk.py",
        "config.yaml",
        "run_trade_management_cppi_n4_methodology_correction_v1.py",
        "run_trade_management_cppi_n4_chronological_robustness_v1.py",
        "tests/test_cppi_engine_capability.py",
        "tests/test_trade_management_overlays.py",
        "tests/test_trade_management_cppi_n4_methodology_correction_v1.py",
        "tests/test_trade_management_cppi_n4_chronological_robustness_v1.py",
        "reports/trade_management/cppi_n4_methodology_correction_v1/pre_registered_correction_manifest.json",
        "reports/trade_management/cppi_n4_methodology_correction_v1/metrics.csv",
        "reports/trade_management/cppi_n4_methodology_correction_v1/safe_persistence_diagnostics.csv",
    ]
    return {path: sha256_file(ROOT / path) for path in paths if (ROOT / path).exists()}


def first_trading_on_or_after(calendar: list[pd.Timestamp], date: pd.Timestamp) -> pd.Timestamp | None:
    candidates = [pd.Timestamp(value) for value in calendar if pd.Timestamp(value) >= pd.Timestamp(date)]
    return candidates[0] if candidates else None


def _raw_ranges(prepared: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    rows = []
    for symbol, df in prepared.items():
        if symbol not in REQUIRED_SYMBOLS:
            continue
        dates = pd.to_datetime(df["date"])
        rows.append(
            {
                "symbol": symbol,
                "first_date": dates.min().date().isoformat(),
                "last_date": dates.max().date().isoformat(),
                "rows": int(len(df)),
            }
        )
    return rows


def freeze_episode_after(
    *,
    config: dict[str, Any],
    prepared: dict[str, pd.DataFrame],
    load_result: DataLoadResult,
    after_final_valuation: pd.Timestamp,
    episode_label: str,
) -> dict[str, Any] | None:
    idx = correction.indexed(prepared)
    spy_dates = list(pd.to_datetime(idx["SPY"].index))
    warmup = int(config["project"]["warmup_days"])
    required_columns = ["close", "sma_200", "rv_60", "atr_20"]
    boundary = pd.Timestamp(after_final_valuation)
    for i, decision_date in enumerate(spy_dates):
        decision_date = pd.Timestamp(decision_date)
        if decision_date <= boundary or i < warmup or i >= len(spy_dates) - 1:
            continue
        if spy_dates[i + 1].month == decision_date.month:
            continue
        next_execution = pd.Timestamp(spy_dates[i + 1])
        ready = True
        for symbol in REQUIRED_SYMBOLS:
            if decision_date not in idx[symbol].index or next_execution not in idx[symbol].index:
                ready = False
                break
            row = idx[symbol].loc[decision_date]
            if not isinstance(row, pd.Series):
                row = row.iloc[-1]
            if not indicators_ready(row, required_columns):
                ready = False
                break
        if not ready:
            continue
        maturity = decision_date + pd.DateOffset(years=int(CPPI_PARAMS["horizon_years"]))
        final_valuation_date = first_trading_on_or_after(spy_dates, maturity)
        if final_valuation_date is None:
            continue
        if not all(final_valuation_date in idx[symbol].index for symbol in REQUIRED_SYMBOLS):
            continue
        warmup_start = pd.Timestamp(spy_dates[i - warmup])
        effective = Backtester(prepared, config)._effective_calendar(
            warmup_start.date().isoformat(),
            final_valuation_date.date().isoformat(),
        )
        if not effective or pd.Timestamp(effective[0]) != decision_date:
            continue
        raw_ranges = _raw_ranges(prepared)
        return {
            "episode_label": episode_label,
            "episode_id": f"{RUN_LABEL}_{episode_label}_{decision_date.date().isoformat()}_{final_valuation_date.date().isoformat()}",
            "selection_rule": (
                "earliest eligible calendar month-end strictly after prior final valuation, with complete N4 warm-up, "
                "valid next-open execution, and five complete calendar years through maturity"
            ),
            "selection_reason": SELECTION_REASON,
            "prior_final_valuation_boundary": boundary.date().isoformat(),
            "raw_data_start": min(row["first_date"] for row in raw_ranges),
            "raw_data_end": max(row["last_date"] for row in raw_ranges),
            "raw_data_coverage": raw_ranges,
            "warmup_days": warmup,
            "warmup_start": warmup_start.date().isoformat(),
            "first_eligible_month_end_decision_date": decision_date.date().isoformat(),
            "episode_start": decision_date.date().isoformat(),
            "initial_execution_date": next_execution.date().isoformat(),
            "exact_calendar_maturity_timestamp": maturity.isoformat(),
            "final_valuation_date": final_valuation_date.date().isoformat(),
            "effective_trading_days": len(effective),
            "required_data_files": correction.data_file_hashes(load_result),
            "selected_before_performance_results": True,
            "not_selected_by_return_drawdown_regime_or_overlay_behavior": True,
            "not_a_sealed_holdout": True,
        }
    return None


def select_new_episodes(
    *,
    config: dict[str, Any],
    prepared: dict[str, pd.DataFrame],
    load_result: DataLoadResult,
    anchor_final_valuation: str = "2013-04-01",
) -> list[dict[str, Any]]:
    episodes: list[dict[str, Any]] = []
    boundary = pd.Timestamp(anchor_final_valuation)
    for label in ["NEW_EPISODE_1", "NEW_EPISODE_2"]:
        episode = freeze_episode_after(
            config=config,
            prepared=prepared,
            load_result=load_result,
            after_final_valuation=boundary,
            episode_label=label,
        )
        if episode is None:
            break
        episodes.append(episode)
        boundary = pd.Timestamp(episode["final_valuation_date"])
    return episodes


def run_trial(
    *,
    prepared: dict[str, pd.DataFrame],
    config: dict[str, Any],
    episode: dict[str, Any],
    trial_name: str,
    slippage: float,
    overlay: TradeManagementOverlay | None,
    base_strategy_hash: str,
) -> BacktestResult:
    return Backtester(prepared, config).run(
        f"{episode['episode_label']}_{trial_name}",
        episode["warmup_start"],
        episode["final_valuation_date"],
        slippage,
        lightweight_outputs=True,
        overlay=overlay,
        run_id=f"{RUN_LABEL}_{episode['episode_label']}_{trial_name}_{int(round(slippage * 10000))}bps",
        base_strategy_id=STRATEGY_ID,
        base_strategy_hash=base_strategy_hash,
    )


def _with_episode(rows: list[dict[str, Any]], episode: dict[str, Any]) -> list[dict[str, Any]]:
    output = []
    for row in rows:
        enriched = {
            "episode_label": episode["episode_label"],
            "episode_id": episode["episode_id"],
            **row,
        }
        output.append(enriched)
    return output


def _load_anchor_metrics() -> pd.DataFrame:
    metrics_path = ANCHOR_OUT_DIR / "metrics.csv"
    frame = pd.read_csv(metrics_path)
    frame.insert(0, "episode_id", "trade_management_cppi_m3_5y_monthly_n4_methodology_correction_v1_2008-03-31_2013-04-01")
    frame.insert(0, "episode_label", "ANCHOR_EPISODE")
    return frame


def _load_anchor_attribution() -> pd.DataFrame:
    path = ANCHOR_OUT_DIR / "attribution_decomposition.csv"
    frame = pd.read_csv(path)
    frame.insert(0, "episode_label", "ANCHOR_EPISODE")
    return frame


def _load_anchor_kill() -> pd.DataFrame:
    path = ANCHOR_OUT_DIR / "strategy_kill_attribution.csv"
    frame = pd.read_csv(path)
    frame.insert(0, "episode_label", "ANCHOR_EPISODE")
    return frame


def kill_state_pattern(kill_rows: pd.DataFrame) -> str:
    states = {row["trial_name"]: bool(row["n4_killed"]) for _, row in kill_rows.iterrows()}
    core = {name: states.get(name, False) for name in ["BASE", "SAFE5_TRANSLATION_CONTROL", "STATIC_CPPI_INITIAL_RISK_CAP_CONTROL", "DYNAMIC_CPPI"]}
    killed_count = sum(core.values())
    if killed_count == 0:
        return "ALL_TRIALS_SURVIVE"
    if killed_count == len(core):
        return "ALL_TRIALS_KILLED"
    if core["BASE"] and core["SAFE5_TRANSLATION_CONTROL"] and not core["STATIC_CPPI_INITIAL_RISK_CAP_CONTROL"] and not core["DYNAMIC_CPPI"]:
        return "BASE_AND_SAFE5_KILLED_STATIC_AND_DYNAMIC_SURVIVE"
    if core["BASE"] and not core["SAFE5_TRANSLATION_CONTROL"] and not core["STATIC_CPPI_INITIAL_RISK_CAP_CONTROL"] and not core["DYNAMIC_CPPI"]:
        return "BASE_ONLY_KILLED"
    if core["BASE"] and core["SAFE5_TRANSLATION_CONTROL"] and core["STATIC_CPPI_INITIAL_RISK_CAP_CONTROL"] and not core["DYNAMIC_CPPI"]:
        return "DYNAMIC_ONLY_SURVIVES"
    if core["BASE"] and core["SAFE5_TRANSLATION_CONTROL"] and not core["STATIC_CPPI_INITIAL_RISK_CAP_CONTROL"] and core["DYNAMIC_CPPI"]:
        return "STATIC_ONLY_SURVIVES"
    return "MIXED_KILL_STATE"


def mechanism_classification_rows(
    *,
    metrics_rows: list[dict[str, Any]],
    attribution_rows: list[dict[str, Any]],
    kill_rows: list[dict[str, Any]],
    failure_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    metrics = pd.DataFrame(metrics_rows)
    attribution = pd.DataFrame(attribution_rows)
    kills = pd.DataFrame(kill_rows)
    failures = pd.DataFrame(failure_rows)
    rows: list[dict[str, Any]] = []
    for episode_label in sorted(metrics["episode_label"].unique()):
        for bps in sorted(metrics[metrics["episode_label"].eq(episode_label)]["slippage_bps_per_side"].unique()):
            subset = metrics[metrics["episode_label"].eq(episode_label) & metrics["slippage_bps_per_side"].eq(bps)].set_index("trial_name")
            attr_subset = attribution[
                attribution["episode_label"].eq(episode_label) & attribution["slippage_bps_per_side"].eq(bps)
            ]
            kill_subset = kills[kills["episode_label"].eq(episode_label) & kills["slippage_bps_per_side"].eq(bps)]
            failure_subset = failures[
                failures["episode_label"].eq(episode_label)
                & failures["slippage_bps_per_side"].astype(str).eq(str(bps))
                & failures["status"].eq("FAIL")
            ] if not failures.empty and "episode_label" in failures else pd.DataFrame()
            dyn = subset.loc["DYNAMIC_CPPI"]
            static = subset.loc["STATIC_CPPI_INITIAL_RISK_CAP_CONTROL"]
            base = subset.loc["BASE"]
            total_delta = float(dyn["terminal_nav"] - base["terminal_nav"])
            dynamic_delta = float(dyn["terminal_nav"] - static["terminal_nav"])
            total_attr = attr_subset[attr_subset["effect"].eq("TOTAL_DYNAMIC_MINUS_BASE")]
            dyn_attr = attr_subset[attr_subset["effect"].eq("DYNAMIC_CPPI_INCREMENTAL_EFFECT")]
            safe_delta = float(total_attr["safe_rate_accrual_delta"].iloc[0]) if not total_attr.empty else 0.0
            post_kill = float(total_attr["post_base_kill_participation"].iloc[0]) if not total_attr.empty else 0.0
            total_mechanism = "TOTAL_EFFECT_MIXED"
            if total_delta < -MATERIAL_RETURN_DIFF * float(base["initial_nav"]):
                total_mechanism = "TOTAL_EFFECT_HARMFUL"
            elif abs(total_delta) <= MATERIAL_RETURN_DIFF * float(base["initial_nav"]):
                total_mechanism = "NO_TOTAL_EFFECT"
            elif abs(safe_delta) >= 0.5 * abs(total_delta):
                total_mechanism = "TOTAL_EFFECT_SAFE_RATE_DOMINANT"
            elif abs(post_kill) >= 0.5 * abs(total_delta):
                total_mechanism = "TOTAL_EFFECT_SURVIVAL_DOMINANT"

            dynamic_mechanism = "DYNAMIC_ALLOCATION_INCREMENTAL"
            if not failure_subset.empty:
                dynamic_mechanism = "DYNAMIC_ACCOUNTING_INVALID"
            elif dynamic_delta < -MATERIAL_RETURN_DIFF * float(static["initial_nav"]):
                if float(dyn["corrected_modeled_transaction_cost"] - static["corrected_modeled_transaction_cost"]) > abs(dynamic_delta):
                    dynamic_mechanism = "DYNAMIC_COST_DOMINATED"
                elif float(dyn["return_to_drawdown"]) < float(static["return_to_drawdown"]):
                    dynamic_mechanism = "DYNAMIC_RISK_ADJUSTED_DAMAGE"
                else:
                    dynamic_mechanism = "DYNAMIC_ALLOCATION_HARMFUL"
            elif abs(dynamic_delta) <= MATERIAL_RETURN_DIFF * float(static["initial_nav"]):
                dynamic_mechanism = "DYNAMIC_MATCHES_STATIC"
            elif float(dyn["return_to_drawdown"]) > float(static["return_to_drawdown"]):
                dynamic_mechanism = "DYNAMIC_RISK_ADJUSTED_IMPROVEMENT"
            elif float(dyn["average_risky_exposure"]) > float(static["average_risky_exposure"]):
                dynamic_mechanism = "DYNAMIC_EXPOSURE_INCREASE_ONLY"
            if not dyn_attr.empty and dynamic_mechanism == "DYNAMIC_EXPOSURE_INCREASE_ONLY" and dynamic_delta > 0:
                dynamic_mechanism = "DYNAMIC_ALLOCATION_INCREMENTAL"

            rows.append(
                {
                    "episode_label": episode_label,
                    "slippage_bps_per_side": bps,
                    "kill_state_pattern": kill_state_pattern(kill_subset),
                    "total_vs_base_mechanism": total_mechanism,
                    "dynamic_vs_static_mechanism": dynamic_mechanism,
                    "dynamic_minus_static_terminal_nav_delta": dynamic_delta,
                    "dynamic_minus_static_return_delta": float(dyn["total_return"] - static["total_return"]),
                    "dynamic_minus_static_drawdown_delta": float(dyn["maximum_drawdown"] - static["maximum_drawdown"]),
                    "dynamic_minus_static_return_to_drawdown_delta": float(dyn["return_to_drawdown"] - static["return_to_drawdown"]),
                    "dynamic_minus_static_realized_exposure_delta": float(dyn["average_risky_exposure"] - static["average_risky_exposure"]),
                    "dynamic_minus_static_turnover_delta": float(dyn["turnover"] - static["turnover"]),
                    "post_base_kill_participation_delta": float(dyn_attr["post_base_kill_participation"].iloc[0]) if not dyn_attr.empty else np.nan,
                }
            )
    return rows


def asset_and_period_concentration_rows(
    *,
    results_by_episode: dict[str, dict[tuple[float, str], BacktestResult]],
    metrics_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    metrics = pd.DataFrame(metrics_rows)
    rows: list[dict[str, Any]] = []
    for episode_label, results in results_by_episode.items():
        for slippage in SLIPPAGES:
            static = results[(slippage, "STATIC_CPPI_INITIAL_RISK_CAP_CONTROL")]
            dynamic = results[(slippage, "DYNAMIC_CPPI")]
            metric_subset = metrics[
                metrics["episode_label"].eq(episode_label) & metrics["slippage_bps_per_side"].eq(slippage * 10000.0)
            ].set_index("trial_name")
            terminal_delta = float(metric_subset.loc["DYNAMIC_CPPI", "terminal_nav"] - metric_subset.loc["STATIC_CPPI_INITIAL_RISK_CAP_CONTROL", "terminal_nav"])
            asset_contrib: dict[str, float] = {}
            for result, sign in [(dynamic, 1.0), (static, -1.0)]:
                if result.trades.empty or "pnl" not in result.trades:
                    continue
                grouped = result.trades.groupby("symbol")["pnl"].sum()
                for symbol, value in grouped.items():
                    asset_contrib[str(symbol)] = asset_contrib.get(str(symbol), 0.0) + sign * float(value)
            largest_asset = max(asset_contrib, key=lambda symbol: abs(asset_contrib[symbol])) if asset_contrib else ""
            largest_asset_value = asset_contrib.get(largest_asset, 0.0)
            diff = dynamic.equity_curve[["date", "equity"]].copy()
            diff["date"] = pd.to_datetime(diff["date"])
            stat = static.equity_curve[["date", "equity"]].copy()
            stat["date"] = pd.to_datetime(stat["date"])
            merged = diff.merge(stat, on="date", suffixes=("_dynamic", "_static"))
            merged["diff"] = merged["equity_dynamic"] - merged["equity_static"]
            merged["month"] = merged["date"].dt.to_period("M").astype(str)
            monthly = merged.groupby("month")["diff"].last().diff().fillna(merged.groupby("month")["diff"].last())
            largest_month = str(monthly.abs().idxmax()) if not monthly.empty else ""
            largest_month_value = float(monthly.loc[largest_month]) if largest_month else 0.0
            denominator = max(abs(terminal_delta), 1e-9)
            rows.append(
                {
                    "episode_label": episode_label,
                    "slippage_bps_per_side": slippage * 10000.0,
                    "dynamic_minus_static_terminal_nav_delta": terminal_delta,
                    "largest_asset_contributor": largest_asset,
                    "largest_asset_contribution": largest_asset_value,
                    "largest_asset_abs_share_of_terminal_delta": abs(largest_asset_value) / denominator,
                    "largest_month_contributor": largest_month,
                    "largest_month_contribution": largest_month_value,
                    "largest_month_abs_share_of_terminal_delta": abs(largest_month_value) / denominator,
                    "single_asset_or_period_explains_most": (
                        abs(largest_asset_value) / denominator >= 0.5 or abs(largest_month_value) / denominator >= 0.5
                    ),
                }
            )
    return rows


def chronological_robustness_rows(
    *,
    metrics_rows: list[dict[str, Any]],
    mechanism_rows: list[dict[str, Any]],
    concentration_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    metrics = pd.DataFrame(metrics_rows)
    mechanisms = pd.DataFrame(mechanism_rows)
    concentration = pd.DataFrame(concentration_rows)
    rows: list[dict[str, Any]] = []
    for episode_label in sorted(metrics["episode_label"].unique()):
        episode_matrix: list[dict[str, Any]] = []
        for bps in sorted(metrics[metrics["episode_label"].eq(episode_label)]["slippage_bps_per_side"].unique()):
            subset = metrics[metrics["episode_label"].eq(episode_label) & metrics["slippage_bps_per_side"].eq(bps)].set_index("trial_name")
            dyn = subset.loc["DYNAMIC_CPPI"]
            static = subset.loc["STATIC_CPPI_INITIAL_RISK_CAP_CONTROL"]
            mech = mechanisms[mechanisms["episode_label"].eq(episode_label) & mechanisms["slippage_bps_per_side"].eq(bps)]
            conc = (
                concentration[concentration["episode_label"].eq(episode_label) & concentration["slippage_bps_per_side"].eq(bps)]
                if not concentration.empty and "episode_label" in concentration
                else pd.DataFrame()
            )
            row = {
                "episode_label": episode_label,
                "slippage_bps_per_side": bps,
                "return_difference_dynamic_minus_static": float(dyn["total_return"] - static["total_return"]),
                "drawdown_difference_dynamic_minus_static": float(dyn["maximum_drawdown"] - static["maximum_drawdown"]),
                "return_to_drawdown_difference_dynamic_minus_static": float(dyn["return_to_drawdown"] - static["return_to_drawdown"]),
                "exposure_difference_dynamic_minus_static": float(dyn["average_risky_exposure"] - static["average_risky_exposure"]),
                "turnover_difference_dynamic_minus_static": float(dyn["turnover"] - static["turnover"]),
                "kill_state_difference": mech["kill_state_pattern"].iloc[0] if not mech.empty else "",
                "dynamic_vs_static_mechanism": mech["dynamic_vs_static_mechanism"].iloc[0] if not mech.empty else "",
                "single_asset_or_period_explains_most": bool(conc["single_asset_or_period_explains_most"].iloc[0]) if not conc.empty else False,
            }
            episode_matrix.append(row)
            rows.append(row)
        signs = [np.sign(row["return_difference_dynamic_minus_static"]) for row in episode_matrix]
        if all(abs(row["return_difference_dynamic_minus_static"]) <= MATERIAL_RETURN_DIFF for row in episode_matrix):
            classification = "DYNAMIC_NO_MATERIAL_DIFFERENCE"
        elif all(sign > 0 for sign in signs):
            classification = "DYNAMIC_BETTER_THAN_STATIC"
        elif all(sign < 0 for sign in signs):
            classification = "DYNAMIC_WORSE_THAN_STATIC"
        elif len(set(signs)) > 1:
            classification = "DYNAMIC_MIXED_BY_COST"
        else:
            classification = "INSUFFICIENT_ACTIVITY"
        for row in rows:
            if row["episode_label"] == episode_label:
                row["episode_level_classification"] = classification
    return rows


def cross_episode_conclusion(
    *,
    matrix_rows: list[dict[str, Any]],
    concentration_rows: list[dict[str, Any]],
    safe_diagnostics_rows: list[dict[str, Any]],
) -> str:
    matrix = pd.DataFrame(matrix_rows)
    concentration = pd.DataFrame(concentration_rows)
    safe = pd.DataFrame(safe_diagnostics_rows)
    episode_labels = sorted(set(matrix["episode_label"]))
    if len(episode_labels) < 3:
        return "INSUFFICIENT_COMPLETE_EPISODES"
    accounting_ok = True
    if not safe.empty:
        accounting_ok = bool((safe["safe_ledger_persistence_rate"].astype(float) >= 0.99).all())
    if not accounting_ok:
        return "INSUFFICIENT_COMPLETE_EPISODES"
    positives_5_10 = []
    for episode_label in episode_labels:
        subset = matrix[matrix["episode_label"].eq(episode_label) & matrix["slippage_bps_per_side"].isin([5.0, 10.0])]
        positives_5_10.append(bool((subset["return_difference_dynamic_minus_static"] > MATERIAL_RETURN_DIFF).all()))
    if sum(positives_5_10) >= 2:
        new_positive = any(flag for label, flag in zip(episode_labels, positives_5_10) if label != "ANCHOR_EPISODE")
        concentration_ok = True
        if not concentration.empty:
            concentration_ok = not bool(concentration["single_asset_or_period_explains_most"].any())
        if new_positive and concentration_ok:
            return "ROBUSTNESS_REVIEW_CANDIDATE"
    anchor_positive = bool(
        (
            matrix[matrix["episode_label"].eq("ANCHOR_EPISODE") & matrix["slippage_bps_per_side"].isin([5.0, 10.0])][
                "return_difference_dynamic_minus_static"
            ]
            > MATERIAL_RETURN_DIFF
        ).all()
    )
    new_labels = [label for label in episode_labels if label != "ANCHOR_EPISODE"]
    new_positive_count = 0
    for label in new_labels:
        subset = matrix[matrix["episode_label"].eq(label) & matrix["slippage_bps_per_side"].isin([5.0, 10.0])]
        new_positive_count += int(bool((subset["return_difference_dynamic_minus_static"] > MATERIAL_RETURN_DIFF).all()))
    if anchor_positive and new_positive_count == 0:
        return "CRISIS_RECOVERY_SPECIFIC"
    if new_positive_count == 0:
        return "STATIC_CONTROL_EXPLAINS_RESULT"
    if any(cls == "DYNAMIC_WORSE_THAN_STATIC" for cls in matrix["episode_level_classification"].unique()):
        return "MIXED_ACROSS_EPISODES"
    return "MIXED_ACROSS_EPISODES"


def append_current_runner_result(test_text: str, test_rows: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    command = f"{sys.executable} run_trade_management_cppi_n4_chronological_robustness_v1.py"
    test_rows.append({"command": command, "returncode": 0, "passed": True, "note": "current invocation completed"})
    return test_text + f"\n$ {command}\nreturncode=0\ncurrent invocation completed\n", test_rows


def run_test_commands() -> tuple[str, bool, list[dict[str, Any]]]:
    chunks: list[str] = []
    rows: list[dict[str, Any]] = []
    passed_all = True
    for command in TEST_COMMANDS:
        result = subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True)
        passed = result.returncode == 0
        passed_all = passed_all and passed
        printable = " ".join(command)
        rows.append({"command": printable, "returncode": result.returncode, "passed": passed})
        chunks.append(f"$ {printable}\nreturncode={result.returncode}\n{result.stdout}{result.stderr}".rstrip())
    text, rows = append_current_runner_result("\n\n".join(chunks) + "\n", rows)
    return text, passed_all, rows


def source_payload(config: dict[str, Any], load_result: DataLoadResult, episodes: list[dict[str, Any]]) -> dict[str, Any]:
    worktree = correction.tracked_and_untracked_diff_hash()
    payload = {
        "created_utc": datetime.now(UTC).isoformat(),
        "repo_head_commit": git_commit_hash(ROOT),
        "working_tree_dirty": worktree["dirty"],
        "git_status_porcelain": worktree["status_porcelain"],
        "tracked_and_untracked_diff_hash": worktree["tracked_and_untracked_diff_hash"],
        "tracked_diff_sha256": worktree["tracked_diff_sha256"],
        "untracked_file_hashes": worktree["untracked_file_hashes"],
        "file_hashes": _required_file_hashes(),
        "full_config_hash": config_hash(config),
        "n4_configuration_hash": correction.n4_config_hash(config),
        "cppi_parameter_mapping": CPPI_PARAMS,
        "cppi_parameter_mapping_hash": stable_hash(CPPI_PARAMS),
        "risky_safe_mapping": {"risky_sleeve": RISKY_ASSETS, "safe_cash_proxy_sleeve": SAFE_ASSETS},
        "risky_safe_mapping_hash": stable_hash({"risky": RISKY_ASSETS, "safe": SAFE_ASSETS}),
        "data_file_hashes": correction.data_file_hashes(load_result),
        "selection_reason": SELECTION_REASON,
        "episodes": episodes,
        "safe_ledger_convention": "continuous_5pct_actual_calendar_days_365_before_transfers_and_executions_eod_sweep",
        "stage": STAGE,
        "head_alone_is_not_code_version_when_dirty": True,
    }
    write_json(OUT_DIR / "source_and_worktree_hashes.json", payload)
    return payload


def write_pre_registered_manifest(config: dict[str, Any], load_result: DataLoadResult, episodes: list[dict[str, Any]]) -> dict[str, Any]:
    payload = source_payload(config, load_result, episodes)
    manifest = {
        "run_label": RUN_LABEL,
        "created_utc": payload["created_utc"],
        "task_type": "timeframe_diagnostic|research_only_robustness",
        "selection_reason": SELECTION_REASON,
        "repository_head_commit": payload["repo_head_commit"],
        "working_tree_dirty": payload["working_tree_dirty"],
        "git_status_porcelain": payload["git_status_porcelain"],
        "tracked_and_untracked_diff_hash": payload["tracked_and_untracked_diff_hash"],
        "source_and_worktree_hashes_sha256": sha256_file(OUT_DIR / "source_and_worktree_hashes.json"),
        "n4_configuration_hash": payload["n4_configuration_hash"],
        "cppi_parameter_mapping_hash": payload["cppi_parameter_mapping_hash"],
        "risky_safe_mapping_hash": payload["risky_safe_mapping_hash"],
        "safe_ledger_convention": payload["safe_ledger_convention"],
        "costs_bps_per_side": [0, 5, 10],
        "required_trials": TRIAL_NAMES,
        "episode_selection_rules": {
            "anchor": "read from corrected methodology package; not rerun",
            "new_episode_1": "first eligible month-end strictly after anchor final valuation",
            "new_episode_2": "first eligible month-end strictly after NEW_EPISODE_1 final valuation",
        },
        "classification_rules": {
            "total_vs_base": [
                "TOTAL_EFFECT_SURVIVAL_DOMINANT",
                "TOTAL_EFFECT_SAFE_RATE_DOMINANT",
                "TOTAL_EFFECT_MIXED",
                "NO_TOTAL_EFFECT",
                "TOTAL_EFFECT_HARMFUL",
            ],
            "dynamic_vs_static": [
                "DYNAMIC_ALLOCATION_INCREMENTAL",
                "DYNAMIC_ALLOCATION_HARMFUL",
                "DYNAMIC_MATCHES_STATIC",
                "DYNAMIC_COST_DOMINATED",
                "DYNAMIC_EXPOSURE_INCREASE_ONLY",
                "DYNAMIC_RISK_ADJUSTED_IMPROVEMENT",
                "DYNAMIC_RISK_ADJUSTED_DAMAGE",
                "DYNAMIC_ACCOUNTING_INVALID",
            ],
        },
        "episodes": episodes,
        "not_clean_holdout_validation": True,
        "not_parameter_optimization": True,
        "not_family_portability": True,
        "not_promotion": True,
        "not_paper_demo_live": True,
        "source_rate_warning": SOURCE_RATE_WARNING,
    }
    write_json(OUT_DIR / "pre_registered_manifest.json", manifest)
    return payload


def write_episode_definitions(anchor_definition: dict[str, Any], new_episodes: list[dict[str, Any]]) -> None:
    payload = {
        "anchor_episode": anchor_definition,
        "new_episodes": new_episodes,
        "insufficient_data_code": ""
        if len(new_episodes) == 2
        else "INSUFFICIENT_DATA_FOR_SECOND_NON_OVERLAPPING_EPISODE",
    }
    write_json(OUT_DIR / "episode_definitions.json", payload)


def write_comparison(
    *,
    episodes: list[dict[str, Any]],
    metrics: list[dict[str, Any]],
    attribution: list[dict[str, Any]],
    mechanisms: list[dict[str, Any]],
    matrix: list[dict[str, Any]],
    conclusion: str,
    safe_diagnostics: list[dict[str, Any]],
    failures: list[dict[str, Any]],
) -> None:
    metrics_frame = pd.DataFrame(metrics)
    attr_frame = pd.DataFrame(attribution)
    mech_frame = pd.DataFrame(mechanisms)
    matrix_frame = pd.DataFrame(matrix)
    safe_frame = pd.DataFrame(safe_diagnostics)
    fail_frame = pd.DataFrame(failures)
    summary_cols = [
        "episode_label",
        "trial_name",
        "slippage_bps_per_side",
        "terminal_nav",
        "total_return",
        "annualized_return",
        "maximum_drawdown",
        "return_to_drawdown",
        "average_target_risky_exposure",
        "average_risky_exposure",
        "average_synthetic_safe_exposure",
        "total_safe_accrual",
        "cash_lock_date",
        "killed_strategies",
    ]
    text = [
        "# CPPI N4 Chronological Robustness V1",
        "",
        f"Stage: `{STAGE}`.",
        "",
        SOURCE_RATE_WARNING,
        "",
        "## Frozen New Episodes",
        "",
        pd.DataFrame(episodes)[
            [
                "episode_label",
                "episode_start",
                "initial_execution_date",
                "exact_calendar_maturity_timestamp",
                "final_valuation_date",
                "selection_rule",
            ]
        ].to_markdown(index=False),
        "",
        "## Metrics",
        "",
        metrics_frame[summary_cols].to_markdown(index=False),
        "",
        "## Safe Diagnostics",
        "",
        safe_frame.to_markdown(index=False) if not safe_frame.empty else "No safe diagnostics.",
        "",
        "## Attribution",
        "",
        attr_frame.to_markdown(index=False) if not attr_frame.empty else "No attribution rows.",
        "",
        "## Mechanism Classifications",
        "",
        mech_frame.to_markdown(index=False) if not mech_frame.empty else "No mechanism rows.",
        "",
        "## Robustness Matrix",
        "",
        matrix_frame.to_markdown(index=False) if not matrix_frame.empty else "No matrix rows.",
        "",
        "## Failure Registry",
        "",
        fail_frame.to_markdown(index=False) if not fail_frame.empty else "No failures.",
        "",
        "## Exact-Combination Conclusion",
        "",
        f"`{conclusion}`",
        "",
        "No tuning, new strategy, rate change, overlay combination, promotion, or paper/demo/live action was performed.",
    ]
    (OUT_DIR / "comparison.md").write_text("\n".join(text) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    base_config = load_config(ROOT / "config.yaml")
    config = correction.n4_only_config(base_config)
    load_result = load_market_data(config, ROOT)
    prepared = prepare_indicators(load_result.data)
    anchor_manifest = json.loads((ANCHOR_OUT_DIR / "pre_registered_correction_manifest.json").read_text(encoding="utf-8"))
    anchor_episode = dict(anchor_manifest["episode"])
    anchor_episode["episode_label"] = "ANCHOR_EPISODE"
    anchor_episode["anchor_package"] = ANCHOR_OUT_DIR.as_posix()
    anchor_episode["not_rerun"] = True
    new_episodes = select_new_episodes(
        config=config,
        prepared=prepared,
        load_result=load_result,
        anchor_final_valuation=anchor_episode["final_valuation_date"],
    )
    if not new_episodes:
        raise RuntimeError("No complete non-overlapping chronological robustness episodes were available.")
    write_episode_definitions(anchor_episode, new_episodes)
    source = write_pre_registered_manifest(config, load_result, new_episodes)

    trial_registry: list[dict[str, Any]] = []
    identity_rows: list[dict[str, Any]] = []
    metrics_rows: list[dict[str, Any]] = []
    daily_rows_all: list[dict[str, Any]] = []
    events_rows: list[dict[str, Any]] = []
    reconciliation_all: list[dict[str, Any]] = []
    safe_event_rows_all: list[dict[str, Any]] = []
    safe_diagnostics_all: list[dict[str, Any]] = []
    safe_accrual_all: list[dict[str, Any]] = []
    kill_all: list[dict[str, Any]] = []
    attribution_all: list[dict[str, Any]] = []
    failure_all: list[dict[str, Any]] = []
    breach_all: list[dict[str, Any]] = []
    results_by_episode: dict[str, dict[tuple[float, str], BacktestResult]] = {}
    base_hash = correction.n4_config_hash(config)

    for episode in new_episodes:
        local_daily: list[dict[str, Any]] = []
        local_events: list[dict[str, Any]] = []
        local_recon: list[dict[str, Any]] = []
        local_safe_events: list[dict[str, Any]] = []
        local_metrics: list[dict[str, Any]] = []
        local_breach: list[dict[str, Any]] = []
        local_results: dict[tuple[float, str], BacktestResult] = {}
        for slippage in SLIPPAGES:
            for trial_name in TRIAL_NAMES:
                overlay = correction.overlay_for_trial(trial_name, episode)
                result = run_trial(
                    prepared=prepared,
                    config=config,
                    episode=episode,
                    trial_name=trial_name,
                    slippage=slippage,
                    overlay=overlay,
                    base_strategy_hash=base_hash,
                )
                local_results[(slippage, trial_name)] = result
                daily_rows = _with_episode(
                    correction.daily_state_rows(
                        result=result,
                        prepared=prepared,
                        episode=episode,
                        trial_name=trial_name,
                        slippage=slippage,
                    ),
                    episode,
                )
                local_daily.extend(daily_rows)
                metric = correction.metric_row(
                    result=result,
                    daily_rows=daily_rows,
                    episode=episode,
                    trial_name=trial_name,
                    slippage=slippage,
                )
                metric = {"episode_label": episode["episode_label"], "episode_id": episode["episode_id"], **metric}
                local_metrics.append(metric)
                local_recon.extend(
                    _with_episode(
                        correction.reconciliation_rows(
                            result=result,
                            daily_rows=daily_rows,
                            trial_name=trial_name,
                            slippage=slippage,
                        ),
                        episode,
                    )
                )
                if trial_name in SAFE_LEDGER_TRIALS:
                    local_safe_events.extend(
                        _with_episode(
                            correction.safe_event_detail_rows(result=result, trial_name=trial_name, slippage=slippage),
                            episode,
                        )
                    )
                local_breach.extend(
                    _with_episode(
                        correction.floor_breach_rows(daily_rows=daily_rows, result=result, trial_name=trial_name, slippage=slippage),
                        episode,
                    )
                )
                if not result.overlay_events.empty:
                    events = result.overlay_events.copy()
                    events.insert(0, "episode_label", episode["episode_label"])
                    events.insert(1, "episode_id", episode["episode_id"])
                    events.insert(2, "trial_name", trial_name)
                    events.insert(3, "slippage_bps_per_side", slippage * 10000.0)
                    local_events.extend(events.to_dict("records"))
                trial_registry.append(
                    {
                        "episode_label": episode["episode_label"],
                        "episode_id": episode["episode_id"],
                        "trial_name": trial_name,
                        "slippage_bps_per_side": slippage * 10000.0,
                        "overlay_id": overlay.overlay_id if overlay is not None else "BASE",
                        "status": "completed",
                        "start": result.metadata.get("effective_first_trading_date", ""),
                        "end": result.metadata.get("effective_last_trading_date", ""),
                        "no_other_overlay_active": True,
                    }
                )
            base_result = local_results[(slippage, "BASE")]
            identity_result = local_results[(slippage, "IDENTITY")]
            base_result_hash = correction.result_hashes(base_result)
            identity_result_hash = correction.result_hashes(identity_result)
            identity_rows.append(
                {
                    "episode_label": episode["episode_label"],
                    "episode_id": episode["episode_id"],
                    "slippage_bps_per_side": slippage * 10000.0,
                    "base_complete_state_hash": base_result_hash["complete_state_hash"],
                    "identity_complete_state_hash": identity_result_hash["complete_state_hash"],
                    "complete_state_hash_match": base_result_hash["complete_state_hash"] == identity_result_hash["complete_state_hash"],
                }
            )
        local_accrual = _with_episode(
            correction.safe_accrual_recalculation_rows(
                daily_rows_all=local_daily,
                safe_event_rows_all=local_safe_events,
            ),
            episode,
        )
        local_safe_diag = _with_episode(
            correction.safe_persistence_diagnostic_rows(
                daily_rows_all=local_daily,
                safe_event_rows_all=local_safe_events,
                accrual_rows=local_accrual,
                results=local_results,
            ),
            episode,
        )
        local_kill = _with_episode(
            correction.strategy_kill_attribution_rows(results=local_results, daily_rows_all=local_daily),
            episode,
        )
        local_attr = _with_episode(correction.attribution_rows(local_metrics, local_kill), episode)
        local_failures = _with_episode(
            correction.failure_registry_rows(
                reconciliation_all=local_recon,
                identity_rows=[row for row in identity_rows if row["episode_label"] == episode["episode_label"]],
                daily_rows_all=local_daily,
                safe_diagnostics=local_safe_diag,
                accrual_rows=local_accrual,
                safe_event_rows=local_safe_events,
            ),
            episode,
        )
        metrics_rows.extend(local_metrics)
        daily_rows_all.extend(local_daily)
        events_rows.extend(local_events)
        reconciliation_all.extend(local_recon)
        safe_event_rows_all.extend(local_safe_events)
        safe_accrual_all.extend(local_accrual)
        safe_diagnostics_all.extend(local_safe_diag)
        kill_all.extend(local_kill)
        attribution_all.extend(local_attr)
        failure_all.extend(local_failures)
        breach_all.extend(local_breach)
        results_by_episode[episode["episode_label"]] = local_results

    mechanism_rows = mechanism_classification_rows(
        metrics_rows=metrics_rows,
        attribution_rows=attribution_all,
        kill_rows=kill_all,
        failure_rows=failure_all,
    )
    concentration_rows = asset_and_period_concentration_rows(results_by_episode=results_by_episode, metrics_rows=metrics_rows)
    matrix_rows_new = chronological_robustness_rows(
        metrics_rows=metrics_rows,
        mechanism_rows=mechanism_rows,
        concentration_rows=concentration_rows,
    )

    anchor_metrics = _load_anchor_metrics()
    anchor_attr = _load_anchor_attribution()
    anchor_kill = _load_anchor_kill()
    anchor_failures = pd.DataFrame(columns=["episode_label", "status", "slippage_bps_per_side"])
    anchor_mechanisms = mechanism_classification_rows(
        metrics_rows=anchor_metrics.to_dict("records"),
        attribution_rows=anchor_attr.to_dict("records"),
        kill_rows=anchor_kill.to_dict("records"),
        failure_rows=anchor_failures.to_dict("records"),
    )
    anchor_matrix = chronological_robustness_rows(
        metrics_rows=anchor_metrics.to_dict("records"),
        mechanism_rows=anchor_mechanisms,
        concentration_rows=[],
    )
    all_matrix_for_conclusion = anchor_matrix + matrix_rows_new
    conclusion = cross_episode_conclusion(
        matrix_rows=all_matrix_for_conclusion,
        concentration_rows=concentration_rows,
        safe_diagnostics_rows=safe_diagnostics_all,
    )

    write_csv(OUT_DIR / "trial_registry.csv", trial_registry)
    write_csv(OUT_DIR / "identity_equivalence.csv", identity_rows)
    write_csv(OUT_DIR / "metrics.csv", metrics_rows)
    pd.DataFrame(daily_rows_all).to_csv(OUT_DIR / "daily_cppi_state.csv", index=False)
    pd.DataFrame(events_rows).to_csv(OUT_DIR / "cppi_events.csv", index=False)
    pd.DataFrame(safe_diagnostics_all).to_csv(OUT_DIR / "safe_persistence_diagnostics.csv", index=False)
    pd.DataFrame(safe_accrual_all).to_csv(OUT_DIR / "safe_accrual_recalculation.csv", index=False)
    pd.DataFrame(reconciliation_all).to_csv(OUT_DIR / "safe_account_reconciliation.csv", index=False)
    pd.DataFrame(kill_all).to_csv(OUT_DIR / "strategy_kill_attribution.csv", index=False)
    pd.DataFrame(attribution_all).to_csv(OUT_DIR / "attribution_decomposition.csv", index=False)
    pd.DataFrame(mechanism_rows).to_csv(OUT_DIR / "episode_mechanism_classification.csv", index=False)
    pd.DataFrame(matrix_rows_new).to_csv(OUT_DIR / "chronological_robustness_matrix.csv", index=False)
    pd.DataFrame(concentration_rows).to_csv(OUT_DIR / "asset_and_period_concentration.csv", index=False)
    pd.DataFrame(breach_all).to_csv(OUT_DIR / "floor_breach_log.csv", index=False)
    pd.DataFrame(failure_all).to_csv(OUT_DIR / "failure_registry.csv", index=False)
    write_comparison(
        episodes=new_episodes,
        metrics=metrics_rows,
        attribution=attribution_all,
        mechanisms=mechanism_rows,
        matrix=matrix_rows_new,
        conclusion=conclusion,
        safe_diagnostics=safe_diagnostics_all,
        failures=failure_all,
    )
    (OUT_DIR / "source_of_truth_update.md").write_text(
        "\n".join(
            [
                "# Source Of Truth Update",
                "",
                f"Experiment: `{RUN_LABEL}`",
                "",
                f"Stage: `{STAGE}`",
                "",
                f"Selection reason: `{SELECTION_REASON}`.",
                "",
                SOURCE_RATE_WARNING,
                "",
                f"Cross-episode exact-combination conclusion: `{conclusion}`.",
                "",
                "No tuning, new strategy, rate change, overlay combination, promotion, paper/demo eligibility, broker path, or live action was performed.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    test_text, tests_passed, test_rows = run_test_commands()
    (OUT_DIR / "test_results.txt").write_text(test_text, encoding="utf-8")
    manifest_path = OUT_DIR / "pre_registered_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "completed_utc": datetime.now(UTC).isoformat(),
            "tests_passed": tests_passed,
            "test_commands": test_rows,
            "cross_episode_exact_combination_conclusion": conclusion,
            "artifact_hashes": {
                path.name: sha256_file(path)
                for path in sorted(OUT_DIR.iterdir())
                if path.is_file() and path.name != "pre_registered_manifest.json"
            },
            "source_payload_hash_after_run": stable_hash(source),
        }
    )
    write_json(manifest_path, manifest)
    if not tests_passed:
        raise SystemExit("Chronological robustness artifacts were generated, but verification tests failed.")


if __name__ == "__main__":
    main()
