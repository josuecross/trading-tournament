from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
import yaml

import run_risk_controlled_high_return_discovery_batch as discovery


def write_price_cache(root: Path, symbol: str, periods: int = 720, drift: float = 0.00018) -> None:
    dates = pd.bdate_range("2021-01-01", periods=periods)
    seed = sum(ord(char) for char in symbol)
    prices = [50.0 + seed % 29]
    for idx in range(1, periods):
        wave = 0.0004 * np.sin(idx / (11 + seed % 7))
        shock = -0.012 if symbol in {"SPY", "QQQ", "XLK"} and 360 <= idx <= 372 else 0.0
        prices.append(max(5.0, prices[-1] * (1.0 + drift + wave + shock)))
    target = root / discovery.CACHE_DIR / f"{symbol}.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(
        {
            "date": dates,
            "open": [price * 0.999 for price in prices],
            "high": [price * 1.006 for price in prices],
            "low": [price * 0.994 for price in prices],
            "close": prices,
            "adj_close": prices,
            "volume": [1_000_000 + idx for idx in range(periods)],
            "symbol": symbol,
        }
    )
    frame.to_csv(target, index=False)


def write_cache(root: Path) -> None:
    for offset, symbol in enumerate(discovery.required_symbols()):
        drift = 0.00003 if symbol == "BIL" else 0.00010 + offset * 0.000004
        write_price_cache(root, symbol, drift=drift)


def registry_row(row_id: str, active_flag: bool = False, status: str = "discovery_reject") -> dict[str, Any]:
    return {
        "id": row_id,
        "strategy_id": row_id,
        "status": "active_observation" if active_flag else status,
        "current_status": "active_observation" if active_flag else status,
        "rules_frozen": active_flag,
        "frozen": active_flag,
        "paper_forward_active": active_flag,
        "candidate_exhaustive_run": False,
        "candidate_exhaustive_recommended": False,
        "promotion_review_required": False,
        "real_money_recommendation": False,
    }


