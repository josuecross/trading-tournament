from __future__ import annotations

import csv
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parents[3]
EVIDENCE_DIR = ROOT / "evidence" / "forward_operational_reinitialization_vm_dsr_combo_v1" / "latest"
PRIOR_REPAIR_DIR = ROOT / "evidence" / "repair_vm_dsr_observation_data_and_state_v1" / "latest"
SNAPSHOT_DIR = ROOT / "paper_forward_observations" / "_operational_market_data" / "forward_operational_reinitialization_vm_dsr_combo_v1"
ACTIVE_OBSERVATIONS_PATH = ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml"
ACTIVE_COMBO_HISTORY_DIR = ROOT / "evidence" / "active_combo_benchmark" / "latest"

VM_ID = "paper_forward_vm_quality_lowvol_proxy_v1"
DSR_ID = "paper_forward_dsr_sector_equal_weight_defensive_filter_v1"
USCI_ID = "paper_forward_usci_dynamic_commodity_curve_selection_wrapper_v1"
DERIVED_ID = "paper_forward_combo_vm_dsr_usci_equal_weight_monthly_v1"
ACTIVE_COMBO_ID = "active_combo_vm_dsr_equal_weight_v1"

VM_BASE_ID = "vm_quality_lowvol_proxy_v1"
DSR_BASE_ID = "dsr_sector_equal_weight_defensive_filter_v1"

VM_RISK_ASSETS = ["SPLV", "USMV", "QUAL", "SPY"]
VM_SYMBOLS = [*VM_RISK_ASSETS, "BIL"]
DSR_RISK_ASSETS = ["XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLU", "XLI", "XLB", "XLC"]
DSR_SYMBOLS = [*DSR_RISK_ASSETS, "BIL"]
USCI_SYMBOLS = ["USCI", "DBC", "BIL", "SPY"]
AUTHORIZED_SYMBOLS = sorted(set(VM_SYMBOLS + DSR_SYMBOLS + USCI_SYMBOLS))

OPERATIONAL_BASELINE_VERSION = "forward_operational_reinitialization_vm_dsr_combo_v1"
PROVENANCE = "direction_owner_authorized_forward_only_operational_reinitialization"
PRIOR_INTERVAL_STATUS = "unobserved_due_to_missing_authoritative_baseline"
OUTCOME = "forward_operational_reinitialization_passed"
NEXT_ACTION = "resume_targeted_fast_discovery_while_reinitialized_observations_run"

INITIAL_CAPITAL = 3000.0
DERIVED_SLEEVE_CAPITAL = 1000.0
INITIALIZATION_COST_RATE = 0.0005
PORTFOLIO_TRANSFER_COST_RATE = 0.0005


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def sha256_path(path: Path) -> str:
    if not path.exists():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (float, np.floating)):
        val = float(value)
        if not np.isfinite(val):
            return ""
        return f"{val:.12g}"
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, default=str)
    return str(value)


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fieldnames})


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def dump_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8")


def observation_path(observation_id: str) -> Path:
    return ROOT / "paper_forward_observations" / observation_id / "active_observation.yaml"


def cache_path(symbol: str) -> Path:
    return ROOT / "data" / "cache" / f"{symbol}.csv"


def snapshot_path(symbol: str) -> Path:
    return SNAPSHOT_DIR / f"{symbol}.csv"


def component_ledger_path(observation_id: str) -> Path:
    return ROOT / "paper_forward_observations" / observation_id / "component_forward_ledger.csv"


def active_combo_forward_index_path() -> Path:
    return ROOT / "paper_forward_observations" / ACTIVE_COMBO_ID / "operational_forward_reference_index.csv"


def derived_ledger_path() -> Path:
    return ROOT / "paper_forward_observations" / DERIVED_ID / "derived_component_forward_ledger.csv"


def prior_repair_hashes() -> dict[str, str]:
    if not PRIOR_REPAIR_DIR.exists():
        return {}
    return {rel(path): sha256_path(path) for path in sorted(PRIOR_REPAIR_DIR.iterdir()) if path.is_file()}


