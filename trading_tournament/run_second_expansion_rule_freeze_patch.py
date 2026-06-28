from __future__ import annotations

import difflib
import json
import shutil
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent
LATEST_DIR = Path("evidence") / "pre_registered_lanes" / "second_expansion_with_lane_framework" / "latest"
PATCH_DIR = Path("evidence") / "pre_registered_lanes" / "second_expansion_with_lane_framework" / "rule_freeze_patch" / "latest"
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
CACHE_DIR = Path("data") / "cache"

EXPECTED_CANDIDATES = [
    "managed_futures_etf_trend_wrapper_v1",
    "gld_gror_balanced_momentum_clean_v1",
    "donchian_atr_breakout_etf_v1",
    "turn_of_month_spy_qqq_v1",
    "cash_pause_overlay_meta_v1",
]
NEXT_ACTION_DISCOVERY = "run_second_expansion_discovery_batch_with_lane_framework"
NEXT_ACTION_MANUAL = "manual_review_required_for_second_expansion_rule_freeze"

FORBIDDEN_OUTCOMES = ["candidate_exhaustive", "paper_forward", "paper_forward_active", "demo_active", "live_ready"]
OVERLAY_VALID_OUTCOMES = ["diagnostic_reject", "risk_overlay_watchlist_candidate"]
MANAGED_FUTURES_LIMITED_OUTCOMES = ["discovery_reject", "promotion_review_candidate_macro_limited_history"]

MANIFEST_FLAGS = {
    "rule_freeze_patch_only": True,
    "backtests_run": False,
    "discovery_run": False,
    "performance_metrics_computed": False,
    "provider_download": False,
    "candidate_exhaustive_run": False,
    "paper_forward_review": False,
    "paper_forward_activation": False,
    "broker_path_touched": False,
    "live_orders": False,
    "real_money_recommendation": False,
    "candidate_membership_changed": False,
    "accepted_strategy_state_changed": False,
    "rejected_strategy_state_changed": False,
    "old_gld_gror_state_resumed": False,
    "sector_rs_discovery_run": False,
    "intraday_candidates_included": False,
    "event_data_candidates_included": False,
    "turn_of_month_rule_fully_frozen": True,
    "donchian_atr_stop_fully_frozen": True,
    "cash_pause_overlay_thresholds_frozen": True,
    "managed_futures_limited_history_handling_frozen": True,
}

FORBIDDEN_PHRASES = [
    "future preregistration may freeze",
    "fixed window without exact window",
    "fixed selection rule without exact rule",
    "ATR stop without ATR lookback",
    "abnormal drawdown without threshold",
    "weekly loss breach without threshold",
    "according to project conventions",
    "if required",
    "optimize later",
    "try multiple",
    "choose best",
]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def clean_patch_dir(root: Path) -> Path:
    output = (root / PATCH_DIR).resolve()
    if root.resolve() not in output.parents:
        raise RuntimeError(f"refusing output outside workspace: {output}")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)
    return output


def strategy_state_snapshot(root: Path) -> list[dict[str, Any]]:
    return deepcopy(load_yaml(root / REGISTRY_PATH).get("strategies", []))


def read_cache_dates(root: Path, symbol: str) -> list[str]:
    path = root / CACHE_DIR / f"{symbol}.csv"
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        return []
    headers = lines[0].split(",")
    try:
        date_index = headers.index("date")
    except ValueError:
        return []
    dates: list[str] = []
    for line in lines[1:]:
        parts = line.split(",")
        if len(parts) > date_index and parts[date_index]:
            dates.append(parts[date_index])
    return sorted(set(dates))


