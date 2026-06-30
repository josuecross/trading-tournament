from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from strategy_lab.research_os.exploratory_sandbox import sandbox_config as config
from strategy_lab.research_os.exploratory_sandbox.sandbox_evidence import run_sandbox_implementation
from strategy_lab.research_os.exploratory_sandbox.sandbox_families import ALLOWED_FAMILIES
from strategy_lab.research_os.exploratory_sandbox.sandbox_indicators import ALLOWED_INDICATORS, validate_indicator_concept
from strategy_lab.research_os.exploratory_sandbox.sandbox_schema import VariantSpec, validate_variant_spec
from strategy_lab.research_os.exploratory_sandbox.sandbox_status_taxonomy import assert_status_allowed
from strategy_lab.research_os.exploratory_sandbox.sandbox_universes import UNIVERSE_GROUPS
from strategy_lab.research_os.exploratory_sandbox.sandbox_variant_generator import generate_variant_plan


def write_cache(path: Path, symbol: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "date,open,high,low,close,adj_close,volume,symbol\n"
        f"2020-01-02,100,101,99,100,100,1000,{symbol}\n"
        f"2020-01-03,101,102,100,101,101,1000,{symbol}\n"
        f"2020-01-06,102,103,101,102,102,1000,{symbol}\n"
        f"2020-01-07,103,104,102,103,103,1000,{symbol}\n",
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
            "current_research_mode": "exploratory_strategy_search_sandbox_preregistered",
            "current_next_action": "implement_exploratory_strategy_search_sandbox",
            "official_current_next_action": "implement_exploratory_strategy_search_sandbox",
            "intraday_research_remains_paused": True,
        },
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
    registry_path = root / config.REGISTRY_PATH
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")

    roadmap_path = root / config.ROADMAP_PATH
    roadmap_path.parent.mkdir(parents=True, exist_ok=True)
    roadmap_path.write_text(
        "# Research Roadmap\n\n## Compact Current State\n\n- Official current next action: `implement_exploratory_strategy_search_sandbox`\n",
        encoding="utf-8",
    )

    all_symbols = sorted({symbol for group in UNIVERSE_GROUPS.values() for symbol in group.symbols})
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
    approved_path = root / config.APPROVED_SYMBOL_MAP_PATH
    approved_path.parent.mkdir(parents=True, exist_ok=True)
    approved_path.write_text(yaml.safe_dump(approved, sort_keys=False), encoding="utf-8")
    for symbol in all_symbols:
        write_cache(root / config.DATA_CACHE_DIR / f"{symbol}.csv", symbol)


