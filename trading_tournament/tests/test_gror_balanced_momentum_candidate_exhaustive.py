from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import yaml

import run_gror_balanced_momentum_candidate_exhaustive as gror


def write_cache(root: Path, symbol: str, drift: float) -> None:
    cache = root / "data" / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    dates = pd.bdate_range("2020-01-01", periods=520)
    prices = [100.0]
    for idx in range(1, len(dates)):
        prices.append(prices[-1] * (1.0 + drift + 0.001 * ((idx % 7) - 3) / 10.0))
    pd.DataFrame({"date": dates, "adj_close": prices, "close": prices}).to_csv(cache / f"{symbol}.csv", index=False)


def write_minimal_registry(root: Path) -> None:
    registry_dir = root / "strategy_lab"
    registry_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "registry": {
            "schema_version": 1,
            "project": "trading_tournament",
            "research_only": True,
            "real_money_recommendation": False,
            "broker_integration": False,
            "live_orders": False,
        },
        "risk_framework": {
            "active_framework": "balanced_speculative_research_v1",
            "framework_path": "risk_framework/risk_framework.yaml",
        },
        "strategies": [
            {
                "id": gror.STRATEGY_ID,
                "status": "candidate_exhaustive_queue",
                "current_status": "candidate_exhaustive_queue",
                "paper_forward_active": False,
                "real_money_recommendation": False,
                "forbidden_next_actions": [],
                "allowed_next_actions": ["create_candidate_exhaustive_prompt_for_gror_balanced_momentum_60_40_v1"],
            },
            {"id": "SPY_200d_trend_model", "status": "active_observation", "paper_forward_active": True},
        ],
    }
    (registry_dir / "strategy_registry.yaml").write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_frozen_rule_and_outputs_are_created_with_incomplete_label_when_cache_missing(tmp_path: Path) -> None:
    write_minimal_registry(tmp_path)
    result = gror.run_candidate_validation(tmp_path, run_id="test_missing", update_registry_file=False)
    latest = Path(result["latest_dir"])
    assert (latest / f"{gror.STRATEGY_ID}_frozen_rule.md").exists()
    assert (latest / f"{gror.STRATEGY_ID}_candidate_exhaustive_packet.zip").exists()
    manifest = json.loads((latest / f"{gror.STRATEGY_ID}_manifest.json").read_text(encoding="utf-8"))
    assert manifest["only_target_row_validated"] is True
    assert manifest["validation_incomplete"] is True
    assert manifest["final_decision"] == "candidate_exhaustive_evidence_incomplete"
    assert manifest["data_downloaded"] is False
    assert manifest["provider_api_called"] is False


def test_synthetic_candidate_validation_outputs_are_created(tmp_path: Path) -> None:
    write_minimal_registry(tmp_path)
    for symbol, drift in {"SPY": 0.0004, "QQQ": 0.0005, "GLD": 0.0002, "IEF": 0.0001, "BIL": 0.00002}.items():
        write_cache(tmp_path, symbol, drift)
    result = gror.run_candidate_validation(tmp_path, run_id="test_complete", update_registry_file=False)
    latest = Path(result["latest_dir"])
    assert result["validation_completed"] is True
    for name in gror.REQUIRED_OUTPUTS:
        assert (latest / name).exists()
    consistency = json.loads((latest / f"{gror.STRATEGY_ID}_consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["consistency_passed"] is True
    assert consistency["only_target_row_validated"] is True


def test_no_parameter_tuning_paper_forward_or_real_money_fields(tmp_path: Path) -> None:
    write_minimal_registry(tmp_path)
    result = gror.run_candidate_validation(tmp_path, run_id="test_safety", update_registry_file=False)
    manifest = json.loads((Path(result["latest_dir"]) / f"{gror.STRATEGY_ID}_manifest.json").read_text(encoding="utf-8"))
    assert manifest["parameter_optimization"] is False
    assert manifest["grid_search"] is False
    assert manifest["paper_forward_activation"] is False
    assert manifest["paper_forward_checkpoint"] is False
    assert manifest["real_money_recommendation"] is False
    assert manifest["broker_integration"] is False
    assert manifest["live_orders"] is False
    assert manifest["order_placement"] is False


def test_final_decision_and_next_action_are_explicit(tmp_path: Path) -> None:
    write_minimal_registry(tmp_path)
    result = gror.run_candidate_validation(tmp_path, run_id="test_decision", update_registry_file=False)
    assert result["final_decision"] in gror.FINAL_DECISIONS
    assert result["next_action"] == gror.NEXT_ACTIONS[result["final_decision"]]
    next_action_text = (Path(result["latest_dir"]) / f"{gror.STRATEGY_ID}_next_action.md").read_text(encoding="utf-8")
    assert result["next_action"] in next_action_text


def test_registry_update_keeps_forbidden_flags_false_and_spy_preserved(tmp_path: Path) -> None:
    write_minimal_registry(tmp_path)
    gror.run_candidate_validation(tmp_path, run_id="test_registry", update_registry_file=True)
    registry = yaml.safe_load((tmp_path / "strategy_lab" / "strategy_registry.yaml").read_text(encoding="utf-8"))
    rows = {row["id"]: row for row in registry["strategies"]}
    target = rows[gror.STRATEGY_ID]
    assert target["candidate_exhaustive_run"] is True
    assert target["paper_forward_active"] is False
    assert target["real_money_recommendation"] is False
    assert target["candidate_exhaustive_decision"] in gror.FINAL_DECISIONS
    assert "broker_integration" in target["forbidden_next_actions"]
    assert rows["SPY_200d_trend_model"]["status"] == "active_observation"
    assert rows["SPY_200d_trend_model"]["paper_forward_active"] is True


def test_active_observations_are_not_mutated_by_actual_incomplete_run() -> None:
    vm = Path("paper_forward_observations/paper_forward_vm_quality_lowvol_proxy_v1/active_observation.yaml")
    dsr = Path("paper_forward_observations/paper_forward_dsr_sector_equal_weight_defensive_filter_v1/active_observation.yaml")
    if not vm.exists() or not dsr.exists():
        return
    before = {vm: sha(vm), dsr: sha(dsr)}
    gror.run_candidate_validation(Path.cwd(), run_id="test_no_active_mutation", update_registry_file=False)
    assert {vm: sha(vm), dsr: sha(dsr)} == before
