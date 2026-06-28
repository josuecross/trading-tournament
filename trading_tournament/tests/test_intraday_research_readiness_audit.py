from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

import run_intraday_research_readiness_audit as audit


def write_fixture(root: Path) -> None:
    registry_path = root / audit.REGISTRY_PATH
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        yaml.safe_dump(
            {
                "registry": {
                    "schema_version": 1,
                    "project": "trading_tournament",
                    "research_only": True,
                    "current_next_action": "pre_register_intraday_research_readiness_audit",
                    "real_money_recommendation": False,
                    "broker_integration": False,
                    "live_orders": False,
                },
                "strategies": [
                    {
                        "id": "paper_forward_vm_quality_lowvol_proxy_v1",
                        "status": "active_observation",
                        "paper_forward_active": True,
                        "candidate_exhaustive_run": False,
                    },
                    {
                        "id": "dual_momentum_paa_clean_v1",
                        "status": "discovery_reject",
                        "paper_forward_active": False,
                        "candidate_exhaustive_run": False,
                    },
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    roadmap = root / audit.ROADMAP_PATH
    roadmap.parent.mkdir(parents=True, exist_ok=True)
    roadmap.write_text("# Research Roadmap\n\nCurrent next action: `pre_register_intraday_research_readiness_audit`\n", encoding="utf-8")

    previous = root / audit.THIRD_EXPANSION_FAILURE_AUDIT_DIR / "third_expansion_failure_audit_manifest.json"
    previous.parent.mkdir(parents=True, exist_ok=True)
    previous.write_text(json.dumps({"next_action": "pre_register_intraday_research_readiness_audit"}), encoding="utf-8")

    for path, text in {
        audit.HISTORICAL_BARS_PATH: 'client.get_historical_bars_page(timeframe="1Day")\npd.to_datetime(x, utc=True)\n',
        audit.RUNTIME_CACHE_PATH: 'return root / f"{symbol}_1Day.csv"\n',
        audit.RUNTIME_ORCHESTRATOR_PATH: "Live mode is out of scope\nget_market_clock\norders.jsonl\n",
        audit.WEEKLY_RUNNER_PATH: "EVENT_FILES = ['order_statuses.jsonl','fills.jsonl','open_orders.jsonl']\nEMERGENCY_STOP_FILE\nreconcile_order_statuses\nsubmitted_orders.jsonl\n",
        audit.RISK_GATE_PATH: "def evaluate_risk_gate(): pass\ntarget_version_already_handled\n",
        audit.ORDER_SIZING_PATH: "notional\n",
        audit.RECONCILE_PATH: "def reconcile_order_statuses(client, order_ids): return [client.get_order_by_id(x) for x in order_ids]\n",
        audit.ALPACA_CLIENT_PATH: "Only Alpaca paper mode is supported\nget_market_clock\nlist_open_orders\nsubmit_order\n",
        audit.RISK_LIMITS_PATH: "max_order_notional: 5\nmax_total_notional_per_run: 25\n",
        audit.PROJECT_CONFIG_PATH: "data:\n  intraday_dir: data/intraday\n",
    }.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")


@pytest.fixture(scope="module")
def audit_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    root = tmp_path_factory.mktemp("intraday_readiness_audit")
    write_fixture(root)
    before = yaml.safe_load((root / audit.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result = audit.run_intraday_research_readiness_audit(root)
    after = yaml.safe_load((root / audit.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result["strategies_before"] = before
    result["strategies_after"] = after
    return result


def output(audit_run: dict[str, Any]) -> Path:
    return Path(audit_run["output_dir"])


def manifest(audit_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(audit_run) / "intraday_readiness_manifest.json").read_text(encoding="utf-8"))


def consistency(audit_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(audit_run) / "intraday_readiness_consistency_check.json").read_text(encoding="utf-8"))


def test_audit_only_mode(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["audit_only"] is True


def test_no_intraday_strategy_backtests(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["intraday_strategy_backtests_run"] is False


def test_no_new_discovery(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["new_discovery_run"] is False


def test_no_new_performance_metrics(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["new_performance_metrics_computed"] is False


def test_no_provider_download(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["provider_download"] is False


def test_no_intraday_data_download(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["intraday_data_downloaded"] is False


def test_no_candidate_exhaustive(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["candidate_exhaustive_run"] is False


def test_no_paper_forward_action(audit_run: dict[str, Any]) -> None:
    loaded = manifest(audit_run)
    assert loaded["paper_forward_review"] is False
    assert loaded["paper_forward_activation"] is False


def test_no_broker_orders_submitted(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["broker_orders_submitted"] is False


def test_no_broker_orders_cancelled(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["broker_orders_cancelled"] is False


def test_no_live_orders(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["live_orders"] is False


def test_no_strategy_state_changes(audit_run: dict[str, Any]) -> None:
    assert audit_run["strategies_before"] == audit_run["strategies_after"]


def test_data_support_audit_exists(audit_run: dict[str, Any]) -> None:
    assert (output(audit_run) / "intraday_data_support_audit.md").exists()


def test_signal_timing_audit_exists(audit_run: dict[str, Any]) -> None:
    assert (output(audit_run) / "intraday_signal_timing_audit.md").exists()


def test_fill_slippage_audit_exists(audit_run: dict[str, Any]) -> None:
    assert (output(audit_run) / "intraday_fill_slippage_audit.md").exists()


def test_order_logging_reconciliation_audit_exists(audit_run: dict[str, Any]) -> None:
    assert (output(audit_run) / "intraday_order_logging_reconciliation_audit.md").exists()


def test_position_risk_audit_exists(audit_run: dict[str, Any]) -> None:
    assert (output(audit_run) / "intraday_position_risk_audit.md").exists()


def test_kill_switch_audit_exists(audit_run: dict[str, Any]) -> None:
    assert (output(audit_run) / "intraday_kill_switch_audit.md").exists()


def test_small_account_operational_audit_exists(audit_run: dict[str, Any]) -> None:
    assert (output(audit_run) / "intraday_small_account_operational_audit.md").exists()


def test_candidate_suitability_file_exists(audit_run: dict[str, Any]) -> None:
    assert (output(audit_run) / "intraday_candidate_suitability.md").exists()


def test_blocker_list_exists(audit_run: dict[str, Any]) -> None:
    assert (output(audit_run) / "intraday_blocker_list.csv").exists()


def test_readiness_verdict_is_valid(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["readiness_verdict"] in audit.VALID_READINESS_VERDICTS


def test_next_action_is_valid(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["next_action"] in audit.VALID_NEXT_ACTIONS
    assert manifest(audit_run)["next_action"] == audit.NEXT_ACTION


def test_manifest_flags_match_strict_scope(audit_run: dict[str, Any]) -> None:
    loaded = manifest(audit_run)
    for key, value in audit.MANIFEST_FLAGS.items():
        assert loaded[key] == value
    assert consistency(audit_run)["consistency_passed"] is True
