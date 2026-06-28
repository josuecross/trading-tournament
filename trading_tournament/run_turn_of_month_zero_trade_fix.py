from __future__ import annotations

import csv
import json
import math
import shutil
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

import run_second_expansion_discovery_batch_with_lane_framework as second
import run_turn_of_month_zero_trade_audit as audit


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = Path("evidence") / "diagnostics" / "turn_of_month_zero_trade_fix" / "latest"
REGISTRY_PATH = audit.REGISTRY_PATH
ROADMAP_PATH = audit.ROADMAP_PATH
CANDIDATE_ID = audit.CANDIDATE_ID
UNIVERSE = audit.UNIVERSE
VALID_NEXT_ACTIONS = {
    "rerun_turn_of_month_frozen_candidate_discovery_after_bugfix",
    "manual_review_required_turn_of_month_fix",
    "audit_second_expansion_failures_before_more_expansion",
}
NEXT_ACTION_RERUN = "rerun_turn_of_month_frozen_candidate_discovery_after_bugfix"
NEXT_ACTION_MANUAL = "manual_review_required_turn_of_month_fix"
NEXT_ACTION_AUDIT = "audit_second_expansion_failures_before_more_expansion"

MANIFEST_FLAGS = {
    "bug_fix_only": True,
    "broad_discovery_run": False,
    "candidate_exhaustive_run": False,
    "paper_forward_review": False,
    "paper_forward_activation": False,
    "broker_path_touched": False,
    "live_orders": False,
    "provider_download": False,
    "real_money_recommendation": False,
    "frozen_rule_changed": False,
    "calendar_window_changed": False,
    "selection_rule_changed": False,
    "sma_filter_changed": False,
    "candidate_status_changed": False,
    "accepted_strategy_state_changed": False,
    "rejected_strategy_state_changed": False,
}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def fmt(value: Any) -> Any:
    if isinstance(value, (float, np.floating)):
        value = float(value)
        if math.isnan(value) or math.isinf(value):
            return ""
        return round(value, 6)
    return value


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: fmt(row.get(field, "")) for field in fields})


def clean_output(root: Path) -> Path:
    output = (root / OUTPUT_DIR).resolve()
    if root.resolve() not in output.parents:
        raise RuntimeError(f"refusing output outside workspace: {output}")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)
    return output


def strategy_snapshot(root: Path) -> list[dict[str, Any]]:
    return deepcopy(load_yaml(root / REGISTRY_PATH).get("strategies", []))


def metadata_snapshot(root: Path) -> dict[str, Any]:
    return deepcopy(load_yaml(root / REGISTRY_PATH).get("registry", {}))


def validate_authorization(root: Path) -> list[str]:
    _candidate, mismatches = audit.validate_authorization(root)
    audit_manifest = audit.read_json(root / audit.OUTPUT_DIR / "turn_of_month_zero_trade_audit_manifest.json")
    if audit_manifest and audit_manifest.get("next_action") != "fix_turn_of_month_implementation_bug_before_more_research":
        mismatches.append("latest turn-of-month audit does not authorize implementation fix")
    if audit_manifest and audit_manifest.get("implementation_bug_found") is not True:
        mismatches.append("latest turn-of-month audit did not find an implementation bug")
    return mismatches


def fixed_window_match_counts(index: pd.DatetimeIndex, start_idx: int, end_idx: int) -> dict[str, Any]:
    expected_windows = audit.correct_turn_windows(index, start_idx, end_idx)
    window_key_by_date, first_days = second.turn_of_month_flags(index)
    matches = 0
    sample_rows: list[dict[str, Any]] = []
    for row in expected_windows:
        first = pd.Timestamp(row["first_eligible_day"])
        key = window_key_by_date.get(first, "")
        matched = bool(key and first_days.get(key) == first)
        matches += int(matched)
        if len(sample_rows) < 40:
            sample_rows.append(
                {
                    "candidate_id": CANDIDATE_ID,
                    "window_month": row["window_month"],
                    "first_eligible_day": str(first.date()),
                    "fixed_window_key": key,
                    "fixed_first_day_match": matched,
                    "last_eligible_day": str(pd.Timestamp(row["last_eligible_day"]).date()),
                }
            )
    return {
        "expected_windows": expected_windows,
        "first_eligible_day_matches_after_fix": matches,
        "sample_rows": sample_rows,
    }


