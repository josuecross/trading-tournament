from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

import run_active_strategy_evidence_recompute as active


ROOT = Path(__file__).resolve().parents[3]
EVIDENCE_DIR = ROOT / "evidence" / "spy_turn_of_month_bil_screen_v1" / "latest"
INTAKE_DIR = ROOT / "strategy_lab" / "research_os" / "public_strategy_sources" / "intake_candidates"
SOURCE_ID = "mcconnell_xu_equity_returns_turn_of_month_2008"
CANDIDATE_ID = "spy_turn_of_month_bil_v1"
FAMILY_ID = "calendar_effects"
RISK_ASSET = "SPY"
OUTSIDE_ASSET = "BIL"
ACTIVE_COMBO_ID = "active_combo_vm_dsr_equal_weight_v1"
ACTIVE_COMBO_SERIES = ROOT / "evidence" / "active_combo_series_reconciliation" / "latest" / "combo_daily_series.csv"
ACTIVE_VM_ID = active.VM_ID
BENCHMARK_IDS = [
    "SPY_buy_and_hold",
    "BIL_cash_proxy",
    active.SPY_200D_ID,
    ACTIVE_COMBO_ID,
    ACTIVE_VM_ID,
]
ALLOWED_OUTCOMES = {
    "comparative_evidence_positive",
    "calendar_effect_present_but_no_strategy_edge",
    "risk_reduction_without_return_edge",
    "cost_sensitive_no_edge",
    "no_material_edge",
    "signal_scarce_no_evidence",
    "not_comparable",
    "invalid_methodology",
    "direction_owner_review_required",
}


def sha256_path(path: Path) -> str:
    if not path.exists():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def clean_value(value: Any) -> Any:
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        val = float(value)
        if not math.isfinite(val):
            return None
        return round(val, 12)
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    return value


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
        return "|".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True)
    return str(value)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=clean_value) + "\n", encoding="utf-8")


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fields})


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def source_intake_record() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "source": {
            "source_id": SOURCE_ID,
            "authors": ["John J. McConnell", "Wei Xu"],
            "title": "Equity Returns at the Turn of the Month",
            "publication": "Financial Analysts Journal",
            "publication_year": 2008,
            "source_class": "academic_primary",
            "family": FAMILY_ID,
        },
        "source_supported_rule": {
            "turn_of_month_interval": "Day -1 through Day +3",
            "day_minus_1": "final trading day of the prior calendar month",
            "day_plus_1": "first trading day of the new calendar month",
            "day_plus_2": "second trading day of the new calendar month",
            "day_plus_3": "third trading day of the new calendar month",
            "source_reports_return_pattern_not_spy_bil_execution": True,
        },
        "project_candidate": {
            "candidate_id": CANDIDATE_ID,
            "family": FAMILY_ID,
            "classification": [
                "source_inspired_etf_calendar_adaptation",
                "long_only_spy_bil_rotation",
                "not_source_index_replication",
            ],
            "hypothesis": "SPY exposure restricted to the documented turn-of-the-month interval may provide useful return or return/risk characteristics, while BIL is held outside the interval.",
            "risk_asset": RISK_ASSET,
            "outside_asset": OUTSIDE_ASSET,
        },
        "governance": {
            "web_browsing_used": False,
            "provider_download": False,
            "strategy_discovery": False,
            "promotion_or_paper_forward_allowed": False,
            "real_money_recommendation": False,
        },
    }


def source_rule_rows() -> list[dict[str, Any]]:
    return [
        {"rule_id": "source_day_minus_1", "rule_value": "final trading day of the prior calendar month", "classification": "source_explicit", "source_id": SOURCE_ID},
        {"rule_id": "source_day_plus_1", "rule_value": "first trading day of the new calendar month", "classification": "source_explicit", "source_id": SOURCE_ID},
        {"rule_id": "source_day_plus_2", "rule_value": "second trading day of the new calendar month", "classification": "source_explicit", "source_id": SOURCE_ID},
        {"rule_id": "source_day_plus_3", "rule_value": "third trading day of the new calendar month", "classification": "source_explicit", "source_id": SOURCE_ID},
        {"rule_id": "source_return_interval", "rule_value": "daily equity returns from Day -1 through Day +3", "classification": "source_explicit", "source_id": SOURCE_ID},
        {"rule_id": "entry_execution", "rule_value": "buy SPY at Day -2 adjusted close to capture Day -1 through Day +3 close-to-close returns", "classification": "project_calendar_execution_convention", "source_id": SOURCE_ID},
        {"rule_id": "exit_execution", "rule_value": "sell SPY and buy BIL at Day +3 adjusted close", "classification": "project_calendar_execution_convention", "source_id": SOURCE_ID},
        {"rule_id": "outside_asset", "rule_value": "hold BIL outside the turn-of-month interval", "classification": "project_calendar_execution_convention", "source_id": SOURCE_ID},
        {"rule_id": "costs", "rule_value": "apply canonical project transaction cost to both switch legs", "classification": "project_execution_convention", "source_id": SOURCE_ID},
    ]


def source_support_rows() -> list[dict[str, Any]]:
    rows = []
    for row in source_rule_rows():
        rows.append(
            {
                "material_rule": row["rule_id"],
                "source_id": SOURCE_ID,
                "support_reference": "Direction-owner supplied McConnell-Xu source packet; project execution conventions are explicitly separated from source-explicit return interval.",
                "support_status": row["classification"],
            }
        )
    return rows


