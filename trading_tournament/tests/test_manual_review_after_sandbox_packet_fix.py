from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from strategy_lab.research_os.exploratory_sandbox import sandbox_config as config
from strategy_lab.research_os.exploratory_sandbox import sandbox_manual_review as review


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def write_fixture(root: Path) -> None:
    registry = {
        "registry": {
            "schema_version": 1,
            "project": "trading_tournament",
            "research_only": True,
            "real_money_recommendation": False,
            "broker_integration": False,
            "live_orders": False,
            "current_next_action": "manual_review_after_sandbox_packet_fix",
            "official_current_next_action": "manual_review_after_sandbox_packet_fix",
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

    roadmap = root / config.ROADMAP_PATH
    roadmap.parent.mkdir(parents=True, exist_ok=True)
    roadmap.write_text("# Research Roadmap\n\n## Compact Current State\n\n- Next action: `manual_review_after_sandbox_packet_fix`\n", encoding="utf-8")

    batch_dir = root / review.BATCH_DIR
    batch_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        batch_dir / "sandbox_batch_manifest.json",
        {
            "variant_count_planned": 80,
            "variant_count_evaluated": 80,
            "families_evaluated_count": 7,
            "sandbox_future_preregistration_candidate_count": 0,
        },
    )
    write_csv(
        batch_dir / "sandbox_variant_results.csv",
        [{"variant_id": "v1", "status": "sandbox_family_weak", "promotable": "false", "paper_candidate_allowed": "false"}],
        ["variant_id", "status", "promotable", "paper_candidate_allowed"],
    )
    for name in [
        "sandbox_family_summary.csv",
        "sandbox_benchmark_comparison_summary.csv",
        "sandbox_risk_summary.csv",
        "sandbox_diversification_summary.csv",
        "sandbox_practicality_summary.csv",
    ]:
        write_csv(batch_dir / name, [{"family_id": "breakout_continuation"}], ["family_id"])

    packet_fix_dir = root / review.PACKET_FIX_DIR
    packet_fix_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        packet_fix_dir / "sandbox_packet_fix_manifest.json",
        {
            "repaired_packet_consistency_passed": True,
            "packet_required_files_exist_after_fix": True,
            "original_packet_consistency_passed": False,
            "sandbox_results_changed": False,
            "variant_statuses_changed": False,
            "family_audit_changed": False,
            "future_preregistration_candidates_created": False,
            "source_future_preregistration_candidate_count": 0,
            "repaired_packet_path": str(batch_dir / "sandbox_batch_packet.zip"),
        },
    )

    audit_dir = root / review.BATCH_AUDIT_DIR
    audit_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        audit_dir / "sandbox_batch_audit_manifest.json",
        {
            "sandbox_results_remain_non_promotable": True,
            "forbidden_statuses_absent": True,
            "promotable_true_count": 0,
            "paper_candidate_allowed_true_count": 0,
            "families_actionable_count": 0,
            "source_future_preregistration_candidate_count": 0,
        },
    )
    family_rows = [
        {
            "family_id": "breakout_continuation",
            "source_status": "sandbox_family_interesting",
            "actionable_now": "False",
            "audit_conclusion": "useful diversifier clue, but not actionable",
        },
        {
            "family_id": "portfolio_combination_sleeve_ensemble",
            "source_status": "sandbox_family_interesting",
            "actionable_now": "False",
            "audit_conclusion": "mostly repackages active combo behavior",
        },
        {
            "family_id": "volatility_regime",
            "source_status": "sandbox_family_weak",
            "actionable_now": "False",
            "audit_conclusion": "risk-buffer failure",
        },
    ]
    write_csv(audit_dir / "sandbox_family_audit.csv", family_rows, ["family_id", "source_status", "actionable_now", "audit_conclusion"])
    (audit_dir / "sandbox_family_audit.md").write_text("family audit unchanged\n", encoding="utf-8")


