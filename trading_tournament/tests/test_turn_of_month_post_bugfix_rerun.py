from __future__ import annotations

import csv
import json
import math
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml

import run_turn_of_month_post_bugfix_rerun as rerun
import run_turn_of_month_zero_trade_audit as audit
import run_turn_of_month_zero_trade_fix as fix


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def synthetic_price(symbol: str, offset: int) -> float:
    seed = sum(ord(char) for char in symbol)
    if symbol == "BIL":
        return 50.0 + offset * 0.002 + math.sin(offset / 31.0) * 0.01
    drift = 0.035 + (seed % 11) * 0.003
    wave = math.sin(offset / (17 + seed % 7)) * (0.6 + (seed % 5) * 0.08)
    dip = -5.0 if symbol in {"SPY", "QQQ"} and 360 <= offset <= 410 else 0.0
    return max(5.0, 70.0 + (seed % 19) + offset * drift + wave + dip)


def write_cache(path: Path, symbol: str, days: int = 920) -> None:
    today = date.today()
    rows = []
    for offset in range(days + 1):
        current = today - timedelta(days=days - offset)
        close = synthetic_price(symbol, offset)
        rows.append(
            {
                "date": current.isoformat(),
                "open": round(close * 0.999, 6),
                "high": round(close * 1.004, 6),
                "low": round(close * 0.996, 6),
                "close": round(close, 6),
                "adj_close": round(close, 6),
                "volume": 1_000_000 + offset,
                "symbol": symbol,
            }
        )
    write_csv(path, rows, ["date", "open", "high", "low", "close", "adj_close", "volume", "symbol"])


