from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

import yaml

from strategy_lab.research_os.strategy_evidence_library.builder import (
    EVIDENCE_LEVELS,
    FAILURE_CODES,
    LIFECYCLE_STATUSES,
    add_spec_field,
    apply_spec_qualification,
    build_strategy_evidence_library,
    classify_source_record,
    duplicate_external_source_rows,
    evidence_chain,
    evaluate_spec_qualification,
    failure_provenance_from_fields,
    implementation_template,
    level_rank,
    qualifies_implementation,
    qualifies_preregistration,
    semantic_snapshot,
    source_classification_consistency,
    source_link_integrity_rows,
    spec_template,
)
from strategy_lab.research_os.strategy_evidence_library.fingerprint import strategy_fingerprint


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "strategy_evidence_library" / "latest"


def load_json(name: str):
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def csv_rows(name: str):
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


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
        is_active_observation = level == "E7"
        if level_rank(level) >= level_rank("E2"):
            if not is_active_observation:
                assert any(spec.get("qualifies_as_preregistration") for spec in specs_by_idea[decision["idea_id"]])
        if level_rank(level) >= level_rank("E3") and not is_active_observation:
            qualified_impls = [
                impl
                for impl in impls_by_variant[decision["variant_id"]]
                if impl.get("qualifies_as_reproducible_implementation")
            ]
            assert qualified_impls
            for impl in qualified_impls:
                assert impl["code_commit_hash"] != "unknown"
                assert impl["configuration_hash"] != "unknown"
                assert impl["dependency_lock_hash"] != "unknown"
        if level_rank(level) >= level_rank("E4") and not is_active_observation:
            qualified_exps = [
                exp for exp in exps_by_variant[decision["variant_id"]] if exp.get("qualifies_as_local_backtest")
            ]
            assert qualified_exps
            assert all(exp["data_snapshot_hash"] != "unknown" for exp in qualified_exps)
        if level_rank(level) >= level_rank("E5") and not is_active_observation:
            assert any(exp.get("qualifies_as_robustness") for exp in exps_by_variant[decision["variant_id"]])
        if level_rank(level) >= level_rank("E6"):
            if level == "E7":
                assert decision["active_observation_linkage"]["index_detail_agree"] is True
            else:
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


def test_source_origin_fields_are_present_and_external_backlog_is_clean() -> None:
    sources = load_json("sel_sources.json")
    backlog_rows = list(csv_rows("external_public_source_backlog.csv"))
    project_evidence_ids = {row["source_id"] for row in sources if row["source_id"].startswith("project_evidence_")}

    required = {
        "raw_source_type",
        "source_origin",
        "source_class",
        "source_role",
        "external_public_source",
        "eligible_for_external_discovery_backlog",
        "classification_rule_id",
        "classification_provenance",
    }
    assert all(required <= set(source) for source in sources)
    assert not (project_evidence_ids & {row["source_id"] for row in backlog_rows})
    assert all(row["source_origin"] == "external" for row in backlog_rows)
    assert all(row["source_url_or_citation_available"] == "True" for row in backlog_rows)


def test_project_evidence_internal_prompt_and_generated_records_do_not_enter_external_backlog() -> None:
    project_source = classify_source_record(
        {
            "source_id": "project_evidence_current_research_checkpoint",
            "source_name": "Internal project evidence: current_research_checkpoint",
            "source_type": "project_evidence_manifest",
            "citation": "evidence/current_research_checkpoint/latest/current_research_checkpoint_manifest.json",
            "original_source_paths": ["evidence/current_research_checkpoint/latest/current_research_checkpoint_manifest.json"],
        }
    )
    prompt_source = classify_source_record(
        {
            "source_id": "internal_prompt_mean_reversion",
            "source_name": "Internal prompt",
            "source_type": "internal_prompt",
            "citation": "strategy_lab/strategy_registry.yaml",
            "original_source_paths": ["strategy_lab/strategy_registry.yaml"],
        }
    )
    generated_source = classify_source_record(
        {
            "source_id": "generated_dashboard_latest",
            "source_name": "Generated dashboard",
            "source_type": "generated_dashboard",
            "citation": "evidence/research_state/latest/research_state_manifest.json",
            "original_source_paths": ["evidence/research_state/latest/research_state_manifest.json"],
        }
    )

    assert project_source["source_origin"] == "internal"
    assert project_source["source_class"] == "internal_project_evidence"
    assert project_source["eligible_for_external_discovery_backlog"] is False
    assert prompt_source["source_class"] == "internal_prompt_idea"
    assert prompt_source["eligible_for_external_discovery_backlog"] is False
    assert generated_source["source_origin"] == "generated"
    assert generated_source["eligible_for_external_discovery_backlog"] is False


