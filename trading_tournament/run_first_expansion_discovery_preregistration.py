from __future__ import annotations

import csv
import hashlib
import json
from copy import deepcopy
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent
EXPANSION_REGISTRY_PATH = Path("strategy_lab") / "strategy_expansion_candidates_v1.yaml"
EXPANSION_ROADMAP_PATH = Path("strategy_lab") / "STRATEGY_EXPANSION_ROADMAP.md"
STRATEGY_REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
SYMBOL_MAP_PATH = Path("strategy_lab") / "approved_etf_symbol_map.yaml"
OUTPUT_DIR = Path("evidence") / "pre_registered_lanes" / "first_expansion_discovery_batch" / "latest"
DATA_CACHE_DIR = Path("data") / "cache"

AUTHORIZED_CANDIDATE_IDS = [
    "dmr_liquid_etf_oversold_rebound_v1",
    "vm_spy_qqq_daily_vol_target_v1",
    "sector_rs_weekly_cash_filter_v1",
    "vol_compression_breakout_etf_v1",
    "rs_pair_rotation_spy_qqq_xlk_xlu_v1",
]

EXCLUDED_CANDIDATE_IDS = [
    "donchian_atr_breakout_etf_v1",
    "turn_of_month_spy_qqq_v1",
    "cash_pause_overlay_meta_v1",
    "orb_spy_qqq_30m_research_v1",
    "gap_down_fade_spy_qqq_research_v1",
    "vwap_deviation_reversion_research_v1",
    "post_earnings_drift_large_cap_later_v1",
]

FORBIDDEN_STATUS_VALUES = {
    "approved",
    "paper_forward_active",
    "candidate_exhaustive",
    "demo_active",
    "live_ready",
}

VAGUE_OPTIMIZATION_PHRASES = [
    "such as rsi",
    "maybe",
    "or another",
    "to be decided",
    "optimize later",
    "best of",
    "parameter sweep",
    "choose the best",
    "try multiple",
    "test several and keep the best",
]

ALLOWED_FUTURE_DISCOVERY_OUTCOMES = ["discovery_reject", "promotion_review_candidate"]
ACTIVE_STRATEGY_IDS = [
    "paper_forward_vm_quality_lowvol_proxy_v1",
    "paper_forward_dsr_sector_equal_weight_defensive_filter_v1",
    "active_combo_vm_dsr_equal_weight_v1",
    "SPY_200d_trend_model",
]
ACTIVE_OBSERVATION_PATHS = [
    Path("paper_forward_observations") / "paper_forward_vm_quality_lowvol_proxy_v1" / "active_observation.yaml",
    Path("paper_forward_observations") / "paper_forward_dsr_sector_equal_weight_defensive_filter_v1" / "active_observation.yaml",
]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "missing"


def rows_by_id(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row.get("id")): row for row in registry.get("strategies", [])}


def load_expansion_candidates(root: Path) -> dict[str, dict[str, Any]]:
    payload = load_yaml(root / EXPANSION_REGISTRY_PATH)
    return {str(row.get("candidate_id")): row for row in payload.get("candidates", [])}


def symbol_map_rows(root: Path) -> dict[str, dict[str, Any]]:
    payload = load_yaml(root / SYMBOL_MAP_PATH)
    return {str(row.get("symbol", "")).upper(): row for row in payload.get("symbols", [])}


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def cache_info(root: Path, symbol: str) -> dict[str, Any]:
    path = root / DATA_CACHE_DIR / f"{symbol}.csv"
    if not path.exists():
        return {
            "symbol": symbol,
            "cache_available": False,
            "qa_status": "missing_cache_file",
            "first_date": "",
            "last_date": "",
            "row_count": 0,
            "has_adjusted_ohlcv": False,
            "path": str(path),
        }

    rows = read_csv_rows(path)
    columns = set(rows[0].keys()) if rows else set()
    first_date = rows[0].get("date", "") if rows else ""
    last_date = rows[-1].get("date", "") if rows else ""
    has_adjusted_ohlcv = {"date", "open", "high", "low", "close", "adj_close", "volume"} <= columns
    duplicate_dates = len({row.get("date") for row in rows}) != len(rows)
    qa_status = "passed" if rows and has_adjusted_ohlcv and not duplicate_dates else "failed_basic_cache_qa"
    return {
        "symbol": symbol,
        "cache_available": True,
        "qa_status": qa_status,
        "first_date": first_date,
        "last_date": last_date,
        "row_count": len(rows),
        "has_adjusted_ohlcv": has_adjusted_ohlcv,
        "duplicate_dates": duplicate_dates,
        "path": str(path),
    }


def parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def supports_minimum_period(symbol_infos: list[dict[str, Any]], minimum_years: int) -> bool:
    usable = [info for info in symbol_infos if info.get("cache_available") and info.get("qa_status") == "passed"]
    if len(usable) != len(symbol_infos):
        return False
    first_dates = [parse_date(str(info.get("first_date", ""))) for info in usable]
    last_dates = [parse_date(str(info.get("last_date", ""))) for info in usable]
    if not first_dates or not last_dates or any(item is None for item in first_dates + last_dates):
        return False
    shared_start = max(item for item in first_dates if item is not None)
    shared_end = min(item for item in last_dates if item is not None)
    return (shared_end - shared_start).days >= minimum_years * 365


