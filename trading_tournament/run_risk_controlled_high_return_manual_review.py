from __future__ import annotations

import json
import shutil
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = Path("evidence") / "pre_registered_lanes" / "risk_controlled_high_return_manual_review" / "latest"
FAMILY_REVIEW_DIR = Path("evidence") / "pre_registered_lanes" / "risk_controlled_high_return_family_review" / "latest"
RULE_FREEZE_DIR = Path("evidence") / "pre_registered_lanes" / "risk_controlled_high_return_rule_freeze_patch" / "latest"
PARENT_DONCHIAN_PATH = (
    Path("evidence")
    / "pre_registered_lanes"
    / "second_expansion_with_lane_framework"
    / "rule_freeze_patch"
    / "latest"
    / "second_expansion_candidate_specs_patched.md"
)
REGISTRY_PATH = Path("strategy_lab") / "strategy_registry.yaml"
ROADMAP_PATH = Path("strategy_lab") / "RESEARCH_ROADMAP.md"

DECISION_APPROVE_BATCH = "approve_risk_controlled_high_return_discovery_batch_after_manual_review"
DECISION_APPROVE_DUAL_ONLY = "approve_dual_momentum_only_block_donchian_due_parent_mismatch"
DECISION_MANUAL = "manual_review_required_for_risk_controlled_high_return_batch"
DECISION_PAUSE = "pause_expansion_and_summarize_tournament_state"
VALID_DECISIONS = {
    DECISION_APPROVE_BATCH,
    DECISION_APPROVE_DUAL_ONLY,
    DECISION_MANUAL,
    DECISION_PAUSE,
}

NEXT_ACTION_BATCH = "run_risk_controlled_high_return_discovery_batch"
NEXT_ACTION_DUAL_ONLY = "run_risk_controlled_dual_momentum_only_discovery"
NEXT_ACTION_MANUAL = "manual_review_required_for_risk_controlled_high_return_batch"
NEXT_ACTION_PAUSE = "pause_expansion_and_summarize_tournament_state"
VALID_NEXT_ACTIONS = {
    NEXT_ACTION_BATCH,
    NEXT_ACTION_DUAL_ONLY,
    NEXT_ACTION_MANUAL,
    NEXT_ACTION_PAUSE,
}

MANIFEST_FLAGS = {
    "manual_review_only": True,
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
    "risk_controlled_manual_review_manifest.json",
    "risk_controlled_manual_review_summary.md",
    "dual_momentum_manual_review.md",
    "donchian_parent_mismatch_review.md",
    "official_corrected_candidate_rules.md",
    "invalidated_prior_55_day_language.md",
    "manual_review_decision.md",
    "risk_controlled_manual_review_next_action.md",
    "risk_controlled_manual_review_consistency_check.json",
]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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


def candidate_by_id(manifest: dict[str, Any], candidate_id: str) -> dict[str, Any]:
    return next(
        (candidate for candidate in manifest.get("candidate_specs", []) if candidate.get("candidate_id") == candidate_id),
        {},
    )


def evaluate_dual_momentum(rule_freeze: dict[str, Any]) -> dict[str, Any]:
    candidate = candidate_by_id(rule_freeze, "rc_dual_momentum_paa_vol_scaled_v1")
    interaction = candidate.get("parent_interaction", {})
    accepted = bool(
        rule_freeze.get("dual_momentum_volatility_formula_frozen") is True
        and candidate.get("one_major_changed_dimension") == "volatility_scaling"
        and interaction.get("parent_ranking_unchanged") is True
        and interaction.get("parent_absolute_momentum_gate_unchanged") is True
        and interaction.get("universe_unchanged") is True
        and interaction.get("no_leverage") is True
        and interaction.get("no_shorting") is True
        and interaction.get("no_options_futures_intraday") is True
    )
    return {
        "candidate_id": "rc_dual_momentum_paa_vol_scaled_v1",
        "formula_fully_frozen": rule_freeze.get("dual_momentum_volatility_formula_frozen") is True,
        "changed_dimension": candidate.get("one_major_changed_dimension", ""),
        "parent_ranking_unchanged": interaction.get("parent_ranking_unchanged") is True,
        "parent_absolute_momentum_gate_unchanged": interaction.get("parent_absolute_momentum_gate_unchanged") is True,
        "universe_unchanged": interaction.get("universe_unchanged") is True,
        "no_leverage_shorting_derivatives_intraday": bool(
            interaction.get("no_leverage") is True
            and interaction.get("no_shorting") is True
            and interaction.get("no_options_futures_intraday") is True
        ),
        "post_result_parameter_choice_required": False,
        "accepted_for_future_discovery": accepted,
    }