def test_active_combo_benchmark_source_is_internal_benchmark_definition() -> None:
    source = classify_source_record(
        {
            "source_id": "project_evidence_active_combo_benchmark",
            "source_name": "Internal project evidence: active_combo_benchmark",
            "source_type": "project_evidence_manifest",
            "citation": "evidence/active_combo_benchmark/latest/active_combo_manifest.json",
            "original_source_paths": ["evidence/active_combo_benchmark/latest/active_combo_manifest.json"],
        }
    )

    assert source["source_origin"] == "internal"
    assert source["source_class"] == "internal_benchmark_definition"
    assert source["external_public_source"] is False
    assert source["eligible_for_external_discovery_backlog"] is False


def test_valid_public_source_qualifies_but_code_repo_and_name_only_do_not() -> None:
    public_source = classify_source_record(
        {
            "source_id": "synthetic_public_paper",
            "source_name": "Synthetic documented strategy",
            "source_type": "public practitioner strategy documentation",
            "citation": "StockCharts ChartSchool Synthetic Strategy",
            "source_claim_summary": "Clear and testable source claim.",
            "original_source_paths": ["strategy_lab/research_os/public_strategy_sources/intake_candidates/synthetic.yaml"],
        }
    )
    code_source = classify_source_record(
        {
            "source_id": "synthetic_github_reference",
            "source_name": "GitHub implementation example",
            "source_type": "public open source repository",
            "citation": "https://github.com/example/strategy",
            "source_code_reference": "https://github.com/example/strategy",
        }
    )
    name_only = classify_source_record(
        {
            "source_id": "name_only_strategy",
            "source_name": "Famous Strategy Name",
            "source_type": "public practitioner strategy documentation",
            "citation": "unknown",
        }
    )

    assert public_source["source_origin"] == "external"
    assert public_source["eligible_for_external_discovery_backlog"] is True
    assert code_source["source_class"] == "open_source_implementation_reference"
    assert code_source["implementation_reference_only"] is True
    assert code_source["eligible_for_external_discovery_backlog"] is False
    assert name_only["external_public_source"] is True
    assert name_only["eligible_for_external_discovery_backlog"] is False
    assert name_only["classification_unresolved_reason"] == "source_url_or_citation_missing"


def test_source_link_integrity_and_duplicate_external_reports_are_deterministic() -> None:
    sources = {
        "source_a": classify_source_record(
            {
                "source_id": "source_a",
                "source_name": "Duplicate Public Source A",
                "source_type": "public practitioner strategy documentation",
                "citation": "A documented public strategy citation",
            }
        ),
        "source_b": classify_source_record(
            {
                "source_id": "source_b",
                "source_name": "Duplicate Public Source B",
                "source_type": "public practitioner strategy documentation",
                "citation": "A documented public strategy citation",
            }
        ),
    }
    ideas = {
        "idea_a": {"idea_id": "idea_a", "source_id": "source_a", "variant_id": "variant_a"},
        "idea_broken": {"idea_id": "idea_broken", "source_id": "missing_source", "variant_id": "variant_b"},
    }
    impls = {"impl_a": {"implementation_id": "impl_a", "variant_id": "variant_a"}}

    link_rows = source_link_integrity_rows(sources, ideas, impls)
    duplicate_rows = duplicate_external_source_rows(sources)
    consistency = source_classification_consistency(
        {
            "sources": list(sources.values()),
            "ideas": list(ideas.values()),
            "implementations": list(impls.values()),
            "reports": {
                "external_public_source_backlog": [],
                "source_link_integrity": link_rows,
                "duplicate_external_sources": duplicate_rows,
            },
        }
    )

    assert any(row["link_status"] == "broken_missing_source" for row in link_rows)
    assert duplicate_rows and duplicate_rows[0]["source_count"] == 2
    assert consistency["broken_source_link_count"] == 1
    assert consistency["source_classification_consistency_passed"] is False


