from __future__ import annotations

import importlib
import importlib.metadata
import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research.profit_oriented_research_batch_v1 import (
    complete_rebalance_weight_frame,
    load_prices,
    month_rebalance_mask,
    weight_invariant_report,
)


BT_MODULE_NAME = "bt"
DEFAULT_SPEC_ID = "bt_adapter_spy200d_bil_control_poc_v1"
WEIGHT_TOLERANCE = 1e-6


class BtDependencyUnavailable(RuntimeError):
    """Raised when the optional bt package is required but unavailable."""


@dataclass(frozen=True)
class BtAdapterSpec:
    spec_id: str = DEFAULT_SPEC_ID
    control_concept: str = "spy200d_bil_control"
    symbols: tuple[str, ...] = ("SPY", "BIL")
    rebalance_frequency: str = "monthly"
    signal_rule: str = "SPY prior close above prior 200-day SMA selects SPY, otherwise BIL"
    signal_timing: str = "use information through t-1 at monthly rebalance"
    cash_symbol: str = "BIL"
    max_daily_exposure: float = 1.0
    max_daily_weight_sum: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "spec_id": self.spec_id,
            "control_concept": self.control_concept,
            "symbols": "|".join(self.symbols),
            "rebalance_frequency": self.rebalance_frequency,
            "signal_rule": self.signal_rule,
            "signal_timing": self.signal_timing,
            "cash_symbol": self.cash_symbol,
            "max_daily_exposure": self.max_daily_exposure,
            "max_daily_weight_sum": self.max_daily_weight_sum,
            "strategy_performance_evidence": False,
        }


def bt_available() -> bool:
    return importlib.util.find_spec(BT_MODULE_NAME) is not None


def bt_version() -> str:
    if not bt_available():
        return "not_available"
    try:
        return importlib.metadata.version(BT_MODULE_NAME)
    except importlib.metadata.PackageNotFoundError:
        module = importlib.import_module(BT_MODULE_NAME)
        return str(getattr(module, "__version__", "unknown"))


def dependency_report() -> dict[str, Any]:
    return {
        "package": "bt",
        "module_name": BT_MODULE_NAME,
        "available_in_current_venv": bt_available(),
        "version": bt_version(),
        "install_attempted": False,
        "dependency_file_modified": False,
        "dependency_convention": "plain requirements.txt only; no optional dependency convention detected",
        "minimal_install_command": ".venv\\Scripts\\python.exe -m pip install bt",
    }


def load_local_price_frame(root: Path = ROOT, spec: BtAdapterSpec | None = None) -> pd.DataFrame:
    spec = spec or BtAdapterSpec()
    prices = load_prices(root, spec.symbols).sort_index()
    if prices.empty:
        return pd.DataFrame()
    return prices.loc[prices[list(spec.symbols)].notna().all(axis=1), list(spec.symbols)].copy()


def reference_spy200d_weights(prices: pd.DataFrame, spec: BtAdapterSpec | None = None) -> pd.DataFrame:
    spec = spec or BtAdapterSpec()
    columns = list(spec.symbols)
    if prices.empty or "SPY" not in prices.columns or spec.cash_symbol not in prices.columns:
        return pd.DataFrame()
    prior_spy = prices["SPY"].shift(1)
    prior_sma = prices["SPY"].shift(1).rolling(200, min_periods=200).mean()
    risk_on = prior_spy > prior_sma
    targets: dict[pd.Timestamp, dict[str, float]] = {}
    for date in prices.index[month_rebalance_mask(prices.index)]:
        target = {symbol: 0.0 for symbol in columns}
        if bool(risk_on.loc[date]):
            target["SPY"] = 1.0
        else:
            target[spec.cash_symbol] = 1.0
        targets[pd.Timestamp(date)] = target
    return complete_rebalance_weight_frame(prices.index, columns, targets, tolerance=WEIGHT_TOLERANCE)


def returns_from_weights(prices: pd.DataFrame, weights: pd.DataFrame) -> pd.Series:
    returns = prices.pct_change(fill_method=None).fillna(0.0)
    aligned = weights.reindex(prices.index).ffill().fillna(0.0).reindex(columns=prices.columns, fill_value=0.0)
    return (aligned.shift(1).fillna(0.0) * returns).sum(axis=1)


def equity_from_returns(daily_returns: pd.Series) -> pd.Series:
    if daily_returns.empty:
        return pd.Series(dtype=float, name="equity")
    return (1.0 + daily_returns.fillna(0.0)).cumprod().rename("equity")


def turnover_from_weights(weights: pd.DataFrame) -> pd.DataFrame:
    if weights.empty:
        return pd.DataFrame(columns=["date", "turnover_proxy"])
    diff = weights.diff().abs().fillna(weights.abs())
    turnover = diff.sum(axis=1) / 2.0
    out = pd.DataFrame({"date": weights.index, "turnover_proxy": turnover.to_numpy()})
    return out.loc[out["turnover_proxy"] > WEIGHT_TOLERANCE].reset_index(drop=True)


