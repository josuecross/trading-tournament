from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

import run_indicator_library_dependency_review as review


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_fixture(root: Path) -> None:
    registry = {
        "registry": {
            "schema_version": 1,
            "project": "trading_tournament",
            "research_only": True,
            "real_money_recommendation": False,
            "broker_integration": False,
            "live_orders": False,
            "current_next_action": "pre_register_indicator_library_dependency_review",
            "official_current_next_action": "pre_register_indicator_library_dependency_review",
            "intraday_research_remains_paused": True,
            "expansion_paused": True,
        },
        "risk_framework": {
            "active_framework": "balanced_speculative_research_v1",
            "framework_path": "risk_framework/risk_framework.yaml",
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
                "id": "rc_donchian_breakout_risk_budget_v1",
                "status": "discovery_reject",
                "paper_forward_active": False,
                "candidate_exhaustive_run": False,
            },
        ],
    }
    registry_path = root / review.REGISTRY_PATH
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")

    roadmap_path = root / review.ROADMAP_PATH
    roadmap_path.parent.mkdir(parents=True, exist_ok=True)
    roadmap_path.write_text(
        """# Research Roadmap

## Compact Current State

- Official current next action: `pre_register_indicator_library_dependency_review`

## Priority Backlog

- Historical section.
""",
        encoding="utf-8",
    )

    requirements_path = root / review.REQUIREMENTS_PATH
    requirements_path.write_text("pandas\nnumpy\npyyaml\npytest\n", encoding="utf-8")
    write_json(
        root / review.VALIDATION_IMPL_DIR / "indicator_validation_implementation_manifest.json",
        {
            "fixture_types_implemented_count": 7,
            "indicator_tests_added_count": 19,
            "lookahead_tests_added_count": 6,
            "indicator_bugs_found_count": 0,
            "material_strategy_result_risk_flag": False,
            "next_action": "pre_register_indicator_library_dependency_review",
        },
    )


