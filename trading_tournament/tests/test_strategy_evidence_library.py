from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import yaml

from strategy_lab.research_os.strategy_evidence_library.builder import (
    EVIDENCE_LEVELS,
    FAILURE_CODES,
    LIFECYCLE_STATUSES,
    evidence_chain,
    level_rank,
)
from strategy_lab.research_os.strategy_evidence_library.fingerprint import strategy_fingerprint


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "strategy_evidence_library" / "latest"


def load_json(name: str):
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def test_manifest_records_non_mutating_sel_generation() -> None:
    manifest = load_json("strategy_evidence_library_manifest.json")

    assert manifest["strategy_evidence_library_generated"] is True
    assert manifest["strategy_selection_performed"] is False
    assert manifest["strategy_statuses_changed"] is False
    assert manifest["paper_demo_decisions_changed"] is False
    assert manifest["approval_thresholds_changed"] is False
    assert manifest["backtest_logic_changed"] is False
    assert manifest["runtime_network_calls"] is False
    assert manifest["registry_entries_seen"] >= 1
    assert manifest["source_records"] >= 1
    assert manifest["idea_records"] >= manifest["registry_entries_seen"]


def test_unique_stable_ids_and_referential_integrity() -> None:
    sources = load_json("sel_sources.json")
    ideas = load_json("sel_ideas.json")
    specs = load_json("sel_preregistrations.json")
    impls = load_json("sel_implementations.json")
    experiments = load_json("sel_experiments.json")
    decisions = load_json("sel_decisions.json")

    for rows, key in [
        (sources, "source_id"),
        (ideas, "idea_id"),
        (specs, "specification_id"),
        (impls, "implementation_id"),
        (experiments, "experiment_id"),
        (decisions, "decision_id"),
    ]:
        values = [row[key] for row in rows]
        assert len(values) == len(set(values)), key
        assert all(value and value == value.strip() for value in values)

    source_ids = {row["source_id"] for row in sources}
    idea_ids = {row["idea_id"] for row in ideas}
    variant_ids = {row["variant_id"] for row in ideas}
    impl_ids = {row["implementation_id"] for row in impls}

    assert all(row["source_id"] in source_ids for row in ideas)
    assert all(row["idea_id"] in idea_ids for row in specs)
    assert all(row["variant_id"] in variant_ids for row in impls)
    assert all(row["variant_id"] in variant_ids for row in experiments)
    assert all(row["implementation_id"] in impl_ids for row in experiments)
    assert all(row["idea_id"] in idea_ids for row in decisions)


def test_evidence_levels_are_cumulative_and_have_required_links() -> None:
    specs_by_idea = defaultdict(list)
    for row in load_json("sel_preregistrations.json"):
        specs_by_idea[row["idea_id"]].append(row)
    impls_by_variant = defaultdict(list)
    for row in load_json("sel_implementations.json"):
        impls_by_variant[row["variant_id"]].append(row)
    exps_by_variant = defaultdict(list)
    for row in load_json("sel_experiments.json"):
        exps_by_variant[row["variant_id"]].append(row)

    for decision in load_json("sel_decisions.json"):
        level = decision["evidence_level"]
        assert level in EVIDENCE_LEVELS
        assert decision["evidence_chain"] == evidence_chain(level)
        if level_rank(level) >= level_rank("E2"):
            assert specs_by_idea[decision["idea_id"]]
        if level_rank(level) >= level_rank("E3"):
            assert impls_by_variant[decision["variant_id"]]
            for impl in impls_by_variant[decision["variant_id"]]:
                assert impl["code_commit_hash"] != "unknown"
                assert impl["configuration_hash"] != "unknown"
                assert impl["dependency_lock_hash"] != "unknown"
        if level_rank(level) >= level_rank("E4"):
            assert exps_by_variant[decision["variant_id"]]
            assert all(exp["data_snapshot_hash"] != "unknown" for exp in exps_by_variant[decision["variant_id"]])
        if level_rank(level) >= level_rank("E6"):
            assert decision["frozen_paper_demo_configuration_hash"] != "unknown"