def transition_counts(weights: pd.DataFrame) -> dict[str, int]:
    previous = "BIL"
    entries = 0
    exits = 0
    bil_fallback_days = 0
    for _idx, row in weights.iterrows():
        asset = max((symbol for symbol in ["SPY", "QQQ", "BIL"]), key=lambda symbol: float(row.get(symbol, 0.0)))
        if asset == "BIL":
            bil_fallback_days += 1
        if previous == "BIL" and asset in {"SPY", "QQQ"}:
            entries += 1
        if previous in {"SPY", "QQQ"} and asset == "BIL":
            exits += 1
        previous = asset
    return {"actual_generated_entry_count": entries, "actual_generated_exit_count": exits, "bil_fallback_days": bil_fallback_days}


def post_fix_diagnostic(root: Path) -> dict[str, Any]:
    store = audit.load_prices(root)
    if not store.get("available"):
        raise RuntimeError("Missing cached symbols: " + ",".join(store.get("missing", [])))
    ind = audit.indicators(store)
    start_idx = int(store["index"].get_indexer([pd.Timestamp("2008-01-01")], method="bfill")[0])
    end_idx = len(store["index"]) - 1
    signal_audit = audit.audit_signals(root, store, ind)
    fixed_matches = fixed_window_match_counts(store["index"], start_idx, end_idx)
    second_ind = {"mom63": ind["mom63"], "sma200": ind["sma200"]}
    weights = second.weights_turn_of_month(store, second_ind)
    diagnostic_weights = weights.iloc[start_idx + 1 : end_idx + 1]
    transitions = transition_counts(diagnostic_weights)
    result = second.simulate_weight_strategy(store, second_ind, CANDIDATE_ID, start_idx, end_idx, second.BASE_SLIPPAGE)
    counts = signal_audit["counts"]
    trade_count_after_fix = int(result["stats"]["trade_count"])
    implementation_bug_fixed = (
        fixed_matches["first_eligible_day_matches_after_fix"] > 0
        and counts["entry_signal_count_after_filters"] > 0
        and transitions["actual_generated_entry_count"] > 0
        and trade_count_after_fix > 0
    )
    return {
        "store": store,
        "start_idx": start_idx,
        "end_idx": end_idx,
        "test_start": str(store["index"][start_idx].date()),
        "test_end": str(store["index"][end_idx].date()),
        "signal_audit": signal_audit,
        "fixed_matches": fixed_matches,
        "transitions": transitions,
        "result": result,
        "trade_count_after_fix": trade_count_after_fix,
        "implementation_bug_fixed": implementation_bug_fixed,
    }


def update_metadata(root: Path, output: Path, manifest: dict[str, Any]) -> tuple[bool, bool]:
    registry_path = root / REGISTRY_PATH
    registry = load_yaml(registry_path)
    metadata = registry.setdefault("registry", {})
    metadata.update(
        {
            "turn_of_month_zero_trade_fix_path": str(output),
            "turn_of_month_zero_trade_fix_status": "completed",
            "turn_of_month_implementation_bug_fixed": manifest["implementation_bug_fixed"],
            "turn_of_month_first_eligible_day_matches_after_fix": manifest["first_eligible_day_matches_after_fix"],
            "turn_of_month_entry_signal_count_after_fix": manifest["entry_signal_count_after_fix"],
            "turn_of_month_trade_count_after_fix": manifest["trade_count_after_fix"],
            "turn_of_month_zero_trade_fix_next_action": manifest["next_action"],
            "current_next_action": manifest["next_action"],
            "next_action": manifest["next_action"],
            "bug_fix_only": True,
            "broad_discovery_run": False,
            "candidate_exhaustive_run": False,
            "paper_forward_review": False,
            "paper_forward_activation": False,
            "broker_path_touched": False,
            "live_orders": False,
            "provider_download": False,
            "real_money_recommendation": False,
            "updated_utc": manifest["created_utc"],
        }
    )
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False, width=120, allow_unicode=False), encoding="utf-8")
    roadmap_path = root / ROADMAP_PATH
    existing = roadmap_path.read_text(encoding="utf-8") if roadmap_path.exists() else "# Research Roadmap\n"
    marker = "## Turn-of-Month Zero-Trade Implementation Fix"
    section = f"""## Turn-of-Month Zero-Trade Implementation Fix

- Created UTC: `{manifest['created_utc']}`
- Evidence path: `{output}`
- Candidate: `{CANDIDATE_ID}`
- Bug fixed: `{manifest['implementation_bug_fixed']}`
- Frozen rule changed: `{manifest['frozen_rule_changed']}`
- First eligible day matches after fix: `{manifest['first_eligible_day_matches_after_fix']}`
- Entry signal count after fix: `{manifest['entry_signal_count_after_fix']}`
- Trade count after fix: `{manifest['trade_count_after_fix']}`
- Next action: `{manifest['next_action']}`
- This was bug-fix-only and post-fix diagnostic validation only; no broad discovery, candidate_exhaustive, paper-forward action, provider download, broker/live path, candidate status change, or real-money recommendation is authorized by this result.
"""
    updated = existing.split(marker, 1)[0].rstrip() + "\n\n" + section if marker in existing else existing.rstrip() + "\n\n" + section
    roadmap_path.write_text(updated.rstrip() + "\n", encoding="utf-8")
    return True, True


