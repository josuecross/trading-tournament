from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

import run_approved_cache_batch_3_discovery as batch3
import run_parallel_discovery_approved_cache_batch as base


def write_price_cache(root: Path, symbol: str, periods: int = 620, start: str = "2021-01-01", drift: float = 0.0002) -> None:
    dates = pd.bdate_range(start, periods=periods)
    prices = [50.0 + len(symbol)]
    for idx in range(1, periods):
        prices.append(prices[-1] * (1 + drift + 0.0002 * ((idx % 9) - 4)))
    target = root / "data" / "cache" / f"{symbol}.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"date": dates, "adj_close": prices, "close": prices}).to_csv(target, index=False)


def write_required_cache(root: Path) -> None:
    for offset, symbol in enumerate(batch3.required_symbols()):
        if symbol == "BIL":
            write_price_cache(root, symbol, drift=0.00002)
        elif symbol == "XLC":
            write_price_cache(root, symbol, periods=360, start="2022-01-03", drift=0.00018)
        else:
            write_price_cache(root, symbol, drift=0.00012 + offset * 0.000008)


def write_symbol_map(root: Path) -> None:
    rows = [{"symbol": symbol, "allowed_for_strategy": True, "allowed_for_benchmark": True} for symbol in sorted(batch3.required_symbols())]
    rows.append({"symbol": "DBC", "allowed_for_strategy": False, "allowed_for_benchmark": True})
    path = root / base.SYMBOL_MAP_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({"symbols": rows}, sort_keys=False), encoding="utf-8")


def registry_row(row_id: str, active: bool, status: str, decision: str) -> dict[str, object]:
    return {
        "id": row_id,
        "display_name": row_id,
        "lane": "paper_forward" if active else "profit_exploration",
        "instrument_family": "ETF",
        "strategy_family": "test_family",
        "version": "v1",
        "parent_id": "",
        "credibility_tier": "tier4_paper_forward" if active else "tier2_exploratory",
        "status": status,
        "role": "test",
        "rules_frozen": active,
        "frozen": active,
        "paper_forward_active": active,
        "implementation_status": "implemented" if active else "implemented_research_sample",
        "data_source": "existing_adjusted_etf_cache",
        "evidence_source": "test",
        "latest_evidence_path": "evidence/test/latest",
        "latest_known_result_summary": "test",
        "allowed_next_action": "observe_only" if active else "research_sample_review",
        "forbidden_next_actions": ["promote_to_real_money", "run_candidate_exhaustive"],
        "risk_framework_status": "paper_forward_allowed" if active else "research_sample_only",
        "paper_forward_allowed_by_risk_framework": active,
        "real_money_recommendation": False,
        "promotion_blockers": "none",
        "promotion_requirements": "none",
        "demotion_or_kill_criteria": "none",
        "notes": "test",
        "strategy_id": row_id,
        "family": "test_family",
        "instrument_lane": "ETF",
        "evidence_tier": "test",
        "current_status": status,
        "allowed_next_actions": ["observe_only"] if active else ["research_sample_review"],
        "candidate_exhaustive_run": False,
        "candidate_exhaustive_recommended": False,
        "promotion_review_required": False,
        "promotion_decision": decision,
        "promotion_reason": "test",
        "primary_failure_mode": "not_flagged",
        "duplication_risk": "not_flagged",
        "risk_budget_status": "test",
        "evidence_needed": "none",
        "duplicate_of": "",
        "blocked_reason": "",
    }


def write_registry(root: Path) -> None:
    rows = [
        registry_row(base.VM_ID, True, "active_paper_demo_observation", "paper_forward_activation_recovered"),
        registry_row(base.DSR_ID, True, "active_paper_demo_observation", "paper_forward_activation_recovered"),
        registry_row(base.SPY_200D_ID, True, "active_observation", "keep_frozen_control"),
        registry_row(base.TOP2_ID, False, "mark_duplicate_or_near_duplicate", "mark_duplicate_or_near_duplicate"),
        registry_row(base.TOP3_ID, False, "mark_duplicate_or_near_duplicate", "mark_duplicate_or_near_duplicate"),
        registry_row("qvm_quality_value_momentum_risk_adjusted_top2_v1", False, "mark_too_risky", "mark_too_risky"),
        registry_row("qvm_quality_value_momentum_top2_v1", False, "mark_duplicate_or_near_duplicate", "mark_duplicate_or_near_duplicate"),
        registry_row("lvq_lowvol_quality_spy_regime_v1", False, "keep_watchlist", "keep_watchlist"),
    ]
    path = root / batch3.REGISTRY_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({"registry": {"schema_version": 1, "research_only": True}, "strategies": rows}, sort_keys=False), encoding="utf-8")


