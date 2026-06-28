from __future__ import annotations

import csv
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml

import run_third_expansion_with_lane_framework_preregistration as prereg


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_cache(path: Path, symbol: str, days: int = 620) -> None:
    today = date.today()
    rows = []
    for offset in range(days):
        current = today - timedelta(days=days - 1 - offset)
        close = 80.0 + offset * 0.05 + (sum(ord(char) for char in symbol) % 17)
        rows.append(
            {
                "date": current.isoformat(),
                "open": round(close * 0.999, 6),
                "high": round(close * 1.004, 6),
                "low": round(close * 0.996, 6),
                "close": round(close, 6),
                "adj_close": round(close, 6),
                "volume": 500000 + offset,
                "symbol": symbol,
            }
        )
    write_csv(path, rows, ["date", "open", "high", "low", "close", "adj_close", "volume", "symbol"])


def write_fixture(root: Path, missing_symbol: str | None = None) -> None:
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
                    "current_next_action": "pre_register_third_expansion_discovery_batch_with_lane_framework",
                },
                "strategies": [
                    {
                        "id": "paper_forward_vm_quality_lowvol_proxy_v1",
                        "strategy_id": "paper_forward_vm_quality_lowvol_proxy_v1",
                        "status": "active_observation",
                        "paper_forward_active": True,
                        "candidate_exhaustive_run": False,
                    },
                    {
                        "id": "turn_of_month_spy_qqq_v1",
                        "strategy_id": "turn_of_month_spy_qqq_v1",
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
    roadmap.write_text(
        "# Research Roadmap\n\nCurrent next action: `pre_register_third_expansion_discovery_batch_with_lane_framework`\n",
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
                        "cache_ready": symbol != missing_symbol,
                    }
                    for symbol in prereg.required_symbols()
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    for symbol in prereg.required_symbols():
        if symbol != missing_symbol:
            write_cache(root / prereg.CACHE_DIR / f"{symbol}.csv", symbol)
    lane_framework = root / prereg.LANE_FRAMEWORK_DIR / "lane_gate_framework.yaml"
    lane_framework.parent.mkdir(parents=True, exist_ok=True)
    lane_framework.write_text(yaml.safe_dump({"lanes": {lane: {} for lane in prereg.LANE_IDS}}, sort_keys=False), encoding="utf-8")


@pytest.fixture(scope="module")
def sufficient_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    root = tmp_path_factory.mktemp("third_expansion_sufficient")
    write_fixture(root)
    before = yaml.safe_load((root / prereg.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result = prereg.run_third_expansion_with_lane_framework_preregistration(root)
    after = yaml.safe_load((root / prereg.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result["strategies_before"] = before
    result["strategies_after"] = after
    return result


@pytest.fixture(scope="module")
def missing_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    root = tmp_path_factory.mktemp("third_expansion_missing")
    write_fixture(root, missing_symbol="AGG")
    return prereg.run_third_expansion_with_lane_framework_preregistration(root)


def output(run: dict[str, Any]) -> Path:
    return Path(run["output_dir"])


def manifest(run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(run) / "third_expansion_manifest.json").read_text(encoding="utf-8"))


def batch(run: dict[str, Any]) -> dict[str, Any]:
    return yaml.safe_load((output(run) / "third_expansion_batch.yaml").read_text(encoding="utf-8"))


def consistency(run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(run) / "third_expansion_consistency_check.json").read_text(encoding="utf-8"))


def test_pre_registration_only(sufficient_run: dict[str, Any]) -> None:
    assert manifest(sufficient_run)["pre_registration_only"] is True


def test_data_availability_audit_only(sufficient_run: dict[str, Any]) -> None:
    assert manifest(sufficient_run)["data_availability_audit_only"] is True


def test_candidate_count_between_three_and_five(sufficient_run: dict[str, Any]) -> None:
    assert 3 <= len(batch(sufficient_run)["candidates"]) <= 5


def test_unique_candidate_ids(sufficient_run: dict[str, Any]) -> None:
    candidate_ids = [candidate["candidate_id"] for candidate in batch(sufficient_run)["candidates"]]
    assert len(candidate_ids) == len(set(candidate_ids))


def test_every_candidate_has_exactly_one_lane(sufficient_run: dict[str, Any]) -> None:
    assert all(isinstance(candidate["lane_id"], str) and candidate["lane_id"] for candidate in batch(sufficient_run)["candidates"])


def test_lane_ids_are_valid_from_framework(sufficient_run: dict[str, Any]) -> None:
    assert {candidate["lane_id"] for candidate in batch(sufficient_run)["candidates"]} <= prereg.LANE_IDS


def test_failure_lessons_file_exists(sufficient_run: dict[str, Any]) -> None:
    assert (output(sufficient_run) / "third_expansion_failure_lessons_applied.md").exists()


def test_no_exact_rejected_variant_is_included(sufficient_run: dict[str, Any]) -> None:
    candidate_ids = {candidate["candidate_id"] for candidate in batch(sufficient_run)["candidates"]}
    assert candidate_ids.isdisjoint(prereg.EXACT_REJECTED_VARIANTS)


def test_old_gld_gror_state_is_not_resumed(sufficient_run: dict[str, Any]) -> None:
    assert manifest(sufficient_run)["old_gld_gror_state_resumed"] is False


def test_no_intraday_demo_candidate_is_included(sufficient_run: dict[str, Any]) -> None:
    loaded = manifest(sufficient_run)
    candidate_ids = {candidate["candidate_id"] for candidate in batch(sufficient_run)["candidates"]}
    assert loaded["intraday_demo_candidate_included"] is False
    assert "intraday_readiness_audit_v1" not in candidate_ids


def test_no_event_data_candidate_is_included(sufficient_run: dict[str, Any]) -> None:
    assert manifest(sufficient_run)["event_data_candidate_included"] is False


def test_no_backtest_or_discovery_is_run(sufficient_run: dict[str, Any]) -> None:
    loaded = manifest(sufficient_run)
    assert loaded["backtests_run"] is False
    assert loaded["discovery_run"] is False


def test_no_performance_metrics_are_computed(sufficient_run: dict[str, Any]) -> None:
    assert manifest(sufficient_run)["performance_metrics_computed"] is False


def test_no_provider_download_occurs(sufficient_run: dict[str, Any]) -> None:
    assert manifest(sufficient_run)["provider_download"] is False


def test_no_candidate_exhaustive_or_paper_forward_action(sufficient_run: dict[str, Any]) -> None:
    loaded = manifest(sufficient_run)
    assert loaded["candidate_exhaustive_run"] is False
    assert loaded["paper_forward_review"] is False
    assert loaded["paper_forward_activation"] is False


def test_no_broker_live_path_is_touched(sufficient_run: dict[str, Any]) -> None:
    loaded = manifest(sufficient_run)
    assert loaded["broker_path_touched"] is False
    assert loaded["live_orders"] is False


def test_data_availability_report_exists(sufficient_run: dict[str, Any]) -> None:
    assert (output(sufficient_run) / "third_expansion_data_availability_report.md").exists()


def test_missing_data_report_exists_even_if_empty(sufficient_run: dict[str, Any]) -> None:
    assert (output(sufficient_run) / "third_expansion_missing_data_report.md").exists()


def test_next_action_is_discovery_only_if_data_is_sufficient(sufficient_run: dict[str, Any]) -> None:
    loaded = manifest(sufficient_run)
    assert loaded["data_availability_status"] == prereg.DATA_STATUS_SUFFICIENT
    assert loaded["next_action"] == prereg.NEXT_ACTION_DISCOVERY


def test_next_action_is_data_refresh_or_manual_review_if_required_data_is_missing_or_unknown(missing_run: dict[str, Any]) -> None:
    loaded = manifest(missing_run)
    assert loaded["data_availability_status"] in {prereg.DATA_STATUS_MISSING, prereg.DATA_STATUS_UNKNOWN}
    assert loaded["next_action"] in {prereg.NEXT_ACTION_DATA, prereg.NEXT_ACTION_MANUAL}


def test_valid_future_outcomes_are_lane_specific_and_safe(sufficient_run: dict[str, Any]) -> None:
    for candidate in batch(sufficient_run)["candidates"]:
        outcomes = set(candidate["valid_future_outcomes"])
        assert outcomes.isdisjoint(prereg.FORBIDDEN_OUTCOMES)
        if candidate["lane_id"] == "macro_gld_duration_risk_off_lane":
            assert outcomes == set(prereg.MACRO_OUTCOMES)
        if candidate["lane_id"] == "moderate_tactical_etf_lane":
            assert outcomes == set(prereg.STRATEGY_OUTCOMES)
        if candidate["candidate_id"] == "static_all_weather_benchmark_v1":
            assert outcomes == set(prereg.CONTROL_OUTCOMES)


def test_manifest_flags_match_strict_scope(sufficient_run: dict[str, Any]) -> None:
    loaded = manifest(sufficient_run)
    for key, value in prereg.MANIFEST_FLAGS.items():
        assert loaded[key] == value
    assert consistency(sufficient_run)["consistency_passed"] is True
    assert sufficient_run["strategies_before"] == sufficient_run["strategies_after"]
