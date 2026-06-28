from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

import run_risk_controlled_high_return_manual_review as review


def write_fixture(root: Path) -> None:
    registry_path = root / review.REGISTRY_PATH
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        yaml.safe_dump(
            {
                "registry": {
                    "schema_version": 1,
                    "project": "trading_tournament",
                    "research_only": True,
                    "current_next_action": "manual_review_required_for_risk_controlled_high_return_batch",
                    "real_money_recommendation": False,
                    "broker_integration": False,
                    "live_orders": False,
                },
                "strategies": [
                    {
                        "id": "dual_momentum_paa_clean_v1",
                        "status": "discovery_reject",
                        "paper_forward_active": False,
                        "candidate_exhaustive_run": False,
                    },
                    {
                        "id": "donchian_atr_breakout_etf_v1",
                        "status": "discovery_reject",
                        "paper_forward_active": False,
                        "candidate_exhaustive_run": False,
                    },
                    {
                        "id": "paper_forward_vm_quality_lowvol_proxy_v1",
                        "status": "active_observation",
                        "paper_forward_active": True,
                        "candidate_exhaustive_run": False,
                    },
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    roadmap_path = root / review.ROADMAP_PATH
    roadmap_path.parent.mkdir(parents=True, exist_ok=True)
    roadmap_path.write_text(
        "# Research Roadmap\n\nCurrent next action: `manual_review_required_for_risk_controlled_high_return_batch`\n",
        encoding="utf-8",
    )

    family_manifest = root / review.FAMILY_REVIEW_DIR / "risk_controlled_high_return_manifest.json"
    family_manifest.parent.mkdir(parents=True, exist_ok=True)
    family_manifest.write_text(
        json.dumps(
            {
                "candidate_count": 2,
                "candidate_ids": [
                    "rc_dual_momentum_paa_vol_scaled_v1",
                    "rc_donchian_breakout_risk_budget_v1",
                ],
                "candidate_specs": [
                    {
                        "candidate_id": "rc_dual_momentum_paa_vol_scaled_v1",
                        "exact_rejected_parent_row": "dual_momentum_paa_clean_v1",
                        "one_major_changed_dimension": "volatility_scaling",
                    },
                    {
                        "candidate_id": "rc_donchian_breakout_risk_budget_v1",
                        "data_requirements": ["55-day high", "20-day low", "ATR(14)"],
                        "exact_rejected_parent_row": "donchian_atr_breakout_etf_v1",
                        "one_major_changed_dimension": "risk_budget_sizing",
                        "signal_rule": "Use the parent Donchian breakout condition: close above the prior 55-day high.",
                    },
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    freeze_manifest = root / review.RULE_FREEZE_DIR / "risk_controlled_rule_freeze_manifest.json"
    freeze_manifest.parent.mkdir(parents=True, exist_ok=True)
    freeze_manifest.write_text(
        json.dumps(
            {
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
                "parent_rule_mismatch_found": True,
                "all_formulas_frozen": True,
                "dual_momentum_volatility_formula_frozen": True,
                "donchian_risk_budget_formula_frozen": True,
                "next_action": "manual_review_required_for_risk_controlled_high_return_batch",
                "candidate_specs": [
                    {
                        "candidate_id": "rc_dual_momentum_paa_vol_scaled_v1",
                        "one_major_changed_dimension": "volatility_scaling",
                        "parent_interaction": {
                            "parent_ranking_unchanged": True,
                            "parent_absolute_momentum_gate_unchanged": True,
                            "universe_unchanged": True,
                            "no_leverage": True,
                            "no_shorting": True,
                            "no_options_futures_intraday": True,
                        },
                    },
                    {
                        "candidate_id": "rc_donchian_breakout_risk_budget_v1",
                        "one_major_changed_dimension": "risk_budget_sizing",
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
                            "exposure_cap_per_position_pct_of_equity": 0.25,
                            "max_positions": 2,
                        },
                    },
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    parent_rule = root / review.PARENT_DONCHIAN_PATH
    parent_rule.parent.mkdir(parents=True, exist_ok=True)
    parent_rule.write_text(
        """# Second Expansion Candidate Specs Patched

## donchian_atr_breakout_etf_v1

- Use prior completed daily data only.
- Entry: enter long at next valid open when prior close is above the prior 20-day high.
- The prior 20-day high excludes the signal day's close.
- ATR lookback: 14 trading days.
- Initial stop threshold: entry price minus 2.0 times ATR(14), using ATR known before entry.
- Daily-data stop timing: close-based stop signal only; if prior close is at or below the stop threshold, exit at the next valid open.
- No trailing stop; initial stop only.
- Exit when earliest occurs: close-based ATR stop signal, max holding period of 20 trading days, missing/stale data forced-exit rule, or abnormal data pause rule.
- Sizing: max 2 open positions, equal notional position sizing, no leverage, no shorting.
""",
        encoding="utf-8",
    )


@pytest.fixture(scope="module")
def manual_review_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    root = tmp_path_factory.mktemp("risk_controlled_high_return_manual_review")
    write_fixture(root)
    strategies_before = yaml.safe_load((root / review.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result = review.run_risk_controlled_high_return_manual_review(root)
    strategies_after = yaml.safe_load((root / review.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result["strategies_before"] = strategies_before
    result["strategies_after"] = strategies_after
    return result


def output(manual_review_run: dict[str, Any]) -> Path:
    return Path(manual_review_run["output_dir"])


def manifest(manual_review_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(manual_review_run) / "risk_controlled_manual_review_manifest.json").read_text(encoding="utf-8"))


def consistency(manual_review_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads(
        (output(manual_review_run) / "risk_controlled_manual_review_consistency_check.json").read_text(encoding="utf-8")
    )


def test_manual_review_only_mode(manual_review_run: dict[str, Any]) -> None:
    assert manifest(manual_review_run)["manual_review_only"] is True


def test_no_backtest(manual_review_run: dict[str, Any]) -> None:
    assert manifest(manual_review_run)["backtests_run"] is False


def test_no_discovery(manual_review_run: dict[str, Any]) -> None:
    assert manifest(manual_review_run)["discovery_run"] is False


def test_no_new_performance_metrics(manual_review_run: dict[str, Any]) -> None:
    assert manifest(manual_review_run)["new_performance_metrics_computed"] is False


def test_no_provider_download(manual_review_run: dict[str, Any]) -> None:
    assert manifest(manual_review_run)["provider_download"] is False


def test_no_intraday_data_used(manual_review_run: dict[str, Any]) -> None:
    assert manifest(manual_review_run)["intraday_data_used"] is False


def test_no_candidate_exhaustive(manual_review_run: dict[str, Any]) -> None:
    assert manifest(manual_review_run)["candidate_exhaustive_run"] is False


def test_no_paper_forward_action(manual_review_run: dict[str, Any]) -> None:
    loaded = manifest(manual_review_run)
    assert loaded["paper_forward_review"] is False
    assert loaded["paper_forward_activation"] is False


def test_no_broker_live_path(manual_review_run: dict[str, Any]) -> None:
    loaded = manifest(manual_review_run)
    assert loaded["broker_path_touched"] is False
    assert loaded["live_orders"] is False


def test_no_real_money_recommendation(manual_review_run: dict[str, Any]) -> None:
    assert manifest(manual_review_run)["real_money_recommendation"] is False


def test_exact_rejected_variants_remain_closed(manual_review_run: dict[str, Any]) -> None:
    assert manifest(manual_review_run)["exact_rejected_variants_reopened"] is False
    assert manual_review_run["strategies_before"] == manual_review_run["strategies_after"]


def test_intraday_remains_paused(manual_review_run: dict[str, Any]) -> None:
    assert manifest(manual_review_run)["intraday_research_remains_paused"] is True


def test_dual_momentum_manual_review_exists(manual_review_run: dict[str, Any]) -> None:
    assert (output(manual_review_run) / "dual_momentum_manual_review.md").exists()
    assert manifest(manual_review_run)["dual_momentum_formula_accepted"] is True


def test_donchian_mismatch_review_exists(manual_review_run: dict[str, Any]) -> None:
    assert (output(manual_review_run) / "donchian_parent_mismatch_review.md").exists()
    assert manifest(manual_review_run)["donchian_parent_mismatch_found"] is True


def test_prior_55_day_language_invalidation_file_exists(manual_review_run: dict[str, Any]) -> None:
    assert (output(manual_review_run) / "invalidated_prior_55_day_language.md").exists()
    assert manifest(manual_review_run)["prior_55_day_language_invalidated"] is True


def test_official_corrected_candidate_rules_file_exists(manual_review_run: dict[str, Any]) -> None:
    assert (output(manual_review_run) / "official_corrected_candidate_rules.md").exists()
    loaded = manifest(manual_review_run)
    assert loaded["official_donchian_rule_uses_20_day_breakout"] is True
    assert loaded["donchian_candidate_accepted_for_future_discovery"] is True


def test_decision_is_valid_and_approves_batch(manual_review_run: dict[str, Any]) -> None:
    loaded = manifest(manual_review_run)
    assert loaded["decision"] in review.VALID_DECISIONS
    assert loaded["decision"] == "approve_risk_controlled_high_return_discovery_batch_after_manual_review"


def test_next_action_is_valid_and_does_not_run_now(manual_review_run: dict[str, Any]) -> None:
    loaded = manifest(manual_review_run)
    assert loaded["next_action"] in review.VALID_NEXT_ACTIONS
    assert loaded["next_action"] == "run_risk_controlled_high_return_discovery_batch"
    assert loaded["candidate_count_for_future_discovery"] == 2


def test_manifest_flags_match_strict_scope(manual_review_run: dict[str, Any]) -> None:
    loaded = manifest(manual_review_run)
    for key, value in review.MANIFEST_FLAGS.items():
        assert loaded[key] == value
    assert consistency(manual_review_run)["consistency_passed"] is True
