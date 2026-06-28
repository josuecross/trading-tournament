from __future__ import annotations

import csv
import json
import shutil
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = Path("evidence") / "pre_registered_lanes" / "risk_controlled_high_return_rule_freeze_patch" / "latest"
FAMILY_REVIEW_DIR = Path("evidence") / "pre_registered_lanes" / "risk_controlled_high_return_family_review" / "latest"
SECOND_RULE_FREEZE_PATH = (
    Path("evidence")
    / "pre_registered_lanes"
    / "second_expansion_with_lane_framework"
    / "rule_freeze_patch"
    / "latest"
    / "second_expansion_candidate_specs_patched.md"
)
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
ROADMAP_PATH = Path("strategy_lab") / "RESEARCH_ROADMAP.md"

NEXT_ACTION_RUN = "run_risk_controlled_high_return_discovery_batch"
NEXT_ACTION_MANUAL = "manual_review_required_for_risk_controlled_high_return_batch"
VALID_NEXT_ACTIONS = {
    NEXT_ACTION_RUN,
    NEXT_ACTION_MANUAL,
    "pause_expansion_and_summarize_tournament_state",
}

MANIFEST_BASE_FLAGS = {
    "rule_freeze_patch_only": True,
    "candidate_membership_changed": False,
    "candidate_count": 2,
    "backtests_run": False,
    "discovery_run": False,
    "new_performance_metrics_computed": False,
    "provider_download": False,
    "intraday_data_used": False,
    "candidate_exhaustive_run": False,
    "paper_forward_review": False,
    "paper_forward_activation": False,
    "broker_path_touched": False,
    "live_orders": False,
    "real_money_recommendation": False,
    "accepted_strategy_state_changed": False,
    "rejected_strategy_state_changed": False,
    "exact_rejected_variants_reopened": False,
    "intraday_research_remains_paused": True,
}

REQUIRED_FILES = [
    "risk_controlled_rule_freeze_manifest.json",
    "risk_controlled_rule_freeze_summary.md",
    "rc_dual_momentum_vol_scaled_frozen_rule.md",
    "rc_donchian_risk_budget_frozen_rule.md",
    "parent_rule_consistency_check.md",
    "risk_controlled_formula_completeness_check.csv",
    "risk_controlled_rule_freeze_candidate_specs.yaml",
    "risk_controlled_rule_freeze_do_not_run_now.md",
    "risk_controlled_rule_freeze_next_action.md",
    "risk_controlled_rule_freeze_consistency_check.json",
]

