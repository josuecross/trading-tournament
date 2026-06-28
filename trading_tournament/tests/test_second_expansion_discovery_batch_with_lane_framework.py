from __future__ import annotations

import csv
import json
import math
from datetime import date, timedelta
from pathlib import Path

import pytest
import yaml

import run_second_expansion_discovery_batch_with_lane_framework as discovery
import run_second_expansion_rule_freeze_patch as patch
import run_second_expansion_with_lane_framework_preregistration as prereg


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def synthetic_price(symbol: str, offset: int) -> float:
    seed = sum(ord(char) for char in symbol)
    drift = 0.035 + (seed % 9) * 0.004
    wave = math.sin(offset / (13 + (seed % 5))) * (1.0 + (seed % 4) * 0.15)
    dip = -8.0 if symbol in {"SPY", "QQQ", "XLK", "XLY"} and 380 <= offset <= 430 else 0.0
    return max(5.0, 80.0 + (seed % 23) + offset * drift + wave + dip)


def write_cache(path: Path, symbol: str, start_days_ago: int) -> None:
    today = date.today()
    rows = []
    for offset in range(start_days_ago + 1):
        current = today - timedelta(days=start_days_ago - offset)
        close = synthetic_price(symbol, offset)
        rows.append(
            {
                "date": current.isoformat(),
                "open": round(close * 0.998, 6),
                "high": round(close * 1.006, 6),
                "low": round(close * 0.994, 6),
                "close": round(close, 6),
                "adj_close": round(close, 6),
                "volume": 250000 + offset,
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
                        "id": discovery.active.VM_ID,
                        "strategy_id": discovery.active.VM_ID,
                        "status": "active_observation",
                        "paper_forward_active": True,
                        "candidate_exhaustive_run": False,
                        "rules_frozen": True,
                    },
                    {
                        "id": discovery.active.DSR_ID,
                        "strategy_id": discovery.active.DSR_ID,
                        "status": "active_observation",
                        "paper_forward_active": True,
                        "candidate_exhaustive_run": False,
                        "rules_frozen": True,
                    },
                    {
                        "id": discovery.active.SPY_200D_ID,
                        "strategy_id": discovery.active.SPY_200D_ID,
                        "status": "frozen_active_control",
                        "paper_forward_active": False,
                        "candidate_exhaustive_run": False,
                        "rules_frozen": True,
                    },
                    {
                        "id": "gror_balanced_momentum_60_40_v1",
                        "strategy_id": "gror_balanced_momentum_60_40_v1",
                        "status": "historical_reject",
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
    roadmap.write_text(
        "# Research Roadmap\n\nCurrent next action: `pre_register_second_expansion_discovery_batch_with_lane_framework`\n",
        encoding="utf-8",
    )
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
    required_symbols = sorted(set(discovery.ALL_CANDIDATE_SYMBOLS + discovery.active.REQUIRED_CACHE_SYMBOLS))
    for symbol in required_symbols:
        start_days = 520 if symbol in {"DBMF", "KMLM", "CTA"} else 920
        write_cache(root / discovery.CACHE_DIR / f"{symbol}.csv", symbol, start_days)
    sector_next = root / prereg.SECTOR_RS_PREREG_DIR / "sector_rs_limited_history_next_action.md"
    sector_next.parent.mkdir(parents=True, exist_ok=True)
    sector_next.write_text("`run_sector_rs_limited_history_discovery_batch`\n", encoding="utf-8")
    lane_framework = root / prereg.LANE_FRAMEWORK_DIR / "lane_gate_framework.yaml"
    lane_framework.parent.mkdir(parents=True, exist_ok=True)
    lane_framework.write_text(yaml.safe_dump({"lanes": {lane: {} for lane in prereg.LANE_IDS}}, sort_keys=False), encoding="utf-8")


@pytest.fixture(scope="module")
def discovery_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    root = tmp_path_factory.mktemp("second_expansion_discovery")
    write_fixture(root)
    prereg.run_second_expansion_with_lane_framework_preregistration(root)
    patch.run_second_expansion_rule_freeze_patch(root)
    batch_before = (root / discovery.PREREG_DIR / "second_expansion_batch.yaml").read_text(encoding="utf-8")
    registry_before = yaml.safe_load((root / discovery.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result = discovery.run_second_expansion_discovery_batch_with_lane_framework(root)
    registry_after = yaml.safe_load((root / discovery.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    batch_after = (root / discovery.PREREG_DIR / "second_expansion_batch.yaml").read_text(encoding="utf-8")
    result["root"] = str(root)
    result["registry_before"] = registry_before
    result["registry_after"] = registry_after
    result["batch_before"] = batch_before
    result["batch_after"] = batch_after
    return result


def output(discovery_run: dict[str, object]) -> Path:
    return Path(discovery_run["output_dir"])


def manifest(discovery_run: dict[str, object]) -> dict[str, object]:
    return json.loads((output(discovery_run) / "second_expansion_discovery_manifest.json").read_text(encoding="utf-8"))


def consistency(discovery_run: dict[str, object]) -> dict[str, object]:
    return json.loads((output(discovery_run) / "second_expansion_discovery_consistency_check.json").read_text(encoding="utf-8"))


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def candidate_results(discovery_run: dict[str, object]) -> list[dict[str, str]]:
    return rows(output(discovery_run) / "second_expansion_candidate_results.csv")


def test_exactly_five_authorized_candidates_evaluated(discovery_run: dict[str, object]) -> None:
    assert manifest(discovery_run)["candidate_ids"] == discovery.AUTHORIZED_CANDIDATES
    assert manifest(discovery_run)["candidate_count"] == 5


def test_no_excluded_candidates_evaluated(discovery_run: dict[str, object]) -> None:
    candidate_ids = {row["candidate_id"] for row in candidate_results(discovery_run)}
    assert candidate_ids.isdisjoint(discovery.EXCLUDED_CANDIDATES)


def test_lane_framework_labels_used_for_all_candidates(discovery_run: dict[str, object]) -> None:
    lane_rows = rows(output(discovery_run) / "second_expansion_lane_results.csv")
    assert {row["candidate_id"] for row in lane_rows} == set(discovery.AUTHORIZED_CANDIDATES)
    assert {row["lane_id"] for row in lane_rows} == set(discovery.LANES.values())


def test_frozen_rules_unchanged(discovery_run: dict[str, object]) -> None:
    assert discovery_run["batch_before"] == discovery_run["batch_after"]
    assert manifest(discovery_run)["frozen_rules_changed"] is False


def test_no_provider_download(discovery_run: dict[str, object]) -> None:
    assert manifest(discovery_run)["provider_download"] is False


def test_no_candidate_exhaustive_produced(discovery_run: dict[str, object]) -> None:
    loaded = manifest(discovery_run)
    assert loaded["candidate_exhaustive_run"] is False
    assert all(row["outcome"] != "candidate_exhaustive" for row in candidate_results(discovery_run))


def test_no_paper_forward_action_produced(discovery_run: dict[str, object]) -> None:
    loaded = manifest(discovery_run)
    assert loaded["paper_forward_review"] is False
    assert loaded["paper_forward_activation"] is False
    assert all("paper_forward" not in row["outcome"] for row in candidate_results(discovery_run))


def test_no_broker_or_live_order_path_touched(discovery_run: dict[str, object]) -> None:
    loaded = manifest(discovery_run)
    assert loaded["broker_path_touched"] is False
    assert loaded["live_orders"] is False


def test_no_real_money_recommendation(discovery_run: dict[str, object]) -> None:
    assert manifest(discovery_run)["real_money_recommendation"] is False


def test_old_stale_gror_state_not_resumed(discovery_run: dict[str, object]) -> None:
    assert manifest(discovery_run)["old_gld_gror_state_resumed"] is False
    assert "gror_balanced_momentum_60_40_v1" not in manifest(discovery_run)["candidate_ids"]


def test_sector_rs_not_run(discovery_run: dict[str, object]) -> None:
    assert manifest(discovery_run)["sector_rs_discovery_run"] is False
    assert "sector_rs_weekly_cash_filter_v1" not in manifest(discovery_run)["candidate_ids"]


def test_intraday_and_event_candidates_not_included(discovery_run: dict[str, object]) -> None:
    loaded = manifest(discovery_run)
    assert loaded["intraday_candidates_included"] is False
    assert loaded["event_data_candidates_included"] is False


def test_managed_futures_limited_history_same_window_only(discovery_run: dict[str, object]) -> None:
    text = (output(discovery_run) / "second_expansion_limited_history_diagnostics.md").read_text(encoding="utf-8")
    same_window = rows(output(discovery_run) / "second_expansion_same_window_benchmarks.csv")
    managed_rows = [row for row in same_window if row["candidate_id"] == "managed_futures_etf_trend_wrapper_v1"]
    assert "Same-window benchmark treatment required: `true`" in text
    assert managed_rows


def test_macro_limited_history_candidate_not_full_promoted(discovery_run: dict[str, object]) -> None:
    lane_rows = rows(output(discovery_run) / "second_expansion_lane_results.csv")
    managed = next(row for row in lane_rows if row["candidate_id"] == "managed_futures_etf_trend_wrapper_v1")
    assert managed["outcome"] != "promotion_review_candidate_macro"
    assert consistency(discovery_run)["managed_futures_full_macro_promotion_blocked"] is True


def test_tactical_daily_bar_stop_timing_represented(discovery_run: dict[str, object]) -> None:
    tactical = rows(output(discovery_run) / "second_expansion_tactical_diagnostics.csv")
    by_id = {row["candidate_id"]: row for row in tactical}
    assert by_id["donchian_atr_breakout_etf_v1"]["stop_timing_or_calendar_rule"] == "close_based_atr_stop"


def test_turn_of_month_exact_calendar_window_represented(discovery_run: dict[str, object]) -> None:
    tactical = rows(output(discovery_run) / "second_expansion_tactical_diagnostics.csv")
    by_id = {row["candidate_id"]: row for row in tactical}
    assert by_id["turn_of_month_spy_qqq_v1"]["stop_timing_or_calendar_rule"] == "last4_first3_calendar_window"


def test_overlay_contribution_represented_as_diagnostic(discovery_run: dict[str, object]) -> None:
    overlay = rows(output(discovery_run) / "second_expansion_overlay_contribution.csv")
    assert overlay[0]["candidate_id"] == "cash_pause_overlay_meta_v1"
    assert overlay[0]["outcome"] in discovery.VALID_OUTCOMES["cash_pause_overlay_meta_v1"]


def test_benchmark_deltas_exported(discovery_run: dict[str, object]) -> None:
    delta_rows = rows(output(discovery_run) / "second_expansion_benchmark_deltas.csv")
    assert delta_rows
    assert {row["candidate_id"] for row in delta_rows} == set(discovery.AUTHORIZED_CANDIDATES[:-1])


def test_risk_gates_exported(discovery_run: dict[str, object]) -> None:
    risk_rows = rows(output(discovery_run) / "second_expansion_risk_gate_results.csv")
    assert {row["candidate_id"] for row in risk_rows} == set(discovery.AUTHORIZED_CANDIDATES[:-1])


def test_slippage_stress_exported(discovery_run: dict[str, object]) -> None:
    stress_rows = rows(output(discovery_run) / "second_expansion_slippage_stress_results.csv")
    assert {row["candidate_id"] for row in stress_rows} == set(discovery.AUTHORIZED_CANDIDATES[:-1])


def test_promotion_watchlist_and_rejection_files_exported(discovery_run: dict[str, object]) -> None:
    out = output(discovery_run)
    assert (out / "second_expansion_promotion_candidates.csv").exists()
    assert (out / "second_expansion_watchlist_candidates.csv").exists()
    assert (out / "second_expansion_rejection_reasons.md").exists()


def test_next_action_valid_and_explicit(discovery_run: dict[str, object]) -> None:
    loaded = manifest(discovery_run)
    text = (output(discovery_run) / "second_expansion_next_action.md").read_text(encoding="utf-8")
    assert loaded["next_action"] in discovery.VALID_NEXT_ACTIONS
    assert f"`{loaded['next_action']}`" in text


def test_consistency_check_passes(discovery_run: dict[str, object]) -> None:
    assert consistency(discovery_run)["consistency_passed"] is True


def test_registry_and_roadmap_metadata_update_without_active_mutations(discovery_run: dict[str, object]) -> None:
    loaded = manifest(discovery_run)
    assert loaded["registry_metadata_updated"] is True
    assert loaded["roadmap_updated"] is True
    assert discovery_run["registry_before"] == discovery_run["registry_after"]