def test_controlled_status_and_failure_enums() -> None:
    for decision in load_json("sel_decisions.json"):
        assert decision["project_status"] in LIFECYCLE_STATUSES
        for code in decision.get("rejection_reason_code", []):
            assert code in FAILURE_CODES


def test_semantic_patch_prevents_placeholder_evidence_inflation() -> None:
    specs = load_json("sel_preregistrations.json")
    decisions = load_json("sel_decisions.json")
    manifest = load_json("strategy_evidence_library_manifest.json")
    semantic_report = load_json("semantic_correction_report.json")

    assert manifest["migration_placeholder_spec_count"] == 0
    assert manifest["placeholder_linked_e2_or_higher_decision_count"] == 0
    assert semantic_report["previous_snapshot"]["migration_placeholder_spec_count"] == 211
    assert semantic_report["previous_snapshot"]["placeholder_linked_e2_or_higher_decision_count"] == 212
    assert semantic_report["corrected_snapshot"]["migration_placeholder_spec_count"] == 0
    assert semantic_report["corrected_snapshot"]["placeholder_linked_e2_or_higher_decision_count"] == 0
    assert not any(
        spec.get("record_kind") == "migration_placeholder" and spec.get("qualifies_as_preregistration")
        for spec in specs
    )
    assert not any(
        decision["evidence_level"] in {"E2", "E3", "E4", "E5", "E6"}
        and any(
            spec.get("record_kind") == "migration_placeholder"
            for spec in specs
            if spec["specification_id"] in decision.get("related_specification_ids", [])
        )
        for decision in decisions
    )


def test_exact_status_preservation_without_lifecycle_inflation() -> None:
    decisions = load_json("sel_decisions.json")
    sensitive_statuses = {
        "promotion_review_passed",
        "benchmark_watchlist",
        "needs_benchmark_delta_review",
        "active_observation_running",
    }
    seen = set()
    for decision in decisions:
        source_values = {
            str(decision.get("source_project_status", "")),
            str(decision.get("source_status_detail", "")),
        }
        matched = {value for value in source_values if value in sensitive_statuses}
        if matched:
            seen |= matched
            assert decision["project_status"] not in {"eligible", "active"}
            assert decision["evidence_level"] != "E7"
        if decision.get("record_role") == "benchmark":
            assert decision["evidence_level"] != "E6"

    assert {"promotion_review_passed", "benchmark_watchlist", "needs_benchmark_delta_review"} <= seen


def test_canonical_active_observations_keep_active_lifecycle_without_e7() -> None:
    active = yaml.safe_load(
        (ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml").read_text(
            encoding="utf-8"
        )
    )
    active_ids = {row["strategy_id"] for row in active["active_observations"]}
    decisions = load_json("sel_decisions.json")
    active_decisions = [row for row in decisions if row["variant_id"] in active_ids]

    assert {row["variant_id"] for row in active_decisions} == active_ids
    for decision in active_decisions:
        assert decision["project_status"] == "active"
        assert decision["record_role"] == "paper_demo_observation"
        assert decision["active_observation_linkage"]["index_detail_agree"] is True
        assert decision["active_observation_linkage"]["detail_status"] == "active_paper_demo_observation"
        assert decision["evidence_level"] == "E1"
        assert decision["verified_evidence_level"] == "E1"
        assert decision["legacy_active_observation_with_incomplete_evidence_chain"] is True