PATCHED_CANDIDATES: list[dict[str, Any]] = [
    {
        "candidate_id": "rc_dual_momentum_paa_vol_scaled_v1",
        "exact_rejected_parent_row": "dual_momentum_paa_clean_v1",
        "one_major_changed_dimension": "volatility_scaling",
        "lane": "macro_gld_duration_risk_off_lane",
        "formula_status": "fully_frozen",
        "volatility_input": {
            "lookback_length_trading_days": 63,
            "return_type": "adjusted_close_to_adjusted_close_simple_daily_returns",
            "annualization": "standard_deviation_of_daily_returns_times_sqrt_252",
            "completed_data_only": True,
            "volatility_proxy_symbol": "SPY",
        },
        "exposure_scalar": {
            "target_annualized_volatility": 0.12,
            "formula": "scalar_raw = 0.12 / realized_vol_63d; scalar = floor_to_0.05_increment(clamp(scalar_raw, 0.25, 1.00))",
            "min_exposure": 0.25,
            "max_exposure": 1.0,
            "rounding_convention": "round down to nearest 0.05 exposure increment",
            "missing_or_invalid_input_scalar": 0.0,
            "unused_exposure_destination": "BIL",
        },
        "timing": {
            "calculation_time": "after the final trading-day close of each month",
            "application_time": "next valid trading-day open for the next monthly allocation period",
            "update_frequency": "monthly only",
            "missing_volatility_inputs": "set scalar to 0.0 and route parent risk allocation to BIL until 63 completed returns are available",
        },
        "parent_interaction": {
            "parent_ranking_unchanged": True,
            "parent_absolute_momentum_gate_unchanged": True,
            "universe_unchanged": True,
            "no_leverage": True,
            "no_shorting": True,
            "no_options_futures_intraday": True,
        },
        "failure_rules": [
            "Reject if formula ambiguity remains.",
            "Reject if scalar requires parameter choice after seeing results.",
            "Reject if scalar converts the row into static all-weather, SPY_200d, active combo, or BIL-heavy defensive clone.",
        ],
        "valid_future_outcomes": ["discovery_reject", "promotion_review_candidate_macro"],
    },
    {
        "candidate_id": "rc_donchian_breakout_risk_budget_v1",
        "exact_rejected_parent_row": "donchian_atr_breakout_etf_v1",
        "one_major_changed_dimension": "risk_budget_sizing",
        "lane": "moderate_tactical_etf_lane",
        "formula_status": "fully_frozen_parent_consistent_formula_requires_manual_review_due_prior_packet_mismatch",
        "parent_signal": {
            "breakout_rule": "enter long at next valid open when the prior completed close is above the prior 20-day high",
            "donchian_lookback_trading_days": 20,
            "prior_high_excludes_signal_day_close": True,
            "atr_lookback_trading_days": 14,
            "stop_rule": "initial stop threshold equals entry price minus 2.0 times ATR(14) known before entry",
            "stop_timing": "daily close-based stop signal only; if prior close is at or below stop threshold, exit at next valid open",
            "trailing_stop": False,
            "holding_exit_rule": "exit on earliest of close-based ATR stop, 20 trading-day max holding period, missing/stale data forced exit, or abnormal data pause",
            "differs_from_second_expansion_parent": False,
        },
        "risk_budget_sizing": {
            "per_position_risk_budget_pct_of_equity": 0.0075,
            "portfolio_risk_budget_pct_of_equity": 0.015,
            "atr_dollar_risk_formula": "dollar_risk_per_share = max(entry_price - initial_stop_threshold, 0); shares = per_position_risk_budget_dollars / dollar_risk_per_share",
            "position_notional_formula": "position_notional = min(shares * entry_price, 0.25 * current_equity)",
            "exposure_cap_per_position_pct_of_equity": 0.25,
            "max_positions": 2,
            "signals_exceed_budget_handling": "process qualifying parent signals in parent universe order and open only positions that fit remaining portfolio risk budget and max-position limit",
            "below_minimum_practical_exposure_handling": "minimum practical exposure is 25 dollars notional; skip signals below this level and route unused allocation to BIL reporting",
        },
        "timing": {
            "signal_calculation_date": "after each daily close using prior completed daily data",
            "entry_date": "next valid trading-day open after signal",
            "exit_date": "next valid trading-day open after any completed close-based exit signal",
            "stop_evaluation_timing": "after each completed daily close only",
            "completed_data_only": True,
        },
        "cash_bil_behavior": {
            "unused_exposure": "assigned to BIL cash proxy for reporting",
            "bil_included_in_equity_curve": True,
            "bil_receives_unused_exposure_by_default": True,
        },
        "failure_rules": [
            "Reject if risk-budget sizing requires post-result adjustment.",
            "Reject if it becomes merely a Donchian or ATR parameter tweak.",
            "Reject if formula ambiguity remains.",
        ],
        "valid_future_outcomes": ["discovery_reject", "promotion_review_candidate"],
    },
]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv_rows(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def clean_output(root: Path) -> Path:
    output = (root / OUTPUT_DIR).resolve()
    workspace = root.resolve()
    if output == workspace or workspace not in output.parents:
        raise RuntimeError(f"refusing output outside workspace: {output}")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)
    return output


def strategy_snapshot(root: Path) -> list[dict[str, Any]]:
    return deepcopy(load_yaml(root / REGISTRY_PATH).get("strategies", []))


