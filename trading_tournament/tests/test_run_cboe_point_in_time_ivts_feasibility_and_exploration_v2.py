from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
import yaml

from strategy_lab.research_os.research import (
    run_cboe_point_in_time_ivts_feasibility_and_exploration_v2 as task,
)


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "research_recovery" / task.TASK_ID / "latest"


@pytest.fixture(scope="module", autouse=True)
def evidence_ready() -> None:
    assert (EVIDENCE / "consistency_check.json").exists(), (
        "Run the dedicated Cboe V2 serial runner before focused tests."
    )


def rows(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def json_payload(name: str) -> dict:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def yaml_payload(name: str) -> dict:
    return yaml.safe_load((EVIDENCE / name).read_text(encoding="utf-8"))


def test_required_artifacts_scope_and_conditional_lineage() -> None:
    assert set(task.REQUIRED_ARTIFACTS).issubset(
        {path.name for path in EVIDENCE.iterdir()}
    )
    manifest = yaml_payload("batch_manifest.yaml")
    assert manifest["task_id"] == task.TASK_ID
    assert manifest["mode"] == "fast-progress"
    assert manifest["stage"] == "exploration"
    assert manifest["strategy_id"] == task.STRATEGY_ID
    assert manifest["prior_trial_id"] == task.PRIOR_TRIAL_ID
    assert manifest["conditional_child_trial_id"] == task.CONDITIONAL_CHILD_TRIAL_ID
    assert manifest["child_trial_created"] is False
    assert manifest["data_gate_passed"] is False
    assert manifest["performance_executed"] is False


def test_no_child_trial_is_created_when_gate_fails() -> None:
    assert rows("trial_ledger.csv") == []
    strategies = rows("strategy_cards.csv")
    assert len(strategies) == 1
    assert strategies[0]["strategy_id"] == task.STRATEGY_ID
    assert strategies[0]["existing_configuration_reference"] == "true"
    assert strategies[0]["new_strategy_id_created"] == "false"
    assert strategies[0]["child_trial_created"] == "false"
    assert strategies[0]["prior_trial_id"] == task.PRIOR_TRIAL_ID


def test_historical_queries_are_repeated_and_reproducible() -> None:
    probe = rows("historical_query_reproducibility.csv")
    assert len(probe) == 2 * len(task.HISTORICAL_REPRO_SAMPLE)
    assert {row["observation_date"] for row in probe} == set(
        task.HISTORICAL_REPRO_SAMPLE
    )
    for date in task.HISTORICAL_REPRO_SAMPLE:
        pair = [row for row in probe if row["observation_date"] == date]
        assert {row["attempt"] for row in pair} == {"1", "2"}
        assert pair[0]["raw_response_hash"] == pair[1]["raw_response_hash"]
        assert pair[0]["normalized_payload_hash"] == pair[1][
            "normalized_payload_hash"
        ]
        assert {row["raw_hash_deterministic"] for row in pair} == {"true"}
        assert {
            row["normalized_values_deterministic"] for row in pair
        } == {"true"}
        assert {
            row["status"] for row in pair
        } == {"reproducible_wrong_series_schema"}


def test_timestamped_endpoint_has_expiry_nodes_not_required_pair() -> None:
    probe = rows("historical_query_reproducibility.csv")
    symbols = set(probe[0]["returned_symbols"].split("|"))
    assert symbols == set(task.EXPECTED_TERM_NODE_SYMBOLS)
    assert "VIX" not in symbols
    assert "VIX3M" not in symbols
    assert {row["required_VIX_present"] for row in probe} == {"false"}
    assert {row["required_VIX3M_present"] for row in probe} == {"false"}
    assert {row["required_pair_values_available"] for row in probe} == {"false"}
    publication = rows("publication_timing_reconciliation.csv")
    assert {row["VIX"] for row in publication} == {""}
    assert {row["VIX3M"] for row in publication} == {""}
    assert {row["authorized_execution_session"] for row in publication} == {""}


def test_daily_histories_have_required_series_but_no_intraday_timestamp() -> None:
    manifest = rows("cboe_point_in_time_manifest.csv")
    assert len(manifest) == 3
    term = next(row for row in manifest if row["endpoint_id"] == "Cboe_delayed_quotes_term_structure")
    assert term["payload_has_generation_times"] == "true"
    assert term["point_in_time_gate_eligible"] == "false"
    assert term["status"] == "timestamped_but_wrong_series_schema"
    daily = [row for row in manifest if row["payload_frequency"] == "daily_OHLC"]
    assert {row["returned_series"] for row in daily} == {"VIX", "VIX3M"}
    assert {row["payload_has_generation_times"] for row in daily} == {"false"}
    assert {row["point_in_time_gate_eligible"] for row in daily} == {"false"}


def test_strategy_contract_and_methodology_boundary_remain_frozen() -> None:
    strategy = rows("strategy_cards.csv")[0]
    parameters = json.loads(strategy["parameters"])
    assert parameters["ratio"] == "VIX/VIX3M"
    assert parameters["median_length"] == 5
    assert parameters["thresholds"] == [0.96, 1.02]
    assert parameters["execution"] == "following_regular_session_close"
    methodology = rows("methodology_boundary_log.csv")
    assert len(methodology) == 1
    assert methodology[0]["effective_date"] == "2025-02-10"
    assert methodology[0]["diagnostic_only"] == "true"
    assert methodology[0]["strategy_rule_changed"] == "false"
    assert methodology[0]["thresholds_changed"] == "false"
    assert methodology[0]["period_variant_created"] == "false"


def test_controls_and_entities_remain_separate() -> None:
    assert len(rows("source_library_records.csv")) == 1
    assert len(rows("strategy_cards.csv")) == 1
    assert len(rows("benchmark_reference_log.csv")) == 6
    assert len(rows("data_capability_task_log.csv")) == 1
    assert len(rows("process_task_log.csv")) == 1
    assert {row["entity_type"] for row in rows("benchmark_reference_log.csv")} == {
        "benchmark_reference"
    }
    assert {
        row["performance_executed"]
        for row in rows("benchmark_reference_log.csv")
    } == {"false"}


def test_no_performance_signal_holdings_turnover_or_cost_is_calculated() -> None:
    assert rows("all_trial_results.csv") == []
    assert rows("control_results.csv") == []
    assert rows("chronological_half_results.csv") == []
    assert rows("portfolio_contribution_results.csv") == []
    assert rows("state_signal_diagnostics.csv") == []
    turnover = rows("turnover_cost_reconciliation.csv")
    assert len(turnover) == 1
    assert turnover[0]["actual_holdings_model_executed"] == "false"
    assert turnover[0]["one_way_turnover"] == ""
    assert turnover[0]["transaction_cost"] == ""


def test_prior_block_and_protected_state_are_preserved() -> None:
    check = json_payload("consistency_check.json")
    assert check["overall_pass"] is True
    assert check["prior_ALFRED_block_visible"] is True
    assert check["prior_trial_id"] == task.PRIOR_TRIAL_ID
    assert check["prior_outcome"] == "inconclusive_data_issue"
    assert check["prior_failure_reason"] == "data_or_comparability_failure"
    assert check["prior_evidence_unchanged"] is True
    assert check["protected_state_unchanged"] is True
    assert check["canonical_cache_unchanged"] is True
    assert check["source_attachment_unchanged"] is True
    assert not any(check["forbidden_actions"].values())


def test_outcome_and_next_action_are_exact() -> None:
    outcome = rows("outcome_summary.csv")
    failure = rows("failure_reasons.csv")
    actions = rows("next_actions.csv")
    assert len(outcome) == len(failure) == len(actions) == 1
    assert outcome[0]["outcome"] == "inconclusive_data_issue"
    assert outcome[0]["failure_reason"] == "data_or_comparability_failure"
    assert outcome[0]["child_trial_created"] == "false"
    assert outcome[0]["performance_executed"] == "false"
    assert failure[0]["prior_ALFRED_block_preserved"] == "true"
    assert actions[0]["exact_next_action"] == (
        "direction_owner_select_next_targeted_family_sprint_v1"
    )
    assert actions[0]["execute_in_this_task"] == "false"


def test_normalization_is_deterministic_and_does_not_relabel_nodes() -> None:
    payload = {
        "timestamp": "2025-02-10 21:15:00",
        "data": {
            "expirations": [
                {"symbol": "VIX2", "month": 2, "expirationDate": "20-Mar-2025"},
                {"symbol": "VIX1", "month": 1, "expirationDate": "20-Feb-2025"},
            ],
            "prices": [
                {
                    "index_symbol": "VIX2",
                    "price_interval": "02/10/2025 15:14:00",
                    "price": 19.0,
                    "price_time": "02/10/2025 15:14:47",
                },
                {
                    "index_symbol": "VIX1",
                    "price_interval": "02/10/2025 15:14:00",
                    "price": 17.0,
                    "price_time": "02/10/2025 15:14:46",
                },
            ],
        },
    }
    first = task.normalized_term_payload(payload)
    second = task.normalized_term_payload(payload)
    assert task.prior.canonical_hash(first) == task.prior.canonical_hash(second)
    assert task.returned_symbols(payload) == ("VIX1", "VIX2")
    assert "VIX" not in task.returned_symbols(payload)
    assert "VIX3M" not in task.returned_symbols(payload)
