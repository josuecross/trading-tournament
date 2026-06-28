from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

import run_tournament_root_cause_audit as audit


def write_fixture(root: Path) -> None:
    registry = root / audit.STRATEGY_REGISTRY_PATH
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry.write_text(
        yaml.safe_dump(
            {
                "registry": {
                    "research_only": True,
                    "real_money_recommendation": False,
                    "broker_integration": False,
                    "live_orders": False,
                },
                "strategies": [
                    {
                        "id": "paper_forward_vm_quality_lowvol_proxy_v1",
                        "strategy_id": "paper_forward_vm_quality_lowvol_proxy_v1",
                        "family": "volatility_managed_equity",
                        "timeframe": "monthly",
                        "status": "active_observation",
                        "paper_forward_active": True,
                        "latest_known_result_summary": "active paper demo",
                        "latest_evidence_path": "evidence/paper_forward_observations/vm/latest",
                    },
                    {
                        "id": "profit_combo_SPY200d_GLD_50_50_v1",
                        "strategy_id": "profit_combo_SPY200d_GLD_50_50_v1",
                        "family": "fixed_weight_combination",
                        "timeframe": "monthly",
                        "status": "active_paper_demo_observation",
                        "paper_forward_active": True,
                        "latest_known_result_summary": "SPY/GLD/BIL paper demo observation",
                        "latest_evidence_path": "evidence/paper_forward_observations/combo_SPY200d_GLD_50_50_v1/latest",
                    },
                    {
                        "id": "gror_balanced_momentum_60_40_v1",
                        "strategy_id": "gror_balanced_momentum_60_40_v1",
                        "family": "global_risk_on_risk_off_etf",
                        "timeframe": "monthly",
                        "status": "watchlist",
                        "paper_forward_active": False,
                        "candidate_exhaustive_run": True,
                        "latest_known_result_summary": "candidate_exhaustive evidence incomplete; GLD IEF BIL risk_on risk_off",
                        "risk_budget_status": "candidate_exhaustive_evidence_incomplete",
                        "latest_evidence_path": "evidence/candidate_exhaustive/gror_balanced_momentum_60_40_v1/latest",
                    },
                    {
                        "id": "portfolio_spy200d_70_gld_15_bil_15_v1",
                        "strategy_id": "portfolio_spy200d_70_gld_15_bil_15_v1",
                        "family": "fixed_weight_portfolio",
                        "timeframe": "monthly",
                        "status": "too_slow",
                        "paper_forward_active": False,
                        "latest_known_result_summary": "gold/cash defense reduced drawdown but target too slow",
                    },
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    expansion = root / audit.EXPANSION_REGISTRY_PATH
    expansion.parent.mkdir(parents=True, exist_ok=True)
    expansion.write_text(yaml.safe_dump({"metadata": {}, "candidates": []}), encoding="utf-8")
    first = root / audit.FIRST_EXPANSION_RESULTS
    first.parent.mkdir(parents=True, exist_ok=True)
    first.write_text(
        "candidate_id,discovery_outcome,decision_reason\n"
        "dmr_liquid_etf_oversold_rebound_v1,discovery_reject,underperforms benchmark\n",
        encoding="utf-8",
    )
    doc = root / "notes" / "macro.md"
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text("GLD GROR global risk risk_on risk_off IEF TLT BIL macro rotation", encoding="utf-8")


@pytest.fixture(scope="module")
def audit_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    root = tmp_path_factory.mktemp("root_cause_audit")
    write_fixture(root)
    return audit.run_tournament_root_cause_audit(root)


def output(audit_run: dict[str, object]) -> Path:
    return Path(audit_run["output_dir"])


def manifest(audit_run: dict[str, object]) -> dict[str, object]:
    return json.loads((output(audit_run) / "tournament_root_cause_manifest.json").read_text(encoding="utf-8"))


def test_audit_is_governance_only(audit_run: dict[str, object]) -> None:
    assert manifest(audit_run)["audit_only"] is True


def test_no_new_backtests_are_run(audit_run: dict[str, object]) -> None:
    assert manifest(audit_run)["new_backtests_run"] is False


def test_no_new_discovery_is_run(audit_run: dict[str, object]) -> None:
    assert manifest(audit_run)["new_discovery_run"] is False


def test_no_provider_download_occurs(audit_run: dict[str, object]) -> None:
    assert manifest(audit_run)["provider_download"] is False


def test_no_candidate_exhaustive_or_paper_forward_action(audit_run: dict[str, object]) -> None:
    loaded = manifest(audit_run)
    assert loaded["candidate_exhaustive_run"] is False
    assert loaded["paper_forward_review"] is False
    assert loaded["paper_forward_activation"] is False


def test_no_broker_live_path_is_touched(audit_run: dict[str, object]) -> None:
    loaded = manifest(audit_run)
    assert loaded["broker_path_touched"] is False
    assert loaded["live_orders"] is False


def test_gld_gror_search_report_exists(audit_run: dict[str, object]) -> None:
    assert (output(audit_run) / "gld_gror_registry_search_results.csv").exists()


def test_failure_dashboard_exists(audit_run: dict[str, object]) -> None:
    assert (output(audit_run) / "failure_reason_dashboard.csv").exists()


def test_accepted_strategy_inventory_exists(audit_run: dict[str, object]) -> None:
    assert (output(audit_run) / "accepted_strategy_inventory.csv").exists()


def test_rejected_strategy_inventory_exists(audit_run: dict[str, object]) -> None:
    assert (output(audit_run) / "rejected_strategy_inventory.csv").exists()


def test_gate_audit_exists(audit_run: dict[str, object]) -> None:
    assert (output(audit_run) / "gate_failure_summary.csv").exists()


def test_backtester_data_checklists_exist(audit_run: dict[str, object]) -> None:
    assert (output(audit_run) / "backtester_methodology_checklist.md").exists()
    assert (output(audit_run) / "data_quality_checklist.md").exists()


def test_lane_redesign_recommendations_exist(audit_run: dict[str, object]) -> None:
    assert (output(audit_run) / "lane_redesign_recommendations.md").exists()


def test_manifest_flags_match_strict_scope(audit_run: dict[str, object]) -> None:
    loaded = manifest(audit_run)
    for key, value in audit.MANIFEST_FLAGS.items():
        assert loaded[key] == value
    assert loaded["next_action"] in {
        "pre_register_gld_gror_macro_research_lane",
        "fix_backtester_or_data_issue_before_more_research",
        "revise_tournament_gates_by_lane",
        "continue_with_pre_registered_second_expansion_batch",
    }
