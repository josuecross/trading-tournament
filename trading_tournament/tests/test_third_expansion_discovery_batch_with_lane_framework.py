from __future__ import annotations

import csv
import json
import math
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml

import run_third_expansion_discovery_batch_with_lane_framework as discovery
import run_third_expansion_with_lane_framework_preregistration as prereg


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def synthetic_price(symbol: str, offset: int) -> float:
    seed = sum(ord(char) for char in symbol)
    drift = 0.026 + (seed % 13) * 0.003
    wave = math.sin(offset / (19 + seed % 7)) * (0.5 + (seed % 4) * 0.1)
    if symbol == "BIL":
        return 50.0 + offset * 0.002 + math.sin(offset / 41.0) * 0.01
    return max(5.0, 70.0 + (seed % 31) + offset * drift + wave)


def write_cache(path: Path, symbol: str, days: int = 520) -> None:
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
                "volume": 750000 + offset,
                "symbol": symbol,
            }
        )
    write_csv(path, rows, ["date", "open", "high", "low", "close", "adj_close", "volume", "symbol"])


def write_fixture(root: Path) -> None:
    registry_path = root / discovery.REGISTRY_PATH
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
                        "id": discovery.active.VM_ID,
                        "strategy_id": discovery.active.VM_ID,
                        "status": "active_observation",
                        "paper_forward_active": True,
                        "candidate_exhaustive_run": False,
                    },
                    {
                        "id": discovery.active.DSR_ID,
                        "strategy_id": discovery.active.DSR_ID,
                        "status": "active_observation",
                        "paper_forward_active": True,
                        "candidate_exhaustive_run": False,
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
    roadmap = root / discovery.ROADMAP_PATH
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
                        "cache_ready": True,
                    }
                    for symbol in prereg.required_symbols()
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    for symbol in sorted(set(prereg.required_symbols() + discovery.active.REQUIRED_CACHE_SYMBOLS)):
        write_cache(root / discovery.CACHE_DIR / f"{symbol}.csv", symbol)
    lane_framework = root / prereg.LANE_FRAMEWORK_DIR / "lane_gate_framework.yaml"
    lane_framework.parent.mkdir(parents=True, exist_ok=True)
    lane_framework.write_text(yaml.safe_dump({"lanes": {lane: {} for lane in prereg.LANE_IDS}}, sort_keys=False), encoding="utf-8")