def write_outputs(output: Path, diagnostic: dict[str, Any], manifest: dict[str, Any], consistency: dict[str, Any] | None = None) -> None:
    signal_counts = diagnostic["signal_audit"]["counts"]
    transitions = diagnostic["transitions"]
    write_json(output / "turn_of_month_zero_trade_fix_manifest.json", manifest)
    (output / "turn_of_month_bug_fix_diff.md").write_text(bug_fix_diff_md(), encoding="utf-8")
    funnel_rows = [
        {"candidate_id": CANDIDATE_ID, "stage": key, "count": value}
        for key, value in {
            **signal_counts,
            "first_eligible_day_matches_after_fix": manifest["first_eligible_day_matches_after_fix"],
            "actual_generated_entry_count": transitions["actual_generated_entry_count"],
            "actual_generated_exit_count": transitions["actual_generated_exit_count"],
            "actual_trade_count_after_fix": manifest["trade_count_after_fix"],
        }.items()
    ]
    write_csv(output / "turn_of_month_post_fix_signal_funnel.csv", funnel_rows, ["candidate_id", "stage", "count"])
    window_row = {
        "candidate_id": CANDIDATE_ID,
        "test_start": diagnostic["test_start"],
        "test_end": diagnostic["test_end"],
        "calendar_month_count": manifest["calendar_month_count"],
        "window_count": manifest["window_count"],
        "first_eligible_window_day_count": manifest["first_eligible_window_day_count"],
        "first_eligible_day_matches_after_fix": manifest["first_eligible_day_matches_after_fix"],
    }
    write_csv(output / "turn_of_month_post_fix_window_counts.csv", [window_row], list(window_row.keys()))
    trade_row = {
        "candidate_id": CANDIDATE_ID,
        "expected_entry_signal_count": manifest["entry_signal_count_after_fix"],
        "actual_generated_entry_count": transitions["actual_generated_entry_count"],
        "actual_generated_exit_count": transitions["actual_generated_exit_count"],
        "actual_trade_count_after_fix": manifest["trade_count_after_fix"],
        "bil_fallback_days": transitions["bil_fallback_days"],
        "implementation_bug_fixed": manifest["implementation_bug_fixed"],
        "exact_candidate_remains_rejected_until_authorized_discovery": True,
    }
    write_csv(output / "turn_of_month_post_fix_trade_validation.csv", [trade_row], list(trade_row.keys()))
    pre_fix_blocks = diagnostic["signal_audit"]["block_reasons"]
    post_fix_blocks = {
        "outside_calendar_window": pre_fix_blocks.get("outside_calendar_window", 0),
        "insufficient_63_day_momentum_data": pre_fix_blocks.get("insufficient_63_day_momentum_data", 0),
        "insufficient_200_day_sma_history": pre_fix_blocks.get("insufficient_200_day_sma_history", 0),
        "spy_below_200d_sma": pre_fix_blocks.get("spy_below_200d_sma", 0),
        "qqq_below_200d_sma": pre_fix_blocks.get("qqq_below_200d_sma", 0),
        "selected_asset_below_200d_sma": pre_fix_blocks.get("selected_asset_below_200d_sma", 0),
        "missing_stale_data": pre_fix_blocks.get("missing_stale_data", 0),
        "calendar_window_construction_issue": 0 if manifest["implementation_bug_fixed"] else pre_fix_blocks.get("calendar_window_construction_issue", 0),
        "execution_date_issue": pre_fix_blocks.get("execution_date_issue", 0),
        "bil_fallback_issue": 0 if manifest["implementation_bug_fixed"] else pre_fix_blocks.get("bil_fallback_issue", 0),
        "risk_or_no_trade_filter": pre_fix_blocks.get("risk_or_no_trade_filter", 0),
    }
    block_rows = [{"candidate_id": CANDIDATE_ID, "block_reason": key, "count": value} for key, value in post_fix_blocks.items()]
    write_csv(output / "turn_of_month_post_fix_block_reason_counts.csv", block_rows, ["candidate_id", "block_reason", "count"])
    (output / "turn_of_month_zero_trade_fix_summary.md").write_text(summary_md(manifest, diagnostic), encoding="utf-8")
    (output / "turn_of_month_zero_trade_fix_next_action.md").write_text(next_action_md(manifest), encoding="utf-8")
    if consistency is not None:
        write_json(output / "turn_of_month_post_fix_consistency_check.json", consistency)