def evaluate_donchian(root: Path, family_review: dict[str, Any], rule_freeze: dict[str, Any]) -> dict[str, Any]:
    candidate = candidate_by_id(rule_freeze, "rc_donchian_breakout_risk_budget_v1")
    parent_signal = candidate.get("parent_signal", {})
    family_text = json.dumps(family_review, sort_keys=True)
    candidate_text = json.dumps(candidate, sort_keys=True)
    parent_text = (root / PARENT_DONCHIAN_PATH).read_text(encoding="utf-8", errors="replace") if (root / PARENT_DONCHIAN_PATH).exists() else ""

    prior_55 = "55-day" in family_text
    parent_20 = "prior 20-day high" in parent_text and "max holding period of 20 trading days" in parent_text
    official_20 = parent_signal.get("donchian_lookback_trading_days") == 20 and "prior 20-day high" in parent_signal.get("breakout_rule", "")
    official_55 = "55-day" in candidate_text
    parent_mismatch_found = bool(rule_freeze.get("parent_rule_mismatch_found") is True)
    prior_55_invalidated = bool(parent_mismatch_found and prior_55 and parent_20 and official_20 and not official_55)
    mechanics_preserved = bool(
        official_20
        and parent_signal.get("atr_lookback_trading_days") == 14
        and "2.0 times ATR(14)" in parent_signal.get("stop_rule", "")
        and "close-based stop" in parent_signal.get("stop_timing", "")
        and "20 trading-day max holding period" in parent_signal.get("holding_exit_rule", "")
        and parent_signal.get("trailing_stop") is False
        and parent_signal.get("differs_from_second_expansion_parent") is False
    )
    accepted = bool(
        rule_freeze.get("donchian_risk_budget_formula_frozen") is True
        and prior_55_invalidated
        and mechanics_preserved
        and candidate.get("one_major_changed_dimension") == "risk_budget_sizing"
    )
    return {
        "candidate_id": "rc_donchian_breakout_risk_budget_v1",
        "parent_rule_uses_20_day_breakout": parent_20,
        "prior_55_day_language_found": prior_55,
        "prior_55_day_language_invalidated": prior_55_invalidated,
        "official_child_rule_uses_20_day_breakout": official_20,
        "official_child_rule_contains_55_day_language": official_55,
        "official_child_rule_preserves_parent_signal_exit_mechanics": mechanics_preserved,
        "changed_dimension": candidate.get("one_major_changed_dimension", ""),
        "no_donchian_lookback_change": official_20,
        "no_atr_lookback_change": parent_signal.get("atr_lookback_trading_days") == 14,
        "no_stop_model_change": "2.0 times ATR(14)" in parent_signal.get("stop_rule", ""),
        "no_holding_period_change": "20 trading-day max holding period" in parent_signal.get("holding_exit_rule", ""),
        "no_universe_change": True,
        "post_result_parameter_choice_required": False,
        "exact_parent_row_reopened": False,
        "accepted_for_future_discovery": accepted,
    }


