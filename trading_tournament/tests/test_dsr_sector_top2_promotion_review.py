from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import yaml

import run_dsr_sector_top2_promotion_review as review


def write_price_cache(root: Path, symbol: str, periods: int = 620, start: str = "2021-01-01", drift: float = 0.0003) -> None:
    dates = pd.bdate_range(start, periods=periods)
    prices = [50.0 + len(symbol)]
    for idx in range(1, periods):
        prices.append(prices[-1] * (1 + drift + 0.0002 * ((idx % 9) - 4)))
    target = root / "data" / "cache" / f"{symbol}.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"date": dates, "adj_close": prices, "close": prices}).to_csv(target, index=False)


def write_required_cache(root: Path) -> None:
    for offset, symbol in enumerate(review.REQUIRED_CACHE_SYMBOLS + ["SPY"]):
        if symbol == "XLC":
            write_price_cache(root, symbol, periods=360, start="2022-01-03", drift=0.00024)
        elif symbol == "BIL":
            write_price_cache(root, symbol, periods=700, drift=0.00002)
        else:
            write_price_cache(root, symbol, periods=700, drift=0.00016 + offset * 0.00001)


def write_registry(root: Path) -> None:
    rows = []
    for row_id, active, status in [
        (review.ACTIVE_DSR_ID, True, "active_paper_demo_observation"),
        (review.VM_QUALITY_ID, True, "active_paper_demo_observation"),
        (review.SPY_200D_ID, True, "active_observation"),
        (review.TARGET_ID, False, "future_review_candidate"),
        (review.TOP3_ID, False, "deferred_candidate_queue"),
    ]:
        rows.append(
            {
                "id": row_id,
                "display_name": row_id,
                "status": status,
                "current_status": status,
                "strategy_id": row_id,
                "family": review.FAMILY if "dsr" in row_id else "test_family",
                "strategy_family": review.FAMILY if "dsr" in row_id else "test_family",
                "rules_frozen": active,
                "paper_forward_active": active,
                "paper_forward_allowed_by_risk_framework": active,
                "real_money_recommendation": False,
                "candidate_exhaustive_run": False,
                "candidate_exhaustive_recommended": row_id == review.TOP3_ID,
                "promotion_decision": "future_promotion_review" if row_id == review.TARGET_ID else "not_target",
                "allowed_next_action": "create_promotion_review_for_dsr_sector_top2_momentum_200d_bil_v1"
                if row_id == review.TARGET_ID
                else "observe_only",
                "next_allowed_action": "create_promotion_review_for_dsr_sector_top2_momentum_200d_bil_v1"
                if row_id == review.TARGET_ID
                else "observe_only",
                "allowed_next_actions": [
                    "create_promotion_review_for_dsr_sector_top2_momentum_200d_bil_v1"
                    if row_id == review.TARGET_ID
                    else "observe_only"
                ],
                "forbidden_next_actions": ["promote_to_real_money", "add_broker_integration", "place_live_orders"],
                "implementation_status": "not_implemented" if row_id == review.TARGET_ID else "implemented",
                "evidence_source": "conversation_recovered",
                "latest_evidence_path": "evidence/test/latest",
                "duplication_risk": "same_family_as_active_dsr_equal_weight_observation" if row_id == review.TARGET_ID else "not_flagged",
            }
        )
    path = root / review.REGISTRY_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            {"registry": {"schema_version": 1, "project": "trading_tournament", "research_only": True}, "strategies": rows},
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def test_dsr_sector_top2_promotion_review_missing_cache_outputs(tmp_path: Path) -> None:
    write_registry(tmp_path)
    before = yaml.safe_load((tmp_path / review.REGISTRY_PATH).read_text(encoding="utf-8"))
    active_before = review.protected_snapshot(before)

    result = review.run_promotion_review(tmp_path, strict_state=False)

    latest = Path(result["output_dir"])
    assert latest.exists()
    required = {
        f"{review.TARGET_ID}_promotion_review_summary.md",
        f"{review.TARGET_ID}_promotion_decision.md",
        f"{review.TARGET_ID}_evidence_scorecard.csv",
        f"{review.TARGET_ID}_profit_review.csv",
        f"{review.TARGET_ID}_risk_review.csv",
        f"{review.TARGET_ID}_benchmark_review.csv",
        f"{review.TARGET_ID}_duplicate_review.csv",
        f"{review.TARGET_ID}_family_comparison.csv",
        f"{review.TARGET_ID}_missing_evidence.md",
        f"{review.TARGET_ID}_next_action.md",
        f"{review.TARGET_ID}_manifest.json",
        f"{review.TARGET_ID}_consistency_check.json",
        f"{review.TARGET_ID}_promotion_review_packet.zip",
    }
    assert required <= {path.name for path in latest.iterdir()}

    assert result["final_decision"] == "evidence_missing"
    assert result["candidate_exhaustive_recommended"] is False
    assert result["next_action"] == "repair_dsr_top2_promotion_review_diagnostics"
    assert review.TARGET_ID == "dsr_sector_top2_momentum_200d_bil_v1"

    profit = pd.read_csv(latest / f"{review.TARGET_ID}_profit_review.csv")
    assert "missing_or_unavailable" in set(profit["value"])

    consistency = json.loads((latest / f"{review.TARGET_ID}_consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["consistency_passed"] is True
    assert consistency["no_candidate_exhaustive_run"] is True
    assert consistency["no_paper_forward_activation"] is True
    assert consistency["no_real_money_recommendation"] is True
    assert consistency["no_dsr_equal_weight_mutation"] is True

    manifest = json.loads((latest / f"{review.TARGET_ID}_manifest.json").read_text(encoding="utf-8"))
    assert manifest["candidate_exhaustive_run"] is False
    assert manifest["paper_forward_activation"] is False
    assert manifest["real_money_recommendation"] is False
    assert manifest["data_downloaded"] is False
    assert manifest["provider_api_called"] is False

    after = yaml.safe_load((tmp_path / review.REGISTRY_PATH).read_text(encoding="utf-8"))
    assert review.protected_snapshot(after) == active_before
    target = {row["id"]: row for row in after["strategies"]}[review.TARGET_ID]
    assert target["paper_forward_active"] is False
    assert target["real_money_recommendation"] is False
    assert target["candidate_exhaustive_run"] is False
    assert target["candidate_exhaustive_recommended"] is False
    assert target["allowed_next_action"] == "repair_dsr_top2_promotion_review_diagnostics"


def test_dsr_sector_top2_promotion_review_uses_ready_cache_and_handles_xlc_history(tmp_path: Path) -> None:
    write_registry(tmp_path)
    write_required_cache(tmp_path)
    before = yaml.safe_load((tmp_path / review.REGISTRY_PATH).read_text(encoding="utf-8"))
    active_before = review.protected_snapshot(before)

    result = review.run_promotion_review(tmp_path, strict_state=False)

    latest = Path(result["output_dir"])
    assert result["diagnostics_available"] is True
    assert result["missing_symbols"] == []
    assert result["final_decision"] in review.ALLOWED_DECISIONS - {"evidence_missing"}
    assert result["data_history_mode"] == "per_asset_availability"
    assert result["next_action"]

    manifest = json.loads((latest / f"{review.TARGET_ID}_manifest.json").read_text(encoding="utf-8"))
    assert manifest["diagnostics_available"] is True
    assert manifest["data_history_mode"] == "per_asset_availability"
    assert manifest["candidate_exhaustive_run"] is False
    assert manifest["paper_forward_activation"] is False
    assert manifest["real_money_recommendation"] is False
    assert manifest["provider_api_called"] is False

    profit = pd.read_csv(latest / f"{review.TARGET_ID}_profit_review.csv")
    assert "180d_median_final_equity" in set(profit["metric"])
    assert "missing_or_unavailable" not in set(profit.loc[profit["metric"] == "180d_median_final_equity", "value"].astype(str))

    rules = pd.read_csv(latest / f"{review.TARGET_ID}_rule_documentation.csv")
    history = rules[rules["field"] == "data_history_mode"].iloc[0]
    assert history["value"] == "per_asset_availability"
    assert "common-start" in history["notes"]
    assert "XLC" in history["notes"]

    cache = pd.read_csv(latest / "cache_status.csv")
    assert set(review.REQUIRED_CACHE_SYMBOLS) <= set(cache["symbol"])
    assert cache[cache["symbol"].isin(review.REQUIRED_CACHE_SYMBOLS)]["qa_status"].eq("passed").all()

    after = yaml.safe_load((tmp_path / review.REGISTRY_PATH).read_text(encoding="utf-8"))
    assert review.protected_snapshot(after) == active_before
    target = {row["id"]: row for row in after["strategies"]}[review.TARGET_ID]
    assert target["paper_forward_active"] is False
    assert target["real_money_recommendation"] is False
    assert target["candidate_exhaustive_run"] is False
