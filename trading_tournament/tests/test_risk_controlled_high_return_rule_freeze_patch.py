from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

import run_risk_controlled_high_return_rule_freeze_patch as patch


def write_fixture(root: Path) -> None:
    registry_path = root / patch.REGISTRY_PATH
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        yaml.safe_dump(
            {
                "registry": {
                    "schema_version": 1,
                    "project": "trading_tournament",
                    "research_only": True,
                    "current_next_action": "freeze_risk_controlled_high_return_rules_before_discovery",
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

    roadmap_path = root / patch.ROADMAP_PATH
    roadmap_path.parent.mkdir(parents=True, exist_ok=True)
    roadmap_path.write_text(
        "# Research Roadmap\n\nCurrent next action: `freeze_risk_controlled_high_return_rules_before_discovery`\n",
        encoding="utf-8",
    )

    family_manifest = root / patch.FAMILY_REVIEW_DIR / "risk_controlled_high_return_manifest.json"
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
                        "lane": "macro_gld_duration_risk_off_lane",
                    },
                    {
                        "candidate_id": "rc_donchian_breakout_risk_budget_v1",
                        "data_requirements": ["55-day high", "20-day low", "ATR(14)"],
                        "exact_rejected_parent_row": "donchian_atr_breakout_etf_v1",
                        "one_major_changed_dimension": "risk_budget_sizing",
                        "lane": "moderate_tactical_etf_lane",
                        "signal_rule": "Use the parent Donchian breakout condition: close above the prior 55-day high.",
                    },
                ],
                "backtests_run": False,
                "discovery_run": False,
                "provider_download": False,
                "intraday_data_used": False,
                "next_action": "run_risk_controlled_high_return_discovery_batch",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    parent_rule = root / patch.SECOND_RULE_FREEZE_PATH
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
def patch_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    root = tmp_path_factory.mktemp("risk_controlled_rule_freeze_patch")
    write_fixture(root)
    strategies_before = yaml.safe_load((root / patch.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result = patch.run_risk_controlled_high_return_rule_freeze_patch(root)
    strategies_after = yaml.safe_load((root / patch.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result["strategies_before"] = strategies_before
    result["strategies_after"] = strategies_after
    return result


def output(patch_run: dict[str, Any]) -> Path:
    return Path(patch_run["output_dir"])


def manifest(patch_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(patch_run) / "risk_controlled_rule_freeze_manifest.json").read_text(encoding="utf-8"))


def consistency(patch_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads(
        (output(patch_run) / "risk_controlled_rule_freeze_consistency_check.json").read_text(encoding="utf-8")
    )


def completeness_rows(patch_run: dict[str, Any]) -> list[dict[str, str]]:
    with (output(patch_run) / "risk_controlled_formula_completeness_check.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        return list(csv.DictReader(handle))


def test_rule_freeze_patch_only(patch_run: dict[str, Any]) -> None:
    assert manifest(patch_run)["rule_freeze_patch_only"] is True


def test_candidate_membership_unchanged(patch_run: dict[str, Any]) -> None:
    loaded = manifest(patch_run)
    assert loaded["candidate_membership_changed"] is False
    assert loaded["candidate_ids"] == loaded["prior_candidate_ids"]
    assert loaded["candidate_ids"] == [
        "rc_dual_momentum_paa_vol_scaled_v1",
        "rc_donchian_breakout_risk_budget_v1",
    ]


def test_candidate_count_exactly_two(patch_run: dict[str, Any]) -> None:
    assert manifest(patch_run)["candidate_count"] == 2


def test_no_backtest(patch_run: dict[str, Any]) -> None:
    assert manifest(patch_run)["backtests_run"] is False


def test_no_discovery(patch_run: dict[str, Any]) -> None:
    assert manifest(patch_run)["discovery_run"] is False


def test_no_new_performance_metrics(patch_run: dict[str, Any]) -> None:
    assert manifest(patch_run)["new_performance_metrics_computed"] is False


def test_no_provider_download(patch_run: dict[str, Any]) -> None:
    assert manifest(patch_run)["provider_download"] is False


def test_no_intraday_data_used(patch_run: dict[str, Any]) -> None:
    assert manifest(patch_run)["intraday_data_used"] is False


def test_no_candidate_exhaustive(patch_run: dict[str, Any]) -> None:
    assert manifest(patch_run)["candidate_exhaustive_run"] is False


def test_no_paper_forward_action(patch_run: dict[str, Any]) -> None:
    loaded = manifest(patch_run)
    assert loaded["paper_forward_review"] is False
    assert loaded["paper_forward_activation"] is False


def test_no_broker_live_path(patch_run: dict[str, Any]) -> None:
    loaded = manifest(patch_run)
    assert loaded["broker_path_touched"] is False
    assert loaded["live_orders"] is False


def test_exact_rejected_variants_remain_closed(patch_run: dict[str, Any]) -> None:
    loaded = manifest(patch_run)
    assert loaded["exact_rejected_variants_reopened"] is False
    assert patch_run["strategies_before"] == patch_run["strategies_after"]


def test_dual_momentum_volatility_formula_fully_frozen(patch_run: dict[str, Any]) -> None:
    loaded = manifest(patch_run)
    rows = [row for row in completeness_rows(patch_run) if row["candidate_id"] == "rc_dual_momentum_paa_vol_scaled_v1"]
    assert loaded["dual_momentum_volatility_formula_frozen"] is True
    assert rows
    assert all(row["status"] == "frozen" for row in rows)


def test_donchian_risk_budget_formula_fully_frozen(patch_run: dict[str, Any]) -> None:
    loaded = manifest(patch_run)
    rows = [row for row in completeness_rows(patch_run) if row["candidate_id"] == "rc_donchian_breakout_risk_budget_v1"]
    assert loaded["donchian_risk_budget_formula_frozen"] is True
    assert rows
    assert all(row["status"] == "frozen" for row in rows)


def test_parent_rule_consistency_check_exists(patch_run: dict[str, Any]) -> None:
    assert (output(patch_run) / "parent_rule_consistency_check.md").exists()


def test_parent_rule_mismatch_flag_recorded(patch_run: dict[str, Any]) -> None:
    loaded = manifest(patch_run)
    assert loaded["parent_rule_mismatch_found"] is True
    assert loaded["parent_rule_consistency"]["mismatch_label"] == "parent_rule_mismatch_requires_manual_review"
    assert consistency(patch_run)["parent_rule_mismatch_flag_recorded"] is True


def test_each_candidate_changes_exactly_one_dimension(patch_run: dict[str, Any]) -> None:
    dimensions = [candidate["one_major_changed_dimension"] for candidate in manifest(patch_run)["candidate_specs"]]
    assert dimensions == ["volatility_scaling", "risk_budget_sizing"]


def test_intraday_remains_paused(patch_run: dict[str, Any]) -> None:
    assert manifest(patch_run)["intraday_research_remains_paused"] is True


def test_next_action_is_valid_and_manual_review(patch_run: dict[str, Any]) -> None:
    loaded = manifest(patch_run)
    assert loaded["next_action"] in patch.VALID_NEXT_ACTIONS
    assert loaded["next_action"] == "manual_review_required_for_risk_controlled_high_return_batch"


def test_manifest_flags_match_strict_scope(patch_run: dict[str, Any]) -> None:
    loaded = manifest(patch_run)
    for key, value in patch.MANIFEST_BASE_FLAGS.items():
        assert loaded[key] == value
    assert loaded["all_formulas_frozen"] is True
    assert consistency(patch_run)["consistency_passed"] is True