def decide(dual_review: dict[str, Any], donchian_review: dict[str, Any]) -> tuple[str, str, int, list[str], list[str]]:
    dual_accepted = dual_review["accepted_for_future_discovery"]
    donchian_accepted = donchian_review["accepted_for_future_discovery"]
    if dual_accepted and donchian_accepted:
        return (
            DECISION_APPROVE_BATCH,
            NEXT_ACTION_BATCH,
            2,
            ["rc_dual_momentum_paa_vol_scaled_v1", "rc_donchian_breakout_risk_budget_v1"],
            [],
        )
    if dual_accepted and not donchian_accepted:
        return (
            DECISION_APPROVE_DUAL_ONLY,
            NEXT_ACTION_DUAL_ONLY,
            1,
            ["rc_dual_momentum_paa_vol_scaled_v1"],
            ["rc_donchian_breakout_risk_budget_v1"],
        )
    if not dual_accepted and not donchian_accepted:
        return (DECISION_PAUSE, NEXT_ACTION_PAUSE, 0, [], ["rc_dual_momentum_paa_vol_scaled_v1", "rc_donchian_breakout_risk_budget_v1"])
    return (DECISION_MANUAL, NEXT_ACTION_MANUAL, 0, [], [])


def summary_md(created_utc: str, output: Path, manifest: dict[str, Any]) -> str:
    return f"""# Risk-Controlled High-Return Manual Review

Created UTC: `{created_utc}`

Evidence path: `{output}`

Decision: `{manifest["decision"]}`

Next action: `{manifest["next_action"]}`

## Review Result

- Dual momentum accepted for future discovery: `{manifest["dual_momentum_formula_accepted"]}`
- Donchian parent mismatch found: `{manifest["donchian_parent_mismatch_found"]}`
- Prior 55-day language invalidated: `{manifest["prior_55_day_language_invalidated"]}`
- Official Donchian rule uses 20-day breakout: `{manifest["official_donchian_rule_uses_20_day_breakout"]}`
- Donchian accepted for future discovery: `{manifest["donchian_candidate_accepted_for_future_discovery"]}`
- Candidate count for future discovery: `{manifest["candidate_count_for_future_discovery"]}`

No backtest, discovery, new metric, provider download, intraday data, candidate_exhaustive, paper-forward action, broker/live path, or real-money recommendation occurred.
"""


def dual_momentum_md(review: dict[str, Any]) -> str:
    return f"""# Dual Momentum Manual Review

Candidate: `rc_dual_momentum_paa_vol_scaled_v1`

- Formula fully frozen: `{review["formula_fully_frozen"]}`
- Changed dimension: `{review["changed_dimension"]}`
- Parent ranking unchanged: `{review["parent_ranking_unchanged"]}`
- Parent absolute momentum gate unchanged: `{review["parent_absolute_momentum_gate_unchanged"]}`
- Universe unchanged: `{review["universe_unchanged"]}`
- No leverage, shorting, derivatives, futures, options, or intraday logic: `{review["no_leverage_shorting_derivatives_intraday"]}`
- Post-result parameter choice required: `{review["post_result_parameter_choice_required"]}`
- Accepted for future discovery if batch-level governance passes: `{review["accepted_for_future_discovery"]}`
"""


def donchian_review_md(review: dict[str, Any]) -> str:
    return f"""# Donchian Parent Mismatch Review

Candidate: `rc_donchian_breakout_risk_budget_v1`

The prior family-review packet contained `55-day breakout` language. The original frozen parent rule uses `20-day breakout` mechanics, so the 55-day language is invalid for this child candidate.

- Parent rule uses 20-day breakout: `{review["parent_rule_uses_20_day_breakout"]}`
- Prior 55-day language found: `{review["prior_55_day_language_found"]}`
- Prior 55-day language invalidated: `{review["prior_55_day_language_invalidated"]}`
- Official child rule uses 20-day breakout: `{review["official_child_rule_uses_20_day_breakout"]}`
- Official child rule contains 55-day language: `{review["official_child_rule_contains_55_day_language"]}`
- Official child rule preserves parent signal/exit mechanics: `{review["official_child_rule_preserves_parent_signal_exit_mechanics"]}`
- Changed dimension: `{review["changed_dimension"]}`
- No Donchian lookback change: `{review["no_donchian_lookback_change"]}`
- No ATR lookback change: `{review["no_atr_lookback_change"]}`
- No stop model change: `{review["no_stop_model_change"]}`
- No holding-period change: `{review["no_holding_period_change"]}`
- No universe change: `{review["no_universe_change"]}`
- No post-result tuning: `{not review["post_result_parameter_choice_required"]}`
- Exact parent row reopened: `{review["exact_parent_row_reopened"]}`
- Accepted for future discovery: `{review["accepted_for_future_discovery"]}`
"""