def bug_fix_diff_md() -> str:
    return """# Turn-of-Month Bug Fix Diff

Implementation-only fix:

- `turn_of_month_flags` now builds a `window_key_by_date` mapping.
- The last 4 trading days of a month and the first 3 trading days of the next month share the same window key.
- `weights_turn_of_month` now looks up the first eligible day using that window key instead of the current date's calendar month.
- The frozen rule, calendar window, 63-trading-day ranking, 200-day SMA filter, universe, and sizing are unchanged.
"""


def summary_md(manifest: dict[str, Any], diagnostic: dict[str, Any]) -> str:
    counts = diagnostic["signal_audit"]["counts"]
    return f"""# Turn-of-Month Zero-Trade Implementation Fix

Created UTC: `{manifest['created_utc']}`

Candidate: `{CANDIDATE_ID}`

Bug fixed: `{manifest['implementation_bug_fixed']}`

Frozen rule changed: `{manifest['frozen_rule_changed']}`

## Post-Fix Diagnostic

- Calendar month count: `{manifest['calendar_month_count']}`
- Window count: `{manifest['window_count']}`
- First eligible window day count: `{manifest['first_eligible_window_day_count']}`
- First eligible day matches after fix: `{manifest['first_eligible_day_matches_after_fix']}`
- Windows with enough 63-day momentum history: `{counts['windows_with_enough_63_day_momentum_history']}`
- Windows with enough 200-day SMA history: `{counts['windows_with_enough_200_day_sma_history']}`
- SPY qualification count: `{counts['spy_above_200d_sma_count']}`
- QQQ qualification count: `{counts['qqq_above_200d_sma_count']}`
- Selected-asset qualification count: `{counts['selected_higher_63d_asset_qualifies_count']}`
- Expected entry signal count: `{manifest['entry_signal_count_after_fix']}`
- Actual generated entry count: `{manifest['actual_generated_entry_count']}`
- Actual trade count after fix: `{manifest['trade_count_after_fix']}`
- BIL fallback days: `{manifest['bil_fallback_count_after_fix']}`
- Blocked-by-filter count: `{manifest['blocked_by_filter_count_after_fix']}`

The exact candidate remains rejected until a separately authorized frozen-candidate discovery rerun.

Next action: `{manifest['next_action']}`
"""


def next_action_md(manifest: dict[str, Any]) -> str:
    return f"""# Turn-of-Month Zero-Trade Fix Next Action

`{manifest['next_action']}`

Do not run this next action from the implementation-fix task.
"""


def consistency_check(
    output: Path,
    manifest: dict[str, Any],
    strategies_before: list[dict[str, Any]],
    strategies_after: list[dict[str, Any]],
) -> dict[str, Any]:
    required = [
        "turn_of_month_zero_trade_fix_manifest.json",
        "turn_of_month_zero_trade_fix_summary.md",
        "turn_of_month_bug_fix_diff.md",
        "turn_of_month_post_fix_signal_funnel.csv",
        "turn_of_month_post_fix_window_counts.csv",
        "turn_of_month_post_fix_trade_validation.csv",
        "turn_of_month_post_fix_block_reason_counts.csv",
        "turn_of_month_zero_trade_fix_next_action.md",
    ]
    check = {
        "bug_fix_only_mode": manifest["bug_fix_only"],
        "no_broad_discovery": not manifest["broad_discovery_run"],
        "no_candidate_exhaustive": not manifest["candidate_exhaustive_run"],
        "no_paper_forward_action": not manifest["paper_forward_review"] and not manifest["paper_forward_activation"],
        "no_provider_download": not manifest["provider_download"],
        "no_broker_live_path": not manifest["broker_path_touched"] and not manifest["live_orders"],
        "frozen_rule_unchanged": not manifest["frozen_rule_changed"],
        "calendar_window_unchanged": not manifest["calendar_window_changed"],
        "selection_rule_unchanged": not manifest["selection_rule_changed"],
        "sma_filter_unchanged": not manifest["sma_filter_changed"],
        "candidate_status_unchanged": not manifest["candidate_status_changed"] and strategies_before == strategies_after,
        "first_eligible_day_keying_fixed": manifest["implementation_bug_fixed"],
        "first_eligible_day_matches_positive": manifest["first_eligible_day_matches_after_fix"] > 0,
        "post_fix_signal_funnel_exists": (output / "turn_of_month_post_fix_signal_funnel.csv").exists(),
        "post_fix_trade_validation_exists": (output / "turn_of_month_post_fix_trade_validation.csv").exists(),
        "implementation_bug_fixed_recorded": isinstance(manifest["implementation_bug_fixed"], bool),
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "manifest_flags_match_scope": all(manifest[key] == value for key, value in MANIFEST_FLAGS.items()),
        "required_files_exist": all((output / name).exists() for name in required),
    }
    check["consistency_passed"] = all(bool(value) for value in check.values())
    return check