def managed_futures_sample(root: Path) -> dict[str, Any]:
    symbols = ["DBMF", "KMLM", "CTA", "BIL", "SPY"]
    dates_by_symbol = {symbol: read_cache_dates(root, symbol) for symbol in symbols}
    first_dates = {symbol: dates[0] if dates else "" for symbol, dates in dates_by_symbol.items()}
    last_dates = {symbol: dates[-1] if dates else "" for symbol, dates in dates_by_symbol.items()}
    common_start = max((value for value in first_dates.values() if value), default="")
    common_last = min((value for value in last_dates.values() if value), default="")
    common_dates = sorted(set.intersection(*(set(dates) for dates in dates_by_symbol.values()))) if all(dates_by_symbol.values()) else []
    warmup_trading_days = 63
    warmup_start = common_dates[warmup_trading_days] if len(common_dates) > warmup_trading_days else ""
    full_years = 0.0
    if warmup_start and common_last:
        start = datetime.strptime(warmup_start, "%Y-%m-%d").date()
        end = datetime.strptime(common_last, "%Y-%m-%d").date()
        full_years = max(0.0, (end - start).days / 365.25)
    return {
        "symbols": symbols,
        "first_dates": first_dates,
        "last_dates": last_dates,
        "common_start_before_warmup": common_start,
        "indicator_warmup_trading_days": warmup_trading_days,
        "common_start_after_warmup": warmup_start,
        "common_last_date": common_last,
        "common_sample_years_after_warmup": round(full_years, 3),
        "fewer_than_5_full_calendar_years_after_warmup": full_years < 5.0,
    }