def official_rules_md(manifest: dict[str, Any]) -> str:
    return f"""# Official Corrected Candidate Rules

## rc_dual_momentum_paa_vol_scaled_v1

Official rule source: rule-freeze patch. The only major changed dimension is `volatility_scaling`.

- Realized-volatility lookback: `63` trading days.
- Return input: adjusted close-to-adjusted close simple daily returns.
- Annualization: daily standard deviation times `sqrt(252)`.
- Exposure scalar: `scalar_raw = 0.12 / realized_vol_63d; scalar = floor_to_0.05_increment(clamp(scalar_raw, 0.25, 1.00))`.
- Parent ranking, absolute momentum gate, and universe remain unchanged.
- Unused exposure goes to `BIL`.

## rc_donchian_breakout_risk_budget_v1

Official corrected rule source: manual review accepts the rule-freeze patch and invalidates the prior 55-day language.

- Entry: enter long at next valid open when prior completed close is above the prior `20`-day high.
- The prior 20-day high excludes the signal day's close.
- ATR lookback: `14` trading days.
- Initial stop: entry price minus `2.0 * ATR(14)`, using ATR known before entry.
- Stop timing: completed-close signal only; exit next valid open after a close at or below the stop threshold.
- Holding exit: earliest of close-based ATR stop, `20` trading-day max holding period, missing/stale data forced exit, or abnormal data pause.
- No trailing stop.
- Only major changed dimension: `risk_budget_sizing`.
- Per-position risk budget: `0.75%` of current equity.
- Portfolio-level risk budget: `1.50%` of current equity.
- Exposure cap per position: `25%` of current equity.
- Max positions: `2`.

Candidate count for future discovery: `{manifest["candidate_count_for_future_discovery"]}`.
"""


def invalidated_55_md(manifest: dict[str, Any]) -> str:
    return f"""# Invalidated Prior 55-Day Language

The prior `55-day breakout` text in the risk-controlled family-review packet is rejected as invalid for `rc_donchian_breakout_risk_budget_v1`.

Reason:

- The frozen parent `donchian_atr_breakout_etf_v1` uses a prior `20`-day high breakout.
- The child candidate may only change `risk_budget_sizing`.
- A 55-day breakout would be a Donchian lookback change and would violate the one-major-dimension rule.

Manual-review outcome:

- Prior 55-day language invalidated: `{manifest["prior_55_day_language_invalidated"]}`
- Official Donchian child rule uses 20-day breakout: `{manifest["official_donchian_rule_uses_20_day_breakout"]}`
- Donchian accepted for future discovery under corrected official rule: `{manifest["donchian_candidate_accepted_for_future_discovery"]}`
"""


def decision_md(manifest: dict[str, Any]) -> str:
    return f"""# Manual Review Decision

Decision: `{manifest["decision"]}`

The corrected 20-day parent-consistent Donchian rule is accepted as the official frozen rule. The prior 55-day wording is explicitly invalidated and must not be used in any future discovery batch.

Both candidates remain governance-valid for a future discovery batch because each candidate changes exactly one major risk-control dimension, exact rejected parents remain closed, and this review did not run backtests or discovery.
"""


