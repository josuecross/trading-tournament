from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent
REGISTRY_PATH = Path("strategy_lab") / "strategy_expansion_candidates_v1.yaml"
ROADMAP_PATH = Path("strategy_lab") / "STRATEGY_EXPANSION_ROADMAP.md"
OUTPUT_DIR = Path("strategy_lab") / "evidence" / "strategy_expansion_candidates_v1" / "latest"
NEXT_ACTION = "pre_register_first_expansion_discovery_batch"

REQUIRED_CANDIDATE_FIELDS = [
    "candidate_id",
    "strategy_name",
    "priority_rank",
    "priority_group",
    "family",
    "edge_type",
    "timeframe",
    "status",
    "demo_eligibility",
    "instruments",
    "allowed_universe",
    "core_hypothesis",
    "entry_rule",
    "exit_rule",
    "sizing_rule",
    "risk_controls",
    "max_position_size",
    "max_open_positions",
    "max_trades_per_day",
    "max_trades_per_week",
    "max_holding_period",
    "data_required",
    "execution_assumptions",
    "benchmark_controls",
    "minimum_backtest_period",
    "minimum_acceptance_criteria",
    "rejection_criteria",
    "main_failure_modes",
    "related_tested_strategies",
    "duplication_checks",
    "next_action",
]

CONTROLLED_STATUS_VALUES = [
    "registered_not_tested",
    "research_only",
    "daily_research_candidate",
    "intraday_research_only",
    "later_data_quality_required",
    "shared_risk_overlay",
    "archived_do_not_repeat_without_new_hypothesis",
]

CONTROLLED_DEMO_ELIGIBILITY_VALUES = [
    "not_eligible_yet",
    "daily_demo_review_possible_after_validation",
    "weekly_demo_review_possible_after_validation",
    "research_only_until_execution_ready",
    "not_alpha_overlay_only",
    "later_only_data_quality_blocked",
]

FORBIDDEN_STATUS_VALUES = [
    "approved",
    "paper_forward_active",
    "candidate_exhaustive",
    "demo_active",
    "live_ready",
]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def list_text(values: list[str]) -> str:
    return "; ".join(values)


def flatten(value: Any) -> str:
    if isinstance(value, list):
        return "; ".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True)
    return str(value)


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: flatten(row.get(field, "")) for field in fields})


