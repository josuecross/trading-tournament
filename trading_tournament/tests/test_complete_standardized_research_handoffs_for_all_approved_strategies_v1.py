from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from contracts.forward_observation.forward_observation_handoff_standard_v1.adapters import (
    StandardV1Adapter,
    normalized_spdj_package_hash,
)
from strategy_lab.research_os.research import (
    complete_standardized_research_handoffs_for_all_approved_strategies_v1 as task,
)


@pytest.fixture(scope="module")
def completed() -> dict[str, object]:
    return task.run()


def test_approved_inventory_is_exactly_eleven(completed: dict[str, object]) -> None:
    assert completed["approved_strategy_count"] == 11
    rows = list(
        csv.DictReader(
            (task.OUTPUT_DIR / "approved_strategy_inventory.csv").open(
                newline="", encoding="utf-8"
            )
        )
    )
    assert [row["strategy_id"] for row in rows] == list(task.APPROVED_IDS)
    assert len({row["strategy_id"] for row in rows}) == 11


def test_ten_additive_standard_specs_cover_non_spdj_cohort() -> None:
    specs = task.specs()
    assert len(specs) == 10
    assert {row.strategy_id for row in specs} == set(task.APPROVED_IDS[:-1])


@pytest.mark.parametrize("spec", task.specs(), ids=lambda row: row.strategy_id)
def test_rule_contracts_are_complete(spec: task.StrategySpec) -> None:
    task.validate_rule(spec)
    assert set(task.RULE_FIELDS).issubset(spec.rule)
    assert "unknown" not in json.dumps(spec.rule, sort_keys=True).lower()


@pytest.mark.parametrize("spec", task.specs(), ids=lambda row: row.strategy_id)
def test_golden_fixture_sets_are_deterministic_and_valid(spec: task.StrategySpec) -> None:
    first = task.build_fixtures(spec)
    second = task.build_fixtures(spec)
    assert first == second
    task.validate_fixture_set(spec, first)
    assert {row["fixture_type"] for row in first}.issubset(set(task.REQUIRED_FIXTURE_TYPES))
    assert all(row["historical_numeric_input"] is False for row in first)


@pytest.mark.parametrize("spec", task.specs(), ids=lambda row: row.strategy_id)
def test_standard_v1_packages_validate(
    completed: dict[str, object], spec: task.StrategySpec
) -> None:
    result = StandardV1Adapter().adapt(spec.package_path)
    assert result.status == "contract_validated"
    assert result.normalized_handoff is not None
    assert result.normalized_handoff.envelope.strategy_id == spec.strategy_id


def test_internal_capture_is_successor_and_legacy_is_preserved(
    completed: dict[str, object],
) -> None:
    spec = next(row for row in task.specs() if row.strategy_id == task.APPROVED_IDS[9])
    lineage = json.loads((spec.package_path / "source_lineage.json").read_text(encoding="utf-8"))
    assert lineage["parent_handoff"] == "evidence/handoff/internal_capture_asymmetry_63d_top3_v1/latest"
    consistency = json.loads((task.OUTPUT_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["checks"]["internal_legacy_package_preserved"] is True


def test_spdj_is_reused_with_original_hash(completed: dict[str, object]) -> None:
    assert normalized_spdj_package_hash(task.SPDJ_PACKAGE) == task.EXPECTED_SPDJ_HASH
    rows = list(
        csv.DictReader(
            (task.OUTPUT_DIR / "handoff_package_inventory.csv").open(
                newline="", encoding="utf-8"
            )
        )
    )
    spdj = next(row for row in rows if row["strategy_id"] == task.APPROVED_IDS[-1])
    assert spdj["handoff_status"] == "existing_standardized_handoff_reused"


def test_counts_and_completion_outcome(completed: dict[str, object]) -> None:
    counts = json.loads((task.OUTPUT_DIR / "standardization_counts.json").read_text(encoding="utf-8"))
    assert counts == {
        "approved_strategy_count": 11,
        "broker_network_calls": 0,
        "conformance_bundles_created": 0,
        "contract_complete_calculator_module_count": 10,
        "current_target_calculations": 0,
        "existing_complete_handoff_count_before": 1,
        "existing_handoffs_enriched": 1,
        "fixture_sets_created": 10,
        "forward_observation_accesses": 0,
        "human_interpretation_required_count": 0,
        "machine_executable_count": 1,
        "material_rule_gap_count": 0,
        "new_standardized_handoffs_created": 9,
        "standardized_handoff_ready_count_after": 11,
    }
    assert completed["outcome"] == task.OUTCOME
    assert completed["next_action"] == task.NEXT_ACTION


def test_no_material_rule_gaps(completed: dict[str, object]) -> None:
    gaps = list(
        csv.DictReader(
            (task.OUTPUT_DIR / "material_rule_gaps.csv").open(
                newline="", encoding="utf-8"
            )
        )
    )
    assert gaps == []


def test_no_current_target_or_forward_project_access(completed: dict[str, object]) -> None:
    consistency = json.loads((task.OUTPUT_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["current_target_calculations"] == 0
    assert consistency["forward_project_path_touched"] is False
    assert consistency["broker_network_calls"] == 0
    assert consistency["checks"]["forward_project_not_accessed"] is True


def test_completion_packet_hash_is_deterministic(completed: dict[str, object]) -> None:
    consistency = json.loads((task.OUTPUT_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    assert task.normalized_completion_hash(task.OUTPUT_DIR) == consistency[
        "deterministic_completion_packet_hash"
    ]
    assert completed["packet_hash"] == consistency["deterministic_completion_packet_hash"]


def test_no_absolute_paths_or_secret_material(completed: dict[str, object]) -> None:
    package_paths = [row.package_path for row in task.specs()]
    hygiene = task.scan_hygiene(package_paths + [task.OUTPUT_DIR])
    assert hygiene == {"secret_hits": [], "absolute_path_hits": [], "passed": True}


def test_required_completion_files_exist(completed: dict[str, object]) -> None:
    required = {
        "completion_report.md",
        "approved_strategy_inventory.csv",
        "rule_completeness_audit.csv",
        "handoff_readiness.csv",
        "handoff_package_inventory.csv",
        "fixture_coverage.csv",
        "machine_executability_audit.csv",
        "material_rule_gaps.csv",
        "standardization_counts.json",
        "consistency_check.json",
        "next_action.md",
    }
    assert required == {path.name for path in task.OUTPUT_DIR.iterdir() if path.is_file()}


def test_protected_state_reconciles(completed: dict[str, object]) -> None:
    consistency = json.loads((task.OUTPUT_DIR / "consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["protected_state_unchanged"] is True
    assert consistency["protected_state_before"] == consistency["protected_state_after"]
    assert consistency["overall_pass"] is True
