from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

import run_intraday_data_constraints_pause as pause


def write_fixture(root: Path) -> None:
    registry_path = root / pause.REGISTRY_PATH
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        yaml.safe_dump(
            {
                "registry": {
                    "schema_version": 1,
                    "project": "trading_tournament",
                    "research_only": True,
                    "current_next_action": "pause_intraday_research_due_data_constraints",
                    "real_money_recommendation": False,
                    "broker_integration": False,
                    "live_orders": False,
                },
                "strategies": [
                    {
                        "id": "paper_forward_vm_quality_lowvol_proxy_v1",
                        "status": "active_observation",
                        "paper_forward_active": True,
                        "candidate_exhaustive_run": False,
                    },
                    {
                        "id": "dual_momentum_paa_clean_v1",
                        "status": "discovery_reject",
                        "paper_forward_active": False,
                        "candidate_exhaustive_run": False,
                    },
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    roadmap = root / pause.ROADMAP_PATH
    roadmap.parent.mkdir(parents=True, exist_ok=True)
    roadmap.write_text(
        "# Research Roadmap\n\nCurrent next action: `pause_intraday_research_due_data_constraints`\n",
        encoding="utf-8",
    )

    readiness = root / pause.READINESS_AUDIT_DIR / "intraday_readiness_manifest.json"
    readiness.parent.mkdir(parents=True, exist_ok=True)
    readiness.write_text(
        json.dumps({"readiness_verdict": "intraday_research_not_ready"}),
        encoding="utf-8",
    )
    blocker_fix = root / pause.BLOCKER_FIX_DIR / "intraday_blocker_fix_manifest.json"
    blocker_fix.parent.mkdir(parents=True, exist_ok=True)
    blocker_fix.write_text(
        json.dumps(
            {
                "blockers_fixed_count": 6,
                "blockers_partially_fixed_count": 2,
                "critical_blockers_remaining_count": 2,
            }
        ),
        encoding="utf-8",
    )
    source_review = root / pause.DATA_SOURCE_REVIEW_DIR / "intraday_data_source_review_manifest.json"
    source_review.parent.mkdir(parents=True, exist_ok=True)
    source_review.write_text(
        json.dumps(
            {
                "source_candidate_count": 3,
                "approved_intraday_data_source_found": False,
                "manual_terms_review_required": True,
                "local_intraday_data_present": False,
                "recommended_data_source_path": "manual_terms_review_then_select_yfinance_intraday_alpaca_data_or_manual_csv_source",
            }
        ),
        encoding="utf-8",
    )
    third_failure = root / pause.THIRD_FAILURE_DIR / "third_expansion_failure_audit_manifest.json"
    third_failure.parent.mkdir(parents=True, exist_ok=True)
    third_failure.write_text(
        json.dumps(
            {
                "exact_rejected_variants_closed": True,
                "daily_weekly_expansion_should_pause": True,
                "families_remaining_open_count": 4,
            }
        ),
        encoding="utf-8",
    )


@pytest.fixture(scope="module")
def pause_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    root = tmp_path_factory.mktemp("intraday_data_constraints_pause")
    write_fixture(root)
    before = yaml.safe_load((root / pause.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result = pause.run_intraday_data_constraints_pause(root)
    after = yaml.safe_load((root / pause.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result["strategies_before"] = before
    result["strategies_after"] = after
    return result


def output(pause_run: dict[str, Any]) -> Path:
    return Path(pause_run["output_dir"])


def manifest(pause_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(pause_run) / "intraday_data_constraints_pause_manifest.json").read_text(encoding="utf-8"))


def consistency(pause_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(pause_run) / "intraday_data_constraints_pause_consistency_check.json").read_text(encoding="utf-8"))


def test_governance_checkpoint_only(pause_run: dict[str, Any]) -> None:
    assert manifest(pause_run)["governance_checkpoint_only"] is True


def test_intraday_research_is_paused(pause_run: dict[str, Any]) -> None:
    assert manifest(pause_run)["intraday_research_paused"] is True


def test_no_intraday_backtests(pause_run: dict[str, Any]) -> None:
    assert manifest(pause_run)["intraday_backtests_run"] is False


def test_no_new_discovery(pause_run: dict[str, Any]) -> None:
    assert manifest(pause_run)["new_discovery_run"] is False


def test_no_new_performance_metrics(pause_run: dict[str, Any]) -> None:
    assert manifest(pause_run)["new_performance_metrics_computed"] is False


def test_no_provider_download(pause_run: dict[str, Any]) -> None:
    assert manifest(pause_run)["provider_download"] is False


def test_no_provider_api_call(pause_run: dict[str, Any]) -> None:
    assert manifest(pause_run)["provider_api_called"] is False


def test_no_intraday_cache_bootstrap(pause_run: dict[str, Any]) -> None:
    assert manifest(pause_run)["intraday_cache_bootstrapped"] is False


def test_no_candidate_exhaustive(pause_run: dict[str, Any]) -> None:
    assert manifest(pause_run)["candidate_exhaustive_run"] is False


def test_no_paper_forward_action(pause_run: dict[str, Any]) -> None:
    loaded = manifest(pause_run)
    assert loaded["paper_forward_review"] is False
    assert loaded["paper_forward_activation"] is False


def test_no_broker_orders_submitted(pause_run: dict[str, Any]) -> None:
    assert manifest(pause_run)["broker_orders_submitted"] is False


def test_no_broker_orders_cancelled(pause_run: dict[str, Any]) -> None:
    assert manifest(pause_run)["broker_orders_cancelled"] is False


def test_no_live_orders(pause_run: dict[str, Any]) -> None:
    assert manifest(pause_run)["live_orders"] is False


def test_no_strategy_state_changes(pause_run: dict[str, Any]) -> None:
    assert pause_run["strategies_before"] == pause_run["strategies_after"]


def test_preserved_infrastructure_file_exists(pause_run: dict[str, Any]) -> None:
    assert (output(pause_run) / "intraday_preserved_infrastructure.md").exists()


def test_forbidden_next_steps_file_exists(pause_run: dict[str, Any]) -> None:
    assert (output(pause_run) / "intraday_forbidden_next_steps.md").exists()


def test_pivot_recommendation_exists(pause_run: dict[str, Any]) -> None:
    assert (output(pause_run) / "non_intraday_research_pivot_recommendation.md").exists()


def test_next_action_is_risk_controlled_high_return_preregistration(pause_run: dict[str, Any]) -> None:
    assert manifest(pause_run)["next_action"] == "pre_register_risk_controlled_high_return_family_review"


def test_manifest_flags_match_strict_scope(pause_run: dict[str, Any]) -> None:
    loaded = manifest(pause_run)
    for key, value in pause.MANIFEST_FLAGS.items():
        assert loaded[key] == value
    assert consistency(pause_run)["consistency_passed"] is True
