from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from strategy_lab.research_os.exploratory_sandbox import sandbox_config as config
from strategy_lab.research_os.objective_reset import revised_objective_sandbox_batch_audit as audit
from strategy_lab.research_os.objective_reset.revised_objective_batch_config import BATCH_ID
from strategy_lab.research_os.objective_reset.revised_objective_sandbox_batch import BATCH_OUTPUT_DIR, BATCH_REQUIRED_FILES


FAMILIES = (
    ("breakout_continuation", 18, "sandbox_future_preregistration_candidate"),
    ("portfolio_combination_sleeve_ensemble", 18, "sandbox_family_weak"),
    ("volatility_regime", 16, "sandbox_family_weak"),
    ("trend_momentum", 16, "sandbox_family_weak"),
    ("macro_portfolio_contribution", 12, "sandbox_future_preregistration_candidate"),
)


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


def source_variant_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    status_cycle = ["sandbox_family_weak"] * 37 + ["sandbox_needs_objective_reset"] * 33 + ["sandbox_component_candidate"] * 10
    cursor = 0
    for family_id, count, _status in FAMILIES:
        for index in range(1, count + 1):
            status = status_cycle[cursor]
            cursor += 1
            is_breakout = family_id == "breakout_continuation"
            is_macro = family_id == "macro_portfolio_contribution"
            is_portfolio = family_id == "portfolio_combination_sleeve_ensemble"
            rows.append(
                {
                    "variant_id": f"ro_{family_id}_{index:02d}",
                    "family_id": family_id,
                    "status": status,
                    "promotable": "false",
                    "paper_candidate_allowed": "false",
                    "standalone_growth_score": 100.0,
                    "portfolio_contribution_score": 70.0 if (is_breakout and index <= 5) else (58.0 if is_macro else 44.0),
                    "risk_integrity_score": 60.0 if ((is_breakout and index <= 6) or (is_macro and index <= 4)) else 0.0,
                    "overfit_risk_score": 35.0,
                    "practicality_score": 60.0 if is_breakout else 18.0,
                    "avg_cash_allocation": 0.72 if is_breakout else 0.13,
                    "trade_count": 90 if is_breakout else 650,
                    "return_drag_penalty": 0.9 if is_breakout else 1.0,
                    "duplicate_penalty": 18.0 if is_portfolio else 0.0,
                    "corr_vs_active_combo": 0.97 if is_portfolio else 0.01,
                    "useful_contribution_evidence": "true" if (is_breakout and index <= 5) else "false",
                    "acceptable_drawdown_risk_integrity": "true"
                    if ((is_breakout and index <= 6) or (is_macro and index <= 4))
                    else "false",
                }
            )
    return rows


def write_source_batch_packet(root: Path) -> None:
    source = root / BATCH_OUTPUT_DIR
    source.mkdir(parents=True, exist_ok=True)
    variant_rows = source_variant_rows()
    write_json(
        source / "revised_objective_sandbox_batch_manifest.json",
        {
            "sandbox_batch_run": True,
            "batch_id": BATCH_ID,
            "variant_count_planned": 80,
            "variant_count_evaluated": 80,
            "family_count_evaluated": 5,
            "sandbox_future_preregistration_candidate_count": 2,
            "families_actionable_count": 0,
            "sandbox_results_non_promotable": True,
            "sandbox_can_create_paper_candidates": False,
            "formal_discovery_run": False,
            "strategy_discovery_run": False,
            "candidate_exhaustive_run": False,
            "paper_forward_review": False,
            "paper_forward_activation": False,
            "provider_download": False,
            "intraday_data_used": False,
            "active_strategy_state_changed": False,
            "rejected_strategy_state_changed": False,
            "exact_rejected_variants_reopened": False,
            "intraday_research_remains_paused": True,
            "next_action": "audit_revised_objective_sandbox_batch_results",
        },
    )
    write_json(source / "revised_objective_sandbox_batch_consistency_check.json", {"consistency_passed": True})
    write_csv(
        source / "batch_002_variant_results.csv",
        variant_rows,
        [
            "variant_id",
            "family_id",
            "status",
            "promotable",
            "paper_candidate_allowed",
            "standalone_growth_score",
            "portfolio_contribution_score",
            "risk_integrity_score",
            "overfit_risk_score",
            "practicality_score",
            "avg_cash_allocation",
            "trade_count",
            "return_drag_penalty",
            "duplicate_penalty",
            "corr_vs_active_combo",
            "useful_contribution_evidence",
            "acceptable_drawdown_risk_integrity",
        ],
    )
    family_rows = [
        {
            "family_id": family_id,
            "family_status": status,
            "future_preregistration_candidate": "True" if status == "sandbox_future_preregistration_candidate" else "False",
            "median_standalone_growth_score": 100.0,
            "median_portfolio_contribution_score": 58.0,
            "median_risk_integrity_score": 0.0,
        }
        for family_id, _count, status in FAMILIES
    ]
    write_csv(
        source / "batch_002_family_summary.csv",
        family_rows,
        [
            "family_id",
            "family_status",
            "future_preregistration_candidate",
            "median_standalone_growth_score",
            "median_portfolio_contribution_score",
            "median_risk_integrity_score",
        ],
    )
    write_csv(
        source / "benchmark_comparison_summary.csv",
        [
            {
                "family_id": family_id,
                "benchmark_id": "active_combo",
                "median_correlation": 0.97 if family_id == "portfolio_combination_sleeve_ensemble" else 0.01,
                "median_delta_180d_median_final_equity": -100.0,
            }
            for family_id, _count, _status in FAMILIES
        ],
        ["family_id", "benchmark_id", "median_correlation", "median_delta_180d_median_final_equity"],
    )
    for name in BATCH_REQUIRED_FILES:
        path = source / name
        if path.exists():
            continue
        if name.endswith(".csv"):
            write_csv(path, [{"family_id": "placeholder"}], ["family_id"])
        elif name.endswith(".json"):
            write_json(path, {"consistency_passed": True})
        else:
            path.write_text(f"# {name}\n", encoding="utf-8")