def test_failure_codes_require_field_level_provenance() -> None:
    for decision in load_json("sel_decisions.json"):
        provenance_by_code = defaultdict(list)
        for row in decision.get("failure_code_provenance", []):
            provenance_by_code[row["failure_code"]].append(row)
            assert row["source_path"]
            assert row["source_field"]
            assert row["supporting_value"] != "unknown"
            assert row["mapping_rule_id"]
            assert row["origin_type"] == "normalized_explicit"
        for code in decision.get("rejection_reason_code", []):
            assert provenance_by_code[code]


def test_generic_failure_keywords_do_not_create_failure_codes() -> None:
    rows = failure_provenance_from_fields(
        "synthetic",
        {
            "notes": "lookahead validation passed and code defect corrected",
            "summary": "the patch evidence is preserved but not an active defect",
        },
    )
    assert rows == []


def test_source_statuses_remain_recoverable_exactly() -> None:
    for decision in load_json("sel_decisions.json"):
        assert "source_project_status" in decision
        assert "source_status_detail" in decision
        assert decision["source_project_status"] != "unknown" or decision["source_status_detail"] != "unknown"


def test_semantic_correction_change_reports_exist_and_are_nonempty() -> None:
    semantic_report = load_json("semantic_correction_report.json")
    assert semantic_report["previous_snapshot_source"] == "verified_pre_patch_baseline"
    assert semantic_report["record_level_change_baseline"] == "legacy_pre_patch_mapping_projection"
    assert semantic_report["evidence_level_change_count"] > 0
    assert semantic_report["lifecycle_change_count"] > 0
    assert semantic_report["removed_failure_code_count"] > 0
    for filename in [
        "semantic_evidence_level_changes.csv",
        "semantic_lifecycle_changes.csv",
        "removed_failure_codes.csv",
        "failure_code_provenance.csv",
    ]:
        assert (EVIDENCE / filename).exists()


def complete_synthetic_spec():
    spec = spec_template("spec_complete", "idea_complete", "variant_complete")
    spec.update(
        {
            "record_kind": "design_evidence_reference",
            "qualifies_as_preregistration": True,
            "specification_content_hash": "abc123",
            "frozen_specification_reference": "evidence/synthetic/latest/manifest.json",
        }
    )
    values = {
        "strategy_universe": ["SPY", "BIL"],
        "entry_rule": "Enter long SPY when condition A is true after close.",
        "exit_rule": "Exit to BIL when condition A is false after close.",
        "timeframe": "daily",
        "rebalance_cadence": "daily",
        "parameters": {"parameter_free": True},
        "required_data": "Daily adjusted OHLCV for SPY and BIL.",
        "signal_timestamp": "completed daily close",
        "order_timestamp": "next project shifted-weight bar",
        "benchmark_rule": "Compare against SPY buy-hold and BIL.",
        "success_criteria": "Total return versus BIL > 0.",
        "failure_criteria": "Invariant failure or total return versus BIL <= 0.",
    }
    for field, value in values.items():
        add_spec_field(spec, field, value, "synthetic", field, "synthetic_complete_spec_v1")
    spec["field_provenance"]["specification_content_hash"] = {
        "source_path": "synthetic",
        "source_field": "content_hash",
        "supporting_value": "abc123",
        "mapping_rule_id": "synthetic_hash_v1",
        "origin_type": "explicit",
    }
    spec["field_provenance"]["frozen_specification_reference"] = {
        "source_path": "synthetic",
        "source_field": "frozen_reference",
        "supporting_value": "evidence/synthetic/latest/manifest.json",
        "mapping_rule_id": "synthetic_frozen_reference_v1",
        "origin_type": "explicit",
    }
    return spec


def test_see_artifact_cannot_satisfy_e2_fields() -> None:
    spec = complete_synthetic_spec()
    add_spec_field(spec, "entry_rule", "see_artifact", "synthetic", "entry_rule", "synthetic_bad_spec_v1")
    apply_spec_qualification(spec)

    qualifies, missing, _ = evaluate_spec_qualification(spec)
    assert qualifies is False
    assert "entry_rule" in missing
    assert qualifies_preregistration(spec) is False


