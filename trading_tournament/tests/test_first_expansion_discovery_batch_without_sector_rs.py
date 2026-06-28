from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

import run_active_strategy_evidence_recompute as active
import run_first_expansion_discovery_batch_without_sector_rs as discovery
import run_first_expansion_discovery_preregistration as prereg
import run_first_expansion_manual_data_period_review as period_review


def write_price_cache(root: Path, symbol: str, periods: int = 720, drift: float = 0.0002) -> None:
    dates = pd.bdate_range("2019-01-01", periods=periods)
    base = 40.0 + (sum(ord(ch) for ch in symbol) % 30)
    wave = np.sin(np.arange(periods) / 11.0) * 0.004
    shocks = np.where(np.arange(periods) % 53 == 0, -0.025, 0.0)
    returns = drift + wave + shocks
    prices = [base]
    for value in returns[1:]:
        prices.append(max(5.0, prices[-1] * (1.0 + float(value))))
    frame = pd.DataFrame(
        {
            "date": dates,
            "open": np.array(prices) * 1.0005,
            "high": np.array(prices) * 1.01,
            "low": np.array(prices) * 0.99,
            "close": prices,
            "adj_close": prices,
            "volume": 1_000_000 + np.arange(periods),
            "symbol": symbol,
        }
    )
    path = root / "data" / "cache" / f"{symbol}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def write_caches(root: Path) -> None:
    for idx, symbol in enumerate(discovery.ALL_AUTHORIZED_SYMBOLS):
        drift = 0.00003 + idx * 0.000002
        if symbol == "BIL":
            drift = 0.00001
        write_price_cache(root, symbol, drift=drift)


def candidate(candidate_id: str, universe: list[str], benchmarks: list[str]) -> dict[str, object]:
    return {
        "candidate_id": candidate_id,
        "family": "test",
        "timeframe": "daily",
        "universe": universe,
        "entry_rule": "frozen synthetic",
        "exit_rule": "frozen synthetic",
        "sizing_rule": "frozen synthetic",
        "benchmark_controls": benchmarks,
        "risk_controls": ["frozen synthetic"],
    }


def write_preregistration(root: Path) -> None:
    path = root / prereg.OUTPUT_DIR / "first_expansion_discovery_batch.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "metadata": {
            "lane_id": "first_expansion_discovery_batch",
            "included_candidate_ids": [
                *discovery.AUTHORIZED_CANDIDATE_IDS[:2],
                "sector_rs_weekly_cash_filter_v1",
                *discovery.AUTHORIZED_CANDIDATE_IDS[2:],
            ],
        },
        "candidates": [
            candidate("dmr_liquid_etf_oversold_rebound_v1", discovery.BROAD_UNIVERSE, ["SPY_200d", "SPY"]),
            candidate("vm_spy_qqq_daily_vol_target_v1", discovery.VM_UNIVERSE, ["SPY_200d", "QQQ"]),
            candidate("sector_rs_weekly_cash_filter_v1", ["XLK", "XLF", "XLRE", "BIL"], ["active DSR"]),
            candidate("vol_compression_breakout_etf_v1", discovery.BROAD_UNIVERSE, ["SPY", "QQQ"]),
            candidate("rs_pair_rotation_spy_qqq_xlk_xlu_v1", discovery.RS_PAIR_UNIVERSE, ["SPY_200d", "QQQ", "XLK", "XLU"]),
        ],
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def write_manual_review(root: Path) -> None:
    path = root / period_review.OUTPUT_DIR / "first_expansion_manual_period_review_manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "selected_resolution": "run_first_expansion_discovery_batch_without_sector_rs",
                "deferred_limited_history_candidate_ids": ["sector_rs_weekly_cash_filter_v1"],
                "period_compatible_candidate_ids": discovery.AUTHORIZED_CANDIDATE_IDS,
                "provider_download": False,
            }
        ),
        encoding="utf-8",
    )