def write_state(root: Path) -> None:
    readiness = root / "evidence" / "approved_etf_cache_readiness" / "latest" / "approved_etf_cache_readiness_manifest.json"
    readiness.parent.mkdir(parents=True, exist_ok=True)
    readiness.write_text(json.dumps({"missing_symbols": []}), encoding="utf-8")

    recompute = root / "evidence" / "active_strategy_evidence_recompute" / "latest" / "active_strategy_recompute_manifest.json"
    recompute.parent.mkdir(parents=True, exist_ok=True)
    recompute.write_text(json.dumps({"decisions": {base.VM_ID: "active_evidence_confirmed_with_minor_deltas", base.DSR_ID: "active_evidence_material_mismatch_manual_review"}}), encoding="utf-8")

    batch2_manifest = root / "evidence" / "parallel_research_discovery" / "approved_cache_batch_2" / "latest" / "approved_cache_batch_2_manifest.json"
    batch2_manifest.parent.mkdir(parents=True, exist_ok=True)
    batch2_manifest.write_text(json.dumps({"candidate_exhaustive_run": False, "best_row": "benchmark_quality_lowvol_equal_weight_v1", "promotion_candidates": 0}), encoding="utf-8")


def prepared_root(tmp_path: Path) -> Path:
    write_symbol_map(tmp_path)
    write_registry(tmp_path)
    write_state(tmp_path)
    write_required_cache(tmp_path)
    return tmp_path