def write_fixture(root: Path) -> None:
    registry = {
        "registry": {
            "schema_version": 1,
            "project": "trading_tournament",
            "research_only": True,
            "real_money_recommendation": False,
            "broker_integration": False,
            "live_orders": False,
            "current_next_action": "audit_revised_objective_sandbox_batch_results",
            "official_current_next_action": "audit_revised_objective_sandbox_batch_results",
            "intraday_research_remains_paused": True,
        },
        "strategies": [
            {"id": "paper_forward_vm_quality_lowvol_proxy_v1", "status": "active_paper_demo_observation"},
            {"id": "paper_forward_dsr_sector_equal_weight_defensive_filter_v1", "status": "active_paper_demo_observation"},
            {"id": "static_all_weather_benchmark_v1", "status": "benchmark_control"},
            {"id": "mfv_equal_weight_trend_filter_v1", "status": "discovery_reject", "paper_forward_active": False},
        ],
    }
    registry_path = root / config.REGISTRY_PATH
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")
    roadmap = root / config.ROADMAP_PATH
    roadmap.parent.mkdir(parents=True, exist_ok=True)
    roadmap.write_text(
        "# Research Roadmap\n\n## Compact Current State\n\n- Next action: `audit_revised_objective_sandbox_batch_results`\n",
        encoding="utf-8",
    )
    write_source_batch_packet(root)


@pytest.fixture(scope="module")
def audit_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    root = tmp_path_factory.mktemp("revised_objective_sandbox_batch_audit")
    write_fixture(root)
    before = yaml.safe_load((root / config.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result = audit.run_revised_objective_sandbox_batch_audit(root)
    after = yaml.safe_load((root / config.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result["root"] = root
    result["strategies_before"] = before
    result["strategies_after"] = after
    return result


def output(audit_run: dict[str, Any]) -> Path:
    return Path(audit_run["output_dir"])


def manifest(audit_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(audit_run) / "revised_objective_sandbox_batch_audit_manifest.json").read_text(encoding="utf-8"))


def consistency(audit_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads(
        (output(audit_run) / "revised_objective_sandbox_batch_audit_consistency_check.json").read_text(encoding="utf-8")
    )


def test_sandbox_batch_audit_only_mode(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["sandbox_batch_audit_only"] is True


def test_audited_batch_id(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["audited_batch_id"] == BATCH_ID


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


def test_no_new_variants_created(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["new_variants_created"] is False


def test_sandbox_results_unchanged(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["sandbox_results_changed"] is False


def test_variant_statuses_unchanged(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["variant_statuses_changed"] is False


def test_no_future_preregistration_candidates_created_by_audit(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["future_preregistration_candidates_created"] is False


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


def test_batch_consistency_review_exists(audit_run: dict[str, Any]) -> None:
    assert (output(audit_run) / "batch_consistency_review.md").exists()


def test_scoring_system_audit_exists(audit_run: dict[str, Any]) -> None:
    assert (output(audit_run) / "scoring_system_audit.md").exists()


def test_standalone_score_saturation_review_exists(audit_run: dict[str, Any]) -> None:
    assert (output(audit_run) / "standalone_score_saturation_review.md").exists()


def test_family_audit_exists(audit_run: dict[str, Any]) -> None:
    assert (output(audit_run) / "family_audit.md").exists()
    assert (output(audit_run) / "family_audit.csv").exists()


def test_future_preregistration_clue_review_exists(audit_run: dict[str, Any]) -> None:
    assert (output(audit_run) / "future_preregistration_clue_review.md").exists()


def test_risk_return_drag_review_exists(audit_run: dict[str, Any]) -> None:
    assert (output(audit_run) / "risk_and_return_drag_review.md").exists()


def test_overfit_duplicate_review_exists(audit_run: dict[str, Any]) -> None:
    assert (output(audit_run) / "overfit_and_duplicate_review.md").exists()


def test_next_action_is_valid(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["next_action"] in audit.VALID_NEXT_ACTIONS
    assert manifest(audit_run)["next_action"] == "fix_revised_objective_sandbox_scoring"


def test_manifest_flags_match_strict_scope(audit_run: dict[str, Any]) -> None:
    loaded = manifest(audit_run)
    for key, expected in audit.MANIFEST_FLAGS.items():
        assert loaded[key] == expected
    assert loaded["standalone_score_saturation_found"] is True
    assert loaded["scoring_fix_required"] is True
    assert consistency(audit_run)["consistency_passed"] is True
