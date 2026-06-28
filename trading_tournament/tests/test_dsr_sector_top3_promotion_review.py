from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import yaml

import run_dsr_sector_top3_promotion_review as review


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
    for row_id, active, status, decision, recommended in [
        (review.ACTIVE_DSR_ID, True, "active_paper_demo_observation", "paper_forward_activation_recovered", False),
        (review.VM_QUALITY_ID, True, "active_paper_demo_observation", "paper_forward_activation_recovered", False),
        (review.SPY_200D_ID, True, "active_observation", "keep_frozen_control", False),
        (review.TOP2_ID, False, "mark_duplicate_or_near_duplicate", "mark_duplicate_or_near_duplicate", False),
        (review.TARGET_ID, False, "deferred_candidate_queue", "promote_to_candidate_exhaustive_queue", True),
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
                "candidate_exhaustive_recommended": recommended,
                "promotion_decision": decision,
                "allowed_next_action": "create_candidate_exhaustive_prompt_for_dsr_sector_top3_momentum_defensive_cash_v1"
                if row_id == review.TARGET_ID
                else "observe_only",
                "next_allowed_action": "create_candidate_exhaustive_prompt_for_dsr_sector_top3_momentum_defensive_cash_v1"
                if row_id == review.TARGET_ID
                else "observe_only",
                "allowed_next_actions": [
                    "create_candidate_exhaustive_prompt_for_dsr_sector_top3_momentum_defensive_cash_v1"
                    if row_id == review.TARGET_ID
                    else "observe_only"
                ],
                "forbidden_next_actions": ["promote_to_real_money", "add_broker_integration", "place_live_orders"],
                "implementation_status": "implemented_research_sample" if row_id == review.TARGET_ID else "implemented",
                "evidence_source": "conversation_recovered",
                "latest_evidence_path": "evidence/test/latest",
                "duplication_risk": "not_flagged",
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


def test_dsr_sector_top3_promotion_review_uses_cache_and_preserves_protected_rows(tmp_path: Path) -> None:
    write_registry(tmp_path)
    write_required_cache(tmp_path)
    before = yaml.safe_load((tmp_path / review.REGISTRY_PATH).read_text(encoding="utf-8"))
    active_before = review.protected_snapshot(before)

    result = review.run_promotion_review(tmp_path, strict_state=False)

    latest = Path(result["output_dir"])
    assert latest.exists()
    assert review.TARGET_ID == "dsr_sector_top3_momentum_defensive_cash_v1"
    assert result["diagnostics_available"] is True
    assert result["missing_symbols"] == []
    assert result["data_history_mode"] == "per_asset_availability"
    assert result["final_decision"] in review.ALLOWED_DECISIONS - {"evidence_missing"}
    assert result["next_action"]

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
        f"{review.TARGET_ID}_rebalance_trace.csv",
    }
    assert required <= {path.name for path in latest.iterdir()}

    profit = pd.read_csv(latest / f"{review.TARGET_ID}_profit_review.csv")
    assert "180d_median_final_equity" in set(profit["metric"])
    assert "missing_or_unavailable" not in set(profit.loc[profit["metric"] == "180d_median_final_equity", "value"].astype(str))

    rules = pd.read_csv(latest / f"{review.TARGET_ID}_rule_documentation.csv")
    assert rules[rules["field"] == "data_history_mode"].iloc[0]["value"] == "per_asset_availability"
    assert "XLC" in rules[rules["field"] == "data_history_mode"].iloc[0]["notes"]

    cache = pd.read_csv(latest / "cache_status.csv")
    assert set(review.REQUIRED_CACHE_SYMBOLS) <= set(cache["symbol"])
    assert cache[cache["symbol"].isin(review.REQUIRED_CACHE_SYMBOLS)]["qa_status"].eq("passed").all()

    consistency = json.loads((latest / f"{review.TARGET_ID}_consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["consistency_passed"] is True
    assert consistency["data_history_mode_recorded"] is True
    assert consistency["no_candidate_exhaustive_run"] is True
    assert consistency["no_paper_forward_activation"] is True
    assert consistency["no_real_money_recommendation"] is True
    assert consistency["no_dsr_equal_weight_mutation"] is True

    manifest = json.loads((latest / f"{review.TARGET_ID}_manifest.json").read_text(encoding="utf-8"))
    assert manifest["candidate_exhaustive_run"] is False
    assert manifest["paper_forward_activation"] is False
    assert manifest["real_money_recommendation"] is False
    assert manifest["provider_api_called"] is False

    after = yaml.safe_load((tmp_path / review.REGISTRY_PATH).read_text(encoding="utf-8"))
    assert review.protected_snapshot(after) == active_before
    target = {row["id"]: row for row in after["strategies"]}[review.TARGET_ID]
    assert target["paper_forward_active"] is False
    assert target["real_money_recommendation"] is False
    assert target["candidate_exhaustive_run"] is False