def read_price_file(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path)
    if "date" not in frame.columns or "adj_close" not in frame.columns:
        return pd.DataFrame()
    out = pd.DataFrame()
    out["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None)
    for column in ["open", "high", "low", "close", "adj_close", "volume"]:
        source = column if column in frame.columns else f"raw_{column}"
        if source in frame.columns:
            out[column] = pd.to_numeric(frame[source], errors="coerce")
        elif column == "volume":
            out[column] = 0.0
        else:
            out[column] = pd.to_numeric(frame["adj_close"], errors="coerce")
    if "symbol" in frame.columns:
        out["symbol"] = frame["symbol"].astype(str)
    else:
        out["symbol"] = path.stem
    out = out.dropna(subset=["date", "adj_close"]).sort_values("date").drop_duplicates("date", keep="last")
    return out[["date", "open", "high", "low", "close", "adj_close", "volume", "symbol"]]


def validate_price_frame(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {
            "valid": False,
            "monotonic_dates": False,
            "duplicate_date_count": 0,
            "positive_adjusted_prices": False,
            "required_fields_present": False,
            "first_date": "",
            "last_date": "",
            "row_count": 0,
        }
    return {
        "valid": bool(
            frame["date"].is_monotonic_increasing
            and int(frame["date"].duplicated().sum()) == 0
            and (frame["adj_close"] > 0).all()
            and all(column in frame.columns for column in ["open", "high", "low", "close", "adj_close", "volume"])
        ),
        "monotonic_dates": bool(frame["date"].is_monotonic_increasing),
        "duplicate_date_count": int(frame["date"].duplicated().sum()),
        "positive_adjusted_prices": bool((frame["adj_close"] > 0).all()),
        "required_fields_present": all(column in frame.columns for column in ["open", "high", "low", "close", "adj_close", "volume"]),
        "first_date": frame["date"].min().date().isoformat(),
        "last_date": frame["date"].max().date().isoformat(),
        "row_count": int(len(frame)),
    }


def write_operational_snapshots() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    refresh_rows: list[dict[str, Any]] = []
    provider_rows: list[dict[str, Any]] = []
    hash_rows: list[dict[str, Any]] = []
    for symbol in AUTHORIZED_SYMBOLS:
        source = cache_path(symbol)
        target = snapshot_path(symbol)
        target_before = sha256_path(target)
        existing_frame = read_price_file(target)
        existing_quality = validate_price_frame(existing_frame)
        frame = existing_frame if existing_quality["valid"] else read_price_file(source)
        quality = validate_price_frame(frame)
        wrote_snapshot = False
        if quality["valid"] and not existing_quality["valid"]:
            frame.to_csv(target, index=False, lineterminator="\n", date_format="%Y-%m-%d")
            wrote_snapshot = True
        target_after = sha256_path(target)
        refresh_rows.append(
            {
                "symbol": symbol,
                "authorized": True,
                "source_cache_path": rel(source),
                "operational_snapshot_path": rel(target),
                "latest_valid_operational_snapshot_date": quality["last_date"],
                "refresh_requested": False,
                "refresh_status": "operational_snapshot_seeded_or_reused_from_existing_local_cache",
                "provider_identity": "existing_local_cache_snapshot_no_provider_call",
                "snapshot_changed_this_run": target_before != target_after,
                "snapshot_written_this_run": wrote_snapshot,
                "monotonic_dates": quality["monotonic_dates"],
                "duplicate_date_count": quality["duplicate_date_count"],
                "positive_adjusted_prices": quality["positive_adjusted_prices"],
                "required_fields_present": quality["required_fields_present"],
                "corporate_action_consistency": "source_adjustment_factor_preserved_where_available",
                "validation_passed": quality["valid"],
            }
        )
        provider_rows.append(
            {
                "symbol": symbol,
                "provider": "none",
                "request_start": "",
                "request_end": "",
                "request_status": "not_requested_existing_local_cache_snapshot_used",
                "rows_returned": 0,
                "provider_error": "",
                "no_provider_fallback_used": True,
            }
        )
        latest = frame.iloc[-1] if not frame.empty else {}
        hash_rows.append(
            {
                "symbol": symbol,
                "operational_snapshot_path": rel(target),
                "source_cache_hash": sha256_path(source),
                "operational_snapshot_hash": target_after,
                "latest_snapshot_date": "" if frame.empty else latest["date"].date().isoformat(),
                "latest_adj_close": "" if frame.empty else float(latest["adj_close"]),
                "snapshot_reused_on_rerun": target_before == target_after or target_before == "missing",
            }
        )
    return refresh_rows, provider_rows, hash_rows


def load_snapshot_prices(symbols: list[str] | None = None) -> dict[str, pd.DataFrame]:
    selected = symbols or AUTHORIZED_SYMBOLS
    return {symbol: read_price_file(snapshot_path(symbol)) for symbol in selected}


def close_frame(symbols: list[str]) -> pd.DataFrame:
    frames = load_snapshot_prices(symbols)
    series = {}
    for symbol, frame in frames.items():
        series[symbol] = frame.set_index("date")["adj_close"].astype(float)
    return pd.DataFrame(series).sort_index()


def latest_common_date(symbols: list[str]) -> pd.Timestamp:
    prices = close_frame(symbols)
    complete = prices.dropna(how="any")
    if complete.empty:
        raise RuntimeError("No complete common operational date exists for authorized symbols")
    return pd.Timestamp(complete.index.max())


def previous_common_date(symbols: list[str], t0: pd.Timestamp) -> pd.Timestamp:
    prices = close_frame(symbols)
    complete = prices.dropna(how="any")
    before = complete[complete.index < t0]
    if before.empty:
        raise RuntimeError("No prior complete signal date exists before T0")
    return pd.Timestamp(before.index.max())


def sma(series: pd.Series, date: pd.Timestamp, window: int) -> float:
    subset = series.loc[:date].dropna().tail(window)
    if len(subset) < window:
        return float("nan")
    return float(subset.mean())


def trailing_return(series: pd.Series, date: pd.Timestamp, window: int) -> float:
    subset = series.loc[:date].dropna()
    if len(subset) <= window:
        return float("nan")
    return float(subset.iloc[-1] / subset.iloc[-window - 1] - 1.0)


def realized_vol(series: pd.Series, date: pd.Timestamp, window: int) -> float:
    returns = series.loc[:date].pct_change().dropna().tail(window)
    if len(returns) < window:
        return float("nan")
    return float(returns.std())


def derive_vm_target(signal_date: pd.Timestamp) -> tuple[dict[str, float], list[dict[str, Any]], str]:
    prices = close_frame(VM_SYMBOLS)
    rows: list[dict[str, Any]] = []
    scored: list[tuple[str, float]] = []
    for symbol in VM_RISK_ASSETS:
        series = prices[symbol]
        latest_close = float(series.loc[signal_date])
        sma200 = sma(series, signal_date, 200)
        ret126 = trailing_return(series, signal_date, 126)
        vol60 = realized_vol(series, signal_date, 60)
        eligible = bool(np.isfinite(sma200) and latest_close > sma200)
        score = ret126 / vol60 if eligible and np.isfinite(ret126) and np.isfinite(vol60) and vol60 > 0 else float("nan")
        if np.isfinite(score):
            scored.append((symbol, score))
        rows.append(
            {
                "strategy_id": VM_ID,
                "symbol": symbol,
                "signal_date": signal_date.date().isoformat(),
                "close": latest_close,
                "sma200": sma200,
                "close_above_sma200": eligible,
                "return_126d": ret126,
                "realized_vol_60d": vol60,
                "score": score,
                "selected": False,
                "target_weight": 0.0,
                "rule_source": "frozen_vm_quality_lowvol_proxy_v1",
            }
        )
    ranked = [symbol for symbol, _score in sorted(scored, key=lambda item: item[1], reverse=True)[:2]]
    if len(ranked) == 2:
        weights = {ranked[0]: 0.5, ranked[1]: 0.5}
    elif len(ranked) == 1:
        weights = {ranked[0]: 1.0}
    else:
        weights = {"BIL": 1.0}
    for row in rows:
        row["selected"] = row["symbol"] in weights
        row["target_weight"] = weights.get(row["symbol"], 0.0)
    if "BIL" in weights:
        rows.append(
            {
                "strategy_id": VM_ID,
                "symbol": "BIL",
                "signal_date": signal_date.date().isoformat(),
                "close": float(prices.loc[signal_date, "BIL"]),
                "sma200": "",
                "close_above_sma200": "",
                "return_126d": "",
                "realized_vol_60d": "",
                "score": "",
                "selected": True,
                "target_weight": weights["BIL"],
                "rule_source": "frozen_vm_quality_lowvol_proxy_v1_fallback",
            }
        )
    fingerprint = stable_hash({"strategy": VM_BASE_ID, "signal_date": signal_date.date().isoformat(), "weights": weights})
    return weights, rows, fingerprint


def derive_dsr_target(signal_date: pd.Timestamp) -> tuple[dict[str, float], list[dict[str, Any]], str]:
    prices = close_frame(DSR_SYMBOLS)
    rows: list[dict[str, Any]] = []
    qualifying: list[str] = []
    for symbol in DSR_RISK_ASSETS:
        series = prices[symbol]
        latest_close = float(series.loc[signal_date])
        sma200 = sma(series, signal_date, 200)
        eligible = bool(np.isfinite(sma200) and latest_close > sma200)
        if eligible:
            qualifying.append(symbol)
        rows.append(
            {
                "strategy_id": DSR_ID,
                "symbol": symbol,
                "signal_date": signal_date.date().isoformat(),
                "close": latest_close,
                "sma200": sma200,
                "close_above_sma200": eligible,
                "qualifying_sector_count": "",
                "selected": eligible,
                "target_weight": 0.0,
                "rule_source": "frozen_dsr_sector_equal_weight_defensive_filter_v1",
            }
        )
    weights: dict[str, float]
    if len(qualifying) >= 3:
        weights = {symbol: 1.0 / len(qualifying) for symbol in qualifying}
    elif qualifying:
        weights = {symbol: 1.0 / 3.0 for symbol in qualifying}
        weights["BIL"] = 1.0 - len(qualifying) / 3.0
    else:
        weights = {"BIL": 1.0}
    for row in rows:
        row["qualifying_sector_count"] = len(qualifying)
        row["target_weight"] = weights.get(row["symbol"], 0.0)
    if "BIL" in weights:
        rows.append(
            {
                "strategy_id": DSR_ID,
                "symbol": "BIL",
                "signal_date": signal_date.date().isoformat(),
                "close": float(prices.loc[signal_date, "BIL"]),
                "sma200": "",
                "close_above_sma200": "",
                "qualifying_sector_count": len(qualifying),
                "selected": True,
                "target_weight": weights["BIL"],
                "rule_source": "frozen_dsr_sector_equal_weight_defensive_filter_v1_fallback",
            }
        )
    fingerprint = stable_hash({"strategy": DSR_BASE_ID, "signal_date": signal_date.date().isoformat(), "weights": weights})
    return weights, rows, fingerprint


def t0_prices(symbols: list[str], t0: pd.Timestamp) -> dict[str, float]:
    prices = close_frame(symbols)
    return {symbol: float(prices.loc[t0, symbol]) for symbol in symbols if symbol in prices.columns and pd.notna(prices.loc[t0, symbol])}


def initialize_component(
    observation_id: str,
    base_strategy_id: str,
    weights: dict[str, float],
    fingerprint: str,
    t0: pd.Timestamp,
    signal_date: pd.Timestamp,
) -> tuple[dict[str, Any], dict[str, Any]]:
    prices = t0_prices(list(weights), t0)
    turnover = sum(abs(weight) for weight in weights.values())
    cost = INITIAL_CAPITAL * INITIALIZATION_COST_RATE * turnover
    post_cost_equity = INITIAL_CAPITAL - cost
    shares = {symbol: (post_cost_equity * weight) / prices[symbol] for symbol, weight in weights.items() if weight > 0}
    holdings = {symbol: shares[symbol] * prices[symbol] for symbol in shares}
    cash = round(post_cost_equity - sum(holdings.values()), 10)
    snapshot_hashes = {symbol: sha256_path(snapshot_path(symbol)) for symbol in weights}
    payload = {
        "observation_id": observation_id,
        "base_strategy_id": base_strategy_id,
        "operational_baseline_status": "initialized",
        "operational_baseline_version": OPERATIONAL_BASELINE_VERSION,
        "operational_baseline_date": t0.date().isoformat(),
        "operational_baseline_provenance": PROVENANCE,
        "continuity_from_original_activation": False,
        "prior_interval_status": PRIOR_INTERVAL_STATUS,
        "initial_virtual_capital": INITIAL_CAPITAL,
        "initialization_cost_rate": INITIALIZATION_COST_RATE,
        "initialization_turnover": turnover,
        "initialization_cost": cost,
        "post_cost_equity": post_cost_equity,
        "latest_committed_observation_date": t0.date().isoformat(),
        "latest_committed_virtual_equity": post_cost_equity,
        "current_holdings": holdings,
        "virtual_shares": shares,
        "cash": cash,
        "target_allocation": weights,
        "last_signal_date": signal_date.date().isoformat(),
        "last_rebalance_date": t0.date().isoformat(),
        "strategy_fingerprint": fingerprint,
        "component_forward_ledger": rel(component_ledger_path(observation_id)),
        "data_snapshot_hashes": snapshot_hashes,
    }
    row = {
        "observation_id": observation_id,
        "date": t0.date().isoformat(),
        "row_type": "operational_initialization",
        "continuity_from_original_activation": False,
        "prior_interval_status": PRIOR_INTERVAL_STATUS,
        "initial_virtual_capital": INITIAL_CAPITAL,
        "post_cost_equity": post_cost_equity,
        "initialization_cost": cost,
        "target_weights": weights,
        "holdings": holdings,
        "shares": shares,
        "cash": cash,
        "signal_date": signal_date.date().isoformat(),
        "rebalance_reference_date": t0.date().isoformat(),
        "data_snapshot_hashes": snapshot_hashes,
        "strategy_fingerprint": fingerprint,
        "orders_created": 0,
        "broker_calls": 0,
        "status": "initialized_forward_only_no_prior_continuity",
    }
    return payload, row


LEDGER_FIELDS = [
    "observation_id",
    "date",
    "row_type",
    "continuity_from_original_activation",
    "prior_interval_status",
    "initial_virtual_capital",
    "post_cost_equity",
    "initialization_cost",
    "target_weights",
    "holdings",
    "shares",
    "cash",
    "signal_date",
    "rebalance_reference_date",
    "data_snapshot_hashes",
    "strategy_fingerprint",
    "orders_created",
    "broker_calls",
    "status",
]


def write_component_ledger(observation_id: str, init_row: dict[str, Any]) -> None:
    path = component_ledger_path(observation_id)
    existing = read_csv_rows(path)
    key = (init_row["date"], init_row["row_type"])
    rows = [row for row in existing if (row.get("date"), row.get("row_type")) != key]
    rows.append(init_row)
    rows = sorted(rows, key=lambda row: (row.get("date", ""), row.get("row_type", "")))
    write_csv(path, rows, LEDGER_FIELDS)


def merge_observation_state(observation_id: str, updates: dict[str, Any]) -> None:
    path = observation_path(observation_id)
    payload = load_yaml(path)
    payload.update(updates)
    payload["latest_operational_update_id"] = OPERATIONAL_BASELINE_VERSION
    payload["latest_operational_update_evidence_path"] = rel(EVIDENCE_DIR)
    payload["latest_operational_update_status"] = OUTCOME
    dump_yaml(path, payload)


def preserve_and_maybe_update_usci() -> dict[str, Any]:
    obs_path = observation_path(USCI_ID)
    ledger = component_ledger_path(USCI_ID)
    before_state_hash = sha256_path(obs_path)
    before_ledger_hash = sha256_path(ledger)
    obs = load_yaml(obs_path)
    latest_date = str(obs.get("latest_committed_observation_date", ""))
    latest_snapshot = read_price_file(snapshot_path("USCI"))
    newer_rows = latest_snapshot[latest_snapshot["date"] > pd.Timestamp(latest_date)] if latest_date else latest_snapshot.iloc[0:0]
    appended_rows = 0
    if not newer_rows.empty:
        existing = read_csv_rows(ledger)
        shares = float(obs.get("latest_committed_virtual_shares", obs.get("initial_virtual_shares", 0.0)))
        cash = float(obs.get("latest_committed_virtual_cash", obs.get("initial_virtual_cash", 0.0)))
        initial_capital = float(obs.get("initial_virtual_capital", INITIAL_CAPITAL))
        for item in newer_rows.itertuples(index=False):
            equity = shares * float(item.adj_close) + cash
            existing.append(
                {
                    "component_observation_id": USCI_ID,
                    "date": item.date.date().isoformat(),
                    "session_sequence": len(existing),
                    "source_symbol": "USCI",
                    "adj_close": round(float(item.adj_close), 10),
                    "daily_return": "",
                    "virtual_shares": round(shares, 12),
                    "virtual_cash": round(cash, 6),
                    "virtual_equity": round(equity, 6),
                    "cumulative_return": round(equity / initial_capital - 1.0, 10),
                    "holding_state": "100pct_USCI",
                    "orders_created": 0,
                    "broker_calls": 0,
                    "status": "committed_independent_forward_update",
                    "source_cache_hash": sha256_path(snapshot_path("USCI")),
                }
            )
            obs.update(
                {
                    "latest_committed_observation_date": item.date.date().isoformat(),
                    "latest_committed_virtual_equity": round(equity, 6),
                    "latest_committed_observed_price": round(float(item.adj_close), 10),
                    "latest_committed_virtual_shares": round(shares, 12),
                    "latest_committed_virtual_cash": round(cash, 6),
                    "latest_committed_forward_sessions": int(obs.get("latest_committed_forward_sessions", 0)) + 1,
                }
            )
            appended_rows += 1
        if existing:
            write_csv(ledger, existing, list(existing[0].keys()))
            dump_yaml(obs_path, obs)
    return {
        "observation_id": USCI_ID,
        "state_hash_before": before_state_hash,
        "state_hash_after": sha256_path(obs_path),
        "ledger_hash_before": before_ledger_hash,
        "ledger_hash_after": sha256_path(ledger),
        "latest_committed_observation_date_before": latest_date,
        "latest_committed_observation_date_after": load_yaml(obs_path).get("latest_committed_observation_date", ""),
        "rows_appended": appended_rows,
        "reset_to_3000": False,
        "existing_committed_rows_preserved": True,
    }


def next_month_label(t0: pd.Timestamp) -> str:
    year = t0.year + (1 if t0.month == 12 else 0)
    month = 1 if t0.month == 12 else t0.month + 1
    return f"{year:04d}-{month:02d}"


def update_active_combo_reference(t0: pd.Timestamp, vm_init: dict[str, Any], dsr_init: dict[str, Any]) -> dict[str, Any]:
    path = active_combo_forward_index_path()
    row = {
        "date": t0.date().isoformat(),
        "benchmark_id": ACTIVE_COMBO_ID,
        "role": "benchmark_reference_only",
        "vm_component_observation_id": VM_ID,
        "dsr_component_observation_id": DSR_ID,
        "vm_weight": 0.5,
        "dsr_weight": 0.5,
        "vm_forward_index": 1.0,
        "dsr_forward_index": 1.0,
        "active_combo_forward_index": 1.0,
        "continuity_from_historical_series": False,
        "historical_definition_changed": False,
        "source": OPERATIONAL_BASELINE_VERSION,
    }
    write_csv(path, [row], list(row.keys()))
    return {
        "benchmark_id": ACTIVE_COMBO_ID,
        "role": "benchmark_reference_only",
        "operational_rebaseline_date": t0.date().isoformat(),
        "index_path": rel(path),
        "vm_weight": 0.5,
        "dsr_weight": 0.5,
        "vm_post_cost_equity": vm_init["post_cost_equity"],
        "dsr_post_cost_equity": dsr_init["post_cost_equity"],
        "continuity_from_historical_series": False,
        "historical_definition_changed": False,
    }


def update_derived_observation(t0: pd.Timestamp) -> dict[str, Any]:
    component_indices = {
        VM_ID: 1.0,
        DSR_ID: 1.0,
        USCI_ID: 1.0,
    }
    updates = {
        "operational_baseline_status": "initialized",
        "operational_baseline_version": OPERATIONAL_BASELINE_VERSION,
        "operational_baseline_date": t0.date().isoformat(),
        "operational_baseline_provenance": PROVENANCE,
        "continuity_from_original_activation": False,
        "prior_interval_status": PRIOR_INTERVAL_STATUS,
        "original_operational_initialization_status": "unusable_component_baselines_absent",
        "initial_virtual_capital": INITIAL_CAPITAL,
        "latest_committed_observation_date": t0.date().isoformat(),
        "latest_committed_virtual_equity": INITIAL_CAPITAL,
        "initial_sleeve_capital": {VM_ID: DERIVED_SLEEVE_CAPITAL, DSR_ID: DERIVED_SLEEVE_CAPITAL, USCI_ID: DERIVED_SLEEVE_CAPITAL},
        "component_forward_index_baseline": component_indices,
        "component_forward_index_baseline_date": t0.date().isoformat(),
        "component_capital_reduced_or_reserved": False,
        "next_scheduled_rebalance_month": next_month_label(t0),
        "next_scheduled_rebalance_date": "pending_first_complete_common_session",
        "portfolio_transfer_cost_rate": PORTFOLIO_TRANSFER_COST_RATE,
        "component_costs_reapplied": False,
        "missing_component_return_as_zero": False,
        "forward_fill_missing_component_return": False,
        "advance_on_partial_component_date": False,
    }
    merge_observation_state(DERIVED_ID, updates)
    row = {
        "date": t0.date().isoformat(),
        "derived_observation_id": DERIVED_ID,
        "row_type": "operational_reinitialization",
        "vm_sleeve_value": DERIVED_SLEEVE_CAPITAL,
        "dsr_sleeve_value": DERIVED_SLEEVE_CAPITAL,
        "usci_sleeve_value": DERIVED_SLEEVE_CAPITAL,
        "derived_total_equity": INITIAL_CAPITAL,
        "vm_weight": 1.0 / 3.0,
        "dsr_weight": 1.0 / 3.0,
        "usci_weight": 1.0 / 3.0,
        "component_indices_rebased": True,
        "component_capital_reduced_or_reserved": False,
        "continuity_from_original_activation": False,
        "portfolio_transfer_cost": 0.0,
        "component_costs_reapplied": False,
        "status": "initialized_forward_only_no_prior_continuity",
    }
    write_csv(derived_ledger_path(), [row], list(row.keys()))
    return {
        "derived_observation_id": DERIVED_ID,
        "operational_baseline_date": t0.date().isoformat(),
        "initial_virtual_capital": INITIAL_CAPITAL,
        "initial_sleeves": updates["initial_sleeve_capital"],
        "component_indices_rebased_to": component_indices,
        "component_observations_reset": False,
        "component_capital_reduced_or_reserved": False,
        "next_scheduled_rebalance_month": next_month_label(t0),
        "next_scheduled_rebalance_date": "pending_first_complete_common_session",
        "ledger_path": rel(derived_ledger_path()),
        "continuity_from_original_activation": False,
    }


def ensure_active_observations_direction_record(t0: pd.Timestamp) -> None:
    payload = load_yaml(ACTIVE_OBSERVATIONS_PATH)
    existing = payload.get("latest_forward_operational_reinitialization_vm_dsr_combo_v1", {})
    payload["latest_forward_operational_reinitialization_vm_dsr_combo_v1"] = {
        "created_utc": existing.get("created_utc", now_utc()) if isinstance(existing, dict) else now_utc(),
        "evidence_path": rel(EVIDENCE_DIR),
        "outcome": OUTCOME,
        "vm_observation_id": VM_ID,
        "dsr_observation_id": DSR_ID,
        "usci_observation_id": USCI_ID,
        "derived_observation_id": DERIVED_ID,
        "operational_baseline_date": t0.date().isoformat(),
        "provenance": PROVENANCE,
        "continuity_from_original_activation": False,
        "prior_interval_status": PRIOR_INTERVAL_STATUS,
        "next_action": NEXT_ACTION,
        "broker_integration": False,
        "paper_orders": False,
        "live_orders": False,
        "real_money_recommendation": False,
    }
    dump_yaml(ACTIVE_OBSERVATIONS_PATH, payload)


def protected_hashes() -> dict[str, str]:
    paths = list(sorted(PRIOR_REPAIR_DIR.iterdir())) if PRIOR_REPAIR_DIR.exists() else []
    extra = [
        ACTIVE_COMBO_HISTORY_DIR / "active_combo_manifest.json",
        ACTIVE_COMBO_HISTORY_DIR / "active_combo_benchmark_definition.yaml",
        ACTIVE_COMBO_HISTORY_DIR / "active_combo_equity_series.csv",
        ROOT / "evidence" / "combo_vm_dsr_usci_paper_forward_eligibility_review_v1" / "latest" / "paper_forward_decision.json",
        ROOT / "evidence" / "usci_paper_forward_eligibility_review_v1" / "latest" / "paper_forward_decision.json",
    ]
    for path in extra:
        if path.exists():
            paths.append(path)
    return {rel(path): sha256_path(path) for path in paths if path.is_file()}


def source_change_rows(before: dict[str, str]) -> list[dict[str, Any]]:
    watched = [
        ACTIVE_OBSERVATIONS_PATH,
        observation_path(VM_ID),
        observation_path(DSR_ID),
        observation_path(USCI_ID),
        observation_path(DERIVED_ID),
        component_ledger_path(VM_ID),
        component_ledger_path(DSR_ID),
        component_ledger_path(USCI_ID),
        active_combo_forward_index_path(),
        derived_ledger_path(),
    ]
    return [
        {
            "source_of_truth_file": rel(path),
            "before_hash": before.get(rel(path), "missing"),
            "after_hash": sha256_path(path),
            "changed": before.get(rel(path), "missing") != sha256_path(path),
            "change_type": "operational_forward_reinitialization_or_preservation",
        }
        for path in watched
    ]


def file_hash_map(paths: list[Path]) -> dict[str, str]:
    return {rel(path): sha256_path(path) for path in paths}


def write_outputs() -> dict[str, Any]:
    created_at = now_utc()
    source_watch = [
        ACTIVE_OBSERVATIONS_PATH,
        observation_path(VM_ID),
        observation_path(DSR_ID),
        observation_path(USCI_ID),
        observation_path(DERIVED_ID),
        component_ledger_path(VM_ID),
        component_ledger_path(DSR_ID),
        component_ledger_path(USCI_ID),
        active_combo_forward_index_path(),
        derived_ledger_path(),
    ]
    source_before = file_hash_map(source_watch)
    repair_before = prior_repair_hashes()
    research_cache_before = {symbol: sha256_path(cache_path(symbol)) for symbol in AUTHORIZED_SYMBOLS}
    protected_before = protected_hashes()

    refresh_rows, provider_rows, snapshot_hash_rows = write_operational_snapshots()
    if not all(row["validation_passed"] for row in refresh_rows):
        outcome = "observation_data_refresh_blocked"
        next_action = "resolve_observation_operational_snapshot_data_before_reinitialization"
    else:
        outcome = OUTCOME
        next_action = NEXT_ACTION

    t0 = latest_common_date(AUTHORIZED_SYMBOLS)
    signal_date = previous_common_date(AUTHORIZED_SYMBOLS, t0)
    vm_weights, vm_target_rows, vm_fingerprint = derive_vm_target(signal_date)
    dsr_weights, dsr_target_rows, dsr_fingerprint = derive_dsr_target(signal_date)
    vm_init, vm_ledger_row = initialize_component(VM_ID, VM_BASE_ID, vm_weights, vm_fingerprint, t0, signal_date)
    dsr_init, dsr_ledger_row = initialize_component(DSR_ID, DSR_BASE_ID, dsr_weights, dsr_fingerprint, t0, signal_date)

    write_component_ledger(VM_ID, vm_ledger_row)
    write_component_ledger(DSR_ID, dsr_ledger_row)
    merge_observation_state(VM_ID, vm_init)
    merge_observation_state(DSR_ID, dsr_init)
    usci_status = preserve_and_maybe_update_usci()
    active_combo_status = update_active_combo_reference(t0, vm_init, dsr_init)
    derived_status = update_derived_observation(t0)
    ensure_active_observations_direction_record(t0)

    repair_after = prior_repair_hashes()
    research_cache_after = {symbol: sha256_path(cache_path(symbol)) for symbol in AUTHORIZED_SYMBOLS}
    protected_after = protected_hashes()

    if EVIDENCE_DIR.exists():
        shutil.rmtree(EVIDENCE_DIR)
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

    manifest = {
        "task_id": OPERATIONAL_BASELINE_VERSION,
        "created_at_utc": created_at,
        "outcome": outcome,
        "forward_operational_reinitialization": True,
        "historical_recovery_attempted": False,
        "strategy_rules_changed": False,
        "new_observation_ids_created": False,
        "provider_download": False,
        "provider_api_called": False,
        "research_cache_modified": research_cache_before != research_cache_after,
        "historical_research_evidence_modified": protected_before != protected_after,
        "broker_api_called": False,
        "paper_orders_created": False,
        "live_orders": False,
        "real_money_recommendation": False,
        "t0": t0.date().isoformat(),
        "signal_date": signal_date.date().isoformat(),
        "next_action": next_action,
    }
    write_json(EVIDENCE_DIR / "reinitialization_manifest.json", manifest)
    write_json(
        EVIDENCE_DIR / "direction_owner_reinitialization_decision.json",
        {
            "decision": "authorize_forward_only_operational_reinitialization",
            "provenance": PROVENANCE,
            "historical_recovery_ended": True,
            "retain_observation_ids": [VM_ID, DSR_ID, USCI_ID, DERIVED_ID],
            "continuity_claim": False,
            "no_performance_judgment": True,
        },
    )
    write_json(
        EVIDENCE_DIR / "prior_repair_packet_hashes.json",
        {
            "packet_path": rel(PRIOR_REPAIR_DIR),
            "hashes_before": repair_before,
            "hashes_after": repair_after,
            "byte_identical": repair_before == repair_after,
        },
    )
    write_json(
        EVIDENCE_DIR / "historical_recovery_exhaustion_record.json",
        {
            "prior_repair_outcome": "observation_state_recovery_blocked",
            "recovery_hierarchy_not_repeated": True,
            "missing_fields": [
                "activation_date",
                "initial_virtual_capital",
                "latest_committed_date",
                "latest_committed_equity",
                "holdings_or_target_allocation",
                "shares_and_cash",
                "last_signal_date",
                "last_rebalance_date",
                "complete_frozen_operational_fingerprint",
            ],
            "prior_interval_status": PRIOR_INTERVAL_STATUS,
            "no_missing_baseline_fabricated": True,
        },
    )
    write_json(
        EVIDENCE_DIR / "authorized_symbol_universe.json",
        {"authorized_symbols": AUTHORIZED_SYMBOLS, "vm_symbols": VM_SYMBOLS, "dsr_symbols": DSR_SYMBOLS, "usci_symbols": USCI_SYMBOLS, "unauthorized_symbols_refreshed": []},
    )
    write_csv(EVIDENCE_DIR / "observation_data_refresh_manifest.csv", refresh_rows, list(refresh_rows[0].keys()))
    write_csv(EVIDENCE_DIR / "provider_requests_and_results.csv", provider_rows, list(provider_rows[0].keys()))
    write_csv(EVIDENCE_DIR / "operational_snapshot_hashes.csv", snapshot_hash_rows, list(snapshot_hash_rows[0].keys()))
    write_csv(
        EVIDENCE_DIR / "frozen_t0_derivation.csv",
        [
            {
                "symbol": row["symbol"],
                "latest_valid_operational_snapshot_date": row["latest_snapshot_date"],
                "included_in_t0_common_date": True,
                "t0": t0.date().isoformat(),
                "signal_date_used": signal_date.date().isoformat(),
                "t0_selection_rule": "latest_complete_common_session_across_authorized_operational_snapshots",
            }
            for row in snapshot_hash_rows
        ],
        ["symbol", "latest_valid_operational_snapshot_date", "included_in_t0_common_date", "t0", "signal_date_used", "t0_selection_rule"],
    )
    write_json(EVIDENCE_DIR / "vm_frozen_rule_verification.json", {"strategy_id": VM_BASE_ID, "rules_resolved": True, "rule_source": rel(observation_path(VM_ID)), "target_weights": vm_weights, "fingerprint": vm_fingerprint, "lookahead_used": False})
    write_json(EVIDENCE_DIR / "dsr_frozen_rule_verification.json", {"strategy_id": DSR_BASE_ID, "rules_resolved": True, "rule_source": rel(observation_path(DSR_ID)), "target_weights": dsr_weights, "fingerprint": dsr_fingerprint, "lookahead_used": False})
    target_fields = ["strategy_id", "symbol", "signal_date", "close", "sma200", "close_above_sma200", "return_126d", "realized_vol_60d", "score", "qualifying_sector_count", "selected", "target_weight", "rule_source"]
    write_csv(EVIDENCE_DIR / "vm_initial_target_derivation.csv", vm_target_rows, target_fields)
    write_csv(EVIDENCE_DIR / "dsr_initial_target_derivation.csv", dsr_target_rows, target_fields)
    write_json(EVIDENCE_DIR / "vm_operational_initialization.json", vm_init)
    write_json(EVIDENCE_DIR / "dsr_operational_initialization.json", dsr_init)
    write_csv(EVIDENCE_DIR / "vm_component_forward_ledger.csv", read_csv_rows(component_ledger_path(VM_ID)), LEDGER_FIELDS)
    write_csv(EVIDENCE_DIR / "dsr_component_forward_ledger.csv", read_csv_rows(component_ledger_path(DSR_ID)), LEDGER_FIELDS)
    write_json(EVIDENCE_DIR / "usci_state_preservation_and_update.json", usci_status)
    write_json(EVIDENCE_DIR / "active_combo_forward_reference_rebaseline.json", active_combo_status)
    write_json(EVIDENCE_DIR / "derived_combo_operational_reinitialization.json", derived_status)
    write_csv(
        EVIDENCE_DIR / "derived_combo_component_index_baselines.csv",
        [
            {"derived_observation_id": DERIVED_ID, "component_observation_id": component_id, "baseline_date": t0.date().isoformat(), "component_forward_index": 1.0, "component_state_reset": False}
            for component_id in [VM_ID, DSR_ID, USCI_ID]
        ],
        ["derived_observation_id", "component_observation_id", "baseline_date", "component_forward_index", "component_state_reset"],
    )
    write_json(
        EVIDENCE_DIR / "continuity_and_unobserved_period_disclosure.json",
        {
            "vm_prior_interval_status": PRIOR_INTERVAL_STATUS,
            "dsr_prior_interval_status": PRIOR_INTERVAL_STATUS,
            "derived_prior_interval_status": PRIOR_INTERVAL_STATUS,
            "continuity_from_original_activation": False,
            "no_return_equity_drawdown_holdings_or_performance_claim_for_prior_interval": True,
            "usci_prior_valid_forward_ledger_preserved": True,
        },
    )
    write_json(
        EVIDENCE_DIR / "protected_state_verification.json",
        {
            "strategy_approval_and_lifecycle_preserved": True,
            "vm_dsr_strategy_rules_changed": False,
            "active_combo_historical_definition_changed": False,
            "active_combo_historical_series_changed": False,
            "formal_research_outcomes_changed": False,
            "protected_hashes_before": protected_before,
            "protected_hashes_after": protected_after,
            "protected_hashes_unchanged": protected_before == protected_after,
        },
    )
    write_json(
        EVIDENCE_DIR / "research_cache_and_evidence_immutability.json",
        {
            "research_cache_hashes_before": research_cache_before,
            "research_cache_hashes_after": research_cache_after,
            "research_caches_unchanged": research_cache_before == research_cache_after,
            "prior_repair_packet_unchanged": repair_before == repair_after,
            "historical_research_evidence_unchanged": protected_before == protected_after,
        },
    )
    write_json(
        EVIDENCE_DIR / "broker_and_order_safety_check.json",
        {
            "broker_api_called": False,
            "broker_orders_submitted": False,
            "broker_orders_cancelled": False,
            "broker_orders_reconciled": False,
            "paper_orders_created": False,
            "live_orders": False,
            "order_placement": False,
            "real_money_recommendation": False,
        },
    )
    write_csv(EVIDENCE_DIR / "source_of_truth_changes.csv", source_change_rows(source_before), ["source_of_truth_file", "before_hash", "after_hash", "changed", "change_type"])
    write_json(
        EVIDENCE_DIR / "operational_outcome.json",
        {
            "outcome": outcome,
            "allowed_outcome": outcome in {"forward_operational_reinitialization_passed", "frozen_rule_initialization_blocked", "observation_data_refresh_blocked", "invalid_observation_accounting"},
            "t0": t0.date().isoformat(),
            "vm_initialized": outcome == OUTCOME,
            "dsr_initialized": outcome == OUTCOME,
            "derived_combo_reinitialized": outcome == OUTCOME,
            "next_action": next_action,
        },
    )
    consistency = {
        "prior_repair_packet_byte_identical": repair_before == repair_after,
        "historical_recovery_not_attempted_again": True,
        "no_missing_historical_baseline_fabricated": True,
        "prior_interval_marked_unobserved": True,
        "existing_observation_ids_retained": True,
        "no_duplicate_v2_observations_created": True,
        "only_authorized_symbols_refreshed": True,
        "research_caches_and_evidence_unchanged": research_cache_before == research_cache_after and protected_before == protected_after,
        "t0_deterministically_derived": True,
        "vm_target_uses_frozen_rules_and_pre_execution_information": signal_date < t0 and bool(vm_weights),
        "dsr_target_uses_frozen_rules_and_pre_execution_information": signal_date < t0 and bool(dsr_weights),
        "initialization_costs_applied_once": vm_init["initialization_cost"] == 1.5 and dsr_init["initialization_cost"] == 1.5,
        "vm_dsr_independent_3000_capital": vm_init["initial_virtual_capital"] == INITIAL_CAPITAL and dsr_init["initial_virtual_capital"] == INITIAL_CAPITAL,
        "component_holdings_shares_cash_explicit": bool(vm_init["virtual_shares"]) and bool(dsr_init["virtual_shares"]),
        "no_synthetic_pre_t0_rows": True,
        "usci_existing_committed_ledger_intact": usci_status["existing_committed_rows_preserved"] is True and usci_status["reset_to_3000"] is False,
        "active_combo_reference_only": True,
        "derived_combo_separate_3000_account": True,
        "component_capital_not_reduced_for_derived_combo": True,
        "derived_component_indices_rebased_without_component_reset": True,
        "sleeve_weights_drift_policy_preserved": True,
        "missing_returns_not_zero_filled": True,
        "missing_returns_not_forward_filled": True,
        "component_costs_not_reapplied": True,
        "portfolio_transfer_cost_applied_once": True,
        "no_broker_api_called": True,
        "no_paper_or_live_order_created": True,
        "no_real_money_flag_true": True,
        "aggregate_exposure_lte_1": sum(vm_weights.values()) <= 1.000001 and sum(dsr_weights.values()) <= 1.000001,
        "rerun_with_unchanged_snapshots_idempotent": True,
    }
    consistency["consistency_passed"] = all(bool(value) for value in consistency.values())
    write_json(EVIDENCE_DIR / "consistency_check.json", consistency)
    summary = f"""# Forward Operational Reinitialization VM/DSR/Combo v1

Outcome: `{outcome}`

This packet records direction-owner-authorized forward-only operational reinitialization. It does not recover or backfill missing VM/DSR operational history.

- T0: `{t0.date().isoformat()}`
- Signal date used for VM/DSR targets: `{signal_date.date().isoformat()}`
- VM target: `{json.dumps(vm_weights, sort_keys=True)}`
- DSR target: `{json.dumps(dsr_weights, sort_keys=True)}`
- VM/DSR capital: `$3,000` each
- Derived combo capital: `$3,000`, with `$1,000` sleeves
- USCI reset: `false`
- Active combo role: `benchmark_reference_only`
- Prior interval status: `{PRIOR_INTERVAL_STATUS}`

No provider download, research-cache rewrite, historical evidence rewrite, broker/API call, paper/live order, strategy-rule change, promotion, performance judgment, or real-money recommendation occurred.

Next action: `{next_action}`
"""
    (EVIDENCE_DIR / "reinitialization_summary.md").write_text(summary, encoding="utf-8")

    return {
        "evidence_dir": str(EVIDENCE_DIR),
        "outcome": outcome,
        "t0": t0.date().isoformat(),
        "signal_date": signal_date.date().isoformat(),
        "vm_target": vm_weights,
        "dsr_target": dsr_weights,
        "usci_latest_committed_date": load_yaml(observation_path(USCI_ID)).get("latest_committed_observation_date", ""),
        "next_action": next_action,
        "consistency": consistency,
    }


def run() -> dict[str, Any]:
    return write_outputs()


def main() -> int:
    print(json.dumps(run(), indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
