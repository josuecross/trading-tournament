from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from strategy_lab.research_os.research import canonical_registry_write_side_effect_review_v1 as review


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "canonical_registry_write_side_effect_review_v1" / "latest"
REGISTRY = ROOT / "strategy_lab" / "strategy_registry.yaml"


@pytest.fixture(scope="module", autouse=True)
def generated_review() -> dict[str, object]:
    before = REGISTRY.read_bytes()
    result = review.run(ROOT)
    after = REGISTRY.read_bytes()
    assert after == before
    return result


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_required_evidence_files_exist() -> None:
    required = {
        "decision.json",
        "decision.md",
        "command_write_inventory.csv",
        "registry_hashes_before_after.csv",
        "registry_diffs.csv",
        "write_call_sites.csv",
        "patches_applied.csv",
        "idempotence_results.csv",
        "remaining_write_side_effects.csv",
        "consistency_check.json",
    }
    assert sorted(name for name in required if not (EVIDENCE / name).exists()) == []


def test_each_scoped_command_runs_twice_and_preserves_registry_hash() -> None:
    rows = read_csv(EVIDENCE / "idempotence_results.csv")
    assert {row["command"] for row in rows} == {name for name, _cmd in review.COMMANDS}
    assert all(row["run_count"] == "2" for row in rows)
    assert all(row["all_exit_zero"] == "True" for row in rows)
    assert all(row["all_registry_hashes_preserved"] == "True" for row in rows)
    assert all(row["second_run_registry_hash_preserved"] == "True" for row in rows)
    assert all(row["idempotent"] == "True" for row in rows)


def test_command_inventory_classifies_current_commands_as_read_only() -> None:
    rows = read_csv(EVIDENCE / "command_write_inventory.csv")
    assert all(row["registry_changed"] == "False" for row in rows)
    assert all(row["classification"] == "no_registry_write" for row in rows)
    assert any(row["command"] == "run_current_research_checkpoint" and row["patch_required"] == "True" for row in rows)


def test_root_cause_call_site_is_documented() -> None:
    rows = read_csv(EVIDENCE / "write_call_sites.csv")
    assert rows
    row = rows[0]
    assert row["command"] == "run_current_research_checkpoint"
    assert row["file"] == "run_current_research_checkpoint.py"
    assert "update_registry_metadata" in row["function_or_call_site"]
    assert row["classification"] == "derived_metadata_write"
    assert "current_research_checkpoint_path" in row["affected_fields"]


def test_checkpoint_outputs_metadata_view_not_registry_write() -> None:
    output = ROOT / "evidence" / "current_research_checkpoint" / "latest"
    manifest = read_json(output / "current_research_checkpoint_manifest.json")
    consistency = read_json(output / "current_research_checkpoint_consistency_check.json")
    view = read_json(output / "current_research_checkpoint_registry_metadata_view.json")
    assert manifest["canonical_registry_write"] is False
    assert consistency["canonical_registry_write"] is False
    assert consistency["registry_metadata_view_created"] is True
    assert view["current_research_checkpoint_path"].endswith("evidence\\current_research_checkpoint\\latest") or view["current_research_checkpoint_path"].endswith("evidence/current_research_checkpoint/latest")


def test_no_generated_artifact_replaces_canonical_registry() -> None:
    patches = read_csv(EVIDENCE / "patches_applied.csv")
    assert all(row["canonical_registry_write_after_patch"] == "False" for row in patches)
    assert all(row["migration_path_added"] == "False" for row in patches)
    assert (ROOT / "evidence" / "current_research_checkpoint" / "latest" / "current_research_checkpoint_registry_metadata_view.json").exists()
    assert REGISTRY.exists()


def test_remaining_side_effects_empty_and_consistency_passes() -> None:
    remaining = read_csv(EVIDENCE / "remaining_write_side_effects.csv")
    consistency = read_json(EVIDENCE / "consistency_check.json")
    assert remaining == []
    assert consistency["remaining_write_side_effect_count"] == 0
    assert consistency["no_remaining_write_side_effects"] is True
    assert consistency["final_registry_matches_initial_review_hash"] is True
    assert consistency["consistency_passed"] is True


def test_registry_status_and_paper_demo_guardrails_are_preserved() -> None:
    decision = read_json(EVIDENCE / "decision.json")
    assert decision["no_strategy_or_lifecycle_state_change"] is True
    assert decision["no_paper_demo_state_change"] is True
    assert decision["normal_commands_read_only_after_patch"] is True
    hashes = read_csv(EVIDENCE / "registry_hashes_before_after.csv")
    assert all(row["before_hash"] == row["after_hash"] for row in hashes)
