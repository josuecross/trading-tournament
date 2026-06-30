from __future__ import annotations

import csv
import json
import math
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml

from strategy_lab.research_os.exploratory_sandbox import sandbox_config as config
from strategy_lab.research_os.objective_reset import revised_objective_sandbox_batch as batch
from strategy_lab.research_os.objective_reset import revised_objective_sandbox_batch_v3_rerun as rerun
from strategy_lab.research_os.objective_reset.revised_objective_batch_config import (
    ALLOWED_RESULT_STATUSES,
    BATCH_ID,
    FORBIDDEN_STATUSES,
    INCLUDED_FAMILIES,
    MAX_TOTAL_VARIANTS,
)
from strategy_lab.research_os.objective_reset.revised_objective_sandbox_scoring_fix_v3_audit import (
    OUTPUT_DIR as SCORING_FIX_V3_AUDIT_DIR,
)


ALL_SYMBOLS = (
    "SPY",
    "QQQ",
    "IWM",
    "DIA",
    "XLK",
    "XLF",
    "XLV",
    "XLE",
    "XLI",
    "XLY",
    "XLP",
    "XLU",
    "XLB",
    "XLRE",
    "XLC",
    "GLD",
    "IEF",
    "TLT",
    "AGG",
    "BIL",
    "VLUE",
    "QUAL",
    "MTUM",
    "SPLV",
    "USMV",
    "DGRO",
    "SCHD",
    "VIG",
    "VTV",
    "SCHG",
)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_price_cache(root: Path) -> None:
    cache_dir = root / config.DATA_CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)
    start = date(2023, 1, 2)
    days: list[date] = []
    current = start
    while len(days) < 620:
        if current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)

    for symbol_index, symbol in enumerate(ALL_SYMBOLS):
        path = cache_dir / f"{symbol}.csv"
        price = 95.0 + symbol_index
        rows = ["date,close,adj_close\n"]
        for day_index, day in enumerate(days):
            drift = 0.00018 + ((symbol_index % 5) - 2) * 0.000015
            cycle = math.sin((day_index + symbol_index) / 31.0) * 0.0009
            defensive = -0.00005 if symbol in {"BIL", "IEF", "TLT", "AGG", "GLD"} else 0.00005
            price *= 1.0 + drift + cycle + defensive
            rows.append(f"{day.isoformat()},{price:.6f},{price:.6f}\n")
        path.write_text("".join(rows), encoding="utf-8")


