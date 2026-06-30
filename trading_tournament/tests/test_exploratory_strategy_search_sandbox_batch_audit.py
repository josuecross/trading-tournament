from __future__ import annotations

import csv
import json
import zipfile
from pathlib import Path
from typing import Any

import pytest
import yaml

from strategy_lab.research_os.exploratory_sandbox import sandbox_batch_audit as audit
from strategy_lab.research_os.exploratory_sandbox import sandbox_config as config


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
            "current_next_action": "audit_exploratory_sandbox_batch_results",
            "official_current_next_action": "audit_exploratory_sandbox_batch_results",
            "intraday_research_remains_paused": True,
            "static_all_weather_benchmark_control_status": "benchmark_control_accepted",
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
    roadmap.write_text("# Research Roadmap\n\n## Compact Current State\n\n- Next action: `audit_exploratory_sandbox_batch_results`\n", encoding="utf-8")
    compact = root / audit.COMPACT_STATE_PATH
    compact.parent.mkdir(parents=True, exist_ok=True)
    compact.write_text("Current next action: `audit_exploratory_sandbox_batch_results`\n", encoding="utf-8")

    batch = root / audit.BATCH_DIR
    batch.mkdir(parents=True, exist_ok=True)
    manifest = {
        "batch_id": "batch_001",
        "sandbox_batch_run": True,
        "variant_count_planned": 80,
        "variant_count_evaluated": 80,
        "families_evaluated_count": 7,
        "sandbox_future_preregistration_candidate_count": 0,
        "sandbox_results_non_promotable": True,
        "sandbox_can_create_paper_candidates": False,
        "next_action": "audit_exploratory_sandbox_batch_results",
    }
    write_json(batch / "sandbox_batch_manifest.json", manifest)
    live_consistency = {
        "consistency_passed": True,
        "required_files_exist": True,
        "no_result_promotable": True,
        "no_result_paper_candidate_allowed": True,
        "forbidden_statuses_absent": True,
    }
    stale_consistency = {**live_consistency, "consistency_passed": False, "required_files_exist": False}
    write_json(batch / "sandbox_batch_consistency_check.json", live_consistency)
    (batch / "sandbox_batch_summary.md").write_text("summary\n", encoding="utf-8")
    (batch / "sandbox_batch_preflight_report.md").write_text("preflight\n", encoding="utf-8")
    (batch / "sandbox_family_summary.md").write_text("family\n", encoding="utf-8")
    (batch / "sandbox_overfitting_risk_summary.md").write_text("overfit\n", encoding="utf-8")
    (batch / "sandbox_research_only_leverage_summary.md").write_text("leverage\n", encoding="utf-8")
    (batch / "sandbox_future_preregistration_candidates.md").write_text("none\n", encoding="utf-8")
    (batch / "sandbox_discarded_or_weak_families.md").write_text("weak\n", encoding="utf-8")
    (batch / "sandbox_do_not_promote.md").write_text("non_promotable_exploration\n", encoding="utf-8")
    (batch / "sandbox_batch_next_action.md").write_text("audit\n", encoding="utf-8")

    family_rows = [
        {
            "family_id": "breakout_continuation",
            "family_status": "sandbox_family_interesting",
            "variants_tested": 12,
            "variants_positive_objective_progress": 12,
            "variants_beating_active_combo": 0,
            "variants_passing_basic_drawdown_screen": 10,
            "variants_low_correlation_to_active_combo": 12,
            "possible_future_preregistration_candidate": "False",
        },
        {
            "family_id": "portfolio_combination_sleeve_ensemble",
            "family_status": "sandbox_family_interesting",
            "variants_tested": 12,
            "variants_positive_objective_progress": 12,
            "variants_beating_active_combo": 1,
            "variants_passing_basic_drawdown_screen": 8,
            "variants_low_correlation_to_active_combo": 3,
            "possible_future_preregistration_candidate": "False",
        },
        {
            "family_id": "volatility_regime",
            "family_status": "sandbox_family_weak",
            "variants_tested": 12,
            "variants_positive_objective_progress": 12,
            "variants_beating_active_combo": 8,
            "variants_passing_basic_drawdown_screen": 0,
            "variants_low_correlation_to_active_combo": 12,
            "possible_future_preregistration_candidate": "False",
        },
    ]
    for family_id in ("trend_momentum", "mean_reversion", "factor_style_rotation", "macro_portfolio_contribution"):
        family_rows.append(
            {
                "family_id": family_id,
                "family_status": "sandbox_family_weak",
                "variants_tested": 12,
                "variants_positive_objective_progress": 1,
                "variants_beating_active_combo": 0,
                "variants_passing_basic_drawdown_screen": 0,
                "variants_low_correlation_to_active_combo": 1,
                "possible_future_preregistration_candidate": "False",
            }
        )
    write_csv(
        batch / "sandbox_family_summary.csv",
        family_rows,
        [
            "family_id",
            "family_status",
            "variants_tested",
            "variants_positive_objective_progress",
            "variants_beating_active_combo",
            "variants_passing_basic_drawdown_screen",
            "variants_low_correlation_to_active_combo",
            "possible_future_preregistration_candidate",
        ],
    )
    variant_rows = [
        {
            "variant_id": "v1",
            "family_id": "breakout_continuation",
            "status": "sandbox_family_interesting",
            "promotable": "false",
            "paper_candidate_allowed": "false",
        },
        {
            "variant_id": "v2",
            "family_id": "trend_momentum",
            "status": "sandbox_family_weak",
            "promotable": "false",
            "paper_candidate_allowed": "false",
        },
    ]
    write_csv(batch / "sandbox_variant_results.csv", variant_rows, ["variant_id", "family_id", "status", "promotable", "paper_candidate_allowed"])
    bench_rows = [
        {"family_id": row["family_id"], "benchmark_id": "active_combo", "median_delta_180d_median_final_equity": -1, "median_correlation": 0.1}
        for row in family_rows
    ]
    write_csv(batch / "sandbox_benchmark_comparison_summary.csv", bench_rows, ["family_id", "benchmark_id", "median_delta_180d_median_final_equity", "median_correlation"])
    write_csv(batch / "sandbox_risk_summary.csv", [{"family_id": row["family_id"]} for row in family_rows], ["family_id"])
    write_csv(
        batch / "sandbox_diversification_summary.csv",
        [{"family_id": row["family_id"], "median_corr_vs_active_combo": 0.1} for row in family_rows],
        ["family_id", "median_corr_vs_active_combo"],
    )
    write_csv(batch / "sandbox_practicality_summary.csv", [{"family_id": row["family_id"]} for row in family_rows], ["family_id"])

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
def audit_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    root = tmp_path_factory.mktemp("exploratory_sandbox_batch_audit")
    write_fixture(root)
    before = yaml.safe_load((root / config.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result = audit.run_sandbox_batch_audit(root)
    after = yaml.safe_load((root / config.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result["root"] = root
    result["strategies_before"] = before
    result["strategies_after"] = after
    return result


def output(audit_run: dict[str, Any]) -> Path:
    return Path(audit_run["output_dir"])


def manifest(audit_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(audit_run) / "sandbox_batch_audit_manifest.json").read_text(encoding="utf-8"))


def consistency(audit_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(audit_run) / "sandbox_batch_audit_consistency_check.json").read_text(encoding="utf-8"))


def test_sandbox_batch_audit_only_mode(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["sandbox_batch_audit_only"] is True


def test_no_new_sandbox_batch(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["new_sandbox_batch_run"] is False


def test_no_formal_strategy_discovery(audit_run: dict[str, Any]) -> None:
    loaded = manifest(audit_run)
    assert loaded["strategy_discovery_run"] is False
    assert loaded["formal_discovery_run"] is False


def test_no_new_backtests(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["new_backtests_run"] is False


def test_no_new_performance_metrics(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["new_performance_metrics_computed"] is False


def test_no_indicator_library_dependency_added(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["indicator_library_dependency_added"] is False


def test_no_provider_download(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["provider_download"] is False


def test_no_intraday_data_used(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["intraday_data_used"] is False


def test_no_candidate_exhaustive(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["candidate_exhaustive_run"] is False


def test_no_paper_forward_action(audit_run: dict[str, Any]) -> None:
    loaded = manifest(audit_run)
    assert loaded["paper_forward_review"] is False
    assert loaded["paper_forward_activation"] is False


def test_no_broker_live_action(audit_run: dict[str, Any]) -> None:
    loaded = manifest(audit_run)
    assert loaded["broker_orders_submitted"] is False
    assert loaded["broker_orders_cancelled"] is False
    assert loaded["live_orders"] is False


def test_no_real_money_recommendation(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["real_money_recommendation"] is False


def test_active_strategy_state_preserved(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["active_strategy_state_changed"] is False
    assert audit_run["strategies_before"] == audit_run["strategies_after"]


def test_rejected_strategy_state_preserved(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["rejected_strategy_state_changed"] is False
    assert audit_run["strategies_before"] == audit_run["strategies_after"]


def test_exact_rejected_variants_not_reopened(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["exact_rejected_variants_reopened"] is False


def test_intraday_remains_paused(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["intraday_research_remains_paused"] is True


def test_sandbox_results_remain_non_promotable(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["sandbox_results_remain_non_promotable"] is True


def test_sandbox_cannot_create_paper_candidates(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["sandbox_can_create_paper_candidates"] is False


def test_consistency_issue_review_exists(audit_run: dict[str, Any]) -> None:
    text = (output(audit_run) / "sandbox_batch_consistency_issue_review.md").read_text(encoding="utf-8")
    assert "packet assembly timing" in text
    assert manifest(audit_run)["consistency_issue_found"] is True


def test_family_audit_exists(audit_run: dict[str, Any]) -> None:
    assert (output(audit_run) / "sandbox_family_audit.md").exists()
    assert (output(audit_run) / "sandbox_family_audit.csv").exists()


def test_overfitting_audit_exists(audit_run: dict[str, Any]) -> None:
    text = (output(audit_run) / "sandbox_overfitting_audit.md").read_text(encoding="utf-8")
    assert "Best single variant cannot be promoted" in text


def test_future_preregistration_review_exists(audit_run: dict[str, Any]) -> None:
    text = (output(audit_run) / "sandbox_future_preregistration_review.md").read_text(encoding="utf-8")
    assert "Actionable family count after audit" in text


def test_next_action_is_valid(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["next_action"] in audit.VALID_NEXT_ACTIONS


def test_manifest_flags_match_strict_scope(audit_run: dict[str, Any]) -> None:
    loaded = manifest(audit_run)
    for key, expected in audit.MANIFEST_FLAGS.items():
        assert loaded[key] == expected
    assert consistency(audit_run)["consistency_passed"] is True