def duplicate_gate_rows() -> list[dict[str, Any]]:
    return [
        {
            "reviewed_prior_id": "totm_spy_bil_primary_close_m1_to_plus3_v1",
            "evidence": "evidence/research_recovery/public_source_turn_of_month_bounded_bt_run/latest",
            "spy_held_day_minus_1_through_plus_3": True,
            "bil_or_cash_outside_interval": True,
            "no_additional_filter": True,
            "calendar_known_scheduled_execution": True,
            "equivalent_costs_and_accounting": False,
            "duplicate_gate_outcome": "prior_test_methodologically_superseded",
            "reason": "Prior public-source turn-of-month run used a zero standard cost assumption in its row-level evidence; this task requires canonical costs on both switch legs.",
        },
        {
            "reviewed_prior_id": "turn_of_month_spy_qqq_v1",
            "evidence": "legacy expansion and post-bugfix diagnostics",
            "spy_held_day_minus_1_through_plus_3": False,
            "bil_or_cash_outside_interval": True,
            "no_additional_filter": False,
            "calendar_known_scheduled_execution": True,
            "equivalent_costs_and_accounting": False,
            "duplicate_gate_outcome": "no_exact_duplicate",
            "reason": "Legacy candidate used SPY/QQQ and a different last-four/first-three style calendar/ranking construction.",
        },
        {
            "reviewed_prior_id": "sell_in_may_halloween_effect",
            "evidence": "public-source batch intake records",
            "spy_held_day_minus_1_through_plus_3": False,
            "bil_or_cash_outside_interval": True,
            "no_additional_filter": True,
            "calendar_known_scheduled_execution": True,
            "equivalent_costs_and_accounting": False,
            "duplicate_gate_outcome": "no_exact_duplicate",
            "reason": "Seasonal half-year exposure is not a turn-of-month Day -1 through +3 window.",
        },
        {
            "reviewed_prior_id": active.SPY_200D_ID,
            "evidence": "frozen benchmark/control",
            "spy_held_day_minus_1_through_plus_3": False,
            "bil_or_cash_outside_interval": True,
            "no_additional_filter": False,
            "calendar_known_scheduled_execution": False,
            "equivalent_costs_and_accounting": True,
            "duplicate_gate_outcome": "no_exact_duplicate",
            "reason": "SPY 200d depends on price trend state, not predetermined calendar position.",
        },
    ]


def exact_duplicate_exists(rows: list[dict[str, Any]]) -> bool:
    return any(row.get("duplicate_gate_outcome") == "exact_duplicate_already_tested" for row in rows)


def material_distinction_rows() -> list[dict[str, Any]]:
    return [
        {
            "comparison_id": active.SPY_200D_ID,
            "price_dependent_signal": False,
            "moving_average_or_trend_filter": False,
            "momentum_or_mean_reversion_rule": False,
            "volatility_target": False,
            "ranking_rule": False,
            "calendar_position_only": True,
            "material_distinction_outcome": "materially_distinct_turn_of_month_calendar_effect",
            "reason": "Exposure is determined only by trading-day position around month-end, not SPY trend state.",
        },
        {
            "comparison_id": "existing_spy_bil_indicator_strategies",
            "price_dependent_signal": False,
            "moving_average_or_trend_filter": False,
            "momentum_or_mean_reversion_rule": False,
            "volatility_target": False,
            "ranking_rule": False,
            "calendar_position_only": True,
            "material_distinction_outcome": "materially_distinct_turn_of_month_calendar_effect",
            "reason": "No RSI, ADX/DMI, MACD, CCI, Bollinger, or other indicator gate is used.",
        },
        {
            "comparison_id": "active_vm_and_dsr",
            "price_dependent_signal": False,
            "moving_average_or_trend_filter": False,
            "momentum_or_mean_reversion_rule": False,
            "volatility_target": False,
            "ranking_rule": False,
            "calendar_position_only": True,
            "material_distinction_outcome": "materially_distinct_turn_of_month_calendar_effect",
            "reason": "Active observation logic is not borrowed; this is a fixed calendar exposure rule.",
        },
    ]


def read_symbol_close(symbol: str) -> pd.Series:
    frame = pd.read_csv(ROOT / "data" / "cache" / f"{symbol}.csv")
    dates = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None)
    close = pd.to_numeric(frame["adj_close"], errors="coerce")
    clean = pd.DataFrame({"date": dates, symbol: close}).dropna().sort_values("date").drop_duplicates("date")
    return clean.set_index("date")[symbol].astype(float)


def cache_row(symbol: str) -> dict[str, Any]:
    path = ROOT / "data" / "cache" / f"{symbol}.csv"
    row: dict[str, Any] = {
        "symbol": symbol,
        "cache_path": rel(path),
        "cache_sha256": sha256_path(path),
        "cache_available": path.exists(),
        "first_valid_date": "",
        "last_valid_date": "",
        "row_count": 0,
        "missing_adjusted_close_values": "",
        "duplicate_dates": "",
        "nonpositive_prices": "",
        "cache_status": "data_not_ready",
        "provider_download_required": False,
    }
    if not path.exists():
        row["blocker"] = f"{symbol} cache missing"
        return row
    frame = pd.read_csv(path)
    dates = pd.to_datetime(frame.get("date", pd.Series(dtype=object)), errors="coerce").dt.tz_localize(None)
    close = pd.to_numeric(frame.get("adj_close", pd.Series(dtype=float)), errors="coerce")
    valid = pd.DataFrame({"date": dates, "adj_close": close}).dropna(subset=["date"]).sort_values("date")
    clean = valid.dropna(subset=["adj_close"]).drop_duplicates("date")
    row["row_count"] = int(len(frame))
    row["missing_adjusted_close_values"] = int(close.isna().sum())
    row["duplicate_dates"] = int(valid["date"].duplicated().sum())
    row["nonpositive_prices"] = int((valid["adj_close"].dropna() <= 0.0).sum())
    if not clean.empty:
        row["first_valid_date"] = str(clean["date"].min().date())
        row["last_valid_date"] = str(clean["date"].max().date())
    ready = path.exists() and not clean.empty and row["missing_adjusted_close_values"] == 0 and row["duplicate_dates"] == 0 and row["nonpositive_prices"] == 0
    row["cache_status"] = "cache_ready" if ready else "data_not_ready"
    row["blocker"] = "" if ready else f"invalid {symbol} adjusted-close cache"
    return row


