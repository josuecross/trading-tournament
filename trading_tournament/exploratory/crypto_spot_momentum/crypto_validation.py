from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from exploratory.crypto_spot_momentum.crypto_data import CryptoDataError, load_crypto_data
from exploratory.crypto_spot_momentum.crypto_metrics import compute_strategy_metrics, summarize_rolling_windows
from exploratory.crypto_spot_momentum.crypto_reporting import new_run_id, write_evidence_packet
from exploratory.crypto_spot_momentum.crypto_strategies import generate_signal_weights, price_matrix, simulate_strategy


BENCHMARK_CONFIGS: dict[str, dict[str, Any]] = {
    "BTC_buy_hold": {"role": "benchmark"},
    "ETH_buy_hold": {"role": "benchmark"},
    "cash_flat": {"role": "benchmark"},
}


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def slippage_value(config: dict[str, Any], label: str) -> float:
    if label == "standard":
        return float(config["costs"]["standard_fee_slippage_per_side"])
    if label == "stress":
        return float(config["costs"]["stress_fee_slippage_per_side"])
    raise ValueError(f"Unknown slippage label: {label}")


def strategy_config(config: dict[str, Any], strategy: str) -> dict[str, Any]:
    return config.get("strategies", {}).get(strategy) or BENCHMARK_CONFIGS.get(strategy, {})


def all_strategy_names(config: dict[str, Any]) -> list[str]:
    names = list(dict.fromkeys(config["strategies"]["enabled"] + config.get("benchmarks", [])))
    return names


