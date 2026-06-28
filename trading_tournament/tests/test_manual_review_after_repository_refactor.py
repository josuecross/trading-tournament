from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

import run_manual_review_after_repository_refactor as manual_review


def write_fixture(root: Path) -> None:
    registry = {
        "registry": {
            "schema_version": 1,
            "project": "trading_tournament",
            "research_only": True,
            "real_money_recommendation": False,
            "broker_integration": False,
            "live_orders": False,
            "current_next_action": "manual_review_required_after_repository_refactor",
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
    registry_path = root / manual_review.REGISTRY_PATH
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")

    roadmap = root / manual_review.ROADMAP_PATH
    roadmap.parent.mkdir(parents=True, exist_ok=True)
    roadmap.write_text(
        "# Research Roadmap\n\n## Compact Current State\n\n- Current next action: `manual_review_required_after_repository_refactor`\n\nCurrent next action: `audit_risk_controlled_high_return_discovery_failures`\n",
        encoding="utf-8",
    )
    compact = root / manual_review.COMPACT_STATE_PATH
    compact.parent.mkdir(parents=True, exist_ok=True)
    compact.write_text("# Current Tournament State\n\nCurrent next action: `manual_review_required_after_repository_refactor`\n", encoding="utf-8")
    (root / ".gitignore").write_text("# BEGIN trading-tournament generated artifact policy\n*.zip\n*.jsonl\n# END trading-tournament generated artifact policy\n", encoding="utf-8")
    refactor_manifest = root / manual_review.REFACTOR_EVIDENCE_DIR / "repo_refactor_manifest.json"
    refactor_manifest.parent.mkdir(parents=True, exist_ok=True)
    refactor_manifest.write_text(json.dumps({"repository_refactor_only": True, "next_action": "manual_review_required_after_repository_refactor"}), encoding="utf-8")


@pytest.fixture(scope="module")
def review_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    root = tmp_path_factory.mktemp("manual_review_after_repository_refactor")
    write_fixture(root)
    before = yaml.safe_load((root / manual_review.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result = manual_review.run_manual_review_after_repository_refactor(root)
    after = yaml.safe_load((root / manual_review.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result["root"] = root
    result["strategies_before"] = before
    result["strategies_after"] = after
    return result


def output(review_run: dict[str, Any]) -> Path:
    return Path(review_run["output_dir"])


def manifest(review_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(review_run) / "manual_refactor_review_manifest.json").read_text(encoding="utf-8"))


def consistency(review_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(review_run) / "manual_refactor_review_consistency_check.json").read_text(encoding="utf-8"))


def test_manual_review_only_mode(review_run: dict[str, Any]) -> None:
    assert manifest(review_run)["manual_review_only"] is True


def test_no_strategy_discovery(review_run: dict[str, Any]) -> None:
    assert manifest(review_run)["strategy_discovery_run"] is False


def test_no_backtests(review_run: dict[str, Any]) -> None:
    assert manifest(review_run)["backtests_run"] is False


def test_no_new_performance_metrics(review_run: dict[str, Any]) -> None:
    assert manifest(review_run)["new_performance_metrics_computed"] is False


def test_no_provider_download(review_run: dict[str, Any]) -> None:
    assert manifest(review_run)["provider_download"] is False


def test_no_intraday_data_used(review_run: dict[str, Any]) -> None:
    assert manifest(review_run)["intraday_data_used"] is False


def test_no_candidate_exhaustive(review_run: dict[str, Any]) -> None:
    assert manifest(review_run)["candidate_exhaustive_run"] is False


def test_no_paper_forward_action(review_run: dict[str, Any]) -> None:
    loaded = manifest(review_run)
    assert loaded["paper_forward_review"] is False
    assert loaded["paper_forward_activation"] is False


def test_no_broker_orders_submitted(review_run: dict[str, Any]) -> None:
    assert manifest(review_run)["broker_orders_submitted"] is False


def test_no_broker_orders_cancelled(review_run: dict[str, Any]) -> None:
    assert manifest(review_run)["broker_orders_cancelled"] is False


def test_no_live_orders(review_run: dict[str, Any]) -> None:
    assert manifest(review_run)["live_orders"] is False


def test_no_real_money_recommendation(review_run: dict[str, Any]) -> None:
    assert manifest(review_run)["real_money_recommendation"] is False


def test_active_strategy_state_preserved(review_run: dict[str, Any]) -> None:
    assert manifest(review_run)["active_strategy_state_changed"] is False
    assert review_run["strategies_before"] == review_run["strategies_after"]


def test_rejected_strategy_state_preserved(review_run: dict[str, Any]) -> None:
    assert manifest(review_run)["rejected_strategy_state_changed"] is False
    assert review_run["strategies_before"] == review_run["strategies_after"]


def test_exact_rejected_variants_not_reopened(review_run: dict[str, Any]) -> None:
    assert manifest(review_run)["exact_rejected_variants_reopened"] is False


def test_intraday_remains_paused(review_run: dict[str, Any]) -> None:
    assert manifest(review_run)["intraday_research_remains_paused"] is True


def test_canonical_state_acceptance_file_exists(review_run: dict[str, Any]) -> None:
    assert (output(review_run) / "canonical_structure_acceptance.md").exists()


def test_next_action_reconciliation_file_exists(review_run: dict[str, Any]) -> None:
    assert (output(review_run) / "next_action_reconciliation.md").exists()


def test_tracked_generated_files_classification_exists(review_run: dict[str, Any]) -> None:
    assert (output(review_run) / "tracked_generated_files_classification.csv").exists()


def test_gitignore_review_exists(review_run: dict[str, Any]) -> None:
    assert (output(review_run) / "gitignore_review.md").exists()


def test_next_action_is_valid(review_run: dict[str, Any]) -> None:
    assert manifest(review_run)["next_action"] in manual_review.VALID_NEXT_ACTIONS
    assert manifest(review_run)["next_action"] == manual_review.NEXT_ACTION


def test_manifest_flags_match_strict_scope(review_run: dict[str, Any]) -> None:
    loaded = manifest(review_run)
    for key, expected in manual_review.MANIFEST_FLAGS.items():
        assert loaded[key] == expected
    assert consistency(review_run)["consistency_passed"] is True
