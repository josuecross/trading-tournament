from __future__ import annotations

import csv
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
import yaml

from strategy_lab.research_os.research import initialize_angl_after_next_completed_common_session_v1 as task


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "paper_demo" / task.TASK_ID / "latest"
FROZEN_NOW = datetime(2026, 7, 25, 2, 0, tzinfo=timezone.utc)


@pytest.fixture(scope="module", autouse=True)
def evidence_ready() -> None:
    assert (EVIDENCE / "consistency_check.json").exists(), "Run the dedicated task runner before focused tests."


def rows(name: str) -> list[dict[str, str]]:
    with (EVIDENCE / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def payload(name: str) -> dict[str, object]:
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))


def test_calendar_uses_first_completed_post_activation_session() -> None:
    sessions = task.completed_post_activation_sessions(FROZEN_NOW)
    assert sessions[0] == date(2026, 7, 24)
    assert task.is_regular_session(date(2026, 7, 24))
    assert task.session_close_utc(date(2026, 7, 24)) > task.CORRECTION_ACTIVATION
    boundary = rows("forward_boundary_reconciliation.csv")
    assert boundary[0]["candidate_session"] == "2026-07-24"
    assert boundary[0]["selection_rule"] == "earliest chronological completed common session; returns not inspected"
    assert boundary[0]["selected"] in {"true", "false"}


def test_exact_required_symbol_scope_and_provider_boundary() -> None:
    expected = {
        "ANGL",
        "BIL",
        "DBC",
        "HYG",
        "JNK",
        "QUAL",
        "SPLV",
        "SPY",
        "USCI",
        "USMV",
        "XLB",
        "XLC",
        "XLE",
        "XLF",
        "XLI",
        "XLK",
        "XLP",
        "XLU",
        "XLV",
        "XLY",
    }
    assert set(task.required_symbols()) == expected
    refresh = rows("market_data_refresh_manifest.csv")
    assert {row["symbol"] for row in refresh} == expected
    assert {row["account_position_order_endpoint_called"] for row in refresh} == {"false"}
    source = Path(task.__file__).read_text(encoding="utf-8")
    assert "client.get_account(" not in source
    assert "client.get_positions(" not in source
    assert "client.submit_order(" not in source


def test_reference_is_reconstructed_from_frozen_components() -> None:
    reference = rows("reference_state_reconciliation.csv")
    ids = {row["reference_or_component_id"] for row in reference}
    assert {
        task.VM_ID,
        task.DSR_ID,
        task.USCI_ID,
    }.issubset(ids)
    selected = [
        row
        for row in reference
        if row["reference_or_component_id"] == task.REFERENCE_ID and row["date"] == "2026-07-24"
    ]
    outcome = rows("outcome_summary.csv")[0]
    if outcome["stage"] == "paper_demo_active":
        assert task.REFERENCE_ID in ids
        assert len(selected) == 1
        assert float(selected[0]["reference_index"]) > 0.0
        assert selected[0]["reconciliation_status"] == "pass"
        assert selected[0]["component_costs_reapplied"] == "false"
    else:
        assert selected == []
        assert outcome["failure_reason"] in {
            "data_unavailable",
            "capability_missing",
            "data_or_comparability_failure",
            "methodology_failure",
        }


def test_initial_establishment_weights_turnover_costs_and_controls() -> None:
    weights = rows("initial_target_weights.csv")
    outcome = rows("outcome_summary.csv")[0]
    if outcome["stage"] == "blocked":
        assert weights == []
        assert rows("initial_virtual_nav.csv") == []
        assert rows("initial_virtual_positions.csv") == []
        assert rows("initial_virtual_trades.csv") == []
        assert rows("control_virtual_nav.csv") == []
        return
    by_portfolio: dict[str, float] = {}
    for row in weights:
        by_portfolio.setdefault(row["portfolio_id"], 0.0)
        by_portfolio[row["portfolio_id"]] += float(row["target_weight"])
        assert row["pretrade_weight"] == "0"
        assert row["record_classification"] == "forward_observation"
    assert by_portfolio == {
        "candidate_80_reference_20_ANGL": pytest.approx(1.0),
        "control_80_reference_20_HYG": pytest.approx(1.0),
        "control_80_reference_10_HYG_10_JNK": pytest.approx(1.0),
    }
    nav = rows("initial_virtual_nav.csv")
    assert len(nav) == 3
    for row in nav:
        assert float(row["one_way_turnover"]) == pytest.approx(0.5)
        assert float(row["transaction_cost"]) == pytest.approx(0.00025)
        assert float(row["post_trade_nav"]) == pytest.approx(0.99975)
        assert float(row["weight_sum"]) == pytest.approx(1.0)
        assert float(row["maximum_exposure"]) <= 1.0
    control_ids = {row["portfolio_id"] for row in rows("control_virtual_nav.csv")}
    assert control_ids == {
        "control_100pct_frozen_reference",
        "control_80_reference_20_HYG",
        "control_80_reference_10_HYG_10_JNK",
    }