@pytest.fixture(scope="module")
def manual_review_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    root = tmp_path_factory.mktemp("manual_review_after_packet_fix")
    write_fixture(root)
    before = yaml.safe_load((root / config.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result = review.run_manual_review(root)
    after = yaml.safe_load((root / config.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result["root"] = root
    result["strategies_before"] = before
    result["strategies_after"] = after
    return result


def output(manual_review_run: dict[str, Any]) -> Path:
    return Path(manual_review_run["output_dir"])


def manifest(manual_review_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(manual_review_run) / "manual_review_after_packet_fix_manifest.json").read_text(encoding="utf-8"))


def consistency(manual_review_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(manual_review_run) / "manual_review_after_packet_fix_consistency_check.json").read_text(encoding="utf-8"))


def test_manual_review_only_mode(manual_review_run: dict[str, Any]) -> None:
    assert manifest(manual_review_run)["manual_review_only"] is True


def test_no_new_sandbox_batch(manual_review_run: dict[str, Any]) -> None:
    assert manifest(manual_review_run)["new_sandbox_batch_run"] is False


def test_no_formal_strategy_discovery(manual_review_run: dict[str, Any]) -> None:
    loaded = manifest(manual_review_run)
    assert loaded["strategy_discovery_run"] is False
    assert loaded["formal_discovery_run"] is False


def test_no_new_backtests(manual_review_run: dict[str, Any]) -> None:
    assert manifest(manual_review_run)["new_backtests_run"] is False


def test_no_new_performance_metrics(manual_review_run: dict[str, Any]) -> None:
    assert manifest(manual_review_run)["new_performance_metrics_computed"] is False


def test_sandbox_results_unchanged(manual_review_run: dict[str, Any]) -> None:
    assert manifest(manual_review_run)["sandbox_results_changed"] is False


def test_variant_statuses_unchanged(manual_review_run: dict[str, Any]) -> None:
    assert manifest(manual_review_run)["variant_statuses_changed"] is False


def test_family_audit_unchanged(manual_review_run: dict[str, Any]) -> None:
    assert manifest(manual_review_run)["family_audit_changed"] is False


def test_no_future_preregistration_candidates_created(manual_review_run: dict[str, Any]) -> None:
    assert manifest(manual_review_run)["future_preregistration_candidates_created"] is False


def test_no_indicator_library_dependency_added(manual_review_run: dict[str, Any]) -> None:
    assert manifest(manual_review_run)["indicator_library_dependency_added"] is False


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


def test_no_broker_live_action(manual_review_run: dict[str, Any]) -> None:
    loaded = manifest(manual_review_run)
    assert loaded["broker_orders_submitted"] is False
    assert loaded["broker_orders_cancelled"] is False
    assert loaded["live_orders"] is False


def test_no_real_money_recommendation(manual_review_run: dict[str, Any]) -> None:
    assert manifest(manual_review_run)["real_money_recommendation"] is False


def test_active_strategy_state_preserved(manual_review_run: dict[str, Any]) -> None:
    assert manifest(manual_review_run)["active_strategy_state_changed"] is False
    assert manual_review_run["strategies_before"] == manual_review_run["strategies_after"]


def test_rejected_strategy_state_preserved(manual_review_run: dict[str, Any]) -> None:
    assert manifest(manual_review_run)["rejected_strategy_state_changed"] is False
    assert manual_review_run["strategies_before"] == manual_review_run["strategies_after"]


def test_exact_rejected_variants_not_reopened(manual_review_run: dict[str, Any]) -> None:
    assert manifest(manual_review_run)["exact_rejected_variants_reopened"] is False


def test_intraday_remains_paused(manual_review_run: dict[str, Any]) -> None:
    assert manifest(manual_review_run)["intraday_research_remains_paused"] is True


def test_sandbox_results_remain_non_promotable(manual_review_run: dict[str, Any]) -> None:
    assert manifest(manual_review_run)["sandbox_results_remain_non_promotable"] is True


def test_sandbox_cannot_create_paper_candidates(manual_review_run: dict[str, Any]) -> None:
    assert manifest(manual_review_run)["sandbox_can_create_paper_candidates"] is False


def test_packet_fix_accepted(manual_review_run: dict[str, Any]) -> None:
    assert manifest(manual_review_run)["packet_fix_accepted"] is True


def test_batch_001_accepted_as_non_promotable_exploration(manual_review_run: dict[str, Any]) -> None:
    assert manifest(manual_review_run)["batch_001_accepted_as_non_promotable_exploration"] is True


def test_next_action_is_valid(manual_review_run: dict[str, Any]) -> None:
    assert manifest(manual_review_run)["next_action"] in review.VALID_NEXT_ACTIONS
    assert manifest(manual_review_run)["next_action"] == "create_objective_reset_review"


def test_manifest_flags_match_strict_scope(manual_review_run: dict[str, Any]) -> None:
    loaded = manifest(manual_review_run)
    for key, expected in review.MANIFEST_FLAGS.items():
        assert loaded[key] == expected
    assert consistency(manual_review_run)["consistency_passed"] is True
