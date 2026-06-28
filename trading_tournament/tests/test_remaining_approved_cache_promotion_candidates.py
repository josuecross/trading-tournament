from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

import run_parallel_discovery_approved_cache_batch as discovery
import run_remaining_approved_cache_promotion_candidates as remaining


def write_price_cache(root: Path, symbol: str, periods: int = 620, start: str = "2021-01-01", drift: float = 0.0002) -> None:
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
    rows = [{"symbol": symbol, "allowed_for_strategy": True, "allowed_for_benchmark": True} for symbol in sorted(discovery.required_symbols())]
    rows.append({"symbol": "DBC", "allowed_for_strategy": False, "allowed_for_benchmark": True})
    path = root / discovery.SYMBOL_MAP_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({"symbols": rows}, sort_keys=False), encoding="utf-8")


def row(row_id: str, active: bool, status: str, decision: str) -> dict[str, object]:
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
        "rules_frozen": active or row_id in {remaining.QVM_TOP2_ID, remaining.LVQ_ID},
        "frozen": active,
        "paper_forward_active": active,
        "implementation_status": "implemented_research_sample" if not active else "implemented",
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
        row(discovery.VM_ID, True, "active_paper_demo_observation", "paper_forward_activation_recovered"),
        row(discovery.DSR_ID, True, "active_paper_demo_observation", "paper_forward_activation_recovered"),
        row(discovery.SPY_200D_ID, True, "active_observation", "keep_frozen_control"),
        row(discovery.TOP2_ID, False, "mark_duplicate_or_near_duplicate", "mark_duplicate_or_near_duplicate"),
        row(discovery.TOP3_ID, False, "mark_duplicate_or_near_duplicate", "mark_duplicate_or_near_duplicate"),
        row(remaining.QVM_RISK_ID, False, "mark_too_risky", "mark_too_risky"),
        row(remaining.QVM_TOP2_ID, False, "promotion_review_candidate", "promotion_review_candidate"),
        row(remaining.LVQ_ID, False, "promotion_review_candidate", "promotion_review_candidate"),
    ]
    path = root / remaining.REGISTRY_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({"registry": {"schema_version": 1, "research_only": True}, "strategies": rows}, sort_keys=False), encoding="utf-8")


def write_state(root: Path) -> None:
    readiness = root / "evidence" / "approved_etf_cache_readiness" / "latest" / "approved_etf_cache_readiness_manifest.json"
    readiness.parent.mkdir(parents=True, exist_ok=True)
    readiness.write_text(json.dumps({"missing_symbols": []}), encoding="utf-8")
    recompute = root / "evidence" / "active_strategy_evidence_recompute" / "latest" / "active_strategy_recompute_manifest.json"
    recompute.parent.mkdir(parents=True, exist_ok=True)
    recompute.write_text(json.dumps({"decisions": {discovery.VM_ID: "active_evidence_confirmed_with_minor_deltas", discovery.DSR_ID: "active_evidence_material_mismatch_manual_review"}}), encoding="utf-8")
    sibling = root / remaining.SIBLING_EVIDENCE
    sibling.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "strategy_id": remaining.QVM_TOP2_ID,
                "current_status": "comparator",
                "evidence_source": "cached_promotion_review",
                "180d_median_equity": 3470.9143,
                "+300 rate": 0.6,
                "+400 rate": 0.6,
                "180d_worst_drawdown": -581.4066,
                "stop-hit rate": 0.0,
                "risk_buffer_vs_minus_600": 18.5934,
                "correlation_vs_target": 0.9855,
                "duplicate_label": "near_duplicate",
                "risk_label": "too_thin",
                "reason_for_status": "test",
                "next_action": "",
            }
        ]
    ).to_csv(sibling, index=False)


def write_observations(root: Path) -> None:
    for strategy_id in [discovery.VM_ID, discovery.DSR_ID]:
        path = root / "paper_forward_observations" / strategy_id / "active_observation.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump({"observation_id": strategy_id, "paper_forward_active": True, "frozen": True}), encoding="utf-8")


def prepared_root(tmp_path: Path) -> Path:
    write_symbol_map(tmp_path)
    write_registry(tmp_path)
    write_state(tmp_path)
    write_observations(tmp_path)
    write_required_cache(tmp_path)
    return tmp_path


