from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

import run_post_next_family_discovery_state_sync as sync


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
            "current_next_action": sync.NEXT_ACTION,
            "official_current_next_action": sync.NEXT_ACTION,
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
                "id": "managed_futures_etf_trend_wrapper_v1",
                "status": "discovery_reject",
                "paper_forward_active": False,
                "candidate_exhaustive_run": False,
            },
        ],
    }
    registry_path = root / sync.REGISTRY_PATH
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")

    roadmap_path = root / sync.ROADMAP_PATH
    roadmap_path.parent.mkdir(parents=True, exist_ok=True)
    roadmap_path.write_text(
        f"""# Research Roadmap

## Compact Current State

- Official current next action: `{sync.NEXT_ACTION}`
""",
        encoding="utf-8",
    )

    compact_path = root / sync.COMPACT_STATE_PATH
    compact_path.parent.mkdir(parents=True, exist_ok=True)
    compact_path.write_text(
        "Current next action before discovery: `run_next_family_discovery_after_indicator_validation`\n",
        encoding="utf-8",
    )

    write_json(
        root / sync.DISCOVERY_DIR / "next_family_discovery_manifest.json",
        {
            "candidate_id": sync.CANDIDATE_ID,
            "selected_family": sync.SELECTED_FAMILY,
            "candidate_outcome": sync.CANDIDATE_OUTCOME,
            "promotion_candidates_count": sync.PROMOTION_CANDIDATES_COUNT,
            "limited_history_label": sync.LIMITED_HISTORY_LABEL,
            "decision_label": sync.DECISION_LABEL,
            "next_action": sync.NEXT_ACTION,
            "candidate_exhaustive_run": False,
            "paper_forward_review": False,
            "paper_forward_activation": False,
            "provider_download": False,
            "intraday_data_used": False,
            "indicator_library_dependency_added": False,
            "real_money_recommendation": False,
            "intraday_research_remains_paused": True,
        },
    )


@pytest.fixture(scope="module")
def sync_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    root = tmp_path_factory.mktemp("post_next_family_discovery_state_sync")
    write_fixture(root)
    before = yaml.safe_load((root / sync.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result = sync.run_post_next_family_discovery_state_sync(root)
    after = yaml.safe_load((root / sync.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result["root"] = root
    result["strategies_before"] = before
    result["strategies_after"] = after
    return result


def output(sync_run: dict[str, Any]) -> Path:
    return Path(sync_run["output_dir"])


def manifest(sync_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(sync_run) / "post_discovery_state_sync_manifest.json").read_text(encoding="utf-8"))


def consistency(sync_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads(
        (output(sync_run) / "post_discovery_state_sync_consistency_check.json").read_text(encoding="utf-8")
    )


def test_state_sync_only_mode(sync_run: dict[str, Any]) -> None:
    assert manifest(sync_run)["state_sync_only"] is True


def test_no_discovery(sync_run: dict[str, Any]) -> None:
    assert manifest(sync_run)["strategy_discovery_run"] is False


def test_no_backtests(sync_run: dict[str, Any]) -> None:
    assert manifest(sync_run)["backtests_run"] is False


def test_no_new_performance_metrics(sync_run: dict[str, Any]) -> None:
    assert manifest(sync_run)["new_performance_metrics_computed"] is False


def test_no_indicator_library_dependency_added(sync_run: dict[str, Any]) -> None:
    assert manifest(sync_run)["indicator_library_dependency_added"] is False


def test_no_provider_download(sync_run: dict[str, Any]) -> None:
    assert manifest(sync_run)["provider_download"] is False


def test_no_intraday_data_used(sync_run: dict[str, Any]) -> None:
    assert manifest(sync_run)["intraday_data_used"] is False


def test_no_candidate_exhaustive(sync_run: dict[str, Any]) -> None:
    assert manifest(sync_run)["candidate_exhaustive_run"] is False


def test_no_paper_forward_action(sync_run: dict[str, Any]) -> None:
    loaded = manifest(sync_run)
    assert loaded["paper_forward_review"] is False
    assert loaded["paper_forward_activation"] is False


def test_no_broker_live_action(sync_run: dict[str, Any]) -> None:
    loaded = manifest(sync_run)
    assert loaded["broker_orders_submitted"] is False
    assert loaded["broker_orders_cancelled"] is False
    assert loaded["live_orders"] is False


def test_no_real_money_recommendation(sync_run: dict[str, Any]) -> None:
    assert manifest(sync_run)["real_money_recommendation"] is False


def test_active_strategy_state_preserved(sync_run: dict[str, Any]) -> None:
    assert manifest(sync_run)["active_strategy_state_changed"] is False
    assert sync_run["strategies_before"] == sync_run["strategies_after"]


def test_rejected_strategy_state_preserved(sync_run: dict[str, Any]) -> None:
    assert manifest(sync_run)["rejected_strategy_state_changed"] is False
    assert sync_run["strategies_before"] == sync_run["strategies_after"]


def test_exact_rejected_variants_not_reopened(sync_run: dict[str, Any]) -> None:
    assert manifest(sync_run)["exact_rejected_variants_reopened"] is False


def test_intraday_remains_paused(sync_run: dict[str, Any]) -> None:
    assert manifest(sync_run)["intraday_research_remains_paused"] is True


def test_compact_state_updated(sync_run: dict[str, Any]) -> None:
    assert manifest(sync_run)["compact_state_updated"] is True
    compact = (sync_run["root"] / sync.COMPACT_STATE_PATH).read_text(encoding="utf-8")
    assert "next_family_discovery_after_indicator_validation_completed" in compact
    assert f"Current next action: `{sync.NEXT_ACTION}`" in compact


def test_candidate_outcome_is_discovery_reject(sync_run: dict[str, Any]) -> None:
    assert manifest(sync_run)["candidate_outcome"] == "discovery_reject"


def test_promotion_candidates_count_is_zero(sync_run: dict[str, Any]) -> None:
    assert manifest(sync_run)["promotion_candidates_count"] == 0


def test_next_action_is_pause(sync_run: dict[str, Any]) -> None:
    assert manifest(sync_run)["next_action"] == sync.NEXT_ACTION


def test_manifest_flags_match_strict_scope(sync_run: dict[str, Any]) -> None:
    loaded = manifest(sync_run)
    for key, expected in sync.MANIFEST_FLAGS.items():
        assert loaded[key] == expected
    assert consistency(sync_run)["consistency_passed"] is True