def test_external_sources_at_e1_or_higher_have_source_records() -> None:
    sources = {row["source_id"]: row for row in load_json("sel_sources.json")}
    ideas = {row["idea_id"]: row for row in load_json("sel_ideas.json")}
    for decision in load_json("sel_decisions.json"):
        if level_rank(decision["evidence_level"]) < level_rank("E1"):
            continue
        idea = ideas[decision["idea_id"]]
        source = sources[idea["source_id"]]
        assert source["source_id"]
        if source["source_type"] != "internal_prompt":
            assert source["citation"] != "unknown"


def test_source_claimed_metrics_are_separate_from_project_observed_metrics() -> None:
    sources = load_json("sel_sources.json")
    experiments = load_json("sel_experiments.json")

    assert all("source_claimed_metrics" in source for source in sources)
    assert all("locally_observed_metrics" not in source for source in sources)
    assert all("locally_observed_metrics" in experiment for experiment in experiments)
    assert all("source_claimed_metrics" not in experiment for experiment in experiments)


def test_controlled_status_and_failure_enums() -> None:
    for decision in load_json("sel_decisions.json"):
        assert decision["project_status"] in LIFECYCLE_STATUSES
        for code in decision.get("rejection_reason_code", []):
            assert code in FAILURE_CODES


def test_deterministic_strategy_fingerprint_generation() -> None:
    left = {
        "family": "Short Term Equity Mean Reversion",
        "signal_direction": "Long Only",
        "universe_type": ["SPY", "BIL"],
        "formation_horizon": "2 days",
        "holding_horizon": "daily",
        "rebalance_frequency": "daily",
        "weighting_method": "single asset or cash",
        "risk_overlay": "200d trend filter",
        "execution_cadence": "shifted close",
    }
    right = {
        "execution_cadence": "shifted-close",
        "risk_overlay": "200D trend filter",
        "weighting_method": "single_asset_or_cash",
        "rebalance_frequency": "DAILY",
        "holding_horizon": "daily",
        "formation_horizon": "2 days",
        "universe_type": ["BIL", "SPY"],
        "signal_direction": "long_only",
        "family": "short-term equity mean reversion",
    }

    assert strategy_fingerprint(left) == strategy_fingerprint(right)


def test_migration_preserves_registry_ids_and_active_observation_references() -> None:
    registry = yaml.safe_load((ROOT / "strategy_lab" / "strategy_registry.yaml").read_text(encoding="utf-8"))
    registry_ids = {row["id"] for row in registry["strategies"]}
    ideas = {row["variant_id"] for row in load_json("sel_ideas.json")}

    assert registry_ids <= ideas

    active = yaml.safe_load(
        (ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml").read_text(
            encoding="utf-8"
        )
    )
    active_ids = {row["strategy_id"] for row in active["active_observations"]}
    decisions = load_json("sel_decisions.json")
    active_decisions = {row["variant_id"] for row in decisions if row["evidence_level"] == "E7"}

    assert active_ids <= active_decisions


def test_reports_and_consistency_check_exist() -> None:
    required = [
        "repository_architecture_findings.md",
        "strategy_evidence_library_summary.md",
        "strategy_inventory.csv",
        "family_mapping.md",
        "duplicate_near_duplicate_variants.md",
        "failure_rejection_reasons_by_family.md",
        "evidence_level_funnel.md",
        "remaining_cleanup_candidates.md",
        "removed_files_and_directories.md",
        "strategy_evidence_library_consistency_check.json",
    ]
    for filename in required:
        assert (EVIDENCE / filename).exists(), filename
    consistency = load_json("strategy_evidence_library_consistency_check.json")
    assert consistency["consistency_passed"] is True