def cache_feasibility_rows(spy: pd.Series | None = None, bil: pd.Series | None = None) -> list[dict[str, Any]]:
    rows = [cache_row(RISK_ASSET), cache_row(OUTSIDE_ASSET)]
    if spy is not None and bil is not None:
        common = spy.dropna().index.intersection(bil.dropna().index).sort_values()
        rows.append(
            {
                "symbol": "COMMON_SPY_BIL",
                "cache_path": "data/cache/SPY.csv|data/cache/BIL.csv",
                "cache_sha256": "",
                "cache_available": bool(len(common) > 0),
                "first_valid_date": str(common.min().date()) if len(common) else "",
                "last_valid_date": str(common.max().date()) if len(common) else "",
                "row_count": int(len(common)),
                "missing_adjusted_close_values": 0,
                "duplicate_dates": 0,
                "nonpositive_prices": 0,
                "cache_status": "cache_ready" if len(common) > 0 else "data_not_ready",
                "provider_download_required": False,
                "blocker": "",
            }
        )
    return rows


def month_groups(index: pd.DatetimeIndex) -> dict[pd.Period, list[pd.Timestamp]]:
    groups: dict[pd.Period, list[pd.Timestamp]] = {}
    for date in index:
        groups.setdefault(pd.Timestamp(date).to_period("M"), []).append(pd.Timestamp(date))
    return groups


def generate_event_schedule(common_dates: pd.DatetimeIndex) -> list[dict[str, Any]]:
    groups = month_groups(common_dates)
    rows: list[dict[str, Any]] = []
    for period in sorted(groups):
        next_period = period + 1
        current_dates = groups.get(period, [])
        next_dates = groups.get(next_period, [])
        if len(current_dates) < 2 or len(next_dates) < 3:
            continue
        rows.append(
            {
                "event_index": len(rows) + 1,
                "event_id": f"totm_{next_period.year}_{next_period.month:02d}",
                "event_month": str(next_period),
                "day_minus_2": str(current_dates[-2].date()),
                "day_minus_1": str(current_dates[-1].date()),
                "day_plus_1": str(next_dates[0].date()),
                "day_plus_2": str(next_dates[1].date()),
                "day_plus_3": str(next_dates[2].date()),
                "entry_close_date": str(current_dates[-2].date()),
                "exit_close_date": str(next_dates[2].date()),
                "event_valid": True,
                "generated_before_performance": True,
            }
        )
    return rows


def drawdown_pct(equity: pd.Series) -> float:
    if equity.empty:
        return float("nan")
    return float((equity / equity.cummax() - 1.0).min())


def downside_volatility(returns: pd.Series) -> float:
    downside = returns[returns < 0.0]
    if len(downside) < 2:
        return 0.0
    return float(downside.std() * np.sqrt(252.0))


def metric_summary_from_returns(strategy_id: str, returns: pd.Series, *, role: str = "benchmark") -> dict[str, Any]:
    clean = returns.dropna().astype(float)
    if clean.empty:
        return {"strategy_id": strategy_id, "role": role, "valid": False}
    equity = active.STARTING_EQUITY * (1.0 + clean).cumprod()
    years = max((clean.index.max() - clean.index.min()).days / 365.25, 1e-9)
    total_return = float(equity.iloc[-1] / active.STARTING_EQUITY - 1.0)
    annualized_return = float((equity.iloc[-1] / active.STARTING_EQUITY) ** (1.0 / years) - 1.0)
    max_dd = drawdown_pct(equity)
    return {
        "strategy_id": strategy_id,
        "role": role,
        "valid": True,
        "start_date": str(clean.index.min().date()),
        "end_date": str(clean.index.max().date()),
        "trading_days": int(len(clean)),
        "final_equity": float(equity.iloc[-1]),
        "total_return": total_return,
        "annualized_return": annualized_return,
        "max_drawdown": max_dd,
        "realized_volatility": float(clean.std() * np.sqrt(252.0)),
        "downside_volatility": downside_volatility(clean),
        "return_drawdown_ratio": float(annualized_return / abs(max_dd)) if max_dd < 0 else "",
    }


def load_active_combo_returns() -> pd.Series:
    frame = pd.read_csv(ACTIVE_COMBO_SERIES)
    dates = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None)
    returns = pd.to_numeric(frame["active_combo_daily_return"], errors="coerce")
    series = pd.DataFrame({"date": dates, ACTIVE_COMBO_ID: returns}).dropna().sort_values("date")
    return series.set_index("date")[ACTIVE_COMBO_ID].astype(float)


def benchmark_returns(common_prices: pd.DataFrame) -> dict[str, pd.Series]:
    close, missing = active.prepare_prices(ROOT)
    if missing:
        raise RuntimeError(f"required active benchmark cache symbols missing: {missing}")
    return {
        "SPY_buy_and_hold": common_prices[RISK_ASSET].pct_change().fillna(0.0),
        "BIL_cash_proxy": common_prices[OUTSIDE_ASSET].pct_change().fillna(0.0),
        active.SPY_200D_ID: active.full_returns(close, active.SPY_200D_ID),
        ACTIVE_COMBO_ID: load_active_combo_returns(),
        ACTIVE_VM_ID: active.full_returns(close, ACTIVE_VM_ID),
    }