@pytest.fixture(scope="module")
def audited_fixture(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    root = prepared_root(tmp_path_factory.mktemp("batch3"))
    result = batch3.run_batch_3(root, strict_state=True)
    return {"root": root, "result": result}


def test_only_approved_symbols_are_used() -> None:
    allowed = set(batch3.required_symbols())
    for spec in batch3.specs():
        assert set(spec["symbols"]) <= allowed


def test_forbidden_symbols_are_rejected() -> None:
    with pytest.raises(ValueError):
        batch3.validate_spec_symbols({"strategy_id": "bad", "symbols": ["SPY", "DBC"]}, {"SPY", "BIL"})


def test_fixed_rules_are_defined_before_running() -> None:
    assert len(batch3.specs()) == 11
    assert all(spec.get("rule") for spec in batch3.specs())
    assert {spec["strategy_id"] for spec in batch3.specs()} == {
        "gwcb_qvm_70_30_cash_brake_v1",
        "gwcb_qvm_60_40_cash_brake_v1",
        "gwcb_spy_qqq_mtum_cash_switch_v1",
        "drgd_growth_or_defense_top2_v1",
        "drgd_growth_80_defense_20_v1",
        "drgd_qqq_canary_defensive_v1",
        "ddg_growth_top2_predefined_guard_v1",
        "ddg_growth_quality_predefined_guard_v1",
        "ddg_balanced_growth_defense_guard_v1",
        "benchmark_qvm_60_40_bil_v1",
        "benchmark_growth_cash_50_50_v1",
    }


def test_predefined_drawdown_guard_allowed_but_not_optimized() -> None:
    guards = [spec for spec in batch3.specs() if "guard_threshold" in spec]
    assert {(spec["guard_symbol"], spec["guard_threshold"]) for spec in guards} == {("SPY", -0.10), ("QQQ", -0.12)}
    assert all("parameter_grid" not in spec and "optimized" not in spec and "tuned" not in spec for spec in guards)


def test_no_candidate_exhaustive_is_run(audited_fixture: dict[str, object]) -> None:
    output = Path(audited_fixture["result"]["output_dir"])
    manifest = json.loads((output / "approved_cache_batch_3_manifest.json").read_text(encoding="utf-8"))
    assert audited_fixture["result"]["consistency"]["no_candidate_exhaustive_run"] is True
    assert manifest["candidate_exhaustive_run"] is False


def test_no_paper_forward_active_flag_is_set(audited_fixture: dict[str, object]) -> None:
    registry = yaml.safe_load((audited_fixture["root"] / batch3.REGISTRY_PATH).read_text(encoding="utf-8"))
    ids = {spec["strategy_id"] for spec in batch3.specs()}
    assert all(row["paper_forward_active"] is False for row in registry["strategies"] if row["id"] in ids)


def test_no_real_money_recommendation_is_created(audited_fixture: dict[str, object]) -> None:
    registry = yaml.safe_load((audited_fixture["root"] / batch3.REGISTRY_PATH).read_text(encoding="utf-8"))
    ids = {spec["strategy_id"] for spec in batch3.specs()}
    assert all(row["real_money_recommendation"] is False for row in registry["strategies"] if row["id"] in ids)


def test_promotion_candidates_are_separate_from_watchlist_rows(audited_fixture: dict[str, object]) -> None:
    output = Path(audited_fixture["result"]["output_dir"])
    promotions = pd.read_csv(output / "approved_cache_batch_3_promotion_candidates.csv")
    watchlist = pd.read_csv(output / "approved_cache_batch_3_watchlist.csv")
    assert set(promotions.get("strategy_id", [])) & set(watchlist.get("strategy_id", [])) == set()


def test_unavailable_benchmark_deltas_are_not_zero_filled(audited_fixture: dict[str, object]) -> None:
    output = Path(audited_fixture["result"]["output_dir"])
    deltas = pd.read_csv(output / "approved_cache_batch_3_benchmark_delta.csv")
    active_combo = deltas[deltas["benchmark_id"] == "active_combo"]
    assert not active_combo.empty
    assert set(active_combo["delta"]) == {"unavailable"}


def test_risk_buffer_too_thin_prevents_promotion() -> None:
    verdict, reason = batch3.classify(
        {"median_final_equity": 3600.0, "target_300_before_stop_rate": 0.8, "target_400_before_stop_rate": 0.6, "worst_drawdown": -575.0, "stop_hit_rate": 0.0, "risk_buffer_vs_minus_600": 25.0},
        {"risk_buffer_vs_minus_600": 10.0},
        {"delta_vs_spy_200d": 100.0, "delta_vs_spy_buy_hold": 100.0, "delta_vs_bil": 500.0},
        {"corr_vs_active_vm": 0.5, "corr_vs_active_dsr": 0.5, "corr_vs_spy_200d": 0.5},
        "growth_with_cash_brake",
    )
    assert verdict == "too_risky"
    assert "risk buffer" in reason


def test_needs_benchmark_delta_review_only_when_deltas_unavailable(audited_fixture: dict[str, object]) -> None:
    verdict, reason = batch3.classify(
        {"median_final_equity": 3600.0, "target_300_before_stop_rate": 0.8, "target_400_before_stop_rate": 0.6, "worst_drawdown": -200.0, "stop_hit_rate": 0.0, "risk_buffer_vs_minus_600": 400.0},
        {"risk_buffer_vs_minus_600": 390.0},
        {"delta_vs_spy_200d": "unavailable", "delta_vs_spy_buy_hold": 100.0, "delta_vs_bil": 500.0},
        {"corr_vs_active_vm": 0.5, "corr_vs_active_dsr": 0.5, "corr_vs_spy_200d": 0.5},
        "growth_with_cash_brake",
    )
    output = Path(audited_fixture["result"]["output_dir"])
    decisions = pd.read_csv(output / "approved_cache_batch_3_decision_log.csv")
    assert verdict == "needs_benchmark_delta_review"
    assert "unavailable" in reason
    assert "needs_benchmark_delta_review" not in set(decisions["decision"])
    assert audited_fixture["result"]["consistency"]["needs_benchmark_delta_review_only_for_missing_deltas"] is True


def test_next_action_is_explicit(audited_fixture: dict[str, object]) -> None:
    output = Path(audited_fixture["result"]["output_dir"])
    next_action = audited_fixture["result"]["next_action"]
    assert next_action in set(batch3.NEXT_ACTIONS.values())
    assert next_action in (output / "approved_cache_batch_3_next_action.md").read_text(encoding="utf-8")


def test_consistency_check_passes(audited_fixture: dict[str, object]) -> None:
    output = Path(audited_fixture["result"]["output_dir"])
    consistency = json.loads((output / "approved_cache_batch_3_consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["consistency_passed"] is True