def write_fixture(root: Path) -> None:
    registry = {
        "registry": {
            "schema_version": 1,
            "project": "trading_tournament",
            "research_only": True,
            "real_money_recommendation": False,
            "broker_integration": False,
            "live_orders": False,
            "current_next_action": "rerun_revised_objective_sandbox_batch_with_fixed_scoring",
            "official_current_next_action": "rerun_revised_objective_sandbox_batch_with_fixed_scoring",
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
                "id": "static_all_weather_benchmark_v1",
                "status": "benchmark_control",
                "paper_forward_active": False,
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
    roadmap.write_text(
        "# Research Roadmap\n\n## Compact Current State\n\n- Next action: `rerun_revised_objective_sandbox_batch_with_fixed_scoring`\n",
        encoding="utf-8",
    )

    approved = {
        "symbols": [
            {
                "symbol": symbol,
                "allowed_for_strategy": True,
                "allowed_for_benchmark": True,
            }
            for symbol in ALL_SYMBOLS
        ]
    }
    approved_path = root / config.APPROVED_SYMBOL_MAP_PATH
    approved_path.parent.mkdir(parents=True, exist_ok=True)
    approved_path.write_text(yaml.safe_dump(approved, sort_keys=False), encoding="utf-8")
    write_price_cache(root)

    prereg_dir = root / batch.PREREGISTRATION_DIR
    write_json(
        prereg_dir / "revised_objective_sandbox_preregistration_manifest.json",
        {
            "sandbox_preregistration_only": True,
            "planned_batch_id": BATCH_ID,
            "planned_max_variants": MAX_TOTAL_VARIANTS,
            "planned_family_count": 5,
            "next_action": "implement_revised_objective_sandbox_batch",
        },
    )
    v3_audit_dir = root / SCORING_FIX_V3_AUDIT_DIR
    write_json(
        v3_audit_dir / "scoring_fix_v3_audit_manifest.json",
        {
            "next_action": "rerun_revised_objective_sandbox_batch_with_fixed_scoring",
            "v3_calibration_accepted": True,
            "rerun_with_fixed_scoring_recommended": True,
        },
    )
    write_json(v3_audit_dir / "scoring_fix_v3_audit_consistency_check.json", {"consistency_passed": True})


@pytest.fixture(scope="module")
def rerun_result(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    root = tmp_path_factory.mktemp("revised_objective_sandbox_batch_v3_rerun")
    write_fixture(root)
    batch.run_revised_objective_sandbox_dry_run(root, update_project_metadata=False)
    before = yaml.safe_load((root / config.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result = rerun.run_revised_objective_sandbox_batch_v3_rerun(root, batch_id=BATCH_ID, max_variants=MAX_TOTAL_VARIANTS)
    after = yaml.safe_load((root / config.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result["root"] = root
    result["strategies_before"] = before
    result["strategies_after"] = after
    return result


def output(rerun_result: dict[str, Any]) -> Path:
    return Path(rerun_result["output_dir"])


def manifest(rerun_result: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(rerun_result) / "fixed_scoring_rerun_manifest.json").read_text(encoding="utf-8"))


def consistency(rerun_result: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(rerun_result) / "fixed_scoring_rerun_consistency_check.json").read_text(encoding="utf-8"))


def result_rows(rerun_result: dict[str, Any]) -> list[dict[str, str]]:
    with (output(rerun_result) / "batch_002_v3_variant_results.csv").open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_fixed_scoring_rerun_mode(rerun_result: dict[str, Any]) -> None:
    assert manifest(rerun_result)["fixed_scoring_rerun"] is True


def test_batch_id_is_revised_objective_batch(rerun_result: dict[str, Any]) -> None:
    assert manifest(rerun_result)["batch_id"] == BATCH_ID


def test_scoring_version_is_v3(rerun_result: dict[str, Any]) -> None:
    assert manifest(rerun_result)["scoring_version"] == "v3"


def test_no_unregistered_variants_created(rerun_result: dict[str, Any]) -> None:
    assert manifest(rerun_result)["new_unregistered_variants_created"] is False


def test_no_new_family_added(rerun_result: dict[str, Any]) -> None:
    assert manifest(rerun_result)["new_family_added"] is False


def test_formal_strategy_discovery_is_false(rerun_result: dict[str, Any]) -> None:
    loaded = manifest(rerun_result)
    assert loaded["formal_discovery_run"] is False
    assert loaded["strategy_discovery_run"] is False


def test_candidate_exhaustive_is_false(rerun_result: dict[str, Any]) -> None:
    assert manifest(rerun_result)["candidate_exhaustive_run"] is False


def test_paper_forward_action_is_false(rerun_result: dict[str, Any]) -> None:
    loaded = manifest(rerun_result)
    assert loaded["paper_forward_review"] is False
    assert loaded["paper_forward_activation"] is False


def test_provider_download_is_false(rerun_result: dict[str, Any]) -> None:
    assert manifest(rerun_result)["provider_download"] is False


def test_intraday_data_used_is_false(rerun_result: dict[str, Any]) -> None:
    assert manifest(rerun_result)["intraday_data_used"] is False


def test_indicator_library_dependency_added_is_false(rerun_result: dict[str, Any]) -> None:
    assert manifest(rerun_result)["indicator_library_dependency_added"] is False


def test_broker_live_action_is_false(rerun_result: dict[str, Any]) -> None:
    loaded = manifest(rerun_result)
    assert loaded["broker_orders_submitted"] is False
    assert loaded["broker_orders_cancelled"] is False
    assert loaded["live_orders"] is False


def test_real_money_recommendation_is_false(rerun_result: dict[str, Any]) -> None:
    assert manifest(rerun_result)["real_money_recommendation"] is False


def test_active_strategy_state_preserved(rerun_result: dict[str, Any]) -> None:
    assert manifest(rerun_result)["active_strategy_state_changed"] is False
    assert rerun_result["strategies_before"] == rerun_result["strategies_after"]


def test_rejected_strategy_state_preserved(rerun_result: dict[str, Any]) -> None:
    assert manifest(rerun_result)["rejected_strategy_state_changed"] is False
    assert rerun_result["strategies_before"] == rerun_result["strategies_after"]


def test_exact_rejected_variants_not_reopened(rerun_result: dict[str, Any]) -> None:
    assert manifest(rerun_result)["exact_rejected_variants_reopened"] is False


def test_intraday_remains_paused(rerun_result: dict[str, Any]) -> None:
    assert manifest(rerun_result)["intraday_research_remains_paused"] is True


def test_old_dollar_target_is_not_hard_gate(rerun_result: dict[str, Any]) -> None:
    assert manifest(rerun_result)["old_dollar_target_is_hard_gate"] is False


def test_stretch_diagnostics_are_not_promotion_gates(rerun_result: dict[str, Any]) -> None:
    assert manifest(rerun_result)["stretch_diagnostics_are_promotion_gates"] is False


def test_variant_count_planned_within_limit(rerun_result: dict[str, Any]) -> None:
    assert manifest(rerun_result)["variant_count_planned"] <= MAX_TOTAL_VARIANTS


def test_variant_count_evaluated_within_limit(rerun_result: dict[str, Any]) -> None:
    assert manifest(rerun_result)["variant_count_evaluated"] <= MAX_TOTAL_VARIANTS


def test_every_result_has_allowed_sandbox_status(rerun_result: dict[str, Any]) -> None:
    assert {row["status"] for row in result_rows(rerun_result)} <= set(ALLOWED_RESULT_STATUSES)


def test_forbidden_statuses_are_absent(rerun_result: dict[str, Any]) -> None:
    assert not ({row["status"] for row in result_rows(rerun_result)} & set(FORBIDDEN_STATUSES))


def test_no_result_is_promotable(rerun_result: dict[str, Any]) -> None:
    assert all(row["promotable"] == "false" for row in result_rows(rerun_result))


def test_no_result_can_create_paper_candidate(rerun_result: dict[str, Any]) -> None:
    assert all(row["paper_candidate_allowed"] == "false" for row in result_rows(rerun_result))


def test_v3_standalone_score_exists(rerun_result: dict[str, Any]) -> None:
    assert all("standalone_growth_score_v3" in row for row in result_rows(rerun_result))


def test_v3_contribution_score_exists(rerun_result: dict[str, Any]) -> None:
    assert all("portfolio_contribution_score_v3" in row for row in result_rows(rerun_result))


def test_v3_risk_score_exists(rerun_result: dict[str, Any]) -> None:
    assert all("risk_integrity_score_v3" in row for row in result_rows(rerun_result))


def test_v3_risk_gate_status_exists(rerun_result: dict[str, Any]) -> None:
    assert all("risk_gate_status_v3" in row for row in result_rows(rerun_result))


def test_v3_saturation_floor_flags_exist(rerun_result: dict[str, Any]) -> None:
    assert all("score_saturation_flag_v3" in row and "score_floor_collapse_flag_v3" in row for row in result_rows(rerun_result))


def test_family_summary_exists(rerun_result: dict[str, Any]) -> None:
    assert (output(rerun_result) / "batch_002_v3_family_summary.csv").exists()


def test_future_preregistration_candidates_file_exists(rerun_result: dict[str, Any]) -> None:
    assert (output(rerun_result) / "future_preregistration_candidates_v3.md").exists()


def test_do_not_promote_file_exists(rerun_result: dict[str, Any]) -> None:
    assert (output(rerun_result) / "do_not_promote_v3.md").exists()


def test_next_action_is_valid(rerun_result: dict[str, Any]) -> None:
    assert manifest(rerun_result)["next_action"] in rerun.VALID_NEXT_ACTIONS


def test_manifest_flags_match_strict_scope(rerun_result: dict[str, Any]) -> None:
    loaded = manifest(rerun_result)
    for key, expected in rerun.MANIFEST_FLAGS.items():
        assert loaded[key] == expected
    assert set(loaded["included_families"]) == set(INCLUDED_FAMILIES)
    assert loaded["v3_scoring_applied"] is True
    assert consistency(rerun_result)["consistency_passed"] is True
