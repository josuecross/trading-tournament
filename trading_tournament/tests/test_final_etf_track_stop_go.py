from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest
import yaml

import run_final_etf_track_stop_go as stopgo


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def registry_row(strategy_id: str, active_flag: bool) -> dict[str, object]:
    return {
        "id": strategy_id,
        "display_name": strategy_id,
        "lane": "paper_forward" if active_flag else "profit_exploration",
        "instrument_family": "ETF",
        "strategy_family": "test",
        "version": "v1",
        "parent_id": "",
        "credibility_tier": "tier4_paper_forward" if active_flag else "tier2_exploratory",
        "status": "active_observation" if active_flag else "benchmark_watchlist",
        "role": "test",
        "rules_frozen": True,
        "paper_forward_active": active_flag,
        "implementation_status": "implemented" if active_flag else "implemented_research_sample",
        "data_source": "existing_adjusted_etf_cache",
        "evidence_source": "test",
        "latest_evidence_path": "evidence/test/latest",
        "latest_known_result_summary": "test",
        "allowed_next_action": "observe_only" if active_flag else "research_sample_review",
        "forbidden_next_actions": ["run_candidate_exhaustive", "promote_to_real_money"],
        "risk_framework_status": "paper_forward_allowed" if active_flag else "research_sample_only",
        "paper_forward_allowed_by_risk_framework": active_flag,
        "real_money_recommendation": False,
        "promotion_blockers": "none",
        "promotion_requirements": "none",
        "demotion_or_kill_criteria": "none",
        "notes": "test",
        "strategy_id": strategy_id,
        "family": "test",
        "instrument_lane": "ETF",
        "evidence_tier": "test",
        "current_status": "active_observation" if active_flag else "benchmark_watchlist",
        "allowed_next_actions": ["observe_only"] if active_flag else ["research_sample_review"],
        "candidate_exhaustive_run": False,
        "candidate_exhaustive_recommended": False,
        "promotion_review_required": False,
        "promotion_decision": "keep_active_observation" if active_flag else "benchmark_watchlist",
        "promotion_reason": "test",
        "primary_failure_mode": "not_flagged",
        "duplication_risk": "not_flagged",
        "risk_budget_status": "test",
        "evidence_needed": "none",
        "duplicate_of": "",
        "blocked_reason": "",
    }