@pytest.fixture(scope="module")
def dependency_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    root = tmp_path_factory.mktemp("indicator_dependency_review")
    write_fixture(root)
    before_strategies = yaml.safe_load((root / review.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    before_requirements = (root / review.REQUIREMENTS_PATH).read_text(encoding="utf-8")
    result = review.run_indicator_library_dependency_review(root)
    after_strategies = yaml.safe_load((root / review.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    after_requirements = (root / review.REQUIREMENTS_PATH).read_text(encoding="utf-8")
    result["root"] = root
    result["strategies_before"] = before_strategies
    result["strategies_after"] = after_strategies
    result["requirements_before"] = before_requirements
    result["requirements_after"] = after_requirements
    return result


def output(dependency_run: dict[str, Any]) -> Path:
    return Path(dependency_run["output_dir"])


def manifest(dependency_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(dependency_run) / "indicator_dependency_review_manifest.json").read_text(encoding="utf-8"))


def consistency(dependency_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads(
        (output(dependency_run) / "indicator_dependency_review_consistency_check.json").read_text(encoding="utf-8")
    )


def test_dependency_review_only_mode(dependency_run: dict[str, Any]) -> None:
    assert manifest(dependency_run)["dependency_review_only"] is True


def test_no_dependency_installed(dependency_run: dict[str, Any]) -> None:
    assert manifest(dependency_run)["dependency_installed"] is False


def test_dependency_files_unchanged(dependency_run: dict[str, Any]) -> None:
    assert manifest(dependency_run)["dependency_files_changed"] is False
    assert dependency_run["requirements_before"] == dependency_run["requirements_after"]


def test_no_strategy_discovery(dependency_run: dict[str, Any]) -> None:
    assert manifest(dependency_run)["strategy_discovery_run"] is False


def test_no_backtests(dependency_run: dict[str, Any]) -> None:
    assert manifest(dependency_run)["backtests_run"] is False


def test_no_new_performance_metrics(dependency_run: dict[str, Any]) -> None:
    assert manifest(dependency_run)["new_performance_metrics_computed"] is False


def test_no_provider_download(dependency_run: dict[str, Any]) -> None:
    assert manifest(dependency_run)["provider_download"] is False


def test_no_intraday_data_used(dependency_run: dict[str, Any]) -> None:
    assert manifest(dependency_run)["intraday_data_used"] is False


def test_no_candidate_exhaustive(dependency_run: dict[str, Any]) -> None:
    assert manifest(dependency_run)["candidate_exhaustive_run"] is False


def test_no_paper_forward_action(dependency_run: dict[str, Any]) -> None:
    loaded = manifest(dependency_run)
    assert loaded["paper_forward_review"] is False
    assert loaded["paper_forward_activation"] is False


def test_no_broker_orders_submitted(dependency_run: dict[str, Any]) -> None:
    assert manifest(dependency_run)["broker_orders_submitted"] is False


def test_no_broker_orders_cancelled(dependency_run: dict[str, Any]) -> None:
    assert manifest(dependency_run)["broker_orders_cancelled"] is False


def test_no_live_orders(dependency_run: dict[str, Any]) -> None:
    assert manifest(dependency_run)["live_orders"] is False


def test_no_real_money_recommendation(dependency_run: dict[str, Any]) -> None:
    assert manifest(dependency_run)["real_money_recommendation"] is False


def test_active_strategy_state_preserved(dependency_run: dict[str, Any]) -> None:
    assert manifest(dependency_run)["active_strategy_state_changed"] is False
    assert dependency_run["strategies_before"] == dependency_run["strategies_after"]


def test_rejected_strategy_state_preserved(dependency_run: dict[str, Any]) -> None:
    assert manifest(dependency_run)["rejected_strategy_state_changed"] is False
    assert dependency_run["strategies_before"] == dependency_run["strategies_after"]


def test_exact_rejected_variants_not_reopened(dependency_run: dict[str, Any]) -> None:
    assert manifest(dependency_run)["exact_rejected_variants_reopened"] is False


def test_expansion_remains_paused(dependency_run: dict[str, Any]) -> None:
    assert manifest(dependency_run)["expansion_remains_paused"] is True


def test_intraday_remains_paused(dependency_run: dict[str, Any]) -> None:
    assert manifest(dependency_run)["intraday_research_remains_paused"] is True


def test_candidate_library_matrix_exists(dependency_run: dict[str, Any]) -> None:
    text = (output(dependency_run) / "candidate_library_dependency_matrix.md").read_text(encoding="utf-8")
    assert "current_custom_indicators_only" in text
    assert "`ta`" in text
    assert "pandas-ta-classic" in text
    assert "TA-Lib" in text
    assert "vectorbt_indicator_layer_only" in text


def test_dependency_risk_assessment_exists(dependency_run: dict[str, Any]) -> None:
    text = (output(dependency_run) / "dependency_risk_assessment.md").read_text(encoding="utf-8")
    assert "Indicator bugs found: `0`" in text
    assert "indicator-mining" in text


def test_dependency_decision_is_valid(dependency_run: dict[str, Any]) -> None:
    loaded = manifest(dependency_run)
    assert loaded["dependency_decision"] in review.VALID_DEPENDENCY_DECISIONS
    assert loaded["dependency_decision"] == "stay_custom_indicators_only"
    assert loaded["selected_dependency_candidate"] == "current_custom_indicators_only"


def test_do_not_install_now_file_exists(dependency_run: dict[str, Any]) -> None:
    text = (output(dependency_run) / "indicator_dependency_do_not_install_now.md").read_text(encoding="utf-8")
    assert "installing `ta`" in text
    assert "changing dependency files" in text
    assert "real-money recommendations" in text


def test_next_action_is_valid(dependency_run: dict[str, Any]) -> None:
    loaded = manifest(dependency_run)
    assert loaded["next_action"] in review.VALID_NEXT_ACTIONS
    assert loaded["next_action"] == "pre_register_next_family_after_indicator_validation"


def test_manifest_flags_match_strict_scope(dependency_run: dict[str, Any]) -> None:
    loaded = manifest(dependency_run)
    for key, expected in review.MANIFEST_FLAGS.items():
        assert loaded[key] == expected
    assert loaded["proposed_dependency_patch_created"] is False
    assert consistency(dependency_run)["consistency_passed"] is True