def test_design_manifest_with_missing_rules_cannot_qualify_as_e2() -> None:
    design_specs = [
        row for row in load_json("sel_preregistrations.json") if row.get("record_kind") == "design_evidence_reference"
    ]
    assert design_specs
    assert not any(row.get("qualifies_as_preregistration") for row in design_specs)
    assert all(row.get("qualification_missing_fields") for row in design_specs)


def test_blocked_or_patch_required_design_cannot_qualify_as_e2() -> None:
    spec = complete_synthetic_spec()
    spec["source_run_readiness_decision"] = "design_blocked_patch_required"
    apply_spec_qualification(spec)

    qualifies, _, blockers = evaluate_spec_qualification(spec)
    assert qualifies is False
    assert blockers
    assert qualifies_preregistration(spec) is False


def test_complete_structured_preregistration_can_qualify_as_e2() -> None:
    spec = complete_synthetic_spec()
    apply_spec_qualification(spec)

    assert evaluate_spec_qualification(spec)[0] is True
    assert qualifies_preregistration(spec) is True


def test_hashed_python_file_without_tests_or_review_cannot_qualify_as_e3() -> None:
    impl = implementation_template("impl_synthetic", "variant_complete")
    impl.update(
        {
            "qualifies_as_reproducible_implementation": True,
            "repository_path": "strategy_lab/research_os/research/synthetic.py",
            "code_content_hash": "code",
            "configuration_hash": "config",
            "dependency_lock_hash": "deps",
            "linked_qualifying_specification_ids": ["spec_complete"],
            "unit_test_status": "unknown",
            "implementation_review_status": "unknown",
        }
    )

    assert qualifies_implementation(impl) is False


def test_tested_implementation_linked_to_e2_can_qualify_as_e3() -> None:
    impl = implementation_template("impl_synthetic", "variant_complete")
    impl.update(
        {
            "qualifies_as_reproducible_implementation": True,
            "repository_path": "strategy_lab/research_os/research/synthetic.py",
            "code_content_hash": "code",
            "configuration_hash": "config",
            "dependency_lock_hash": "deps",
            "linked_qualifying_specification_ids": ["spec_complete"],
            "linked_tests": ["tests/test_synthetic.py::test_rule"],
            "unit_test_status": "passed",
        }
    )

    assert qualifies_implementation(impl) is True


def test_later_levels_are_not_assigned_without_complete_prior_chain() -> None:
    decisions = load_json("sel_decisions.json")
    experiments = load_json("sel_experiments.json")

    assert not any(row["evidence_level"] in {"E2", "E3", "E4", "E5", "E6", "E7"} for row in decisions)
    assert not any(row.get("qualifies_as_local_backtest") for row in experiments)
    assert not any(row.get("qualifies_as_robustness") for row in experiments)


def test_reconciliation_and_audit_records_do_not_create_duplicate_e4() -> None:
    experiments = load_json("sel_experiments.json")
    assert not any(
        row.get("qualifies_as_local_backtest")
        and row.get("experiment_record_kind") in {"audit_reference", "reconciliation_reference"}
        for row in experiments
    )
    assert not load_json("cumulative_evidence_correction_report.json")["e4_e5_e6_e7_chain_record_count"]


def test_active_lifecycle_status_remains_active_with_incomplete_chain() -> None:
    active = yaml.safe_load(
        (ROOT / "strategy_lab" / "research_os" / "operations" / "active_observations.yaml").read_text(
            encoding="utf-8"
        )
    )
    active_ids = {row["strategy_id"] for row in active["active_observations"]}
    active_decisions = [
        row for row in load_json("sel_decisions.json") if row["variant_id"] in active_ids and row["project_status"] == "active"
    ]

    assert {row["variant_id"] for row in active_decisions} == active_ids
    for decision in active_decisions:
        assert decision["canonical_lifecycle_status"] == "active"
        assert decision["verified_evidence_level"] == "E1"
        assert decision["evidence_level"] == "E1"
        assert decision["legacy_active_observation_with_incomplete_evidence_chain"] is True
        assert decision["missing_evidence_stages"] == ["E2", "E3", "E4", "E5", "E6"]