@pytest.fixture(scope="module")
def discovery_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    root = tmp_path_factory.mktemp("third_expansion_discovery")
    write_fixture(root)
    prereg.run_third_expansion_with_lane_framework_preregistration(root)
    batch_before = (root / discovery.PREREG_DIR / "third_expansion_batch.yaml").read_text(encoding="utf-8")
    registry_before = yaml.safe_load((root / discovery.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result = discovery.run_third_expansion_discovery_batch_with_lane_framework(root)
    registry_after = yaml.safe_load((root / discovery.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    batch_after = (root / discovery.PREREG_DIR / "third_expansion_batch.yaml").read_text(encoding="utf-8")
    result["root"] = str(root)
    result["registry_before"] = registry_before
    result["registry_after"] = registry_after
    result["batch_before"] = batch_before
    result["batch_after"] = batch_after
    return result


def output(discovery_run: dict[str, Any]) -> Path:
    return Path(discovery_run["output_dir"])


def manifest(discovery_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(discovery_run) / "third_expansion_discovery_manifest.json").read_text(encoding="utf-8"))


def consistency(discovery_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(discovery_run) / "third_expansion_discovery_consistency_check.json").read_text(encoding="utf-8"))


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def candidate_results(discovery_run: dict[str, Any]) -> list[dict[str, str]]:
    return rows(output(discovery_run) / "third_expansion_candidate_results.csv")


def test_exactly_four_candidates_are_evaluated(discovery_run: dict[str, Any]) -> None:
    assert manifest(discovery_run)["candidate_count"] == 4
    assert len(candidate_results(discovery_run)) == 4


def test_candidate_ids_match_authorized_list(discovery_run: dict[str, Any]) -> None:
    assert manifest(discovery_run)["candidate_ids"] == discovery.AUTHORIZED_CANDIDATES


def test_no_excluded_candidate_is_evaluated(discovery_run: dict[str, Any]) -> None:
    candidate_ids = {row["candidate_id"] for row in candidate_results(discovery_run)}
    assert candidate_ids.isdisjoint(discovery.EXCLUDED_CANDIDATES)


def test_lane_framework_is_used(discovery_run: dict[str, Any]) -> None:
    assert manifest(discovery_run)["lane_framework_used"] is True


def test_frozen_rules_are_unchanged(discovery_run: dict[str, Any]) -> None:
    assert discovery_run["batch_before"] == discovery_run["batch_after"]
    assert manifest(discovery_run)["frozen_rules_changed"] is False


def test_provider_download_is_false(discovery_run: dict[str, Any]) -> None:
    assert manifest(discovery_run)["provider_download"] is False


def test_candidate_outcomes_are_lane_specific_and_valid(discovery_run: dict[str, Any]) -> None:
    for row in candidate_results(discovery_run):
        assert row["outcome"] in discovery.VALID_OUTCOMES[row["candidate_id"]]


def test_no_candidate_goes_to_candidate_exhaustive(discovery_run: dict[str, Any]) -> None:
    assert manifest(discovery_run)["candidate_exhaustive_run"] is False
    assert all(row["outcome"] != "candidate_exhaustive" for row in candidate_results(discovery_run))


def test_no_candidate_goes_to_paper_forward(discovery_run: dict[str, Any]) -> None:
    loaded = manifest(discovery_run)
    assert loaded["paper_forward_review"] is False
    assert loaded["paper_forward_activation"] is False
    assert all("paper_forward" not in row["outcome"] for row in candidate_results(discovery_run))


def test_no_broker_live_path_is_touched(discovery_run: dict[str, Any]) -> None:
    loaded = manifest(discovery_run)
    assert loaded["broker_path_touched"] is False
    assert loaded["live_orders"] is False


def test_old_gld_gror_state_is_not_resumed(discovery_run: dict[str, Any]) -> None:
    assert manifest(discovery_run)["old_gld_gror_state_resumed"] is False
    assert "gror_balanced_momentum_60_40_v1" not in manifest(discovery_run)["candidate_ids"]


def test_intraday_event_candidates_are_not_included(discovery_run: dict[str, Any]) -> None:
    loaded = manifest(discovery_run)
    assert loaded["intraday_demo_candidate_included"] is False
    assert loaded["event_data_candidate_included"] is False


def test_same_window_benchmarks_exist_for_macro_candidates(discovery_run: dict[str, Any]) -> None:
    same_window = rows(output(discovery_run) / "third_expansion_same_window_benchmarks.csv")
    by_candidate = {row["candidate_id"] for row in same_window}
    assert {"dual_momentum_paa_clean_v1", "gld_ief_spy_defensive_rotation_v1"} <= by_candidate


def test_all_weather_candidate_cannot_become_normal_promotion_candidate(discovery_run: dict[str, Any]) -> None:
    by_id = {row["candidate_id"]: row for row in candidate_results(discovery_run)}
    assert by_id["static_all_weather_benchmark_v1"]["outcome"] not in {"promotion_review_candidate", "promotion_review_candidate_macro"}


def test_volatility_regime_has_anti_duplication_diagnostics(discovery_run: dict[str, Any]) -> None:
    diag = rows(output(discovery_run) / "third_expansion_volatility_regime_diagnostics.csv")
    assert diag
    assert {"corr_vs_active_vm", "corr_vs_active_combo"} <= set(diag[0])


def test_risk_gate_results_exist_for_every_candidate(discovery_run: dict[str, Any]) -> None:
    risk_rows = rows(output(discovery_run) / "third_expansion_risk_gate_results.csv")
    assert {row["candidate_id"] for row in risk_rows} == set(discovery.AUTHORIZED_CANDIDATES)


def test_slippage_stress_results_exist_for_every_applicable_candidate(discovery_run: dict[str, Any]) -> None:
    stress_rows = rows(output(discovery_run) / "third_expansion_slippage_stress_results.csv")
    assert {row["candidate_id"] for row in stress_rows} == set(discovery.AUTHORIZED_CANDIDATES)


def test_benchmark_deltas_exist_or_unavailable_benchmarks_are_reported(discovery_run: dict[str, Any]) -> None:
    deltas = rows(output(discovery_run) / "third_expansion_benchmark_deltas.csv")
    assert deltas
    assert all(row["benchmark_available"] == "True" or row["unavailable_reason"] for row in deltas)


def test_promotion_candidate_file_exists_even_if_empty(discovery_run: dict[str, Any]) -> None:
    assert (output(discovery_run) / "third_expansion_promotion_candidates.csv").exists()


def test_rejection_reasons_exist_for_rejected_candidates(discovery_run: dict[str, Any]) -> None:
    text = (output(discovery_run) / "third_expansion_rejection_reasons.md").read_text(encoding="utf-8")
    rejected = [row["candidate_id"] for row in candidate_results(discovery_run) if row["outcome"] in {"discovery_reject", "benchmark_control_reject", "diagnostic_only"}]
    assert all(candidate_id in text for candidate_id in rejected)


def test_manifest_flags_match_strict_scope(discovery_run: dict[str, Any]) -> None:
    loaded = manifest(discovery_run)
    for key, value in discovery.MANIFEST_FLAGS.items():
        assert loaded[key] == value
    assert consistency(discovery_run)["consistency_passed"] is True
    assert discovery_run["registry_before"] == discovery_run["registry_after"]
