from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest
import yaml

import run_breadth_state_regime_preregistration as bsr


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
    rows = [
        registry_row(bsr.VM_ID, True),
        registry_row(bsr.DSR_ID, True),
        registry_row(bsr.SPY_200D_ID, True),
    ]
    path = root / bsr.REGISTRY_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
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
    for strategy_id, rel_path in bsr.ACTIVE_OBSERVATION_PATHS.items():
        path = root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump({"strategy_id": strategy_id, "paper_forward_active": True, "frozen": True}, sort_keys=False), encoding="utf-8")


def write_approved_policy_and_map(root: Path) -> None:
    policy = root / bsr.APPROVED_POLICY_PATH
    policy.parent.mkdir(parents=True, exist_ok=True)
    policy.write_text("# Approved ETF Cache Policy\n\nNo provider download during audit-only mode.\n", encoding="utf-8")
    symbols = [{"symbol": symbol, "allowed_for_strategy": True, "cache_ready": True} for symbol in sorted(bsr.referenced_symbols())]
    (root / bsr.APPROVED_SYMBOL_MAP_PATH).write_text(
        yaml.safe_dump({"symbols": symbols}, sort_keys=False),
        encoding="utf-8",
    )


def write_state_evidence(root: Path) -> None:
    write_json(
        root / "evidence" / "final_etf_track_stop_go" / "latest" / "final_etf_track_stop_go_consistency_check.json",
        {"consistency_passed": True},
    )
    decision = root / "evidence" / "final_etf_track_stop_go" / "latest" / "final_etf_track_decision.md"
    decision.parent.mkdir(parents=True, exist_ok=True)
    decision.write_text(f"`{bsr.FINAL_DECISION}`\n", encoding="utf-8")
    (decision.parent / "recommended_final_next_action.md").write_text(f"`{bsr.REQUIRED_PREVIOUS_NEXT_ACTION}`\n", encoding="utf-8")
    write_csv(
        decision.parent / "final_candidate_pipeline_status.csv",
        [
            {"stage": "surviving_promotion_candidates", "count": 0, "rows": "", "status": "empty", "notes": ""},
            {"stage": "candidate_exhaustive_queue", "count": 0, "rows": "", "status": "empty", "notes": ""},
            {"stage": "paper_forward_new_actions", "count": 0, "rows": "", "status": "empty", "notes": ""},
        ],
        ["stage", "count", "rows", "status", "notes"],
    )
    write_json(
        root / "evidence" / "active_combo_benchmark" / "latest" / "active_combo_manifest.json",
        {"benchmark_id": bsr.ACTIVE_COMBO_ID, "active_combo_is_reference_not_active_strategy": True},
    )
    for rel in [
        "evidence/current_research_checkpoint/latest",
        "evidence/parallel_research_discovery/active_sleeve_ensemble/latest",
        "evidence/research_state/latest",
        "evidence/strategy_lab/latest",
    ]:
        (root / rel).mkdir(parents=True, exist_ok=True)


def write_roadmap(root: Path) -> None:
    path = root / bsr.ROADMAP_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# Research Roadmap\n\nCurrent next action: `pre_register_breadth_state_regime_lane`\n", encoding="utf-8")


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture()
def synthetic_prereg(tmp_path: Path) -> dict[str, object]:
    write_registry(tmp_path)
    write_active_observations(tmp_path)
    write_approved_policy_and_map(tmp_path)
    write_state_evidence(tmp_path)
    write_roadmap(tmp_path)
    before = {sid: file_hash(tmp_path / rel_path) for sid, rel_path in bsr.ACTIVE_OBSERVATION_PATHS.items()}
    result = bsr.run_breadth_state_regime_preregistration(tmp_path, strict_state=True)
    after = {sid: file_hash(tmp_path / rel_path) for sid, rel_path in bsr.ACTIVE_OBSERVATION_PATHS.items()}
    return {"root": tmp_path, "result": result, "before": before, "after": after}


def output_path(synthetic_prereg: dict[str, object]) -> Path:
    return Path(synthetic_prereg["result"]["output_dir"])


def future_rows(synthetic_prereg: dict[str, object]) -> list[dict[str, str]]:
    return list(csv.DictReader((output_path(synthetic_prereg) / "breadth_state_regime_future_rows.csv").open(encoding="utf-8")))