def write_registry(root: Path) -> None:
    path = root / discovery.REGISTRY_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        registry_row(discovery.active.VM_ID, True),
        registry_row(discovery.active.DSR_ID, True),
        registry_row(discovery.active.SPY_200D_ID, True),
        registry_row("dual_momentum_paa_clean_v1", False),
        registry_row("donchian_atr_breakout_etf_v1", False),
    ]
    path.write_text(
        yaml.safe_dump(
            {
                "registry": {
                    "schema_version": 1,
                    "project": "trading_tournament",
                    "research_only": True,
                    "current_next_action": "run_risk_controlled_high_return_discovery_batch",
                    "real_money_recommendation": False,
                    "broker_integration": False,
                    "live_orders": False,
                },
                "strategies": rows,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    roadmap = root / discovery.ROADMAP_PATH
    roadmap.parent.mkdir(parents=True, exist_ok=True)
    roadmap.write_text("# Research Roadmap\n\nCurrent next action: `run_risk_controlled_high_return_discovery_batch`\n", encoding="utf-8")


def write_governance(root: Path) -> None:
    manual = root / discovery.MANUAL_REVIEW_DIR / "risk_controlled_manual_review_manifest.json"
    manual.parent.mkdir(parents=True, exist_ok=True)
    manual.write_text(
        json.dumps(
            {
                "decision": "approve_risk_controlled_high_return_discovery_batch_after_manual_review",
                "next_action": "run_risk_controlled_high_return_discovery_batch",
                "candidate_count_for_future_discovery": 2,
                "accepted_candidate_ids_for_future_discovery": discovery.AUTHORIZED_CANDIDATES,
                "prior_55_day_language_invalidated": True,
                "official_donchian_rule_uses_20_day_breakout": True,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    freeze = root / discovery.RULE_FREEZE_DIR / "risk_controlled_rule_freeze_manifest.json"
    freeze.parent.mkdir(parents=True, exist_ok=True)
    freeze.write_text(
        json.dumps(
            {
                "candidate_ids": discovery.AUTHORIZED_CANDIDATES,
                "candidate_count": 2,
                "candidate_membership_changed": False,
                "all_formulas_frozen": True,
                "dual_momentum_volatility_formula_frozen": True,
                "donchian_risk_budget_formula_frozen": True,
                "parent_rule_mismatch_found": True,
                "next_action": "manual_review_required_for_risk_controlled_high_return_batch",
            },
            indent=2,
        ),
        encoding="utf-8",
    )


@pytest.fixture(scope="module")
def discovery_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    root = tmp_path_factory.mktemp("risk_controlled_high_return_discovery")
    write_registry(root)
    write_governance(root)
    write_cache(root)
    before = yaml.safe_load((root / discovery.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result = discovery.run_risk_controlled_high_return_discovery_batch(root)
    after = yaml.safe_load((root / discovery.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result["root"] = root
    result["strategies_before"] = before
    result["strategies_after"] = after
    return result


def output(discovery_run: dict[str, Any]) -> Path:
    return Path(discovery_run["output_dir"])


def manifest(discovery_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(discovery_run) / "risk_controlled_discovery_manifest.json").read_text(encoding="utf-8"))


def consistency(discovery_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(discovery_run) / "risk_controlled_discovery_consistency_check.json").read_text(encoding="utf-8"))


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def candidate_results(discovery_run: dict[str, Any]) -> list[dict[str, str]]:
    return rows(output(discovery_run) / "risk_controlled_candidate_results.csv")


def test_exactly_two_candidates_are_evaluated(discovery_run: dict[str, Any]) -> None:
    assert manifest(discovery_run)["candidate_count"] == 2
    assert len(candidate_results(discovery_run)) == 2


def test_candidate_ids_match_approved_list(discovery_run: dict[str, Any]) -> None:
    assert manifest(discovery_run)["candidate_ids"] == discovery.AUTHORIZED_CANDIDATES
    assert [row["candidate_id"] for row in candidate_results(discovery_run)] == discovery.AUTHORIZED_CANDIDATES


def test_no_excluded_candidates_are_evaluated(discovery_run: dict[str, Any]) -> None:
    evaluated = {row["candidate_id"] for row in candidate_results(discovery_run)}
    assert evaluated.isdisjoint(discovery.EXCLUDED_CANDIDATES)


def test_invalidated_55_day_donchian_rule_is_not_used(discovery_run: dict[str, Any]) -> None:
    assert manifest(discovery_run)["invalidated_55_day_donchian_used"] is False
    assert consistency(discovery_run)["invalidated_55_day_donchian_rule_not_used"] is True


def test_official_donchian_rule_uses_20_day_breakout(discovery_run: dict[str, Any]) -> None:
    assert consistency(discovery_run)["official_donchian_rule_uses_20_day_breakout"] is True


def test_dual_momentum_volatility_scalar_is_frozen(discovery_run: dict[str, Any]) -> None:
    scalar_rows = rows(output(discovery_run) / "risk_controlled_dual_momentum_scalar_diagnostics.csv")
    assert scalar_rows
    assert discovery.floor_to_005(0.287) == pytest.approx(0.25)
    assert consistency(discovery_run)["dual_momentum_volatility_scalar_frozen"] is True


def test_donchian_risk_budget_sizing_is_frozen(discovery_run: dict[str, Any]) -> None:
    sizing_rows = rows(output(discovery_run) / "risk_controlled_donchian_sizing_diagnostics.csv")
    assert sizing_rows
    assert consistency(discovery_run)["donchian_risk_budget_sizing_frozen"] is True


def test_provider_download_is_false(discovery_run: dict[str, Any]) -> None:
    assert manifest(discovery_run)["provider_download"] is False


def test_intraday_data_is_not_used(discovery_run: dict[str, Any]) -> None:
    assert manifest(discovery_run)["intraday_data_used"] is False


def test_no_candidate_exhaustive(discovery_run: dict[str, Any]) -> None:
    assert manifest(discovery_run)["candidate_exhaustive_run"] is False
    assert all(row["outcome"] not in discovery.FORBIDDEN_OUTCOMES for row in candidate_results(discovery_run))


def test_no_paper_forward_action(discovery_run: dict[str, Any]) -> None:
    loaded = manifest(discovery_run)
    assert loaded["paper_forward_review"] is False
    assert loaded["paper_forward_activation"] is False


def test_no_broker_live_path(discovery_run: dict[str, Any]) -> None:
    loaded = manifest(discovery_run)
    assert loaded["broker_path_touched"] is False
    assert loaded["live_orders"] is False


def test_exact_rejected_variants_remain_closed(discovery_run: dict[str, Any]) -> None:
    assert manifest(discovery_run)["exact_rejected_variants_reopened"] is False
    assert discovery_run["strategies_before"] == discovery_run["strategies_after"]


def test_intraday_remains_paused(discovery_run: dict[str, Any]) -> None:
    assert manifest(discovery_run)["intraday_research_remains_paused"] is True


def test_risk_gate_results_exist(discovery_run: dict[str, Any]) -> None:
    gate_rows = rows(output(discovery_run) / "risk_controlled_risk_gate_results.csv")
    assert {row["candidate_id"] for row in gate_rows} == set(discovery.AUTHORIZED_CANDIDATES)


def test_slippage_stress_results_exist(discovery_run: dict[str, Any]) -> None:
    stress_rows = rows(output(discovery_run) / "risk_controlled_slippage_stress_results.csv")
    assert {row["candidate_id"] for row in stress_rows} == set(discovery.AUTHORIZED_CANDIDATES)


def test_benchmark_deltas_exist_or_unavailable_reported(discovery_run: dict[str, Any]) -> None:
    delta_rows = rows(output(discovery_run) / "risk_controlled_benchmark_deltas.csv")
    assert delta_rows
    unavailable = [row for row in delta_rows if row["available"] == "False"]
    assert any("parent_reference" in row["benchmark_id"] for row in unavailable)
    assert all(row["unavailable_reason"] for row in unavailable)


def test_dual_momentum_scalar_diagnostics_exist(discovery_run: dict[str, Any]) -> None:
    assert (output(discovery_run) / "risk_controlled_dual_momentum_scalar_diagnostics.csv").exists()
    assert rows(output(discovery_run) / "risk_controlled_dual_momentum_scalar_diagnostics.csv")


def test_donchian_sizing_diagnostics_exist(discovery_run: dict[str, Any]) -> None:
    assert (output(discovery_run) / "risk_controlled_donchian_sizing_diagnostics.csv").exists()
    assert rows(output(discovery_run) / "risk_controlled_donchian_sizing_diagnostics.csv")


def test_parent_comparison_exists_or_unavailability_reported(discovery_run: dict[str, Any]) -> None:
    parent_rows = rows(output(discovery_run) / "risk_controlled_parent_comparison.csv")
    assert {row["candidate_id"] for row in parent_rows} == set(discovery.AUTHORIZED_CANDIDATES)
    assert all(row["parent_rerun"] == "False" for row in parent_rows)
    assert all(row["comparison_status"] == "unavailable_parent_closed" for row in parent_rows)


def test_promotion_candidate_file_exists_even_if_empty(discovery_run: dict[str, Any]) -> None:
    assert (output(discovery_run) / "risk_controlled_promotion_candidates.csv").exists()


def test_rejection_reasons_exist_if_rejected(discovery_run: dict[str, Any]) -> None:
    rejected = manifest(discovery_run)["rejected_candidate_ids"]
    if rejected:
        text = (output(discovery_run) / "risk_controlled_rejection_reasons.md").read_text(encoding="utf-8")
        assert all(candidate_id in text for candidate_id in rejected)


def test_manifest_flags_match_strict_scope(discovery_run: dict[str, Any]) -> None:
    loaded = manifest(discovery_run)
    for key, value in discovery.MANIFEST_FLAGS.items():
        assert loaded[key] == value
    assert consistency(discovery_run)["consistency_passed"] is True
