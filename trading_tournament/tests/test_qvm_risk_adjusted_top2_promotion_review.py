from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

import run_parallel_discovery_approved_cache_batch as discovery
import run_qvm_risk_adjusted_top2_promotion_review as review


def write_price_cache(root: Path, symbol: str, periods: int = 620, start: str = "2021-01-01", drift: float = 0.00022) -> None:
    dates = pd.bdate_range(start, periods=periods)
    prices = [50.0 + len(symbol)]
    for idx in range(1, periods):
        prices.append(prices[-1] * (1 + drift + 0.0002 * ((idx % 9) - 4)))
    target = root / "data" / "cache" / f"{symbol}.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"date": dates, "adj_close": prices, "close": prices}).to_csv(target, index=False)


def write_required_cache(root: Path) -> None:
    for offset, symbol in enumerate(discovery.required_symbols()):
        if symbol == "BIL":
            write_price_cache(root, symbol, drift=0.00002)
        elif symbol == "XLC":
            write_price_cache(root, symbol, periods=360, start="2022-01-03", drift=0.00018)
        else:
            write_price_cache(root, symbol, drift=0.00012 + offset * 0.000008)


def write_symbol_map(root: Path) -> None:
    rows = [{"symbol": symbol, "allowed_for_strategy": True, "allowed_for_benchmark": True} for symbol in sorted(set(discovery.required_symbols()))]
    rows.append({"symbol": "DBC", "allowed_for_strategy": False, "allowed_for_benchmark": True})
    path = root / discovery.SYMBOL_MAP_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({"symbols": rows}, sort_keys=False), encoding="utf-8")


def base_registry_row(row_id: str, active: bool, status: str, decision: str) -> dict[str, object]:
    return {
        "id": row_id,
        "display_name": row_id,
        "lane": "paper_forward" if active else "profit_exploration",
        "instrument_family": "ETF",
        "strategy_family": "quality_value_momentum_blend",
        "version": "v1",
        "parent_id": "",
        "credibility_tier": "tier4_paper_forward" if active else "tier2_exploratory",
        "status": status,
        "role": "test",
        "rules_frozen": active or row_id == review.TARGET_ID,
        "frozen": active,
        "paper_forward_active": active,
        "implementation_status": "implemented_research_sample" if row_id == review.TARGET_ID else "implemented",
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
        "family": "quality_value_momentum_blend",
        "instrument_lane": "ETF",
        "evidence_tier": "test",
        "current_status": status,
        "allowed_next_actions": ["observe_only"] if active else ["research_sample_review"],
        "candidate_exhaustive_run": False,
        "candidate_exhaustive_recommended": False,
        "promotion_review_required": row_id == review.TARGET_ID,
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
        base_registry_row(discovery.VM_ID, True, "active_paper_demo_observation", "paper_forward_activation_recovered"),
        base_registry_row(discovery.DSR_ID, True, "active_paper_demo_observation", "paper_forward_activation_recovered"),
        base_registry_row(discovery.SPY_200D_ID, True, "active_observation", "keep_frozen_control"),
        base_registry_row(discovery.TOP2_ID, False, "mark_duplicate_or_near_duplicate", "mark_duplicate_or_near_duplicate"),
        base_registry_row(discovery.TOP3_ID, False, "mark_duplicate_or_near_duplicate", "mark_duplicate_or_near_duplicate"),
        base_registry_row(review.TARGET_ID, False, "promotion_review_candidate", "promotion_review_candidate"),
    ]
    path = root / review.REGISTRY_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({"registry": {"schema_version": 1, "research_only": True}, "strategies": rows}, sort_keys=False), encoding="utf-8")


def write_state_files(root: Path) -> None:
    readiness = root / "evidence" / "approved_etf_cache_readiness" / "latest" / "approved_etf_cache_readiness_manifest.json"
    readiness.parent.mkdir(parents=True, exist_ok=True)
    readiness.write_text(json.dumps({"missing_symbols": []}), encoding="utf-8")
    recompute = root / "evidence" / "active_strategy_evidence_recompute" / "latest" / "active_strategy_recompute_manifest.json"
    recompute.parent.mkdir(parents=True, exist_ok=True)
    recompute.write_text(json.dumps({"decisions": {discovery.VM_ID: "active_evidence_confirmed_with_minor_deltas", discovery.DSR_ID: "active_evidence_material_mismatch_manual_review"}}), encoding="utf-8")
    promo_dir = root / "evidence" / "parallel_research_discovery" / "new_batch_approved_cache" / "latest"
    promo_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{"strategy_id": review.TARGET_ID}]).to_csv(promo_dir / "parallel_discovery_approved_cache_promotion_candidates.csv", index=False)


def write_observations(root: Path) -> None:
    for strategy_id in [discovery.VM_ID, discovery.DSR_ID]:
        path = root / "paper_forward_observations" / strategy_id / "active_observation.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump({"observation_id": strategy_id, "paper_forward_active": True, "frozen": True}), encoding="utf-8")