def candidates_by_id(batch: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {candidate.get("candidate_id", ""): candidate for candidate in batch.get("candidates", [])}


def patch_turn_of_month(candidate: dict[str, Any]) -> None:
    candidate["timeframe"] = "daily_calendar_window"
    candidate["allowed_instruments"] = ["SPY", "QQQ", "BIL"]
    candidate["turn_of_month_window"] = "Last 4 trading days of each calendar month through first 3 trading days of next calendar month."
    candidate["selection_rule"] = "On the first eligible trading day of the window, compare SPY and QQQ by fixed 63-trading-day total return using prior completed daily data only; select the higher-ranked asset only if it is above its 200-day SMA; otherwise hold BIL."
    candidate["sizing_rule"] = "100% selected SPY, QQQ, or BIL; max one risk asset; no leverage; no shorting."
    candidate["trade_controls"] = [
        "Max one entry cycle per calendar month.",
        "Max one exit cycle per calendar month.",
        "No intraday confirmation.",
    ]
    candidate["frozen_rule"] = [
        "Timeframe: daily_calendar_window.",
        "Universe: SPY, QQQ, BIL.",
        "Turn-of-month window: last 4 trading days of each calendar month through the first 3 trading days of the next calendar month.",
        "Use one pre-registered calendar window only; do not test alternate windows and do not optimize the window.",
        "Use prior completed daily data only.",
        "On the first eligible trading day of the window, compare SPY and QQQ by fixed 63-trading-day total return.",
        "Select the higher-ranked asset only if it is above its 200-day SMA.",
        "If neither SPY nor QQQ qualifies, hold BIL.",
        "Hold selected asset through the fixed calendar window unless the missing/stale data rule forces BIL.",
        "Outside the fixed calendar window, hold BIL.",
        "Sizing: 100% selected asset or BIL; max one risk asset; no leverage; no shorting.",
        "Trade controls: max one entry cycle and one exit cycle per calendar month; no intraday confirmation.",
    ]


def patch_donchian(candidate: dict[str, Any]) -> None:
    candidate["timeframe"] = "daily"
    candidate["entry_rule"] = "Use prior completed daily data only; enter long at next valid open when prior close is above the prior 20-day high, with the prior 20-day high excluding the signal day's close."
    candidate["stop_rule"] = "ATR lookback 14 trading days; initial stop threshold is entry price minus 2.0 times ATR(14), using ATR known before entry; close-based stop signal only; if prior close is at or below stop threshold, exit at next valid open."
    candidate["exit_rule"] = "Exit on earliest of close-based ATR stop signal, max holding period of 20 trading days, missing/stale data forced exit, or abnormal data pause."
    candidate["sizing_rule"] = "Max 2 open positions, equal notional position sizing, no leverage, no shorting."
    candidate["trade_controls"] = [
        "Use moderate tactical ETF lane trade-frequency gate.",
        "Do not apply conservative ETF lane max-trades/week gate.",
        "Max new entries per day: 2.",
        "Max open positions: 2.",
    ]
    candidate["frozen_rule"] = [
        "Timeframe: daily.",
        "Universe: SPY, QQQ, IWM, DIA, XLK, XLF, XLV, XLE, XLI, XLY, XLP, XLU, XLB, XLRE, with BIL cash-fallback convention named BIL_cash_proxy from strategy_registry.yaml.",
        "Use prior completed daily data only.",
        "Entry: enter long at next valid open when prior close is above the prior 20-day high.",
        "The prior 20-day high excludes the signal day's close.",
        "No intraday confirmation and no parameter sweep.",
        "ATR lookback: 14 trading days.",
        "Initial stop threshold: entry price minus 2.0 times ATR(14), using ATR known before entry.",
        "Daily-data stop timing: close-based stop signal only; if prior close is at or below the stop threshold, exit at the next valid open.",
        "Do not simulate intraday stop fills from daily low; this v1 uses daily-bar close-based stop timing only.",
        "No trailing stop; initial stop only.",
        "Exit when earliest occurs: close-based ATR stop signal, max holding period of 20 trading days, missing/stale data forced-exit rule, or abnormal data pause rule.",
        "Sizing: max 2 open positions, equal notional position sizing, no leverage, no shorting.",
        "Trade controls: moderate tactical ETF lane trade-frequency gate, max new entries per day 2, max open positions 2.",
    ]


def patch_cash_pause(candidate: dict[str, Any]) -> None:
    candidate["status"] = "shared_risk_overlay"
    candidate["lane_id"] = "diversifier_contribution_lane"
    candidate["application_base"] = "Apply only as diagnostic overlay to active_combo_vm_dsr_equal_weight_v1 when available as benchmark/watchlist reference; otherwise diagnostic_unavailable_no_base."
    candidate["pause_trigger"] = [
        "Pause new entries for the next scheduled period when strategy equity drawdown from trailing 20-trading-day equity high is >= 6%.",
        "Pause new entries for the next scheduled period when prior completed calendar-week strategy return is <= -3%.",
        "Pause new entries when stale/missing data condition is triggered.",
        "Pause new entries when broker/reconciliation/log abnormality is reported by existing project diagnostics; offline backtest should mark these triggers not applicable unless existing logs support them.",
    ]
    candidate["pause_duration"] = "One scheduled period; re-evaluate after each scheduled period; existing positions follow the base strategy's frozen exit policy; new entries are blocked during pause."
    candidate["valid_future_outcomes"] = OVERLAY_VALID_OUTCOMES
    candidate["forbidden_future_outcomes"] = ["promotion_review_candidate", *FORBIDDEN_OUTCOMES]
    candidate["allowed_application"] = [
        "Apply only as diagnostic overlay to active_combo_vm_dsr_equal_weight_v1 if available as benchmark/watchlist reference.",
        "If active combo is unavailable in the repository, mark overlay as diagnostic_unavailable_no_base.",
        "Do not apply this overlay to rejected strategies.",
        "Do not use this overlay to rescue any rejected strategy.",
        "Do not alter accepted active strategy state.",
    ]
    candidate["frozen_rule"] = [
        "Status: shared_risk_overlay.",
        "Lane: diversifier_contribution_lane.",
        "Purpose: diagnostic risk overlay only; not standalone alpha.",
        "Application base: active_combo_vm_dsr_equal_weight_v1 benchmark/watchlist reference only; diagnostic_unavailable_no_base if unavailable.",
        "Do not apply this overlay to rejected strategies and do not use it to rescue rejected strategies.",
        "Do not alter accepted active strategy state.",
        "Pause trigger: pause new entries for the next scheduled period if strategy equity drawdown from trailing 20-trading-day equity high is greater than or equal to 6%.",
        "Pause trigger: pause new entries for the next scheduled period if prior completed calendar-week strategy return is less than or equal to -3%.",
        "Pause trigger: pause new entries if stale/missing data condition is triggered.",
        "Pause trigger: broker/reconciliation/log abnormality from existing project diagnostics; offline backtest marks this not applicable unless existing logs support it.",
        "Pause duration: one scheduled period, then re-evaluate after each scheduled period.",
        "Existing positions follow the base strategy's frozen exit policy; new entries are blocked during pause.",
        "Valid future outcomes: diagnostic_reject or risk_overlay_watchlist_candidate only.",
    ]


def patch_managed_futures(candidate: dict[str, Any], sample: dict[str, Any]) -> None:
    candidate["lane_id"] = "macro_gld_duration_risk_off_lane"
    candidate["limited_history_treatment"] = {
        "data_available_but_limited_history": True,
        "same_window_comparison_required": True,
        "required_symbols_for_same_window": ["DBMF", "KMLM", "CTA", "BIL", "SPY"],
        "indicator_warmup_trading_days": sample["indicator_warmup_trading_days"],
        "common_start_after_warmup": sample["common_start_after_warmup"],
        "common_last_date": sample["common_last_date"],
        "common_sample_years_after_warmup": sample["common_sample_years_after_warmup"],
        "minimum_full_calendar_years_for_full_macro_promotion": 5,
        "full_promotion_review_candidate_macro_allowed": not sample["fewer_than_5_full_calendar_years_after_warmup"],
        "downgrade_when_too_short": "promotion_review_candidate_macro_limited_history",
    }
    if sample["fewer_than_5_full_calendar_years_after_warmup"]:
        candidate["valid_future_outcomes"] = MANAGED_FUTURES_LIMITED_OUTCOMES
    candidate["frozen_rule"] = [
        "Weekly rebalance.",
        "Use prior completed data only.",
        "Rank available approved managed-futures ETF proxies DBMF, KMLM, and CTA by fixed 13-week momentum.",
        "Hold the top approved proxy only if it has positive 13-week momentum and sufficient data.",
        "Otherwise hold BIL.",
        "No leverage, no margin, no shorting, and no direct futures.",
        "Limited-history treatment: data is available but limited-history.",
        "Discovery must use same-window comparison after DBMF, KMLM, CTA, BIL, SPY, and 63-trading-day indicator warmup are available.",
        "Do not compare this candidate to full-history active references.",
        "Same-window benchmarks are mandatory.",
        "If common sample after warmup has fewer than 5 full calendar years, full promotion_review_candidate_macro is blocked.",
        "If full macro promotion is blocked, valid positive outcome is promotion_review_candidate_macro_limited_history; otherwise use discovery_reject.",
    ]


def patch_batch(batch: dict[str, Any], sample: dict[str, Any]) -> dict[str, Any]:
    patched = deepcopy(batch)
    lookup = candidates_by_id(patched)
    patch_managed_futures(lookup["managed_futures_etf_trend_wrapper_v1"], sample)
    patch_donchian(lookup["donchian_atr_breakout_etf_v1"])
    patch_turn_of_month(lookup["turn_of_month_spy_qqq_v1"])
    patch_cash_pause(lookup["cash_pause_overlay_meta_v1"])
    patched.setdefault("metadata", {})["rule_freeze_patch_applied"] = True
    patched["metadata"]["rule_freeze_patch_next_action"] = NEXT_ACTION_DISCOVERY
    return patched


def candidate_specs_md(batch: dict[str, Any]) -> str:
    lines = ["# Second Expansion Candidate Specs", ""]
    for candidate in batch.get("candidates", []):
        lines.extend(
            [
                f"## {candidate['candidate_id']}",
                "",
                f"- Lane: `{candidate['lane_id']}`",
                f"- Status: `{candidate['status']}`",
                f"- Family: `{candidate['family']}`",
                f"- Timeframe: `{candidate['timeframe']}`",
                f"- Purpose: {candidate['purpose']}",
                f"- Allowed instruments: `{';'.join(candidate.get('allowed_instruments', [])) or 'not_applicable_overlay'}`",
                f"- Data status: `{candidate.get('candidate_data_status', '')}`",
                f"- Valid future outcomes: `{';'.join(candidate.get('valid_future_outcomes', []))}`",
                "",
                "Frozen v1 rule:",
                "",
            ]
        )
        lines.extend(f"- {item}" for item in candidate.get("frozen_rule", []))
        if candidate.get("allowed_application"):
            lines.extend(["", "Allowed application:", ""])
            lines.extend(f"- {item}" for item in candidate["allowed_application"])
        if candidate.get("limited_history_treatment"):
            lines.extend(["", "Limited-history treatment:", ""])
            for key, value in candidate["limited_history_treatment"].items():
                lines.append(f"- {key}: `{value}`")
        lines.append("")
    return "\n".join(lines)


def risk_policy_md() -> str:
    return """# Second Expansion Risk Policy

- Use the lane-specific gate framework.
- No candidate may move directly to candidate_exhaustive, paper-forward, demo_active, live_ready, broker integration, or real-money use.
- Macro candidates require same-window comparisons and crisis/diversification diagnostics.
- Managed-futures ETF wrapper discovery must use the limited-history same-window rule after DBMF, KMLM, CTA, BIL, SPY, and 63-trading-day indicator warmup are available.
- Managed-futures ETF wrapper cannot receive full promotion_review_candidate_macro if the common sample after warmup has fewer than 5 full calendar years.
- Moderate tactical candidates must survive slippage/spread, drawdown, risk-buffer, and trade-frequency gates.
- Donchian/ATR breakout uses daily-bar close-based ATR stop timing only, ATR(14), 2.0x stop multiple, initial stop only, and no intraday stop simulation.
- Turn-of-month uses one calendar window only: last 4 trading days through first 3 trading days of the next calendar month.
- The overlay candidate is not standalone alpha and is not standalone paper/demo eligible.
- Cash pause overlay applies only to active_combo_vm_dsr_equal_weight_v1 benchmark/watchlist reference and cannot rescue rejected strategies.
- No direct futures, options, margin, leverage, shorting, intraday confirmation, provider download, or broker/live path is authorized.
"""


def acceptance_gates_md() -> str:
    return """# Second Expansion Acceptance Gates

## Macro / GLD / Duration / Risk-Off Lane

- Valid outcomes for standard macro candidate: `discovery_reject` or `promotion_review_candidate_macro`.
- Valid outcomes for limited-history managed-futures ETF wrapper: `discovery_reject` or `promotion_review_candidate_macro_limited_history` when fewer than 5 full calendar years remain after warmup.
- Same-window active VM, active DSR, active combo, SPY_200d, and relevant asset benchmarks are required.
- Managed-futures-style exposure must be ETF/fund-wrapper only.
- Crisis/risk-off or diversification benefit must be visible in future evidence.

## Moderate Tactical ETF Lane

- Valid outcomes: `discovery_reject` or `promotion_review_candidate`.
- Must survive strict slippage/spread, drawdown, risk-buffer, turnover, and trade-count gates.
- Donchian/ATR breakout must use ATR(14), 2.0x initial stop, close-based daily stop signal, and no intraday stop fills.
- Turn-of-month must use last 4 trading days through first 3 trading days of next calendar month, 63-day SPY/QQQ total-return ranking, and 200-day SMA qualification.
- Must not duplicate SPY/QQQ/active combo without useful edge.

## Diversifier Contribution Lane

- Valid outcomes: `diagnostic_reject` or `risk_overlay_watchlist_candidate`.
- Must be judged by marginal contribution to active_combo_vm_dsr_equal_weight_v1 as benchmark/watchlist reference.
- Cash pause overlay is not eligible for normal promotion candidate status.
"""


def rejection_gates_md() -> str:
    return """# Second Expansion Rejection Gates

## Macro Candidates

- Reject if same-window benchmarks cannot be computed.
- Reject if GLD buy-and-hold explains the result.
- Reject if data comparability is incomplete.
- Reject if the row is simply an equity wrapper with GLD decoration.
- Reject if managed-futures common sample after warmup is too short and limited-history watchlist evidence is not strong enough.
- Reject if drawdown, risk-buffer, or slippage gates fail.
- Reject if there is no crisis or diversification benefit.

## Moderate Tactical Candidates

- Reject if slippage erases edge.
- Reject if drawdown or risk buffer fails.
- Reject if trade count is too thin for confidence or too high for ETF execution.
- Reject if Donchian/ATR needs unfrozen intraday stop assumptions to work.
- Reject if turn-of-month depends on alternate calendar windows or parameter choice.
- Reject if the row duplicates SPY, QQQ, or active combo without useful edge.

## Overlay Candidate

- Reject if it simply dilutes exposure.
- Reject if it improves drawdown only by destroying target probability.
- Reject if portfolio contribution is weak.
- Reject if it attempts to rescue rejected strategies without new pre-registration.
- Reject if active_combo_vm_dsr_equal_weight_v1 benchmark/watchlist reference is unavailable and diagnostic_unavailable_no_base cannot be resolved.
"""


def next_action_md(next_action: str) -> str:
    return f"# Second Expansion Next Action\n\n`{next_action}`\n\nDo not run this next action from the rule-freeze patch task.\n"


def scan_ambiguities(texts: dict[str, str]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    lowered = {name: text.lower() for name, text in texts.items()}
    for phrase in FORBIDDEN_PHRASES:
        needle = phrase.lower()
        for file_name, text in lowered.items():
            if needle in text:
                findings.append({"file": file_name, "phrase": phrase})
    return {
        "remaining_ambiguities_count": len(findings),
        "findings": findings,
        "scanned_files": sorted(texts),
    }


def consistency_check(
    manifest: dict[str, Any],
    before_ids: list[str],
    after_ids: list[str],
    strategies_before: list[dict[str, Any]],
    strategies_after: list[dict[str, Any]],
    batch: dict[str, Any],
) -> dict[str, Any]:
    lookup = candidates_by_id(batch)
    turn_text = " ".join(lookup["turn_of_month_spy_qqq_v1"].get("frozen_rule", []))
    donchian_text = " ".join(lookup["donchian_atr_breakout_etf_v1"].get("frozen_rule", []))
    overlay_text = " ".join(lookup["cash_pause_overlay_meta_v1"].get("frozen_rule", []) + lookup["cash_pause_overlay_meta_v1"].get("allowed_application", []))
    managed = lookup["managed_futures_etf_trend_wrapper_v1"]
    managed_text = " ".join(managed.get("frozen_rule", []))
    check = {
        "rule_freeze_patch_only": manifest["rule_freeze_patch_only"],
        "no_backtests_run": not manifest["backtests_run"],
        "no_discovery_run": not manifest["discovery_run"],
        "no_performance_metrics_computed": not manifest["performance_metrics_computed"],
        "no_provider_download": not manifest["provider_download"],
        "candidate_membership_unchanged": before_ids == after_ids == EXPECTED_CANDIDATES,
        "accepted_rejected_strategy_states_unchanged": strategies_before == strategies_after,
        "old_gld_gror_state_not_resumed": not manifest["old_gld_gror_state_resumed"],
        "sector_rs_discovery_not_run": not manifest["sector_rs_discovery_run"],
        "no_intraday_event_candidate_included": not manifest["intraday_candidates_included"] and not manifest["event_data_candidates_included"],
        "turn_of_month_exact_calendar_window": "last 4 trading days" in turn_text and "first 3 trading days" in turn_text,
        "turn_of_month_exact_selection_rule": "63-trading-day total return" in turn_text and "200-day SMA" in turn_text,
        "donchian_atr_lookback_and_stop_multiple": "ATR lookback: 14 trading days" in donchian_text and "2.0 times ATR(14)" in donchian_text,
        "donchian_daily_data_stop_timing": "close-based stop signal" in donchian_text and "exit at the next valid open" in donchian_text,
        "cash_pause_thresholds_frozen": "20-trading-day equity high" in overlay_text and "6%" in overlay_text and "calendar-week" in overlay_text and "-3%" in overlay_text,
        "cash_pause_application_base_frozen": "active_combo_vm_dsr_equal_weight_v1" in overlay_text,
        "cash_pause_no_normal_promotion": "promotion_review_candidate" not in lookup["cash_pause_overlay_meta_v1"].get("valid_future_outcomes", []),
        "managed_futures_limited_history_same_window": "Limited-history treatment" in managed_text and managed.get("limited_history_treatment", {}).get("same_window_comparison_required") is True,
        "managed_futures_full_promotion_blocked_if_too_short": managed.get("limited_history_treatment", {}).get("full_promotion_review_candidate_macro_allowed") is False and "promotion_review_candidate_macro" not in managed.get("valid_future_outcomes", []),
        "no_unresolved_optimization_phrases": manifest["remaining_ambiguities_count"] == 0,
        "next_action_discovery_only_if_no_ambiguities": (manifest["remaining_ambiguities_count"] == 0 and manifest["next_action"] == NEXT_ACTION_DISCOVERY) or (manifest["remaining_ambiguities_count"] > 0 and manifest["next_action"] == NEXT_ACTION_MANUAL),
        "manifest_flags_match_scope": all(manifest[key] == value for key, value in MANIFEST_FLAGS.items()),
    }
    check["consistency_passed"] = all(bool(value) for value in check.values())
    return check


def summary_md(manifest: dict[str, Any], sample: dict[str, Any]) -> str:
    return f"""# Second Expansion Rule-Freeze Patch

Created UTC: `{manifest['created_utc']}`

Rule-freeze patch only: `{manifest['rule_freeze_patch_only']}`

Remaining ambiguities: `{manifest['remaining_ambiguities_count']}`

Next action: `{manifest['next_action']}`

## Fields Patched

- `turn_of_month_spy_qqq_v1`: exact calendar window, SPY/QQQ 63-trading-day selection rule, SMA qualification, sizing, and trade controls.
- `donchian_atr_breakout_etf_v1`: ATR(14), 2.0x initial stop threshold, close-based daily stop signal, initial-stop-only policy, exits, sizing, and trade controls.
- `cash_pause_overlay_meta_v1`: active-combo-only diagnostic base, 6% trailing-20-day drawdown trigger, -3% completed-calendar-week loss trigger, one scheduled-period pause duration, and outcome restrictions.
- `managed_futures_etf_trend_wrapper_v1`: limited-history same-window treatment and full macro-promotion block when common sample after warmup is under 5 full calendar years.

Managed-futures common sample after warmup: `{sample['common_start_after_warmup']}` to `{sample['common_last_date']}`, about `{sample['common_sample_years_after_warmup']}` years.
"""


def run_second_expansion_rule_freeze_patch(root: Path = ROOT) -> dict[str, Any]:
    latest = root / LATEST_DIR
    patch_output = clean_patch_dir(root)
    batch_path = latest / "second_expansion_batch.yaml"
    old_batch = load_yaml(batch_path)
    old_specs = (latest / "second_expansion_candidate_specs.md").read_text(encoding="utf-8")
    before_ids = [candidate.get("candidate_id", "") for candidate in old_batch.get("candidates", [])]
    strategies_before = strategy_state_snapshot(root)
    sample = managed_futures_sample(root)
    new_batch = patch_batch(old_batch, sample)
    after_ids = [candidate.get("candidate_id", "") for candidate in new_batch.get("candidates", [])]
    new_specs = candidate_specs_md(new_batch)
    new_risk = risk_policy_md()
    new_acceptance = acceptance_gates_md()
    new_rejection = rejection_gates_md()
    scan = scan_ambiguities(
        {
            "second_expansion_candidate_specs.md": new_specs,
            "second_expansion_batch.yaml": yaml.safe_dump(new_batch, sort_keys=False, width=120, allow_unicode=False),
            "second_expansion_risk_policy.md": new_risk,
            "second_expansion_acceptance_gates.md": new_acceptance,
            "second_expansion_rejection_gates.md": new_rejection,
        }
    )
    next_action = NEXT_ACTION_DISCOVERY if scan["remaining_ambiguities_count"] == 0 else NEXT_ACTION_MANUAL
    manifest = {
        "artifact": "second_expansion_rule_freeze_patch",
        "created_utc": now_utc(),
        "patch_output_dir": str(patch_output),
        "latest_packet_dir": str(latest.resolve()),
        "remaining_ambiguities_count": scan["remaining_ambiguities_count"],
        "next_action": next_action,
        "managed_futures_common_sample": sample,
        **MANIFEST_FLAGS,
    }

    (batch_path).write_text(yaml.safe_dump(new_batch, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")
    (latest / "second_expansion_candidate_specs.md").write_text(new_specs, encoding="utf-8")
    (latest / "second_expansion_risk_policy.md").write_text(new_risk, encoding="utf-8")
    (latest / "second_expansion_acceptance_gates.md").write_text(new_acceptance, encoding="utf-8")
    (latest / "second_expansion_rejection_gates.md").write_text(new_rejection, encoding="utf-8")
    (latest / "second_expansion_next_action.md").write_text(next_action_md(next_action), encoding="utf-8")

    strategies_after = strategy_state_snapshot(root)
    consistency = consistency_check(manifest, before_ids, after_ids, strategies_before, strategies_after, new_batch)
    write_json(latest / "second_expansion_consistency_check.json", consistency)

    diff = "\n".join(
        difflib.unified_diff(
            old_specs.splitlines(),
            new_specs.splitlines(),
            fromfile="second_expansion_candidate_specs.md.before",
            tofile="second_expansion_candidate_specs.md.after",
            lineterm="",
        )
    )
    write_json(patch_output / "second_expansion_rule_freeze_patch_manifest.json", manifest)
    (patch_output / "second_expansion_rule_freeze_patch_summary.md").write_text(summary_md(manifest, sample), encoding="utf-8")
    (patch_output / "second_expansion_candidate_specs_patched.md").write_text(new_specs, encoding="utf-8")
    (patch_output / "second_expansion_rule_freeze_diff.md").write_text(diff + "\n", encoding="utf-8")
    write_json(patch_output / "second_expansion_unresolved_ambiguity_scan.json", scan)
    write_json(patch_output / "second_expansion_rule_freeze_consistency_check.json", consistency)
    (patch_output / "second_expansion_rule_freeze_next_action.md").write_text(next_action_md(next_action), encoding="utf-8")

    return {
        "patch_output_dir": str(patch_output),
        "latest_packet_dir": str(latest.resolve()),
        "remaining_ambiguities_count": scan["remaining_ambiguities_count"],
        "next_action": next_action,
        "candidate_membership_changed": before_ids != after_ids,
        "consistency": consistency,
    }


def main() -> None:
    print(json.dumps(run_second_expansion_rule_freeze_patch(ROOT), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
