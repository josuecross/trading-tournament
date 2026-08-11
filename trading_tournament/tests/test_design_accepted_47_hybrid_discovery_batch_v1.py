from __future__ import annotations

import csv
import json

import yaml

from strategy_lab.research_os.research import design_accepted_47_hybrid_discovery_batch_v1 as task


OUTPUT = task.OUTPUT_DIR


def rows(name: str) -> list[dict[str, str]]:
    with (OUTPUT / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def yml(name: str) -> dict:
    return yaml.safe_load((OUTPUT / name).read_text(encoding="utf-8"))


def test_output_set_outcome_and_design_only_boundary() -> None:
    assert {path.name for path in OUTPUT.iterdir() if path.is_file()} == task.REQUIRED_OUTPUTS
    manifest = yml("design_manifest.yaml")
    assert manifest["outcome"] == "hybrid_batch_design_ready"
    assert manifest["next_action"] == "accepted_47_hybrid_discovery_batch_v1"
    assert manifest["strategy_records_created"] == 0
    assert manifest["trial_records_created"] == 0
    assert manifest["provider_or_network_access"] is False
    assert manifest["data_modified"] is False
    assert manifest["performance_calculated"] is False
    assert manifest["backtest_run"] is False


def test_three_architectures_three_families_and_twelve_unique_trials() -> None:
    specs = yml("selected_architecture_specifications.yaml")["architectures"]
    catalog = rows("configuration_trial_catalog.csv")
    assert len(specs) == 3
    assert len({spec["family_id"] for spec in specs}) == 3
    assert len(catalog) == 12
    assert len({row["strategy_id"] for row in catalog}) == 12
    assert len({row["trial_id"] for row in catalog}) == 12
    assert {sum(row["architecture_id"] == spec["architecture_id"] for row in catalog) for spec in specs} == {4}
    assert all(row["parent_trial_id"] == "" and row["adaptation_label"] == "" for row in catalog)


def test_exact_accepted_membership_is_frozen_without_EEMV_or_EFAV() -> None:
    batch = yml("frozen_batch_spec.yaml")
    assert tuple(batch["accepted_membership"]) == task.ACCEPTED_UNIVERSE
    assert len(batch["accepted_membership"]) == 47
    assert batch["excluded_symbols"] == ["EEMV", "EFAV"]
    assert batch["provider_access_allowed"] is False
    assert batch["data_endpoint"] == "2026-08-04"


def test_required_pair_lane_is_economic_long_only_and_complete() -> None:
    pair = yml("selected_architecture_specifications.yaml")["architectures"][0]
    pairs = [(row["A"], row["B"]) for row in pair["economic_pairs"]]
    assert pair["architecture_id"] == task.PAIR_ARCHITECTURE
    assert pairs == [("IEF", "TLT"), ("LQD", "HYG"), ("GLD", "SLV"), ("IYR", "XLRE")]
    assert all(row["rationale"] for row in pair["economic_pairs"])
    assert pair["formula"]["z_score"] == "z_t=(x_t-mean_t)/standard_deviation_t"
    assert pair["state_machine"]["direct_A_to_B_or_B_to_A"] is False
    assert pair["allocation"]["pair_sleeve_weight"] == 0.25
    assert pair["execution"] == "following regular common session close"
    assert "short" not in pair["strategy_type"]


def test_cross_group_lane_uses_correlation_transition_not_return_ranking() -> None:
    correlation = yml("selected_architecture_specifications.yaml")["architectures"][1]
    assert correlation["architecture_id"] == task.CORRELATION_ARCHITECTURE
    assert correlation["formula"]["score"] == "short_correlation-long_correlation"
    assert correlation["selection_and_allocation"]["selected_count"] == 4
    assert correlation["selectable_universe"] == list(task.CORRELATION_SELECTABLE)
    assert {"EFA", "EEM", "TLT", "HYG", "GLD", "DBC", "IYR", "IFRA"} <= set(correlation["instrument_universe"])
    assert "return" not in correlation["formula"]["score"]
    assert correlation["controls"]["named_same_purpose_control"] == "lowest_static_long_window_correlation_top4_control"


def test_internal_technical_lane_is_not_factory_volume_breakout() -> None:
    volume = yml("selected_architecture_specifications.yaml")["architectures"][2]
    assert volume["architecture_id"] == task.VOLUME_ARCHITECTURE
    assert volume["source_or_research_lineage"] == "internally_generated_technical_hypothesis"
    assert volume["formula"]["directional_volume_ratio"].startswith("sum(raw_volume_s where return_s<0)")
    assert volume["signal_frequency"] == "final completed regular session of each week"
    assert tuple(volume["risk_basket"]) == task.VOLUME_RISK_BASKET
    assert tuple(volume["defensive_basket"]) == task.VOLUME_DEFENSIVE_BASKET
    rendered = json.dumps(volume).lower()
    assert "breakout" not in rendered
    assert volume["controls"]["named_same_purpose_control"] == "price_only_negative_session_breadth_state_control"


def test_bounded_grids_vary_at_most_two_parameters_and_are_frozen() -> None:
    specs = yml("selected_architecture_specifications.yaml")["architectures"]
    batch = yml("frozen_batch_spec.yaml")
    assert all(spec["optimization_mode"] == "bounded_optimization" for spec in specs)
    assert all(spec["configuration_grid"]["varying_parameters"] <= 3 for spec in specs)
    assert all(spec["configuration_count"] == 4 for spec in specs)
    optimization = batch["bounded_optimization"]
    assert optimization["grid_frozen_before_performance"] is True
    assert optimization["post_result_expansion_allowed"] is False
    assert "floor(80%" in optimization["development_final_split"]
    assert "lexical strategy_id" in optimization["selection"]
    assert "not validation" in optimization["final_segment"]


def test_control_first_and_route_requirements_are_frozen() -> None:
    controls = rows("control_catalog.csv")
    specs = yml("selected_architecture_specifications.yaml")["architectures"]
    for spec in specs:
        architecture_controls = [row for row in controls if row["architecture_id"] == spec["architecture_id"]]
        roles = {row["control_role"] for row in architecture_controls}
        assert "primary_broad_benchmark" in roles
        assert "named_same_purpose_control" in roles
        assert any("static" in role or "exposure" in role for role in roles)
        assert spec["incremental_value_hypothesis"]
        assert spec["concentration_hypothesis"]
        assert spec["route"] == "standalone_with_diversifier_diagnostic"
    routes = yml("frozen_batch_spec.yaml")["routes"]
    assert routes["reference"] == "frozen_current_active_vm_dsr_usci_combo"
    assert routes["portfolio_diagnostics_are_trials"] is False
    assert len(routes["portfolio_diagnostics"]) == 4


def test_no_material_rule_is_unknown_or_left_to_codex() -> None:
    frozen_text = (OUTPUT / "selected_architecture_specifications.yaml").read_text(encoding="utf-8").lower()
    batch_text = (OUTPUT / "frozen_batch_spec.yaml").read_text(encoding="utf-8").lower()
    for prohibited in ("tbd", "unknown", "left to codex", "choose after", "selected from performance"):
        assert prohibited not in frozen_text
        assert prohibited not in batch_text
    for spec in yml("selected_architecture_specifications.yaml")["architectures"]:
        for field in ("architecture_id", "family_id", "display_name", "strategy_type", "source_or_research_lineage", "instrument_universe", "formula", "signal_frequency", "execution", "warmup", "missing_data", "route", "controls", "incremental_value_hypothesis", "concentration_hypothesis", "principal_failure_risk"):
            assert spec[field]


def test_rejections_use_authorized_reasons_and_create_no_trials() -> None:
    rejected = rows("rejection_ledger.csv")
    allowed = {
        "already_tested", "duplicate_or_redundant", "not_economically_distinct",
        "formula_incomplete", "unsupported_translation", "data_unavailable",
        "capability_missing", "performance_selected_universe", "turnover_risk",
        "concentration_by_design", "other",
    }
    assert len(rejected) == 4
    assert {row["reason"] for row in rejected} <= allowed
    assert all(row["explanation"] and row["reconsideration_condition"] for row in rejected)
    catalog_text = (OUTPUT / "configuration_trial_catalog.csv").read_text(encoding="utf-8")
    assert not any(row["architecture"] in catalog_text for row in rejected)


def test_conditional_prompt_authorizes_only_frozen_exploration() -> None:
    prompt = (OUTPUT / "conditional_codex_prompt.md").read_text(encoding="utf-8")
    assert "`accepted_47_hybrid_discovery_batch_v1`" in prompt
    assert "exactly three architectures, three families and twelve unique configurations/trials" in prompt
    assert "Do not access a provider or network" in prompt
    assert "Do not promote a control" in prompt
    assert "Do not tune to escape closure" in prompt
    assert "robustness or validation" in prompt
    assert "paper/demo" in prompt
    assert "broker/account/order/position/transfer/real-money" in prompt
    assert prompt.count("Perform one task only:") == 1


def test_protected_state_and_sources_remain_unchanged() -> None:
    protected = rows("protected_state_reconciliation.csv")
    checks = json.loads((OUTPUT / "consistency_check.json").read_text(encoding="utf-8"))
    sources = rows("source_evidence_manifest.csv")
    assert sources and all(row["exists"] == "True" and row["sha256"] != "missing" for row in sources)
    assert protected and all(row["unchanged"] == "True" for row in protected)
    assert checks["all_protected_state_unchanged"] is True
    assert checks["strategy_records_created"] == 0
    assert checks["trial_records_created"] == 0
    assert checks["performance_calculated"] is False
    assert checks["backtest_run"] is False
    assert checks["overall_pass"] is True

