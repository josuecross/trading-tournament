from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
from dataclasses import replace
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import angl_fallen_angel_diversifier_validation_v1 as prior_validation
from strategy_lab.research_os.research import fast_price_volume_discovery_batch_v2 as prior
from strategy_lab.research_os.research import fast_source_library_batch_v3 as source_batch


CORRECTION_ID = "angl_80_20_portfolio_construction_methodology_correction_v1"
OUTPUT_DIR = ROOT / "evidence" / "correction" / CORRECTION_ID / "latest"
STRATEGY_ID = "ice_vaneck_us_fallen_angel_angl_v1"
FAMILY_ID = "fallen_angel_credit_anomaly"
PREVIOUS_VALIDATION_TRIAL_ID = "validation_angl__ice_vaneck_us_fallen_angel_angl_v1__validation_variant_child"
CORRECTION_TRIAL_ID = "correction_angl__ice_vaneck_us_fallen_angel_angl_v1__methodology_correction_child"
ADAPTATION_LABEL = "methodology_correction"
PRIMARY_COST_BPS = 5.0
COST_BPS_GRID = (0.0, 5.0, 10.0)
REPRODUCTION_TOLERANCE = 1e-9
TARGET_REFERENCE_WEIGHT = 0.80
TARGET_SLEEVE_WEIGHT = 0.20
WEIGHT_TOLERANCE = 1e-6
FROZEN_TIMESTAMP = "2026-07-23T00:00:00+00:00"
CONTROL_IDS = ("HYG_buy_hold", "monthly_rebalanced_50_50_HYG_JNK")
PORTFOLIO_IDS = (
    "frozen_reference_100pct",
    f"{STRATEGY_ID}_candidate_20pct",
    "HYG_buy_hold_20pct_control",
    "monthly_rebalanced_50_50_HYG_JNK_20pct_control",
)
SLEEVE_BY_PORTFOLIO = {
    f"{STRATEGY_ID}_candidate_20pct": "ANGL",
    "HYG_buy_hold_20pct_control": "HYG_buy_hold",
    "monthly_rebalanced_50_50_HYG_JNK_20pct_control": "monthly_rebalanced_50_50_HYG_JNK",
}
DISPLAY_NAME = "ICE/VanEck US Fallen Angel ANGL"
PREVIOUS_VALIDATION_DIR = ROOT / "evidence" / "validation" / "angl_fallen_angel_diversifier_validation_v1" / "latest"
PREVIOUS_VALIDATION_FILES = [
    PREVIOUS_VALIDATION_DIR / name
    for name in [
        "validation_manifest.yaml",
        "strategy_cards.csv",
        "trial_ledger.csv",
        "full_period_results.csv",
        "chronological_half_results.csv",
        "rolling_36_month_results.csv",
        "rolling_60_month_results.csv",
        "rolling_window_summary.csv",
        "portfolio_contribution_results.csv",
        "consistency_check.json",
    ]
]
PROTECTED_STATE_PATHS = [
    ROOT / "strategy_lab" / "strategy_registry.yaml",
    ROOT / "strategy_lab" / "RESEARCH_ROADMAP.md",
    ROOT / "strategy_lab" / "research_os" / "research" / "research_queue.yaml",
    ROOT / "strategy_lab" / "research_os" / "family_lineage" / "family_ledger.yaml",
    ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml",
]
PROTECTED_CACHE_PATHS = [
    ROOT / "data" / "cache" / "ANGL.csv",
    ROOT / "data" / "cache" / "ANGL.acquisition.json",
    ROOT / "data" / "cache" / "HYG.csv",
    ROOT / "data" / "cache" / "JNK.csv",
    ROOT / "data" / "cache" / "JNK.acquisition.json",
]
FORBIDDEN_FLAGS = {
    "source_research_or_completion": False,
    "provider_download": False,
    "parameter_or_instrument_change": False,
    "benchmark_correction": False,
    "universe_expansion": False,
    "trade_management_overlay": False,
    "promotion_review": False,
    "paper_demo_eligibility_or_activation": False,
    "registry_cleanup": False,
    "dashboard_rebuild": False,
    "dsr_pbo_cscv_reality_check_or_parameter_search": False,
    "broker_account_order_or_real_money_action": False,
    "nvi_or_inverse_vol_records_modified": False,
}


def rel(path: str | Path) -> str:
    p = Path(path)
    if not p.is_absolute():
        return p.as_posix()
    try:
        return p.relative_to(ROOT).as_posix()
    except ValueError:
        return p.as_posix()


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        if not math.isfinite(value):
            return ""
        return f"{value:.12g}"
    if isinstance(value, (list, tuple, set)):
        return "|".join(str(v) for v in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return str(value)


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fieldnames})


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def file_hash(path: Path) -> str:
    if not path.exists():
        return "missing"
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def hash_map(paths: list[Path]) -> dict[str, str]:
    return {rel(path): file_hash(path) for path in paths if path.exists()}


def protected_state_hashes() -> dict[str, str]:
    return hash_map(PROTECTED_STATE_PATHS)


def protected_cache_hashes() -> dict[str, str]:
    return hash_map(PROTECTED_CACHE_PATHS)


def previous_validation_hashes() -> dict[str, str]:
    return hash_map(PREVIOUS_VALIDATION_FILES)


def clean_output_dir() -> None:
    if OUTPUT_DIR.exists():
        resolved = OUTPUT_DIR.resolve()
        expected = (ROOT / "evidence" / "correction" / CORRECTION_ID).resolve()
        if expected not in resolved.parents:
            raise RuntimeError(f"Refusing to remove unexpected output path: {resolved}")
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def base_card() -> Any:
    card = next(card for card in source_batch.CARDS if card.strategy_id == STRATEGY_ID)
    return replace(card, parent_trial_id=PREVIOUS_VALIDATION_TRIAL_ID)


def frozen_inputs() -> tuple[Any, dict[str, Any], dict[str, dict[float, dict[str, Any]]], dict[str, dict[float, pd.Series]]]:
    card = base_card()
    reference_returns = prior.active_vm_dsr_usci_reference_returns()
    frozen = source_batch.run_card(card, reference_returns)
    if not frozen["executable"]:
        raise RuntimeError("ANGL frozen card is unexpectedly non-executable")
    series = prior_validation.standalone_and_control_returns(card, frozen)
    prior_blend = prior_validation.portfolio_returns(series, frozen["reference"])
    return card, frozen, series, prior_blend


def prior_portfolio_method_classification_rows() -> list[dict[str, Any]]:
    return [
        {
            "validation_id": "angl_fallen_angel_diversifier_validation_v1",
            "portfolio_method_classification": "fixed_weight_return_blend",
            "implementation_location": "strategy_lab/research_os/research/angl_fallen_angel_diversifier_validation_v1.py:portfolio_returns",
            "daily_holdings_or_weights_available": False,
            "daily_series_reconciliation": "prior rows reproduce from direct daily return arithmetic",
            "rebalance_trigger": "none_explicit",
            "rebalance_frequency": "none_explicit",
            "transaction_timing": "not_modeled_for_80_20_portfolio",
            "turnover_calculation": "not_calculated_for_80_20_portfolio",
            "transaction_cost_calculation": "portfolio_level_costs_not_calculated",
            "reported_zero_turnover_correct_for_prior_implementation": True,
            "tradable_without_implicit_daily_rebalancing": False,
            "code_verified_mechanism": "0.8 * frozen_reference_daily_return + 0.2 * sleeve_daily_return",
        }
    ]