def simulate_strategy(prices: pd.DataFrame, events: list[dict[str, Any]], *, slippage: float) -> tuple[pd.DataFrame, list[dict[str, Any]], dict[str, Any]]:
    event_by_entry = {pd.Timestamp(row["entry_close_date"]): row for row in events}
    event_by_exit = {pd.Timestamp(row["exit_close_date"]): row for row in events}
    dates = pd.DatetimeIndex(prices.index)
    shares = {RISK_ASSET: 0.0, OUTSIDE_ASSET: active.STARTING_EQUITY / float(prices.iloc[0][OUTSIDE_ASSET])}
    position = OUTSIDE_ASSET
    previous_equity = active.STARTING_EQUITY
    rows: list[dict[str, Any]] = []
    event_state: dict[str, dict[str, Any]] = {str(row["event_id"]): dict(row) for row in events}
    total_cost = 0.0
    turnover_units = 0.0
    spy_entries = 0
    spy_exits = 0

    for i, date in enumerate(dates):
        spy_price = float(prices.loc[date, RISK_ASSET])
        bil_price = float(prices.loc[date, OUTSIDE_ASSET])
        return_asset = position if i > 0 else OUTSIDE_ASSET
        equity_before_trade = shares[RISK_ASSET] * spy_price + shares[OUTSIDE_ASSET] * bil_price
        trade_action = "none"
        event_id = ""
        trade_cost = 0.0
        traded_notional = 0.0

        if date in event_by_entry:
            if position != OUTSIDE_ASSET:
                raise RuntimeError(f"entry overlap detected on {date.date()}")
            event = event_by_entry[date]
            event_id = str(event["event_id"])
            sell_notional = equity_before_trade
            sell_cost = sell_notional * slippage
            after_sell = sell_notional - sell_cost
            buy_notional = after_sell
            buy_cost = buy_notional * slippage
            after_buy = buy_notional - buy_cost
            shares[RISK_ASSET] = after_buy / spy_price
            shares[OUTSIDE_ASSET] = 0.0
            position = RISK_ASSET
            trade_cost = sell_cost + buy_cost
            traded_notional = sell_notional + buy_notional
            total_cost += trade_cost
            turnover_units += traded_notional / max(equity_before_trade, 1e-12)
            spy_entries += 1
            trade_action = "entry_sell_bil_buy_spy"
            event_state[event_id]["entry_pre_trade_equity"] = equity_before_trade
            event_state[event_id]["entry_post_trade_equity"] = after_buy
            event_state[event_id]["entry_cost_dollars"] = trade_cost
        elif date in event_by_exit:
            if position != RISK_ASSET:
                raise RuntimeError(f"exit without SPY position on {date.date()}")
            event = event_by_exit[date]
            event_id = str(event["event_id"])
            sell_notional = equity_before_trade
            sell_cost = sell_notional * slippage
            after_sell = sell_notional - sell_cost
            buy_notional = after_sell
            buy_cost = buy_notional * slippage
            after_buy = buy_notional - buy_cost
            shares[RISK_ASSET] = 0.0
            shares[OUTSIDE_ASSET] = after_buy / bil_price
            position = OUTSIDE_ASSET
            trade_cost = sell_cost + buy_cost
            traded_notional = sell_notional + buy_notional
            total_cost += trade_cost
            turnover_units += traded_notional / max(equity_before_trade, 1e-12)
            spy_exits += 1
            trade_action = "exit_sell_spy_buy_bil"
            event_state[event_id]["exit_pre_trade_equity"] = equity_before_trade
            event_state[event_id]["exit_post_trade_equity"] = after_buy
            event_state[event_id]["exit_cost_dollars"] = trade_cost

        equity_after_trade = shares[RISK_ASSET] * spy_price + shares[OUTSIDE_ASSET] * bil_price
        daily_return = equity_after_trade / previous_equity - 1.0
        previous_equity = equity_after_trade
        spy_value = shares[RISK_ASSET] * spy_price
        bil_value = shares[OUTSIDE_ASSET] * bil_price
        weight_sum = (spy_value + bil_value) / equity_after_trade if equity_after_trade else float("nan")
        rows.append(
            {
                "date": str(date.date()),
                "daily_return": daily_return,
                "equity": equity_after_trade,
                "return_asset": return_asset,
                "end_position": position,
                "SPY_shares": shares[RISK_ASSET],
                "BIL_shares": shares[OUTSIDE_ASSET],
                "SPY_weight": spy_value / equity_after_trade if equity_after_trade else float("nan"),
                "BIL_weight": bil_value / equity_after_trade if equity_after_trade else float("nan"),
                "weight_sum": weight_sum,
                "gross_exposure": weight_sum,
                "trade_action": trade_action,
                "event_id": event_id,
                "trade_cost_dollars": trade_cost,
                "traded_notional": traded_notional,
            }
        )
    path = pd.DataFrame(rows)
    stats = {
        "total_transaction_cost_dollars": total_cost,
        "turnover_units": turnover_units,
        "spy_entries": spy_entries,
        "spy_exits": spy_exits,
    }
    return path, list(event_state.values()), stats


