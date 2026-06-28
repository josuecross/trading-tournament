from __future__ import annotations

import csv
import json
import math
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml

import run_active_strategy_evidence_recompute as active
import run_first_expansion_discovery_preregistration as first_prereg
import run_sector_rs_limited_history_discovery_batch as discovery
import run_sector_rs_limited_history_preregistration as prereg


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def synthetic_price(symbol: str, offset: int) -> float:
    seed = sum(ord(char) for char in symbol)
    drift = 0.035 + (seed % 11) * 0.003
    wave = math.sin(offset / (17 + seed % 7)) * (0.8 + (seed % 5) * 0.1)
    drawdown = -5.0 if symbol in {"XLK", "XLY", "SPY", "QQQ"} and 420 <= offset <= 460 else 0.0
    return max(10.0, 70.0 + (seed % 29) + offset * drift + wave + drawdown)


def write_cache(path: Path, symbol: str, start_days_ago: int = 920) -> None:
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
                "volume": 300000 + offset,
                "symbol": symbol,
            }
        )
    write_csv(path, rows, ["date", "open", "high", "low", "close", "adj_close", "volume", "symbol"])


def write_prereg_context(root: Path) -> None:
    first_batch = root / first_prereg.OUTPUT_DIR / "first_expansion_discovery_batch.yaml"
    first_batch.parent.mkdir(parents=True, exist_ok=True)
    first_batch.write_text(
        yaml.safe_dump(
            {
                "metadata": {"included_candidate_ids": [prereg.CANDIDATE_ID]},
                "candidates": [
                    {
                        "candidate_id": prereg.CANDIDATE_ID,
                        "family": "sector_relative_strength_rotation",
                        "timeframe": "weekly",
                        "universe": prereg.SECTOR_UNIVERSE,
                        "entry_rule": "At weekly rebalance, rank sectors by fixed 13-week momentum using prior completed data only.",
                        "exit_rule": "At weekly rebalance, exit failed sectors.",
                        "sizing_rule": "Allocate 50% to each accepted sector.",
                        "risk_controls": ["Max 2 sectors.", "Weekly rebalance only."],
                        "benchmark_controls": ["active DSR", "active combo", "SPY_200d"],
                        "acceptance_criteria": ["future discovery only"],
                        "rejection_criteria": ["weak evidence"],
                        "duplication_checks": ["active DSR", "active combo"],
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    write_csv(
        root / prereg.MANUAL_PERIOD_REVIEW_DIR / "first_expansion_candidate_period_compatibility.csv",
        [
            {
                "candidate_id": prereg.CANDIDATE_ID,
                "required_symbols": ";".join(prereg.SECTOR_UNIVERSE),
                "earliest_required_symbol_start_date": "2007-01-03",
                "effective_all_symbols_start_date": "2015-10-08",
                "common_last_date": "2026-06-18",
                "common_history_years": "10.69",
                "full_2007_style_period_supported": "False",
                "blocked_by_xlre": "True",
                "xlre_in_universe": "True",
                "cache_missing": "False",
                "issue_classification": "period_inception_limitation",
                "can_proceed_without_changing_frozen_rules": "False",
                "requires_separate_limited_history_batch": "True",
                "comparability_vs_active_vm_affected": "True",
                "comparability_vs_active_dsr_affected": "True",
                "comparability_vs_active_combo_affected": "True",
                "comparability_vs_spy_200d_affected": "True",
                "recommended_handling": "defer_to_limited_history_preregistration",
            }
        ],
        [
            "candidate_id",
            "required_symbols",
            "earliest_required_symbol_start_date",
            "effective_all_symbols_start_date",
            "common_last_date",
            "common_history_years",
            "full_2007_style_period_supported",
            "blocked_by_xlre",
            "xlre_in_universe",
            "cache_missing",
            "issue_classification",
            "can_proceed_without_changing_frozen_rules",
            "requires_separate_limited_history_batch",
            "comparability_vs_active_vm_affected",
            "comparability_vs_active_dsr_affected",
            "comparability_vs_active_combo_affected",
            "comparability_vs_spy_200d_affected",
            "recommended_handling",
        ],
    )
    write_csv(
        root / prereg.FIRST_EXPANSION_DISCOVERY_DIR / "first_expansion_candidate_results.csv",
        [{"candidate_id": candidate_id, "discovery_outcome": "discovery_reject"} for candidate_id in prereg.FIRST_EXPANSION_REJECT_IDS],
        ["candidate_id", "discovery_outcome"],
    )
    expansion_registry = root / prereg.EXPANSION_REGISTRY_PATH
    expansion_registry.parent.mkdir(parents=True, exist_ok=True)
    expansion_registry.write_text(
        yaml.safe_dump(
            {
                "metadata": {
                    "artifact": "strategy_expansion_candidates_v1",
                    "etf_wrapper_track_status": "archived_after_breadth_state_regime_no_candidate",
                    "provider_download": False,
                },
                "candidates": [],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    expansion_roadmap = root / prereg.EXPANSION_ROADMAP_PATH
    expansion_roadmap.parent.mkdir(parents=True, exist_ok=True)
    expansion_roadmap.write_text("# Strategy Expansion Roadmap\n", encoding="utf-8")


def write_discovery_context(root: Path) -> None:
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
                    "current_next_action": "run_sector_rs_limited_history_discovery_batch",
                },
                "strategies": [
                    {
                        "id": active.VM_ID,
                        "strategy_id": active.VM_ID,
                        "status": "active_observation",
                        "paper_forward_active": True,
                        "candidate_exhaustive_run": False,
                    },
                    {
                        "id": active.DSR_ID,
                        "strategy_id": active.DSR_ID,
                        "status": "active_observation",
                        "paper_forward_active": True,
                        "candidate_exhaustive_run": False,
                    },
                    {
                        "id": active.SPY_200D_ID,
                        "strategy_id": active.SPY_200D_ID,
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
    research_roadmap = root / discovery.RESEARCH_ROADMAP_PATH
    research_roadmap.parent.mkdir(parents=True, exist_ok=True)
    research_roadmap.write_text("# Research Roadmap\n\nCurrent next action: `run_sector_rs_limited_history_discovery_batch`\n", encoding="utf-8")
    second_manifest = root / discovery.SECOND_EXPANSION_DIR / "second_expansion_discovery_manifest.json"
    second_manifest.parent.mkdir(parents=True, exist_ok=True)
    second_manifest.write_text(
        json.dumps(
            {
                "promotion_candidates_count": 0,
                "promotion_candidate_ids": [],
                "macro_limited_history_candidate_ids": [],
                "watchlist_candidate_ids": [],
                "rejected_candidate_ids": discovery.SECOND_EXPANSION_REJECT_IDS[:-1],
                "diagnostic_reject_ids": [discovery.SECOND_EXPANSION_REJECT_IDS[-1]],
                "next_action": "run_sector_rs_limited_history_discovery_batch",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    for symbol in discovery.LOAD_SYMBOLS:
        write_cache(root / discovery.CACHE_DIR / f"{symbol}.csv", symbol)


@pytest.fixture(scope="module")
def discovery_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    root = tmp_path_factory.mktemp("sector_rs_discovery")
    write_prereg_context(root)
    write_discovery_context(root)
    prereg.run_sector_rs_limited_history_preregistration(root)
    batch_before = (root / discovery.PREREG_DIR / "sector_rs_limited_history_batch.yaml").read_text(encoding="utf-8")
    registry_before = yaml.safe_load((root / discovery.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result = discovery.run_sector_rs_limited_history_discovery_batch(root)
    batch_after = (root / discovery.PREREG_DIR / "sector_rs_limited_history_batch.yaml").read_text(encoding="utf-8")
    registry_after = yaml.safe_load((root / discovery.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result["root"] = str(root)
    result["batch_before"] = batch_before
    result["batch_after"] = batch_after
    result["registry_before"] = registry_before
    result["registry_after"] = registry_after
    return result


def output(discovery_run: dict[str, Any]) -> Path:
    return Path(discovery_run["output_dir"])


def manifest(discovery_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(discovery_run) / "sector_rs_limited_history_discovery_manifest.json").read_text(encoding="utf-8"))


def consistency(discovery_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(discovery_run) / "sector_rs_limited_history_discovery_consistency_check.json").read_text(encoding="utf-8"))


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_exactly_one_candidate_is_evaluated(discovery_run: dict[str, Any]) -> None:
    assert manifest(discovery_run)["candidate_count"] == 1
    assert manifest(discovery_run)["evaluated_candidate_ids"] == [discovery.CANDIDATE_ID]


def test_candidate_is_exactly_sector_rs(discovery_run: dict[str, Any]) -> None:
    assert manifest(discovery_run)["candidate_id"] == "sector_rs_weekly_cash_filter_v1"


def test_no_other_expansion_candidates_are_evaluated(discovery_run: dict[str, Any]) -> None:
    assert set(manifest(discovery_run)["evaluated_candidate_ids"]).isdisjoint(discovery.EXCLUDED_IDS)
    candidate_rows = rows(output(discovery_run) / "sector_rs_limited_history_candidate_results.csv")
    assert [row["candidate_id"] for row in candidate_rows] == [discovery.CANDIDATE_ID]


def test_second_expansion_rejected_rows_remain_rejected(discovery_run: dict[str, Any]) -> None:
    assert manifest(discovery_run)["second_expansion_rejects_remain_rejected"] is True


def test_no_intraday_candidate_is_included(discovery_run: dict[str, Any]) -> None:
    assert manifest(discovery_run)["intraday_candidates_included"] is False


def test_no_event_data_candidate_is_included(discovery_run: dict[str, Any]) -> None:
    assert manifest(discovery_run)["event_data_candidates_included"] is False


def test_frozen_rules_are_not_changed(discovery_run: dict[str, Any]) -> None:
    assert discovery_run["batch_before"] == discovery_run["batch_after"]
    assert manifest(discovery_run)["frozen_rules_changed"] is False


def test_universe_is_not_changed(discovery_run: dict[str, Any]) -> None:
    assert manifest(discovery_run)["candidate_universe"] == discovery.UNIVERSE
    assert manifest(discovery_run)["candidate_universe_changed"] is False


def test_xlre_remains_in_universe(discovery_run: dict[str, Any]) -> None:
    assert "XLRE" in manifest(discovery_run)["candidate_universe"]


def test_limited_history_label_is_present(discovery_run: dict[str, Any]) -> None:
    loaded = manifest(discovery_run)
    assert loaded["limited_history_due_to_xlre_inception"] is True
    assert loaded["limited_history_label"] == discovery.LIMITED_HISTORY_LABEL


def test_methodology_is_common_start_after_xlre_warmup(discovery_run: dict[str, Any]) -> None:
    assert manifest(discovery_run)["methodology"] == "common_start_2016_after_xlre_sma_warmup"


def test_same_window_benchmark_recompute_is_required_and_used(discovery_run: dict[str, Any]) -> None:
    loaded = manifest(discovery_run)
    assert loaded["same_window_benchmark_recompute_used"] is True
    assert rows(output(discovery_run) / "sector_rs_limited_history_same_window_benchmarks.csv")


def test_full_history_benchmarks_are_not_used(discovery_run: dict[str, Any]) -> None:
    assert manifest(discovery_run)["not_2007_style_full_history_test"] is True


def test_provider_download_is_false(discovery_run: dict[str, Any]) -> None:
    assert manifest(discovery_run)["provider_download"] is False


def test_candidate_outcomes_are_limited(discovery_run: dict[str, Any]) -> None:
    assert manifest(discovery_run)["discovery_outcome"] in discovery.VALID_OUTCOMES


def test_candidate_cannot_go_to_candidate_exhaustive(discovery_run: dict[str, Any]) -> None:
    loaded = manifest(discovery_run)
    assert loaded["candidate_exhaustive_run"] is False
    assert loaded["discovery_outcome"] != "candidate_exhaustive"


def test_candidate_cannot_go_to_paper_forward(discovery_run: dict[str, Any]) -> None:
    loaded = manifest(discovery_run)
    assert loaded["paper_forward_review"] is False
    assert loaded["paper_forward_activation"] is False
    assert "paper_forward" not in loaded["discovery_outcome"]


def test_no_broker_or_live_path_is_touched(discovery_run: dict[str, Any]) -> None:
    loaded = manifest(discovery_run)
    assert loaded["broker_path_touched"] is False
    assert loaded["live_orders"] is False


def test_risk_gate_results_exist(discovery_run: dict[str, Any]) -> None:
    assert rows(output(discovery_run) / "sector_rs_limited_history_risk_gate_results.csv")


def test_slippage_stress_results_exist(discovery_run: dict[str, Any]) -> None:
    assert rows(output(discovery_run) / "sector_rs_limited_history_slippage_stress_results.csv")


def test_benchmark_deltas_exist(discovery_run: dict[str, Any]) -> None:
    delta_rows = rows(output(discovery_run) / "sector_rs_limited_history_benchmark_deltas.csv")
    assert delta_rows
    assert {row["benchmark_id"] for row in delta_rows} >= {active.DSR_ID, discovery.combo.COMBO_ID, active.VM_ID, active.SPY_200D_ID}


def test_sector_concentration_diagnostics_exist(discovery_run: dict[str, Any]) -> None:
    concentration = rows(output(discovery_run) / "sector_rs_limited_history_sector_concentration.csv")
    assert {row["symbol"] for row in concentration} >= set(discovery.UNIVERSE)


def test_bil_allocation_diagnostics_exist(discovery_run: dict[str, Any]) -> None:
    bil_rows = rows(output(discovery_run) / "sector_rs_limited_history_bil_allocation_diagnostics.csv")
    assert bil_rows[0]["candidate_id"] == discovery.CANDIDATE_ID


def test_promotion_candidate_file_exists_even_if_empty(discovery_run: dict[str, Any]) -> None:
    assert (output(discovery_run) / "sector_rs_limited_history_promotion_candidates.csv").exists()


def test_rejection_reasons_exist_if_rejected(discovery_run: dict[str, Any]) -> None:
    if manifest(discovery_run)["discovery_outcome"] == "discovery_reject":
        text = (output(discovery_run) / "sector_rs_limited_history_rejection_reasons.md").read_text(encoding="utf-8")
        assert discovery.CANDIDATE_ID in text


def test_manifest_flags_match_strict_scope(discovery_run: dict[str, Any]) -> None:
    loaded = manifest(discovery_run)
    for key, value in discovery.MANIFEST_FLAGS.items():
        assert loaded[key] == value
    assert consistency(discovery_run)["consistency_passed"] is True
    assert discovery_run["registry_before"] == discovery_run["registry_after"]