def prepared_root(tmp_path: Path) -> Path:
    write_symbol_map(tmp_path)
    write_registry(tmp_path)
    write_state_files(tmp_path)
    write_observations(tmp_path)
    write_required_cache(tmp_path)
    return tmp_path


@pytest.fixture(scope="module")
def reviewed_fixture(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    root = prepared_root(tmp_path_factory.mktemp("qvm_review"))
    before = {sid: path.read_text(encoding="utf-8") for sid, path in review.active_observation_paths(root).items()}
    result = review.run_promotion_review(root, strict_state=True)
    after = {sid: path.read_text(encoding="utf-8") for sid, path in review.active_observation_paths(root).items()}
    return {"root": root, "result": result, "before": before, "after": after}


def test_target_strategy_is_correct() -> None:
    assert review.TARGET_ID == "qvm_quality_value_momentum_risk_adjusted_top2_v1"
    assert review.target_spec()["rule"] == "top_n_risk_adjusted"


def test_cache_is_used_when_available(reviewed_fixture: dict[str, object]) -> None:
    consistency = reviewed_fixture["result"]["consistency"]
    assert consistency["cache_used"] is True


def test_approved_symbols_only_are_used(tmp_path: Path) -> None:
    root = prepared_root(tmp_path)
    approved = discovery.approved_strategy_symbols(root)
    discovery.validate_spec_symbols(review.target_spec(), approved)
    assert set(review.TARGET_SYMBOLS) <= approved


def test_risk_buffer_near_minus_600_is_flagged() -> None:
    payload = {
        "diagnostics_available": True,
        "summaries": {review.TARGET_ID: {180: {"risk_buffer_vs_minus_600": 18.0, "worst_drawdown": -582.0, "stop_hit_rate": 0.0, "median_final_equity": 3500.0, "target_300_before_stop_rate": 0.6, "target_400_before_stop_rate": 0.6}}},
        "stress_summary": {180: {"worst_drawdown": -601.0}},
    }
    decision, _next_action, recommended, reason = review.decide(payload, [])
    assert decision == "mark_too_risky"
    assert recommended is False
    assert reason == "risk_buffer_too_thin"


def test_unavailable_benchmark_comparisons_are_not_zero_filled(reviewed_fixture: dict[str, object]) -> None:
    deltas = pd.read_csv(Path(reviewed_fixture["result"]["output_dir"]) / f"{review.TARGET_ID}_benchmark_review.csv")
    active_combo = deltas[deltas["benchmark_id"] == "active_combo"]
    assert not active_combo.empty
    assert set(active_combo["delta"]) == {"unavailable"}


def test_holdings_review_is_created_or_missing_evidence_recorded(reviewed_fixture: dict[str, object]) -> None:
    output = Path(reviewed_fixture["result"]["output_dir"])
    assert (output / f"{review.TARGET_ID}_holdings_frequency.csv").exists() or "Holdings" in (output / f"{review.TARGET_ID}_missing_evidence.md").read_text(encoding="utf-8")


def test_final_decision_is_explicit(reviewed_fixture: dict[str, object]) -> None:
    result = reviewed_fixture["result"]
    assert result["decision"]
    assert result["next_action"]


def test_no_candidate_exhaustive_is_run(reviewed_fixture: dict[str, object]) -> None:
    result = reviewed_fixture["result"]
    manifest = json.loads((Path(result["output_dir"]) / f"{review.TARGET_ID}_manifest.json").read_text(encoding="utf-8"))
    assert manifest["candidate_exhaustive_run"] is False
    assert result["candidate_exhaustive_recommended"] is False or isinstance(result["candidate_exhaustive_recommended"], bool)


def test_no_paper_forward_active_flag_is_set(reviewed_fixture: dict[str, object]) -> None:
    root = reviewed_fixture["root"]
    registry = yaml.safe_load((root / review.REGISTRY_PATH).read_text(encoding="utf-8"))
    target = {row["id"]: row for row in registry["strategies"]}[review.TARGET_ID]
    assert target["paper_forward_active"] is False


def test_no_real_money_recommendation_is_created(reviewed_fixture: dict[str, object]) -> None:
    root = reviewed_fixture["root"]
    registry = yaml.safe_load((root / review.REGISTRY_PATH).read_text(encoding="utf-8"))
    target = {row["id"]: row for row in registry["strategies"]}[review.TARGET_ID]
    assert target["real_money_recommendation"] is False


def test_active_observations_are_not_mutated(reviewed_fixture: dict[str, object]) -> None:
    assert reviewed_fixture["before"] == reviewed_fixture["after"]
    assert reviewed_fixture["result"]["consistency"]["no_active_observation_mutation"] is True


def test_consistency_check_passes(reviewed_fixture: dict[str, object]) -> None:
    result = reviewed_fixture["result"]
    consistency = json.loads((Path(result["output_dir"]) / f"{review.TARGET_ID}_consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["consistency_passed"] is True
    assert consistency["no_real_money_recommendation"] is True
