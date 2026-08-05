from __future__ import annotations

import csv
import json
from datetime import date

import numpy as np
import pandas as pd
import yaml

from strategy_lab.research_os.research import (
    activate_decelerated_psar_prospective_validation_v1 as task,
)


OUTPUT = task.OUTPUT_DIR


def rows(name: str) -> list[dict[str, str]]:
    with (OUTPUT / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def payload(name: str) -> dict:
    return json.loads((OUTPUT / name).read_text(encoding="utf-8"))


def manifest() -> dict:
    return yaml.safe_load(
        (OUTPUT / "activation_manifest.yaml").read_text(encoding="utf-8")
    )


def test_required_outputs_and_deferred_entity_counts() -> None:
    assert {path.name for path in OUTPUT.iterdir() if path.is_file()} == (
        task.REQUIRED_OUTPUTS
    )
    value = manifest()
    assert value["outcome"] == task.DEFERRED
    assert value["failure_reason"] == "data_or_comparability_failure"
    assert value["exact_next_action"] == task.NEXT_DEFERRED
    assert value["strategy_configurations_created"] == 0
    assert value["strategy_configurations_updated"] == 0
    assert value["experiment_trials_created"] == 0
    assert value["validation_observations_created"] == 0
    assert value["paper_demo_observations_created"] == 0
    assert value["initialization_records_created"] == 0
    assert value["completed_validation_performance_rows"] == 0


def test_design_and_future_trial_identity_reconcile_without_activation() -> None:
    reconciliation = rows("design_reconciliation.csv")
    before_after = rows("future_trial_before_after.csv")
    assert reconciliation
    assert {row["status"] for row in reconciliation} == {"pass"}
    assert len(before_after) == 1
    assert before_after[0]["trial_id"] == task.TRIAL_ID
    assert before_after[0]["before_executed"] == "false"
    assert before_after[0]["before_activated"] == "false"
    assert before_after[0]["after_status"] == "not_created"
    assert before_after[0]["after_executed_trial_created"] == "false"
    assert before_after[0]["after_validation_observation_created"] == "false"
    assert before_after[0]["prior_design_packet_rewritten"] == "false"


def test_exact_symbol_scope_and_initialization_requirements_remain_frozen() -> None:
    scope = rows("required_symbol_scope.csv")
    history = rows("initialization_history_requirements.csv")
    assert tuple(row["symbol"] for row in scope) == task.SYMBOLS
    assert len(scope) == 17
    assert {row["frozen_before_provider_access"] for row in scope} == {"true"}
    assert {row["canonical_cache_modified"] for row in scope} == {"false"}
    assert {row["prospective_stream_only"] for row in scope} == {"true"}
    assert len(history) == 7
    assert {row["requested_start"] for row in history} == {"2007-01-03"}
    assert {row["selected_from_performance"] for row in history} == {"false"}
    assert {row["historical_validation_rows_created"] for row in history} == {
        "0"
    }


def test_consumed_provider_cycle_is_recorded_without_retry() -> None:
    attempts = rows("provider_attempt_log.csv")
    data_task = rows("data_capability_task_log.csv")
    assert len(attempts) == 1
    assert attempts[0]["attempted"] == "true"
    assert attempts[0]["status"] == (
        "cycle_consumed_results_not_admitted_after_local_"
        "post_acquisition_methodology_error"
    )
    assert attempts[0]["network_calls_previously_consumed"] == "true"
    assert attempts[0]["network_calls_in_resume_run"] == "0"
    assert attempts[0]["order_endpoint_called"] == "false"
    assert "AttributeError" in attempts[0]["error"]
    assert len(data_task) == 1
    assert data_task[0]["stage"] == "blocked"
    assert data_task[0]["historical_cache_mutation"] == "false"


def test_no_trial_observation_snapshot_or_initialization_was_created() -> None:
    assert rows("validation_trial_record.csv") == []
    assert rows("validation_observation_record.csv") == []
    assert rows("portfolio_initialization_record.csv") == []
    assert rows("immutable_snapshot_manifest.csv") == []
    assert rows("candidate_state_initialization.csv") == []
    assert rows("comparator_state_initialization.csv") == []
    assert rows("frozen_reference_state_initialization.csv") == []
    assert rows("retrieval_reproducibility.csv") == []
    report = (OUTPUT / "activation_report.md").read_text(encoding="utf-8")
    assert "did not yield an admissible duplicate immutable snapshot set" in report
    assert "no raw or normalized snapshot was admitted" in report


def test_frame_reproducibility_contract_is_exact() -> None:
    frame = pd.DataFrame(
        {
            "trading_date": ["2026-07-27", "2026-07-28"],
            "adjusted_open": [100.0, 101.0],
            "adjusted_high": [102.0, 103.0],
            "adjusted_low": [99.0, 100.0],
            "adjusted_close": [101.0, 102.0],
            "adjusted_volume": [1_000.0, 1_100.0],
        }
    )
    left = {symbol: frame.copy() for symbol in task.SYMBOLS}
    right = {symbol: frame.copy() for symbol in task.SYMBOLS}
    result, passed = task.frames_reproduce(left, right)
    assert passed is True
    assert len(result) == len(task.SYMBOLS)
    assert {row["reproducibility_status"] for row in result} == {"pass"}
    right["SPY"].loc[1, "adjusted_close"] = 102.01
    _result, changed_pass = task.frames_reproduce(left, right)
    assert changed_pass is False


def test_frozen_psar_state_initializer_is_deterministic() -> None:
    dates = pd.bdate_range("2025-01-02", periods=320)
    base = 100.0 + np.linspace(0.0, 30.0, len(dates))
    wave = 2.0 * np.sin(np.arange(len(dates)) / 11.0)
    close = base + wave
    frame = pd.DataFrame(
        {
            "trading_date": dates.date.astype(str),
            "adjusted_open": close - 0.2,
            "adjusted_high": close + 1.0,
            "adjusted_low": close - 1.0,
            "adjusted_close": close,
            "adjusted_volume": np.full(len(dates), 1_000_000.0),
        }
    )
    through = date.fromisoformat(frame.iloc[-1]["trading_date"])
    first, _path = task.psar_state(frame, through, True)
    second, _path = task.psar_state(frame, through, True)
    assert first == second
    assert first["target"] in (
        {"SPY": 1.0, "BIL": 0.0},
        {"SPY": 0.0, "BIL": 1.0},
    )
    assert 0.02 <= first["AF"] <= 0.20
    assert first["trend_state"] in {"uptrend", "downtrend"}


def test_consistency_proves_protected_state_and_zero_activity() -> None:
    check = payload("consistency_check.json")
    assert check["overall_pass"] is True
    assert check["design_reconciliation_pass"] is True
    assert check["future_trial_identity_unused_before_activation"] is True
    assert check["all_activation_gates_pass"] is False
    assert check["experiment_trials_created"] == 0
    assert check["validation_observations_created"] == 0
    assert check["completed_validation_performance_rows"] == 0
    assert check["historical_backfill_performed"] is False
    assert check["historical_validation_performance_calculated"] is False
    assert check["protected_state_unchanged"] is True
    assert check["historical_canonical_caches_unchanged"] is True
    assert check["prior_PSAR_evidence_unchanged"] is True
    assert check["design_packet_unchanged"] is True
    assert check["order_endpoint_called"] is False
    assert check["broker_submission"] is False
    assert check["paper_order_submission"] is False
    assert check["real_money_authorization"] is False