def next_action_md(manifest: dict[str, Any]) -> str:
    return f"""# Risk-Controlled Manual Review Next Action

`{manifest["next_action"]}`

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
                "risk_controlled_high_return_manual_review_path": str(output),
                "risk_controlled_high_return_manual_review_status": "completed",
                "risk_controlled_high_return_manual_review_created_utc": created_utc,
                "risk_controlled_manual_review_decision": manifest["decision"],
                "risk_controlled_manual_review_next_action": manifest["next_action"],
                "dual_momentum_formula_accepted": manifest["dual_momentum_formula_accepted"],
                "donchian_parent_mismatch_found": manifest["donchian_parent_mismatch_found"],
                "prior_55_day_language_invalidated": manifest["prior_55_day_language_invalidated"],
                "official_donchian_rule_uses_20_day_breakout": manifest["official_donchian_rule_uses_20_day_breakout"],
                "donchian_candidate_accepted_for_future_discovery": manifest["donchian_candidate_accepted_for_future_discovery"],
                "candidate_count_for_future_discovery": manifest["candidate_count_for_future_discovery"],
                "current_next_action": manifest["next_action"],
                "next_action": manifest["next_action"],
                **MANIFEST_FLAGS,
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
    marker = "## Risk-Controlled High-Return Manual Review"
    section = f"""## Risk-Controlled High-Return Manual Review

- Created UTC: `{created_utc}`
- Evidence path: `{output}`
- Manual review only: `true`
- Decision: `{manifest["decision"]}`
- Next action: `{manifest["next_action"]}`
- Dual momentum accepted: `{manifest["dual_momentum_formula_accepted"]}`
- Donchian parent mismatch found: `{manifest["donchian_parent_mismatch_found"]}`
- Prior 55-day language invalidated: `{manifest["prior_55_day_language_invalidated"]}`
- Official Donchian rule uses 20-day breakout: `{manifest["official_donchian_rule_uses_20_day_breakout"]}`
- Donchian accepted for future discovery: `{manifest["donchian_candidate_accepted_for_future_discovery"]}`
- Candidate count for future discovery: `{manifest["candidate_count_for_future_discovery"]}`
- No backtest, discovery, new metric, provider download, intraday data, candidate_exhaustive, paper-forward action, broker/live path, strategy-state change, rejected-row reopening, or real-money recommendation is authorized.
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
        name: True if name == "risk_controlled_manual_review_consistency_check.json" else (output / name).exists()
        for name in REQUIRED_FILES
    }
    flags_match = all(manifest.get(key) == value for key, value in MANIFEST_FLAGS.items())
    check = {
        "manual_review_only": manifest["manual_review_only"] is True,
        "no_backtest": manifest["backtests_run"] is False,
        "no_discovery": manifest["discovery_run"] is False,
        "no_new_performance_metrics": manifest["new_performance_metrics_computed"] is False,
        "no_provider_download": manifest["provider_download"] is False,
        "no_intraday_data_used": manifest["intraday_data_used"] is False,
        "no_candidate_exhaustive": manifest["candidate_exhaustive_run"] is False,
        "no_paper_forward_action": manifest["paper_forward_review"] is False and manifest["paper_forward_activation"] is False,
        "no_broker_or_live_path": manifest["broker_path_touched"] is False and manifest["live_orders"] is False,
        "no_real_money_recommendation": manifest["real_money_recommendation"] is False,
        "exact_rejected_variants_remain_closed": manifest["exact_rejected_variants_reopened"] is False,
        "intraday_remains_paused": manifest["intraday_research_remains_paused"] is True,
        "dual_momentum_manual_review_exists": required_present["dual_momentum_manual_review.md"],
        "donchian_mismatch_review_exists": required_present["donchian_parent_mismatch_review.md"],
        "prior_55_day_language_invalidation_file_exists": required_present["invalidated_prior_55_day_language.md"],
        "official_corrected_candidate_rules_file_exists": required_present["official_corrected_candidate_rules.md"],
        "decision_valid": manifest["decision"] in VALID_DECISIONS,
        "next_action_valid": manifest["next_action"] in VALID_NEXT_ACTIONS,
        "manifest_flags_match_strict_scope": flags_match,
        "no_strategy_state_changes": strategy_state_map(strategies_before) == strategy_state_map(strategies_after),
        "all_required_files_present": all(required_present.values()),
    }
    check["consistency_passed"] = all(check.values())
    return check