def test_lane_is_pre_registered_but_not_run(synthetic_prereg: dict[str, object]) -> None:
    manifest = json.loads((output_path(synthetic_prereg) / "breadth_state_regime_manifest.json").read_text(encoding="utf-8"))
    assert manifest["lane_id"] == bsr.LANE_ID
    assert manifest["lane_status"] == bsr.LANE_STATUS
    assert manifest["strategy_discovery_run"] is False


def test_future_rows_are_fixed_before_any_results(synthetic_prereg: dict[str, object]) -> None:
    assert [row["row_id"] for row in future_rows(synthetic_prereg)] == [row["row_id"] for row in bsr.FUTURE_ROWS]


def test_breadth_state_thresholds_are_fixed(synthetic_prereg: dict[str, object]) -> None:
    text = (output_path(synthetic_prereg) / "breadth_state_regime_state_definitions.md").read_text(encoding="utf-8")
    assert "risk_breadth_count >= 8" in text
    assert "between 5 and 7 inclusive" in text
    assert "risk_breadth_count <= 4" in text


def test_no_threshold_variants_are_created(synthetic_prereg: dict[str, object]) -> None:
    rows = future_rows(synthetic_prereg)
    thresholds = {row["risk_breadth_thresholds"] for row in rows}
    assert len(thresholds) == 1
    assert len(rows) == 4


def test_only_approved_cache_ready_symbols_or_active_sleeves_are_referenced(synthetic_prereg: dict[str, object]) -> None:
    approved = bsr.approved_symbols(Path(synthetic_prereg["root"]))
    for row in future_rows(synthetic_prereg):
        symbols = set(row["allowed_symbols"].split(";"))
        assert symbols <= approved
        active_sleeves = set(filter(None, row["active_sleeves_allowed"].split(";")))
        assert active_sleeves <= set(bsr.ACTIVE_SLEEVE_IDS)


def test_deferred_symbols_are_not_used(synthetic_prereg: dict[str, object]) -> None:
    for row in future_rows(synthetic_prereg):
        assert set(row["allowed_symbols"].split(";")).isdisjoint(bsr.DEFERRED_SYMBOLS)


def test_no_strategy_metrics_are_computed(synthetic_prereg: dict[str, object]) -> None:
    manifest = json.loads((output_path(synthetic_prereg) / "breadth_state_regime_manifest.json").read_text(encoding="utf-8"))
    assert manifest["strategy_metrics_computed"] is False
    assert manifest["performance_computation_run"] is False


def test_no_research_sample_is_run(synthetic_prereg: dict[str, object]) -> None:
    manifest = json.loads((output_path(synthetic_prereg) / "breadth_state_regime_manifest.json").read_text(encoding="utf-8"))
    assert manifest["research_sample_run"] is False


def test_no_candidate_exhaustive_flag_is_created(synthetic_prereg: dict[str, object]) -> None:
    manifest = json.loads((output_path(synthetic_prereg) / "breadth_state_regime_manifest.json").read_text(encoding="utf-8"))
    assert manifest["candidate_exhaustive_run"] is False


def test_no_paper_forward_active_flag_is_set(synthetic_prereg: dict[str, object]) -> None:
    assert all(row["paper_forward_active"] == "False" for row in future_rows(synthetic_prereg))


def test_no_real_money_recommendation_is_created(synthetic_prereg: dict[str, object]) -> None:
    manifest = json.loads((output_path(synthetic_prereg) / "breadth_state_regime_manifest.json").read_text(encoding="utf-8"))
    assert manifest["real_money_recommendation"] is False


def test_active_observation_files_are_not_mutated(synthetic_prereg: dict[str, object]) -> None:
    assert synthetic_prereg["before"] == synthetic_prereg["after"]


def test_stop_condition_is_recorded(synthetic_prereg: dict[str, object]) -> None:
    risk_policy = (output_path(synthetic_prereg) / "breadth_state_regime_risk_policy.md").read_text(encoding="utf-8")
    assert "produces no promotion-review candidate" in risk_policy
    assert "archived/stopped" in risk_policy


def test_next_action_is_explicit(synthetic_prereg: dict[str, object]) -> None:
    text = (output_path(synthetic_prereg) / "breadth_state_regime_next_action.md").read_text(encoding="utf-8")
    assert bsr.NEXT_ACTION_SUCCESS in text


def test_consistency_check_passes(synthetic_prereg: dict[str, object]) -> None:
    consistency = json.loads((output_path(synthetic_prereg) / "breadth_state_regime_consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["consistency_passed"] is True
