from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

import run_parallel_discovery_approved_cache_batch as batch


def write_price_cache(root: Path, symbol: str, periods: int = 620, start: str = "2021-01-01", drift: float = 0.00025) -> None:
    dates = pd.bdate_range(start, periods=periods)
    prices = [50.0 + len(symbol)]
    for idx in range(1, periods):
        prices.append(prices[-1] * (1 + drift + 0.0002 * ((idx % 9) - 4)))
    target = root / "data" / "cache" / f"{symbol}.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"date": dates, "adj_close": prices, "close": prices}).to_csv(target, index=False)


def write_required_cache(root: Path) -> None:
    for offset, symbol in enumerate(batch.required_symbols()):
        if symbol == "BIL":
            write_price_cache(root, symbol, drift=0.00002)
        elif symbol == "XLC":
            write_price_cache(root, symbol, periods=360, start="2022-01-03", drift=0.00018)
        else:
            write_price_cache(root, symbol, drift=0.00012 + offset * 0.000008)


def write_symbol_map(root: Path) -> None:
    approved = sorted(set(batch.required_symbols()) - batch.FORBIDDEN_SYMBOLS)
    rows = [{"symbol": symbol, "allowed_for_strategy": True, "allowed_for_benchmark": True} for symbol in approved]
    rows.append({"symbol": "DBC", "allowed_for_strategy": False, "allowed_for_benchmark": True})
    path = root / batch.SYMBOL_MAP_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({"symbols": rows}, sort_keys=False), encoding="utf-8")


def write_registry(root: Path) -> None:
    rows = []
    for row_id, active, status, decision in [
        (batch.VM_ID, True, "active_paper_demo_observation", "paper_forward_activation_recovered"),
        (batch.DSR_ID, True, "active_paper_demo_observation", "paper_forward_activation_recovered"),
        (batch.SPY_200D_ID, True, "active_observation", "keep_frozen_control"),
        (batch.TOP2_ID, False, "mark_duplicate_or_near_duplicate", "mark_duplicate_or_near_duplicate"),
        (batch.TOP3_ID, False, "mark_duplicate_or_near_duplicate", "mark_duplicate_or_near_duplicate"),
    ]:
        rows.append(
            {
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
                "implementation_status": "implemented",
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
        )
    path = root / batch.REGISTRY_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({"registry": {"schema_version": 1, "research_only": True}, "strategies": rows}, sort_keys=False), encoding="utf-8")


def write_state_files(root: Path) -> None:
    readiness = root / "evidence" / "approved_etf_cache_readiness" / "latest" / "approved_etf_cache_readiness_manifest.json"
    readiness.parent.mkdir(parents=True, exist_ok=True)
    readiness.write_text(json.dumps({"missing_symbols": []}), encoding="utf-8")
    recompute = root / "evidence" / "active_strategy_evidence_recompute" / "latest" / "active_strategy_recompute_manifest.json"
    recompute.parent.mkdir(parents=True, exist_ok=True)
    recompute.write_text(
        json.dumps(
            {
                "decisions": {
                    batch.VM_ID: "active_evidence_confirmed_with_minor_deltas",
                    batch.DSR_ID: "active_evidence_material_mismatch_manual_review",
                }
            }
        ),
        encoding="utf-8",
    )


def prepared_root(tmp_path: Path) -> Path:
    write_symbol_map(tmp_path)
    write_registry(tmp_path)
    write_state_files(tmp_path)
    write_required_cache(tmp_path)
    return tmp_path


@pytest.fixture(scope="module")
def audited_fixture(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    root = prepared_root(tmp_path_factory.mktemp("approved_cache_discovery"))
    result = batch.run_parallel_discovery(root, strict_state=True)
    return {"root": root, "result": result}


def test_only_approved_symbols_are_used() -> None:
    approved = set(batch.required_symbols()) - batch.FORBIDDEN_SYMBOLS
    for spec in batch.candidate_specs():
        assert set(spec["symbols"]) <= approved


def test_forbidden_symbols_are_rejected() -> None:
    with pytest.raises(ValueError):
        batch.validate_spec_symbols({"strategy_id": "bad", "symbols": ["SPY", "DBC"]}, {"SPY", "BIL"})


def test_no_candidate_exhaustive_is_run(audited_fixture: dict[str, object]) -> None:
    result = audited_fixture["result"]
    manifest = json.loads((Path(result["output_dir"]) / "parallel_discovery_approved_cache_manifest.json").read_text(encoding="utf-8"))
    assert manifest["candidate_exhaustive_run"] is False
    assert result["consistency"]["no_candidate_exhaustive_run"] is True


def test_no_paper_forward_active_flag_is_set(audited_fixture: dict[str, object]) -> None:
    root = audited_fixture["root"]
    registry = yaml.safe_load((root / batch.REGISTRY_PATH).read_text(encoding="utf-8"))
    new_ids = {spec["strategy_id"] for spec in batch.candidate_specs()}
    for row in registry["strategies"]:
        if row["id"] in new_ids:
            assert row["paper_forward_active"] is False


def test_no_real_money_recommendation_is_created(audited_fixture: dict[str, object]) -> None:
    root = audited_fixture["root"]
    registry = yaml.safe_load((root / batch.REGISTRY_PATH).read_text(encoding="utf-8"))
    new_ids = {spec["strategy_id"] for spec in batch.candidate_specs()}
    for row in registry["strategies"]:
        if row["id"] in new_ids:
            assert row["real_money_recommendation"] is False


def test_promotion_candidates_are_separate_from_watchlist_rows(audited_fixture: dict[str, object]) -> None:
    result = audited_fixture["result"]
    latest = Path(result["output_dir"])
    promotions = pd.read_csv(latest / "parallel_discovery_approved_cache_promotion_candidates.csv")
    watchlist = pd.read_csv(latest / "parallel_discovery_approved_cache_watchlist.csv")
    overlap = set(promotions.get("strategy_id", [])) & set(watchlist.get("strategy_id", []))
    assert overlap == set()


def test_benchmark_deltas_are_not_zero_filled_when_unavailable(audited_fixture: dict[str, object]) -> None:
    result = audited_fixture["result"]
    deltas = pd.read_csv(Path(result["output_dir"]) / "parallel_discovery_approved_cache_benchmark_delta.csv")
    active_combo = deltas[deltas["benchmark_id"] == "active_combo"]
    assert not active_combo.empty
    assert set(active_combo["delta"]) == {"unavailable"}


def test_next_action_is_explicit(audited_fixture: dict[str, object]) -> None:
    result = audited_fixture["result"]
    text = (Path(result["output_dir"]) / "parallel_discovery_approved_cache_next_action.md").read_text(encoding="utf-8")
    assert result["next_action"]
    assert f"`{result['next_action']}`" in text


def test_consistency_check_passes(audited_fixture: dict[str, object]) -> None:
    result = audited_fixture["result"]
    consistency = json.loads((Path(result["output_dir"]) / "parallel_discovery_approved_cache_consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["consistency_passed"] is True
    assert consistency["no_paper_forward_activation"] is True
    assert consistency["no_real_money_recommendation"] is True
