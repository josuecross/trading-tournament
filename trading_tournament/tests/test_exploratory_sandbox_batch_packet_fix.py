from __future__ import annotations

import csv
import json
import zipfile
from pathlib import Path
from typing import Any

import pytest
import yaml

from strategy_lab.research_os.exploratory_sandbox import sandbox_config as config
from strategy_lab.research_os.exploratory_sandbox import sandbox_packet_fix as packet_fix


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
            "current_next_action": "fix_exploratory_sandbox_batch_evidence_packet",
            "official_current_next_action": "fix_exploratory_sandbox_batch_evidence_packet",
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
    roadmap.write_text("# Research Roadmap\n\n## Compact Current State\n\n- Next action: `fix_exploratory_sandbox_batch_evidence_packet`\n", encoding="utf-8")

    audit_dir = root / packet_fix.AUDIT_OUTPUT_DIR
    audit_dir.mkdir(parents=True, exist_ok=True)
    (audit_dir / "sandbox_family_audit.md").write_text("family audit unchanged\n", encoding="utf-8")
    write_json(audit_dir / "sandbox_batch_audit_manifest.json", {"next_action": "fix_exploratory_sandbox_batch_evidence_packet"})

    batch = root / packet_fix.BATCH_DIR
    batch.mkdir(parents=True, exist_ok=True)
    manifest = {
        "batch_id": "batch_001",
        "sandbox_batch_run": True,
        "sandbox_results_non_promotable": True,
        "sandbox_can_create_paper_candidates": False,
        "strategy_discovery_run": False,
        "formal_discovery_run": False,
        "candidate_exhaustive_run": False,
        "paper_forward_review": False,
        "paper_forward_activation": False,
        "provider_download": False,
        "intraday_data_used": False,
        "broker_orders_submitted": False,
        "broker_orders_cancelled": False,
        "live_orders": False,
        "real_money_recommendation": False,
        "variant_count_planned": 80,
        "variant_count_evaluated": 80,
        "families_evaluated_count": 7,
        "sandbox_future_preregistration_candidate_count": 0,
    }
    write_json(batch / "sandbox_batch_manifest.json", manifest)
    live_consistency = {
        "consistency_passed": True,
        "required_files_exist": True,
        "results_non_promotable": True,
        "sandbox_cannot_create_paper_candidates": True,
        "no_provider_download": True,
        "no_intraday_data_used": True,
        "no_candidate_exhaustive": True,
        "no_paper_forward_action": True,
        "no_broker_live_action": True,
        "no_real_money_recommendation": True,
    }
    stale_consistency = {**live_consistency, "consistency_passed": False, "required_files_exist": False}
    write_json(batch / "sandbox_batch_consistency_check.json", live_consistency)
    (batch / "sandbox_batch_summary.md").write_text("summary\n", encoding="utf-8")
    (batch / "sandbox_batch_preflight_report.md").write_text("preflight\n", encoding="utf-8")
    (batch / "sandbox_family_summary.md").write_text("family\n", encoding="utf-8")
    (batch / "sandbox_overfitting_risk_summary.md").write_text("overfit\n", encoding="utf-8")
    (batch / "sandbox_research_only_leverage_summary.md").write_text("leverage\n", encoding="utf-8")
    (batch / "sandbox_future_preregistration_candidates.md").write_text("count 0\n", encoding="utf-8")
    (batch / "sandbox_discarded_or_weak_families.md").write_text("weak\n", encoding="utf-8")
    (batch / "sandbox_do_not_promote.md").write_text("non_promotable_exploration\n", encoding="utf-8")
    (batch / "sandbox_batch_next_action.md").write_text("next\n", encoding="utf-8")
    write_csv(
        batch / "sandbox_variant_results.csv",
        [
            {
                "variant_id": "v1",
                "family_id": "breakout_continuation",
                "status": "sandbox_family_interesting",
                "promotable": "false",
                "paper_candidate_allowed": "false",
            }
        ],
        ["variant_id", "family_id", "status", "promotable", "paper_candidate_allowed"],
    )
    write_csv(
        batch / "sandbox_family_summary.csv",
        [{"family_id": "breakout_continuation", "family_status": "sandbox_family_interesting"}],
        ["family_id", "family_status"],
    )
    write_csv(batch / "sandbox_benchmark_comparison_summary.csv", [{"family_id": "breakout_continuation"}], ["family_id"])
    write_csv(batch / "sandbox_risk_summary.csv", [{"family_id": "breakout_continuation"}], ["family_id"])
    write_csv(batch / "sandbox_diversification_summary.csv", [{"family_id": "breakout_continuation"}], ["family_id"])
    write_csv(batch / "sandbox_practicality_summary.csv", [{"family_id": "breakout_continuation"}], ["family_id"])

    with zipfile.ZipFile(batch / "sandbox_batch_packet.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(batch.iterdir()):
            if path.name == "sandbox_batch_packet.zip":
                continue
            if path.name == "sandbox_batch_consistency_check.json":
                tmp = batch / "_stale_consistency.json"
                write_json(tmp, stale_consistency)
                archive.write(tmp, "sandbox_batch_consistency_check.json")
                tmp.unlink()
            else:
                archive.write(path, path.name)


@pytest.fixture(scope="module")
def packet_fix_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    root = tmp_path_factory.mktemp("exploratory_sandbox_packet_fix")
    write_fixture(root)
    before = yaml.safe_load((root / config.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result = packet_fix.run_packet_fix(root)
    after = yaml.safe_load((root / config.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result["root"] = root
    result["strategies_before"] = before
    result["strategies_after"] = after
    return result


def output(packet_fix_run: dict[str, Any]) -> Path:
    return Path(packet_fix_run["output_dir"])


def manifest(packet_fix_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(packet_fix_run) / "sandbox_packet_fix_manifest.json").read_text(encoding="utf-8"))


def consistency(packet_fix_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(packet_fix_run) / "sandbox_packet_fix_consistency_check.json").read_text(encoding="utf-8"))


def repaired_packet_consistency(packet_fix_run: dict[str, Any]) -> dict[str, Any]:
    packet = Path(manifest(packet_fix_run)["repaired_packet_path"])
    with zipfile.ZipFile(packet, "r") as archive:
        with archive.open("sandbox_batch_consistency_check.json") as handle:
            return json.loads(handle.read().decode("utf-8"))


def test_packet_fix_only_mode(packet_fix_run: dict[str, Any]) -> None:
    assert manifest(packet_fix_run)["packet_fix_only"] is True


def test_no_new_sandbox_batch(packet_fix_run: dict[str, Any]) -> None:
    assert manifest(packet_fix_run)["new_sandbox_batch_run"] is False


def test_no_formal_strategy_discovery(packet_fix_run: dict[str, Any]) -> None:
    loaded = manifest(packet_fix_run)
    assert loaded["strategy_discovery_run"] is False
    assert loaded["formal_discovery_run"] is False


def test_no_new_backtests(packet_fix_run: dict[str, Any]) -> None:
    assert manifest(packet_fix_run)["new_backtests_run"] is False


def test_no_new_performance_metrics(packet_fix_run: dict[str, Any]) -> None:
    assert manifest(packet_fix_run)["new_performance_metrics_computed"] is False


def test_sandbox_results_unchanged(packet_fix_run: dict[str, Any]) -> None:
    assert manifest(packet_fix_run)["sandbox_results_changed"] is False


def test_variant_statuses_unchanged(packet_fix_run: dict[str, Any]) -> None:
    assert manifest(packet_fix_run)["variant_statuses_changed"] is False


def test_family_audit_unchanged(packet_fix_run: dict[str, Any]) -> None:
    assert manifest(packet_fix_run)["family_audit_changed"] is False


def test_no_future_preregistration_candidates_created(packet_fix_run: dict[str, Any]) -> None:
    assert manifest(packet_fix_run)["future_preregistration_candidates_created"] is False
    assert manifest(packet_fix_run)["source_future_preregistration_candidate_count"] == 0


def test_no_indicator_library_dependency_added(packet_fix_run: dict[str, Any]) -> None:
    assert manifest(packet_fix_run)["indicator_library_dependency_added"] is False


def test_no_provider_download(packet_fix_run: dict[str, Any]) -> None:
    assert manifest(packet_fix_run)["provider_download"] is False


def test_no_intraday_data_used(packet_fix_run: dict[str, Any]) -> None:
    assert manifest(packet_fix_run)["intraday_data_used"] is False


def test_no_candidate_exhaustive(packet_fix_run: dict[str, Any]) -> None:
    assert manifest(packet_fix_run)["candidate_exhaustive_run"] is False


def test_no_paper_forward_action(packet_fix_run: dict[str, Any]) -> None:
    loaded = manifest(packet_fix_run)
    assert loaded["paper_forward_review"] is False
    assert loaded["paper_forward_activation"] is False


def test_no_broker_live_action(packet_fix_run: dict[str, Any]) -> None:
    loaded = manifest(packet_fix_run)
    assert loaded["broker_orders_submitted"] is False
    assert loaded["broker_orders_cancelled"] is False
    assert loaded["live_orders"] is False


def test_no_real_money_recommendation(packet_fix_run: dict[str, Any]) -> None:
    assert manifest(packet_fix_run)["real_money_recommendation"] is False


def test_active_strategy_state_preserved(packet_fix_run: dict[str, Any]) -> None:
    assert manifest(packet_fix_run)["active_strategy_state_changed"] is False
    assert packet_fix_run["strategies_before"] == packet_fix_run["strategies_after"]


def test_rejected_strategy_state_preserved(packet_fix_run: dict[str, Any]) -> None:
    assert manifest(packet_fix_run)["rejected_strategy_state_changed"] is False
    assert packet_fix_run["strategies_before"] == packet_fix_run["strategies_after"]


def test_exact_rejected_variants_not_reopened(packet_fix_run: dict[str, Any]) -> None:
    assert manifest(packet_fix_run)["exact_rejected_variants_reopened"] is False


def test_intraday_remains_paused(packet_fix_run: dict[str, Any]) -> None:
    assert manifest(packet_fix_run)["intraday_research_remains_paused"] is True


def test_sandbox_results_remain_non_promotable(packet_fix_run: dict[str, Any]) -> None:
    assert manifest(packet_fix_run)["sandbox_results_remain_non_promotable"] is True


def test_sandbox_cannot_create_paper_candidates(packet_fix_run: dict[str, Any]) -> None:
    assert manifest(packet_fix_run)["sandbox_can_create_paper_candidates"] is False


def test_repaired_packet_consistency_passed(packet_fix_run: dict[str, Any]) -> None:
    assert manifest(packet_fix_run)["original_packet_consistency_passed"] is False
    assert manifest(packet_fix_run)["repaired_packet_consistency_passed"] is True
    assert repaired_packet_consistency(packet_fix_run)["consistency_passed"] is True


def test_repaired_packet_required_files_exist(packet_fix_run: dict[str, Any]) -> None:
    assert manifest(packet_fix_run)["packet_required_files_exist_after_fix"] is True
    assert repaired_packet_consistency(packet_fix_run)["required_files_exist"] is True


def test_next_action_is_valid(packet_fix_run: dict[str, Any]) -> None:
    assert manifest(packet_fix_run)["next_action"] in packet_fix.VALID_NEXT_ACTIONS


def test_manifest_flags_match_strict_scope(packet_fix_run: dict[str, Any]) -> None:
    loaded = manifest(packet_fix_run)
    for key, expected in packet_fix.MANIFEST_FLAGS.items():
        assert loaded[key] == expected
    assert consistency(packet_fix_run)["consistency_passed"] is True
