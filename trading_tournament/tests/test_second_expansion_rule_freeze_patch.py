from __future__ import annotations

import csv
import json
from datetime import date, timedelta
from pathlib import Path

import pytest
import yaml

import run_second_expansion_rule_freeze_patch as patch
import run_second_expansion_with_lane_framework_preregistration as prereg


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_cache(path: Path, symbol: str, start_days_ago: int) -> None:
    today = date.today()
    rows = []
    for offset in range(start_days_ago + 1):
        current = today - timedelta(days=start_days_ago - offset)
        rows.append(
            {
                "date": current.isoformat(),
                "open": 100 + offset,
                "high": 101 + offset,
                "low": 99 + offset,
                "close": 100.5 + offset,
                "adj_close": 100.5 + offset,
                "volume": 100000,
                "symbol": symbol,
            }
        )
    write_csv(path, rows, ["date", "open", "high", "low", "close", "adj_close", "volume", "symbol"])


def write_fixture(root: Path) -> None:
    registry_path = root / prereg.REGISTRY_PATH
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        yaml.safe_dump(
            {
                "registry": {
                    "schema_version": 1,
                    "project": "trading_tournament",
                    "research_only": True,
                    "real_money_recommendation": False,
                    "broker_integration": False,
                    "live_orders": False,
                    "current_next_action": "pre_register_second_expansion_discovery_batch_with_lane_framework",
                },
                "strategies": [
                    {
                        "id": "active_combo_vm_dsr_equal_weight_v1",
                        "strategy_id": "active_combo_vm_dsr_equal_weight_v1",
                        "status": "benchmark_watchlist",
                        "paper_forward_active": False,
                        "candidate_exhaustive_run": False,
                    },
                    {
                        "id": "dmr_liquid_etf_oversold_rebound_v1",
                        "strategy_id": "dmr_liquid_etf_oversold_rebound_v1",
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
    roadmap = root / prereg.ROADMAP_PATH
    roadmap.parent.mkdir(parents=True, exist_ok=True)
    roadmap.write_text("# Research Roadmap\n\nCurrent next action: `pre_register_second_expansion_discovery_batch_with_lane_framework`\n", encoding="utf-8")
    symbol_map = root / prereg.SYMBOL_MAP_PATH
    symbol_map.parent.mkdir(parents=True, exist_ok=True)
    symbol_map.write_text(
        yaml.safe_dump(
            {
                "symbols": [
                    {
                        "symbol": symbol,
                        "allowed_for_strategy": True,
                        "allowed_for_benchmark": True,
                        "cache_ready": True,
                    }
                    for symbol in prereg.REQUIRED_SYMBOLS
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    for symbol in prereg.REQUIRED_SYMBOLS:
        start_days = 1300 if symbol in {"DBMF", "KMLM", "CTA"} else 2500
        write_cache(root / prereg.CACHE_DIR / f"{symbol}.csv", symbol, start_days)
    sector_next = root / prereg.SECTOR_RS_PREREG_DIR / "sector_rs_limited_history_next_action.md"
    sector_next.parent.mkdir(parents=True, exist_ok=True)
    sector_next.write_text("`run_sector_rs_limited_history_discovery_batch`\n", encoding="utf-8")
    lane_framework = root / prereg.LANE_FRAMEWORK_DIR / "lane_gate_framework.yaml"
    lane_framework.parent.mkdir(parents=True, exist_ok=True)
    lane_framework.write_text(yaml.safe_dump({"lanes": {lane: {} for lane in prereg.LANE_IDS}}), encoding="utf-8")


@pytest.fixture(scope="module")
def patch_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    root = tmp_path_factory.mktemp("rule_freeze_patch")
    write_fixture(root)
    prereg.run_second_expansion_with_lane_framework_preregistration(root)
    before = yaml.safe_load((root / prereg.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result = patch.run_second_expansion_rule_freeze_patch(root)
    after = yaml.safe_load((root / prereg.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result["root"] = str(root)
    result["strategies_before"] = before
    result["strategies_after"] = after
    return result


def patch_output(patch_run: dict[str, object]) -> Path:
    return Path(patch_run["patch_output_dir"])


def latest_output(patch_run: dict[str, object]) -> Path:
    return Path(patch_run["latest_packet_dir"])


def manifest(patch_run: dict[str, object]) -> dict[str, object]:
    return json.loads((patch_output(patch_run) / "second_expansion_rule_freeze_patch_manifest.json").read_text(encoding="utf-8"))


def batch(patch_run: dict[str, object]) -> dict[str, object]:
    return yaml.safe_load((latest_output(patch_run) / "second_expansion_batch.yaml").read_text(encoding="utf-8"))


def candidate(patch_run: dict[str, object], candidate_id: str) -> dict[str, object]:
    return next(item for item in batch(patch_run)["candidates"] if item["candidate_id"] == candidate_id)


def candidate_text(patch_run: dict[str, object], candidate_id: str) -> str:
    item = candidate(patch_run, candidate_id)
    values = []
    for value in item.values():
        if isinstance(value, list):
            values.extend(str(part) for part in value)
        elif isinstance(value, dict):
            values.extend(str(part) for part in value.values())
        else:
            values.append(str(value))
    return " ".join(values)


def test_rule_freeze_patch_only(patch_run: dict[str, object]) -> None:
    assert manifest(patch_run)["rule_freeze_patch_only"] is True


def test_no_backtests_were_run(patch_run: dict[str, object]) -> None:
    assert manifest(patch_run)["backtests_run"] is False


def test_no_discovery_was_run(patch_run: dict[str, object]) -> None:
    assert manifest(patch_run)["discovery_run"] is False


def test_no_performance_metrics_were_computed(patch_run: dict[str, object]) -> None:
    assert manifest(patch_run)["performance_metrics_computed"] is False


def test_no_provider_download_occurred(patch_run: dict[str, object]) -> None:
    assert manifest(patch_run)["provider_download"] is False


def test_candidate_membership_is_unchanged(patch_run: dict[str, object]) -> None:
    assert [item["candidate_id"] for item in batch(patch_run)["candidates"]] == patch.EXPECTED_CANDIDATES
    assert manifest(patch_run)["candidate_membership_changed"] is False


def test_accepted_rejected_strategy_states_are_unchanged(patch_run: dict[str, object]) -> None:
    assert patch_run["strategies_before"] == patch_run["strategies_after"]
    assert manifest(patch_run)["accepted_strategy_state_changed"] is False
    assert manifest(patch_run)["rejected_strategy_state_changed"] is False


def test_old_gld_gror_state_is_not_resumed(patch_run: dict[str, object]) -> None:
    assert manifest(patch_run)["old_gld_gror_state_resumed"] is False
    assert "gror_balanced_momentum_60_40_v1" not in [item["candidate_id"] for item in batch(patch_run)["candidates"]]


def test_sector_rs_discovery_is_not_run(patch_run: dict[str, object]) -> None:
    assert manifest(patch_run)["sector_rs_discovery_run"] is False
    assert "sector_rs_weekly_cash_filter_v1" not in [item["candidate_id"] for item in batch(patch_run)["candidates"]]


def test_no_intraday_or_event_candidate_is_included(patch_run: dict[str, object]) -> None:
    assert manifest(patch_run)["intraday_candidates_included"] is False
    assert manifest(patch_run)["event_data_candidates_included"] is False


def test_turn_of_month_has_exact_calendar_window(patch_run: dict[str, object]) -> None:
    text = candidate_text(patch_run, "turn_of_month_spy_qqq_v1")
    assert "last 4 trading days" in text
    assert "first 3 trading days" in text


def test_turn_of_month_has_exact_spy_qqq_selection_rule(patch_run: dict[str, object]) -> None:
    text = candidate_text(patch_run, "turn_of_month_spy_qqq_v1")
    assert "63-trading-day total return" in text
    assert "200-day SMA" in text
    assert "If neither SPY nor QQQ qualifies, hold BIL" in text


def test_donchian_has_atr_lookback_and_stop_multiple(patch_run: dict[str, object]) -> None:
    text = candidate_text(patch_run, "donchian_atr_breakout_etf_v1")
    assert "ATR lookback: 14 trading days" in text
    assert "2.0 times ATR(14)" in text


def test_donchian_has_daily_data_stop_timing(patch_run: dict[str, object]) -> None:
    text = candidate_text(patch_run, "donchian_atr_breakout_etf_v1")
    assert "close-based stop signal" in text
    assert "exit at the next valid open" in text
    assert "Do not simulate intraday stop fills from daily low" in text


def test_cash_pause_has_exact_drawdown_and_weekly_loss_thresholds(patch_run: dict[str, object]) -> None:
    text = candidate_text(patch_run, "cash_pause_overlay_meta_v1")
    assert "20-trading-day equity high" in text
    assert "6%" in text
    assert "calendar-week" in text
    assert "-3%" in text


def test_cash_pause_has_exact_application_base(patch_run: dict[str, object]) -> None:
    text = candidate_text(patch_run, "cash_pause_overlay_meta_v1")
    assert "active_combo_vm_dsr_equal_weight_v1" in text
    assert "Do not apply this overlay to rejected strategies" in text


def test_cash_pause_cannot_produce_normal_promotion_candidate_status(patch_run: dict[str, object]) -> None:
    outcomes = candidate(patch_run, "cash_pause_overlay_meta_v1")["valid_future_outcomes"]
    assert outcomes == patch.OVERLAY_VALID_OUTCOMES
    assert "promotion_review_candidate" not in outcomes


def test_managed_futures_has_limited_history_same_window_handling(patch_run: dict[str, object]) -> None:
    item = candidate(patch_run, "managed_futures_etf_trend_wrapper_v1")
    treatment = item["limited_history_treatment"]
    assert treatment["data_available_but_limited_history"] is True
    assert treatment["same_window_comparison_required"] is True
    assert "DBMF" in treatment["required_symbols_for_same_window"]


def test_managed_futures_full_promotion_is_blocked_when_common_sample_too_short(patch_run: dict[str, object]) -> None:
    item = candidate(patch_run, "managed_futures_etf_trend_wrapper_v1")
    treatment = item["limited_history_treatment"]
    assert treatment["common_sample_years_after_warmup"] < 5
    assert treatment["full_promotion_review_candidate_macro_allowed"] is False
    assert "promotion_review_candidate_macro" not in item["valid_future_outcomes"]
    assert "promotion_review_candidate_macro_limited_history" in item["valid_future_outcomes"]


def test_no_unresolved_optimization_phrases_remain(patch_run: dict[str, object]) -> None:
    scan = json.loads((patch_output(patch_run) / "second_expansion_unresolved_ambiguity_scan.json").read_text(encoding="utf-8"))
    assert scan["remaining_ambiguities_count"] == 0


def test_next_action_is_discovery_only_if_unresolved_ambiguity_count_is_zero(patch_run: dict[str, object]) -> None:
    loaded = manifest(patch_run)
    assert loaded["remaining_ambiguities_count"] == 0
    assert loaded["next_action"] == patch.NEXT_ACTION_DISCOVERY
    consistency = json.loads((patch_output(patch_run) / "second_expansion_rule_freeze_consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["consistency_passed"] is True