@pytest.fixture(scope="module")
def sandbox_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    root = tmp_path_factory.mktemp("exploratory_sandbox_implementation")
    write_fixture(root)
    before = yaml.safe_load((root / config.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result = run_sandbox_implementation(root, max_variants=200, update_metadata=True)
    after = yaml.safe_load((root / config.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result["root"] = root
    result["strategies_before"] = before
    result["strategies_after"] = after
    return result


def output(sandbox_run: dict[str, Any]) -> Path:
    return Path(sandbox_run["output_dir"])


def manifest(sandbox_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(sandbox_run) / "exploratory_sandbox_implementation_manifest.json").read_text(encoding="utf-8"))


def consistency(sandbox_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads(
        (output(sandbox_run) / "exploratory_sandbox_implementation_consistency_check.json").read_text(encoding="utf-8")
    )


def variant_rows(sandbox_run: dict[str, Any]) -> list[dict[str, str]]:
    with (output(sandbox_run) / "sandbox_variant_plan_dry_run.csv").open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_sandbox_implementation_only_mode(sandbox_run: dict[str, Any]) -> None:
    assert manifest(sandbox_run)["sandbox_implementation_only"] is True


def test_sandbox_search_not_run(sandbox_run: dict[str, Any]) -> None:
    assert manifest(sandbox_run)["sandbox_search_run"] is False


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
    bad = VariantSpec(
        variant_id="mfv_equal_weight_trend_filter_v1",
        family_id="trend_momentum",
        universe_group="core_equity",
        symbols=("SPY", "QQQ"),
        indicator_concept="sma",
        parameter_set={"lookback": 50},
        holding_period_type="daily_close_to_daily_close",
        rebalance_frequency="predefined_weekly_or_monthly",
    )
    with pytest.raises(ValueError):
        validate_variant_spec(bad)


def test_intraday_remains_paused(sandbox_run: dict[str, Any]) -> None:
    assert manifest(sandbox_run)["intraday_research_remains_paused"] is True


def test_sandbox_results_are_non_promotable(sandbox_run: dict[str, Any]) -> None:
    assert manifest(sandbox_run)["sandbox_results_non_promotable"] is True


def test_sandbox_cannot_create_paper_candidates(sandbox_run: dict[str, Any]) -> None:
    assert manifest(sandbox_run)["sandbox_can_create_paper_candidates"] is False


def test_variant_plan_exists(sandbox_run: dict[str, Any]) -> None:
    assert (output(sandbox_run) / "sandbox_variant_plan_dry_run.csv").exists()
    assert manifest(sandbox_run)["variant_plan_generated"] is True


def test_variant_plan_rows_bounded(sandbox_run: dict[str, Any]) -> None:
    rows = variant_rows(sandbox_run)
    assert 0 < len(rows) <= 200
    assert manifest(sandbox_run)["variant_plan_rows"] == len(rows)
    with pytest.raises(ValueError):
        generate_variant_plan(sandbox_run["root"], max_variants=201)


def test_every_variant_promotable_false(sandbox_run: dict[str, Any]) -> None:
    assert {row["promotable"] for row in variant_rows(sandbox_run)} == {"false"}


def test_every_variant_paper_candidate_allowed_false(sandbox_run: dict[str, Any]) -> None:
    assert {row["paper_candidate_allowed"] for row in variant_rows(sandbox_run)} == {"false"}


def test_forbidden_statuses_are_blocked(sandbox_run: dict[str, Any]) -> None:
    assert manifest(sandbox_run)["forbidden_statuses_blocked"] is True
    with pytest.raises(ValueError):
        assert_status_allowed("paper_forward")


def test_forbidden_indicators_are_blocked() -> None:
    with pytest.raises(ValueError):
        validate_indicator_concept("MACD")


def test_allowed_family_count_is_7(sandbox_run: dict[str, Any]) -> None:
    assert len(ALLOWED_FAMILIES) == 7
    assert manifest(sandbox_run)["allowed_family_count"] == 7


def test_allowed_universe_count_is_7(sandbox_run: dict[str, Any]) -> None:
    assert len(UNIVERSE_GROUPS) == 7
    assert manifest(sandbox_run)["allowed_universe_count"] == 7


def test_allowed_indicator_count_is_12(sandbox_run: dict[str, Any]) -> None:
    assert len(ALLOWED_INDICATORS) == 12
    assert manifest(sandbox_run)["allowed_indicator_count"] == 12


def test_scoring_framework_exists(sandbox_run: dict[str, Any]) -> None:
    text = (output(sandbox_run) / "sandbox_scoring_framework_report.md").read_text(encoding="utf-8")
    assert "family_robustness_score" in text
    assert "does not calculate strategy performance metrics" in text


def test_anti_overfitting_controls_exist(sandbox_run: dict[str, Any]) -> None:
    text = (output(sandbox_run) / "sandbox_anti_overfitting_report.md").read_text(encoding="utf-8")
    assert "Best single variant cannot be promoted" in text


def test_research_only_leverage_policy_exists(sandbox_run: dict[str, Any]) -> None:
    text = (output(sandbox_run) / "sandbox_research_only_leverage_report.md").read_text(encoding="utf-8")
    assert "1.25x" in text
    assert "No broker, margin, live, or real-money use" in text


def test_data_preflight_report_exists(sandbox_run: dict[str, Any]) -> None:
    text = (output(sandbox_run) / "sandbox_data_preflight_report.md").read_text(encoding="utf-8")
    assert "Local cache metadata only" in text
    assert "core_equity" in text


def test_next_action_is_valid(sandbox_run: dict[str, Any]) -> None:
    assert manifest(sandbox_run)["next_action"] in config.VALID_NEXT_ACTIONS
    assert (output(sandbox_run) / "sandbox_implementation_next_action.md").exists()


def test_manifest_flags_match_strict_scope(sandbox_run: dict[str, Any]) -> None:
    loaded = manifest(sandbox_run)
    for key, expected in config.MANIFEST_FLAGS.items():
        assert loaded[key] == expected
    assert consistency(sandbox_run)["consistency_passed"] is True
