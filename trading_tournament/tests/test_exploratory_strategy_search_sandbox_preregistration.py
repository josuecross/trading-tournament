from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

import run_exploratory_strategy_search_sandbox_preregistration as sandbox


def write_cache(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "date,adj_close\n"
        "2024-01-02,100\n"
        "2024-01-03,101\n"
        "2024-01-04,102\n"
        "2024-01-05,103\n",
        encoding="utf-8",
    )


def write_fixture(root: Path) -> None:
    registry = {
        "registry": {
            "schema_version": 1,
            "project": "trading_tournament",
            "research_only": True,
            "real_money_recommendation": False,
            "broker_integration": False,
            "live_orders": False,
            "current_next_action": "pause_expansion_and_wait_for_manual_direction",
            "official_current_next_action": "pause_expansion_and_wait_for_manual_direction",
            "intraday_research_remains_paused": True,
        },
        "risk_framework": {"active_framework": "balanced_speculative_research_v1"},
        "strategies": [
            {
                "id": "paper_forward_vm_quality_lowvol_proxy_v1",
                "status": "active_paper_demo_observation",
                "paper_forward_active": True,
                "rules_frozen": True,
            },
            {
                "id": "paper_forward_dsr_sector_equal_weight_defensive_filter_v1",
                "status": "active_paper_demo_observation",
                "paper_forward_active": True,
                "rules_frozen": True,
            },
            {
                "id": "mfv_equal_weight_trend_filter_v1",
                "status": "discovery_reject",
                "paper_forward_active": False,
                "candidate_exhaustive_run": False,
            },
        ],
    }
    registry_path = root / sandbox.REGISTRY_PATH
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")

    roadmap_path = root / sandbox.ROADMAP_PATH
    roadmap_path.parent.mkdir(parents=True, exist_ok=True)
    roadmap_path.write_text(
        "# Research Roadmap\n\n## Compact Current State\n\n- Official current next action: `pause_expansion_and_wait_for_manual_direction`\n",
        encoding="utf-8",
    )
    compact_path = root / sandbox.COMPACT_STATE_PATH
    compact_path.parent.mkdir(parents=True, exist_ok=True)
    compact_path.write_text("# Current Tournament State\n", encoding="utf-8")

    all_symbols = sorted({symbol for symbols in sandbox.UNIVERSE_GROUPS.values() for symbol in symbols})
    approved = {
        "schema_version": 1,
        "symbols": [
            {
                "symbol": symbol,
                "allowed_for_strategy": True,
                "allowed_for_benchmark": True,
            }
            for symbol in all_symbols
        ],
    }
    approved_path = root / sandbox.APPROVED_SYMBOL_MAP_PATH
    approved_path.parent.mkdir(parents=True, exist_ok=True)
    approved_path.write_text(yaml.safe_dump(approved, sort_keys=False), encoding="utf-8")
    for symbol in all_symbols:
        write_cache(root / sandbox.DATA_CACHE_DIR / f"{symbol}.csv")


