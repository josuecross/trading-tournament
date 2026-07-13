from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
import yaml

import run_current_research_checkpoint as checkpoint


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def registry_row(row_id: str, active: bool, status: str, evidence_source: str = "test") -> dict[str, object]:
    return {
        "id": row_id,
        "status": status,
        "rules_frozen": active,
        "paper_forward_active": active,
        "evidence_source": evidence_source,
        "candidate_exhaustive_recommended": False,
        "promotion_review_required": False,
    }


def write_registry(root: Path) -> None:
    rows = [
        registry_row(checkpoint.VM_ID, True, "active_paper_demo_observation", "active_strategy_evidence_recompute"),
        registry_row(checkpoint.DSR_ID, True, "active_paper_demo_observation", "active_strategy_evidence_recompute"),
        registry_row(checkpoint.SPY_200D_ID, True, "active_observation", "focused_candidate_exhaustive_and_paper_forward"),
        registry_row(checkpoint.BIL_ID, True, "benchmark", "compact_challenge_and_paper_forward"),
        registry_row(checkpoint.LVQ_ID, False, "keep_watchlist", "lvq_promotion_review"),
    ]
    path = root / checkpoint.REGISTRY_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            {
                "registry": {"schema_version": 1, "project": "trading_tournament", "research_only": True, "real_money_recommendation": False, "broker_integration": False, "live_orders": False},
                "risk_framework": {"active_framework": "balanced_speculative_research_v1", "framework_path": "risk_framework/risk_framework.yaml"},
                "strategies": rows,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def write_state(root: Path) -> None:
    roadmap = root / checkpoint.ROADMAP_PATH
    roadmap.parent.mkdir(parents=True, exist_ok=True)
    roadmap.write_text("# Research Roadmap\n\nCurrent next action: `old_action`\n", encoding="utf-8")

    profit_rows = [
        {"strategy_id": checkpoint.VM_ID, "metric": "180d_median_final_equity", "value": "3328.0857", "horizon": "180", "notes": "test"},
        {"strategy_id": checkpoint.VM_ID, "metric": "target_300_before_stop_rate", "value": "0.6", "horizon": "180", "notes": "test"},
        {"strategy_id": checkpoint.VM_ID, "metric": "target_400_before_stop_rate", "value": "0.6", "horizon": "180", "notes": "test"},
        {"strategy_id": checkpoint.DSR_ID, "metric": "180d_median_final_equity", "value": "3403.0195", "horizon": "180", "notes": "test"},
        {"strategy_id": checkpoint.DSR_ID, "metric": "target_300_before_stop_rate", "value": "0.6", "horizon": "180", "notes": "test"},
        {"strategy_id": checkpoint.DSR_ID, "metric": "target_400_before_stop_rate", "value": "0.6", "horizon": "180", "notes": "test"},
    ]
    risk_rows = [
        {"strategy_id": checkpoint.VM_ID, "metric": "180d_worst_drawdown", "value": "-256.1641", "horizon": "180", "notes": "test"},
        {"strategy_id": checkpoint.VM_ID, "metric": "stop_hit_rate", "value": "0.0", "horizon": "180", "notes": "test"},
        {"strategy_id": checkpoint.DSR_ID, "metric": "180d_worst_drawdown", "value": "-498.9477", "horizon": "180", "notes": "test"},
        {"strategy_id": checkpoint.DSR_ID, "metric": "stop_hit_rate", "value": "0.0", "horizon": "180", "notes": "test"},
    ]
    fields = ["strategy_id", "metric", "value", "horizon", "notes"]
    write_csv(root / "evidence" / "active_strategy_evidence_recompute" / "latest" / "active_strategy_recompute_profit_review.csv", profit_rows, fields)
    write_csv(root / "evidence" / "active_strategy_evidence_recompute" / "latest" / "active_strategy_recompute_risk_review.csv", risk_rows, fields)

    lvq_rows = [
        {"metric": "180d_median_final_equity", "value": "3350.0801", "horizon": "180", "notes": "test"},
        {"metric": "target_300_before_stop_rate", "value": "0.6", "horizon": "180", "notes": "test"},
        {"metric": "target_400_before_stop_rate", "value": "0.4", "horizon": "180", "notes": "test"},
    ]
    lvq_risk = [
        {"metric": "180d_worst_drawdown", "value": "-221.4401", "horizon": "180", "notes": "test"},
        {"metric": "stop_hit_rate", "value": "0.0", "horizon": "180", "notes": "test"},
    ]
    write_csv(root / "evidence" / "promotion_reviews" / checkpoint.LVQ_ID / "latest" / f"{checkpoint.LVQ_ID}_profit_review.csv", lvq_rows, ["metric", "value", "horizon", "notes"])
    write_csv(root / "evidence" / "promotion_reviews" / checkpoint.LVQ_ID / "latest" / f"{checkpoint.LVQ_ID}_risk_review.csv", lvq_risk, ["metric", "value", "horizon", "notes"])

    expanded = root / "evidence" / "parallel_research_discovery" / "expanded_universe_batch_1" / "latest"
    expanded.mkdir(parents=True, exist_ok=True)
    (expanded / "expanded_universe_batch_1_manifest.json").write_text(json.dumps({"next_action": "continue_next_expanded_universe_discovery_batch_or_pause"}), encoding="utf-8")
    write_csv(expanded / "expanded_universe_batch_1_promotion_candidates.csv", [], ["strategy_id"])
    write_csv(root / "evidence" / "parallel_research_discovery" / "approved_cache_batch_2" / "latest" / "approved_cache_batch_2_promotion_candidates.csv", [], ["strategy_id"])
    write_csv(root / "evidence" / "parallel_research_discovery" / "approved_cache_batch_3" / "latest" / "approved_cache_batch_3_promotion_candidates.csv", [], ["strategy_id"])
    write_csv(expanded / "expanded_universe_batch_1_benchmark_delta.csv", [{"strategy_id": "x", "benchmark_id": "active_combo", "delta": "unavailable", "comparison_status": "unavailable"}], ["strategy_id", "benchmark_id", "delta", "comparison_status"])


def write_exact_active_combo_reconciliation(root: Path) -> None:
    base = root / checkpoint.ACTIVE_COMBO_RECONCILIATION_DIR
    base.mkdir(parents=True, exist_ok=True)
    (base / "active_combo_series_reconciliation.json").write_text(
        json.dumps(
            {
                "combo_id": checkpoint.COMBO_ID,
                "reconstructability_classification": "exactly_reconstructable",
                "checkpoint_combo_row_safe_to_restore": True,
                "series_reconstructed": True,
                "max_daily_exposure": 1.0,
                "weight_invariant_passed": True,
                "bil_remainder_passed": True,
                "date_alignment_passed": True,
            }
        ),
        encoding="utf-8",
    )
    (base / "reconciliation_consistency_check.json").write_text(json.dumps({"consistency_passed": True}), encoding="utf-8")
    write_csv(
        base / "combo_metric_summary.csv",
        [
            {"benchmark_id": checkpoint.COMBO_ID, "metric": "180d_median_final_equity", "value": "3373.0109", "horizon": "180", "notes": "test"},
            {"benchmark_id": checkpoint.COMBO_ID, "metric": "target_300_before_stop_rate", "value": "0.6", "horizon": "180", "notes": "test"},
            {"benchmark_id": checkpoint.COMBO_ID, "metric": "target_400_before_stop_rate", "value": "0.6", "horizon": "180", "notes": "test"},
            {"benchmark_id": checkpoint.COMBO_ID, "metric": "180d_worst_drawdown", "value": "-247.5385", "horizon": "180", "notes": "test"},
            {"benchmark_id": checkpoint.COMBO_ID, "metric": "stop_hit_rate", "value": "0.0", "horizon": "180", "notes": "test"},
        ],
        ["benchmark_id", "metric", "value", "horizon", "notes"],
    )


@pytest.fixture()
def synthetic_checkpoint(tmp_path: Path) -> dict[str, object]:
    write_registry(tmp_path)
    write_state(tmp_path)
    before = yaml.safe_load((tmp_path / checkpoint.REGISTRY_PATH).read_text(encoding="utf-8"))
    result = checkpoint.run_current_research_checkpoint(tmp_path)
    return {"root": tmp_path, "before": before, "result": result}


def test_no_strategy_runner_is_called(synthetic_checkpoint: dict[str, object]) -> None:
    manifest = json.loads((Path(synthetic_checkpoint["result"]["output_dir"]) / "current_research_checkpoint_manifest.json").read_text(encoding="utf-8"))
    assert manifest["strategy_discovery_run"] is False
    assert manifest["research_sample_run"] is False


def test_no_provider_download_is_called(synthetic_checkpoint: dict[str, object]) -> None:
    manifest = json.loads((Path(synthetic_checkpoint["result"]["output_dir"]) / "current_research_checkpoint_manifest.json").read_text(encoding="utf-8"))
    assert manifest["provider_download"] is False


def test_no_candidate_exhaustive_flag_is_created(synthetic_checkpoint: dict[str, object]) -> None:
    manifest = json.loads((Path(synthetic_checkpoint["result"]["output_dir"]) / "current_research_checkpoint_manifest.json").read_text(encoding="utf-8"))
    pipeline = {row["stage"]: row for row in csv.DictReader((Path(synthetic_checkpoint["result"]["output_dir"]) / "candidate_pipeline_status.csv").open(encoding="utf-8"))}
    assert manifest["candidate_exhaustive_run"] is False
    assert pipeline["candidate_exhaustive_queue"]["count"] == "0"


def test_no_paper_forward_active_flag_is_changed(synthetic_checkpoint: dict[str, object]) -> None:
    root = Path(synthetic_checkpoint["root"])
    before_rows = {row["id"]: row for row in synthetic_checkpoint["before"]["strategies"]}
    after_rows = {row["id"]: row for row in yaml.safe_load((root / checkpoint.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]}
    for sid in [checkpoint.VM_ID, checkpoint.DSR_ID]:
        assert after_rows[sid]["paper_forward_active"] == before_rows[sid]["paper_forward_active"]
        assert after_rows[sid]["rules_frozen"] == before_rows[sid]["rules_frozen"]


def test_no_real_money_recommendation_is_created(synthetic_checkpoint: dict[str, object]) -> None:
    root = Path(synthetic_checkpoint["root"])
    registry = yaml.safe_load((root / checkpoint.REGISTRY_PATH).read_text(encoding="utf-8"))
    assert registry["registry"]["no_real_money_recommendation"] is True
    assert json.loads((Path(synthetic_checkpoint["result"]["output_dir"]) / "current_research_checkpoint_manifest.json").read_text(encoding="utf-8"))["real_money_recommendation"] is False


def test_active_vm_and_active_dsr_are_represented(synthetic_checkpoint: dict[str, object]) -> None:
    rows = list(csv.DictReader((Path(synthetic_checkpoint["result"]["output_dir"]) / "current_best_strategy_set.csv").open(encoding="utf-8")))
    ids = {row["strategy_id"] for row in rows}
    assert checkpoint.VM_ID in ids
    assert checkpoint.DSR_ID in ids


def test_candidate_pipeline_is_empty(synthetic_checkpoint: dict[str, object]) -> None:
    rows = {row["stage"]: row for row in csv.DictReader((Path(synthetic_checkpoint["result"]["output_dir"]) / "candidate_pipeline_status.csv").open(encoding="utf-8"))}
    assert rows["promotion_review_candidates"]["count"] == "0"
    assert rows["candidate_exhaustive_queue"]["count"] == "0"


def test_saturated_lanes_are_represented(synthetic_checkpoint: dict[str, object]) -> None:
    rows = list(csv.DictReader((Path(synthetic_checkpoint["result"]["output_dir"]) / "saturated_lanes.csv").open(encoding="utf-8")))
    families = {row["family"] for row in rows}
    assert "regional_international_momentum" in families
    assert "quality_value_momentum_blend" in families


def test_accepted_dsr_caveat_is_recorded(synthetic_checkpoint: dict[str, object]) -> None:
    text = (Path(synthetic_checkpoint["result"]["output_dir"]) / "accepted_caveats.md").read_text(encoding="utf-8")
    assert "4071.04" in text
    assert "3481.6998" in text
    assert "unverified_non_comparable" in text
    assert "reproducible_diagnostic_only" in text
    assert "not activation performance" in text
    assert "eligible_E4=`false`" in text


def test_active_combo_repair_is_recommended(synthetic_checkpoint: dict[str, object]) -> None:
    text = (Path(synthetic_checkpoint["result"]["output_dir"]) / "recommended_engineering_next_steps.md").read_text(encoding="utf-8")
    assert checkpoint.NEXT_ENGINEERING_ACTION in text


def test_active_combo_row_is_included_after_exact_reconciliation(tmp_path: Path) -> None:
    write_registry(tmp_path)
    write_state(tmp_path)
    write_exact_active_combo_reconciliation(tmp_path)
    result = checkpoint.run_current_research_checkpoint(tmp_path)
    output = Path(result["output_dir"])
    best = list(csv.DictReader((output / "current_best_strategy_set.csv").open(encoding="utf-8")))
    ids = {row["strategy_id"] for row in best}
    assert {checkpoint.VM_ID, checkpoint.DSR_ID, checkpoint.SPY_200D_ID, checkpoint.BIL_ID, checkpoint.LVQ_ID} <= ids
    combo_row = next(row for row in best if row["strategy_id"] == checkpoint.COMBO_ID)
    assert combo_row["role"] == "reconstructed_benchmark_reference"
    assert combo_row["recommended_action"] == "compare_only"
    pipeline = {row["stage"]: row for row in csv.DictReader((output / "candidate_pipeline_status.csv").open(encoding="utf-8"))}
    assert "data_pending" not in pipeline
    assert pipeline["benchmark_reference_available"]["rows"] == checkpoint.COMBO_ID
    caveats = (output / "accepted_caveats.md").read_text(encoding="utf-8")
    assert "Active Combo Benchmark Restored" in caveats
    assert "Active Combo Unavailable" not in caveats


def test_consistency_check_passes(synthetic_checkpoint: dict[str, object]) -> None:
    consistency = json.loads((Path(synthetic_checkpoint["result"]["output_dir"]) / "current_research_checkpoint_consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["consistency_passed"] is True