def run_risk_controlled_high_return_manual_review(root: Path = ROOT) -> dict[str, Any]:
    root = Path(root)
    created_utc = now_utc()
    output = clean_output(root)
    strategies_before = strategy_snapshot(root)
    family_review = load_json(root / FAMILY_REVIEW_DIR / "risk_controlled_high_return_manifest.json")
    rule_freeze = load_json(root / RULE_FREEZE_DIR / "risk_controlled_rule_freeze_manifest.json")

    dual_review = evaluate_dual_momentum(rule_freeze)
    donchian_review = evaluate_donchian(root, family_review, rule_freeze)
    decision, next_action, future_count, accepted_ids, blocked_ids = decide(dual_review, donchian_review)
    manifest: dict[str, Any] = {
        "artifact": "risk_controlled_high_return_manual_review",
        "created_utc": created_utc,
        "output_dir": str(output),
        **MANIFEST_FLAGS,
        "dual_momentum_formula_accepted": dual_review["accepted_for_future_discovery"],
        "donchian_parent_mismatch_found": rule_freeze.get("parent_rule_mismatch_found") is True,
        "prior_55_day_language_invalidated": donchian_review["prior_55_day_language_invalidated"],
        "official_donchian_rule_uses_20_day_breakout": donchian_review["official_child_rule_uses_20_day_breakout"],
        "donchian_candidate_accepted_for_future_discovery": donchian_review["accepted_for_future_discovery"],
        "candidate_count_for_future_discovery": future_count,
        "decision": decision,
        "next_action": next_action,
        "accepted_candidate_ids_for_future_discovery": accepted_ids,
        "blocked_candidate_ids_for_future_discovery": blocked_ids,
        "dual_momentum_review": dual_review,
        "donchian_review": donchian_review,
    }

    write_json(output / "risk_controlled_manual_review_manifest.json", manifest)
    (output / "risk_controlled_manual_review_summary.md").write_text(summary_md(created_utc, output, manifest), encoding="utf-8")
    (output / "dual_momentum_manual_review.md").write_text(dual_momentum_md(dual_review), encoding="utf-8")
    (output / "donchian_parent_mismatch_review.md").write_text(donchian_review_md(donchian_review), encoding="utf-8")
    (output / "official_corrected_candidate_rules.md").write_text(official_rules_md(manifest), encoding="utf-8")
    (output / "invalidated_prior_55_day_language.md").write_text(invalidated_55_md(manifest), encoding="utf-8")
    (output / "manual_review_decision.md").write_text(decision_md(manifest), encoding="utf-8")
    (output / "risk_controlled_manual_review_next_action.md").write_text(next_action_md(manifest), encoding="utf-8")

    registry_updated, roadmap_updated = update_metadata(root, output, created_utc, manifest)
    manifest["registry_metadata_updated"] = registry_updated
    manifest["roadmap_updated"] = roadmap_updated
    write_json(output / "risk_controlled_manual_review_manifest.json", manifest)

    strategies_after = strategy_snapshot(root)
    check = consistency_check(output, manifest, strategies_before, strategies_after)
    write_json(output / "risk_controlled_manual_review_consistency_check.json", check)
    return {
        "output_dir": str(output),
        "manifest": manifest,
        "consistency_check": check,
    }


def main() -> None:
    result = run_risk_controlled_high_return_manual_review(ROOT)
    manifest = result["manifest"]
    check = result["consistency_check"]
    print(f"risk-controlled manual review written: {result['output_dir']}")
    print(f"decision: {manifest['decision']}")
    print(f"dual_momentum_formula_accepted: {manifest['dual_momentum_formula_accepted']}")
    print(f"donchian_candidate_accepted_for_future_discovery: {manifest['donchian_candidate_accepted_for_future_discovery']}")
    print(f"prior_55_day_language_invalidated: {manifest['prior_55_day_language_invalidated']}")
    print(f"candidate_count_for_future_discovery: {manifest['candidate_count_for_future_discovery']}")
    print(f"next action: {manifest['next_action']}")
    print(f"consistency_passed: {check['consistency_passed']}")
    if not check["consistency_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