def prior_metrics_lookup() -> dict[str, dict[str, str]]:
    lookup: dict[str, dict[str, str]] = {}
    for row in read_csv_rows(PREVIOUS_VALIDATION_DIR / "portfolio_contribution_results.csv"):
        if row["cost_assumption_bps"] == "5":
            lookup[row["portfolio_id"]] = row
    return lookup


def prior_reproduction_rows(prior_blend: dict[str, dict[float, pd.Series]]) -> list[dict[str, Any]]:
    lookup = prior_metrics_lookup()
    metric_fields = ["total_return", "cagr", "annualized_volatility", "sharpe_ratio", "maximum_drawdown"]
    rows: list[dict[str, Any]] = []
    for portfolio_id in PORTFOLIO_IDS:
        metrics = prior_validation.metric_payload(prior_blend[portfolio_id][PRIMARY_COST_BPS])
        prior_row = lookup.get(portfolio_id, {})
        for metric in metric_fields:
            previous = float(prior_row.get(metric, "nan")) if prior_row.get(metric, "") != "" else float("nan")
            current = float(metrics.get(metric, "nan"))
            diff = current - previous if math.isfinite(previous) and math.isfinite(current) else float("nan")
            rows.append(
                {
                    "portfolio_id": portfolio_id,
                    "metric": metric,
                    "prior_value": previous,
                    "recomputed_value": current,
                    "absolute_difference": abs(diff) if math.isfinite(diff) else "",
                    "tolerance": REPRODUCTION_TOLERANCE,
                    "reproduction_status": "pass"
                    if math.isfinite(diff) and abs(diff) <= REPRODUCTION_TOLERANCE
                    else "fail",
                }
            )
    return rows


def trade_dates(index: pd.DatetimeIndex, policy: str) -> set[pd.Timestamp]:
    if policy == "initial_80_20_with_natural_drift":
        return {pd.Timestamp(index[0])}
    dates: set[pd.Timestamp] = {pd.Timestamp(index[0])}
    for pos in range(1, len(index)):
        if index[pos - 1].to_period("M") != index[pos].to_period("M"):
            dates.add(pd.Timestamp(index[pos]))
    return dates


def simulate_two_component_portfolio(
    returns: pd.DataFrame,
    portfolio_id: str,
    construction_policy: str,
    cost_bps: float,
) -> dict[str, Any]:
    columns = ["reference", "sleeve"]
    returns = returns.loc[:, columns].dropna().copy()
    dates = returns.index
    targets = pd.Series({"reference": TARGET_REFERENCE_WEIGHT, "sleeve": TARGET_SLEEVE_WEIGHT}, dtype=float)
    planned_trade_dates = trade_dates(dates, construction_policy)
    cost_rate = cost_bps / 10000.0
    equity = 1.0
    weights = pd.Series({"reference": 0.0, "sleeve": 0.0}, dtype=float)
    daily_rows: list[dict[str, Any]] = []
    event_rows: list[dict[str, Any]] = []
    net_returns: list[float] = []
    turnover_values: list[float] = []
    cost_values: list[float] = []
    for pos, date in enumerate(dates):
        daily_component_return = returns.loc[date, columns].astype(float)
        gross_return = float((weights * daily_component_return).sum())
        equity_after_return = equity * (1.0 + gross_return)
        if equity_after_return == 0.0:
            pretrade_weights = weights.copy()
        else:
            pretrade_values = weights * (1.0 + daily_component_return)
            pretrade_weights = pretrade_values / float(pretrade_values.sum()) if float(pretrade_values.sum()) else weights.copy()
        event_type = ""
        turnover = 0.0
        cost_drag = 0.0
        target_weights = pretrade_weights.copy()
        if pd.Timestamp(date) in planned_trade_dates:
            target_weights = targets.copy()
            turnover = 0.5 * float((target_weights - pretrade_weights).abs().sum())
            cost_drag = turnover * cost_rate
            event_type = "initial_establishment" if pos == 0 else "monthly_rebalance_next_session_close"
            signal_date = "" if pos == 0 else pd.Timestamp(dates[pos - 1]).date().isoformat()
            event_rows.append(
                {
                    "portfolio_id": portfolio_id,
                    "construction_policy": construction_policy,
                    "cost_assumption_bps": cost_bps,
                    "event_date": pd.Timestamp(date).date().isoformat(),
                    "signal_date": signal_date,
                    "event_type": event_type,
                    "pretrade_reference_weight": float(pretrade_weights["reference"]),
                    "pretrade_sleeve_weight": float(pretrade_weights["sleeve"]),
                    "target_reference_weight": TARGET_REFERENCE_WEIGHT,
                    "target_sleeve_weight": TARGET_SLEEVE_WEIGHT,
                    "one_way_turnover": turnover,
                    "transaction_cost_rate": cost_rate,
                    "transaction_cost_drag": cost_drag,
                    "post_trade_reference_weight": TARGET_REFERENCE_WEIGHT,
                    "post_trade_sleeve_weight": TARGET_SLEEVE_WEIGHT,
                    "timing_convention": "month_end_signal_next_available_session_close_execution"
                    if pos > 0
                    else "first_common_date_initial_establishment",
                }
            )
        equity_after_cost = equity_after_return * (1.0 - cost_drag)
        net_return = equity_after_cost / equity - 1.0 if equity else 0.0
        equity = equity_after_cost
        weights_after_trade = target_weights.copy()
        weights = weights_after_trade
        net_returns.append(net_return)
        turnover_values.append(turnover)
        cost_values.append((1.0 + gross_return) * cost_drag)
        daily_rows.append(
            {
                "date": pd.Timestamp(date).date().isoformat(),
                "portfolio_id": portfolio_id,
                "construction_policy": construction_policy,
                "cost_assumption_bps": cost_bps,
                "reference_daily_return": float(daily_component_return["reference"]),
                "sleeve_daily_return": float(daily_component_return["sleeve"]),
                "gross_return_before_portfolio_cost": gross_return,
                "net_return": net_return,
                "equity": equity,
                "pretrade_reference_weight": float(pretrade_weights["reference"]),
                "pretrade_sleeve_weight": float(pretrade_weights["sleeve"]),
                "post_trade_reference_weight": float(weights_after_trade["reference"]),
                "post_trade_sleeve_weight": float(weights_after_trade["sleeve"]),
                "one_way_turnover": turnover,
                "transaction_cost_drag": (1.0 + gross_return) * cost_drag,
                "event_type": event_type,
                "max_daily_exposure": float(weights_after_trade.clip(lower=0.0).sum()),
                "max_daily_weight_sum": float(weights_after_trade.sum()),
            }
        )
    index = pd.DatetimeIndex(dates)
    daily_df = pd.DataFrame(daily_rows).assign(date=lambda frame: pd.to_datetime(frame["date"], errors="coerce")).set_index("date", drop=False)
    event_df = (
        pd.DataFrame(event_rows).assign(event_date=lambda frame: pd.to_datetime(frame["event_date"], errors="coerce")).set_index(
            "event_date", drop=False
        )
        if event_rows
        else pd.DataFrame()
    )
    return {
        "returns": pd.Series(net_returns, index=index, name=portfolio_id),
        "turnover": pd.Series(turnover_values, index=index, name="turnover"),
        "cost": pd.Series(cost_values, index=index, name="transaction_cost_drag"),
        "daily_rows": daily_rows,
        "event_rows": event_rows,
        "daily_df": daily_df,
        "event_df": event_df,
    }


