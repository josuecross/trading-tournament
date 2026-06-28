from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

import run_active_strategy_evidence_recompute as active
import run_first_expansion_discovery_preregistration as first_prereg
import run_sector_rs_limited_history_preregistration as prereg


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_context(root: Path) -> None:
    first_batch = root / first_prereg.OUTPUT_DIR / "first_expansion_discovery_batch.yaml"
    first_batch.parent.mkdir(parents=True, exist_ok=True)
    first_batch.write_text(
        yaml.safe_dump(
            {
                "metadata": {"included_candidate_ids": [prereg.CANDIDATE_ID]},
                "candidates": [
                    {
                        "candidate_id": prereg.CANDIDATE_ID,
                        "family": "sector_relative_strength_rotation",
                        "timeframe": "weekly",
                        "universe": prereg.SECTOR_UNIVERSE,
                        "entry_rule": "At weekly rebalance, rank sectors by fixed 13-week momentum using prior completed data only.",
                        "exit_rule": "At weekly rebalance, exit failed sectors.",
                        "sizing_rule": "Allocate 50% to each accepted sector.",
                        "risk_controls": ["Max 2 sectors.", "Weekly rebalance only."],
                        "benchmark_controls": ["active DSR", "active combo", "SPY_200d"],
                        "acceptance_criteria": ["future discovery only"],
                        "rejection_criteria": ["weak evidence"],
                        "duplication_checks": ["active DSR", "active combo"],
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    write_csv(
        root / prereg.MANUAL_PERIOD_REVIEW_DIR / "first_expansion_candidate_period_compatibility.csv",
        [
            {
                "candidate_id": prereg.CANDIDATE_ID,
                "required_symbols": ";".join(prereg.SECTOR_UNIVERSE),
                "earliest_required_symbol_start_date": "2007-01-03",
                "effective_all_symbols_start_date": "2015-10-08",
                "common_last_date": "2026-06-18",
                "common_history_years": "10.69",
                "full_2007_style_period_supported": "False",
                "blocked_by_xlre": "True",
                "xlre_in_universe": "True",
                "cache_missing": "False",
                "issue_classification": "period_inception_limitation",
                "can_proceed_without_changing_frozen_rules": "False",
                "requires_separate_limited_history_batch": "True",
                "comparability_vs_active_vm_affected": "True",
                "comparability_vs_active_dsr_affected": "True",
                "comparability_vs_active_combo_affected": "True",
                "comparability_vs_spy_200d_affected": "True",
                "recommended_handling": "defer_to_limited_history_preregistration",
            }
        ],
        [
            "candidate_id",
            "required_symbols",
            "earliest_required_symbol_start_date",
            "effective_all_symbols_start_date",
            "common_last_date",
            "common_history_years",
            "full_2007_style_period_supported",
            "blocked_by_xlre",
            "xlre_in_universe",
            "cache_missing",
            "issue_classification",
            "can_proceed_without_changing_frozen_rules",
            "requires_separate_limited_history_batch",
            "comparability_vs_active_vm_affected",
            "comparability_vs_active_dsr_affected",
            "comparability_vs_active_combo_affected",
            "comparability_vs_spy_200d_affected",
            "recommended_handling",
        ],
    )
    write_csv(
        root / prereg.FIRST_EXPANSION_DISCOVERY_DIR / "first_expansion_candidate_results.csv",
        [{"candidate_id": candidate_id, "discovery_outcome": "discovery_reject"} for candidate_id in prereg.FIRST_EXPANSION_REJECT_IDS],
        ["candidate_id", "discovery_outcome"],
    )
    registry = root / prereg.EXPANSION_REGISTRY_PATH
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry.write_text(
        yaml.safe_dump(
            {
                "metadata": {
                    "artifact": "strategy_expansion_candidates_v1",
                    "etf_wrapper_track_status": "archived_after_breadth_state_regime_no_candidate",
                    "provider_download": False,
                },
                "candidates": [],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    roadmap = root / prereg.EXPANSION_ROADMAP_PATH
    roadmap.parent.mkdir(parents=True, exist_ok=True)
    roadmap.write_text("# Strategy Expansion Roadmap\n", encoding="utf-8")
    for strategy_id, path in active.active_observation_paths(root).items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump({"strategy_id": strategy_id, "paper_forward_active": True}), encoding="utf-8")


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def prereg_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    root = tmp_path_factory.mktemp("sector_rs_limited_history")
    write_context(root)
    before = {sid: file_hash(path) for sid, path in active.active_observation_paths(root).items()}
    result = prereg.run_sector_rs_limited_history_preregistration(root)
    after = {sid: file_hash(path) for sid, path in active.active_observation_paths(root).items()}
    return {"root": root, "result": result, "before": before, "after": after}


def output_path(prereg_run: dict[str, object]) -> Path:
    return Path(prereg_run["result"]["output_dir"])


def manifest(prereg_run: dict[str, object]) -> dict[str, Any]:
    return json.loads((output_path(prereg_run) / "sector_rs_limited_history_manifest.json").read_text(encoding="utf-8"))


def batch(prereg_run: dict[str, object]) -> dict[str, Any]:
    return yaml.safe_load((output_path(prereg_run) / "sector_rs_limited_history_batch.yaml").read_text(encoding="utf-8"))


def consistency(prereg_run: dict[str, object]) -> dict[str, Any]:
    return json.loads((output_path(prereg_run) / "sector_rs_limited_history_consistency_check.json").read_text(encoding="utf-8"))


def test_only_sector_rs_is_included(prereg_run: dict[str, object]) -> None:
    assert manifest(prereg_run)["included_candidate_ids"] == [prereg.CANDIDATE_ID]
    assert batch(prereg_run)["metadata"]["included_candidate_ids"] == [prereg.CANDIDATE_ID]


def test_limited_history_flag_is_present(prereg_run: dict[str, object]) -> None:
    assert manifest(prereg_run)["limited_history_due_to_xlre_inception"] is True
    assert batch(prereg_run)["candidates"][0]["limited_history_label"] == prereg.LIMITED_HISTORY_LABEL


def test_xlre_inception_issue_is_recorded(prereg_run: dict[str, object]) -> None:
    loaded = manifest(prereg_run)
    assert loaded["xlre_first_available_date"] == "2015-10-08"
    assert loaded["methodology"] == prereg.METHODOLOGY


def test_xlre_is_not_removed_or_substituted(prereg_run: dict[str, object]) -> None:
    universe = batch(prereg_run)["candidates"][0]["universe"]
    assert universe == prereg.SECTOR_UNIVERSE
    assert "XLRE" in universe


def test_frozen_rules_are_not_changed(prereg_run: dict[str, object]) -> None:
    assert manifest(prereg_run)["frozen_rules_changed"] is False
    assert consistency(prereg_run)["consistency_passed"] is True


def test_candidate_universe_is_unchanged(prereg_run: dict[str, object]) -> None:
    assert manifest(prereg_run)["candidate_universe_changed"] is False


def test_benchmarks_are_same_window_limited_history(prereg_run: dict[str, object]) -> None:
    candidate = batch(prereg_run)["candidates"][0]
    assert manifest(prereg_run)["benchmarks_changed"] is False
    assert candidate["same_window_benchmark_recompute_required"] is True
    assert all("same limited-history window" in item for item in candidate["benchmark_plan"])


def test_pre_registration_only_is_true(prereg_run: dict[str, object]) -> None:
    assert manifest(prereg_run)["pre_registration_only"] is True


def test_no_backtest_or_discovery_was_run(prereg_run: dict[str, object]) -> None:
    loaded = manifest(prereg_run)
    assert loaded["backtests_run"] is False
    assert loaded["discovery_run"] is False


def test_no_performance_metrics_were_computed(prereg_run: dict[str, object]) -> None:
    assert manifest(prereg_run)["performance_metrics_computed"] is False


def test_no_provider_download_occurred(prereg_run: dict[str, object]) -> None:
    assert manifest(prereg_run)["provider_download"] is False


def test_no_candidate_exhaustive_or_paper_forward_action(prereg_run: dict[str, object]) -> None:
    loaded = manifest(prereg_run)
    assert loaded["candidate_exhaustive_run"] is False
    assert loaded["paper_forward_review"] is False
    assert loaded["paper_forward_activation"] is False


def test_no_broker_or_live_path_is_touched(prereg_run: dict[str, object]) -> None:
    loaded = manifest(prereg_run)
    assert loaded["broker_path_touched"] is False
    assert loaded["live_orders"] is False


def test_valid_future_outcomes_are_limited(prereg_run: dict[str, object]) -> None:
    assert manifest(prereg_run)["valid_future_outcomes"] == prereg.VALID_FUTURE_OUTCOMES
    assert batch(prereg_run)["metadata"]["valid_future_outcomes"] == prereg.VALID_FUTURE_OUTCOMES


def test_next_action_is_discovery_batch(prereg_run: dict[str, object]) -> None:
    assert manifest(prereg_run)["next_action"] == prereg.NEXT_ACTION


def test_first_expansion_rejected_candidates_remain_rejected(prereg_run: dict[str, object]) -> None:
    status = consistency(prereg_run)["first_expansion_reject_status"]
    assert set(status) == set(prereg.FIRST_EXPANSION_REJECT_IDS)
    assert all(value == "discovery_reject" for value in status.values())


def test_no_intraday_or_event_candidate_is_included(prereg_run: dict[str, object]) -> None:
    included = set(manifest(prereg_run)["included_candidate_ids"])
    assert included.isdisjoint(prereg.INTRADAY_CANDIDATE_IDS)
    assert included.isdisjoint(prereg.EVENT_DATA_CANDIDATE_IDS)


def test_active_observations_unchanged(prereg_run: dict[str, object]) -> None:
    assert prereg_run["before"] == prereg_run["after"]


def test_required_output_files_exist(prereg_run: dict[str, object]) -> None:
    expected = {
        "sector_rs_limited_history_manifest.json",
        "sector_rs_limited_history_batch.yaml",
        "sector_rs_limited_history_candidate_spec.md",
        "sector_rs_limited_history_methodology.md",
        "sector_rs_limited_history_benchmark_plan.md",
        "sector_rs_limited_history_acceptance_gates.md",
        "sector_rs_limited_history_rejection_gates.md",
        "sector_rs_limited_history_data_requirements.md",
        "sector_rs_limited_history_do_not_run_now.md",
        "sector_rs_limited_history_next_action.md",
        "sector_rs_limited_history_consistency_check.json",
    }
    assert expected.issubset({path.name for path in output_path(prereg_run).iterdir()})
