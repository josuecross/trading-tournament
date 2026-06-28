from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest
import yaml

import run_active_sleeve_ensemble_preregistration as prereg


def write_registry(root: Path) -> None:
    rows = []
    for strategy_id in [prereg.VM_ID, prereg.DSR_ID]:
        rows.append(
            {
                "id": strategy_id,
                "rules_frozen": True,
                "paper_forward_active": True,
                "real_money_recommendation": False,
            }
        )
    path = root / prereg.REGISTRY_PATH
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
                "strategies": rows,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def write_checkpoint(root: Path) -> None:
    checkpoint = root / "evidence" / "current_research_checkpoint" / "latest"
    checkpoint.mkdir(parents=True, exist_ok=True)
    with (checkpoint / "candidate_pipeline_status.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["stage", "count", "rows", "status", "next_action"], lineterminator="\n")
        writer.writeheader()
        writer.writerows(
            [
                {"stage": "promotion_review_candidates", "count": 0, "rows": "", "status": "empty", "next_action": "none"},
                {"stage": "candidate_exhaustive_queue", "count": 0, "rows": "", "status": "empty", "next_action": "none"},
            ]
        )


def write_active_combo(root: Path) -> None:
    combo = root / "evidence" / "active_combo_benchmark" / "latest"
    combo.mkdir(parents=True, exist_ok=True)
    (combo / "active_combo_manifest.json").write_text(
        json.dumps(
            {
                "benchmark_id": prereg.ACTIVE_COMBO_ID,
                "active_combo_is_reference_not_active_strategy": True,
                "next_action": "pre_register_active_sleeve_ensemble_lane",
            }
        ),
        encoding="utf-8",
    )


def write_active_observations(root: Path) -> None:
    for strategy_id in [prereg.VM_ID, prereg.DSR_ID]:
        path = root / "paper_forward_observations" / strategy_id / "active_observation.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump({"strategy_id": strategy_id, "paper_forward_active": True, "frozen": True}, sort_keys=False), encoding="utf-8")


def write_roadmap(root: Path) -> None:
    path = root / prereg.ROADMAP_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# Research Roadmap\n\n## Current Research Checkpoint\n\nETF-wrapper discovery is paused.\n", encoding="utf-8")


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture()
def synthetic_prereg(tmp_path: Path) -> dict[str, object]:
    write_registry(tmp_path)
    write_checkpoint(tmp_path)
    write_active_combo(tmp_path)
    write_active_observations(tmp_path)
    write_roadmap(tmp_path)
    obs_paths = prereg.active_observation_paths(tmp_path)
    before = {sid: file_hash(path) for sid, path in obs_paths.items()}
    result = prereg.run_active_sleeve_ensemble_preregistration(tmp_path, strict_state=True)
    after = {sid: file_hash(path) for sid, path in obs_paths.items()}
    return {"root": tmp_path, "result": result, "before": before, "after": after}


def test_lane_is_pre_registered_but_not_run(synthetic_prereg: dict[str, object]) -> None:
    manifest = json.loads((Path(synthetic_prereg["result"]["output_dir"]) / "active_sleeve_ensemble_manifest.json").read_text(encoding="utf-8"))
    assert manifest["lane_status"] == "pre_registered_not_run"
    assert manifest["strategy_discovery_run"] is False


def test_future_rows_are_fixed_before_any_results(synthetic_prereg: dict[str, object]) -> None:
    rows = list(csv.DictReader((Path(synthetic_prereg["result"]["output_dir"]) / "active_sleeve_ensemble_future_rows.csv").open(encoding="utf-8")))
    assert [row["row_id"] for row in rows] == [row["row_id"] for row in prereg.FUTURE_ROWS]
    assert len(rows) == 6


def test_only_vm_dsr_bil_and_spy200d_inputs_are_used(synthetic_prereg: dict[str, object]) -> None:
    rows = list(csv.DictReader((Path(synthetic_prereg["result"]["output_dir"]) / "active_sleeve_ensemble_future_rows.csv").open(encoding="utf-8")))
    allowed = {prereg.VM_ID, prereg.DSR_ID, prereg.BIL_ID, prereg.SPY_200D_ID}
    for row in rows:
        assert set(row["allowed_inputs"].split(";")) == allowed


def test_lvq_is_not_included_as_first_pass_active_ensemble_sleeve(synthetic_prereg: dict[str, object]) -> None:
    definition = yaml.safe_load((Path(synthetic_prereg["result"]["output_dir"]) / "active_sleeve_ensemble_lane_definition.yaml").read_text(encoding="utf-8"))
    assert "lvq_lowvol_quality_spy_regime_v1" not in definition["sleeves_allowed"]
    assert "lvq_lowvol_quality_spy_regime_v1" in definition["excluded_first_pass_sleeves"]


def test_no_strategy_metrics_are_computed(synthetic_prereg: dict[str, object]) -> None:
    output = Path(synthetic_prereg["result"]["output_dir"])
    assert not (output / "active_sleeve_ensemble_metrics.csv").exists()
    assert json.loads((output / "active_sleeve_ensemble_manifest.json").read_text(encoding="utf-8"))["strategy_metrics_computed"] is False


def test_no_research_sample_is_run(synthetic_prereg: dict[str, object]) -> None:
    manifest = json.loads((Path(synthetic_prereg["result"]["output_dir"]) / "active_sleeve_ensemble_manifest.json").read_text(encoding="utf-8"))
    assert manifest["research_sample_run"] is False


def test_no_candidate_exhaustive_flag_is_created(synthetic_prereg: dict[str, object]) -> None:
    manifest = json.loads((Path(synthetic_prereg["result"]["output_dir"]) / "active_sleeve_ensemble_manifest.json").read_text(encoding="utf-8"))
    assert manifest["candidate_exhaustive_run"] is False


def test_no_paper_forward_active_flag_is_set(synthetic_prereg: dict[str, object]) -> None:
    rows = list(csv.DictReader((Path(synthetic_prereg["result"]["output_dir"]) / "active_sleeve_ensemble_future_rows.csv").open(encoding="utf-8")))
    assert all(row["paper_forward_active"] == "False" for row in rows)


def test_no_real_money_recommendation_is_created(synthetic_prereg: dict[str, object]) -> None:
    manifest = json.loads((Path(synthetic_prereg["result"]["output_dir"]) / "active_sleeve_ensemble_manifest.json").read_text(encoding="utf-8"))
    assert manifest["real_money_recommendation"] is False


def test_active_observation_files_are_not_mutated(synthetic_prereg: dict[str, object]) -> None:
    assert synthetic_prereg["before"] == synthetic_prereg["after"]


def test_next_action_is_explicit(synthetic_prereg: dict[str, object]) -> None:
    text = (Path(synthetic_prereg["result"]["output_dir"]) / "active_sleeve_ensemble_next_action.md").read_text(encoding="utf-8")
    assert synthetic_prereg["result"]["next_action"] == prereg.NEXT_ACTION_SUCCESS
    assert prereg.NEXT_ACTION_SUCCESS in text


def test_consistency_check_passes(synthetic_prereg: dict[str, object]) -> None:
    consistency = json.loads((Path(synthetic_prereg["result"]["output_dir"]) / "active_sleeve_ensemble_consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["consistency_passed"] is True
