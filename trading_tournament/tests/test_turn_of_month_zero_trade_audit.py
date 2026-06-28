from __future__ import annotations

import csv
import json
import math
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml

import run_turn_of_month_zero_trade_audit as audit


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def synthetic_price(symbol: str, offset: int) -> float:
    drift = {"SPY": 0.055, "QQQ": 0.075, "BIL": 0.004}[symbol]
    wave = math.sin(offset / 19.0) * (0.4 if symbol != "BIL" else 0.02)
    return 50.0 + offset * drift + wave


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
                "volume": 1000000 + offset,
                "symbol": symbol,
            }
        )
    write_csv(path, rows, ["date", "open", "high", "low", "close", "adj_close", "volume", "symbol"])


def write_fixture(root: Path) -> None:
    registry_path = root / audit.REGISTRY_PATH
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
                        "id": audit.CANDIDATE_ID,
                        "strategy_id": audit.CANDIDATE_ID,
                        "status": "discovery_reject",
                        "paper_forward_active": False,
                        "candidate_exhaustive_run": False,
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    roadmap = root / audit.ROADMAP_PATH
    roadmap.parent.mkdir(parents=True, exist_ok=True)
    roadmap.write_text("# Research Roadmap\n\nCurrent next action: `audit_turn_of_month_zero_trade_result`\n", encoding="utf-8")
    batch = {
        "metadata": {"included_candidate_ids": [audit.CANDIDATE_ID], "next_action": "run_second_expansion_discovery_batch_with_lane_framework"},
        "candidates": [
            {
                "candidate_id": audit.CANDIDATE_ID,
                "lane_id": audit.LANE_ID,
                "allowed_instruments": audit.UNIVERSE,
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
        [{"candidate_id": audit.CANDIDATE_ID, "trade_count": 0, "stop_timing_or_calendar_rule": "last4_first3_calendar_window"}],
        ["candidate_id", "trade_count", "stop_timing_or_calendar_rule"],
    )
    sector_path = root / audit.SECTOR_RS_DIR / "sector_rs_limited_history_discovery_manifest.json"
    sector_path.parent.mkdir(parents=True, exist_ok=True)
    sector_path.write_text(json.dumps({"next_action": "audit_turn_of_month_zero_trade_result"}, indent=2), encoding="utf-8")
    for symbol in audit.UNIVERSE:
        write_cache(root / audit.CACHE_DIR / f"{symbol}.csv", symbol)


@pytest.fixture(scope="module")
def audit_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    root = tmp_path_factory.mktemp("turn_of_month_zero_trade")
    write_fixture(root)
    before = yaml.safe_load((root / audit.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result = audit.run_turn_of_month_zero_trade_audit(root)
    after = yaml.safe_load((root / audit.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result["root"] = str(root)
    result["strategies_before"] = before
    result["strategies_after"] = after
    return result


def output(audit_run: dict[str, Any]) -> Path:
    return Path(audit_run["output_dir"])


def manifest(audit_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(audit_run) / "turn_of_month_zero_trade_audit_manifest.json").read_text(encoding="utf-8"))


def consistency(audit_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(audit_run) / "turn_of_month_zero_trade_consistency_check.json").read_text(encoding="utf-8"))


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_audit_only_mode(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["audit_only"] is True


def test_no_new_discovery(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["new_discovery_run"] is False


def test_no_new_backtest(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["new_backtests_run"] is False


def test_no_performance_metrics_from_new_tests(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["performance_metrics_computed_from_new_tests"] is False


def test_no_provider_download(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["provider_download"] is False


def test_no_candidate_exhaustive(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["candidate_exhaustive_run"] is False


def test_no_paper_forward_action(audit_run: dict[str, Any]) -> None:
    loaded = manifest(audit_run)
    assert loaded["paper_forward_review"] is False
    assert loaded["paper_forward_activation"] is False


def test_no_broker_live_path(audit_run: dict[str, Any]) -> None:
    loaded = manifest(audit_run)
    assert loaded["broker_path_touched"] is False
    assert loaded["live_orders"] is False


def test_frozen_rule_unchanged(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["frozen_rule_changed"] is False


def test_candidate_status_unchanged(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["candidate_status_changed"] is False
    assert audit_run["strategies_before"] == audit_run["strategies_after"]


def test_calendar_window_counts_are_exported(audit_run: dict[str, Any]) -> None:
    assert rows(output(audit_run) / "turn_of_month_window_counts.csv")


def test_signal_funnel_is_exported(audit_run: dict[str, Any]) -> None:
    funnel = rows(output(audit_run) / "turn_of_month_signal_funnel.csv")
    assert {row["stage"] for row in funnel} >= {"entry_signal_count_before_execution", "entry_signal_count_after_filters"}


def test_block_reason_counts_are_exported(audit_run: dict[str, Any]) -> None:
    block_rows = rows(output(audit_run) / "turn_of_month_block_reason_counts.csv")
    assert {row["block_reason"] for row in block_rows} >= {"calendar_window_construction_issue", "bil_fallback_issue"}


def test_data_availability_check_exists(audit_run: dict[str, Any]) -> None:
    assert rows(output(audit_run) / "turn_of_month_data_availability_check.csv")


def test_implementation_findings_exist(audit_run: dict[str, Any]) -> None:
    text = (output(audit_run) / "turn_of_month_implementation_findings.md").read_text(encoding="utf-8")
    assert audit.CANDIDATE_ID in text


def test_manifest_records_zero_trade_result(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["zero_trade_result_confirmed"] is True


def test_manifest_records_implementation_bug_flag(audit_run: dict[str, Any]) -> None:
    assert manifest(audit_run)["implementation_bug_found"] is True


def test_next_action_is_valid(audit_run: dict[str, Any]) -> None:
    loaded = manifest(audit_run)
    assert loaded["next_action"] in audit.VALID_NEXT_ACTIONS
    assert consistency(audit_run)["consistency_passed"] is True