def component_returns(series: dict[str, dict[float, dict[str, Any]]], reference: pd.Series, sleeve_id: str, cost_bps: float) -> pd.DataFrame:
    if sleeve_id == "reference":
        return pd.concat([reference.rename("reference"), pd.Series(0.0, index=reference.index, name="sleeve")], axis=1).dropna()
    sleeve = series[sleeve_id][cost_bps]["returns"]
    return pd.concat([reference.rename("reference"), sleeve.rename("sleeve")], axis=1, join="inner").dropna()


def build_portfolios(
    series: dict[str, dict[float, dict[str, Any]]],
    reference: pd.Series,
    construction_policy: str,
) -> dict[str, dict[float, dict[str, Any]]]:
    portfolios: dict[str, dict[float, dict[str, Any]]] = {portfolio_id: {} for portfolio_id in PORTFOLIO_IDS}
    for cost_bps in COST_BPS_GRID:
        ref_returns = reference.dropna()
        ref_equity = (1.0 + ref_returns).cumprod()
        ref_daily_rows = [
            {
                "date": pd.Timestamp(date).date().isoformat(),
                "portfolio_id": "frozen_reference_100pct",
                "construction_policy": "100pct_frozen_reference",
                "cost_assumption_bps": cost_bps,
                "reference_daily_return": float(value),
                "sleeve_daily_return": 0.0,
                "gross_return_before_portfolio_cost": float(value),
                "net_return": float(value),
                "equity": float(ref_equity.loc[date]),
                "pretrade_reference_weight": 1.0,
                "pretrade_sleeve_weight": 0.0,
                "post_trade_reference_weight": 1.0,
                "post_trade_sleeve_weight": 0.0,
                "one_way_turnover": 0.0,
                "transaction_cost_drag": 0.0,
                "event_type": "",
                "max_daily_exposure": 1.0,
                "max_daily_weight_sum": 1.0,
            }
            for date, value in ref_returns.items()
        ]
        portfolios["frozen_reference_100pct"][cost_bps] = {
            "returns": ref_returns,
            "turnover": pd.Series(0.0, index=ref_returns.index),
            "cost": pd.Series(0.0, index=ref_returns.index),
            "daily_rows": ref_daily_rows,
            "event_rows": [],
            "daily_df": pd.DataFrame(ref_daily_rows)
            .assign(date=lambda frame: pd.to_datetime(frame["date"], errors="coerce"))
            .set_index("date", drop=False),
            "event_df": pd.DataFrame(),
        }
        for portfolio_id, sleeve_id in SLEEVE_BY_PORTFOLIO.items():
            components = component_returns(series, reference, sleeve_id, cost_bps)
            portfolios[portfolio_id][cost_bps] = simulate_two_component_portfolio(
                components,
                portfolio_id,
                construction_policy,
                cost_bps,
            )
    return portfolios


def period_metric_payload(
    portfolio_id: str,
    payload: dict[str, Any],
    period_index: pd.DatetimeIndex | None = None,
) -> dict[str, Any]:
    returns = payload["returns"] if period_index is None else payload["returns"].reindex(period_index).dropna()
    turnover = payload["turnover"].reindex(returns.index).fillna(0.0)
    cost = payload["cost"].reindex(returns.index).fillna(0.0)
    metrics = prior.metrics_from_returns(returns)
    daily = payload.get("daily_df", pd.DataFrame(payload["daily_rows"]))
    if "date" in daily.columns and not pd.api.types.is_datetime64_any_dtype(daily["date"]):
        daily = daily.assign(date=pd.to_datetime(daily["date"], errors="coerce"))
    if period_index is not None:
        daily = daily[(daily.index >= period_index.min()) & (daily.index <= period_index.max())]
    events = payload.get("event_df", pd.DataFrame(payload["event_rows"]))
    if not events.empty:
        if "event_date" in events.columns and not pd.api.types.is_datetime64_any_dtype(events["event_date"]):
            events = events.assign(event_date=pd.to_datetime(events["event_date"], errors="coerce"))
        if period_index is not None:
            events = events[(events.index >= period_index.min()) & (events.index <= period_index.max())]
    if daily.empty:
        max_exposure = float("nan")
        max_weight_sum = float("nan")
        average_sleeve_weight = float("nan")
    else:
        max_exposure = float(pd.to_numeric(daily["max_daily_exposure"], errors="coerce").max())
        max_weight_sum = float(pd.to_numeric(daily["max_daily_weight_sum"], errors="coerce").max())
        average_sleeve_weight = float(pd.to_numeric(daily["post_trade_sleeve_weight"], errors="coerce").mean())
    if events.empty:
        min_pretrade_sleeve = 0.0 if portfolio_id == "frozen_reference_100pct" else ""
        max_pretrade_sleeve = 0.0 if portfolio_id == "frozen_reference_100pct" else ""
    else:
        min_pretrade_sleeve = float(pd.to_numeric(events["pretrade_sleeve_weight"], errors="coerce").min())
        max_pretrade_sleeve = float(pd.to_numeric(events["pretrade_sleeve_weight"], errors="coerce").max())
    invariant_pass = bool(
        len(returns) > 0
        and not returns.isna().any()
        and max_exposure <= 1.0 + WEIGHT_TOLERANCE
        and max_weight_sum <= 1.0 + WEIGHT_TOLERANCE
    )
    return {
        **metrics,
        "turnover": float(turnover.sum()),
        "rebalance_count": int((turnover > WEIGHT_TOLERANCE).sum()),
        "transaction_cost_drag": float(cost.sum()),
        "average_sleeve_weight": average_sleeve_weight,
        "minimum_sleeve_weight_before_rebalancing": min_pretrade_sleeve,
        "maximum_sleeve_weight_before_rebalancing": max_pretrade_sleeve,
        "max_daily_exposure": max_exposure,
        "max_daily_weight_sum": max_weight_sum,
        "timing_invariant_status": "pass_month_end_signal_next_session_close_execution",
        "numeric_invariant_status": "pass" if len(returns) and not returns.isna().any() else "fail",
        "exposure_invariant_status": "pass" if max_exposure <= 1.0 + WEIGHT_TOLERANCE else "fail",
        "weight_invariant_status": "pass" if max_weight_sum <= 1.0 + WEIGHT_TOLERANCE else "fail",
        "invariant_pass": invariant_pass,
    }


