from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

import run_research_operating_system_refactor as ros


def write_registry(root: Path) -> None:
    rows = [
        {
            "id": ros.VM_ID,
            "status": "active_observation",
            "current_status": "active_observation",
            "paper_forward_active": True,
            "candidate_exhaustive_run": False,
            "real_money_recommendation": False,
        },
        {
            "id": ros.DSR_ID,
            "status": "active_observation",
            "current_status": "active_observation",
            "paper_forward_active": True,
            "candidate_exhaustive_run": False,
            "real_money_recommendation": False,
        },
        {
            "id": "rc_dual_momentum_paa_vol_scaled_v1",
            "status": "discovery_reject",
            "current_status": "discovery_reject",
            "paper_forward_active": False,
            "candidate_exhaustive_run": False,
            "real_money_recommendation": False,
        },
        {
            "id": "rc_donchian_breakout_risk_budget_v1",
            "status": "discovery_reject",
            "current_status": "discovery_reject",
            "paper_forward_active": False,
            "candidate_exhaustive_run": False,
            "real_money_recommendation": False,
        },
    ]
    path = root / ros.REGISTRY_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            {
                "registry": {
                    "schema_version": 1,
                    "project": "trading_tournament",
                    "research_only": True,
                    "real_money_recommendation": False,
                    "broker_integration": False,
                    "live_orders": False,
                },
                "risk_framework": {
                    "active_framework": "balanced_speculative_research_v1",
                    "framework_path": "risk_framework/risk_framework.yaml",
                },
                "strategies": rows,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def write_active_observations(root: Path) -> None:
    for strategy_id, rel_path in ros.ACTIVE_OBSERVATION_PATHS.items():
        path = root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump({"strategy_id": strategy_id, "frozen": True}, sort_keys=False), encoding="utf-8")


def write_roadmap(root: Path) -> None:
    path = root / ros.ROADMAP_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# Research Roadmap\n\nCurrent next action: `audit_family_failures`\n", encoding="utf-8")