def strategy_state_map(strategies: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    state: dict[str, dict[str, Any]] = {}
    for row in strategies:
        row_id = row.get("id") or row.get("strategy_id")
        if not row_id:
            continue
        state[row_id] = {
            "status": row.get("status") or row.get("current_status"),
            "current_status": row.get("current_status"),
            "paper_forward_active": row.get("paper_forward_active"),
            "candidate_exhaustive_run": row.get("candidate_exhaustive_run"),
            "candidate_exhaustive_recommended": row.get("candidate_exhaustive_recommended"),
            "promotion_review_required": row.get("promotion_review_required"),
        }
    return state


def prior_candidate_specs(root: Path) -> tuple[dict[str, Any], list[str]]:
    manifest = load_json(root / FAMILY_REVIEW_DIR / "risk_controlled_high_return_manifest.json")
    candidates = manifest.get("candidate_specs", [])
    return manifest, [str(candidate.get("candidate_id")) for candidate in candidates]


def parent_rule_consistency(root: Path, family_manifest: dict[str, Any]) -> dict[str, Any]:
    parent_text = (root / SECOND_RULE_FREEZE_PATH).read_text(encoding="utf-8", errors="replace") if (root / SECOND_RULE_FREEZE_PATH).exists() else ""
    current_donchian = next(
        (candidate for candidate in family_manifest.get("candidate_specs", []) if candidate.get("candidate_id") == "rc_donchian_breakout_risk_budget_v1"),
        {},
    )
    current_text = json.dumps(current_donchian, sort_keys=True)
    parent_20 = "prior 20-day high" in parent_text and "max holding period of 20 trading days" in parent_text
    parent_55 = "prior 55-day high" in parent_text
    current_55 = "55-day" in current_text
    current_20 = "20-day high" in current_text
    mismatch = bool(parent_20 and current_55 and not parent_55)
    return {
        "parent_rule_source": str(SECOND_RULE_FREEZE_PATH),
        "parent_uses_20_day_breakout": parent_20,
        "parent_uses_55_day_breakout": parent_55,
        "family_review_candidate_uses_55_day_breakout_text": current_55,
        "family_review_candidate_uses_20_day_breakout_text": current_20,
        "parent_rule_mismatch_found": mismatch,
        "mismatch_label": "parent_rule_mismatch_requires_manual_review" if mismatch else "",
        "patched_rule_preserves_parent_except_sizing": True,
    }


def completeness_rows() -> list[dict[str, Any]]:
    return [
        {
            "candidate_id": "rc_dual_momentum_paa_vol_scaled_v1",
            "area": "volatility_input",
            "required_detail": "lookback, close-to-close returns, annualization, completed-data-only",
            "status": "frozen",
            "value": "63 trading days; adjusted close-to-adjusted close simple returns; annualized with sqrt(252); prior completed data only",
        },
        {
            "candidate_id": "rc_dual_momentum_paa_vol_scaled_v1",
            "area": "exposure_scalar",
            "required_detail": "target volatility, formula, min/max, rounding, unused exposure",
            "status": "frozen",
            "value": "target 12%; floor_to_0.05(clamp(0.12/realized_vol_63d, 0.25, 1.00)); invalid input scalar 0; unused exposure to BIL",
        },
        {
            "candidate_id": "rc_dual_momentum_paa_vol_scaled_v1",
            "area": "timing_parent_interaction_failure_rules",
            "required_detail": "calculation/application/update/missing inputs/parent interaction/failure rules",
            "status": "frozen",
            "value": "month-end after close; next valid open; monthly only; missing vol routes to BIL; parent ranking and absolute momentum unchanged",
        },
        {
            "candidate_id": "rc_donchian_breakout_risk_budget_v1",
            "area": "parent_signal",
            "required_detail": "Donchian rule/lookback, ATR lookback, stop, holding/exit, parent difference",
            "status": "frozen",
            "value": "parent-consistent 20-day breakout; ATR(14); 2.0x initial stop; close-based stop; 20 trading-day max hold; no parent-rule difference in patched rule",
        },
        {
            "candidate_id": "rc_donchian_breakout_risk_budget_v1",
            "area": "risk_budget_sizing",
            "required_detail": "per-position and portfolio budget, ATR risk formula, exposure cap, max positions, overflow, minimum exposure",
            "status": "frozen",
            "value": "0.75% equity per position; 1.5% portfolio risk; min(risk/stop distance, 25% notional cap); max 2 positions; skip below $25",
        },
        {
            "candidate_id": "rc_donchian_breakout_risk_budget_v1",
            "area": "timing_cash_failure_rules",
            "required_detail": "signal/entry/exit/stop timing, completed data, BIL behavior, failure rules",
            "status": "frozen",
            "value": "signal after daily close; entry/exit next valid open; stop after completed close only; unused exposure to BIL reporting; no post-result sizing adjustment",
        },
    ]


def all_formulas_frozen(rows: list[dict[str, Any]]) -> bool:
    return all(row["status"] == "frozen" for row in rows)


def summary_md(created_utc: str, output: Path, manifest: dict[str, Any]) -> str:
    return f"""# Risk-Controlled High-Return Rule-Freeze Patch

Created UTC: `{created_utc}`

Evidence path: `{output}`

Candidate count: `{manifest["candidate_count"]}`

Candidate membership changed: `{manifest["candidate_membership_changed"]}`

Parent rule mismatch found: `{manifest["parent_rule_mismatch_found"]}`

All formulas frozen: `{manifest["all_formulas_frozen"]}`

Next action: `{manifest["next_action"]}`

## Decision

Both candidate formulas are now fully specified in this patch. The Donchian rule is frozen to the original second-expansion parent mechanics except for risk-budget sizing. Because the earlier risk-controlled family-review packet used 55-day breakout language while the parent used a 20-day breakout, the batch requires manual review before discovery.

No backtest, discovery, performance metric, provider download, intraday data use, candidate_exhaustive, paper-forward action, broker/live path, or real-money recommendation occurred.
"""


def dual_rule_md() -> str:
    spec = PATCHED_CANDIDATES[0]
    return f"""# rc_dual_momentum_paa_vol_scaled_v1 Frozen Rule

Volatility input:

- Lookback: `63` trading days.
- Return series: adjusted close-to-adjusted close simple daily returns.
- Annualization: standard deviation of daily returns times `sqrt(252)`.
- Data timing: prior completed data only.
- Volatility proxy: `SPY`.

Exposure scalar:

- Target annualized volatility: `12%`.
- Formula: `{spec["exposure_scalar"]["formula"]}`.
- Minimum scalar: `0.25`.
- Maximum scalar: `1.00`.
- Rounding: round down to the nearest `0.05` exposure increment.
- If volatility input is missing or invalid, scalar is `0.0`.
- Unused exposure goes to `BIL`.

Timing:

- Calculate after the final trading-day close of each month.
- Apply at the next valid trading-day open.
- Update monthly only.
- Missing volatility inputs route parent risk allocation to `BIL` until enough completed returns exist.

Parent interaction:

- Parent ranking unchanged.
- Parent absolute momentum gate unchanged.
- Universe unchanged.
- No leverage, no shorting, no options, no futures, no intraday logic.

Failure rules:

- Reject if formula ambiguity remains.
- Reject if scalar requires parameter choice after seeing results.
- Reject if scalar converts the row into static all-weather, SPY_200d, active combo, or BIL-heavy defensive clone.
"""


def donchian_rule_md() -> str:
    spec = PATCHED_CANDIDATES[1]
    return f"""# rc_donchian_breakout_risk_budget_v1 Frozen Rule

Parent signal:

- Breakout: enter long at next valid open when prior completed close is above the prior `20`-day high.
- The prior high excludes the signal day's close.
- ATR lookback: `14` trading days.
- Stop: initial stop threshold equals entry price minus `2.0 * ATR(14)`, using ATR known before entry.
- Stop timing: completed daily close only; if prior close is at or below stop threshold, exit at next valid open.
- No trailing stop.
- Exit on earliest of close-based ATR stop, `20` trading-day max holding period, missing/stale data forced exit, or abnormal data pause.
- Patched rule differs from the original parent only in sizing.

Risk-budget sizing:

- Per-position risk budget: `0.75%` of current equity.
- Portfolio-level risk budget: `1.50%` of current equity.
- ATR dollar-risk formula: `{spec["risk_budget_sizing"]["atr_dollar_risk_formula"]}`.
- Position notional formula: `{spec["risk_budget_sizing"]["position_notional_formula"]}`.
- Exposure cap per position: `25%` of current equity.
- Max positions: `2`.
- If signals exceed available risk budget, process qualifying parent signals in parent universe order and open only positions fitting remaining portfolio risk and max-position limits.
- Minimum practical exposure: `$25` notional; below that, skip the signal and route unused allocation to BIL reporting.

Timing:

- Signal calculation: after each daily close using completed daily data.
- Entry: next valid trading-day open after signal.
- Exit: next valid trading-day open after a completed close-based exit signal.
- Stop evaluation: after completed daily close only.

Cash/BIL behavior:

- Unused exposure is assigned to `BIL` cash proxy for reporting.
- `BIL` is included in the equity curve.
- `BIL` receives unused exposure by default.

Failure rules:

- Reject if risk-budget sizing requires post-result adjustment.
- Reject if it becomes merely a Donchian or ATR parameter tweak.
- Reject if formula ambiguity remains.
"""


def parent_check_md(check: dict[str, Any]) -> str:
    return f"""# Parent Rule Consistency Check

Parent source: `{check["parent_rule_source"]}`

- Parent uses 20-day breakout: `{check["parent_uses_20_day_breakout"]}`
- Parent uses 55-day breakout: `{check["parent_uses_55_day_breakout"]}`
- Family-review candidate text used 55-day breakout language: `{check["family_review_candidate_uses_55_day_breakout_text"]}`
- Family-review candidate text used 20-day breakout language: `{check["family_review_candidate_uses_20_day_breakout_text"]}`
- Parent rule mismatch found: `{check["parent_rule_mismatch_found"]}`
- Mismatch label: `{check["mismatch_label"]}`
- Patched rule preserves parent except sizing: `{check["patched_rule_preserves_parent_except_sizing"]}`

Conclusion: the patched Donchian formula is parent-consistent, but discovery should not proceed until manual review accepts the correction because the previous risk-controlled packet contained 55-day breakout language.
"""


def do_not_run_md() -> str:
    return """# Risk-Controlled Rule-Freeze Do Not Run Now

This packet is a rule-freeze clarification only.

Do not run:

- backtests,
- discovery,
- new performance metrics,
- candidate_exhaustive,
- paper-forward review or activation,
- provider downloads,
- intraday data,
- broker/live paths,
- real-money recommendations.
"""


def next_action_md(next_action: str) -> str:
    return f"""# Risk-Controlled Rule-Freeze Next Action

`{next_action}`

Do not run the next action in this task.
"""


def update_metadata(root: Path, output: Path, created_utc: str, manifest: dict[str, Any]) -> tuple[bool, bool]:
    registry_updated = False
    registry_path = root / REGISTRY_PATH
    if registry_path.exists():
        registry = load_yaml(registry_path)
        metadata = registry.setdefault("registry", {})
        metadata.update(
            {
                "risk_controlled_high_return_rule_freeze_path": str(output),
                "risk_controlled_high_return_rule_freeze_status": "completed_manual_review_required",
                "risk_controlled_high_return_rule_freeze_created_utc": created_utc,
                "risk_controlled_rule_freeze_parent_rule_mismatch_found": manifest["parent_rule_mismatch_found"],
                "risk_controlled_rule_freeze_all_formulas_frozen": manifest["all_formulas_frozen"],
                "risk_controlled_rule_freeze_next_action": manifest["next_action"],
                "current_next_action": manifest["next_action"],
                "next_action": manifest["next_action"],
                **MANIFEST_BASE_FLAGS,
                "parent_rule_mismatch_found": manifest["parent_rule_mismatch_found"],
                "all_formulas_frozen": manifest["all_formulas_frozen"],
                "updated_utc": created_utc,
            }
        )
        registry_path.write_text(yaml.safe_dump(registry, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")
        registry_updated = True

    roadmap_path = root / ROADMAP_PATH
    existing = roadmap_path.read_text(encoding="utf-8") if roadmap_path.exists() else "# Research Roadmap\n"
    lines = existing.splitlines()
    for idx, line in enumerate(lines):
        if line.startswith("Current next action:"):
            lines[idx] = f"Current next action: `{manifest['next_action']}`"
            break
    else:
        insert_at = 1 if lines and lines[0].startswith("#") else 0
        lines.insert(insert_at, f"Current next action: `{manifest['next_action']}`")
    base = "\n".join(lines)
    marker = "## Risk-Controlled High-Return Rule-Freeze Patch"
    section = f"""## Risk-Controlled High-Return Rule-Freeze Patch

- Created UTC: `{created_utc}`
- Evidence path: `{output}`
- Rule-freeze patch only: `true`
- Candidate membership changed: `false`
- Candidate count: `2`
- Parent rule mismatch found: `{manifest["parent_rule_mismatch_found"]}`
- All formulas frozen: `{manifest["all_formulas_frozen"]}`
- Intraday research remains paused: `true`
- Next action: `{manifest["next_action"]}`
- No backtest, discovery, new performance metric, provider download, intraday data, candidate_exhaustive, paper-forward action, broker/live path, strategy-state change, rejected-row reopening, or real-money recommendation is authorized.
"""
    updated = base.split(marker, 1)[0].rstrip() + "\n\n" + section if marker in base else base.rstrip() + "\n\n" + section
    roadmap_path.parent.mkdir(parents=True, exist_ok=True)
    roadmap_path.write_text(updated.rstrip() + "\n", encoding="utf-8")
    return registry_updated, True


def consistency_check(
    output: Path,
    manifest: dict[str, Any],
    strategies_before: list[dict[str, Any]],
    strategies_after: list[dict[str, Any]],
) -> dict[str, Any]:
    required_present = {
        name: True if name == "risk_controlled_rule_freeze_consistency_check.json" else (output / name).exists()
        for name in REQUIRED_FILES
    }
    base_flags_match = all(manifest.get(key) == value for key, value in MANIFEST_BASE_FLAGS.items())
    candidates = manifest["candidate_specs"]
    check = {
        "rule_freeze_patch_only": manifest["rule_freeze_patch_only"] is True,
        "candidate_membership_unchanged": manifest["candidate_membership_changed"] is False
        and manifest["candidate_ids"] == manifest["prior_candidate_ids"],
        "candidate_count_exactly_two": manifest["candidate_count"] == 2,
        "no_backtest": manifest["backtests_run"] is False,
        "no_discovery": manifest["discovery_run"] is False,
        "no_new_performance_metrics": manifest["new_performance_metrics_computed"] is False,
        "no_provider_download": manifest["provider_download"] is False,
        "no_intraday_data_used": manifest["intraday_data_used"] is False,
        "no_candidate_exhaustive": manifest["candidate_exhaustive_run"] is False,
        "no_paper_forward_action": manifest["paper_forward_review"] is False and manifest["paper_forward_activation"] is False,
        "no_broker_or_live_path": manifest["broker_path_touched"] is False and manifest["live_orders"] is False,
        "exact_rejected_variants_remain_closed": manifest["exact_rejected_variants_reopened"] is False,
        "dual_momentum_volatility_formula_fully_frozen": manifest["dual_momentum_volatility_formula_frozen"] is True,
        "donchian_risk_budget_formula_fully_frozen": manifest["donchian_risk_budget_formula_frozen"] is True,
        "parent_rule_consistency_check_exists": required_present["parent_rule_consistency_check.md"],
        "parent_rule_mismatch_flag_recorded": isinstance(manifest["parent_rule_mismatch_found"], bool),
        "each_candidate_changes_exactly_one_dimension": [candidate["one_major_changed_dimension"] for candidate in candidates] == ["volatility_scaling", "risk_budget_sizing"],
        "intraday_remains_paused": manifest["intraday_research_remains_paused"] is True,
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "manifest_flags_match_strict_scope": base_flags_match,
        "no_strategy_state_changes": strategy_state_map(strategies_before) == strategy_state_map(strategies_after),
        "all_required_files_present": all(required_present.values()),
    }
    check["consistency_passed"] = all(check.values())
    return check


def run_risk_controlled_high_return_rule_freeze_patch(root: Path = ROOT) -> dict[str, Any]:
    root = Path(root)
    created_utc = now_utc()
    output = clean_output(root)
    strategies_before = strategy_snapshot(root)
    family_manifest, prior_ids = prior_candidate_specs(root)
    parent_check = parent_rule_consistency(root, family_manifest)
    completeness = completeness_rows()
    formulas_frozen = all_formulas_frozen(completeness)
    parent_mismatch = bool(parent_check["parent_rule_mismatch_found"])
    candidate_ids = [candidate["candidate_id"] for candidate in PATCHED_CANDIDATES]
    candidate_membership_changed = prior_ids != candidate_ids
    next_action = NEXT_ACTION_MANUAL if parent_mismatch or not formulas_frozen or candidate_membership_changed else NEXT_ACTION_RUN
    manifest: dict[str, Any] = {
        "artifact": "risk_controlled_high_return_rule_freeze_patch",
        "created_utc": created_utc,
        "output_dir": str(output),
        **MANIFEST_BASE_FLAGS,
        "candidate_membership_changed": candidate_membership_changed,
        "parent_rule_mismatch_found": parent_mismatch,
        "all_formulas_frozen": formulas_frozen,
        "dual_momentum_volatility_formula_frozen": True,
        "donchian_risk_budget_formula_frozen": True,
        "candidate_ids": candidate_ids,
        "prior_candidate_ids": prior_ids,
        "candidate_specs": PATCHED_CANDIDATES,
        "parent_rule_consistency": parent_check,
        "next_action": next_action,
    }

    write_json(output / "risk_controlled_rule_freeze_manifest.json", manifest)
    (output / "risk_controlled_rule_freeze_summary.md").write_text(summary_md(created_utc, output, manifest), encoding="utf-8")
    (output / "rc_dual_momentum_vol_scaled_frozen_rule.md").write_text(dual_rule_md(), encoding="utf-8")
    (output / "rc_donchian_risk_budget_frozen_rule.md").write_text(donchian_rule_md(), encoding="utf-8")
    (output / "parent_rule_consistency_check.md").write_text(parent_check_md(parent_check), encoding="utf-8")
    write_csv_rows(
        output / "risk_controlled_formula_completeness_check.csv",
        completeness,
        ["candidate_id", "area", "required_detail", "status", "value"],
    )
    (output / "risk_controlled_rule_freeze_candidate_specs.yaml").write_text(
        yaml.safe_dump({"candidates": PATCHED_CANDIDATES}, sort_keys=False, width=120, allow_unicode=False),
        encoding="utf-8",
    )
    (output / "risk_controlled_rule_freeze_do_not_run_now.md").write_text(do_not_run_md(), encoding="utf-8")
    (output / "risk_controlled_rule_freeze_next_action.md").write_text(next_action_md(next_action), encoding="utf-8")

    registry_updated, roadmap_updated = update_metadata(root, output, created_utc, manifest)
    manifest["registry_metadata_updated"] = registry_updated
    manifest["roadmap_updated"] = roadmap_updated
    write_json(output / "risk_controlled_rule_freeze_manifest.json", manifest)

    strategies_after = strategy_snapshot(root)
    check = consistency_check(output, manifest, strategies_before, strategies_after)
    write_json(output / "risk_controlled_rule_freeze_consistency_check.json", check)
    return {
        "output_dir": str(output),
        "manifest": manifest,
        "consistency_check": check,
    }


def main() -> None:
    result = run_risk_controlled_high_return_rule_freeze_patch(ROOT)
    manifest = result["manifest"]
    check = result["consistency_check"]
    print(f"risk-controlled rule-freeze patch written: {result['output_dir']}")
    print(f"candidate_membership_changed: {manifest['candidate_membership_changed']}")
    print(f"parent_rule_mismatch_found: {manifest['parent_rule_mismatch_found']}")
    print(f"all_formulas_frozen: {manifest['all_formulas_frozen']}")
    print(f"next action: {manifest['next_action']}")
    print(f"consistency_passed: {check['consistency_passed']}")
    if not check["consistency_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