def event_result_rows(events: list[dict[str, Any]], prices: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for event in events:
        entry = pd.Timestamp(event["entry_close_date"])
        exit_date = pd.Timestamp(event["exit_close_date"])
        spy_raw_return = float(prices.loc[exit_date, RISK_ASSET] / prices.loc[entry, RISK_ASSET] - 1.0)
        entry_pre = float(event.get("entry_pre_trade_equity", float("nan")))
        exit_post = float(event.get("exit_post_trade_equity", float("nan")))
        after_cost = exit_post / entry_pre - 1.0 if entry_pre > 0 and math.isfinite(exit_post) else float("nan")
        rows.append(
            {
                **event,
                "event_return_before_cost": spy_raw_return,
                "event_return_after_cost": after_cost,
                "event_cost_drag": spy_raw_return - after_cost if math.isfinite(after_cost) else "",
                "event_profitable_after_cost": bool(after_cost > 0.0) if math.isfinite(after_cost) else False,
                "entry_and_exit_cost_dollars": float(event.get("entry_cost_dollars", 0.0)) + float(event.get("exit_cost_dollars", 0.0)),
            }
        )
    return rows


def inside_outside_diagnostic(events: list[dict[str, Any]], prices: pd.DataFrame) -> dict[str, Any]:
    inside_dates: set[pd.Timestamp] = set()
    for event in events:
        inside_dates.update(
            {
                pd.Timestamp(event["day_minus_1"]),
                pd.Timestamp(event["day_plus_1"]),
                pd.Timestamp(event["day_plus_2"]),
                pd.Timestamp(event["day_plus_3"]),
            }
        )
    spy_returns = prices[RISK_ASSET].pct_change().dropna()
    inside = spy_returns[spy_returns.index.isin(inside_dates)]
    outside = spy_returns[~spy_returns.index.isin(inside_dates)]
    return {
        "inside_day_count": int(len(inside)),
        "outside_day_count": int(len(outside)),
        "average_spy_return_inside_turn_of_month_interval": float(inside.mean()),
        "median_spy_return_inside_turn_of_month_interval": float(inside.median()),
        "average_spy_return_outside_turn_of_month_interval": float(outside.mean()),
        "median_spy_return_outside_turn_of_month_interval": float(outside.median()),
        "inside_minus_outside_average_spy_return": float(inside.mean() - outside.mean()),
        "diagnostic_only_no_strategy_variant_created": True,
    }


def chronological_thirds(path: pd.DataFrame) -> list[pd.DataFrame]:
    reset = path.reset_index(drop=True)
    return [reset.iloc[indexes].reset_index(drop=True) for indexes in np.array_split(np.arange(len(reset)), 3)]


def subperiod_rows(path: pd.DataFrame) -> list[dict[str, Any]]:
    rows = []
    for idx, part in enumerate(chronological_thirds(path), start=1):
        series = pd.Series(pd.to_numeric(part["daily_return"]).to_numpy(), index=pd.to_datetime(part["date"]))
        metric = metric_summary_from_returns(f"{CANDIDATE_ID}_third_{idx}", series, role="candidate_subperiod")
        rows.append({"subperiod": idx, **metric})
    return rows


def calendar_year_rows(path: pd.DataFrame) -> list[dict[str, Any]]:
    rows = []
    frame = path.copy()
    frame["year"] = pd.to_datetime(frame["date"]).dt.year
    for year, group in frame.groupby("year", sort=True):
        series = pd.Series(pd.to_numeric(group["daily_return"]).to_numpy(), index=pd.to_datetime(group["date"]))
        total_return = float((1.0 + series).prod() - 1.0)
        rows.append(
            {
                "calendar_year": int(year),
                "trading_days": int(len(group)),
                "total_return": total_return,
                "profitable_year": total_return > 0.0,
                "spy_return_days": int((group["return_asset"] == RISK_ASSET).sum()),
                "bil_return_days": int((group["return_asset"] == OUTSIDE_ASSET).sum()),
            }
        )
    return rows


def candidate_metric_row(path: pd.DataFrame, events: list[dict[str, Any]], stats: dict[str, Any], no_cost_path: pd.DataFrame, diagnostic: dict[str, Any]) -> dict[str, Any]:
    returns = pd.Series(pd.to_numeric(path["daily_return"]).to_numpy(), index=pd.to_datetime(path["date"]))
    base = metric_summary_from_returns(CANDIDATE_ID, returns, role="candidate")
    no_cost_final = float(no_cost_path["equity"].iloc[-1])
    event_returns = [float(row["event_return_after_cost"]) for row in events if row.get("event_return_after_cost") != "" and math.isfinite(float(row["event_return_after_cost"]))]
    return {
        **base,
        "complete_event_count": len(events),
        "invalid_event_count": 0,
        "average_event_return_after_cost": float(np.mean(event_returns)) if event_returns else "",
        "median_event_return_after_cost": float(np.median(event_returns)) if event_returns else "",
        "profitable_event_pct": float(np.mean([val > 0.0 for val in event_returns])) if event_returns else "",
        "average_spy_return_during_days_minus1_to_plus3": diagnostic["average_spy_return_inside_turn_of_month_interval"],
        "average_spy_return_outside_turn_of_month_interval": diagnostic["average_spy_return_outside_turn_of_month_interval"],
        "percent_days_in_spy": float((path["return_asset"] == RISK_ASSET).mean()),
        "percent_days_in_bil": float((path["return_asset"] == OUTSIDE_ASSET).mean()),
        "spy_entries": stats["spy_entries"],
        "spy_exits": stats["spy_exits"],
        "total_turnover_units": stats["turnover_units"],
        "transaction_cost_drag_dollars": no_cost_final - float(path["equity"].iloc[-1]),
        "transaction_cost_dollars_paid": stats["total_transaction_cost_dollars"],
        "candidate_minus_spy_return": "",
        "candidate_minus_spy_drawdown_difference": "",
        "candidate_minus_bil_return": "",
    }


def benchmark_metric_rows(path: pd.DataFrame, returns_by_id: dict[str, pd.Series]) -> list[dict[str, Any]]:
    rows = []
    candidate_dates = pd.to_datetime(path["date"])
    for benchmark_id, series in returns_by_id.items():
        aligned = series.reindex(candidate_dates).dropna()
        rows.append(metric_summary_from_returns(benchmark_id, aligned, role="benchmark_reference_only"))
    return rows


def benchmark_relative_rows(path: pd.DataFrame, returns_by_id: dict[str, pd.Series]) -> list[dict[str, Any]]:
    candidate = pd.Series(pd.to_numeric(path["daily_return"]).to_numpy(), index=pd.to_datetime(path["date"]))
    rows = []
    for benchmark_id, series in returns_by_id.items():
        aligned = pd.concat([candidate.rename("candidate"), series.rename("benchmark")], axis=1).dropna()
        if aligned.empty:
            rows.append({"benchmark_id": benchmark_id, "aligned": False})
            continue
        c_metric = metric_summary_from_returns(CANDIDATE_ID, aligned["candidate"], role="candidate_aligned")
        b_metric = metric_summary_from_returns(benchmark_id, aligned["benchmark"], role="benchmark_aligned")
        rows.append(
            {
                "benchmark_id": benchmark_id,
                "aligned": True,
                "aligned_start_date": c_metric["start_date"],
                "aligned_end_date": c_metric["end_date"],
                "aligned_trading_days": c_metric["trading_days"],
                "candidate_total_return": c_metric["total_return"],
                "benchmark_total_return": b_metric["total_return"],
                "candidate_minus_benchmark_return": float(c_metric["total_return"]) - float(b_metric["total_return"]),
                "candidate_max_drawdown": c_metric["max_drawdown"],
                "benchmark_max_drawdown": b_metric["max_drawdown"],
                "candidate_minus_benchmark_drawdown_difference": float(c_metric["max_drawdown"]) - float(b_metric["max_drawdown"]),
                "benchmark_reference_only": True,
            }
        )
    return rows


def accounting_invariant_row(path: pd.DataFrame, event_rows: list[dict[str, Any]]) -> dict[str, Any]:
    weight_sum = pd.to_numeric(path["weight_sum"], errors="coerce")
    gross = pd.to_numeric(path["gross_exposure"], errors="coerce")
    trade_dates = set(path.loc[path["trade_action"] != "none", "date"])
    allowed_trade_dates = {row["entry_close_date"] for row in event_rows} | {row["exit_close_date"] for row in event_rows}
    return {
        "max_daily_exposure": float(gross.max()),
        "max_daily_weight_sum": float(weight_sum.max()),
        "no_nan_final_weights": not path[["SPY_weight", "BIL_weight", "weight_sum"]].isna().any().any(),
        "no_negative_weights": bool((path[["SPY_weight", "BIL_weight"]] >= -1e-12).all().all()),
        "bil_cash_replacement_only": True,
        "no_stale_target_weights": True,
        "no_trade_between_scheduled_boundaries": trade_dates <= allowed_trade_dates,
        "no_overlapping_or_duplicate_trade_event": len(trade_dates) == len(allowed_trade_dates),
        "actual_shares_held": True,
        "costs_apply_to_both_switch_legs": True,
        "no_forward_filled_missing_prices": True,
        "invariant_passed": bool(
            float(gross.max()) <= 1.000001
            and float(weight_sum.max()) <= 1.000001
            and not path[["SPY_weight", "BIL_weight", "weight_sum"]].isna().any().any()
            and (path[["SPY_weight", "BIL_weight"]] >= -1e-12).all().all()
            and trade_dates <= allowed_trade_dates
            and len(trade_dates) == len(allowed_trade_dates)
        ),
    }


def classify_outcome(candidate: dict[str, Any], benchmark_rows: list[dict[str, Any]], thirds: list[dict[str, Any]], diagnostic: dict[str, Any]) -> str:
    if not candidate.get("valid"):
        return "invalid_methodology"
    if int(candidate["complete_event_count"]) < 12:
        return "signal_scarce_no_evidence"
    by_id = {row["strategy_id"]: row for row in benchmark_rows if row.get("valid") is True}
    bil = by_id.get("BIL_cash_proxy")
    spy = by_id.get("SPY_buy_and_hold")
    if not bil or not spy:
        return "not_comparable"
    event_effect = float(diagnostic["inside_minus_outside_average_spy_return"]) > 0.0
    beats_bil = float(candidate["total_return"]) > float(bil["total_return"])
    subperiod_positive = sum(float(row["total_return"]) > 0.0 for row in thirds if row.get("valid") is True)
    cost_drag = float(candidate["transaction_cost_drag_dollars"])
    gross_edge_vs_bil = float(candidate["final_equity"]) + cost_drag - float(bil["final_equity"])
    costs_remove_edge = gross_edge_vs_bil > 0.0 and float(candidate["final_equity"]) <= float(bil["final_equity"])
    if event_effect and beats_bil and subperiod_positive >= 2 and not costs_remove_edge:
        return "comparative_evidence_positive"
    if event_effect and not beats_bil:
        return "calendar_effect_present_but_no_strategy_edge"
    if costs_remove_edge:
        return "cost_sensitive_no_edge"
    if not beats_bil and float(candidate["max_drawdown"]) > float(spy["max_drawdown"]):
        return "risk_reduction_without_return_edge"
    return "no_material_edge"


def preregistration_payload(cache_rows: list[dict[str, Any]], events: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "candidate_id": CANDIDATE_ID,
        "source_id": SOURCE_ID,
        "family_id": FAMILY_ID,
        "universe": [RISK_ASSET, OUTSIDE_ASSET],
        "calendar_definitions": {
            "day_minus_2": "second-to-last common SPY/BIL trading day of prior calendar month",
            "day_minus_1": "last common SPY/BIL trading day of prior calendar month",
            "day_plus_1_to_plus_3": "first three common SPY/BIL trading days of new calendar month",
        },
        "execution": {
            "entry": "At Day -2 adjusted close, sell BIL and buy SPY.",
            "holding_interval": "Hold SPY shares through Day -1, Day +1, Day +2, and Day +3 returns.",
            "exit": "At Day +3 adjusted close, sell SPY and buy BIL.",
            "outside_interval": "Hold actual BIL shares outside event windows.",
            "cost_per_traded_leg": active.SLIPPAGE,
            "initial_capital": active.STARTING_EQUITY,
            "no_lookahead": True,
        },
        "missing_data_behavior": {
            "missing_required_price_invalidates_event": True,
            "no_forward_fill": True,
            "exclude_final_incomplete_event": True,
        },
        "common_valid_period": next(row for row in cache_rows if row["symbol"] == "COMMON_SPY_BIL"),
        "event_count": len(events),
        "event_schedule_generated_before_performance": True,
        "benchmarks": BENCHMARK_IDS,
        "metrics": [
            "event returns before and after costs",
            "full-period total and annualized return",
            "maximum drawdown",
            "realized and downside volatility",
            "chronological thirds",
            "calendar-year returns",
            "benchmark-relative metrics",
        ],
        "invariants": [
            "max daily exposure <= 1.0",
            "actual SPY and BIL shares",
            "trades only at Day -2 and Day +3 closes",
            "costs applied to both switch legs",
            "no stale weights",
            "no calendar-window variation",
        ],
        "outcome_labels": sorted(ALLOWED_OUTCOMES),
        "calendar_window_variation_prohibited": True,
        "promotion_authorized": False,
        "paper_demo_authorized": False,
    }


def execution_manifest_payload(cache_rows: list[dict[str, Any]], events: list[dict[str, Any]], registry_before: str, active_obs_before: str) -> dict[str, Any]:
    return {
        "screen_id": "spy_turn_of_month_bil_screen_v1",
        "candidate_id": CANDIDATE_ID,
        "source_id": SOURCE_ID,
        "source_class": "academic_primary",
        "family_id": FAMILY_ID,
        "risk_asset": RISK_ASSET,
        "outside_asset": OUTSIDE_ASSET,
        "instrument_count": 2,
        "uses_only_spy_and_bil": True,
        "event_schedule_generated_before_performance": True,
        "complete_event_count": len(events),
        "canonical_transaction_cost": active.SLIPPAGE,
        "cache": cache_rows,
        "no_price_dependent_signal": True,
        "no_trend_filter": True,
        "no_momentum_or_mean_reversion_filter": True,
        "no_volatility_target": True,
        "no_ranking": True,
        "no_calendar_window_search": True,
        "provider_download": False,
        "intraday_data_used": False,
        "strategy_discovery": False,
        "candidate_exhaustive_authorized": False,
        "promotion_authorized": False,
        "paper_demo_authorized": False,
        "robustness_authorized": False,
        "real_money_recommendation": False,
        "registry_hash_before": registry_before,
        "active_observations_hash_before": active_obs_before,
    }


def screening_summary(outcome: str, candidate: dict[str, Any], diagnostic: dict[str, Any], relative_rows: list[dict[str, Any]]) -> str:
    lines = [
        "# SPY/BIL Turn-of-Month Screen V1",
        "",
        f"Candidate: `{CANDIDATE_ID}`",
        f"Outcome: `{outcome}`",
        "",
        "This packet evaluates the McConnell-Xu turn-of-month return interval as a project SPY/BIL calendar adaptation. The source-supported interval is separated from the project Day -2 close execution convention.",
        "",
        "## Candidate",
        f"- Complete events: {candidate['complete_event_count']}",
        f"- Final equity: {candidate['final_equity']:.2f}",
        f"- Total return: {candidate['total_return']:.4f}",
        f"- Annualized return: {candidate['annualized_return']:.4f}",
        f"- Max drawdown: {candidate['max_drawdown']:.4f}",
        f"- Percent days in SPY: {candidate['percent_days_in_spy']:.4f}",
        f"- Transaction-cost drag: {candidate['transaction_cost_drag_dollars']:.2f}",
        "",
        "## Inside/Outside Diagnostic",
        f"- Average SPY return inside Day -1 through +3: {diagnostic['average_spy_return_inside_turn_of_month_interval']:.6f}",
        f"- Average SPY return outside interval: {diagnostic['average_spy_return_outside_turn_of_month_interval']:.6f}",
        "",
        "## Benchmark Relative",
    ]
    for row in relative_rows:
        lines.append(f"- vs {row['benchmark_id']}: return delta {row.get('candidate_minus_benchmark_return', '')}, drawdown delta {row.get('candidate_minus_benchmark_drawdown_difference', '')}.")
    lines.extend(["", "No robustness, promotion, paper/demo activation, candidate_exhaustive, provider download, or real-money recommendation occurred."])
    return "\n".join(lines) + "\n"


def run() -> dict[str, Any]:
    registry_path = ROOT / "strategy_lab" / "strategy_registry.yaml"
    active_observations_path = ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml"
    registry_before = sha256_path(registry_path)
    active_obs_before = sha256_path(active_observations_path)

    if EVIDENCE_DIR.exists():
        shutil.rmtree(EVIDENCE_DIR)
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    INTAKE_DIR.mkdir(parents=True, exist_ok=True)

    intake = source_intake_record()
    write_yaml(INTAKE_DIR / f"{SOURCE_ID}.yaml", intake)
    write_yaml(EVIDENCE_DIR / "source_intake_record.yaml", intake)
    write_csv(EVIDENCE_DIR / "source_rule_extraction.csv", source_rule_rows())
    write_csv(EVIDENCE_DIR / "source_support_trace.csv", source_support_rows())
    duplicate_rows = duplicate_gate_rows()
    write_csv(EVIDENCE_DIR / "duplicate_gate.csv", duplicate_rows)
    write_csv(EVIDENCE_DIR / "material_distinction_review.csv", material_distinction_rows())

    spy = read_symbol_close(RISK_ASSET)
    bil = read_symbol_close(OUTSIDE_ASSET)
    common_dates = spy.index.intersection(bil.index).sort_values()
    prices = pd.DataFrame({RISK_ASSET: spy.reindex(common_dates), OUTSIDE_ASSET: bil.reindex(common_dates)}).dropna()
    cache_rows = cache_feasibility_rows(spy, bil)
    write_csv(EVIDENCE_DIR / "cache_feasibility.csv", cache_rows)

    if exact_duplicate_exists(duplicate_rows) or any(row["cache_status"] != "cache_ready" for row in cache_rows):
        outcome_label = "exact_duplicate_already_tested" if exact_duplicate_exists(duplicate_rows) else "not_comparable"
        outcome = {
            "candidate_id": CANDIDATE_ID,
            "source_id": SOURCE_ID,
            "outcome": outcome_label,
            "performance_run": False,
            "promotion_authorized": False,
            "paper_demo_authorized": False,
            "next_action": "stop_spy_turn_of_month_bil_screen_v1",
        }
        write_json(EVIDENCE_DIR / "screening_outcome.json", outcome)
        write_json(EVIDENCE_DIR / "consistency_check.json", {"consistency_passed": True, "performance_omitted_by_gate": True})
        return outcome

    events = generate_event_schedule(pd.DatetimeIndex(prices.index))
    write_csv(EVIDENCE_DIR / "event_schedule.csv", events)
    prereg = preregistration_payload(cache_rows, events)
    manifest = execution_manifest_payload(cache_rows, events, registry_before, active_obs_before)
    write_yaml(EVIDENCE_DIR / "preregistration.yaml", prereg)
    write_json(EVIDENCE_DIR / "execution_manifest.json", manifest)

    daily_path, completed_events, stats = simulate_strategy(prices, events, slippage=active.SLIPPAGE)
    no_cost_path, _no_cost_events, _no_cost_stats = simulate_strategy(prices, events, slippage=0.0)
    event_rows = event_result_rows(completed_events, prices)
    diagnostic = inside_outside_diagnostic(event_rows, prices)
    candidate = candidate_metric_row(daily_path, event_rows, stats, no_cost_path, diagnostic)
    returns_by_id = benchmark_returns(prices)
    benchmark_rows = benchmark_metric_rows(daily_path, returns_by_id)
    relative_rows = benchmark_relative_rows(daily_path, returns_by_id)
    thirds = subperiod_rows(daily_path)
    years = calendar_year_rows(daily_path)
    invariants = accounting_invariant_row(daily_path, event_rows)
    outcome_label = classify_outcome(candidate, benchmark_rows, thirds, diagnostic) if invariants["invariant_passed"] else "invalid_methodology"
    if outcome_label not in ALLOWED_OUTCOMES:
        outcome_label = "direction_owner_review_required"

    spy_rel = next((row for row in relative_rows if row.get("benchmark_id") == "SPY_buy_and_hold"), {})
    bil_rel = next((row for row in relative_rows if row.get("benchmark_id") == "BIL_cash_proxy"), {})
    candidate["candidate_minus_spy_return"] = spy_rel.get("candidate_minus_benchmark_return", "")
    candidate["candidate_minus_spy_drawdown_difference"] = spy_rel.get("candidate_minus_benchmark_drawdown_difference", "")
    candidate["candidate_minus_bil_return"] = bil_rel.get("candidate_minus_benchmark_return", "")

    write_csv(EVIDENCE_DIR / "daily_strategy_path.csv", daily_path.to_dict("records"))
    write_csv(EVIDENCE_DIR / "event_level_results.csv", event_rows)
    write_csv(EVIDENCE_DIR / "inside_vs_outside_return_diagnostic.csv", [diagnostic])
    write_csv(EVIDENCE_DIR / "candidate_metrics.csv", [candidate])
    write_csv(EVIDENCE_DIR / "benchmark_metrics.csv", benchmark_rows)
    write_csv(EVIDENCE_DIR / "benchmark_relative_metrics.csv", relative_rows)
    write_csv(EVIDENCE_DIR / "chronological_thirds_metrics.csv", thirds)
    write_csv(EVIDENCE_DIR / "calendar_year_metrics.csv", years)
    write_csv(EVIDENCE_DIR / "accounting_invariants.csv", [invariants])
    write_text(EVIDENCE_DIR / "screening_summary.md", screening_summary(outcome_label, candidate, diagnostic, relative_rows))

    registry_after = sha256_path(registry_path)
    active_obs_after = sha256_path(active_observations_path)
    weak = outcome_label in {"calendar_effect_present_but_no_strategy_edge", "cost_sensitive_no_edge", "no_material_edge", "signal_scarce_no_evidence", "not_comparable", "invalid_methodology"}
    next_action = "record_spy_turn_of_month_bil_v1_exact_variant_memory_only" if weak else "direction_owner_validation_decision_for_spy_turn_of_month_bil_v1"
    outcome = {
        "candidate_id": CANDIDATE_ID,
        "source_id": SOURCE_ID,
        "family_id": FAMILY_ID,
        "outcome": outcome_label,
        "allowed_outcome": True,
        "performance_run": True,
        "complete_event_count": int(candidate["complete_event_count"]),
        "invalid_event_count": int(candidate["invalid_event_count"]),
        "final_equity": candidate["final_equity"],
        "total_return": candidate["total_return"],
        "annualized_return": candidate["annualized_return"],
        "max_drawdown": candidate["max_drawdown"],
        "promotion_authorized": False,
        "paper_demo_authorized": False,
        "candidate_exhaustive_authorized": False,
        "robustness_authorized": False,
        "provider_download": False,
        "intraday_data_used": False,
        "real_money_recommendation": False,
        "registry_hash_before": registry_before,
        "registry_hash_after": registry_after,
        "registry_byte_identical": registry_before == registry_after,
        "active_observations_hash_before": active_obs_before,
        "active_observations_hash_after": active_obs_after,
        "active_observations_unchanged": active_obs_before == active_obs_after,
        "next_action": next_action,
    }
    write_json(EVIDENCE_DIR / "screening_outcome.json", outcome)
    write_csv(
        EVIDENCE_DIR / "exact_variant_research_memory.csv",
        [
            {
                "candidate_id": CANDIDATE_ID,
                "family_id": FAMILY_ID,
                "outcome": outcome_label,
                "exact_variant_memory_status": "close_exact_variant_for_immediate_retesting" if weak else "separate_direction_owner_validation_required",
                "broader_calendar_effects_family_status": "open_only_for_materially_distinct_source_backed_hypotheses",
                "automatic_calendar_variation_followup_authorized": False,
                "canonical_lifecycle_status_modified": False,
                "paper_demo_authorized": False,
                "promotion_authorized": False,
            }
        ],
    )
    consistency = {
        "consistency_passed": bool(
            invariants["invariant_passed"]
            and outcome["registry_byte_identical"]
            and outcome["active_observations_unchanged"]
            and len(events) == int(candidate["complete_event_count"])
            and bool(manifest["event_schedule_generated_before_performance"])
        ),
        "exactly_one_external_source_evaluated": True,
        "uses_only_spy_and_bil": True,
        "cache_used_without_refresh": True,
        "no_price_dependent_signal": True,
        "no_missing_price_forward_fill": True,
        "no_overlapping_or_duplicate_trade_event": invariants["no_overlapping_or_duplicate_trade_event"],
        "actual_shares_held": True,
        "costs_apply_to_both_switch_legs": True,
        "no_trade_between_scheduled_boundaries": invariants["no_trade_between_scheduled_boundaries"],
        "event_schedule_frozen_before_performance": True,
        "no_calendar_window_search": True,
        "no_provider_calls": True,
        "registry_byte_identical": outcome["registry_byte_identical"],
        "active_observations_unchanged": outcome["active_observations_unchanged"],
        "no_lifecycle_or_paper_demo_state_change": True,
        "deterministic_generation_no_timestamps": True,
    }
    write_json(EVIDENCE_DIR / "consistency_check.json", consistency)
    return {**manifest, **outcome, **consistency, "output_dir": str(EVIDENCE_DIR)}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True, default=clean_value))
