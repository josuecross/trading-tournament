from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

import run_active_combo_benchmark_reporting as combo
import run_active_strategy_evidence_recompute as active
import run_strategy_lab


def write_price_cache(root: Path, symbol: str, periods: int = 620, drift: float = 0.0002) -> None:
    dates = pd.bdate_range("2021-01-01", periods=periods)
    prices = [50.0 + len(symbol)]
    for idx in range(1, periods):
        prices.append(prices[-1] * (1 + drift + 0.0002 * ((idx % 9) - 4)))
    target = root / "data" / "cache" / f"{symbol}.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"date": dates, "adj_close": prices, "close": prices}).to_csv(target, index=False)


def write_required_cache(root: Path) -> None:
    for idx, symbol in enumerate(active.REQUIRED_CACHE_SYMBOLS + active.OPTIONAL_BENCHMARK_SYMBOLS):
        write_price_cache(root, symbol, drift=0.00006 + idx * 0.000006)


def registry_row(row_id: str, active_flag: bool, stale_candidate: bool = False, stale_promotion: bool = False) -> dict[str, object]:
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
        "candidate_exhaustive_recommended": stale_candidate,
        "promotion_review_required": stale_promotion,
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
        registry_row("gror_balanced_momentum_60_40_v1", False, stale_candidate=True),
        registry_row("qvm_quality_value_momentum_top2_v1", False, stale_promotion=True),
    ]
    path = root / combo.REGISTRY_PATH
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
        json.dumps(
            {
                "active_combo_available": False,
                "stale_candidate_exhaustive_flags": ["gror_balanced_momentum_60_40_v1"],
                "stale_promotion_review_flags": ["qvm_quality_value_momentum_top2_v1"],
            }
        ),
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


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture()
def synthetic_combo(tmp_path: Path) -> dict[str, object]:
    write_registry(tmp_path)
    write_checkpoint(tmp_path)
    write_active_observations(tmp_path)
    write_required_cache(tmp_path)
    obs_paths = active.active_observation_paths(tmp_path)
    before = {sid: file_hash(path) for sid, path in obs_paths.items()}
    result = combo.run_active_combo_benchmark_reporting(tmp_path, strict_state=True)
    after = {sid: file_hash(path) for sid, path in obs_paths.items()}
    return {"root": tmp_path, "result": result, "before_hashes": before, "after_hashes": after}


def test_active_combo_definition_is_50_50_vm_dsr_by_default(synthetic_combo: dict[str, object]) -> None:
    definition = yaml.safe_load((Path(synthetic_combo["result"]["output_dir"]) / "active_combo_benchmark_definition.yaml").read_text(encoding="utf-8"))
    assert definition["benchmark_id"] == combo.COMBO_ID
    assert {row["strategy_id"]: row["allocation"] for row in definition["sleeves"]} == {active.VM_ID: 0.5, active.DSR_ID: 0.5}


def test_active_combo_is_reference_not_active_paper_forward_strategy(synthetic_combo: dict[str, object]) -> None:
    manifest = json.loads((Path(synthetic_combo["result"]["output_dir"]) / "active_combo_manifest.json").read_text(encoding="utf-8"))
    assert manifest["active_combo_is_reference_not_active_strategy"] is True
    assert manifest["paper_forward_activation"] is False


def test_active_combo_equity_series_is_created_from_cached_data(synthetic_combo: dict[str, object]) -> None:
    rows = list(csv.DictReader((Path(synthetic_combo["result"]["output_dir"]) / "active_combo_equity_series.csv").open(encoding="utf-8")))
    assert rows
    assert float(rows[-1]["active_combo_equity"]) > 0


def test_unavailable_comparisons_are_not_zero_filled(synthetic_combo: dict[str, object]) -> None:
    missing = (Path(synthetic_combo["result"]["output_dir"]) / "active_combo_missing_evidence.md").read_text(encoding="utf-8")
    deltas = list(csv.DictReader((Path(synthetic_combo["result"]["output_dir"]) / "active_combo_benchmark_delta_reference.csv").open(encoding="utf-8")))
    assert "not be zero-filled" in missing
    assert all(row["comparison_status"] == "computed" and row["delta"] not in {"", "0"} for row in deltas)


def test_active_observation_files_are_not_mutated(synthetic_combo: dict[str, object]) -> None:
    assert synthetic_combo["before_hashes"] == synthetic_combo["after_hashes"]
    assert synthetic_combo["result"]["consistency"]["active_observations_unchanged"] is True


def test_no_candidate_exhaustive_is_run(synthetic_combo: dict[str, object]) -> None:
    manifest = json.loads((Path(synthetic_combo["result"]["output_dir"]) / "active_combo_manifest.json").read_text(encoding="utf-8"))
    assert manifest["candidate_exhaustive_run"] is False


def test_no_paper_forward_checkpoint_is_run(synthetic_combo: dict[str, object]) -> None:
    manifest = json.loads((Path(synthetic_combo["result"]["output_dir"]) / "active_combo_manifest.json").read_text(encoding="utf-8"))
    assert manifest["paper_forward_checkpoint"] is False


def test_no_provider_download_is_called(synthetic_combo: dict[str, object]) -> None:
    manifest = json.loads((Path(synthetic_combo["result"]["output_dir"]) / "active_combo_manifest.json").read_text(encoding="utf-8"))
    assert manifest["provider_download"] is False


def test_stale_registry_flags_are_detected(synthetic_combo: dict[str, object]) -> None:
    rows = list(csv.DictReader((Path(synthetic_combo["result"]["output_dir"]) / "registry_stale_flag_audit.csv").open(encoding="utf-8")))
    assert {"gror_balanced_momentum_60_40_v1", "qvm_quality_value_momentum_top2_v1"} <= {row["strategy_id"] for row in rows}


def test_stale_historical_flags_do_not_create_current_permission(synthetic_combo: dict[str, object]) -> None:
    root = Path(synthetic_combo["root"])
    registry = yaml.safe_load((root / combo.REGISTRY_PATH).read_text(encoding="utf-8"))
    stale_rows = [row for row in registry["strategies"] if row["id"] in {"gror_balanced_momentum_60_40_v1", "qvm_quality_value_momentum_top2_v1"}]
    assert all(row["current_candidate_exhaustive_permission"] is False for row in stale_rows)
    assert all(row["current_promotion_review_permission"] is False for row in stale_rows)


def test_weaker_than_active_references_watchlist_is_allowed() -> None:
    assert combo.WEAKER_LABEL in run_strategy_lab.ALLOWED_STATUSES


def test_next_action_is_explicit(synthetic_combo: dict[str, object]) -> None:
    next_action = (Path(synthetic_combo["result"]["output_dir"]) / "active_combo_next_action.md").read_text(encoding="utf-8")
    assert synthetic_combo["result"]["next_action"] in next_action
    assert synthetic_combo["result"]["next_action"] == combo.NEXT_ACTION_SUCCESS


def test_consistency_check_passes(synthetic_combo: dict[str, object]) -> None:
    consistency = json.loads((Path(synthetic_combo["result"]["output_dir"]) / "active_combo_consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["consistency_passed"] is True
