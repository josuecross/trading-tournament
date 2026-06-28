from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

import run_active_strategy_evidence_recompute as review


def write_price_cache(root: Path, symbol: str, periods: int = 720, start: str = "2021-01-01", drift: float = 0.00035) -> None:
    dates = pd.bdate_range(start, periods=periods)
    prices = [50.0 + len(symbol)]
    for idx in range(1, periods):
        cycle = 0.00025 * ((idx % 11) - 5)
        prices.append(prices[-1] * (1 + drift + cycle))
    target = root / "data" / "cache" / f"{symbol}.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"date": dates, "adj_close": prices, "close": prices}).to_csv(target, index=False)


def write_required_cache(root: Path) -> None:
    for offset, symbol in enumerate(review.REQUIRED_CACHE_SYMBOLS + review.OPTIONAL_BENCHMARK_SYMBOLS):
        if symbol == "BIL":
            write_price_cache(root, symbol, drift=0.00002)
        elif symbol == "XLC":
            write_price_cache(root, symbol, periods=420, start="2022-01-03", drift=0.00025)
        else:
            write_price_cache(root, symbol, drift=0.00018 + offset * 0.00001)


def write_observations(root: Path) -> None:
    observations = {
        review.VM_ID: {
            "observation_id": review.VM_ID,
            "base_strategy_id": "vm_quality_lowvol_proxy_v1",
            "status": "active_paper_demo_observation",
            "frozen": True,
            "rules_frozen": True,
            "paper_forward_active": True,
            "real_money_recommendation": False,
        },
        review.DSR_ID: {
            "observation_id": review.DSR_ID,
            "base_strategy_id": "dsr_sector_equal_weight_defensive_filter_v1",
            "status": "active_paper_demo_observation",
            "frozen": True,
            "rules_frozen": True,
            "paper_forward_active": True,
            "real_money_recommendation": False,
        },
    }
    for strategy_id, payload in observations.items():
        path = root / "paper_forward_observations" / strategy_id / "active_observation.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def write_registry(root: Path) -> None:
    rows = []
    for row_id, active, status, decision in [
        (review.VM_ID, True, "active_paper_demo_observation", "paper_forward_activation_recovered"),
        (review.DSR_ID, True, "active_paper_demo_observation", "paper_forward_activation_recovered"),
        (review.SPY_200D_ID, True, "active_observation", "keep_frozen_control"),
        (review.TOP2_ID, False, "mark_duplicate_or_near_duplicate", "mark_duplicate_or_near_duplicate"),
        (review.TOP3_ID, False, "mark_duplicate_or_near_duplicate", "mark_duplicate_or_near_duplicate"),
    ]:
        rows.append(
            {
                "id": row_id,
                "display_name": row_id,
                "status": status,
                "current_status": status,
                "strategy_id": row_id,
                "family": "defensive_sector_rotation_etf" if "dsr" in row_id else "volatility_managed_equity_etf",
                "strategy_family": "defensive_sector_rotation_etf" if "dsr" in row_id else "volatility_managed_equity_etf",
                "rules_frozen": active,
                "frozen": active,
                "paper_forward_active": active,
                "paper_forward_allowed_by_risk_framework": active,
                "real_money_recommendation": False,
                "candidate_exhaustive_run": False,
                "candidate_exhaustive_recommended": False,
                "promotion_decision": decision,
                "allowed_next_action": "observe_only",
                "allowed_next_actions": ["observe_only"],
                "forbidden_next_actions": ["promote_to_real_money", "add_broker_integration", "place_live_orders"],
                "implementation_status": "implemented",
                "evidence_source": "conversation_recovered",
                "latest_evidence_path": "evidence/test/latest",
            }
        )
    path = root / review.REGISTRY_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump({"registry": {"schema_version": 1, "research_only": True}, "strategies": rows}, sort_keys=False),
        encoding="utf-8",
    )


def write_readiness(root: Path) -> None:
    path = root / "evidence" / "approved_etf_cache_readiness" / "latest" / "approved_etf_cache_readiness_manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"missing_symbols": [], "mode": "audit_only"}), encoding="utf-8")


def prepared_root(tmp_path: Path) -> Path:
    write_registry(tmp_path)
    write_observations(tmp_path)
    write_readiness(tmp_path)
    write_required_cache(tmp_path)
    return tmp_path


