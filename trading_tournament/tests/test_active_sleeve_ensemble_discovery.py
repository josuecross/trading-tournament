from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

import run_active_combo_benchmark_reporting as combo
import run_active_sleeve_ensemble_discovery as discovery
import run_active_sleeve_ensemble_preregistration as prereg
import run_active_strategy_evidence_recompute as active


def write_price_cache(root: Path, symbol: str, periods: int = 620, drift: float = 0.00018) -> None:
    dates = pd.bdate_range("2021-01-01", periods=periods)
    prices = [50.0 + len(symbol)]
    for idx in range(1, periods):
        wave = 0.00035 * ((idx % 11) - 5)
        prices.append(prices[-1] * (1 + drift + wave))
    target = root / "data" / "cache" / f"{symbol}.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"date": dates, "adj_close": prices, "close": prices}).to_csv(target, index=False)


def write_required_cache(root: Path) -> None:
    for idx, symbol in enumerate(active.REQUIRED_CACHE_SYMBOLS + active.OPTIONAL_BENCHMARK_SYMBOLS):
        write_price_cache(root, symbol, drift=0.00008 + idx * 0.000008)


def registry_row(row_id: str, active_flag: bool) -> dict[str, object]:
    return {
        "id": row_id,
        "display_name": row_id,
        "lane": "paper_forward" if active_flag else "profit_exploration",
        "instrument_family": "ETF",
        "strategy_family": "test_family",
        "version": "v1",
        "parent_id": "",
        "credibility_tier": "tier4_paper_forward" if active_flag else "tier2_exploratory",
        "status": "active_paper_demo_observation" if active_flag else "keep_watchlist",
        "role": "test",
        "rules_frozen": active_flag,
        "frozen": active_flag,
        "paper_forward_active": active_flag,
        "implementation_status": "implemented" if active_flag else "implemented_research_sample",
        "data_source": "existing_adjusted_etf_cache",
        "evidence_source": "test",
        "latest_evidence_path": "evidence/test/latest",
        "latest_known_result_summary": "test",
        "allowed_next_action": "observe_only" if active_flag else "research_sample_review",
        "forbidden_next_actions": ["promote_to_real_money", "run_candidate_exhaustive"],
        "risk_framework_status": "paper_forward_allowed" if active_flag else "research_sample_only",
        "paper_forward_allowed_by_risk_framework": active_flag,
        "real_money_recommendation": False,
        "promotion_blockers": "none",
        "promotion_requirements": "none",
        "demotion_or_kill_criteria": "none",
        "notes": "test",
        "strategy_id": row_id,
        "family": "test_family",
        "instrument_lane": "ETF",
        "evidence_tier": "test",
        "current_status": "active_paper_demo_observation" if active_flag else "keep_watchlist",
        "allowed_next_actions": ["observe_only"] if active_flag else ["research_sample_review"],
        "candidate_exhaustive_run": False,
        "candidate_exhaustive_recommended": False,
        "promotion_review_required": False,
        "promotion_decision": "keep_active_observation" if active_flag else "keep_watchlist",
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
        registry_row(active.VM_ID, True),
        registry_row(active.DSR_ID, True),
        registry_row(active.SPY_200D_ID, True),
    ]
    path = root / discovery.REGISTRY_PATH
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
                    "current_research_checkpoint_path": str(root / "evidence" / "current_research_checkpoint" / "latest"),
                },
                "risk_framework": {"active_framework": "balanced_speculative_research_v1", "framework_path": "risk_framework/risk_framework.yaml"},
                "strategies": rows,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def write_checkpoint(root: Path) -> None:
    checkpoint = root / "evidence" / "current_research_checkpoint" / "latest"
    checkpoint.mkdir(parents=True, exist_ok=True)
    (checkpoint / "current_research_checkpoint_manifest.json").write_text(
        json.dumps({"stale_candidate_exhaustive_flags": [], "stale_promotion_review_flags": []}),
        encoding="utf-8",
    )
    with (checkpoint / "candidate_pipeline_status.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["stage", "count", "rows", "status", "next_action"], lineterminator="\n")
        writer.writeheader()
        writer.writerows(
            [
                {"stage": "active_frozen", "count": 2, "rows": f"{active.VM_ID};{active.DSR_ID}", "status": "protected", "next_action": "observe_only"},
                {"stage": "promotion_review_candidates", "count": 0, "rows": "", "status": "empty", "next_action": "none"},
                {"stage": "candidate_exhaustive_queue", "count": 0, "rows": "", "status": "empty", "next_action": "none"},
                {"stage": "paper_forward_active", "count": 2, "rows": f"{active.VM_ID};{active.DSR_ID}", "status": "protected", "next_action": "observe_only"},
            ]
        )


def write_active_observations(root: Path) -> None:
    for strategy_id in [active.VM_ID, active.DSR_ID]:
        path = root / "paper_forward_observations" / strategy_id / "active_observation.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump({"strategy_id": strategy_id, "paper_forward_active": True, "frozen": True}, sort_keys=False), encoding="utf-8")


def write_roadmap(root: Path) -> None:
    path = root / discovery.ROADMAP_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# Research Roadmap\n\nCurrent next action: `create_managed_futures_etf_wrapper_fast_exploration_review_prompt`\n",
        encoding="utf-8",
    )


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def synthetic_discovery(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    tmp_path = tmp_path_factory.mktemp("active_sleeve_ensemble")
    write_registry(tmp_path)
    write_checkpoint(tmp_path)
    write_active_observations(tmp_path)
    write_roadmap(tmp_path)
    write_required_cache(tmp_path)
    combo.run_active_combo_benchmark_reporting(tmp_path, strict_state=True)
    prereg.run_active_sleeve_ensemble_preregistration(tmp_path, strict_state=True)
    write_roadmap(tmp_path)
    obs_paths = active.active_observation_paths(tmp_path)
    before = {sid: file_hash(path) for sid, path in obs_paths.items()}
    result = discovery.run_active_sleeve_ensemble_discovery(tmp_path, strict_state=True)
    after = {sid: file_hash(path) for sid, path in obs_paths.items()}
    return {"root": tmp_path, "result": result, "before": before, "after": after}


def output_path(synthetic_discovery: dict[str, object]) -> Path:
    return Path(synthetic_discovery["result"]["output_dir"])


def test_only_six_preregistered_rows_are_run(synthetic_discovery: dict[str, object]) -> None:
    rows = list(csv.DictReader((output_path(synthetic_discovery) / "active_sleeve_ensemble_results.csv").open(encoding="utf-8")))
    assert [row["strategy_id"] for row in rows] == discovery.ENSEMBLE_ROWS


def test_no_extra_ensemble_rows_are_added(synthetic_discovery: dict[str, object]) -> None:
    manifest = json.loads((output_path(synthetic_discovery) / "active_sleeve_ensemble_discovery_manifest.json").read_text(encoding="utf-8"))
    assert manifest["rows_tested"] == discovery.ENSEMBLE_ROWS
    assert len(manifest["rows_tested"]) == 6


def test_equal_weight_matches_active_combo_benchmark_definition(synthetic_discovery: dict[str, object]) -> None:
    deltas = list(csv.DictReader((output_path(synthetic_discovery) / "active_sleeve_ensemble_benchmark_delta.csv").open(encoding="utf-8")))
    row = next(item for item in deltas if item["strategy_id"] == "ase_vm_dsr_equal_weight_v1" and item["reference_id"] == combo.COMBO_ID)
    assert row["comparison_status"] == "computed"
    assert abs(float(row["delta"])) < 0.0001


def test_active_combo_is_used_as_benchmark_reference(synthetic_discovery: dict[str, object]) -> None:
    manifest = json.loads((output_path(synthetic_discovery) / "active_sleeve_ensemble_discovery_manifest.json").read_text(encoding="utf-8"))
    assert combo.COMBO_ID in manifest["reference_ids"]


def test_no_candidate_exhaustive_is_run(synthetic_discovery: dict[str, object]) -> None:
    manifest = json.loads((output_path(synthetic_discovery) / "active_sleeve_ensemble_discovery_manifest.json").read_text(encoding="utf-8"))
    assert manifest["candidate_exhaustive_run"] is False


def test_no_paper_forward_active_flag_is_set(synthetic_discovery: dict[str, object]) -> None:
    root = Path(synthetic_discovery["root"])
    registry = yaml.safe_load((root / discovery.REGISTRY_PATH).read_text(encoding="utf-8"))
    rows = [row for row in registry["strategies"] if row["id"] in discovery.ENSEMBLE_ROWS]
    assert rows
    assert all(row["paper_forward_active"] is False for row in rows)


def test_no_real_money_recommendation_is_created(synthetic_discovery: dict[str, object]) -> None:
    root = Path(synthetic_discovery["root"])
    registry = yaml.safe_load((root / discovery.REGISTRY_PATH).read_text(encoding="utf-8"))
    rows = [row for row in registry["strategies"] if row["id"] in discovery.ENSEMBLE_ROWS]
    assert all(row["real_money_recommendation"] is False for row in rows)


def test_active_observation_files_are_not_mutated(synthetic_discovery: dict[str, object]) -> None:
    assert synthetic_discovery["before"] == synthetic_discovery["after"]
    assert synthetic_discovery["result"]["consistency"]["active_observations_unchanged"] is True


def test_unavailable_benchmark_comparisons_are_not_zero_filled(synthetic_discovery: dict[str, object]) -> None:
    rows = list(csv.DictReader((output_path(synthetic_discovery) / "active_sleeve_ensemble_benchmark_delta.csv").open(encoding="utf-8")))
    unavailable = [row for row in rows if row["comparison_status"] == "unavailable"]
    assert all(row["delta"] == "unavailable" for row in unavailable)
    assert all(row["delta"] != "" for row in rows if row["comparison_status"] == "computed")


def test_next_action_is_explicit(synthetic_discovery: dict[str, object]) -> None:
    text = (output_path(synthetic_discovery) / "active_sleeve_ensemble_next_action.md").read_text(encoding="utf-8")
    assert synthetic_discovery["result"]["next_action"] in text
    assert synthetic_discovery["result"]["next_action"] in {
        discovery.NEXT_ACTION_PROMOTION,
        discovery.NEXT_ACTION_WATCHLIST,
        discovery.NEXT_ACTION_ARCHIVE,
        discovery.NEXT_ACTION_REPAIR,
    }


def test_roadmap_current_next_action_inconsistency_is_resolved(synthetic_discovery: dict[str, object]) -> None:
    root = Path(synthetic_discovery["root"])
    roadmap = (root / discovery.ROADMAP_PATH).read_text(encoding="utf-8")
    assert f"Current next action: `{discovery.NEXT_ACTION_RUN}`" in roadmap
    assert synthetic_discovery["result"]["roadmap_status"]["roadmap_next_action_consistent"] is True


def test_consistency_check_passes(synthetic_discovery: dict[str, object]) -> None:
    consistency = json.loads((output_path(synthetic_discovery) / "active_sleeve_ensemble_consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["consistency_passed"] is True