@pytest.fixture(scope="module")
def refactor_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    root = tmp_path_factory.mktemp("research_os_refactor")
    write_registry(root)
    write_active_observations(root)
    write_roadmap(root)
    before = yaml.safe_load((root / ros.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result = ros.run_research_operating_system_refactor(root)
    after = yaml.safe_load((root / ros.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result["root"] = root
    result["strategies_before"] = before
    result["strategies_after"] = after
    return result


def output(refactor_run: dict[str, Any]) -> Path:
    return Path(refactor_run["output_dir"])


def research_os_dir(refactor_run: dict[str, Any]) -> Path:
    return Path(refactor_run["research_os_dir"])


def manifest(refactor_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(refactor_run) / "research_os_refactor_manifest.json").read_text(encoding="utf-8"))


def consistency(refactor_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(refactor_run) / "research_os_refactor_consistency_check.json").read_text(encoding="utf-8"))


def family_registry(refactor_run: dict[str, Any]) -> dict[str, Any]:
    return yaml.safe_load((research_os_dir(refactor_run) / "family_registry.yaml").read_text(encoding="utf-8"))


def family_by_id(refactor_run: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["family_id"]: row for row in family_registry(refactor_run)["families"]}


def test_research_os_refactor_only(refactor_run: dict[str, Any]) -> None:
    assert manifest(refactor_run)["research_os_refactor_only"] is True


def test_no_backtests(refactor_run: dict[str, Any]) -> None:
    assert manifest(refactor_run)["backtests_run"] is False


def test_no_discovery(refactor_run: dict[str, Any]) -> None:
    assert manifest(refactor_run)["discovery_run"] is False


def test_no_new_performance_metrics(refactor_run: dict[str, Any]) -> None:
    assert manifest(refactor_run)["new_performance_metrics_computed"] is False


def test_no_provider_download(refactor_run: dict[str, Any]) -> None:
    assert manifest(refactor_run)["provider_download"] is False


def test_no_intraday_data_used(refactor_run: dict[str, Any]) -> None:
    assert manifest(refactor_run)["intraday_data_used"] is False


def test_intraday_remains_paused(refactor_run: dict[str, Any]) -> None:
    assert manifest(refactor_run)["intraday_research_remains_paused"] is True
    assert consistency(refactor_run)["intraday_families_data_source_blocked"] is True


def test_no_candidate_exhaustive(refactor_run: dict[str, Any]) -> None:
    assert manifest(refactor_run)["candidate_exhaustive_run"] is False


def test_no_paper_forward_action(refactor_run: dict[str, Any]) -> None:
    loaded = manifest(refactor_run)
    assert loaded["paper_forward_review"] is False
    assert loaded["paper_forward_activation"] is False


def test_no_broker_live_path(refactor_run: dict[str, Any]) -> None:
    loaded = manifest(refactor_run)
    assert loaded["broker_path_touched"] is False
    assert loaded["live_orders"] is False
    assert consistency(refactor_run)["no_broker_live_path"] is True


def test_no_real_money_recommendation(refactor_run: dict[str, Any]) -> None:
    assert manifest(refactor_run)["real_money_recommendation"] is False


def test_no_accepted_strategy_state_changed(refactor_run: dict[str, Any]) -> None:
    assert manifest(refactor_run)["accepted_strategy_state_changed"] is False
    assert refactor_run["strategies_before"] == refactor_run["strategies_after"]


def test_no_rejected_strategy_state_changed(refactor_run: dict[str, Any]) -> None:
    assert manifest(refactor_run)["rejected_strategy_state_changed"] is False
    assert refactor_run["strategies_before"] == refactor_run["strategies_after"]


def test_no_exact_rejected_variants_reopened(refactor_run: dict[str, Any]) -> None:
    assert manifest(refactor_run)["exact_rejected_variants_reopened"] is False
    assert family_by_id(refactor_run)["donchian_breakout"]["family_open_status"].startswith("closed_exact")


def test_no_new_strategy_candidates_created(refactor_run: dict[str, Any]) -> None:
    assert manifest(refactor_run)["new_strategy_candidates_created"] is False


def test_no_indicator_library_installed(refactor_run: dict[str, Any]) -> None:
    assert manifest(refactor_run)["indicator_library_installed"] is False
    governance = yaml.safe_load((research_os_dir(refactor_run) / "indicator_governance.yaml").read_text(encoding="utf-8"))
    assert governance["library_install_allowed_in_this_step"] is False


def test_family_registry_exists(refactor_run: dict[str, Any]) -> None:
    assert (research_os_dir(refactor_run) / "family_registry.yaml").exists()


def test_lane_model_exists(refactor_run: dict[str, Any]) -> None:
    assert (research_os_dir(refactor_run) / "lane_model.yaml").exists()


def test_candidate_role_model_exists(refactor_run: dict[str, Any]) -> None:
    assert (research_os_dir(refactor_run) / "candidate_role_model.yaml").exists()


def test_research_value_scorecard_exists(refactor_run: dict[str, Any]) -> None:
    assert (research_os_dir(refactor_run) / "research_value_scorecard.yaml").exists()


def test_promotion_eligibility_gates_exists(refactor_run: dict[str, Any]) -> None:
    assert (research_os_dir(refactor_run) / "promotion_eligibility_gates.yaml").exists()


def test_paper_demo_eligibility_gates_exists(refactor_run: dict[str, Any]) -> None:
    assert (research_os_dir(refactor_run) / "paper_demo_eligibility_gates.yaml").exists()


def test_failure_taxonomy_exists(refactor_run: dict[str, Any]) -> None:
    assert (research_os_dir(refactor_run) / "failure_taxonomy.yaml").exists()


def test_parent_child_lineage_rules_exists(refactor_run: dict[str, Any]) -> None:
    assert (research_os_dir(refactor_run) / "parent_child_lineage_rules.yaml").exists()


def test_signal_funnel_contract_exists(refactor_run: dict[str, Any]) -> None:
    assert (research_os_dir(refactor_run) / "signal_funnel_contract.yaml").exists()


def test_data_source_gate_model_exists(refactor_run: dict[str, Any]) -> None:
    assert (research_os_dir(refactor_run) / "data_source_gate_model.yaml").exists()


def test_indicator_governance_exists(refactor_run: dict[str, Any]) -> None:
    assert (research_os_dir(refactor_run) / "indicator_governance.yaml").exists()


def test_benchmark_control_registry_exists(refactor_run: dict[str, Any]) -> None:
    assert (research_os_dir(refactor_run) / "benchmark_control_registry.yaml").exists()


def test_next_action_policy_exists(refactor_run: dict[str, Any]) -> None:
    assert (research_os_dir(refactor_run) / "next_action_policy.yaml").exists()


def test_static_all_weather_remains_benchmark_control_only(refactor_run: dict[str, Any]) -> None:
    static_family = family_by_id(refactor_run)["static_all_weather_benchmark"]
    controls = yaml.safe_load((research_os_dir(refactor_run) / "benchmark_control_registry.yaml").read_text(encoding="utf-8"))["controls"]
    static_control = controls[ros.STATIC_ALL_WEATHER_ID]
    assert static_family["status"] == "benchmark_control_accepted"
    assert static_family["role"] == "benchmark_control"
    assert static_control["promotion_eligible"] is False
    assert static_control["candidate_exhaustive_eligible"] is False
    assert static_control["paper_demo_live_eligible"] is False


def test_intraday_families_remain_data_source_blocked(refactor_run: dict[str, Any]) -> None:
    intraday = [row for row in family_registry(refactor_run)["families"] if row["family_id"].startswith("intraday_")]
    assert intraday
    assert all(row["data_status"] == "blocked_due_to_intraday_source" for row in intraday)


def test_risk_controlled_rejected_active_states_are_not_mutated(refactor_run: dict[str, Any]) -> None:
    assert consistency(refactor_run)["risk_controlled_rejected_active_states_not_mutated"] is True
    assert refactor_run["strategies_before"] == refactor_run["strategies_after"]


def test_next_action_is_valid(refactor_run: dict[str, Any]) -> None:
    assert manifest(refactor_run)["next_action"] in ros.VALID_NEXT_ACTIONS
    assert consistency(refactor_run)["next_action_valid"] is True


def test_manifest_flags_match_strict_scope(refactor_run: dict[str, Any]) -> None:
    loaded = manifest(refactor_run)
    for key, expected in ros.MANIFEST_FLAGS.items():
        assert loaded[key] is expected
    assert consistency(refactor_run)["consistency_passed"] is True