@pytest.fixture(scope="module")
def sandbox_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    root = tmp_path_factory.mktemp("exploratory_sandbox_preregistration")
    write_fixture(root)
    before = yaml.safe_load((root / sandbox.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result = sandbox.run_exploratory_strategy_search_sandbox_preregistration(root)
    after = yaml.safe_load((root / sandbox.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result["root"] = root
    result["strategies_before"] = before
    result["strategies_after"] = after
    return result


def output(sandbox_run: dict[str, Any]) -> Path:
    return Path(sandbox_run["output_dir"])


def manifest(sandbox_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(sandbox_run) / "exploratory_sandbox_preregistration_manifest.json").read_text(encoding="utf-8"))


def consistency(sandbox_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(sandbox_run) / "exploratory_sandbox_consistency_check.json").read_text(encoding="utf-8"))


def test_sandbox_preregistration_only_mode(sandbox_run: dict[str, Any]) -> None:
    assert manifest(sandbox_run)["sandbox_preregistration_only"] is True


def test_no_strategy_discovery(sandbox_run: dict[str, Any]) -> None:
    assert manifest(sandbox_run)["strategy_discovery_run"] is False


def test_no_backtests(sandbox_run: dict[str, Any]) -> None:
    assert manifest(sandbox_run)["backtests_run"] is False


def test_no_new_performance_metrics(sandbox_run: dict[str, Any]) -> None:
    assert manifest(sandbox_run)["new_performance_metrics_computed"] is False


def test_no_indicator_library_dependency_added(sandbox_run: dict[str, Any]) -> None:
    assert manifest(sandbox_run)["indicator_library_dependency_added"] is False


def test_no_provider_download(sandbox_run: dict[str, Any]) -> None:
    assert manifest(sandbox_run)["provider_download"] is False


def test_no_intraday_data_used(sandbox_run: dict[str, Any]) -> None:
    assert manifest(sandbox_run)["intraday_data_used"] is False


def test_no_candidate_exhaustive(sandbox_run: dict[str, Any]) -> None:
    assert manifest(sandbox_run)["candidate_exhaustive_run"] is False


def test_no_paper_forward_action(sandbox_run: dict[str, Any]) -> None:
    loaded = manifest(sandbox_run)
    assert loaded["paper_forward_review"] is False
    assert loaded["paper_forward_activation"] is False


def test_no_broker_live_action(sandbox_run: dict[str, Any]) -> None:
    loaded = manifest(sandbox_run)
    assert loaded["broker_orders_submitted"] is False
    assert loaded["broker_orders_cancelled"] is False
    assert loaded["live_orders"] is False


def test_no_real_money_recommendation(sandbox_run: dict[str, Any]) -> None:
    assert manifest(sandbox_run)["real_money_recommendation"] is False


def test_active_strategy_state_preserved(sandbox_run: dict[str, Any]) -> None:
    assert manifest(sandbox_run)["active_strategy_state_changed"] is False
    assert sandbox_run["strategies_before"] == sandbox_run["strategies_after"]


def test_rejected_strategy_state_preserved(sandbox_run: dict[str, Any]) -> None:
    assert manifest(sandbox_run)["rejected_strategy_state_changed"] is False
    assert sandbox_run["strategies_before"] == sandbox_run["strategies_after"]


def test_exact_rejected_variants_not_reopened(sandbox_run: dict[str, Any]) -> None:
    assert manifest(sandbox_run)["exact_rejected_variants_reopened"] is False


def test_intraday_remains_paused(sandbox_run: dict[str, Any]) -> None:
    assert manifest(sandbox_run)["intraday_research_remains_paused"] is True


def test_sandbox_results_are_non_promotable(sandbox_run: dict[str, Any]) -> None:
    assert manifest(sandbox_run)["sandbox_results_non_promotable"] is True


def test_sandbox_cannot_create_paper_candidates(sandbox_run: dict[str, Any]) -> None:
    assert manifest(sandbox_run)["sandbox_can_create_paper_candidates"] is False


def test_variant_limit_present_and_bounded(sandbox_run: dict[str, Any]) -> None:
    assert 0 < manifest(sandbox_run)["max_total_future_variants"] <= 200


def test_allowed_families_file_exists(sandbox_run: dict[str, Any]) -> None:
    text = (output(sandbox_run) / "sandbox_allowed_families.md").read_text(encoding="utf-8")
    assert "trend_momentum" in text
    assert "portfolio_combination_sleeve_ensemble" in text


def test_allowed_universes_file_exists(sandbox_run: dict[str, Any]) -> None:
    text = (output(sandbox_run) / "sandbox_allowed_universes.md").read_text(encoding="utf-8")
    assert "core_equity_etfs" in text
    assert "managed_futures_wrappers" in text


def test_allowed_indicators_file_exists(sandbox_run: dict[str, Any]) -> None:
    text = (output(sandbox_run) / "sandbox_allowed_indicators.md").read_text(encoding="utf-8")
    assert "`SMA`" in text
    assert "external indicator-library outputs" in text


def test_scoring_framework_exists(sandbox_run: dict[str, Any]) -> None:
    assert (output(sandbox_run) / "sandbox_scoring_framework.md").exists()


def test_anti_overfitting_controls_exist(sandbox_run: dict[str, Any]) -> None:
    text = (output(sandbox_run) / "sandbox_anti_overfitting_controls.md").read_text(encoding="utf-8")
    assert "Best single variant cannot be promoted" in text


def test_status_taxonomy_exists(sandbox_run: dict[str, Any]) -> None:
    text = (output(sandbox_run) / "sandbox_status_taxonomy.md").read_text(encoding="utf-8")
    assert "sandbox_future_preregistration_candidate" in text
    assert "promotion_review_candidate" in text


def test_future_graduation_rules_exist(sandbox_run: dict[str, Any]) -> None:
    assert (output(sandbox_run) / "sandbox_future_graduation_rules.md").exists()


def test_research_only_leverage_policy_exists(sandbox_run: dict[str, Any]) -> None:
    text = (output(sandbox_run) / "sandbox_research_only_leverage_policy.md").read_text(encoding="utf-8")
    assert "research_only_leverage_sensitivity_non_promotable" in text


def test_do_not_run_now_file_exists(sandbox_run: dict[str, Any]) -> None:
    text = (output(sandbox_run) / "sandbox_do_not_run_now.md").read_text(encoding="utf-8")
    assert "sandbox exploration" in text
    assert "real-money recommendations" in text


def test_next_action_is_valid(sandbox_run: dict[str, Any]) -> None:
    assert manifest(sandbox_run)["next_action"] in sandbox.VALID_NEXT_ACTIONS
    assert manifest(sandbox_run)["next_action"] == "implement_exploratory_strategy_search_sandbox"


def test_manifest_flags_match_strict_scope(sandbox_run: dict[str, Any]) -> None:
    loaded = manifest(sandbox_run)
    for key, expected in sandbox.MANIFEST_FLAGS.items():
        assert loaded[key] == expected
    assert consistency(sandbox_run)["consistency_passed"] is True
