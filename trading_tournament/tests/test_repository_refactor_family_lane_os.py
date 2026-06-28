from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

import run_repository_refactor_family_lane_os as repo_refactor


def write_fixture(root: Path) -> None:
    registry = {
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
        "strategies": [
            {
                "id": "paper_forward_vm_quality_lowvol_proxy_v1",
                "status": "active_observation",
                "paper_forward_active": True,
                "candidate_exhaustive_run": False,
            },
            {
                "id": "paper_forward_dsr_sector_equal_weight_defensive_filter_v1",
                "status": "active_observation",
                "paper_forward_active": True,
                "candidate_exhaustive_run": False,
            },
            {
                "id": "rc_dual_momentum_paa_vol_scaled_v1",
                "status": "discovery_reject",
                "paper_forward_active": False,
                "candidate_exhaustive_run": False,
            },
        ],
    }
    registry_path = root / repo_refactor.REGISTRY_PATH
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")
    roadmap_path = root / repo_refactor.ROADMAP_PATH
    roadmap_path.parent.mkdir(parents=True, exist_ok=True)
    roadmap_path.write_text("# Research Roadmap\n\nCurrent next action: `audit_family_failures`\n", encoding="utf-8")
    (root / ".gitignore").write_text("__pycache__/\n.pytest_cache/\n", encoding="utf-8")
    cache_dir = root / "module" / "__pycache__"
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "junk.pyc").write_bytes(b"junk")


@pytest.fixture(scope="module")
def refactor_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    root = tmp_path_factory.mktemp("repo_refactor_family_lane_os")
    write_fixture(root)
    before = yaml.safe_load((root / repo_refactor.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result = repo_refactor.run_repository_refactor_family_lane_os(root)
    after = yaml.safe_load((root / repo_refactor.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result["root"] = root
    result["strategies_before"] = before
    result["strategies_after"] = after
    return result


def root(refactor_run: dict[str, Any]) -> Path:
    return Path(refactor_run["root"])


def output(refactor_run: dict[str, Any]) -> Path:
    return Path(refactor_run["output_dir"])


def manifest(refactor_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(refactor_run) / "repo_refactor_manifest.json").read_text(encoding="utf-8"))


def consistency(refactor_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(refactor_run) / "repo_refactor_consistency_check.json").read_text(encoding="utf-8"))


def test_refactor_only_mode(refactor_run: dict[str, Any]) -> None:
    assert manifest(refactor_run)["repository_refactor_only"] is True


def test_no_strategy_discovery(refactor_run: dict[str, Any]) -> None:
    assert manifest(refactor_run)["strategy_discovery_run"] is False


def test_no_backtests(refactor_run: dict[str, Any]) -> None:
    assert manifest(refactor_run)["backtests_run"] is False


def test_no_new_performance_metrics(refactor_run: dict[str, Any]) -> None:
    assert manifest(refactor_run)["new_performance_metrics_computed"] is False


def test_no_provider_download(refactor_run: dict[str, Any]) -> None:
    assert manifest(refactor_run)["provider_download"] is False


def test_no_intraday_data_used(refactor_run: dict[str, Any]) -> None:
    assert manifest(refactor_run)["intraday_data_used"] is False


def test_no_candidate_exhaustive(refactor_run: dict[str, Any]) -> None:
    assert manifest(refactor_run)["candidate_exhaustive_run"] is False


def test_no_paper_forward_action(refactor_run: dict[str, Any]) -> None:
    loaded = manifest(refactor_run)
    assert loaded["paper_forward_review"] is False
    assert loaded["paper_forward_activation"] is False


def test_no_broker_orders_submitted(refactor_run: dict[str, Any]) -> None:
    assert manifest(refactor_run)["broker_orders_submitted"] is False


def test_no_broker_orders_cancelled(refactor_run: dict[str, Any]) -> None:
    assert manifest(refactor_run)["broker_orders_cancelled"] is False


def test_no_live_orders(refactor_run: dict[str, Any]) -> None:
    assert manifest(refactor_run)["live_orders"] is False


def test_no_real_money_recommendation(refactor_run: dict[str, Any]) -> None:
    assert manifest(refactor_run)["real_money_recommendation"] is False


def test_active_strategy_state_not_changed(refactor_run: dict[str, Any]) -> None:
    assert manifest(refactor_run)["active_strategy_state_changed"] is False
    assert refactor_run["strategies_before"] == refactor_run["strategies_after"]


def test_rejected_strategy_state_not_changed(refactor_run: dict[str, Any]) -> None:
    assert manifest(refactor_run)["rejected_strategy_state_changed"] is False
    assert refactor_run["strategies_before"] == refactor_run["strategies_after"]


def test_exact_rejected_variants_not_reopened(refactor_run: dict[str, Any]) -> None:
    assert manifest(refactor_run)["exact_rejected_variants_reopened"] is False


def test_intraday_remains_paused(refactor_run: dict[str, Any]) -> None:
    assert manifest(refactor_run)["intraday_research_remains_paused"] is True


def test_compact_state_file_exists(refactor_run: dict[str, Any]) -> None:
    assert (root(refactor_run) / "reports" / "compact_state" / "current_tournament_state.md").exists()


def test_family_status_directory_exists(refactor_run: dict[str, Any]) -> None:
    status_dir = root(refactor_run) / "family_registry" / "family_status"
    assert status_dir.exists()
    assert (status_dir / "dual_momentum.md").exists()


def test_lane_policy_exists(refactor_run: dict[str, Any]) -> None:
    assert (root(refactor_run) / "lanes" / "lane_scorecard_policy.md").exists()


def test_indicator_governance_policy_exists(refactor_run: dict[str, Any]) -> None:
    assert (root(refactor_run) / "indicator_layer" / "indicator_policy.md").exists()
    assert (root(refactor_run) / "indicator_layer" / "approved_indicators.yaml").exists()


def test_artifact_policy_exists(refactor_run: dict[str, Any]) -> None:
    assert (root(refactor_run) / "governance" / "artifact_policy.md").exists()
    assert (root(refactor_run) / "governance" / "cleanup_policy.md").exists()


def test_cleanup_inventory_exists(refactor_run: dict[str, Any]) -> None:
    assert (output(refactor_run) / "repo_cleanup_inventory.csv").exists()


def test_gitignore_update_report_exists(refactor_run: dict[str, Any]) -> None:
    assert (output(refactor_run) / "gitignore_update_report.md").exists()
    assert "trading-tournament generated artifact policy" in (root(refactor_run) / ".gitignore").read_text(encoding="utf-8")


def test_refactor_next_action_is_valid(refactor_run: dict[str, Any]) -> None:
    assert manifest(refactor_run)["next_action"] in repo_refactor.VALID_NEXT_ACTIONS
    assert consistency(refactor_run)["next_action_valid"] is True


def test_manifest_flags_match_strict_scope(refactor_run: dict[str, Any]) -> None:
    loaded = manifest(refactor_run)
    for key, expected in repo_refactor.MANIFEST_FLAGS.items():
        assert loaded[key] == expected
    assert consistency(refactor_run)["consistency_passed"] is True
