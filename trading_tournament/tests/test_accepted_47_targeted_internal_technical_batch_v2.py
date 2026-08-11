from __future__ import annotations

import csv
import json
import math

import yaml

from strategy_lab.research_os.exploratory_sandbox.sandbox_config import ROOT
from strategy_lab.research_os.research import accepted_47_targeted_internal_technical_batch_v2 as subject


OUTPUT = ROOT / "evidence" / "research_recovery" / subject.TASK_ID / "latest"


def rows(name: str) -> list[dict[str, str]]:
    with (OUTPUT / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_exact_frozen_architecture_grid_and_protected_capture_scope() -> None:
    assert len(subject.ARCHITECTURES) == 3
    assert len(subject.CONFIGS) == 12
    assert all(len(subject.configs_for_architecture(arch.architecture_code)) == 4 for arch in subject.ARCHITECTURES)
    assert len({config.strategy_id for config in subject.CONFIGS}) == 12
    assert len({config.trial_id for config in subject.CONFIGS}) == 12
    assert not any("capture_asymmetry" in config.strategy_id for config in subject.CONFIGS)
    assert not any("capture" in config.trial_id for config in subject.CONFIGS)
    assert [config.configuration_code for config in subject.CONFIGS] == [
        "A1", "A2", "A3", "A4", "B1", "B2", "B3", "B4", "C1", "C2", "C3", "C4",
    ]


def test_duplicate_preflight_scans_and_allows_distinct_architectures() -> None:
    preflight = subject.duplicate_preflight_rows()
    assert {row["architecture_code"] for row in preflight} == {"A", "B", "C"}
    assert all(row["preflight_status"] == "pass" for row in preflight)
    assert all(row["execute_architecture_trials"] is True for row in preflight)
    by_code = {row["architecture_code"]: row for row in preflight}
    assert by_code["A"]["distinctive_characteristic"] == "own_return_positive_sum_over_absolute_negative_return_pain"
    assert by_code["B"]["distinctive_characteristic"] == "mean_close_location_value_over_trailing_ohlc_window"
    assert by_code["C"]["distinctive_characteristic"] == "frequency_of_returns_below_mean_minus_1_5_standard_deviations"
    assert all(row["protected_capture_asymmetry_variant_created"] is False for row in preflight)


def test_formula_fixtures_and_following_session_execution() -> None:
    frames = subject.load_frames()

    arch_a = subject.architecture_by_code("A")
    split_a = subject.architecture_split(frames, arch_a)
    config_a = subject.configs_for_architecture("A")[0]
    signal_a, execution_a = split_a.signal_execution_pairs[0]
    assert execution_a == subject.next_session(split_a.prices.index, signal_a)
    scores, positive_sums, negative_pains, counts = subject.gain_to_pain_scores(
        split_a.prices, arch_a.universe, signal_a, config_a.lookback_sessions
    )
    top_a = subject.sorted_desc(scores)[0]
    assert counts["eligible_count"] > 0
    assert math.isclose(scores[top_a], positive_sums[top_a] / negative_pains[top_a], rel_tol=0.0, abs_tol=1e-14)

    arch_b = subject.architecture_by_code("B")
    split_b = subject.architecture_split(frames, arch_b)
    config_b = subject.configs_for_architecture("B")[0]
    scores_b, valid_counts = subject.clv_pressure_scores(
        split_b.highs, split_b.lows, split_b.closes, arch_b.universe, split_b.signal_execution_pairs[0][0], config_b.lookback_sessions
    )
    top_b = subject.sorted_desc(scores_b)[0]
    assert -1.0000001 <= scores_b[top_b] <= 1.0000001
    assert valid_counts[top_b] >= math.ceil(0.9 * config_b.lookback_sessions)

    arch_c = subject.architecture_by_code("C")
    split_c = subject.architecture_split(frames, arch_c)
    config_c = subject.configs_for_architecture("C")[0]
    scores_c, frequency, realized_vol, tail_counts = subject.tail_frequency_scores(
        split_c.prices, arch_c.universe, split_c.signal_execution_pairs[0][0], config_c.lookback_sessions
    )
    top_c = subject.sorted_desc(scores_c)[0]
    assert math.isclose(scores_c[top_c], -frequency[top_c], rel_tol=0.0, abs_tol=1e-14)
    assert realized_vol[top_c] > 0.0
    assert tail_counts[top_c] >= 0


def test_run_outputs_required_packet_and_bounded_entities() -> None:
    result = subject.run()
    assert result["batch_id"] == subject.TASK_ID
    assert {path.name for path in OUTPUT.iterdir() if path.is_file()} == subject.REQUIRED_OUTPUT_FILES
    counts = json.loads((OUTPUT / "entity_count_reconciliation.json").read_text(encoding="utf-8"))
    assert counts["architectures_preregistered"] == 3
    assert counts["strategy_configurations"] == 12
    assert counts["canonical_experiment_trials"] == 12
    assert counts["executed_trials"] == 12
    assert counts["duplicate_or_blocked_trials"] == 0
    assert counts["architecture_winners"] == 1
    assert counts["exploratory_followup_candidates"] == 0
    assert counts["robustness_trials_created"] == 0
    assert counts["validation_trials_created"] == 0
    assert counts["paper_demo_eligibility_records_created"] == 0
    assert counts["handoff_export_records_created"] == 0
    assert counts["observations_created"] == 0


def test_selection_winner_and_evaluation_access_are_isolated() -> None:
    selection = rows("selection_segment_results.csv")
    assert len(selection) == 36
    assert {row["cost_bps_one_way"] for row in selection} == {"0", "5", "10"}
    assert all(row["performance_executed"] == "true" for row in selection)

    winners = rows("architecture_winner_selection.csv")
    by_arch = {row["architecture_id"]: row for row in winners}
    assert by_arch["positive_negative_return_path_quality"]["selection_status"] == "no_selection_eligible_configuration"
    assert by_arch["rolling_intraday_close_location_characteristic"]["selected_trial_id"] == "accepted47_internal_v2__clv21__top3"
    assert by_arch["standardized_downside_tail_event_selection"]["selection_status"] == "no_selection_eligible_configuration"

    evaluated = {row["trial_id"] for row in rows("evaluation_segment_results.csv")}
    assert evaluated == {"accepted47_internal_v2__clv21__top3"}
    assert len(rows("evaluation_segment_results.csv")) == 3
    assert all(row["selection_frozen_before_evaluation_metrics"] == "true" for row in rows("evaluation_segment_results.csv"))


def test_evaluation_failure_precedence_and_no_followup_routing() -> None:
    failure = {row["trial_id"]: row for row in rows("failure_reasons.csv")}
    assert failure["accepted47_internal_v2__clv21__top3"]["primary_failure_reason"] == "weak_vs_primary_control"
    subhalves = rows("evaluation_subhalf_results.csv")
    assert len(subhalves) == 2
    assert {row["diagnostic_state"] for row in subhalves} == {"pass", "period_instability"}
    assert rows("exploratory_followup_candidates.csv") == []
    summary = rows("outcome_summary.csv")
    process = next(row for row in summary if row["entity_type"] == "process_task")
    assert process["outcome"] == "targeted_internal_batch_v2_no_followup"
    assert process["batch_next_action"] == subject.NO_FOLLOWUP_NEXT_ACTION


def test_manifest_consistency_and_protected_state() -> None:
    manifest = yaml.safe_load((OUTPUT / "batch_manifest.yaml").read_text(encoding="utf-8"))
    assert manifest["mode"] == subject.MODE
    assert manifest["data_boundary"]["provider_access"] is False
    assert manifest["data_boundary"]["network_access"] is False
    assert manifest["protected_successful_strategy"]["fingerprint"] == subject.PROTECTED_CAPTURE_HANDOFF_FINGERPRINT
    assert manifest["protected_successful_strategy"]["nearby_variant_created"] is False
    assert manifest["batch_outcome"] == "targeted_internal_batch_v2_no_followup"
    assert manifest["exact_next_action"] == subject.NO_FOLLOWUP_NEXT_ACTION
    consistency = json.loads((OUTPUT / "consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["overall_pass"] is True
    assert consistency["checks"]["no_capture_asymmetry_variant_created"] is True
    assert consistency["checks"]["nonwinner_evaluation_access_prohibited"] is True
    assert consistency["checks"]["protected_capture_strategy_fingerprint_preserved"] is True
    assert consistency["checks"]["protected_state_cache_and_prior_evidence_unchanged"] is True
    assert all(value is False for value in consistency["forbidden_actions"].values())


def test_deterministic_rerun_hash_stable() -> None:
    before = json.loads((OUTPUT / "consistency_check.json").read_text(encoding="utf-8"))["deterministic_core_hash"]
    subject.run()
    after = json.loads((OUTPUT / "consistency_check.json").read_text(encoding="utf-8"))["deterministic_core_hash"]
    assert after == before