def candidate_definitions() -> list[dict[str, Any]]:
    candidates = [
        {
            "candidate_id": "dmr_liquid_etf_oversold_rebound_v1",
            "strategy_name": "Liquid ETF Oversold Rebound",
            "priority_rank": 1,
            "priority_group": "priority_1_immediate_daily_weekly",
            "family": "daily_mean_reversion",
            "edge_type": "mean_reversion",
            "timeframe": "daily",
            "status": "daily_research_candidate",
            "demo_eligibility": "daily_demo_review_possible_after_validation",
            "instruments": ["SPY", "QQQ", "IWM", "DIA", "XLK", "XLF", "XLV", "XLE", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE"],
            "allowed_universe": "Highly liquid broad and sector ETFs only; no single stocks, leverage, shorts, options, futures, forex, or crypto.",
            "core_hypothesis": "Short-horizon ETF oversold rebounds can be profitable when the instrument and market backdrop remain in healthy long-term uptrends.",
            "entry_rule": "At the daily close, rank eligible ETFs with close above their 200-day SMA and SPY above its 200-day SMA by RSI(2). Enter the two lowest RSI(2) readings only when RSI(2) <= 10.",
            "exit_rule": "Exit at the next daily close above the 5-day SMA, on a 2.0 ATR(14) stop from entry, after 5 trading days, or when SPY closes below its 200-day SMA.",
            "sizing_rule": "Equal risk slots with at most two open ETF positions; unused cash remains cash/BIL proxy in reporting.",
            "risk_controls": [
                "Max 2 open positions.",
                "Max 25% notional per position.",
                "ATR stop required on every entry.",
                "Max 2 new entries per day.",
                "Pause new entries for the rest of the week after two closed losing trades or a 3% strategy drawdown in the same week.",
            ],
            "max_position_size": "25% notional per position",
            "max_open_positions": 2,
            "max_trades_per_day": 2,
            "max_trades_per_week": 6,
            "max_holding_period": "5 trading days",
            "data_required": ["Adjusted daily OHLCV for eligible ETFs", "RSI(2)", "5-day SMA", "200-day SMA", "ATR(14)"],
            "execution_assumptions": ["End-of-day signal", "Next session open or close simulation must be declared before testing", "No intraday fills assumed"],
            "benchmark_controls": ["SPY buy-and-hold", "SPY 200d trend model", "active VM", "active DSR", "active combo benchmark"],
            "minimum_backtest_period": "At least 10 years when data exists, including 2018, 2020, 2022, and 2025-2026 windows.",
            "minimum_acceptance_criteria": [
                "Positive median final equity after costs in sampled and full windows.",
                "Beats SPY 200d and active combo on risk-adjusted return or materially improves drawdown at comparable return.",
                "No single ETF accounts for most of the edge.",
            ],
            "rejection_criteria": [
                "Fails drawdown buffer versus active references.",
                "Profit concentrated in one crisis rebound.",
                "Turnover costs erase edge.",
            ],
            "main_failure_modes": ["Mean reversion keeps catching falling ETFs", "RSI threshold is too sparse or too crowded", "Sector correlations create hidden concentration"],
            "related_tested_strategies": ["SPY_200d_trend_model", "active_combo_vm_dsr_equal_weight_v1", "breadth_state_regime_lane"],
            "duplication_checks": ["Must not reduce to active VM trend filter only", "Must not be a near-duplicate of previous ETF wrapper defensive shifts"],
            "diversity_family": "mean-reversion",
            "instrument_scope": "broad ETFs; sector ETFs",
            "risk_level": "medium",
            "execution_difficulty": "low",
            "next_action": "pre_register_before_any_backtest",
        },
        {
            "candidate_id": "vm_spy_qqq_daily_vol_target_v1",
            "strategy_name": "SPY QQQ Daily Volatility Target",
            "priority_rank": 2,
            "priority_group": "priority_1_immediate_daily_weekly",
            "family": "volatility_managed_equity",
            "edge_type": "volatility_management",
            "timeframe": "daily",
            "status": "daily_research_candidate",
            "demo_eligibility": "daily_demo_review_possible_after_validation",
            "instruments": ["SPY", "QQQ", "BIL"],
            "allowed_universe": "SPY, QQQ, and BIL only; long-only exposure with no leverage.",
            "core_hypothesis": "Trend-following equity exposure may improve small-account survivability if exposure is scaled down during high realized-volatility regimes.",
            "entry_rule": "Hold SPY and QQQ when each closes above its 200-day SMA and SPY closes above its 200-day SMA; otherwise assign that sleeve to BIL.",
            "exit_rule": "Reduce or exit a sleeve when its close falls below the 200-day SMA, when a pre-registered realized volatility spike block is active, or at the next rebalance.",
            "sizing_rule": "Target 50% SPY and 50% QQQ in calm volatility, 25%/25% in elevated volatility, and residual allocation to BIL; never exceed 100% total notional.",
            "risk_controls": [
                "No leverage and no margin.",
                "Max 100% total notional exposure.",
                "Residual allocation goes to BIL.",
                "Drawdown pause blocks new risk increases.",
                "Volatility spike condition can only reduce exposure, never increase it.",
            ],
            "max_position_size": "50% notional per equity ETF before volatility scaling",
            "max_open_positions": 3,
            "max_trades_per_day": 2,
            "max_trades_per_week": 4,
            "max_holding_period": "Open-ended while daily rules remain valid",
            "data_required": ["Adjusted daily OHLCV for SPY, QQQ, BIL", "200-day SMA", "20-day realized volatility", "60-day realized volatility"],
            "execution_assumptions": ["End-of-day signal", "Daily rebalance only when target exposure changes", "BIL used as cash proxy"],
            "benchmark_controls": ["active VM", "SPY 200d trend model", "active combo benchmark", "SPY/QQQ 50/50 buy-and-hold"],
            "minimum_backtest_period": "At least 15 years when available, with explicit 2020 and 2022 stress windows.",
            "minimum_acceptance_criteria": [
                "Distinct from active VM after rule comparison.",
                "Improves drawdown or volatility materially versus 50/50 SPY/QQQ without unacceptable return drag.",
                "Does not lag active VM and active combo by enough to fail the profit goal.",
            ],
            "rejection_criteria": [
                "Near-duplicate of active VM.",
                "Volatility scaling removes too much upside.",
                "High-volatility whipsaw produces worse drawdown and lower return.",
            ],
            "main_failure_modes": ["Hidden duplication with active VM", "Late volatility response", "Too much BIL drag"],
            "related_tested_strategies": ["paper_forward_vm_quality_lowvol_proxy_v1", "SPY_200d_trend_model", "active_combo_vm_dsr_equal_weight_v1"],
            "duplication_checks": ["Compare holdings, exposure path, drawdown path, and signal dates against active VM before any promotion review"],
            "diversity_family": "volatility-management",
            "instrument_scope": "risk-on/risk-off pair",
            "risk_level": "medium",
            "execution_difficulty": "low",
            "next_action": "pre_register_before_any_backtest",
        },
        {
            "candidate_id": "sector_rs_weekly_cash_filter_v1",
            "strategy_name": "Weekly Sector Relative Strength Cash Filter",
            "priority_rank": 3,
            "priority_group": "priority_1_immediate_daily_weekly",
            "family": "sector_relative_strength_rotation",
            "edge_type": "sector_rotation",
            "timeframe": "weekly",
            "status": "registered_not_tested",
            "demo_eligibility": "weekly_demo_review_possible_after_validation",
            "instruments": ["XLK", "XLF", "XLV", "XLE", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE", "BIL"],
            "allowed_universe": "Liquid sector ETFs and BIL only.",
            "core_hypothesis": "Weekly sector leadership with an explicit cash filter may capture medium-term rotation without the slower behavior of monthly ETF-wrapper rows.",
            "entry_rule": "On the final trading day of each week, rank sectors by fixed 13-week total return; hold the top two only if each closes above its 26-week SMA and SPY closes above its 40-week SMA.",
            "exit_rule": "Exit a sector at weekly rebalance if it falls out of the top two, fails its 26-week SMA filter, or SPY fails the 40-week SMA filter; allocate failed sleeves to BIL.",
            "sizing_rule": "Allocate 50% to each selected sector; failed or missing slots go to BIL.",
            "risk_controls": [
                "Max 2 sector positions.",
                "50% cap per sector.",
                "Weekly rebalance only.",
                "BIL fallback for weak sectors.",
                "Pause new sector entries for one week after a 5% strategy drawdown from prior month-end equity.",
            ],
            "max_position_size": "50% notional per sector ETF",
            "max_open_positions": 2,
            "max_trades_per_day": 2,
            "max_trades_per_week": 4,
            "max_holding_period": "Open-ended while weekly rules remain valid",
            "data_required": ["Adjusted daily OHLCV converted to weekly bars", "13-week total return", "26-week SMA", "40-week SPY SMA"],
            "execution_assumptions": ["Weekly signal only", "No intraday decisioning", "No sector shorting"],
            "benchmark_controls": ["active DSR", "active combo benchmark", "equal-weight sector basket", "SPY 200d trend model"],
            "minimum_backtest_period": "At least 15 years where sector ETF history permits; include rate-shock and bear-market windows.",
            "minimum_acceptance_criteria": [
                "Not a near-duplicate of active DSR.",
                "Beats equal-weight sectors and active combo on either median final equity or drawdown-adjusted return.",
                "Turnover remains within cap without excessive whipsaw.",
            ],
            "rejection_criteria": [
                "Weaker than active DSR and active combo.",
                "Returns dominated by XLK-only concentration.",
                "Cash filter causes persistent underinvestment.",
            ],
            "main_failure_modes": ["Sector momentum reverses quickly", "Hidden XLK/QQQ concentration", "Weekly filter too slow"],
            "related_tested_strategies": ["paper_forward_dsr_sector_equal_weight_defensive_filter_v1", "active_combo_vm_dsr_equal_weight_v1", "dsr_sector_top2_momentum_200d_bil_v1"],
            "duplication_checks": ["Compare selected sectors, rebalance dates, BIL usage, and return sources against active DSR"],
            "diversity_family": "sector-rotation",
            "instrument_scope": "sector ETFs",
            "risk_level": "medium",
            "execution_difficulty": "low",
            "next_action": "pre_register_before_any_backtest",
        },
        {
            "candidate_id": "vol_compression_breakout_etf_v1",
            "strategy_name": "ETF Volatility Compression Breakout",
            "priority_rank": 4,
            "priority_group": "priority_1_immediate_daily_weekly",
            "family": "volatility_compression_breakout",
            "edge_type": "breakout",
            "timeframe": "daily",
            "status": "daily_research_candidate",
            "demo_eligibility": "daily_demo_review_possible_after_validation",
            "instruments": ["SPY", "QQQ", "IWM", "DIA", "XLK", "XLF", "XLV", "XLE", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE"],
            "allowed_universe": "Broad and sector ETFs only; long-only.",
            "core_hypothesis": "A fixed breakout after volatility compression can capture directional expansion while ATR stops cap failed breakouts.",
            "entry_rule": "Enter an ETF at the daily close when its 10-day ATR divided by close is below its fixed 252-day 30th percentile and the close breaks above the prior 20-day high.",
            "exit_rule": "Exit on a 2.5 ATR(14) trailing stop, a close below the 20-day SMA, after 20 trading days, or after an extreme adverse gap stop.",
            "sizing_rule": "At most two equal-size positions selected by highest 63-day return among qualifying breakouts.",
            "risk_controls": [
                "Max 2 open positions.",
                "Max 25% notional per position.",
                "No entry after a gap up greater than 2 ATR from the prior close.",
                "ATR trailing stop required.",
                "Pause new entries after a 4% weekly strategy loss.",
            ],
            "max_position_size": "25% notional per position",
            "max_open_positions": 2,
            "max_trades_per_day": 2,
            "max_trades_per_week": 5,
            "max_holding_period": "20 trading days",
            "data_required": ["Adjusted daily OHLCV", "ATR(10)", "ATR(14)", "20-day high", "20-day SMA", "252-day ATR percentile"],
            "execution_assumptions": ["Daily close signal", "No stop fills better than stop level in simulation", "No intraday breakout logic"],
            "benchmark_controls": ["SPY buy-and-hold", "SPY 200d trend model", "active combo benchmark", "Donchian breakout candidate"],
            "minimum_backtest_period": "At least 10 years, including low-volatility and high-volatility regimes.",
            "minimum_acceptance_criteria": [
                "Profitable after conservative slippage.",
                "Drawdown controlled by ATR stop and weekly pause.",
                "Performance not explained by one sector ETF or one volatility regime.",
            ],
            "rejection_criteria": [
                "Breakout failures dominate gains.",
                "Compression filter is redundant with plain trend following.",
                "Too few trades for reliable inference.",
            ],
            "main_failure_modes": ["False breakouts", "Gap entries chase exhausted moves", "Sparse signal sample"],
            "related_tested_strategies": ["breadth_state_regime_lane", "expanded_universe_batch_1", "active_combo_vm_dsr_equal_weight_v1"],
            "duplication_checks": ["Must show distinct entry timing from top-N ETF momentum wrappers and breadth-state rows"],
            "diversity_family": "breakout",
            "instrument_scope": "broad ETFs; sector ETFs",
            "risk_level": "medium_high",
            "execution_difficulty": "low",
            "next_action": "pre_register_before_any_backtest",
        },
        {
            "candidate_id": "rs_pair_rotation_spy_qqq_xlk_xlu_v1",
            "strategy_name": "SPY QQQ XLK XLU Relative Strength Pair Rotation",
            "priority_rank": 5,
            "priority_group": "priority_1_immediate_daily_weekly",
            "family": "long_only_relative_strength_pair_rotation",
            "edge_type": "relative_strength",
            "timeframe": "weekly",
            "status": "registered_not_tested",
            "demo_eligibility": "weekly_demo_review_possible_after_validation",
            "instruments": ["SPY", "QQQ", "XLK", "XLU", "BIL"],
            "allowed_universe": "SPY, QQQ, XLK, XLU, and BIL only.",
            "core_hypothesis": "A compact risk-on/risk-off sleeve may capture equity leadership while moving to defensive utility or BIL when growth risk weakens.",
            "entry_rule": "At weekly close, rank SPY, QQQ, XLK, and XLU by fixed 13-week return; hold the top ETF only if it closes above its 26-week SMA and SPY closes above its 40-week SMA, otherwise hold BIL.",
            "exit_rule": "Exit at the next weekly rebalance if the held ETF is no longer top-ranked, fails its trend filter, or SPY fails the market filter.",
            "sizing_rule": "Hold one 100% sleeve position or BIL; no split allocation.",
            "risk_controls": [
                "Max 1 risk position.",
                "BIL fallback.",
                "Weekly turnover cap of one full switch.",
                "Hidden concentration review for QQQ and XLK exposure.",
                "Drawdown pause routes to BIL for one week after a 5% strategy drawdown.",
            ],
            "max_position_size": "100% notional in one ETF or BIL",
            "max_open_positions": 1,
            "max_trades_per_day": 1,
            "max_trades_per_week": 2,
            "max_holding_period": "Open-ended while weekly rules remain valid",
            "data_required": ["Adjusted daily OHLCV converted to weekly bars", "13-week return", "26-week SMA", "40-week SPY SMA"],
            "execution_assumptions": ["Weekly rebalance", "No leverage", "No intraday execution model"],
            "benchmark_controls": ["SPY 200d trend model", "active VM", "active combo benchmark", "SPY/QQQ 50/50"],
            "minimum_backtest_period": "At least 15 years where XLK and XLU history permits.",
            "minimum_acceptance_criteria": [
                "Clear distinct behavior from active VM.",
                "No excessive QQQ/XLK concentration after concentration audit.",
                "Risk-adjusted results beat simple SPY/QQQ controls or drawdown improves materially.",
            ],
            "rejection_criteria": [
                "Hidden QQQ/XLK concentration explains returns.",
                "Too slow to meet profit objective.",
                "BIL filter whipsaws during recoveries.",
            ],
            "main_failure_modes": ["Concentration in technology beta", "Weekly lag", "Defensive switch occurs too late"],
            "related_tested_strategies": ["paper_forward_vm_quality_lowvol_proxy_v1", "paper_forward_dsr_sector_equal_weight_defensive_filter_v1", "active_combo_vm_dsr_equal_weight_v1"],
            "duplication_checks": ["Audit overlap with active VM and active DSR exposures before considering promotion review"],
            "diversity_family": "relative-strength",
            "instrument_scope": "risk-on/risk-off pair",
            "risk_level": "medium",
            "execution_difficulty": "low",
            "next_action": "pre_register_before_any_backtest",
        },
        {
            "candidate_id": "donchian_atr_breakout_etf_v1",
            "strategy_name": "Donchian ATR ETF Breakout",
            "priority_rank": 6,
            "priority_group": "priority_2_higher_risk_daily",
            "family": "daily_breakout",
            "edge_type": "trend-following breakout",
            "timeframe": "daily",
            "status": "daily_research_candidate",
            "demo_eligibility": "daily_demo_review_possible_after_validation",
            "instruments": ["SPY", "QQQ", "IWM", "DIA", "XLK", "XLF", "XLV", "XLE", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE"],
            "allowed_universe": "Broad and sector ETFs only; long-only.",
            "core_hypothesis": "Fixed Donchian breakouts with ATR stops may catch persistent ETF trends that slower wrapper models miss.",
            "entry_rule": "Enter at the daily close when an ETF closes above its prior 55-day high and SPY closes above its 200-day SMA.",
            "exit_rule": "Exit on a close below the prior 20-day low, a 2.0 ATR(14) trailing stop, or after 30 trading days.",
            "sizing_rule": "Allocate equal notional across at most two active breakout positions; unused cash remains unallocated.",
            "risk_controls": [
                "Max 2 open positions.",
                "Max 25% notional per position.",
                "ATR trailing stop required.",
                "Max 4 new breakout entries per week.",
                "No new entries after two stopped breakout losses in the same week.",
            ],
            "max_position_size": "25% notional per position",
            "max_open_positions": 2,
            "max_trades_per_day": 2,
            "max_trades_per_week": 4,
            "max_holding_period": "30 trading days",
            "data_required": ["Adjusted daily OHLCV", "55-day high", "20-day low", "ATR(14)", "SPY 200-day SMA"],
            "execution_assumptions": ["Daily close signal", "Conservative stop simulation", "No intraday breakout entry"],
            "benchmark_controls": ["SPY buy-and-hold", "SPY 200d trend model", "vol compression breakout candidate", "active combo benchmark"],
            "minimum_backtest_period": "At least 10 years with separate crisis and non-crisis summaries.",
            "minimum_acceptance_criteria": [
                "Shows persistent upside outside one crisis period.",
                "ATR stops keep drawdown within risk buffer.",
                "Beats plain SPY trend model on either final equity or drawdown-adjusted return.",
            ],
            "rejection_criteria": [
                "Too many false breakouts.",
                "High drawdown despite stops.",
                "No improvement over simpler volatility compression breakout or SPY 200d controls.",
            ],
            "main_failure_modes": ["Late entries", "Whipsaw near highs", "ATR stop too wide for small account"],
            "related_tested_strategies": ["SPY_200d_trend_model", "breadth_state_regime_lane", "expanded_universe_batch_1"],
            "duplication_checks": ["Must not be evaluated as another top-N ETF wrapper; entry is price breakout, not rank-only momentum"],
            "diversity_family": "trend-following",
            "instrument_scope": "broad ETFs; sector ETFs",
            "risk_level": "medium_high",
            "execution_difficulty": "low",
            "next_action": "hold_for_later_preregistration",
        },
        {
            "candidate_id": "turn_of_month_spy_qqq_v1",
            "strategy_name": "SPY QQQ Turn Of Month Window",
            "priority_rank": 7,
            "priority_group": "priority_2_higher_risk_daily",
            "family": "calendar_anomaly",
            "edge_type": "calendar/event",
            "timeframe": "daily",
            "status": "daily_research_candidate",
            "demo_eligibility": "daily_demo_review_possible_after_validation",
            "instruments": ["SPY", "QQQ", "BIL"],
            "allowed_universe": "SPY, QQQ, and BIL only.",
            "core_hypothesis": "A fixed turn-of-month window may capture recurring flow effects while avoiding continuous equity exposure.",
            "entry_rule": "Hold 50% SPY and 50% QQQ from the close of the fourth-to-last trading day of each month through the close of the third trading day of the next month; otherwise hold BIL.",
            "exit_rule": "Exit to BIL at the close of the third trading day of the month or when a pre-registered hard drawdown pause is active.",
            "sizing_rule": "50% SPY and 50% QQQ during the fixed window; 100% BIL outside the window.",
            "risk_controls": [
                "Fixed calendar window only.",
                "No tuning of alternative calendar windows after results.",
                "No leverage.",
                "BIL outside the window.",
                "Monthly drawdown pause if the window loses more than 4%.",
            ],
            "max_position_size": "50% notional per equity ETF",
            "max_open_positions": 2,
            "max_trades_per_day": 2,
            "max_trades_per_week": 4,
            "max_holding_period": "8 trading days",
            "data_required": ["Adjusted daily OHLCV for SPY, QQQ, BIL", "Trading calendar with month boundaries"],
            "execution_assumptions": ["Daily close rebalance", "No intraday fills", "Calendar known before testing"],
            "benchmark_controls": ["SPY buy-and-hold", "SPY/QQQ 50/50 buy-and-hold", "BIL", "active combo benchmark"],
            "minimum_backtest_period": "At least 20 years where possible, with separate pre- and post-2020 summaries.",
            "minimum_acceptance_criteria": [
                "Positive edge after costs without calendar-window tuning.",
                "Works on both SPY and QQQ sleeves, not one isolated instrument.",
                "Drawdown lower than continuous SPY/QQQ exposure.",
            ],
            "rejection_criteria": [
                "Only one subperiod works.",
                "Window edge disappears after costs.",
                "Requires alternate calendar windows to look viable.",
            ],
            "main_failure_modes": ["Calendar anomaly decays", "Too little exposure to meet profit goal", "Month-end shocks"],
            "related_tested_strategies": ["SPY_200d_trend_model", "active_combo_vm_dsr_equal_weight_v1"],
            "duplication_checks": ["Must be treated as calendar exposure, not trend-following or ETF wrapper momentum"],
            "diversity_family": "calendar/event",
            "instrument_scope": "SPY/QQQ only",
            "risk_level": "medium",
            "execution_difficulty": "low",
            "next_action": "hold_for_later_preregistration",
        },
        {
            "candidate_id": "cash_pause_overlay_meta_v1",
            "strategy_name": "Shared Cash Pause Risk Overlay",
            "priority_rank": 8,
            "priority_group": "priority_2_higher_risk_daily",
            "family": "shared_risk_overlay",
            "edge_type": "risk_overlay",
            "timeframe": "meta-overlay",
            "status": "shared_risk_overlay",
            "demo_eligibility": "not_alpha_overlay_only",
            "instruments": ["APPLIES_TO_ALL_CANDIDATE_STRATEGIES"],
            "allowed_universe": "Applies to registered strategy candidates only; it is not a standalone alpha strategy.",
            "core_hypothesis": "A common cash pause can reduce compounding damage from abnormal drawdown, execution issues, or repeated failed signals.",
            "entry_rule": "No standalone entries. Overlay activates when a candidate hits a pre-registered drawdown, loss-streak, data-quality, or execution kill-switch condition.",
            "exit_rule": "Overlay deactivates only after the pre-registered cooling-off period and data-quality checks pass.",
            "sizing_rule": "When active, block new entries or route affected strategy sleeves to cash/BIL according to each candidate's rule packet.",
            "risk_controls": [
                "Not alpha by itself.",
                "Cannot increase exposure.",
                "Cannot override stops.",
                "Must log reason for every pause.",
                "Requires manual review before changing thresholds.",
            ],
            "max_position_size": "No standalone position",
            "max_open_positions": 0,
            "max_trades_per_day": 0,
            "max_trades_per_week": 0,
            "max_holding_period": "Cooling-off period defined per candidate before testing",
            "data_required": ["Strategy equity curve", "Closed trade log", "Data-quality status", "Execution readiness status"],
            "execution_assumptions": ["Overlay only reduces risk", "No broker integration", "No live order path"],
            "benchmark_controls": ["Each candidate with overlay disabled", "Each candidate with overlay enabled", "active combo benchmark"],
            "minimum_backtest_period": "Same as the underlying candidate being tested.",
            "minimum_acceptance_criteria": [
                "Reduces drawdown or tail risk without destroying the candidate's return profile.",
                "Does not create hidden parameter tuning.",
                "Pause reasons are auditable.",
            ],
            "rejection_criteria": [
                "Overlay only improves results through tuned hindsight thresholds.",
                "Overlay blocks most profitable recoveries.",
                "Pause logic cannot be audited.",
            ],
            "main_failure_modes": ["Over-filtering", "Hindsight threshold creep", "False sense of risk control"],
            "related_tested_strategies": ["active_combo_vm_dsr_equal_weight_v1", "breadth_state_regime_lane", "all_future_candidates"],
            "duplication_checks": ["Must not be counted as a separate alpha candidate in performance promotion reviews"],
            "diversity_family": "risk-overlay",
            "instrument_scope": "applies to all strategies",
            "risk_level": "risk_reducing_only",
            "execution_difficulty": "medium",
            "next_action": "define_candidate_specific_overlay_policy_before_any_backtest",
        },
        {
            "candidate_id": "orb_spy_qqq_30m_research_v1",
            "strategy_name": "SPY QQQ 30 Minute Opening Range Breakout Research",
            "priority_rank": 9,
            "priority_group": "priority_3_intraday_research_only",
            "family": "opening_range_breakout",
            "edge_type": "intraday_momentum",
            "timeframe": "intraday",
            "status": "intraday_research_only",
            "demo_eligibility": "research_only_until_execution_ready",
            "instruments": ["SPY", "QQQ"],
            "allowed_universe": "SPY and QQQ only until intraday data and execution readiness are independently validated.",
            "core_hypothesis": "Upside breaks of the first 30-minute range may capture intraday trend days when volatility and session filters are favorable.",
            "entry_rule": "After the first 30 minutes, enter long on a break above the opening range high only if pre-registered spread, volatility, and session filters pass.",
            "exit_rule": "Exit at a hard stop below the opening range midpoint or low, at a fixed session time, at max daily loss, or before the close; no overnight holds.",
            "sizing_rule": "Single intraday position with fixed small notional risk per trade; no scaling in.",
            "risk_controls": [
                "Research-only until execution infrastructure is proven.",
                "Max 1 trade per day.",
                "Hard stop required.",
                "No overnight hold.",
                "Daily and weekly loss kill switches.",
                "Spread and data-quality filters required.",
            ],
            "max_position_size": "Small fixed research risk; exact notional must be pre-registered before testing",
            "max_open_positions": 1,
            "max_trades_per_day": 1,
            "max_trades_per_week": 5,
            "max_holding_period": "Intraday only; flat before close",
            "data_required": ["Intraday OHLCV at 1-minute or 5-minute granularity", "Bid-ask spread proxy", "Session calendar", "Corporate action adjusted ETF data"],
            "execution_assumptions": ["No paper/demo eligibility yet", "Conservative slippage model required", "No live or broker path"],
            "benchmark_controls": ["Buy-and-hold SPY/QQQ daily controls", "Same-day no-trade baseline", "Intraday random-entry control if later allowed"],
            "minimum_backtest_period": "At least 3 years of high-quality intraday data before any demo review.",
            "minimum_acceptance_criteria": [
                "Positive expectancy after conservative slippage and spreads.",
                "No dependence on untradeable first-tick fills.",
                "Daily loss controls cap tail risk.",
            ],
            "rejection_criteria": [
                "Edge disappears after spread/slippage.",
                "Requires unverified intraday data.",
                "Loss tails exceed small-account risk limits.",
            ],
            "main_failure_modes": ["False opening breakouts", "Execution slippage", "Overnight gap temptation", "Data-quality bias"],
            "related_tested_strategies": ["none_intraday_not_previously_approved", "ETF_wrapper_track_archived"],
            "duplication_checks": ["Must remain research-only and must not be conflated with daily breakout candidates"],
            "diversity_family": "intraday momentum",
            "instrument_scope": "SPY/QQQ only",
            "risk_level": "high_research_only",
            "execution_difficulty": "high",
            "next_action": "hold_until_intraday_data_quality_plan_is_pre_registered",
        },
        {
            "candidate_id": "gap_down_fade_spy_qqq_research_v1",
            "strategy_name": "SPY QQQ Gap Down Fade Research",
            "priority_rank": 10,
            "priority_group": "priority_3_intraday_research_only",
            "family": "gap_fade",
            "edge_type": "intraday_reversion",
            "timeframe": "intraday",
            "status": "intraday_research_only",
            "demo_eligibility": "research_only_until_execution_ready",
            "instruments": ["SPY", "QQQ"],
            "allowed_universe": "SPY and QQQ only until intraday data quality is proven.",
            "core_hypothesis": "Large gap-down opens may partially revert intraday after selling pressure stabilizes, but only with strict stops and no overnight risk.",
            "entry_rule": "Enter long only after a pre-registered large gap-down open and stabilization condition are both observed; do not buy the opening print.",
            "exit_rule": "Exit at VWAP, a fixed afternoon time, a hard stop below opening low or session ATR stop, max daily loss, or before close.",
            "sizing_rule": "One small fixed-risk intraday position; no averaging down.",
            "risk_controls": [
                "Research-only.",
                "Max 1 trade per day.",
                "No overnight hold.",
                "Stop below opening low or fixed session ATR stop.",
                "Max daily and weekly loss limits.",
                "No trade during major data-quality or halt events.",
            ],
            "max_position_size": "Small fixed research risk; exact notional must be pre-registered before testing",
            "max_open_positions": 1,
            "max_trades_per_day": 1,
            "max_trades_per_week": 5,
            "max_holding_period": "Intraday only; flat before close",
            "data_required": ["Intraday OHLCV", "Prior daily close", "Opening print validation", "VWAP", "Spread proxy", "Session calendar"],
            "execution_assumptions": ["No opening-print fills assumed", "Conservative slippage required", "No broker or live path"],
            "benchmark_controls": ["No-trade baseline on gap days", "Gap-down buy-at-open diagnostic only if data supports it", "SPY/QQQ daily controls"],
            "minimum_backtest_period": "At least 3 years of high-quality intraday data with gap-day sample diagnostics.",
            "minimum_acceptance_criteria": [
                "Positive expectancy after slippage.",
                "Tail losses capped by hard stops.",
                "Works across both SPY and QQQ or has a documented symbol-specific reason before testing.",
            ],
            "rejection_criteria": [
                "Catches trend-down days too often.",
                "Requires buying before stabilization is observable.",
                "Gap sample too small for confidence.",
            ],
            "main_failure_modes": ["Gap continuation", "Stop gaps through level", "VWAP target too optimistic", "Data timestamp errors"],
            "related_tested_strategies": ["none_intraday_not_previously_approved", "ETF_wrapper_track_archived"],
            "duplication_checks": ["Distinct from daily ETF mean reversion because entry, stop, and exit are intraday and execution-dependent"],
            "diversity_family": "intraday reversion",
            "instrument_scope": "SPY/QQQ only",
            "risk_level": "high_research_only",
            "execution_difficulty": "high",
            "next_action": "hold_until_intraday_data_quality_plan_is_pre_registered",
        },
        {
            "candidate_id": "vwap_deviation_reversion_research_v1",
            "strategy_name": "VWAP Deviation Reversion Research",
            "priority_rank": 11,
            "priority_group": "priority_3_intraday_research_only",
            "family": "vwap_intraday_reversion",
            "edge_type": "intraday_reversion",
            "timeframe": "intraday",
            "status": "intraday_research_only",
            "demo_eligibility": "research_only_until_execution_ready",
            "instruments": ["SPY", "QQQ", "IWM"],
            "allowed_universe": "SPY, QQQ, and IWM only until intraday data and execution readiness are proven.",
            "core_hypothesis": "Large downside deviations from VWAP can mean-revert intraday when selling pressure slows, but the edge is execution-sensitive.",
            "entry_rule": "After the first 15 minutes, enter long when price is a pre-registered distance below VWAP and a fixed selling-pressure slowdown condition is present.",
            "exit_rule": "Exit at VWAP, at hard stop, at max daily loss, or before close; no overnight holds.",
            "sizing_rule": "At most one active intraday position with fixed small notional risk; no averaging down.",
            "risk_controls": [
                "Research-only.",
                "No trade in first 15 minutes.",
                "Spread filter required.",
                "Hard stop required.",
                "Max 2 trades per day.",
                "No overnight hold.",
            ],
            "max_position_size": "Small fixed research risk; exact notional must be pre-registered before testing",
            "max_open_positions": 1,
            "max_trades_per_day": 2,
            "max_trades_per_week": 8,
            "max_holding_period": "Intraday only; flat before close",
            "data_required": ["Intraday OHLCV", "VWAP", "Volume", "Spread proxy", "Session calendar"],
            "execution_assumptions": ["Conservative slippage required", "No paper/demo eligibility yet", "No live or broker path"],
            "benchmark_controls": ["No-trade baseline", "Randomized intraday reversion timing diagnostic if later allowed", "SPY/QQQ/IWM daily controls"],
            "minimum_backtest_period": "At least 3 years of high-quality intraday data with slippage and spread sensitivity.",
            "minimum_acceptance_criteria": [
                "Positive expectancy after spread and slippage.",
                "Loss tails fit small-account limits.",
                "Edge persists outside extreme volatility windows.",
            ],
            "rejection_criteria": [
                "Only profitable before realistic execution costs.",
                "Needs repeated averaging down.",
                "Breaks during trend days.",
            ],
            "main_failure_modes": ["Trend-day losses", "VWAP data errors", "Spread/slippage drag", "Overtrading"],
            "related_tested_strategies": ["none_intraday_not_previously_approved", "ETF_wrapper_track_archived"],
            "duplication_checks": ["Must remain separate from gap fade and daily mean reversion; signal is VWAP deviation within session"],
            "diversity_family": "intraday reversion",
            "instrument_scope": "broad ETFs",
            "risk_level": "high_research_only",
            "execution_difficulty": "high",
            "next_action": "hold_until_intraday_data_quality_plan_is_pre_registered",
        },
        {
            "candidate_id": "post_earnings_drift_large_cap_later_v1",
            "strategy_name": "Large Cap Post Earnings Drift Later Candidate",
            "priority_rank": 12,
            "priority_group": "priority_4_later_data_quality_dependent",
            "family": "post_earnings_drift",
            "edge_type": "calendar/event",
            "timeframe": "daily",
            "status": "later_data_quality_required",
            "demo_eligibility": "later_only_data_quality_blocked",
            "instruments": ["HIGHLY_LIQUID_LARGE_CAP_STOCKS_LATER"],
            "allowed_universe": "Highly liquid large-cap stocks only after survivorship-bias-safe earnings data is available.",
            "core_hypothesis": "Confirmed earnings surprises may drift over multiple days, but event data quality and survivorship controls are mandatory before testing.",
            "entry_rule": "No test until earnings event data is validated. Future fixed v1 would enter after clean event confirmation, not before the announcement.",
            "exit_rule": "Future fixed v1 must define event-horizon exit, stop, and max holding period before testing.",
            "sizing_rule": "Small equal-risk positions across a capped number of names after data-quality approval.",
            "risk_controls": [
                "Later only due to data-quality requirements.",
                "No survivorship bias.",
                "Max positions required before testing.",
                "Event-quality filter required.",
                "No options, leverage, shorts, or margin.",
            ],
            "max_position_size": "To be pre-registered after data-quality approval; must be small per name",
            "max_open_positions": "To be capped before testing",
            "max_trades_per_day": "To be capped before testing",
            "max_trades_per_week": "To be capped before testing",
            "max_holding_period": "To be fixed before testing",
            "data_required": ["Survivorship-bias-safe equity universe", "Point-in-time earnings dates", "Earnings surprise fields", "Adjusted daily OHLCV", "Liquidity filters"],
            "execution_assumptions": ["No test until event data is audited", "No broker path", "No live order path"],
            "benchmark_controls": ["Large-cap universe equal-weight control", "SPY", "Sector-neutral diagnostic if later allowed"],
            "minimum_backtest_period": "At least 10 years after point-in-time event data validation.",
            "minimum_acceptance_criteria": [
                "Data provenance is auditable.",
                "Edge survives liquidity and survivorship controls.",
                "Portfolio risk is not dominated by one sector or reporting season.",
            ],
            "rejection_criteria": [
                "Data cannot be made point-in-time.",
                "Results depend on survivorship-biased universe.",
                "Event sample quality cannot be audited.",
            ],
            "main_failure_modes": ["Bad event data", "Survivorship bias", "Crowded earnings drift decay", "Single-stock gap risk"],
            "related_tested_strategies": ["none_single_stock_not_currently_allowed", "ETF_wrapper_track_archived"],
            "duplication_checks": ["Not comparable to ETF wrapper lanes until a separate event-data governance packet exists"],
            "diversity_family": "calendar/event",
            "instrument_scope": "large-cap stocks later",
            "risk_level": "high_later_only",
            "execution_difficulty": "high",
            "next_action": "defer_until_data_quality_governance_packet",
        },
    ]

    seen_fields = set(REQUIRED_CANDIDATE_FIELDS)
    for candidate in candidates:
        missing = [field for field in REQUIRED_CANDIDATE_FIELDS if field not in candidate]
        if missing:
            raise ValueError(f"{candidate.get('candidate_id', '<unknown>')} missing fields: {missing}")
        extra_required_overlap = [field for field in seen_fields if field not in candidate]
        if extra_required_overlap:
            raise ValueError(f"{candidate['candidate_id']} missing required overlap: {extra_required_overlap}")
    return candidates


def registry_payload(candidates: list[dict[str, Any]], created_utc: str) -> dict[str, Any]:
    return {
        "metadata": {
            "schema_version": 1,
            "artifact": "strategy_expansion_candidates_v1",
            "created_utc": created_utc,
            "project": "trading_tournament",
            "purpose": "Durable pre-registration registry for future paper/demo research candidates.",
            "research_only": True,
            "saved_candidates_only": True,
            "backtests_run": False,
            "discovery_run": False,
            "candidate_exhaustive_run": False,
            "paper_forward_review": False,
            "paper_forward_activation": False,
            "broker_path_touched": False,
            "live_orders": False,
            "provider_download": False,
            "real_money_recommendation": False,
            "etf_wrapper_track_status": "archived_after_breadth_state_regime_no_candidate",
            "next_action": NEXT_ACTION,
        },
        "controlled_values": {
            "status": CONTROLLED_STATUS_VALUES,
            "demo_eligibility": CONTROLLED_DEMO_ELIGIBILITY_VALUES,
            "forbidden_status": FORBIDDEN_STATUS_VALUES,
        },
        "variant_governance": {
            "parameter_mining_allowed": False,
            "new_variant_requires_new_candidate_id": True,
            "new_variant_changes_exactly_one_major_dimension": True,
            "new_variant_requires_written_hypothesis_before_testing": True,
        },
        "candidates": candidates,
    }


def roadmap_text(candidates: list[dict[str, Any]], created_utc: str) -> str:
    lines = [
        "# Strategy Expansion Roadmap",
        "",
        f"Created UTC: `{created_utc}`",
        "",
        "This roadmap saves research candidates only. It does not approve, backtest, promote, activate paper-forward, or touch any broker/live-order path.",
        "",
        "The ETF-wrapper and breadth-state regime track is treated as archived after no promotion candidates. The expansion pipeline now separates strategy family, rule variant, symbol universe, timeframe, and risk controls before any testing.",
        "",
        "Current next action: `pre_register_first_expansion_discovery_batch`",
        "",
        "## Priority Order",
        "",
        "| Rank | Candidate | Family | Timeframe | Status | Demo eligibility |",
        "|---:|---|---|---|---|---|",
    ]
    for candidate in candidates:
        lines.append(
            f"| {candidate['priority_rank']} | `{candidate['candidate_id']}` | {candidate['family']} | {candidate['timeframe']} | {candidate['status']} | {candidate['demo_eligibility']} |"
        )
    lines.extend(
        [
            "",
            "## Research Lanes",
            "",
            "- Priority 1 contains immediate daily or weekly candidates with explicit benchmark and duplication checks.",
            "- Priority 2 contains higher-risk daily or meta-overlay candidates that need careful risk review before testing.",
            "- Priority 3 contains intraday research-only ideas. These are not demo eligible until intraday data quality and execution assumptions are proven.",
            "- Priority 4 is later-only because point-in-time data quality is not yet established.",
            "",
            "## Stop Rules",
            "",
            "- Saving a candidate does not approve it.",
            "- A failed test rejects the exact variant, not an entire strategy family.",
            "- Any future variant must be pre-registered and must change exactly one major dimension.",
            "- Do not reopen archived ETF-wrapper ideas without a structurally different hypothesis.",
            "- Do not run the first expansion discovery batch from this roadmap step.",
        ]
    )
    return "\n".join(lines) + "\n"


def tested_strategy_review_text() -> str:
    return """# Tested Strategy Review

This review exists to prevent the expansion registry from repeating already-tested ETF-wrapper ideas while still allowing structurally different research families.

| Area | Classification | Benchmark use | Duplication risk for new candidates | Exhausted/open status | Future hypothesis requirement |
|---|---|---|---|---|---|
| `paper_forward_vm_quality_lowvol_proxy_v1` active VM strategy | active / accepted | Yes, primary active reference | Volatility-managed candidates must prove they are not active VM clones | Open only for structurally different volatility management | Required before any variant |
| `paper_forward_dsr_sector_equal_weight_defensive_filter_v1` active DSR strategy | active / accepted | Yes, primary active reference | Sector rotation candidates must compare holdings and cash behavior against active DSR | Open only for different sector timing or risk model | Required before any variant |
| `active_combo_vm_dsr_equal_weight_v1` active combo | diagnostic / benchmark_watchlist | Yes, benchmark only | Ensemble and blended sleeves are high duplication risk | Not an active strategy; useful as reference | Required for any combo-like idea |
| `SPY_200d_trend_model` | active / benchmark control | Yes | Trend filters must show value beyond this simple control | Open as benchmark, not as new alpha | Required for modifications |
| breadth-state regime lane | archived / rejected | No, except as archived evidence | Do not repeat the same market breadth/state ETF-wrapper mechanics | Exhausted under current mechanics after no promotion candidates | New hypothesis required |
| ETF-wrapper track overall | archived / stopped | Historical reference only | High risk of repeating saturated top-N, defensive, and ensemble mechanics | Stopped after repeated no-candidate results | Structurally different family required |
| active-sleeve ensemble | diagnostic / benchmark_watchlist | Yes for equal-weight active combo comparison | Ensemble tilts mostly duplicated active combo | Exhausted unless a new structural thesis appears | Required |
| QVM variants | rejected | Diagnostic only | Upside rows had thin risk buffer and drawdown issues | Exact tested variants closed | Required |
| LVQ variants | rejected | Diagnostic only | Safer rows lagged active references | Exact tested variants closed | Required |
| DSR variants | rejected / duplicate_or_near_duplicate | Diagnostic only | Near-duplicate risk against active DSR | Exact tested variants closed | Required |
| approved-cache batch 2 | rejected | Diagnostic only | Safe but weak rows should not be repeated cosmetically | Exact tested batch closed | Required |
| approved-cache batch 3 | rejected | Diagnostic only | Risk-controlled variants lagged references | Exact tested batch closed | Required |
| expanded-universe batch 1 | rejected | Diagnostic only | Regional upside failed risk gate; safer rows too slow | Exact tested batch closed | Required |

Conclusion: the expansion registry is allowed because it moves into pre-registered mean-reversion, breakout, volatility-management, compact relative-strength, calendar, overlay, intraday, and later event-data families. It does not approve any row and does not restart the archived ETF-wrapper track.
"""


def future_variant_rules_text() -> str:
    return """# Future Variant Rules

These rules allow controlled exploration without uncontrolled parameter mining.

1. A failed result rejects the exact candidate variant, not necessarily the entire family.
2. A new variant is allowed only if it changes exactly one major dimension: symbol universe, timeframe, entry rule family, exit rule family, or risk-control model.
3. Do not test many parameter values after seeing results.
4. Each new variant must receive a new candidate ID.
5. Each new variant must have a written hypothesis before testing.
6. Each new variant must declare what failed in the prior test and why the new test is structurally different.
7. Do not reopen archived ETF-wrapper strategies unless the hypothesis is structurally different from the stopped ETF-wrapper track.
8. Do not use small cosmetic changes to bypass rejection.
9. Do not promote a family just because one variant works; validate the exact rule.
10. Do not reject an entire family just because one narrow variant fails.

Operational controls:

- No post-result threshold tuning.
- No grid search unless separately approved as a methodology research project, not as a candidate promotion path.
- No intraday demo review until data quality, slippage, spreads, and execution assumptions are independently documented.
- No candidate may move to candidate_exhaustive or paper-forward from this registry alone.
"""


def manifest_payload(candidates: list[dict[str, Any]], created_utc: str, root: Path) -> dict[str, Any]:
    priority_order = [candidate["candidate_id"] for candidate in sorted(candidates, key=lambda row: int(row["priority_rank"]))]
    return {
        "artifact": "strategy_expansion_candidates_v1",
        "created_utc": created_utc,
        "candidate_count": len(candidates),
        "priority_order": priority_order,
        "candidate_registry_path": str((root / REGISTRY_PATH).resolve()),
        "roadmap_path": str((root / ROADMAP_PATH).resolve()),
        "output_dir": str((root / OUTPUT_DIR).resolve()),
        "next_action": NEXT_ACTION,
        "saved_candidates_only": True,
        "backtests_run": False,
        "discovery_run": False,
        "candidate_exhaustive_run": False,
        "paper_forward_review": False,
        "paper_forward_activation": False,
        "broker_path_touched": False,
        "live_orders": False,
        "provider_download": False,
        "real_money_recommendation": False,
        "forbidden_status_values_absent": True,
        "intraday_demo_eligible": False,
        "etf_wrapper_track_status": "archived_after_breadth_state_regime_no_candidate",
        "notes": [
            "This packet is a saved candidate registry only.",
            "No first expansion discovery batch was run.",
            "No active observations or strategy_registry active state were changed.",
        ],
    }


def diversity_rows(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "candidate_id": candidate["candidate_id"],
            "priority_rank": candidate["priority_rank"],
            "family": candidate["family"],
            "diversity_family": candidate["diversity_family"],
            "timeframe": candidate["timeframe"],
            "instrument_scope": candidate["instrument_scope"],
            "edge_type": candidate["edge_type"],
            "risk_level": candidate["risk_level"],
            "execution_difficulty": candidate["execution_difficulty"],
            "demo_eligibility": candidate["demo_eligibility"],
            "status": candidate["status"],
        }
        for candidate in candidates
    ]


def run_strategy_expansion_candidates_registry(root: Path = ROOT) -> dict[str, Any]:
    created_utc = now_utc()
    candidates = candidate_definitions()
    output_dir = root / OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    registry = registry_payload(candidates, created_utc)
    (root / REGISTRY_PATH).parent.mkdir(parents=True, exist_ok=True)
    (root / REGISTRY_PATH).write_text(yaml.safe_dump(registry, sort_keys=False, allow_unicode=False), encoding="utf-8")
    (root / ROADMAP_PATH).write_text(roadmap_text(candidates, created_utc), encoding="utf-8")

    write_csv(output_dir / "candidate_registry_snapshot.csv", candidates, REQUIRED_CANDIDATE_FIELDS)
    write_csv(
        output_dir / "diversity_map.csv",
        diversity_rows(candidates),
        [
            "candidate_id",
            "priority_rank",
            "family",
            "diversity_family",
            "timeframe",
            "instrument_scope",
            "edge_type",
            "risk_level",
            "execution_difficulty",
            "demo_eligibility",
            "status",
        ],
    )
    (output_dir / "tested_strategy_review.md").write_text(tested_strategy_review_text(), encoding="utf-8")
    (output_dir / "future_variant_rules.md").write_text(future_variant_rules_text(), encoding="utf-8")
    manifest = manifest_payload(candidates, created_utc, root)
    (output_dir / "strategy_expansion_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    result = run_strategy_expansion_candidates_registry(ROOT)
    print(json.dumps({"output_dir": result["output_dir"], "candidate_count": result["candidate_count"], "next_action": result["next_action"]}, indent=2))