@pytest.fixture(scope="module")
def audited_fixture(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    root = prepared_root(tmp_path_factory.mktemp("active_recompute"))
    observation_before = {strategy_id: path.read_text(encoding="utf-8") for strategy_id, path in review.active_observation_paths(root).items()}
    result = review.run_active_strategy_evidence_recompute(root, strict_state=True)
    observation_after = {strategy_id: path.read_text(encoding="utf-8") for strategy_id, path in review.active_observation_paths(root).items()}
    return {"root": root, "result": result, "observation_before": observation_before, "observation_after": observation_after}


def test_both_active_strategy_ids_are_targeted() -> None:
    assert review.TARGET_STRATEGY_IDS == [review.VM_ID, review.DSR_ID]


def test_recompute_uses_cache_when_available(audited_fixture: dict[str, object]) -> None:
    result = audited_fixture["result"]
    latest = Path(result["output_dir"])

    assert result["cache_used"] is True
    cache = pd.read_csv(latest / "cache_status.csv")
    required = cache[cache["symbol"].isin(review.REQUIRED_CACHE_SYMBOLS)]
    assert required["qa_status"].eq("passed").all()
    assert (latest / "active_strategy_recompute_profit_review.csv").exists()


def test_recovered_vs_recomputed_handles_missing_recovered_values() -> None:
    row = review.recovered_comparison_row(review.VM_ID, "synthetic_metric", None, 123.0)
    assert row["verdict"] == "recovered_value_missing"
    assert row["recomputed_value"] == 123.0


def test_material_mismatch_is_flagged() -> None:
    row = review.recovered_comparison_row(review.VM_ID, "180d_median_final_equity", 3000.0, 3600.0, tolerance=100.0)
    assert row["verdict"] == "material_mismatch_requires_review"


def test_minor_deltas_are_not_auto_failed() -> None:
    row = review.recovered_comparison_row(review.VM_ID, "180d_median_final_equity", 3000.0, 3160.0, tolerance=100.0)
    assert row["verdict"] == "minor_methodology_delta"
    decision, manual = review.decide_strategy([row], diagnostics_available=True)
    assert decision == "active_evidence_confirmed_with_minor_deltas"
    assert manual is False


def test_active_observation_files_are_not_mutated(audited_fixture: dict[str, object]) -> None:
    result = audited_fixture["result"]
    assert audited_fixture["observation_after"] == audited_fixture["observation_before"]
    assert result["consistency"]["no_active_observation_mutation"] is True


def test_no_candidate_exhaustive_flag_is_created(audited_fixture: dict[str, object]) -> None:
    root = audited_fixture["root"]
    result = audited_fixture["result"]
    manifest = json.loads((Path(result["output_dir"]) / "active_strategy_recompute_manifest.json").read_text(encoding="utf-8"))
    registry = yaml.safe_load((root / review.REGISTRY_PATH).read_text(encoding="utf-8"))

    assert manifest["candidate_exhaustive_run"] is False
    for row in registry["strategies"]:
        if row["id"] in review.TARGET_STRATEGY_IDS:
            assert row["candidate_exhaustive_run"] is False
            assert row["no_candidate_exhaustive_run"] is True


def test_no_paper_forward_checkpoint_is_run(audited_fixture: dict[str, object]) -> None:
    root = audited_fixture["root"]
    result = audited_fixture["result"]
    manifest = json.loads((Path(result["output_dir"]) / "active_strategy_recompute_manifest.json").read_text(encoding="utf-8"))
    registry = yaml.safe_load((root / review.REGISTRY_PATH).read_text(encoding="utf-8"))

    assert manifest["paper_forward_checkpoint"] is False
    for row in registry["strategies"]:
        if row["id"] in review.TARGET_STRATEGY_IDS:
            assert row["no_paper_forward_checkpoint"] is True


def test_no_real_money_recommendation_is_created(audited_fixture: dict[str, object]) -> None:
    root = audited_fixture["root"]
    result = audited_fixture["result"]
    manifest = json.loads((Path(result["output_dir"]) / "active_strategy_recompute_manifest.json").read_text(encoding="utf-8"))
    registry = yaml.safe_load((root / review.REGISTRY_PATH).read_text(encoding="utf-8"))

    assert manifest["real_money_recommendation"] is False
    for row in registry["strategies"]:
        if row["id"] in review.TARGET_STRATEGY_IDS:
            assert row["real_money_recommendation"] is False
            assert row["no_real_money_recommendation"] is True


def test_next_action_is_explicit(audited_fixture: dict[str, object]) -> None:
    result = audited_fixture["result"]
    next_action = (Path(result["output_dir"]) / "active_strategy_recompute_next_action.md").read_text(encoding="utf-8")

    assert result["overall_next_action"]
    assert f"`{result['overall_next_action']}`" in next_action


def test_consistency_check_passes(audited_fixture: dict[str, object]) -> None:
    result = audited_fixture["result"]
    consistency = json.loads((Path(result["output_dir"]) / "active_strategy_recompute_consistency_check.json").read_text(encoding="utf-8"))

    assert consistency["consistency_passed"] is True
    assert consistency["no_candidate_exhaustive_run"] is True
    assert consistency["no_paper_forward_checkpoint"] is True
    assert consistency["no_real_money_recommendation"] is True
    assert result["consistency"]["consistency_passed"] is True