@pytest.fixture(scope="module")
def reviewed_fixture(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    root = prepared_root(tmp_path_factory.mktemp("remaining_reviews"))
    before = {sid: path.read_text(encoding="utf-8") for sid, path in remaining.active_observation_paths(root).items()}
    result = remaining.run_remaining_reviews(root, strict_state=True)
    after = {sid: path.read_text(encoding="utf-8") for sid, path in remaining.active_observation_paths(root).items()}
    return {"root": root, "result": result, "before": before, "after": after}


def test_qvm_top2_can_be_dispositioned_from_sibling_evidence(tmp_path: Path) -> None:
    root = prepared_root(tmp_path)
    evidence = remaining.read_qvm_sibling_evidence(root)
    decision, next_action, reason = remaining.qvm_top2_decision(evidence)
    assert decision == "mark_duplicate_or_near_duplicate"
    assert next_action == "archive_qvm_quality_value_momentum_top2_v1_as_duplicate_diagnostic"
    assert "near-duplicate" in reason


def test_qvm_top2_does_not_require_full_recompute_if_sibling_evidence_present(reviewed_fixture: dict[str, object]) -> None:
    manifest = json.loads((Path(reviewed_fixture["result"]["qvm_top2_output_dir"]) / f"{remaining.QVM_TOP2_ID}_manifest.json").read_text(encoding="utf-8"))
    assert manifest["sibling_evidence_used"] is True
    assert manifest["full_recompute_run"] is False


def test_lvq_target_strategy_is_correct() -> None:
    assert remaining.LVQ_ID == "lvq_lowvol_quality_spy_regime_v1"
    assert remaining.specs_by_id()[remaining.LVQ_ID]["rule"] == "spy_regime_equal_weight"


def test_approved_symbols_only_are_used(tmp_path: Path) -> None:
    root = prepared_root(tmp_path)
    approved = discovery.approved_strategy_symbols(root)
    discovery.validate_spec_symbols(remaining.specs_by_id()[remaining.LVQ_ID], approved)
    assert set(remaining.LVQ_SYMBOLS) <= approved


def test_unavailable_benchmark_comparisons_are_not_zero_filled(reviewed_fixture: dict[str, object]) -> None:
    deltas = pd.read_csv(Path(reviewed_fixture["result"]["lvq_output_dir"]) / f"{remaining.LVQ_ID}_benchmark_review.csv")
    active_combo = deltas[deltas["benchmark_id"] == "active_combo"]
    assert not active_combo.empty
    assert set(active_combo["delta"]) == {"unavailable"}


def test_holdings_review_is_created_or_missing_evidence_recorded(reviewed_fixture: dict[str, object]) -> None:
    output = Path(reviewed_fixture["result"]["lvq_output_dir"])
    assert (output / f"{remaining.LVQ_ID}_holdings_frequency.csv").exists() or "Holdings" in (output / f"{remaining.LVQ_ID}_missing_evidence.md").read_text(encoding="utf-8")


def test_final_decisions_are_explicit(reviewed_fixture: dict[str, object]) -> None:
    result = reviewed_fixture["result"]
    assert result["qvm_top2_decision"]
    assert result["qvm_top2_next_action"]
    assert result["lvq_decision"]
    assert result["lvq_next_action"]


def test_no_candidate_exhaustive_is_run(reviewed_fixture: dict[str, object]) -> None:
    result = reviewed_fixture["result"]
    assert result["lvq_candidate_exhaustive_recommended"] in {True, False}
    assert result["qvm_consistency"]["no_candidate_exhaustive_run"] is True
    assert result["lvq_consistency"]["no_candidate_exhaustive_run"] is True


def test_no_paper_forward_active_flag_is_set(reviewed_fixture: dict[str, object]) -> None:
    registry = yaml.safe_load((reviewed_fixture["root"] / remaining.REGISTRY_PATH).read_text(encoding="utf-8"))
    rows = {row["id"]: row for row in registry["strategies"]}
    assert rows[remaining.QVM_TOP2_ID]["paper_forward_active"] is False
    assert rows[remaining.LVQ_ID]["paper_forward_active"] is False


def test_no_real_money_recommendation_is_created(reviewed_fixture: dict[str, object]) -> None:
    registry = yaml.safe_load((reviewed_fixture["root"] / remaining.REGISTRY_PATH).read_text(encoding="utf-8"))
    rows = {row["id"]: row for row in registry["strategies"]}
    assert rows[remaining.QVM_TOP2_ID]["real_money_recommendation"] is False
    assert rows[remaining.LVQ_ID]["real_money_recommendation"] is False


def test_active_observations_are_not_mutated(reviewed_fixture: dict[str, object]) -> None:
    assert reviewed_fixture["before"] == reviewed_fixture["after"]
    assert reviewed_fixture["result"]["lvq_consistency"]["no_active_observation_mutation"] is True


def test_consistency_checks_pass(reviewed_fixture: dict[str, object]) -> None:
    result = reviewed_fixture["result"]
    qvm = json.loads((Path(result["qvm_top2_output_dir"]) / f"{remaining.QVM_TOP2_ID}_consistency_check.json").read_text(encoding="utf-8"))
    lvq = json.loads((Path(result["lvq_output_dir"]) / f"{remaining.LVQ_ID}_consistency_check.json").read_text(encoding="utf-8"))
    assert qvm["consistency_passed"] is True
    assert lvq["consistency_passed"] is True