def write_registry_and_roadmap(root: Path) -> None:
    registry = root / discovery.EXPANSION_REGISTRY_PATH
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry.write_text(
        yaml.safe_dump(
            {
                "metadata": {
                    "artifact": "strategy_expansion_candidates_v1",
                    "provider_download": False,
                    "candidate_exhaustive_run": False,
                    "paper_forward_activation": False,
                    "real_money_recommendation": False,
                },
                "candidates": [],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    roadmap = root / discovery.EXPANSION_ROADMAP_PATH
    roadmap.parent.mkdir(parents=True, exist_ok=True)
    roadmap.write_text("# Strategy Expansion Roadmap\n", encoding="utf-8")
    for strategy_id, path in active.active_observation_paths(root).items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump({"strategy_id": strategy_id, "paper_forward_active": True}), encoding="utf-8")


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def synthetic_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    root = tmp_path_factory.mktemp("first_expansion_no_sector")
    write_preregistration(root)
    write_manual_review(root)
    write_registry_and_roadmap(root)
    write_caches(root)
    before = {sid: file_hash(path) for sid, path in active.active_observation_paths(root).items()}
    result = discovery.run_first_expansion_discovery_batch_without_sector_rs(root)
    after = {sid: file_hash(path) for sid, path in active.active_observation_paths(root).items()}
    return {"root": root, "result": result, "before": before, "after": after}


def output_path(synthetic_run: dict[str, object]) -> Path:
    return Path(synthetic_run["result"]["output_dir"])


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def manifest(synthetic_run: dict[str, object]) -> dict[str, object]:
    return json.loads((output_path(synthetic_run) / "first_expansion_discovery_manifest.json").read_text(encoding="utf-8"))


def test_exactly_four_candidates_are_evaluated(synthetic_run: dict[str, object]) -> None:
    assert manifest(synthetic_run)["candidates_evaluated"] == discovery.AUTHORIZED_CANDIDATE_IDS
    assert manifest(synthetic_run)["candidates_evaluated_count"] == 4


def test_sector_rs_is_not_evaluated(synthetic_run: dict[str, object]) -> None:
    assert "sector_rs_weekly_cash_filter_v1" not in manifest(synthetic_run)["candidates_evaluated"]
    assert manifest(synthetic_run)["sector_rs_deferred"] is True


def test_no_excluded_candidates_are_evaluated(synthetic_run: dict[str, object]) -> None:
    evaluated = set(manifest(synthetic_run)["candidates_evaluated"])
    assert not evaluated.intersection(discovery.EXCLUDED_CANDIDATE_IDS)


def test_intraday_and_event_candidates_are_not_included(synthetic_run: dict[str, object]) -> None:
    loaded = manifest(synthetic_run)
    assert loaded["intraday_candidates_included"] is False
    assert loaded["event_data_candidates_included"] is False


def test_frozen_candidate_rules_are_not_changed(synthetic_run: dict[str, object]) -> None:
    consistency = json.loads((output_path(synthetic_run) / "first_expansion_discovery_consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["frozen_rules_changed"] is False


def test_candidate_universes_are_not_changed(synthetic_run: dict[str, object]) -> None:
    consistency = json.loads((output_path(synthetic_run) / "first_expansion_discovery_consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["candidate_universe_changed"] is False


def test_benchmarks_are_not_changed(synthetic_run: dict[str, object]) -> None:
    consistency = json.loads((output_path(synthetic_run) / "first_expansion_discovery_consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["benchmarks_changed"] is False


def test_no_provider_download_occurs(synthetic_run: dict[str, object]) -> None:
    assert manifest(synthetic_run)["provider_download"] is False


def test_discovery_and_backtests_run_only_for_authorized_four(synthetic_run: dict[str, object]) -> None:
    loaded = manifest(synthetic_run)
    assert loaded["discovery_run"] is True
    assert loaded["backtests_run"] is True
    rows = read_csv(output_path(synthetic_run) / "first_expansion_candidate_results.csv")
    assert [row["candidate_id"] for row in rows] == discovery.AUTHORIZED_CANDIDATE_IDS


def test_candidate_outcomes_are_limited(synthetic_run: dict[str, object]) -> None:
    rows = read_csv(output_path(synthetic_run) / "first_expansion_candidate_results.csv")
    assert {row["discovery_outcome"] for row in rows}.issubset(discovery.VALID_OUTCOMES)


def test_no_candidate_goes_to_candidate_exhaustive(synthetic_run: dict[str, object]) -> None:
    rows = read_csv(output_path(synthetic_run) / "first_expansion_candidate_results.csv")
    assert all(row["candidate_exhaustive_recommended"] == "False" for row in rows)
    assert manifest(synthetic_run)["candidate_exhaustive_run"] is False


def test_no_candidate_goes_to_paper_forward(synthetic_run: dict[str, object]) -> None:
    rows = read_csv(output_path(synthetic_run) / "first_expansion_candidate_results.csv")
    assert all(row["paper_forward_active"] == "False" for row in rows)
    assert manifest(synthetic_run)["paper_forward_activation"] is False


def test_no_broker_or_live_path_is_touched(synthetic_run: dict[str, object]) -> None:
    loaded = manifest(synthetic_run)
    assert loaded["broker_path_touched"] is False
    assert loaded["live_orders"] is False


def test_mixed_inception_diagnostics_exist_for_xlre_candidates(synthetic_run: dict[str, object]) -> None:
    text = (output_path(synthetic_run) / "first_expansion_mixed_inception_diagnostics.md").read_text(encoding="utf-8")
    assert "dmr_liquid_etf_oversold_rebound_v1" in text
    assert "vol_compression_breakout_etf_v1" in text
    assert "XLRE" in text


def test_risk_gate_results_exist_for_every_candidate(synthetic_run: dict[str, object]) -> None:
    rows = read_csv(output_path(synthetic_run) / "first_expansion_risk_gate_results.csv")
    assert {row["candidate_id"] for row in rows} == set(discovery.AUTHORIZED_CANDIDATE_IDS)


def test_benchmark_deltas_exist_or_are_explicitly_unavailable(synthetic_run: dict[str, object]) -> None:
    rows = read_csv(output_path(synthetic_run) / "first_expansion_benchmark_deltas.csv")
    assert rows
    assert {row["comparison_status"] for row in rows}.issubset({"computed", "unavailable"})


def test_promotion_candidate_file_exists_even_if_empty(synthetic_run: dict[str, object]) -> None:
    path = output_path(synthetic_run) / "first_expansion_promotion_candidates.csv"
    assert path.exists()
    assert "candidate_id" in path.read_text(encoding="utf-8").splitlines()[0]


def test_rejection_reasons_exist_for_rejected_candidates(synthetic_run: dict[str, object]) -> None:
    text = (output_path(synthetic_run) / "first_expansion_rejection_reasons.md").read_text(encoding="utf-8")
    rejected = manifest(synthetic_run)["rejected_candidate_ids"]
    for candidate_id in rejected:
        assert candidate_id in text


def test_manifest_flags_match_strict_scope(synthetic_run: dict[str, object]) -> None:
    loaded = manifest(synthetic_run)
    for key in [
        "provider_download",
        "candidate_exhaustive_run",
        "paper_forward_review",
        "paper_forward_activation",
        "broker_path_touched",
        "live_orders",
        "real_money_recommendation",
        "frozen_rules_changed",
        "candidate_universe_changed",
        "benchmarks_changed",
        "active_strategy_state_changed",
        "etf_wrapper_track_reopened",
    ]:
        assert loaded[key] is False
    assert loaded["next_action"] in {
        "promotion_review_for_selected_first_expansion_rows",
        "pre_register_sector_rs_limited_history_batch",
        "pre_register_second_expansion_discovery_batch",
    }


def test_active_observations_are_unchanged(synthetic_run: dict[str, object]) -> None:
    assert synthetic_run["before"] == synthetic_run["after"]


def test_consistency_check_passes(synthetic_run: dict[str, object]) -> None:
    consistency = json.loads((output_path(synthetic_run) / "first_expansion_discovery_consistency_check.json").read_text(encoding="utf-8"))
    assert consistency["consistency_passed"] is True