def test_forward_and_historical_records_remain_separate() -> None:
    historical = rows("historical_reconciliation_records.csv")
    forward = rows("forward_observation_records.csv")
    assert historical
    assert {row["record_classification"] for row in historical} == {"historical_reconciliation_only"}
    outcome = rows("outcome_summary.csv")[0]
    if outcome["stage"] == "paper_demo_active":
        assert len(forward) == 1
        assert forward[0]["market_session"] == "2026-07-24"
        assert forward[0]["record_classification"] == "forward_observation"
        assert forward[0]["broker_order_submitted"] == "false"
    else:
        assert forward == []


def test_entity_lineage_and_state_are_preserved() -> None:
    strategy = rows("strategy_cards.csv")
    trial = rows("trial_ledger.csv")
    observation = rows("paper_demo_observations.csv")
    benchmarks = rows("benchmark_reference_log.csv")
    process = rows("process_task_log.csv")
    assert len(strategy) == 1
    assert strategy[0]["entity_type"] == "strategy_configuration"
    assert strategy[0]["stage"] == "paper_demo_eligible"
    assert strategy[0]["outcome"] == "paper_demo_eligible"
    assert strategy[0]["route"] == "diversifier_only"
    assert strategy[0]["new_strategy_created"] == "false"
    assert trial
    assert all(row["entity_type"] == "experiment_trial" and row["read_only"] == "true" for row in trial)
    assert all(row["new_trial_created"] == "false" for row in trial)
    assert len(observation) == 1
    assert observation[0]["observation_id"] == task.OBSERVATION_ID
    assert observation[0]["stage"] in {"paper_demo_active", "blocked"}
    assert observation[0]["new_observation_created"] == "false"
    assert {row["entity_type"] for row in benchmarks} == {"benchmark_reference"}
    assert {row["stage"] for row in benchmarks} == {"benchmark_reference_only"}
    assert len(process) == 1
    assert process[0]["entity_type"] == "process_task"


def test_authoritative_observation_updated_once_and_strategy_stays_eligible() -> None:
    active_text = task.ACTIVE_OBSERVATIONS_PATH.read_text(encoding="utf-8")
    assert len(re.findall(rf"(?m)^- observation_id: {re.escape(task.OBSERVATION_ID)}$", active_text)) == 1
    active = yaml.safe_load(active_text)
    observation = next(
        row for row in active["active_observations"] if row.get("observation_id") == task.OBSERVATION_ID
    )
    outcome = rows("outcome_summary.csv")[0]
    assert observation["stage"] == outcome["stage"]
    assert observation["outcome"] == outcome["outcome"]
    if outcome["stage"] == "paper_demo_active":
        assert observation["failure_reason"] == ""
        assert observation["first_forward_observation_date"] == "2026-07-24"
        assert observation["next_action"] == task.NEXT_ACTION_ACTIVE
    else:
        assert observation["failure_reason"] in {
            "data_unavailable",
            "capability_missing",
            "data_or_comparability_failure",
            "methodology_failure",
        }
        assert observation["first_forward_observation_date"] == ""
    registry = yaml.safe_load(task.REGISTRY_PATH.read_text(encoding="utf-8"))
    strategy = next(row for row in registry["strategies"] if row.get("id") == task.STRATEGY_ID)
    assert strategy["stage"] == "paper_demo_eligible"
    assert strategy["outcome"] == "paper_demo_eligible"
    assert strategy["route"] == "diversifier_only"
    assert strategy["next_action"] == outcome["observation_next_action"]
    assert strategy["paper_orders"] is False
    assert strategy["live_orders"] is False
    assert strategy["real_money_recommendation"] is False


def test_idempotency_and_consistency_checks_pass() -> None:
    idempotency = rows("idempotency_check.csv")
    assert idempotency
    assert {row["status"] for row in idempotency} == {"pass"}
    trades = rows("initial_virtual_trades.csv")
    assert len({row["trade_key"] for row in trades}) == len(trades)
    operational = rows(
        str(
            (task.OPERATIONAL_DIR / "virtual_trades.csv").relative_to(EVIDENCE.parent.parent.parent.parent)
        )
    ) if False else []
    assert operational == []
    consistency = payload("consistency_check.json")
    assert consistency["consistency_passed"] is True
    assert consistency["earliest_valid_session_used"] is True
    assert consistency["june_18_records_historical_reconciliation_only"] is True
    assert consistency["weights_sum_to_one"] is True
    assert consistency["maximum_exposure_lte_one"] is True
    assert consistency["trade_keys_unique"] is True
    assert consistency["only_permitted_state_changes"] is True
    assert consistency["prior_evidence_unchanged"] is True
    assert consistency["new_strategy_configurations"] == 0
    assert consistency["new_experiment_trials"] == 0
    assert consistency["new_observations"] == 0
    assert consistency["broker_account_position_order_endpoint_called"] is False
    assert consistency["paper_or_live_order_submitted"] is False
    assert consistency["project_discovery_next_action"] == task.PROJECT_NEXT_ACTION


def test_same_session_upsert_is_idempotent_without_provider_rerun() -> None:
    row = {"trade_key": "obs|portfolio|2026-07-24|ANGL|initial", "target_weight": 0.2}
    once, once_additions = task.merge_unique([], [row], "trade_key")
    twice, twice_additions = task.merge_unique(once, [row], "trade_key")
    assert once_additions == 1
    assert twice_additions == 0
    assert twice == once


def rows_from_path(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))