def write_fixture(root: Path) -> None:
    registry_path = root / rerun.REGISTRY_PATH
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
                    "current_next_action": "audit_turn_of_month_zero_trade_result",
                },
                "strategies": [
                    {
                        "id": rerun.CANDIDATE_ID,
                        "strategy_id": rerun.CANDIDATE_ID,
                        "status": "discovery_reject",
                        "paper_forward_active": False,
                        "candidate_exhaustive_run": False,
                    },
                    {
                        "id": rerun.second.active.VM_ID,
                        "strategy_id": rerun.second.active.VM_ID,
                        "status": "active_observation",
                        "paper_forward_active": True,
                        "candidate_exhaustive_run": False,
                    },
                    {
                        "id": rerun.second.active.DSR_ID,
                        "strategy_id": rerun.second.active.DSR_ID,
                        "status": "active_observation",
                        "paper_forward_active": True,
                        "candidate_exhaustive_run": False,
                    },
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    roadmap = root / rerun.ROADMAP_PATH
    roadmap.parent.mkdir(parents=True, exist_ok=True)
    roadmap.write_text("# Research Roadmap\n\nCurrent next action: `audit_turn_of_month_zero_trade_result`\n", encoding="utf-8")
    batch = {
        "metadata": {
            "included_candidate_ids": [rerun.CANDIDATE_ID],
            "next_action": "run_second_expansion_discovery_batch_with_lane_framework",
        },
        "candidates": [
            {
                "candidate_id": rerun.CANDIDATE_ID,
                "lane_id": rerun.LANE_ID,
                "allowed_instruments": rerun.UNIVERSE,
                "frozen_rule": [
                    "Turn-of-month window: last 4 trading days of each calendar month through the first 3 trading days of the next calendar month.",
                    "On the first eligible trading day of the window, compare SPY and QQQ by fixed 63-trading-day total return.",
                    "Select the higher-ranked asset only if it is above its 200-day SMA.",
                ],
            }
        ],
    }
    batch_path = root / audit.PREREG_DIR / "second_expansion_batch.yaml"
    batch_path.parent.mkdir(parents=True, exist_ok=True)
    batch_path.write_text(yaml.safe_dump(batch, sort_keys=False), encoding="utf-8")
    patch_path = root / audit.RULE_PATCH_DIR / "second_expansion_rule_freeze_patch_manifest.json"
    patch_path.parent.mkdir(parents=True, exist_ok=True)
    patch_path.write_text(json.dumps({"turn_of_month_rule_fully_frozen": True}, indent=2), encoding="utf-8")
    second_dir = root / audit.SECOND_EXPANSION_DIR
    second_dir.mkdir(parents=True, exist_ok=True)
    (second_dir / "second_expansion_discovery_manifest.json").write_text(
        json.dumps({"next_action": "run_sector_rs_limited_history_discovery_batch"}, indent=2),
        encoding="utf-8",
    )
    write_csv(
        second_dir / "second_expansion_tactical_diagnostics.csv",
        [
            {
                "candidate_id": rerun.CANDIDATE_ID,
                "trade_count": 0,
                "stop_timing_or_calendar_rule": "last4_first3_calendar_window",
            }
        ],
        ["candidate_id", "trade_count", "stop_timing_or_calendar_rule"],
    )
    sector_path = root / audit.SECTOR_RS_DIR / "sector_rs_limited_history_discovery_manifest.json"
    sector_path.parent.mkdir(parents=True, exist_ok=True)
    sector_path.write_text(json.dumps({"next_action": "audit_turn_of_month_zero_trade_result"}, indent=2), encoding="utf-8")
    for symbol in rerun.LOAD_SYMBOLS:
        write_cache(root / rerun.CACHE_DIR / f"{symbol}.csv", symbol)


@pytest.fixture(scope="module")
def post_bugfix_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    root = tmp_path_factory.mktemp("turn_of_month_post_bugfix_rerun")
    write_fixture(root)
    audit.run_turn_of_month_zero_trade_audit(root)
    fix.run_turn_of_month_zero_trade_fix(root)
    strategies_before = yaml.safe_load((root / rerun.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result = rerun.run_turn_of_month_post_bugfix_rerun(root)
    strategies_after = yaml.safe_load((root / rerun.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result["root"] = str(root)
    result["strategies_before"] = strategies_before
    result["strategies_after"] = strategies_after
    return result


def output(post_bugfix_run: dict[str, Any]) -> Path:
    return Path(post_bugfix_run["output_dir"])


def manifest(post_bugfix_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(post_bugfix_run) / "turn_of_month_post_bugfix_rerun_manifest.json").read_text(encoding="utf-8"))


def consistency(post_bugfix_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(post_bugfix_run) / "turn_of_month_post_bugfix_consistency_check.json").read_text(encoding="utf-8"))


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_exactly_one_candidate_is_evaluated(post_bugfix_run: dict[str, Any]) -> None:
    loaded = manifest(post_bugfix_run)
    assert loaded["candidate_count"] == 1
    assert loaded["evaluated_candidate_ids"] == [rerun.CANDIDATE_ID]


def test_candidate_is_exact_turn_of_month_candidate(post_bugfix_run: dict[str, Any]) -> None:
    assert manifest(post_bugfix_run)["candidate_id"] == "turn_of_month_spy_qqq_v1"
    assert rows(output(post_bugfix_run) / "turn_of_month_post_bugfix_candidate_results.csv")[0]["candidate_id"] == rerun.CANDIDATE_ID


def test_no_excluded_candidates_are_evaluated(post_bugfix_run: dict[str, Any]) -> None:
    evaluated = set(manifest(post_bugfix_run)["evaluated_candidate_ids"])
    assert evaluated.isdisjoint(rerun.EXCLUDED_CANDIDATES)


def test_frozen_rule_is_unchanged(post_bugfix_run: dict[str, Any]) -> None:
    assert manifest(post_bugfix_run)["frozen_rule_changed"] is False


def test_calendar_window_is_unchanged(post_bugfix_run: dict[str, Any]) -> None:
    assert manifest(post_bugfix_run)["calendar_window_changed"] is False


def test_selection_rule_is_unchanged(post_bugfix_run: dict[str, Any]) -> None:
    assert manifest(post_bugfix_run)["selection_rule_changed"] is False


def test_sma_filter_is_unchanged(post_bugfix_run: dict[str, Any]) -> None:
    assert manifest(post_bugfix_run)["sma_filter_changed"] is False


def test_provider_download_is_false(post_bugfix_run: dict[str, Any]) -> None:
    assert manifest(post_bugfix_run)["provider_download"] is False


def test_outcome_is_limited_to_valid_discovery_outcomes(post_bugfix_run: dict[str, Any]) -> None:
    loaded = manifest(post_bugfix_run)
    assert loaded["discovery_outcome"] in rerun.VALID_OUTCOMES
    assert loaded["discovery_outcome"] not in rerun.FORBIDDEN_OUTCOMES


def test_no_candidate_exhaustive(post_bugfix_run: dict[str, Any]) -> None:
    assert manifest(post_bugfix_run)["candidate_exhaustive_run"] is False


def test_no_paper_forward_action_or_flag_change(post_bugfix_run: dict[str, Any]) -> None:
    loaded = manifest(post_bugfix_run)
    assert loaded["paper_forward_review"] is False
    assert loaded["paper_forward_activation"] is False
    assert post_bugfix_run["strategies_before"] == post_bugfix_run["strategies_after"]


def test_no_broker_or_live_path(post_bugfix_run: dict[str, Any]) -> None:
    loaded = manifest(post_bugfix_run)
    assert loaded["broker_path_touched"] is False
    assert loaded["live_orders"] is False


def test_sector_rs_discovery_is_not_run(post_bugfix_run: dict[str, Any]) -> None:
    assert manifest(post_bugfix_run)["sector_rs_discovery_run"] is False


def test_intraday_and_event_candidates_are_not_included(post_bugfix_run: dict[str, Any]) -> None:
    loaded = manifest(post_bugfix_run)
    assert loaded["intraday_candidates_included"] is False
    assert loaded["event_data_candidates_included"] is False


def test_signal_entry_reconciliation_file_exists(post_bugfix_run: dict[str, Any]) -> None:
    assert (output(post_bugfix_run) / "turn_of_month_post_bugfix_signal_entry_reconciliation.md").exists()


def test_signal_entry_reconciliation_status_is_recorded(post_bugfix_run: dict[str, Any]) -> None:
    assert manifest(post_bugfix_run)["signal_entry_reconciliation_status"]


def test_risk_gate_results_exist(post_bugfix_run: dict[str, Any]) -> None:
    assert rows(output(post_bugfix_run) / "turn_of_month_post_bugfix_risk_gate_results.csv")


def test_slippage_stress_results_exist(post_bugfix_run: dict[str, Any]) -> None:
    assert rows(output(post_bugfix_run) / "turn_of_month_post_bugfix_slippage_stress_results.csv")


def test_benchmark_deltas_exist_or_report_unavailable(post_bugfix_run: dict[str, Any]) -> None:
    delta_rows = rows(output(post_bugfix_run) / "turn_of_month_post_bugfix_benchmark_deltas.csv")
    assert delta_rows
    assert all(row["benchmark_available"] == "True" or row["unavailable_reason"] for row in delta_rows)


def test_promotion_candidate_file_exists_even_if_empty(post_bugfix_run: dict[str, Any]) -> None:
    assert (output(post_bugfix_run) / "turn_of_month_post_bugfix_promotion_candidates.csv").exists()


def test_rejection_reasons_exist_if_rejected(post_bugfix_run: dict[str, Any]) -> None:
    if manifest(post_bugfix_run)["discovery_outcome"] == "discovery_reject":
        assert (output(post_bugfix_run) / "turn_of_month_post_bugfix_rejection_reasons.md").exists()


def test_manifest_flags_match_strict_scope(post_bugfix_run: dict[str, Any]) -> None:
    loaded = manifest(post_bugfix_run)
    assert all(loaded[key] == value for key, value in rerun.MANIFEST_FLAGS.items())
    assert loaded["old_gld_gror_state_resumed"] is False
    assert loaded["real_money_recommendation"] is False
    assert loaded["next_action"] in rerun.VALID_NEXT_ACTIONS
    assert consistency(post_bugfix_run)["consistency_passed"] is True