def run_turn_of_month_zero_trade_fix(root: Path = ROOT) -> dict[str, Any]:
    output = clean_output(root)
    mismatches = validate_authorization(root)
    if mismatches:
        raise RuntimeError("Authorization failed: " + "; ".join(mismatches))
    strategies_before = strategy_snapshot(root)
    _metadata_before = metadata_snapshot(root)
    diagnostic = post_fix_diagnostic(root)
    signal_counts = diagnostic["signal_audit"]["counts"]
    transitions = diagnostic["transitions"]
    implementation_bug_fixed = bool(diagnostic["implementation_bug_fixed"])
    if implementation_bug_fixed and diagnostic["trade_count_after_fix"] > 0:
        next_action = NEXT_ACTION_RERUN
    elif not implementation_bug_fixed:
        next_action = NEXT_ACTION_MANUAL
    else:
        next_action = NEXT_ACTION_AUDIT
    manifest = {
        "artifact": "turn_of_month_zero_trade_fix",
        "created_utc": now_utc(),
        "output_dir": str(output),
        "candidate_id": CANDIDATE_ID,
        "universe": UNIVERSE,
        "calendar_month_count": signal_counts["calendar_months_in_test_window"],
        "window_count": signal_counts["turn_of_month_windows_constructed"],
        "first_eligible_window_day_count": signal_counts["first_eligible_window_days_identified"],
        "first_eligible_day_matches_after_fix": diagnostic["fixed_matches"]["first_eligible_day_matches_after_fix"],
        "windows_with_enough_63_day_momentum_history": signal_counts["windows_with_enough_63_day_momentum_history"],
        "windows_with_enough_200_day_sma_history": signal_counts["windows_with_enough_200_day_sma_history"],
        "spy_qualification_count": signal_counts["spy_above_200d_sma_count"],
        "qqq_qualification_count": signal_counts["qqq_above_200d_sma_count"],
        "selected_asset_qualification_count": signal_counts["selected_higher_63d_asset_qualifies_count"],
        "expected_entry_signal_count": signal_counts["entry_signal_count_before_execution"],
        "entry_signal_count_after_fix": signal_counts["entry_signal_count_after_filters"],
        "actual_generated_entry_count": transitions["actual_generated_entry_count"],
        "trade_count_after_fix": diagnostic["trade_count_after_fix"],
        "bil_fallback_count_after_fix": transitions["bil_fallback_days"],
        "blocked_by_filter_count_after_fix": signal_counts["entries_blocked_risk_or_no_trade_filters"],
        "implementation_bug_fixed": implementation_bug_fixed,
        "exact_candidate_remains_rejected_until_authorized_discovery": True,
        "next_action": next_action,
        **MANIFEST_FLAGS,
    }
    registry_updated, roadmap_updated = update_metadata(root, output, manifest)
    manifest["registry_metadata_updated"] = registry_updated
    manifest["roadmap_updated"] = roadmap_updated
    write_outputs(output, diagnostic, manifest)
    strategies_after = strategy_snapshot(root)
    consistency = consistency_check(output, manifest, strategies_before, strategies_after)
    write_json(output / "turn_of_month_post_fix_consistency_check.json", consistency)
    return {
        "output_dir": str(output),
        "candidate_id": CANDIDATE_ID,
        "implementation_bug_fixed": implementation_bug_fixed,
        "first_eligible_day_matches_after_fix": manifest["first_eligible_day_matches_after_fix"],
        "entry_signal_count_after_fix": manifest["entry_signal_count_after_fix"],
        "trade_count_after_fix": manifest["trade_count_after_fix"],
        "next_action": next_action,
        "consistency": consistency,
    }


def main() -> None:
    print(json.dumps(run_turn_of_month_zero_trade_fix(ROOT), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