def test_active_dsr_metric_evidence_status_is_annotated_without_e4_upgrade() -> None:
    dsr = next(
        row
        for row in load_json("sel_decisions.json")
        if row["variant_id"] == "paper_forward_dsr_sector_equal_weight_defensive_filter_v1"
    )

    assert dsr["project_status"] == "active"
    assert dsr["evidence_level"] == "E1"
    assert dsr["historical_recovered_metrics"]["best_final_equity"] == 4071.04
    assert dsr["historical_metric_role"] == "historical_recovered_claim"
    assert dsr["historical_metric_evidence_status"] == "unverified_non_comparable"
    assert dsr["current_diagnostic_metrics"]["best_final_equity"] == 3481.6998
    assert dsr["current_diagnostic_role"] == "current_sampled_window_diagnostic"
    assert dsr["current_diagnostic_scope"] == "best_of_five_sampled_180d_cached_data_windows"
    assert dsr["metric_comparability"] == "non_comparable"
    assert dsr["metric_eligible_for_evidence_stage"]["E4"] is False
    assert "not_qualifying_e4" in dsr["evidence_warning"]
    assert dsr["source_artifact_provenance"]


def test_e7_is_not_assigned_from_active_status_alone() -> None:
    assert not [row for row in load_json("sel_decisions.json") if row["evidence_level"] == "E7"]


def test_no_generated_decision_contains_unsupported_synthesized_chain() -> None:
    for decision in load_json("sel_decisions.json"):
        assert decision["evidence_chain"] == evidence_chain(decision["verified_evidence_level"])
        assert decision["evidence_level"] == decision["verified_evidence_level"]


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


def test_in_memory_sel_generation_is_semantically_deterministic() -> None:
    first = build_strategy_evidence_library(ROOT, cleanup_generated=False)
    second = build_strategy_evidence_library(ROOT, cleanup_generated=False)

    assert semantic_snapshot(first["decisions"], first["specifications"]) == semantic_snapshot(
        second["decisions"], second["specifications"]
    )
    first_decisions = sorted(
        (row["decision_id"], row["variant_id"], row["evidence_level"], row["project_status"])
        for row in first["decisions"]
    )
    second_decisions = sorted(
        (row["decision_id"], row["variant_id"], row["evidence_level"], row["project_status"])
        for row in second["decisions"]
    )
    assert first_decisions == second_decisions


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
    active_decisions = {
        row["variant_id"]
        for row in decisions
        if row["project_status"] == "active" and row.get("record_role") == "paper_demo_observation"
    }

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
        "semantic_correction_report.md",
        "semantic_correction_report.json",
        "semantic_evidence_level_changes.csv",
        "semantic_lifecycle_changes.csv",
        "removed_failure_codes.csv",
        "failure_code_provenance.md",
        "failure_code_provenance.csv",
        "cumulative_evidence_correction_report.md",
        "cumulative_evidence_correction_report.json",
        "e2_qualification_review.csv",
        "e3_implementation_qualification_review.csv",
        "e4_reclassified_records.csv",
        "e4_e5_e6_e7_chain_records.csv",
        "active_incomplete_evidence_chains.csv",
        "external_public_source_backlog.csv",
        "external_public_source_backlog.md",
        "internal_project_evidence_sources.csv",
        "internal_project_evidence_sources.md",
        "external_implementation_references.csv",
        "external_implementation_references.md",
        "source_classification_changes.csv",
        "source_classification_summary.csv",
        "source_classification_summary.md",
        "unresolved_source_classification.csv",
        "unresolved_source_classification.md",
        "source_link_integrity.csv",
        "source_link_integrity.md",
        "duplicate_external_sources.csv",
        "duplicate_external_sources.md",
        "external_sources_no_implementation.csv",
        "external_sources_no_implementation.md",
        "source_classification_consistency_check.json",
        "strategy_evidence_library_consistency_check.json",
    ]
    for filename in required:
        assert (EVIDENCE / filename).exists(), filename
    consistency = load_json("strategy_evidence_library_consistency_check.json")
    assert consistency["consistency_passed"] is True