def weights_to_rows(weights: pd.DataFrame) -> list[dict[str, Any]]:
    if weights.empty:
        return []
    rows: list[dict[str, Any]] = []
    for date, row in weights.iterrows():
        payload = {"date": pd.Timestamp(date).date().isoformat()}
        for symbol, value in row.items():
            payload[symbol] = float(value)
        payload["weight_sum"] = float(row.sum())
        payload["risky_exposure"] = float(row.drop(labels=["BIL"], errors="ignore").sum())
        rows.append(payload)
    return rows


def equity_to_rows(daily_returns: pd.Series, equity: pd.Series) -> list[dict[str, Any]]:
    if daily_returns.empty or equity.empty:
        return []
    aligned = pd.concat([daily_returns.rename("daily_return"), equity.rename("equity")], axis=1).dropna()
    return [
        {
            "date": pd.Timestamp(date).date().isoformat(),
            "daily_return": float(row["daily_return"]),
            "equity": float(row["equity"]),
        }
        for date, row in aligned.iterrows()
    ]


def invariant_summary(weights: pd.DataFrame) -> dict[str, Any]:
    report = weight_invariant_report(weights, tolerance=WEIGHT_TOLERANCE)
    passed = (
        not weights.empty
        and report["max_daily_exposure"] <= 1.000001
        and report["max_daily_weight_sum"] <= 1.000001
        and int(report["weight_sum_violation_count"]) == 0
        and int(report["negative_weight_violation_count"]) == 0
        and int(report["nan_weight_count"]) == 0
        and int(report["impossible_cash_and_risky_exposure_days"]) == 0
    )
    return {**report, "exposure_invariant_passed": passed}


def run_bt_spy200d_control(prices: pd.DataFrame, spec: BtAdapterSpec | None = None) -> dict[str, Any]:
    spec = spec or BtAdapterSpec()
    if not bt_available():
        raise BtDependencyUnavailable("optional dependency `bt` is not installed")
    bt = importlib.import_module(BT_MODULE_NAME)
    columns = list(spec.symbols)
    recorded_targets: dict[pd.Timestamp, dict[str, float]] = {}

    class TargetWeightRecorder(bt.Algo):
        def __call__(self, target: Any) -> bool:
            raw_weights = target.temp.get("weights", {})
            recorded_targets[pd.Timestamp(target.now)] = {
                symbol: float(raw_weights.get(symbol, 0.0)) for symbol in columns
            }
            return True

    signal = pd.DataFrame(False, index=prices.index, columns=list(spec.symbols))
    prior_spy = prices["SPY"].shift(1)
    prior_sma = prices["SPY"].shift(1).rolling(200, min_periods=200).mean()
    risk_on = prior_spy > prior_sma
    signal.loc[risk_on.fillna(False), "SPY"] = True
    signal.loc[~risk_on.fillna(False), spec.cash_symbol] = True
    target_recorder = TargetWeightRecorder()

    strategy = bt.Strategy(
        spec.spec_id,
        [
            bt.algos.RunMonthly(),
            bt.algos.SelectWhere(signal),
            bt.algos.WeighEqually(),
            target_recorder,
            bt.algos.Rebalance(),
        ],
    )
    backtest = bt.Backtest(strategy, prices)
    result = bt.run(backtest)

    # bt's security/account weights can drift after market moves. The adapter
    # contract is daily target weights, so record temp["weights"] at rebalance
    # dates and expand them through the existing project invariant-safe helper.
    bt_security_weights = pd.DataFrame()
    for accessor in ("get_security_weights", "get_weights"):
        candidate = getattr(result, accessor, None)
        if callable(candidate):
            maybe = candidate()
            if isinstance(maybe, pd.DataFrame) and not maybe.empty:
                bt_security_weights = maybe.reindex(prices.index).ffill().fillna(0.0)
                break
    bt_target_weights = complete_rebalance_weight_frame(
        prices.index,
        columns,
        recorded_targets,
        tolerance=WEIGHT_TOLERANCE,
    )
    reference_weights = reference_spy200d_weights(prices, spec)
    project_returns = returns_from_weights(prices, reference_weights).rename("project_reference_return")
    project_equity = equity_from_returns(project_returns)
    return {
        "bt_result_type": type(result).__name__,
        "bt_weights": bt_target_weights,
        "bt_security_weights": bt_security_weights,
        "project_reference_weights": reference_weights,
        "project_reference_returns": project_returns,
        "project_reference_equity": project_equity,
        "bt_weights_exported": not bt_target_weights.empty,
        "bt_security_weights_exported": not bt_security_weights.empty,
    }


def compare_weights(left: pd.DataFrame, right: pd.DataFrame) -> dict[str, Any]:
    if left.empty or right.empty:
        return {
            "comparison_performed": False,
            "max_abs_weight_difference": float("nan"),
            "row_count_compared": 0,
            "comparison_status": "not_performed_missing_weight_export",
        }
    common = left.reindex(right.index).fillna(0.0).reindex(columns=right.columns, fill_value=0.0)
    diff = (common - right).abs()
    max_diff = float(diff.max().max()) if not diff.empty else float("nan")
    return {
        "comparison_performed": True,
        "max_abs_weight_difference": max_diff,
        "row_count_compared": int(len(diff)),
        "comparison_status": "matched" if np.isfinite(max_diff) and max_diff <= 1e-9 else "mismatch",
    }