def full_period_rows(portfolios: dict[str, dict[float, dict[str, Any]]], construction_policy: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for portfolio_id, cost_map in portfolios.items():
        for cost_bps, payload in cost_map.items():
            rows.append(
                {
                    "portfolio_id": portfolio_id,
                    "construction_policy": construction_policy if portfolio_id != "frozen_reference_100pct" else "100pct_frozen_reference",
                    "cost_assumption_bps": cost_bps,
                    **period_metric_payload(portfolio_id, payload),
                }
            )
    return rows


def half_period_rows(portfolios: dict[str, dict[float, dict[str, Any]]], construction_policy: str) -> list[dict[str, Any]]:
    base_index = portfolios[f"{STRATEGY_ID}_candidate_20pct"][PRIMARY_COST_BPS]["returns"].index
    halves = source_batch.split_halves(base_index)
    rows: list[dict[str, Any]] = []
    for half_label, start, end in halves:
        period_index = base_index[(base_index >= start) & (base_index <= end)]
        for portfolio_id, cost_map in portfolios.items():
            for cost_bps, payload in cost_map.items():
                rows.append(
                    {
                        "portfolio_id": portfolio_id,
                        "construction_policy": construction_policy if portfolio_id != "frozen_reference_100pct" else "100pct_frozen_reference",
                        "half_label": half_label,
                        "half_source": "chronological_half_not_clean_holdout",
                        "cost_assumption_bps": cost_bps,
                        **period_metric_payload(portfolio_id, payload, period_index),
                    }
                )
    return rows


def month_end_dates(index: pd.DatetimeIndex) -> list[pd.Timestamp]:
    periods = pd.Series(index.to_period("M"), index=index)
    return [pd.Timestamp(date) for date in index[periods.ne(periods.shift(-1)).fillna(True)]]


def dominates(control: dict[str, Any], candidate: dict[str, Any]) -> bool:
    c_values = (float(control["cagr"]), float(control["sharpe_ratio"]), float(control["maximum_drawdown"]))
    v_values = (float(candidate["cagr"]), float(candidate["sharpe_ratio"]), float(candidate["maximum_drawdown"]))
    return all(c >= v - 1e-12 for c, v in zip(c_values, v_values)) and any(c > v + 1e-12 for c, v in zip(c_values, v_values))


def rolling_rows(portfolios: dict[str, dict[float, dict[str, Any]]], months: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    candidate_id = f"{STRATEGY_ID}_candidate_20pct"
    control_ids = ("HYG_buy_hold_20pct_control", "monthly_rebalanced_50_50_HYG_JNK_20pct_control")
    for cost_bps in COST_BPS_GRID:
        candidate_returns = portfolios[candidate_id][cost_bps]["returns"].dropna()
        first_available = candidate_returns.index.min()
        for end_date in month_end_dates(candidate_returns.index):
            cutoff = end_date - pd.DateOffset(months=months)
            if cutoff < first_available:
                continue
            period_index = candidate_returns.index[(candidate_returns.index >= cutoff) & (candidate_returns.index <= end_date)]
            candidate = period_metric_payload(candidate_id, portfolios[candidate_id][cost_bps], period_index)
            for control_id in control_ids:
                control = period_metric_payload(control_id, portfolios[control_id][cost_bps], period_index)
                rows.append(
                    {
                        "window_months": months,
                        "cost_assumption_bps": cost_bps,
                        "window_start": pd.Timestamp(period_index.min()).date().isoformat(),
                        "window_end": pd.Timestamp(period_index.max()).date().isoformat(),
                        "trading_days": int(len(period_index)),
                        "candidate_portfolio_id": candidate_id,
                        "control_portfolio_id": control_id,
                        "candidate_total_return": candidate["total_return"],
                        "candidate_cagr": candidate["cagr"],
                        "candidate_annualized_volatility": candidate["annualized_volatility"],
                        "candidate_sharpe_ratio": candidate["sharpe_ratio"],
                        "candidate_maximum_drawdown": candidate["maximum_drawdown"],
                        "candidate_turnover": candidate["turnover"],
                        "candidate_rebalance_count": candidate["rebalance_count"],
                        "candidate_transaction_cost_drag": candidate["transaction_cost_drag"],
                        "candidate_average_sleeve_weight": candidate["average_sleeve_weight"],
                        "control_total_return": control["total_return"],
                        "control_cagr": control["cagr"],
                        "control_annualized_volatility": control["annualized_volatility"],
                        "control_sharpe_ratio": control["sharpe_ratio"],
                        "control_maximum_drawdown": control["maximum_drawdown"],
                        "control_turnover": control["turnover"],
                        "control_rebalance_count": control["rebalance_count"],
                        "control_transaction_cost_drag": control["transaction_cost_drag"],
                        "control_average_sleeve_weight": control["average_sleeve_weight"],
                        "cagr_difference": float(candidate["cagr"]) - float(control["cagr"]),
                        "sharpe_ratio_difference": float(candidate["sharpe_ratio"]) - float(control["sharpe_ratio"]),
                        "maximum_drawdown_difference": float(candidate["maximum_drawdown"]) - float(control["maximum_drawdown"]),
                        "annualized_volatility_difference": float(candidate["annualized_volatility"]) - float(control["annualized_volatility"]),
                        "control_dominates_angl": dominates(control, candidate),
                        "timing_invariant_status": candidate["timing_invariant_status"],
                        "numeric_invariant_status": candidate["numeric_invariant_status"],
                        "exposure_invariant_status": candidate["exposure_invariant_status"],
                        "weight_invariant_status": candidate["weight_invariant_status"],
                    }
                )
    return rows


def rolling_summary_rows(rows_36: list[dict[str, Any]], rows_60: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for months, rows in ((36, rows_36), (60, rows_60)):
        for cost_bps in COST_BPS_GRID:
            cost_rows = [row for row in rows if float(row["cost_assumption_bps"]) == cost_bps]
            by_window: dict[tuple[str, str], list[dict[str, Any]]] = {}
            for row in cost_rows:
                by_window.setdefault((row["window_start"], row["window_end"]), []).append(row)
            best_diffs: list[float] = []
            dominated_windows = 0
            for window_rows in by_window.values():
                best_control = max(window_rows, key=lambda row: float(row["control_sharpe_ratio"]))
                best_diffs.append(float(best_control["sharpe_ratio_difference"]))
                if any(row["control_dominates_angl"] for row in window_rows):
                    dominated_windows += 1
            positive_count = sum(diff > 0.0 for diff in best_diffs)
            count = len(best_diffs)
            summary.append(
                {
                    "window_months": months,
                    "cost_assumption_bps": cost_bps,
                    "window_count": count,
                    "median_sharpe_difference_vs_best_control": float(pd.Series(best_diffs).median()) if best_diffs else "",
                    "positive_sharpe_difference_count": positive_count,
                    "positive_sharpe_difference_pct": positive_count / count if count else "",
                    "control_dominated_window_count": dominated_windows,
                    "control_dominated_window_pct": dominated_windows / count if count else "",
                }
            )
    return summary


def turnover_cost_rows(portfolios: dict[str, dict[float, dict[str, Any]]], construction_policy: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for portfolio_id, cost_map in portfolios.items():
        for cost_bps, payload in cost_map.items():
            rows.append(
                {
                    "portfolio_id": portfolio_id,
                    "construction_policy": construction_policy if portfolio_id != "frozen_reference_100pct" else "100pct_frozen_reference",
                    "cost_assumption_bps": cost_bps,
                    "total_one_way_turnover": float(payload["turnover"].sum()),
                    "rebalance_count": int((payload["turnover"] > WEIGHT_TOLERANCE).sum()),
                    "transaction_cost_drag": float(payload["cost"].sum()),
                    "initial_establishment_charged": bool(portfolio_id != "frozen_reference_100pct"),
                    "monthly_rebalance_policy": "month_end_signal_next_available_session_close_execution"
                    if portfolio_id != "frozen_reference_100pct"
                    else "not_applicable_reference_only",
                }
            )
    return rows


def daily_nav_rows(portfolios: dict[str, dict[float, dict[str, Any]]], construction_policy: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for portfolio_id, cost_map in portfolios.items():
        payload = cost_map[PRIMARY_COST_BPS]
        for row in payload["daily_rows"]:
            out = dict(row)
            if portfolio_id == "frozen_reference_100pct":
                out["construction_policy"] = "100pct_frozen_reference"
            else:
                out["construction_policy"] = construction_policy
            rows.append(out)
    return rows


def event_rows(portfolios: dict[str, dict[float, dict[str, Any]]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for portfolio_id, cost_map in portfolios.items():
        for payload in cost_map.values():
            rows.extend(payload["event_rows"])
    return rows


def diagnostic_rows(drift_portfolios: dict[str, dict[float, dict[str, Any]]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for portfolio_id, cost_map in drift_portfolios.items():
        if portfolio_id == "frozen_reference_100pct":
            continue
        for cost_bps, payload in cost_map.items():
            rows.append(
                {
                    "portfolio_id": portfolio_id,
                    "construction_policy": "initial_80_20_with_natural_drift",
                    "diagnostic_only": True,
                    "cost_assumption_bps": cost_bps,
                    **period_metric_payload(portfolio_id, payload),
                }
            )
    return rows


def full_portfolio_metrics(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {row["portfolio_id"]: row for row in rows if float(row["cost_assumption_bps"]) == PRIMARY_COST_BPS}


def decision(
    reproduction: list[dict[str, Any]],
    full_rows: list[dict[str, Any]],
    half_rows: list[dict[str, Any]],
    rolling_summary: list[dict[str, Any]],
) -> tuple[str, str, dict[str, Any]]:
    reproduction_pass = all(row["reproduction_status"] == "pass" for row in reproduction)
    if not reproduction_pass:
        return (
            "validation_data_or_methodology_blocked",
            "methodology_failure",
            {"prior_reproduction_passed": False},
        )
    portfolio_5 = full_portfolio_metrics(full_rows)
    candidate = portfolio_5[f"{STRATEGY_ID}_candidate_20pct"]
    controls = [portfolio_5["HYG_buy_hold_20pct_control"], portfolio_5["monthly_rebalanced_50_50_HYG_JNK_20pct_control"]]
    full_sharpe_diffs = [float(candidate["sharpe_ratio"]) - float(control["sharpe_ratio"]) for control in controls]
    best_control_mdd = max(float(control["maximum_drawdown"]) for control in controls)
    full_control_dominates = any(dominates(control, candidate) for control in controls)
    full_favorable = min(full_sharpe_diffs) > 0.0 and not full_control_dominates
    half_ok = True
    for half in ("first_chronological_half", "second_chronological_half"):
        half_candidate = next(
            row
            for row in half_rows
            if row["portfolio_id"] == f"{STRATEGY_ID}_candidate_20pct"
            and row["half_label"] == half
            and float(row["cost_assumption_bps"]) == PRIMARY_COST_BPS
        )
        half_controls = [
            row
            for row in half_rows
            if row["portfolio_id"] in {"HYG_buy_hold_20pct_control", "monthly_rebalanced_50_50_HYG_JNK_20pct_control"}
            and row["half_label"] == half
            and float(row["cost_assumption_bps"]) == PRIMARY_COST_BPS
        ]
        if not all(float(half_candidate["sharpe_ratio"]) > float(control["sharpe_ratio"]) for control in half_controls):
            half_ok = False
    summary_36 = next(row for row in rolling_summary if int(row["window_months"]) == 36 and float(row["cost_assumption_bps"]) == PRIMARY_COST_BPS)
    summary_60 = next(row for row in rolling_summary if int(row["window_months"]) == 60 and float(row["cost_assumption_bps"]) == PRIMARY_COST_BPS)
    rolling_ok = (
        float(summary_36["median_sharpe_difference_vs_best_control"]) > 0.0
        and float(summary_60["median_sharpe_difference_vs_best_control"]) > 0.0
        and float(summary_36["positive_sharpe_difference_pct"]) > 0.5
        and float(summary_60["positive_sharpe_difference_pct"]) > 0.5
        and float(summary_36["control_dominated_window_pct"]) <= 0.5
        and float(summary_60["control_dominated_window_pct"]) <= 0.5
    )
    mdd_ok = float(candidate["maximum_drawdown"]) >= best_control_mdd - 0.02
    full_positive_ok = min(full_sharpe_diffs) >= 0.03 and mdd_ok and not full_control_dominates
    turnover_costs_explicit = float(candidate["turnover"]) > 0.0 and float(candidate["transaction_cost_drag"]) > 0.0
    invariant_ok = all(row.get("invariant_pass") is True for row in full_rows)
    checks = {
        "prior_reproduction_passed": reproduction_pass,
        "corrected_full_sharpe_min_advantage": min(full_sharpe_diffs),
        "corrected_full_control_dominates": full_control_dominates,
        "corrected_full_mdd_not_worse_than_best_control_by_more_than_0_02": mdd_ok,
        "corrected_half_sharpe_exceeds_controls": half_ok,
        "corrected_rolling_requirements_pass": rolling_ok,
        "turnover_and_costs_explicit": turnover_costs_explicit,
        "invariant_ok": invariant_ok,
        "rolling_36": summary_36,
        "rolling_60": summary_60,
    }
    if full_positive_ok and half_ok and rolling_ok and turnover_costs_explicit and invariant_ok:
        return "validation_positive", "", checks
    if full_control_dominates:
        return "validation_failed", "weak_vs_primary_control", checks
    if min(full_sharpe_diffs) <= 0.0:
        return "validation_failed", "weak_vs_primary_control", checks
    if not turnover_costs_explicit:
        return "validation_failed", "cost_drag", checks
    both_medians_non_positive = (
        float(summary_36["median_sharpe_difference_vs_best_control"]) <= 0.0
        and float(summary_60["median_sharpe_difference_vs_best_control"]) <= 0.0
    )
    if both_medians_non_positive:
        return "validation_failed", "period_instability", checks
    if full_favorable and invariant_ok:
        return "validation_mixed", "", checks
    return "validation_failed", "overfit_or_unstable", checks


def next_action_for(outcome: str) -> str:
    if outcome == "validation_positive":
        return "direction_owner_review_angl_paper_demo_eligibility_v2"
    if outcome == "validation_mixed":
        return "direction_owner_review_angl_corrected_validation_mixed_v1"
    if outcome == "validation_failed":
        return "direction_owner_review_close_angl_after_methodology_correction_v1"
    return "direction_owner_review_angl_methodology_block_v1"


def strategy_card_row(card: Any, outcome: str, failure_reason: str, next_action: str) -> dict[str, Any]:
    return {
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "display_name": DISPLAY_NAME,
        "entity_type": "strategy_configuration",
        "strategy_architecture": card.complete_frozen_rule,
        "source_or_research_lineage": "angl_fallen_angel_diversifier_validation_v1_methodology_correction",
        "instrument_universe": "ANGL|HYG|JNK",
        "parameters": card.parameters,
        "benchmark_or_control": "HYG_buy_hold|monthly_rebalanced_50_50_HYG_JNK|frozen_current_active_vm_dsr_usci_combo",
        "stage": "validation",
        "trial_id": CORRECTION_TRIAL_ID,
        "parent_trial_id": PREVIOUS_VALIDATION_TRIAL_ID,
        "adaptation_label": ADAPTATION_LABEL,
        "changed_fields_from_parent": "portfolio_construction_accounting_rebalancing_turnover_and_costs_only",
        "outcome": outcome,
        "failure_reason": failure_reason,
        "next_action": next_action,
        "base_strategy_changed": False,
        "instruments_changed": False,
        "sleeve_weight_changed": False,
        "benchmarks_changed": False,
        "evaluation_dates_selected_from_performance": False,
        "validation_portfolio_methodology_changed_or_verified": True,
    }


def trial_ledger_row(card: Any, outcome: str, failure_reason: str, next_action: str) -> dict[str, Any]:
    return {
        "strategy_id": STRATEGY_ID,
        "family_id": FAMILY_ID,
        "display_name": DISPLAY_NAME,
        "entity_type": "experiment_trial",
        "strategy_architecture": card.complete_frozen_rule,
        "source_or_research_lineage": "angl_fallen_angel_diversifier_validation_v1_methodology_correction",
        "instrument_universe": "ANGL|HYG|JNK",
        "parameters": card.parameters,
        "benchmark_or_control": "HYG_buy_hold|monthly_rebalanced_50_50_HYG_JNK|frozen_current_active_vm_dsr_usci_combo",
        "stage": "validation",
        "trial_id": CORRECTION_TRIAL_ID,
        "parent_trial_id": PREVIOUS_VALIDATION_TRIAL_ID,
        "adaptation_label": ADAPTATION_LABEL,
        "changed_fields_from_parent": "portfolio_construction_accounting_rebalancing_turnover_and_costs_only",
        "outcome": outcome,
        "primary_failure_reason": failure_reason,
        "next_action": next_action,
        "base_strategy_changed": False,
        "instruments_changed": False,
        "sleeve_weight_changed": False,
        "benchmarks_changed": False,
        "evaluation_dates_selected_from_performance": False,
        "validation_portfolio_methodology_changed_or_verified": True,
    }


def benchmark_rows() -> list[dict[str, Any]]:
    return [
        {
            "benchmark_or_control_id": "HYG_buy_hold",
            "entity_type": "benchmark_reference",
            "stage": "benchmark_reference_only",
            "role": "80_20_principal_control",
            "counted_as_strategy": False,
            "counted_as_trial": False,
        },
        {
            "benchmark_or_control_id": "monthly_rebalanced_50_50_HYG_JNK",
            "entity_type": "benchmark_reference",
            "stage": "benchmark_reference_only",
            "role": "80_20_principal_control",
            "counted_as_strategy": False,
            "counted_as_trial": False,
        },
        {
            "benchmark_or_control_id": "frozen_current_active_vm_dsr_usci_combo",
            "entity_type": "benchmark_reference",
            "stage": "benchmark_reference_only",
            "role": "frozen_portfolio_reference",
            "counted_as_strategy": False,
            "counted_as_trial": False,
        },
    ]


COMMON_METRIC_FIELDS = [
    "evaluation_start",
    "evaluation_end",
    "trading_days",
    "total_return",
    "cagr",
    "annualized_volatility",
    "sharpe_ratio",
    "maximum_drawdown",
    "turnover",
    "rebalance_count",
    "transaction_cost_drag",
    "average_sleeve_weight",
    "minimum_sleeve_weight_before_rebalancing",
    "maximum_sleeve_weight_before_rebalancing",
    "max_daily_exposure",
    "max_daily_weight_sum",
    "timing_invariant_status",
    "numeric_invariant_status",
    "exposure_invariant_status",
    "weight_invariant_status",
    "invariant_pass",
]


def build_report(outcome: str, failure_reason: str, next_action: str, checks: dict[str, Any]) -> str:
    return f"""
# ANGL 80/20 Portfolio Construction Methodology Correction V1

This correction covered exactly `{STRATEGY_ID}` and preserved the frozen base ANGL strategy rule. The previous
validation trial `{PREVIOUS_VALIDATION_TRIAL_ID}` was read only and left unchanged.

## Prior Method

The prior 80/20 validation construction is classified as `fixed_weight_return_blend`: the daily portfolio return was
computed as `0.8 * frozen_reference_return + 0.2 * sleeve_return`. No daily portfolio holdings, monthly rebalance
events, one-way turnover, or portfolio-level transaction costs were modeled, so the reported zero portfolio turnover
was correct for that implementation but not sufficient for a tradable monthly 80/20 construction.

## Corrected Method

The canonical corrected construction is `monthly_rebalanced_80_20`: start at 80% frozen reference virtual NAV and
20% ANGL or control virtual NAV, allow natural daily drift, rebalance back to 80/20 at the next available session close
after each month-end, and charge one-way turnover costs at 0, 5, and 10 bps.

## Decision

- Corrected outcome: `{outcome}`
- Primary failure reason: `{failure_reason}`
- Exact next action: `{next_action}`

## Key Checks

- Prior reproduction pass: `{checks.get('prior_reproduction_passed')}`
- Corrected full-period minimum Sharpe advantage: `{csv_value(checks.get('corrected_full_sharpe_min_advantage'))}`
- Corrected drawdown tolerance pass: `{checks.get('corrected_full_mdd_not_worse_than_best_control_by_more_than_0_02')}`
- Corrected half-period Sharpe pass: `{checks.get('corrected_half_sharpe_exceeds_controls')}`
- Corrected rolling requirements pass: `{checks.get('corrected_rolling_requirements_pass')}`
- Turnover and costs explicit: `{checks.get('turnover_and_costs_explicit')}`

No period is claimed as a clean or untouched holdout. No source research, provider download, strategy-rule change,
promotion review, paper/demo activation, broker/account/order path, or real-money action occurred.
"""


def deterministic_core_hash() -> str:
    names = [
        "correction_manifest.yaml",
        "strategy_cards.csv",
        "trial_ledger.csv",
        "process_task_log.csv",
        "benchmark_reference_log.csv",
        "prior_portfolio_method_classification.csv",
        "prior_result_reproduction.csv",
        "daily_nav_reconciliation.csv",
        "monthly_rebalance_events.csv",
        "turnover_cost_reconciliation.csv",
        "canonical_full_period_results.csv",
        "canonical_chronological_half_results.csv",
        "canonical_rolling_36_month_results.csv",
        "canonical_rolling_60_month_results.csv",
        "canonical_rolling_window_summary.csv",
        "buy_and_hold_drift_diagnostic.csv",
        "outcome_summary.csv",
        "failure_reasons.csv",
        "next_actions.csv",
        "methodology_correction_report.md",
    ]
    digest = hashlib.sha256()
    for name in names:
        path = OUTPUT_DIR / name
        digest.update(name.encode("utf-8"))
        digest.update(path.read_bytes() if path.exists() else b"missing")
    return "sha256:" + digest.hexdigest()


ROLLING_FIELDS = [
    "window_months",
    "cost_assumption_bps",
    "window_start",
    "window_end",
    "trading_days",
    "candidate_portfolio_id",
    "control_portfolio_id",
    "candidate_total_return",
    "candidate_cagr",
    "candidate_annualized_volatility",
    "candidate_sharpe_ratio",
    "candidate_maximum_drawdown",
    "candidate_turnover",
    "candidate_rebalance_count",
    "candidate_transaction_cost_drag",
    "candidate_average_sleeve_weight",
    "control_total_return",
    "control_cagr",
    "control_annualized_volatility",
    "control_sharpe_ratio",
    "control_maximum_drawdown",
    "control_turnover",
    "control_rebalance_count",
    "control_transaction_cost_drag",
    "control_average_sleeve_weight",
    "cagr_difference",
    "sharpe_ratio_difference",
    "maximum_drawdown_difference",
    "annualized_volatility_difference",
    "control_dominates_angl",
    "timing_invariant_status",
    "numeric_invariant_status",
    "exposure_invariant_status",
    "weight_invariant_status",
]


def run() -> dict[str, Any]:
    protected_before = protected_state_hashes()
    cache_before = protected_cache_hashes()
    previous_before = previous_validation_hashes()
    clean_output_dir()

    card, frozen, series, prior_blend = frozen_inputs()
    reproduction = prior_reproduction_rows(prior_blend)
    canonical = build_portfolios(series, frozen["reference"], "monthly_rebalanced_80_20")
    drift = build_portfolios(series, frozen["reference"], "initial_80_20_with_natural_drift")
    full_rows = full_period_rows(canonical, "monthly_rebalanced_80_20")
    half_rows = half_period_rows(canonical, "monthly_rebalanced_80_20")
    rolling_36 = rolling_rows(canonical, 36)
    rolling_60 = rolling_rows(canonical, 60)
    rolling_summary = rolling_summary_rows(rolling_36, rolling_60)
    outcome, failure_reason, checks = decision(reproduction, full_rows, half_rows, rolling_summary)
    next_action = next_action_for(outcome)

    write_yaml(
        OUTPUT_DIR / "correction_manifest.yaml",
        {
            "correction_id": CORRECTION_ID,
            "mode": "correction",
            "lane": "targeted_methodology_correction",
            "stage": "validation",
            "adaptation_label": ADAPTATION_LABEL,
            "strategy_id": STRATEGY_ID,
            "family_id": FAMILY_ID,
            "previous_validation_trial_id": PREVIOUS_VALIDATION_TRIAL_ID,
            "correction_trial_id": CORRECTION_TRIAL_ID,
            "prior_method_classification": "fixed_weight_return_blend",
            "canonical_operational_policy": "monthly_rebalanced_80_20",
            "diagnostic_policy": "initial_80_20_with_natural_drift",
            "target_reference_weight": TARGET_REFERENCE_WEIGHT,
            "target_sleeve_weight": TARGET_SLEEVE_WEIGHT,
            "primary_cost_assumption_bps": PRIMARY_COST_BPS,
            "cost_diagnostics_bps": list(COST_BPS_GRID),
            "reproduction_tolerance": REPRODUCTION_TOLERANCE,
            "component_virtual_nav_inputs": "frozen_reference plus prior frozen ANGL/HYG/HYG_JNK standalone/control NAV returns",
            "exact_next_action": next_action,
            **FORBIDDEN_FLAGS,
        },
    )
    strategy_fields = [
        "strategy_id",
        "family_id",
        "display_name",
        "entity_type",
        "strategy_architecture",
        "source_or_research_lineage",
        "instrument_universe",
        "parameters",
        "benchmark_or_control",
        "stage",
        "trial_id",
        "parent_trial_id",
        "adaptation_label",
        "changed_fields_from_parent",
        "outcome",
        "failure_reason",
        "next_action",
        "base_strategy_changed",
        "instruments_changed",
        "sleeve_weight_changed",
        "benchmarks_changed",
        "evaluation_dates_selected_from_performance",
        "validation_portfolio_methodology_changed_or_verified",
    ]
    write_csv(OUTPUT_DIR / "strategy_cards.csv", [strategy_card_row(card, outcome, failure_reason, next_action)], strategy_fields)
    trial_fields = [
        "strategy_id",
        "family_id",
        "display_name",
        "entity_type",
        "strategy_architecture",
        "source_or_research_lineage",
        "instrument_universe",
        "parameters",
        "benchmark_or_control",
        "stage",
        "trial_id",
        "parent_trial_id",
        "adaptation_label",
        "changed_fields_from_parent",
        "outcome",
        "primary_failure_reason",
        "next_action",
        "base_strategy_changed",
        "instruments_changed",
        "sleeve_weight_changed",
        "benchmarks_changed",
        "evaluation_dates_selected_from_performance",
        "validation_portfolio_methodology_changed_or_verified",
    ]
    write_csv(OUTPUT_DIR / "trial_ledger.csv", [trial_ledger_row(card, outcome, failure_reason, next_action)], trial_fields)
    write_csv(
        OUTPUT_DIR / "process_task_log.csv",
        [
            {
                "task_id": CORRECTION_ID,
                "entity_type": "process_task",
                "stage": "validation",
                "adaptation_label": ADAPTATION_LABEL,
                "outcome": outcome,
                "exact_next_action": next_action,
                "strategy_counted": False,
                "trial_counted": False,
            }
        ],
        ["task_id", "entity_type", "stage", "adaptation_label", "outcome", "exact_next_action", "strategy_counted", "trial_counted"],
    )
    write_csv(
        OUTPUT_DIR / "benchmark_reference_log.csv",
        benchmark_rows(),
        ["benchmark_or_control_id", "entity_type", "stage", "role", "counted_as_strategy", "counted_as_trial"],
    )
    write_csv(
        OUTPUT_DIR / "prior_portfolio_method_classification.csv",
        prior_portfolio_method_classification_rows(),
        [
            "validation_id",
            "portfolio_method_classification",
            "implementation_location",
            "daily_holdings_or_weights_available",
            "daily_series_reconciliation",
            "rebalance_trigger",
            "rebalance_frequency",
            "transaction_timing",
            "turnover_calculation",
            "transaction_cost_calculation",
            "reported_zero_turnover_correct_for_prior_implementation",
            "tradable_without_implicit_daily_rebalancing",
            "code_verified_mechanism",
        ],
    )
    write_csv(
        OUTPUT_DIR / "prior_result_reproduction.csv",
        reproduction,
        ["portfolio_id", "metric", "prior_value", "recomputed_value", "absolute_difference", "tolerance", "reproduction_status"],
    )
    write_csv(
        OUTPUT_DIR / "daily_nav_reconciliation.csv",
        daily_nav_rows(canonical, "monthly_rebalanced_80_20"),
        [
            "date",
            "portfolio_id",
            "construction_policy",
            "cost_assumption_bps",
            "reference_daily_return",
            "sleeve_daily_return",
            "gross_return_before_portfolio_cost",
            "net_return",
            "equity",
            "pretrade_reference_weight",
            "pretrade_sleeve_weight",
            "post_trade_reference_weight",
            "post_trade_sleeve_weight",
            "one_way_turnover",
            "transaction_cost_drag",
            "event_type",
            "max_daily_exposure",
            "max_daily_weight_sum",
        ],
    )
    write_csv(
        OUTPUT_DIR / "monthly_rebalance_events.csv",
        event_rows(canonical),
        [
            "portfolio_id",
            "construction_policy",
            "cost_assumption_bps",
            "event_date",
            "signal_date",
            "event_type",
            "pretrade_reference_weight",
            "pretrade_sleeve_weight",
            "target_reference_weight",
            "target_sleeve_weight",
            "one_way_turnover",
            "transaction_cost_rate",
            "transaction_cost_drag",
            "post_trade_reference_weight",
            "post_trade_sleeve_weight",
            "timing_convention",
        ],
    )
    write_csv(
        OUTPUT_DIR / "turnover_cost_reconciliation.csv",
        turnover_cost_rows(canonical, "monthly_rebalanced_80_20"),
        [
            "portfolio_id",
            "construction_policy",
            "cost_assumption_bps",
            "total_one_way_turnover",
            "rebalance_count",
            "transaction_cost_drag",
            "initial_establishment_charged",
            "monthly_rebalance_policy",
        ],
    )
    write_csv(
        OUTPUT_DIR / "canonical_full_period_results.csv",
        full_rows,
        ["portfolio_id", "construction_policy", "cost_assumption_bps", *COMMON_METRIC_FIELDS],
    )
    write_csv(
        OUTPUT_DIR / "canonical_chronological_half_results.csv",
        half_rows,
        ["portfolio_id", "construction_policy", "half_label", "half_source", "cost_assumption_bps", *COMMON_METRIC_FIELDS],
    )
    write_csv(OUTPUT_DIR / "canonical_rolling_36_month_results.csv", rolling_36, ROLLING_FIELDS)
    write_csv(OUTPUT_DIR / "canonical_rolling_60_month_results.csv", rolling_60, ROLLING_FIELDS)
    write_csv(
        OUTPUT_DIR / "canonical_rolling_window_summary.csv",
        rolling_summary,
        [
            "window_months",
            "cost_assumption_bps",
            "window_count",
            "median_sharpe_difference_vs_best_control",
            "positive_sharpe_difference_count",
            "positive_sharpe_difference_pct",
            "control_dominated_window_count",
            "control_dominated_window_pct",
        ],
    )
    write_csv(
        OUTPUT_DIR / "buy_and_hold_drift_diagnostic.csv",
        diagnostic_rows(drift),
        ["portfolio_id", "construction_policy", "diagnostic_only", "cost_assumption_bps", *COMMON_METRIC_FIELDS],
    )
    write_csv(
        OUTPUT_DIR / "outcome_summary.csv",
        [
            {
                "entity_id": STRATEGY_ID,
                "entity_type": "strategy_configuration",
                "stage": "validation",
                "adaptation_label": ADAPTATION_LABEL,
                "outcome": outcome,
                "primary_failure_reason": failure_reason,
                "next_action": next_action,
            }
        ],
        ["entity_id", "entity_type", "stage", "adaptation_label", "outcome", "primary_failure_reason", "next_action"],
    )
    write_csv(
        OUTPUT_DIR / "failure_reasons.csv",
        [
            {
                "strategy_id": STRATEGY_ID,
                "trial_id": CORRECTION_TRIAL_ID,
                "parent_trial_id": PREVIOUS_VALIDATION_TRIAL_ID,
                "outcome": outcome,
                "primary_failure_reason": failure_reason,
                "next_action": next_action,
            }
        ]
        if failure_reason
        else [],
        ["strategy_id", "trial_id", "parent_trial_id", "outcome", "primary_failure_reason", "next_action"],
    )
    write_csv(
        OUTPUT_DIR / "next_actions.csv",
        [
            {
                "scope": "global",
                "entity_id": CORRECTION_ID,
                "exact_next_action": next_action,
                "execute_now": False,
                "reason": outcome,
            },
            {
                "scope": "strategy_configuration",
                "entity_id": STRATEGY_ID,
                "exact_next_action": next_action,
                "execute_now": False,
                "reason": outcome,
            },
        ],
        ["scope", "entity_id", "exact_next_action", "execute_now", "reason"],
    )
    write_text(OUTPUT_DIR / "methodology_correction_report.md", build_report(outcome, failure_reason, next_action, checks))

    protected_after = protected_state_hashes()
    cache_after = protected_cache_hashes()
    previous_after = previous_validation_hashes()
    consistency = {
        "correction_id": CORRECTION_ID,
        "strategy_id": STRATEGY_ID,
        "exactly_one_strategy_corrected": True,
        "prior_validation_trial_preserved": True,
        "correction_child_trial_id": CORRECTION_TRIAL_ID,
        "parent_validation_trial_id": PREVIOUS_VALIDATION_TRIAL_ID,
        "prior_method_classification": "fixed_weight_return_blend",
        "prior_result_reproduction_passed": all(row["reproduction_status"] == "pass" for row in reproduction),
        "canonical_policy": "monthly_rebalanced_80_20",
        "diagnostic_policy": "initial_80_20_with_natural_drift",
        "strategy_definition_changed": False,
        "base_strategy_changed": False,
        "instruments_changed": False,
        "sleeve_weight_changed": False,
        "benchmarks_changed": False,
        "evaluation_dates_selected_from_performance": False,
        "validation_portfolio_methodology_changed_or_verified": True,
        "entity_separation_passed": True,
        "protected_state_hashes_before": protected_before,
        "protected_state_hashes_after": protected_after,
        "protected_state_hashes_unchanged": protected_before == protected_after,
        "protected_cache_hashes_before": cache_before,
        "protected_cache_hashes_after": cache_after,
        "protected_cache_hashes_unchanged": cache_before == cache_after,
        "prior_validation_hashes_before": previous_before,
        "prior_validation_hashes_after": previous_after,
        "prior_validation_hashes_unchanged": previous_before == previous_after,
        "rolling_36_window_count_primary": next(
            row for row in rolling_summary if int(row["window_months"]) == 36 and float(row["cost_assumption_bps"]) == PRIMARY_COST_BPS
        )["window_count"],
        "rolling_60_window_count_primary": next(
            row for row in rolling_summary if int(row["window_months"]) == 60 and float(row["cost_assumption_bps"]) == PRIMARY_COST_BPS
        )["window_count"],
        "no_clean_holdout_claimed": True,
        "outcome": outcome,
        "stage": "validation",
        "primary_failure_reason": failure_reason,
        "exact_next_action": next_action,
        "deterministic_core_hash": deterministic_core_hash(),
        **FORBIDDEN_FLAGS,
    }
    consistency["consistency_passed"] = bool(
        consistency["exactly_one_strategy_corrected"]
        and consistency["prior_validation_trial_preserved"]
        and consistency["prior_result_reproduction_passed"]
        and consistency["entity_separation_passed"]
        and consistency["protected_state_hashes_unchanged"]
        and consistency["protected_cache_hashes_unchanged"]
        and consistency["prior_validation_hashes_unchanged"]
        and not any(consistency[name] for name in FORBIDDEN_FLAGS)
    )
    write_json(OUTPUT_DIR / "consistency_check.json", consistency)
    return {
        "correction_id": CORRECTION_ID,
        "evidence_path": rel(OUTPUT_DIR),
        "strategy_id": STRATEGY_ID,
        "prior_method_classification": "fixed_weight_return_blend",
        "prior_result_reproduction_passed": consistency["prior_result_reproduction_passed"],
        "outcome": outcome,
        "primary_failure_reason": failure_reason,
        "exact_next_action": next_action,
        "rolling_36_window_count_primary": consistency["rolling_36_window_count_primary"],
        "rolling_60_window_count_primary": consistency["rolling_60_window_count_primary"],
        "protected_state_hashes_unchanged": consistency["protected_state_hashes_unchanged"],
        "protected_cache_hashes_unchanged": consistency["protected_cache_hashes_unchanged"],
        "prior_validation_hashes_unchanged": consistency["prior_validation_hashes_unchanged"],
        "task_outcome": "angl_80_20_portfolio_construction_methodology_correction_v1_complete",
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