def sample_start_indices(
    data: pd.DataFrame,
    horizon: int,
    method: str,
    sample_size: int | None,
) -> tuple[list[int], int]:
    dates = sorted(pd.to_datetime(data["date"].unique()))
    possible = max(0, len(dates) - horizon + 1)
    if possible <= 0:
        return [], possible
    if method == "all_possible":
        return list(range(possible)), possible
    requested = sample_size or possible
    requested = min(requested, possible)
    if method == "deterministic_sample":
        return sorted(set(np.linspace(0, possible - 1, requested, dtype=int).tolist())), possible

    # Deterministic stratified sample: evenly spaced, high/low BTC volatility, BTC trend regimes, and recent starts.
    base = set(np.linspace(0, possible - 1, max(1, requested // 3), dtype=int).tolist())
    prices = data.pivot(index="date", columns="symbol", values="adj_close").sort_index().ffill()
    btc_col = "BTC-USD" if "BTC-USD" in prices.columns else prices.columns[0]
    btc = prices[btc_col]
    vol = btc.pct_change(fill_method=None).rolling(30, min_periods=10).std()
    sma = btc.rolling(200, min_periods=50).mean()
    start_dates = pd.Index(dates[:possible])
    vol_at_start = vol.reindex(start_dates)
    trend_at_start = (btc.reindex(start_dates) > sma.reindex(start_dates)).fillna(False)
    high_vol = vol_at_start.sort_values(ascending=False).head(max(1, requested // 6)).index
    low_vol = vol_at_start.sort_values(ascending=True).head(max(1, requested // 6)).index
    above = start_dates[trend_at_start.to_numpy()]
    below = start_dates[~trend_at_start.to_numpy()]
    recent = start_dates[-max(1, requested // 6) :]
    date_to_idx = {date: i for i, date in enumerate(start_dates)}
    for group in [high_vol, low_vol, above[:: max(1, len(above) // max(1, requested // 8))], below[:: max(1, len(below) // max(1, requested // 8))], recent]:
        for date in group:
            if date in date_to_idx:
                base.add(date_to_idx[date])
    return sorted(base)[:requested], possible


def run_full_period(
    config: dict[str, Any],
    data: pd.DataFrame,
    slippage_labels: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame]]:
    project_cfg = config["project"]
    rows: list[dict[str, Any]] = []
    equity_curves: dict[str, pd.DataFrame] = {}
    for label in slippage_labels:
        fee = slippage_value(config, label)
        for strategy in all_strategy_names(config):
            sim = simulate_strategy(
                data=data,
                strategy_name=strategy,
                strategy_config=strategy_config(config, strategy),
                starting_equity=float(project_cfg["starting_equity"]),
                fee_slippage_per_side=fee,
            )
            metrics = compute_strategy_metrics(
                strategy=strategy,
                slippage_label=label,
                fee_slippage_per_side=fee,
                equity_curve=sim.equity_curve,
                weights=sim.weights,
                rebalances=sim.rebalances,
                asset_contributions=sim.asset_contributions,
                turnover_estimate=sim.turnover_estimate,
                project_cfg=project_cfg,
            )
            rows.append(metrics)
            if label == "standard":
                equity_curves[strategy] = sim.equity_curve
    all_results = pd.DataFrame(rows)
    benchmarks = set(config.get("benchmarks", []))
    benchmark_results = all_results[all_results["strategy"].isin(benchmarks)].reset_index(drop=True)
    strategy_results = all_results[~all_results["strategy"].isin(benchmarks)].reset_index(drop=True)
    return strategy_results, benchmark_results, equity_curves


def run_rolling_windows(
    config: dict[str, Any],
    data: pd.DataFrame,
    mode_cfg: dict[str, Any],
) -> pd.DataFrame:
    project_cfg = config["project"]
    prices = price_matrix(data)
    dates = list(prices.index)
    rows: list[dict[str, Any]] = []
    signal_cache = {
        strategy: generate_signal_weights(data, strategy, strategy_config(config, strategy))
        for strategy in all_strategy_names(config)
        if strategy != "cash_flat"
    }
    for label in mode_cfg.get("slippage_labels", ["standard"]):
        fee = slippage_value(config, label)
        for horizon in mode_cfg.get("horizons", [90]):
            starts, possible_count = sample_start_indices(
                data=data,
                horizon=int(horizon),
                method=mode_cfg.get("rolling_method", "deterministic_sample"),
                sample_size=mode_cfg.get("sample_size_per_group"),
            )
            for strategy in all_strategy_names(config):
                signal_df = signal_cache.get(strategy)
                for idx in starts:
                    start = pd.Timestamp(dates[idx])
                    end = pd.Timestamp(dates[idx + int(horizon) - 1])
                    window = _fast_window_metrics(
                        prices=prices,
                        signal_weights=signal_df,
                        idx=int(idx),
                        horizon=int(horizon),
                        starting_equity=float(project_cfg["starting_equity"]),
                        fee_slippage_per_side=fee,
                        project_cfg=project_cfg,
                    )
                    rows.append(
                        {
                            "strategy": strategy,
                            "slippage_label": label,
                            "horizon": int(horizon),
                            "start_date": start.date().isoformat(),
                            "end_date": end.date().isoformat(),
                            "credibility_tier": "Tier 1 exploratory screen",
                            "final_validation": False,
                            "candidate_validation": False,
                            "paper_forward_ready": False,
                            "sampled_results_are_final": False,
                            "rolling_method": mode_cfg.get("rolling_method", "deterministic_sample"),
                            "possible_window_count": possible_count,
                            **window,
                        }
                    )
    return pd.DataFrame(rows)


def _fast_window_metrics(
    prices: pd.DataFrame,
    signal_weights: pd.DataFrame | None,
    idx: int,
    horizon: int,
    starting_equity: float,
    fee_slippage_per_side: float,
    project_cfg: dict[str, Any],
) -> dict[str, Any]:
    price_slice = prices.iloc[idx : idx + horizon].to_numpy(dtype=float)
    n_rows, n_cols = price_slice.shape
    if n_rows == 0:
        return {
            "final_equity": starting_equity,
            "total_return": 0.0,
            "max_equity": starting_equity,
            "min_equity": starting_equity,
            "max_drawdown_dollars": 0.0,
            "max_drawdown_pct": 0.0,
            "number_of_rebalances": 0,
            **_target_stop_from_arrays(np.array([starting_equity]), project_cfg, prices.index[idx : idx + horizon]),
        }

    returns = np.zeros_like(price_slice, dtype=float)
    if n_rows > 1:
        returns[1:] = np.divide(
            price_slice[1:],
            price_slice[:-1],
            out=np.ones_like(price_slice[1:]),
            where=np.isfinite(price_slice[:-1]) & (price_slice[:-1] != 0),
        ) - 1.0
    returns = np.nan_to_num(returns, nan=0.0, posinf=0.0, neginf=0.0)

    weights = np.zeros((n_rows, n_cols), dtype=float)
    if signal_weights is not None:
        signal_slice = signal_weights.iloc[idx : idx + horizon].reindex(columns=prices.columns).to_numpy(dtype=float)
        last = np.zeros(n_cols, dtype=float)
        for i in range(1, n_rows):
            previous_signal = signal_slice[i - 1]
            if not np.isnan(previous_signal).all():
                last = np.nan_to_num(previous_signal, nan=0.0, posinf=0.0, neginf=0.0)
                last = np.clip(last, 0.0, 1.0)
                total = last.sum()
                if total > 1.0:
                    last = last / total
            weights[i] = last

    equities = np.zeros(n_rows, dtype=float)
    prev_equity = starting_equity
    prev_weights = np.zeros(n_cols, dtype=float)
    rebalances = 0
    for i in range(n_rows):
        current_weights = weights[i]
        turnover = float(np.abs(current_weights - prev_weights).sum())
        cost = prev_equity * turnover * fee_slippage_per_side
        gross_return = float((current_weights * returns[i]).sum())
        equity = max(0.0, prev_equity * (1.0 + gross_return) - cost)
        equities[i] = equity
        if turnover > 1e-9:
            rebalances += 1
        prev_equity = equity
        prev_weights = current_weights

    high_water = np.maximum.accumulate(equities)
    drawdown_dollars = equities - high_water
    drawdown_pct = np.divide(drawdown_dollars, high_water, out=np.zeros_like(drawdown_dollars), where=high_water != 0)
    return {
        "final_equity": float(equities[-1]),
        "total_return": float(equities[-1] / starting_equity - 1.0),
        "max_equity": float(equities.max()),
        "min_equity": float(equities.min()),
        "max_drawdown_dollars": float(drawdown_dollars.min()),
        "max_drawdown_pct": float(drawdown_pct.min()),
        "number_of_rebalances": int(rebalances),
        **_target_stop_from_arrays(equities, project_cfg, prices.index[idx : idx + horizon]),
    }


def _target_stop_from_arrays(equities: np.ndarray, project_cfg: dict[str, Any], dates: pd.Index) -> dict[str, Any]:
    high_water = np.maximum.accumulate(equities)
    absolute_hit = equities <= float(project_cfg["project_stop_equity"])
    trailing_hit = equities <= high_water - float(project_cfg["trailing_drawdown_dollars"])
    mode = project_cfg.get("project_stop_mode", "both")
    if mode == "absolute_floor":
        any_hit = absolute_hit
    elif mode == "trailing_drawdown":
        any_hit = trailing_hit
    else:
        any_hit = absolute_hit | trailing_hit

    first_stop_idx = int(np.argmax(any_hit)) if any_hit.any() else None
    first_stop_date = pd.Timestamp(dates[first_stop_idx]).date().isoformat() if first_stop_idx is not None and len(dates) else ""

    def target_state(target: float) -> tuple[bool, bool, Any]:
        target_hit = equities >= target
        if not target_hit.any():
            return False, False, "", ""
        target_idx = int(np.argmax(target_hit))
        before_stop = True if first_stop_idx is None else target_idx <= first_stop_idx
        target_date = pd.Timestamp(dates[target_idx]).date().isoformat() if len(dates) else ""
        return True, bool(before_stop), target_idx, target_date

    t300 = target_state(float(project_cfg["target_300_equity"]))
    t400 = target_state(float(project_cfg["target_400_equity"]))
    return {
        "target_300_hit": t300[0],
        "target_300_before_stop": t300[1],
        "target_300_first_date": t300[3],
        "time_to_target_300_days": t300[2],
        "target_400_hit": t400[0],
        "target_400_before_stop": t400[1],
        "target_400_first_date": t400[3],
        "time_to_target_400_days": t400[2],
        "absolute_floor_stop_hit": bool(absolute_hit.any()),
        "trailing_drawdown_stop_hit": bool(trailing_hit.any()),
        "any_project_stop_hit": bool(any_hit.any()),
        "first_project_stop_date": first_stop_date,
    }


def write_incomplete_packet(
    config: dict[str, Any],
    config_path: Path,
    mode: str,
    source: str,
    reason: str,
) -> tuple[Path, Path]:
    empty = pd.DataFrame()
    return write_evidence_packet(
        run_id=new_run_id(),
        config=config,
        mode=mode,
        source=source,
        network_download_occurred=False,
        data_coverage=empty,
        warnings=[reason],
        strategy_results=empty,
        benchmark_results=empty,
        rolling_results=empty,
        rolling_summary=empty,
        equity_curves={},
        config_path=config_path,
        incomplete_reason=reason,
    )


def run_exploration(
    config_path: Path,
    mode: str | None = None,
    source: str = "yfinance",
    no_network: bool = False,
    reuse_cache: bool = True,
    force_download: bool = False,
    max_workers: int | None = None,
) -> dict[str, Any]:
    del max_workers  # reserved for later; no parallel exchange/API logic is used.
    config = load_config(config_path)
    mode = mode or config["validation"]["default_mode"]
    modes = config["validation"]["modes"]
    if mode not in modes:
        raise ValueError(f"Unknown validation mode: {mode}")
    mode_cfg = modes[mode]
    try:
        loaded = load_crypto_data(
            config=config,
            source=source,
            no_network=no_network,
            reuse_cache=reuse_cache,
            force_download=force_download,
        )
    except CryptoDataError as exc:
        run_dir, latest_dir = write_incomplete_packet(config, config_path, mode, source, str(exc))
        return {
            "run_dir": run_dir,
            "latest_dir": latest_dir,
            "status": "incomplete",
            "reason": str(exc),
            "network_download_occurred": False,
        }

    strategy_results, benchmark_results, equity_curves = run_full_period(
        config=config,
        data=loaded.data,
        slippage_labels=mode_cfg.get("slippage_labels", ["standard"]),
    )
    rolling_results = run_rolling_windows(config=config, data=loaded.data, mode_cfg=mode_cfg)
    rolling_summary = summarize_rolling_windows(rolling_results)
    run_id = new_run_id()
    run_dir, latest_dir = write_evidence_packet(
        run_id=run_id,
        config=config,
        mode=mode,
        source=loaded.source,
        network_download_occurred=loaded.network_download_occurred,
        data_coverage=loaded.coverage,
        warnings=loaded.warnings,
        strategy_results=strategy_results,
        benchmark_results=benchmark_results,
        rolling_results=rolling_results,
        rolling_summary=rolling_summary,
        equity_curves=equity_curves,
        config_path=config_path,
    )
    return {
        "run_id": run_id,
        "run_dir": run_dir,
        "latest_dir": latest_dir,
        "status": "complete",
        "source": loaded.source,
        "network_download_occurred": loaded.network_download_occurred,
        "strategy_results": strategy_results,
        "benchmark_results": benchmark_results,
        "rolling_summary": rolling_summary,
    }