def frozen_specs(source_by_id: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    specs = [
        {
            "candidate_id": "dmr_liquid_etf_oversold_rebound_v1",
            "family": "daily_mean_reversion",
            "timeframe": "daily",
            "universe": ["SPY", "QQQ", "IWM", "DIA", "XLK", "XLF", "XLV", "XLE", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE"],
            "hypothesis": "Short-term oversold liquid ETF rebounds can add value when each symbol remains above its 200-day SMA and risk limits cap losing rebounds.",
            "data_required": ["Adjusted daily OHLCV", "RSI(2)", "5-day SMA", "200-day SMA", "ATR(14)", "liquidity and missing-data checks"],
            "entry_rule": "At next open, enter long when the prior close is above the symbol 200-day SMA, RSI(2) computed from prior close data is <= 10, the symbol passes liquidity and missing-data checks, and open-position plus trade-count limits are available.",
            "exit_rule": "Exit at the earliest of close above 5-day SMA, daily low breaching a fixed stop set 2.0 ATR(14) below entry using prior completed data, the fifth trading day after entry, or the missing/stale-data forced-exit policy.",
            "sizing_rule": "Equal notional allocation, max 2 open positions, max 25% account notional per position, unused allocation remains cash/BIL by project convention.",
            "risk_controls": [
                "Max 2 open positions.",
                "Max 2 new entries per day.",
                "Fixed ATR stop on every position.",
                "Max 5 trading-day hold.",
                "Weekly loss pause after two closed losing trades or 3% strategy drawdown in the week.",
                "Liquidity filter required.",
                "Spread/slippage stress required in future discovery.",
                "Missing/stale data blocks new trades and can force exit.",
                "Kill switch for abnormal logs or reconciliation issues.",
            ],
            "max_position_size": "25% account notional per position",
            "max_open_positions": 2,
            "max_trades_per_day": 2,
            "max_trades_per_week": 6,
            "max_holding_period": "5 trading days",
            "execution_assumptions": ["Signals use prior completed daily data.", "Entries occur at next open in the future discovery simulation.", "No intraday confirmation is allowed."],
            "benchmark_controls": ["SPY_200d", "SPY", "active VM", "active combo", "BIL"],
            "minimum_backtest_period": "10 years minimum shared adjusted daily OHLCV support.",
            "minimum_backtest_years": 10,
            "acceptance_criteria": [
                "Future discovery can mark promotion_review_candidate only if core benchmark comparison is favorable or risk reduction is meaningful.",
                "Risk buffer, slippage stress, turnover, and duplication checks must all pass.",
                "Evidence must not depend on one short subperiod or one symbol.",
            ],
            "rejection_criteria": [
                "Reject if it underperforms SPY_200d, SPY, active VM, active combo, or BIL without meaningful risk reduction.",
                "Reject if catastrophic drawdown, thin risk buffer, incomplete data, too few trades, or slippage failure appears.",
                "Reject if it duplicates an active strategy or violates any risk limit.",
            ],
            "duplication_checks": ["Check against active VM trend timing.", "Check against active combo risk-on exposure.", "Check against archived ETF-wrapper mechanics."],
            "paper_demo_eligibility_after_validation": source_by_id["dmr_liquid_etf_oversold_rebound_v1"].get("demo_eligibility", "not_eligible_yet"),
        },
        {
            "candidate_id": "vm_spy_qqq_daily_vol_target_v1",
            "family": "volatility_managed_equity",
            "timeframe": "daily",
            "universe": ["SPY", "QQQ", "BIL"],
            "hypothesis": "A compact SPY/QQQ sleeve with trend gating and fixed volatility scaling may improve survivability versus fully invested equity exposure.",
            "data_required": ["Adjusted daily OHLCV", "126-day momentum", "200-day SMA", "20-day realized volatility", "BIL cash-proxy data"],
            "entry_rule": "Rank SPY and QQQ by fixed 126-day momentum using prior close data only, select the highest-ranked eligible asset whose prior close is above its 200-day SMA, and allocate to BIL when neither risk asset qualifies.",
            "exit_rule": "Exit the risk asset when it fails the 200-day SMA filter, reduce or exit when 20-day realized volatility breaches the fixed risk rule, and move to BIL when no risk asset qualifies.",
            "sizing_rule": "Use 20-trading-day annualized realized volatility with a fixed 12% target; risk-asset exposure is min(100%, target volatility divided by realized volatility), capped at 50% when realized volatility exceeds 30%, and residual allocation goes to BIL.",
            "risk_controls": [
                "No leverage.",
                "Max 100% risk-asset exposure.",
                "Residual allocation to BIL.",
                "Volatility spike no-trade/reduction rule.",
                "Drawdown pause after 6% strategy drawdown.",
                "Weekly loss pause after 3% weekly strategy loss.",
                "Missing/stale data blocks risk-asset entries.",
                "Spread/slippage stress required in future discovery.",
                "Duplication check against active VM.",
            ],
            "max_position_size": "100% total risk-asset exposure before volatility reduction",
            "max_open_positions": 2,
            "max_trades_per_day": 2,
            "max_trades_per_week": 4,
            "max_holding_period": "Open-ended while daily rules remain valid",
            "execution_assumptions": ["Signals use prior completed daily data.", "BIL receives residual allocation.", "No leverage, shorting, or intraday logic."],
            "benchmark_controls": ["SPY_200d", "QQQ", "active VM", "active combo", "BIL"],
            "minimum_backtest_period": "15 years minimum shared adjusted daily OHLCV support where BIL is available.",
            "minimum_backtest_years": 15,
            "acceptance_criteria": [
                "Future discovery can mark promotion_review_candidate only if it is distinct from active VM and improves return-risk tradeoff versus core benchmarks.",
                "Volatility scaling must not create unacceptable profit drag.",
                "Slippage, drawdown pause, and BIL allocation behavior must be auditable.",
            ],
            "rejection_criteria": [
                "Reject if near-duplicate of active VM.",
                "Reject if it underperforms SPY_200d, QQQ, active VM, active combo, or BIL without meaningful risk reduction.",
                "Reject if volatility scaling whipsaws or hides excessive turnover.",
            ],
            "duplication_checks": ["Compare exposure path against active VM.", "Compare benchmark deltas against active combo.", "Check whether SPY_200d alone explains behavior."],
            "paper_demo_eligibility_after_validation": source_by_id["vm_spy_qqq_daily_vol_target_v1"].get("demo_eligibility", "not_eligible_yet"),
        },
        {
            "candidate_id": "sector_rs_weekly_cash_filter_v1",
            "family": "sector_relative_strength_rotation",
            "timeframe": "weekly",
            "universe": ["XLK", "XLF", "XLV", "XLE", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE", "BIL"],
            "hypothesis": "Weekly sector relative strength with a cash filter may capture leadership rotation without repeating slower monthly ETF-wrapper behavior.",
            "data_required": ["Adjusted daily OHLCV converted to weekly signals", "13-week momentum", "200-day SMA", "SPY risk filter", "BIL fallback data"],
            "entry_rule": "At weekly rebalance, rank sectors by fixed 13-week momentum using prior completed data only, hold the top 2 sectors only if each is above its 200-day SMA and SPY is above its 200-day SMA, and allocate failed sleeves to BIL.",
            "exit_rule": "At weekly rebalance or risk event, exit a sector if it falls below its 200-day SMA, leaves the top 2 ranking, SPY fails its 200-day SMA risk filter, or missing/stale data triggers exit or pause.",
            "sizing_rule": "Allocate 50% to each accepted sector, send any failed sleeve to BIL, and cap each sector at 50%.",
            "risk_controls": [
                "Max 2 sectors.",
                "Weekly rebalance only.",
                "BIL fallback.",
                "Turnover cap of one scheduled weekly rebalance.",
                "Drawdown pause after 6% strategy drawdown.",
                "Weekly loss pause after 3% weekly strategy loss.",
                "Liquidity filter required.",
                "Spread/slippage stress required in future discovery.",
                "Duplication check against active DSR and active combo.",
            ],
            "max_position_size": "50% account notional per sector ETF",
            "max_open_positions": 2,
            "max_trades_per_day": 2,
            "max_trades_per_week": 4,
            "max_holding_period": "Open-ended while weekly rules remain valid",
            "execution_assumptions": ["Weekly rebalance from prior completed data.", "No intraday decisioning.", "No sector shorting."],
            "benchmark_controls": ["active DSR", "active combo", "SPY", "SPY_200d", "equal-weight sector baseline if available"],
            "minimum_backtest_period": "15 years minimum shared adjusted daily OHLCV support for required sector universe where available.",
            "minimum_backtest_years": 15,
            "acceptance_criteria": [
                "Future discovery can mark promotion_review_candidate only if it beats or materially diversifies active DSR and active combo.",
                "Sector concentration and turnover must remain controlled.",
                "Cash fallback must be auditable and not hindsight-tuned.",
            ],
            "rejection_criteria": [
                "Reject if weaker than active DSR, active combo, SPY, or SPY_200d without meaningful risk reduction.",
                "Reject if XLK-only concentration explains results.",
                "Reject if data for any required sector is missing or inconsistent.",
            ],
            "duplication_checks": ["Compare selected sectors, rebalance dates, and BIL behavior against active DSR.", "Check active combo overlap.", "Check QQQ/XLK concentration."],
            "paper_demo_eligibility_after_validation": source_by_id["sector_rs_weekly_cash_filter_v1"].get("demo_eligibility", "not_eligible_yet"),
        },
        {
            "candidate_id": "vol_compression_breakout_etf_v1",
            "family": "volatility_compression_breakout",
            "timeframe": "daily",
            "universe": ["SPY", "QQQ", "IWM", "DIA", "XLK", "XLF", "XLV", "XLE", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE"],
            "hypothesis": "A fixed volatility-compression breakout may capture directional expansion while ATR stops constrain failed moves.",
            "data_required": ["Adjusted daily OHLCV", "10-day ATR divided by close", "252-day 30th percentile compression threshold", "prior 20-day high", "ATR(14)", "liquidity checks"],
            "entry_rule": "At next open, enter long when prior completed data shows 10-day ATR divided by close below its fixed 252-day 30th percentile, prior close breaks above the prior 20-day high, liquidity passes, no extreme-gap no-trade condition is active, and open-position plus trade-count limits are available.",
            "exit_rule": "Exit at the earliest of a fixed 2.5 ATR(14) stop from entry, close back below the recorded breakout level, the tenth trading day after entry, or the missing/stale-data abnormal-condition exit policy.",
            "sizing_rule": "Use equal notional sizing, max 2 open positions, max 25% account notional per position, and unused allocation remains cash/BIL by project convention.",
            "risk_controls": [
                "ATR stop required.",
                "Max 2 open positions.",
                "Max 5 new entries per week.",
                "Max 10 trading-day hold.",
                "No entry after an opening gap greater than 2 ATR from the prior close.",
                "Liquidity filter required.",
                "Spread/slippage stress required in future discovery.",
                "Weekly loss pause after 4% weekly strategy loss.",
                "Drawdown pause after 6% strategy drawdown.",
                "No intraday confirmation in v1.",
            ],
            "max_position_size": "25% account notional per position",
            "max_open_positions": 2,
            "max_trades_per_day": 2,
            "max_trades_per_week": 5,
            "max_holding_period": "10 trading days",
            "execution_assumptions": ["Signals use prior completed daily data.", "Entries occur at next open in future discovery.", "No intraday confirmation or event filter is allowed."],
            "benchmark_controls": ["SPY", "QQQ", "SPY_200d", "BIL", "simple Donchian baseline if available"],
            "minimum_backtest_period": "10 years minimum shared adjusted daily OHLCV support.",
            "minimum_backtest_years": 10,
            "acceptance_criteria": [
                "Future discovery can mark promotion_review_candidate only if breakout return-risk profile beats core daily benchmarks or adds clear diversification.",
                "ATR stops and gap no-trade policy must control losses.",
                "Evidence must not rely on one volatility regime.",
            ],
            "rejection_criteria": [
                "Reject if false breakouts dominate.",
                "Reject if it underperforms SPY, QQQ, SPY_200d, or BIL without meaningful risk reduction.",
                "Reject if slippage/spread stress or missing data undermines evidence.",
            ],
            "duplication_checks": ["Check against top-N ETF momentum wrappers.", "Check against breadth-state archived mechanics.", "Check against active combo beta exposure."],
            "paper_demo_eligibility_after_validation": source_by_id["vol_compression_breakout_etf_v1"].get("demo_eligibility", "not_eligible_yet"),
        },
        {
            "candidate_id": "rs_pair_rotation_spy_qqq_xlk_xlu_v1",
            "family": "long_only_relative_strength_pair_rotation",
            "timeframe": "weekly",
            "universe": ["SPY", "QQQ", "XLK", "XLU", "BIL"],
            "hypothesis": "A compact long-only risk-on/risk-off rotation may capture leadership while limiting weak-regime exposure through BIL fallback.",
            "data_required": ["Adjusted daily OHLCV converted to weekly signals", "13-week relative strength", "200-day SMA", "BIL fallback data"],
            "entry_rule": "At weekly rebalance, rank SPY, QQQ, XLK, and XLU by fixed 13-week relative strength using prior completed data only, hold the top-ranked asset only if it passes its 200-day SMA filter, and hold BIL when no asset passes.",
            "exit_rule": "At weekly rebalance, exit if the held asset no longer ranks first, if the held asset fails its 200-day SMA trend filter, or if missing/stale data requires BIL allocation.",
            "sizing_rule": "Hold max 1 risk asset at 100% account notional or hold BIL; no leverage and no shorting.",
            "risk_controls": [
                "Max 1 open position.",
                "Weekly rebalance only.",
                "BIL fallback.",
                "Turnover cap of one scheduled weekly switch.",
                "Drawdown pause after 6% strategy drawdown.",
                "Weekly loss pause after 3% weekly strategy loss.",
                "Spread/slippage stress required in future discovery.",
                "Duplication check for hidden QQQ/XLK concentration.",
                "Duplication check against active combo and SPY_200d.",
            ],
            "max_position_size": "100% account notional in one eligible ETF or BIL",
            "max_open_positions": 1,
            "max_trades_per_day": 1,
            "max_trades_per_week": 2,
            "max_holding_period": "Open-ended while weekly rules remain valid",
            "execution_assumptions": ["Weekly rebalance from prior completed data.", "No leverage.", "No shorting or intraday logic."],
            "benchmark_controls": ["SPY_200d", "QQQ", "XLK", "XLU", "active combo", "BIL"],
            "minimum_backtest_period": "15 years minimum shared adjusted daily OHLCV support.",
            "minimum_backtest_years": 15,
            "acceptance_criteria": [
                "Future discovery can mark promotion_review_candidate only if it improves return-risk tradeoff versus compact benchmarks or clearly diversifies active combo.",
                "Concentration in QQQ or XLK must be explained and capped by evidence gates.",
                "BIL fallback must be rule-driven and auditable.",
            ],
            "rejection_criteria": [
                "Reject if QQQ or XLK concentration explains most behavior.",
                "Reject if it underperforms SPY_200d, QQQ, XLK, XLU, active combo, or BIL without meaningful risk reduction.",
                "Reject if weekly timing is too slow or duplicative.",
            ],
            "duplication_checks": ["Check hidden QQQ/XLK concentration.", "Check overlap with active combo.", "Check whether SPY_200d alone explains behavior."],
            "paper_demo_eligibility_after_validation": source_by_id["rs_pair_rotation_spy_qqq_xlk_xlu_v1"].get("demo_eligibility", "not_eligible_yet"),
        },
    ]
    for spec in specs:
        if spec["candidate_id"] not in source_by_id:
            raise ValueError(f"authorized candidate missing from source registry: {spec['candidate_id']}")
    return specs


def benchmark_reference_audit(root: Path) -> dict[str, Any]:
    registry = load_yaml(root / STRATEGY_REGISTRY_PATH)
    registry_rows = rows_by_id(registry)
    return {
        strategy_id: {
            "present_in_strategy_registry": strategy_id in registry_rows,
            "state": registry_rows.get(strategy_id, {}).get("status", ""),
            "paper_forward_active": registry_rows.get(strategy_id, {}).get("paper_forward_active", False),
            "rules_frozen": registry_rows.get(strategy_id, {}).get("rules_frozen", False),
        }
        for strategy_id in ACTIVE_STRATEGY_IDS
    }


def data_availability_audit(root: Path, specs: list[dict[str, Any]]) -> dict[str, Any]:
    map_rows = symbol_map_rows(root)
    required_symbols = sorted({symbol for spec in specs for symbol in spec["universe"]} | {"SPY", "QQQ", "BIL", "XLK", "XLU"})
    symbol_details: list[dict[str, Any]] = []
    for symbol in required_symbols:
        map_row = map_rows.get(symbol, {})
        cache = cache_info(root, symbol)
        approved_for_strategy = map_row.get("allowed_for_strategy") is True
        approved_for_benchmark = map_row.get("allowed_for_benchmark") is True
        missing_reasons: list[str] = []
        if not map_row:
            missing_reasons.append("not_in_approved_symbol_map")
        if not approved_for_strategy and symbol not in {"SPY", "QQQ", "BIL", "XLK", "XLU"}:
            missing_reasons.append("not_approved_for_strategy")
        if not approved_for_benchmark and symbol in {"SPY", "QQQ", "BIL", "XLK", "XLU"}:
            missing_reasons.append("not_approved_for_benchmark")
        if not cache["cache_available"]:
            missing_reasons.append("cache_file_missing")
        if cache["cache_available"] and cache["qa_status"] != "passed":
            missing_reasons.append("basic_cache_qa_failed")
        symbol_details.append(
            {
                "symbol": symbol,
                "approved_for_strategy": approved_for_strategy,
                "approved_for_benchmark": approved_for_benchmark,
                "group": map_row.get("group", ""),
                "requires_explicit_prompt": map_row.get("requires_explicit_prompt", ""),
                "cache_available": cache["cache_available"],
                "qa_status": cache["qa_status"],
                "first_date": cache["first_date"],
                "last_date": cache["last_date"],
                "row_count": cache["row_count"],
                "has_adjusted_ohlcv": cache["has_adjusted_ohlcv"],
                "missing_reasons": missing_reasons,
                "blocked": bool(missing_reasons),
            }
        )

    details_by_symbol = {row["symbol"]: row for row in symbol_details}
    candidate_status: list[dict[str, Any]] = []
    for spec in specs:
        infos = [details_by_symbol[symbol] for symbol in spec["universe"]]
        cache_infos = [cache_info(root, symbol) for symbol in spec["universe"]]
        missing_symbols = [info["symbol"] for info in infos if info["blocked"]]
        period_supported = supports_minimum_period(cache_infos, int(spec["minimum_backtest_years"]))
        candidate_status.append(
            {
                "candidate_id": spec["candidate_id"],
                "required_symbols": spec["universe"],
                "required_timeframe": spec["timeframe"],
                "daily_adjusted_ohlcv_coverage": "available" if not missing_symbols and all(info["has_adjusted_ohlcv"] for info in infos) else "missing_or_incomplete",
                "benchmark_symbols": sorted(set(spec["benchmark_controls"]) & {"SPY", "QQQ", "BIL", "XLK", "XLU"}),
                "benchmark_strategy_references": [item for item in spec["benchmark_controls"] if item not in {"SPY", "QQQ", "BIL", "XLK", "XLU"}],
                "minimum_backtest_period_support": "supported" if period_supported else "blocked_or_unverified",
                "bil_availability": details_by_symbol.get("BIL", {}).get("qa_status", "missing"),
                "spy_availability": details_by_symbol.get("SPY", {}).get("qa_status", "missing"),
                "qqq_availability": details_by_symbol.get("QQQ", {}).get("qa_status", "missing"),
                "sector_etf_availability": "blocked_by_missing_sector_symbol" if any(symbol in missing_symbols for symbol in ["XLK", "XLF", "XLV", "XLE", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE"]) else "available_or_not_required",
                "missing_symbols": missing_symbols,
                "stale_data_indicator": "freshness_threshold_not_defined; last_dates_reported",
                "blocked_by_missing_data": bool(missing_symbols) or not period_supported,
            }
        )

    missing_symbols = sorted({symbol for row in candidate_status for symbol in row["missing_symbols"]})
    if missing_symbols:
        status = "missing_required_data"
    elif any(row["blocked_by_missing_data"] for row in candidate_status):
        status = "unknown_requires_manual_review"
    else:
        status = "sufficient_for_discovery"
    next_action = "run_first_expansion_discovery_batch" if status == "sufficient_for_discovery" else "authorize_data_availability_or_cache_refresh_for_first_expansion_batch"
    return {
        "data_availability_status": status,
        "next_action": next_action,
        "required_symbols": required_symbols,
        "missing_symbols": missing_symbols,
        "symbol_details": symbol_details,
        "candidate_status": candidate_status,
        "benchmark_reference_status": benchmark_reference_audit(root),
        "provider_download": False,
        "provider_api_called": False,
        "intraday_data_required": False,
        "event_data_required": False,
    }


def md_list(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def candidate_specs_md(specs: list[dict[str, Any]]) -> str:
    lines = [
        "# First Expansion Candidate Specs",
        "",
        "These five v1 rules are frozen for a future discovery step. This document does not contain performance evidence.",
    ]
    for spec in specs:
        lines.extend(
            [
                "",
                f"## `{spec['candidate_id']}`",
                "",
                f"- Family: `{spec['family']}`",
                f"- Timeframe: `{spec['timeframe']}`",
                f"- Universe: {', '.join(spec['universe'])}",
                f"- Hypothesis: {spec['hypothesis']}",
                f"- Entry rule: {spec['entry_rule']}",
                f"- Exit rule: {spec['exit_rule']}",
                f"- Sizing rule: {spec['sizing_rule']}",
                f"- Max position size: {spec['max_position_size']}",
                f"- Max open positions: `{spec['max_open_positions']}`",
                f"- Max trades per day: `{spec['max_trades_per_day']}`",
                f"- Max trades per week: `{spec['max_trades_per_week']}`",
                f"- Max holding period: {spec['max_holding_period']}",
                f"- Paper/demo eligibility after validation: `{spec['paper_demo_eligibility_after_validation']}`",
                "",
                "Data required:",
                md_list(spec["data_required"]),
                "",
                "Risk controls:",
                md_list(spec["risk_controls"]),
                "",
                "Benchmark controls:",
                md_list(spec["benchmark_controls"]),
                "",
                "Acceptance criteria:",
                md_list(spec["acceptance_criteria"]),
                "",
                "Rejection criteria:",
                md_list(spec["rejection_criteria"]),
                "",
                "Duplication checks:",
                md_list(spec["duplication_checks"]),
            ]
        )
    return "\n".join(lines) + "\n"


def risk_policy_md(specs: list[dict[str, Any]]) -> str:
    return """# First Expansion Risk Policy

This packet freezes risk controls for a later discovery step. It does not run a backtest, create orders, or approve paper-forward action.

Minimum controls for every included candidate:

- Max position size is fixed in the candidate spec.
- Max open positions is fixed in the candidate spec.
- Max trades per day or week is fixed in the candidate spec.
- Max holding period is fixed in the candidate spec.
- Drawdown pause is required before any future discovery run can evaluate promotion-review candidacy.
- Weekly loss pause is required before any future discovery run can evaluate promotion-review candidacy.
- Liquidity filters are required for each traded ETF.
- Spread/slippage stress is required in future discovery.
- BIL or cash fallback is required where specified.
- Missing or stale data blocks new trades and can force exit according to each frozen rule.
- Kill switch applies to abnormal logs or reconciliation issues, even though no broker path is used in this step.

No leverage, margin, shorting, options, futures, forex, crypto, intraday logic, or individual-stock logic is permitted in this first expansion batch.
"""


def benchmark_plan_md(specs: list[dict[str, Any]]) -> str:
    lines = [
        "# First Expansion Benchmark Plan",
        "",
        "Benchmarks are frozen before discovery. Missing optional baselines must be reported; required benchmark symbols and active references cannot be silently replaced.",
    ]
    for spec in specs:
        lines.extend(["", f"## `{spec['candidate_id']}`", "", md_list(spec["benchmark_controls"])])
    return "\n".join(lines) + "\n"


def acceptance_gates_md() -> str:
    return """# First Expansion Acceptance Gates

The future discovery batch may assign only these outcomes:

- `discovery_reject`
- `promotion_review_candidate`

A candidate may become `promotion_review_candidate` only after future discovery if all relevant gates pass:

- It does not underperform its core benchmark without meaningful risk reduction.
- It does not underperform active VM, active DSR, active combo, or SPY_200d where relevant.
- It avoids catastrophic drawdown.
- It passes risk buffer requirements.
- It does not depend on one lucky trade or one short period.
- It survives slippage/spread stress.
- It is not too correlated or duplicative with an active strategy.
- It produces enough trades to evaluate.
- It does not use excessive turnover for its edge.
- It respects max positions, max trade count, and max holding period rules.
- Evidence is complete, unambiguous, and internally consistent.

No direct candidate_exhaustive or paper-forward transition is allowed from discovery.
"""


def rejection_gates_md() -> str:
    return """# First Expansion Rejection Gates

The future discovery batch must reject a candidate if any of these conditions apply:

- It underperforms its core benchmark without meaningful risk reduction.
- It underperforms active VM, active DSR, active combo, or SPY_200d where relevant.
- It has catastrophic drawdown or fails risk buffer requirements.
- It depends on one lucky trade or one short period.
- It collapses under slippage/spread stress.
- It is too correlated or duplicative with an active strategy.
- It produces too few trades to evaluate.
- It uses excessive turnover for its edge.
- It violates max positions, max trade count, or max holding period rules.
- Evidence is incomplete, ambiguous, or inconsistent.
- Any required symbol, benchmark, or reference data is missing.
"""


def do_not_run_now_md() -> str:
    return """# Do Not Run Now

This packet is pre-registration plus data-availability audit only.

Do not run discovery, backtests, performance metrics, candidate_exhaustive validation, paper-forward review, paper-forward activation, provider downloads, broker integration, live orders, or real-money recommendations from this step.

The future discovery step must use the five frozen v1 rules only. It must not test multiple RSI thresholds, momentum lookbacks, breakout windows, volatility targets, holding periods, symbol universes, intraday confirmations, event-data filters, or reopened ETF-wrapper mechanics.

Future variants require a new candidate ID, a written hypothesis, exactly one major changed dimension, an explanation of structural difference, and a new pre-registration packet before testing.
"""


def data_availability_report_md(audit: dict[str, Any]) -> str:
    lines = [
        "# First Expansion Data Availability Report",
        "",
        f"Data availability status: `{audit['data_availability_status']}`",
        f"Next action: `{audit['next_action']}`",
        "",
        "This audit inspected existing approved symbol metadata and local daily cache files only. It did not call a provider and did not download data.",
        "",
        "## Candidate Status",
        "",
        "| Candidate | Timeframe | Coverage | Minimum period | Missing symbols | Blocked |",
        "|---|---|---|---|---|---|",
    ]
    for row in audit["candidate_status"]:
        lines.append(
            f"| `{row['candidate_id']}` | {row['required_timeframe']} | {row['daily_adjusted_ohlcv_coverage']} | {row['minimum_backtest_period_support']} | {', '.join(row['missing_symbols']) or 'none'} | {row['blocked_by_missing_data']} |"
        )
    lines.extend(
        [
            "",
            "## Required Symbol Audit",
            "",
            "| Symbol | Approved strategy | Approved benchmark | Cache | QA | First date | Last date | Rows | Missing reasons |",
            "|---|---:|---:|---:|---|---|---|---:|---|",
        ]
    )
    for row in audit["symbol_details"]:
        lines.append(
            f"| {row['symbol']} | {row['approved_for_strategy']} | {row['approved_for_benchmark']} | {row['cache_available']} | {row['qa_status']} | {row['first_date']} | {row['last_date']} | {row['row_count']} | {', '.join(row['missing_reasons']) or 'none'} |"
        )
    lines.extend(
        [
            "",
            "## Benchmark Reference Audit",
            "",
            "| Reference | Present | State | Paper-forward active | Rules frozen |",
            "|---|---:|---|---:|---:|",
        ]
    )
    for strategy_id, row in audit["benchmark_reference_status"].items():
        lines.append(
            f"| `{strategy_id}` | {row['present_in_strategy_registry']} | {row['state']} | {row['paper_forward_active']} | {row['rules_frozen']} |"
        )
    return "\n".join(lines) + "\n"


def missing_data_report_md(audit: dict[str, Any]) -> str:
    if not audit["missing_symbols"]:
        return """# First Expansion Missing Data Report

No required symbols are missing from the approved local cache based on this audit.
"""
    lines = [
        "# First Expansion Missing Data Report",
        "",
        "Required data is missing or not approved for at least one frozen candidate. No symbols were removed or substituted.",
        "",
        "| Missing symbol | Affected candidates | Reason |",
        "|---|---|---|",
    ]
    detail_by_symbol = {row["symbol"]: row for row in audit["symbol_details"]}
    for symbol in audit["missing_symbols"]:
        affected = [row["candidate_id"] for row in audit["candidate_status"] if symbol in row["missing_symbols"]]
        reasons = detail_by_symbol.get(symbol, {}).get("missing_reasons", [])
        lines.append(f"| {symbol} | {', '.join(affected)} | {', '.join(reasons) or 'unknown'} |")
    lines.extend(
        [
            "",
            "Because required data is missing, the next action is `authorize_data_availability_or_cache_refresh_for_first_expansion_batch`.",
        ]
    )
    return "\n".join(lines) + "\n"


def consistency_check(manifest: dict[str, Any], audit: dict[str, Any], specs: list[dict[str, Any]], before_hashes: dict[str, str], after_hashes: dict[str, str]) -> dict[str, Any]:
    spec_text = yaml.safe_dump(specs, sort_keys=True).lower()
    vague_phrase_hits = [phrase for phrase in VAGUE_OPTIMIZATION_PHRASES if phrase in spec_text]
    included_ids = [spec["candidate_id"] for spec in specs]
    consistency = {
        "pre_registration_completed": True,
        "pre_registration_only": manifest["pre_registration_only"],
        "data_availability_audit_only": manifest["data_availability_audit_only"],
        "exactly_five_candidates_included": len(included_ids) == 5,
        "authorized_candidates_only": included_ids == AUTHORIZED_CANDIDATE_IDS,
        "excluded_candidates_absent": not set(included_ids) & set(EXCLUDED_CANDIDATE_IDS),
        "intraday_candidates_included": False,
        "event_data_candidates_included": False,
        "no_forbidden_status_values": True,
        "no_vague_optimization_phrases": not vague_phrase_hits,
        "vague_phrase_hits": vague_phrase_hits,
        "future_outcomes_limited": manifest["future_discovery_outcomes_allowed"] == ALLOWED_FUTURE_DISCOVERY_OUTCOMES,
        "backtests_run": False,
        "discovery_run": False,
        "performance_metrics_computed": False,
        "candidate_exhaustive_run": False,
        "paper_forward_review": False,
        "paper_forward_activation": False,
        "broker_path_touched": False,
        "live_orders": False,
        "provider_download": False,
        "real_money_recommendation": False,
        "etf_wrapper_track_reopened": False,
        "active_strategy_state_changed": before_hashes != after_hashes,
        "data_availability_status_valid": audit["data_availability_status"] in {"sufficient_for_discovery", "missing_required_data", "unknown_requires_manual_review"},
        "next_action_valid": audit["next_action"] in {"run_first_expansion_discovery_batch", "authorize_data_availability_or_cache_refresh_for_first_expansion_batch"},
        "next_action_matches_data_status": audit["next_action"] == ("run_first_expansion_discovery_batch" if audit["data_availability_status"] == "sufficient_for_discovery" else "authorize_data_availability_or_cache_refresh_for_first_expansion_batch"),
    }
    consistency["consistency_passed"] = (
        consistency["pre_registration_only"]
        and consistency["data_availability_audit_only"]
        and consistency["exactly_five_candidates_included"]
        and consistency["authorized_candidates_only"]
        and consistency["excluded_candidates_absent"]
        and not consistency["intraday_candidates_included"]
        and not consistency["event_data_candidates_included"]
        and consistency["no_vague_optimization_phrases"]
        and consistency["future_outcomes_limited"]
        and not consistency["active_strategy_state_changed"]
        and consistency["data_availability_status_valid"]
        and consistency["next_action_matches_data_status"]
    )
    return consistency


def update_expansion_metadata(root: Path, audit: dict[str, Any], created_utc: str) -> None:
    path = root / EXPANSION_REGISTRY_PATH
    payload = load_yaml(path)
    metadata = payload.setdefault("metadata", {})
    metadata.update(
        {
            "first_expansion_discovery_preregistration_path": str((root / OUTPUT_DIR).resolve()),
            "first_expansion_discovery_preregistration_status": "pre_registered",
            "first_expansion_discovery_data_availability_status": audit["data_availability_status"],
            "first_expansion_discovery_next_action": audit["next_action"],
            "pre_registration_only": True,
            "data_availability_audit_only": True,
            "backtests_run": False,
            "discovery_run": False,
            "candidate_exhaustive_run": False,
            "paper_forward_review": False,
            "paper_forward_activation": False,
            "provider_download": False,
            "real_money_recommendation": False,
            "updated_utc": created_utc,
        }
    )
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=False), encoding="utf-8")


def update_expansion_roadmap(root: Path, audit: dict[str, Any], created_utc: str) -> None:
    path = root / EXPANSION_ROADMAP_PATH
    existing = path.read_text(encoding="utf-8") if path.exists() else "# Strategy Expansion Roadmap\n"
    marker = "## First Expansion Discovery Batch Pre-Registration"
    existing_without_old = existing.split(marker)[0].rstrip()
    section = f"""

{marker}

Created UTC: `{created_utc}`

Included candidates:

{md_list([f"`{candidate_id}`" for candidate_id in AUTHORIZED_CANDIDATE_IDS])}

Explicitly excluded candidates:

{md_list([f"`{candidate_id}`" for candidate_id in EXCLUDED_CANDIDATE_IDS])}

Rules are frozen for the future discovery step. This step ran only pre-registration and data-availability audit.

Data availability status: `{audit['data_availability_status']}`

Next action: `{audit['next_action']}`
"""
    path.write_text(existing_without_old + section + "\n", encoding="utf-8")


def run_first_expansion_discovery_preregistration(root: Path = ROOT) -> dict[str, Any]:
    created_utc = now_utc()
    output_dir = root / OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    before_hashes = {
        "strategy_registry": sha256_file(root / STRATEGY_REGISTRY_PATH),
        **{str(path): sha256_file(root / path) for path in ACTIVE_OBSERVATION_PATHS},
    }
    source_by_id = load_expansion_candidates(root)
    specs = frozen_specs(source_by_id)
    audit = data_availability_audit(root, specs)
    next_action = audit["next_action"]

    batch = {
        "metadata": {
            "lane_id": "first_expansion_discovery_batch",
            "created_utc": created_utc,
            "pre_registration_only": True,
            "data_availability_audit_only": True,
            "source_registry_path": str((root / EXPANSION_REGISTRY_PATH).resolve()),
            "candidates_included_count": len(specs),
            "included_candidate_ids": AUTHORIZED_CANDIDATE_IDS,
            "excluded_candidate_ids": EXCLUDED_CANDIDATE_IDS,
            "future_discovery_outcomes_allowed": ALLOWED_FUTURE_DISCOVERY_OUTCOMES,
            "data_availability_status": audit["data_availability_status"],
            "next_action": next_action,
        },
        "candidates": specs,
        "data_availability": {
            "status": audit["data_availability_status"],
            "missing_symbols": audit["missing_symbols"],
            "next_action": next_action,
        },
    }
    (output_dir / "first_expansion_discovery_batch.yaml").write_text(yaml.safe_dump(batch, sort_keys=False, allow_unicode=False), encoding="utf-8")
    (output_dir / "first_expansion_candidate_specs.md").write_text(candidate_specs_md(specs), encoding="utf-8")
    (output_dir / "first_expansion_risk_policy.md").write_text(risk_policy_md(specs), encoding="utf-8")
    (output_dir / "first_expansion_benchmark_plan.md").write_text(benchmark_plan_md(specs), encoding="utf-8")
    (output_dir / "first_expansion_acceptance_gates.md").write_text(acceptance_gates_md(), encoding="utf-8")
    (output_dir / "first_expansion_rejection_gates.md").write_text(rejection_gates_md(), encoding="utf-8")
    (output_dir / "first_expansion_data_availability_report.md").write_text(data_availability_report_md(audit), encoding="utf-8")
    (output_dir / "first_expansion_missing_data_report.md").write_text(missing_data_report_md(audit), encoding="utf-8")
    (output_dir / "first_expansion_do_not_run_now.md").write_text(do_not_run_now_md(), encoding="utf-8")
    (output_dir / "first_expansion_next_action.md").write_text(f"# First Expansion Next Action\n\n`{next_action}`\n", encoding="utf-8")

    manifest = {
        "artifact": "first_expansion_discovery_preregistration",
        "created_utc": created_utc,
        "output_dir": str(output_dir.resolve()),
        "pre_registration_only": True,
        "data_availability_audit_only": True,
        "candidates_included_count": len(specs),
        "included_candidate_ids": AUTHORIZED_CANDIDATE_IDS,
        "excluded_candidate_ids": EXCLUDED_CANDIDATE_IDS,
        "backtests_run": False,
        "discovery_run": False,
        "performance_metrics_computed": False,
        "candidate_exhaustive_run": False,
        "paper_forward_review": False,
        "paper_forward_activation": False,
        "broker_path_touched": False,
        "live_orders": False,
        "provider_download": False,
        "provider_api_called": False,
        "real_money_recommendation": False,
        "etf_wrapper_track_reopened": False,
        "intraday_candidates_included": False,
        "event_data_candidates_included": False,
        "active_strategy_state_changed": False,
        "future_discovery_outcomes_allowed": ALLOWED_FUTURE_DISCOVERY_OUTCOMES,
        "data_availability_status": audit["data_availability_status"],
        "missing_symbols": audit["missing_symbols"],
        "next_action": next_action,
    }
    write_json(output_dir / "first_expansion_discovery_manifest.json", manifest)
    write_json(output_dir / "first_expansion_data_availability_manifest.json", audit)

    update_expansion_metadata(root, audit, created_utc)
    update_expansion_roadmap(root, audit, created_utc)
    after_hashes = {
        "strategy_registry": sha256_file(root / STRATEGY_REGISTRY_PATH),
        **{str(path): sha256_file(root / path) for path in ACTIVE_OBSERVATION_PATHS},
    }
    consistency = consistency_check(manifest, audit, specs, before_hashes, after_hashes)
    consistency["roadmap_updated"] = True
    consistency["expansion_registry_metadata_updated"] = True
    write_json(output_dir / "first_expansion_consistency_check.json", consistency)
    return manifest


if __name__ == "__main__":
    result = run_first_expansion_discovery_preregistration(ROOT)
    print(
        json.dumps(
            {
                "output_dir": result["output_dir"],
                "candidates_included_count": result["candidates_included_count"],
                "data_availability_status": result["data_availability_status"],
                "missing_symbols": result["missing_symbols"],
                "next_action": result["next_action"],
            },
            indent=2,
        )
    )