def write_registry(root: Path) -> None:
    path = root / stopgo.REGISTRY_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        registry_row(stopgo.VM_ID, True),
        registry_row(stopgo.DSR_ID, True),
        registry_row(stopgo.SPY_200D_ID, True),
        registry_row(stopgo.ENSEMBLE_EQUAL_WEIGHT_ID, False),
    ]
    path.write_text(
        yaml.safe_dump(
            {
                "registry": {
                    "schema_version": 1,
                    "project": "trading_tournament",
                    "research_only": True,
                    "real_money_recommendation": False,
                    "broker_integration": False,
                    "live_orders": False,
                    "etf_discovery_status": "paused",
                },
                "risk_framework": {"active_framework": "balanced_speculative_research_v1", "framework_path": "risk_framework/risk_framework.yaml"},
                "strategies": rows,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def write_active_observations(root: Path) -> None:
    for strategy_id, rel_path in stopgo.ACTIVE_OBSERVATION_PATHS.items():
        path = root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump({"strategy_id": strategy_id, "paper_forward_active": True, "frozen": True}, sort_keys=False), encoding="utf-8")


def write_evidence(root: Path) -> None:
    write_csv(
        root / "evidence" / "current_research_checkpoint" / "latest" / "candidate_pipeline_status.csv",
        [
            {"stage": "active_frozen", "count": 2, "rows": f"{stopgo.VM_ID};{stopgo.DSR_ID}", "status": "protected", "next_action": "observe_only"},
            {"stage": "promotion_review_candidates", "count": 0, "rows": "", "status": "empty", "next_action": "none"},
            {"stage": "candidate_exhaustive_queue", "count": 0, "rows": "", "status": "empty", "next_action": "none"},
            {"stage": "candidate_exhaustive_watchlist", "count": 0, "rows": "", "status": "empty", "next_action": "none"},
            {"stage": "paper_forward_active", "count": 2, "rows": f"{stopgo.VM_ID};{stopgo.DSR_ID}", "status": "no_new_action", "next_action": "observe_only"},
        ],
        ["stage", "count", "rows", "status", "next_action"],
    )
    write_json(
        root / "evidence" / "active_combo_benchmark" / "latest" / "active_combo_manifest.json",
        {
            "benchmark_id": stopgo.ACTIVE_COMBO_ID,
            "active_combo_benchmark_created": True,
            "active_combo_is_reference_not_active_strategy": True,
            "candidate_exhaustive_run": False,
            "paper_forward_activation": False,
            "provider_download": False,
            "real_money_recommendation": False,
            "next_action": "pre_register_active_sleeve_ensemble_lane",
        },
    )
    write_json(
        root / "evidence" / "pre_registered_lanes" / "active_sleeve_ensemble" / "latest" / "active_sleeve_ensemble_manifest.json",
        {"lane_status": "pre_registered_not_run", "next_action": "run_active_sleeve_ensemble_discovery_batch"},
    )
    ensemble_dir = root / "evidence" / "parallel_research_discovery" / "active_sleeve_ensemble" / "latest"
    write_json(
        ensemble_dir / "active_sleeve_ensemble_discovery_manifest.json",
        {
            "decisions": {
                "ase_vm_dsr_equal_weight_v1": "benchmark_watchlist",
                "ase_dsr_tilt_60_40_v1": "duplicate_or_near_duplicate",
            },
            "next_action": "keep_active_sleeve_ensemble_as_benchmark_watchlist",
            "candidate_exhaustive_run": False,
            "paper_forward_activation": False,
            "provider_download": False,
            "real_money_recommendation": False,
        },
    )
    write_csv(
        ensemble_dir / "active_sleeve_ensemble_promotion_candidates.csv",
        [],
        ["strategy_id", "decision", "promotion_review_required"],
    )
    for rel in [
        "evidence/parallel_research_discovery/expanded_universe_batch_1/latest",
        "evidence/parallel_research_discovery/approved_cache_batch_3/latest",
        "evidence/parallel_research_discovery/approved_cache_batch_2/latest",
        "evidence/parallel_research_discovery/new_batch_approved_cache/latest",
        "evidence/promotion_reviews/qvm_quality_value_momentum_risk_adjusted_top2_v1/latest",
        "evidence/promotion_reviews/lvq_lowvol_quality_spy_regime_v1/latest",
        "evidence/promotion_reviews/dsr_sector_top2_momentum_200d_bil_v1/latest",
        "evidence/promotion_reviews/dsr_sector_top3_momentum_defensive_cash_v1/latest",
        "evidence/research_state/latest",
        "evidence/strategy_lab/latest",
    ]:
        (root / rel).mkdir(parents=True, exist_ok=True)


def write_roadmap(root: Path) -> None:
    path = root / stopgo.ROADMAP_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# Research Roadmap\n\nCurrent next action: `keep_active_sleeve_ensemble_as_benchmark_watchlist`\n", encoding="utf-8")


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture()
def synthetic_stop_go(tmp_path: Path) -> dict[str, object]:
    write_registry(tmp_path)
    write_active_observations(tmp_path)
    write_evidence(tmp_path)
    write_roadmap(tmp_path)
    obs_before = {sid: file_hash(tmp_path / rel_path) for sid, rel_path in stopgo.ACTIVE_OBSERVATION_PATHS.items()}
    registry_before = yaml.safe_load((tmp_path / stopgo.REGISTRY_PATH).read_text(encoding="utf-8"))
    result = stopgo.run_final_etf_track_stop_go(tmp_path)
    obs_after = {sid: file_hash(tmp_path / rel_path) for sid, rel_path in stopgo.ACTIVE_OBSERVATION_PATHS.items()}
    registry_after = yaml.safe_load((tmp_path / stopgo.REGISTRY_PATH).read_text(encoding="utf-8"))
    return {
        "root": tmp_path,
        "result": result,
        "obs_before": obs_before,
        "obs_after": obs_after,
        "registry_before": registry_before,
        "registry_after": registry_after,
    }


def output_path(synthetic_stop_go: dict[str, object]) -> Path:
    return Path(synthetic_stop_go["result"]["output_dir"])


def test_no_strategy_runner_is_called(synthetic_stop_go: dict[str, object]) -> None:
    manifest = json.loads((output_path(synthetic_stop_go) / "final_etf_track_stop_go_manifest.json").read_text(encoding="utf-8"))
    assert manifest["strategy_runner_called"] is False
    assert manifest["strategy_discovery_run"] is False


def test_no_provider_download_is_called(synthetic_stop_go: dict[str, object]) -> None:
    manifest = json.loads((output_path(synthetic_stop_go) / "final_etf_track_stop_go_manifest.json").read_text(encoding="utf-8"))
    assert manifest["provider_download"] is False


def test_no_candidate_exhaustive_flag_is_created(synthetic_stop_go: dict[str, object]) -> None:
    registry = synthetic_stop_go["registry_after"]
    assert registry["registry"]["no_candidate_exhaustive_run"] is True
    assert all(row.get("candidate_exhaustive_run") is False for row in registry["strategies"])


def test_no_paper_forward_active_flag_is_changed(synthetic_stop_go: dict[str, object]) -> None:
    before = {row["id"]: row["paper_forward_active"] for row in synthetic_stop_go["registry_before"]["strategies"]}
    after = {row["id"]: row["paper_forward_active"] for row in synthetic_stop_go["registry_after"]["strategies"]}
    assert before == after
    assert synthetic_stop_go["obs_before"] == synthetic_stop_go["obs_after"]


def test_no_real_money_recommendation_is_created(synthetic_stop_go: dict[str, object]) -> None:
    registry = synthetic_stop_go["registry_after"]
    assert registry["registry"]["no_real_money_recommendation"] is True
    assert registry["registry"]["real_money_recommendation"] is False


def test_active_sleeve_ensemble_result_is_represented(synthetic_stop_go: dict[str, object]) -> None:
    rows = list(csv.DictReader((output_path(synthetic_stop_go) / "evidence_since_checkpoint.csv").open(encoding="utf-8")))
    assert "active_sleeve_ensemble_discovery_batch" in {row["artifact"] for row in rows}


def test_candidate_pipeline_is_empty(synthetic_stop_go: dict[str, object]) -> None:
    rows = list(csv.DictReader((output_path(synthetic_stop_go) / "final_candidate_pipeline_status.csv").open(encoding="utf-8")))
    by_stage = {row["stage"]: row for row in rows}
    assert by_stage["candidate_exhaustive_queue"]["count"] == "0"
    assert by_stage["surviving_promotion_candidates"]["count"] == "0"


def test_stop_go_decision_is_explicit(synthetic_stop_go: dict[str, object]) -> None:
    text = (output_path(synthetic_stop_go) / "final_etf_track_decision.md").read_text(encoding="utf-8")
    assert stopgo.FINAL_DECISION in text


def test_recommended_final_next_action_is_explicit(synthetic_stop_go: dict[str, object]) -> None:
    text = (output_path(synthetic_stop_go) / "recommended_final_next_action.md").read_text(encoding="utf-8")
    assert stopgo.NEXT_ACTION in text


def test_consistency_check_passes(synthetic_stop_go: dict[str, object]) -> None:
    consistency = json.loads((output_path(synthetic_stop_go) / "final_etf_track_stop_go_consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["consistency_passed"] is True
