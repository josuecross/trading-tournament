from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

import pytest
import yaml

from strategy_lab.research_os.exploratory_sandbox import sandbox_config as config
from strategy_lab.research_os.exploratory_sandbox.sandbox_batch import (
    MANIFEST_FLAGS,
    VALID_BATCH_NEXT_ACTIONS,
    run_sandbox_batch,
)
from strategy_lab.research_os.exploratory_sandbox.sandbox_evidence import run_sandbox_implementation
from strategy_lab.research_os.exploratory_sandbox.sandbox_status_taxonomy import ALLOWED_SANDBOX_STATUSES, FORBIDDEN_STATUSES
from strategy_lab.research_os.exploratory_sandbox.sandbox_universes import UNIVERSE_GROUPS


def write_cache(path: Path, symbol: str, offset: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = ["date,open,high,low,close,adj_close,volume,symbol"]
    price = 100.0 + offset
    for idx in range(320):
        price *= 1.0 + 0.0004 + (0.0001 * math.sin(idx / 9.0 + offset))
        date = f"2020-01-{(idx % 28) + 1:02d}" if idx < 28 else f"2020-{((idx // 28) % 12) + 1:02d}-{(idx % 28) + 1:02d}"
        rows.append(f"{date},{price},{price * 1.01},{price * 0.99},{price},{price},1000,{symbol}")
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def write_fixture(root: Path) -> None:
    all_symbols = sorted({symbol for group in UNIVERSE_GROUPS.values() for symbol in group.symbols} | {"SPLV", "USMV", "QUAL", "IEF"})
    registry = {
        "registry": {
            "schema_version": 1,
            "project": "trading_tournament",
            "research_only": True,
            "real_money_recommendation": False,
            "broker_integration": False,
            "live_orders": False,
            "current_research_mode": "exploratory_strategy_search_sandbox_implemented",
            "current_next_action": "run_exploratory_strategy_search_sandbox_batch",
            "official_current_next_action": "run_exploratory_strategy_search_sandbox_batch",
            "next_action": "run_exploratory_strategy_search_sandbox_batch",
            "intraday_research_remains_paused": True,
            "static_all_weather_benchmark_control_status": "benchmark_control_accepted",
        },
        "strategies": [
            {
                "id": "paper_forward_vm_quality_lowvol_proxy_v1",
                "status": "active_paper_demo_observation",
                "paper_forward_active": True,
                "rules_frozen": True,
            },
            {
                "id": "paper_forward_dsr_sector_equal_weight_defensive_filter_v1",
                "status": "active_paper_demo_observation",
                "paper_forward_active": True,
                "rules_frozen": True,
            },
            {
                "id": "mfv_equal_weight_trend_filter_v1",
                "status": "discovery_reject",
                "paper_forward_active": False,
                "candidate_exhaustive_run": False,
            },
        ],
    }
    registry_path = root / config.REGISTRY_PATH
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")

    roadmap_path = root / config.ROADMAP_PATH
    roadmap_path.parent.mkdir(parents=True, exist_ok=True)
    roadmap_path.write_text(
        "# Research Roadmap\n\n## Compact Current State\n\n- Official current next action: `run_exploratory_strategy_search_sandbox_batch`\n",
        encoding="utf-8",
    )
    compact = root / "reports" / "compact_state" / "current_tournament_state.md"
    compact.parent.mkdir(parents=True, exist_ok=True)
    compact.write_text("Current next action: `run_exploratory_strategy_search_sandbox_batch`\n", encoding="utf-8")

    approved = {
        "schema_version": 1,
        "symbols": [
            {
                "symbol": symbol,
                "allowed_for_strategy": True,
                "allowed_for_benchmark": True,
            }
            for symbol in all_symbols
        ],
    }
    approved_path = root / config.APPROVED_SYMBOL_MAP_PATH
    approved_path.parent.mkdir(parents=True, exist_ok=True)
    approved_path.write_text(yaml.safe_dump(approved, sort_keys=False), encoding="utf-8")
    for idx, symbol in enumerate(all_symbols):
        write_cache(root / config.DATA_CACHE_DIR / f"{symbol}.csv", symbol, float(idx))

    combo_dir = root / "evidence" / "active_combo_benchmark" / "latest"
    combo_dir.mkdir(parents=True, exist_ok=True)
    combo_rows = [
        "date,active_combo_equity,vm_sleeve_equity,dsr_sleeve_equity,vm_standalone_equity,dsr_standalone_equity,active_combo_daily_return,vm_sleeve_daily_return,dsr_sleeve_daily_return"
    ]
    combo = 3000.0
    vm = 3000.0
    dsr = 3000.0
    for idx in range(320):
        date = f"2020-01-{(idx % 28) + 1:02d}" if idx < 28 else f"2020-{((idx // 28) % 12) + 1:02d}-{(idx % 28) + 1:02d}"
        vm *= 1.00035
        dsr *= 1.00025
        combo = 0.5 * vm + 0.5 * dsr
        combo_rows.append(f"{date},{combo},{combo / 2},{combo / 2},{vm},{dsr},0.0003,0.00035,0.00025")
    (combo_dir / "active_combo_equity_series.csv").write_text("\n".join(combo_rows) + "\n", encoding="utf-8")


@pytest.fixture(scope="module")
def sandbox_batch_run(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    root = tmp_path_factory.mktemp("exploratory_sandbox_batch")
    write_fixture(root)
    run_sandbox_implementation(root, max_variants=200, update_metadata=True)
    before = yaml.safe_load((root / config.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result = run_sandbox_batch(root, batch_id="batch_001", max_variants=200, update_registry=True)
    after = yaml.safe_load((root / config.REGISTRY_PATH).read_text(encoding="utf-8"))["strategies"]
    result["root"] = root
    result["strategies_before"] = before
    result["strategies_after"] = after
    return result


def output(sandbox_batch_run: dict[str, Any]) -> Path:
    return Path(sandbox_batch_run["output_dir"])


def manifest(sandbox_batch_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(sandbox_batch_run) / "sandbox_batch_manifest.json").read_text(encoding="utf-8"))


def consistency(sandbox_batch_run: dict[str, Any]) -> dict[str, Any]:
    return json.loads((output(sandbox_batch_run) / "sandbox_batch_consistency_check.json").read_text(encoding="utf-8"))


def result_rows(sandbox_batch_run: dict[str, Any]) -> list[dict[str, str]]:
    with (output(sandbox_batch_run) / "sandbox_variant_results.csv").open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_sandbox_batch_run_mode(sandbox_batch_run: dict[str, Any]) -> None:
    assert manifest(sandbox_batch_run)["sandbox_batch_run"] is True


def test_results_are_non_promotable(sandbox_batch_run: dict[str, Any]) -> None:
    assert manifest(sandbox_batch_run)["sandbox_results_non_promotable"] is True


def test_sandbox_cannot_create_paper_candidates(sandbox_batch_run: dict[str, Any]) -> None:
    assert manifest(sandbox_batch_run)["sandbox_can_create_paper_candidates"] is False


def test_no_formal_strategy_discovery(sandbox_batch_run: dict[str, Any]) -> None:
    loaded = manifest(sandbox_batch_run)
    assert loaded["strategy_discovery_run"] is False
    assert loaded["formal_discovery_run"] is False


def test_no_candidate_exhaustive(sandbox_batch_run: dict[str, Any]) -> None:
    assert manifest(sandbox_batch_run)["candidate_exhaustive_run"] is False


def test_no_paper_forward_action(sandbox_batch_run: dict[str, Any]) -> None:
    loaded = manifest(sandbox_batch_run)
    assert loaded["paper_forward_review"] is False
    assert loaded["paper_forward_activation"] is False


def test_no_provider_download(sandbox_batch_run: dict[str, Any]) -> None:
    assert manifest(sandbox_batch_run)["provider_download"] is False


def test_no_intraday_data_used(sandbox_batch_run: dict[str, Any]) -> None:
    assert manifest(sandbox_batch_run)["intraday_data_used"] is False


def test_no_indicator_library_dependency_added(sandbox_batch_run: dict[str, Any]) -> None:
    assert manifest(sandbox_batch_run)["indicator_library_dependency_added"] is False


def test_no_broker_live_action(sandbox_batch_run: dict[str, Any]) -> None:
    loaded = manifest(sandbox_batch_run)
    assert loaded["broker_orders_submitted"] is False
    assert loaded["broker_orders_cancelled"] is False
    assert loaded["live_orders"] is False


def test_no_real_money_recommendation(sandbox_batch_run: dict[str, Any]) -> None:
    assert manifest(sandbox_batch_run)["real_money_recommendation"] is False


def test_active_strategy_state_preserved(sandbox_batch_run: dict[str, Any]) -> None:
    assert manifest(sandbox_batch_run)["active_strategy_state_changed"] is False
    assert sandbox_batch_run["strategies_before"] == sandbox_batch_run["strategies_after"]


def test_rejected_strategy_state_preserved(sandbox_batch_run: dict[str, Any]) -> None:
    assert manifest(sandbox_batch_run)["rejected_strategy_state_changed"] is False
    assert sandbox_batch_run["strategies_before"] == sandbox_batch_run["strategies_after"]


def test_exact_rejected_variants_not_reopened(sandbox_batch_run: dict[str, Any]) -> None:
    assert manifest(sandbox_batch_run)["exact_rejected_variants_reopened"] is False


def test_intraday_remains_paused(sandbox_batch_run: dict[str, Any]) -> None:
    assert manifest(sandbox_batch_run)["intraday_research_remains_paused"] is True


def test_variant_count_planned_bounded(sandbox_batch_run: dict[str, Any]) -> None:
    assert manifest(sandbox_batch_run)["variant_count_planned"] <= 200


def test_variant_count_evaluated_bounded(sandbox_batch_run: dict[str, Any]) -> None:
    assert manifest(sandbox_batch_run)["variant_count_evaluated"] <= 200


def test_every_result_has_allowed_sandbox_status(sandbox_batch_run: dict[str, Any]) -> None:
    assert {row["status"] for row in result_rows(sandbox_batch_run)} <= set(ALLOWED_SANDBOX_STATUSES)


def test_forbidden_statuses_absent(sandbox_batch_run: dict[str, Any]) -> None:
    assert not ({row["status"] for row in result_rows(sandbox_batch_run)} & set(FORBIDDEN_STATUSES))


def test_no_result_promotable(sandbox_batch_run: dict[str, Any]) -> None:
    assert {row["promotable"] for row in result_rows(sandbox_batch_run)} == {"false"}


def test_no_result_paper_candidate_allowed(sandbox_batch_run: dict[str, Any]) -> None:
    assert {row["paper_candidate_allowed"] for row in result_rows(sandbox_batch_run)} == {"false"}


def test_family_summary_exists(sandbox_batch_run: dict[str, Any]) -> None:
    assert (output(sandbox_batch_run) / "sandbox_family_summary.csv").exists()
    assert (output(sandbox_batch_run) / "sandbox_family_summary.md").exists()


def test_benchmark_comparison_summary_exists(sandbox_batch_run: dict[str, Any]) -> None:
    assert (output(sandbox_batch_run) / "sandbox_benchmark_comparison_summary.csv").exists()


def test_risk_summary_exists(sandbox_batch_run: dict[str, Any]) -> None:
    assert (output(sandbox_batch_run) / "sandbox_risk_summary.csv").exists()


def test_diversification_summary_exists(sandbox_batch_run: dict[str, Any]) -> None:
    assert (output(sandbox_batch_run) / "sandbox_diversification_summary.csv").exists()


def test_overfitting_risk_summary_exists(sandbox_batch_run: dict[str, Any]) -> None:
    assert (output(sandbox_batch_run) / "sandbox_overfitting_risk_summary.md").exists()


def test_do_not_promote_file_exists(sandbox_batch_run: dict[str, Any]) -> None:
    text = (output(sandbox_batch_run) / "sandbox_do_not_promote.md").read_text(encoding="utf-8")
    assert "non_promotable_exploration" in text


def test_next_action_is_valid(sandbox_batch_run: dict[str, Any]) -> None:
    assert manifest(sandbox_batch_run)["next_action"] in VALID_BATCH_NEXT_ACTIONS


def test_manifest_flags_match_strict_scope(sandbox_batch_run: dict[str, Any]) -> None:
    loaded = manifest(sandbox_batch_run)
    for key, expected in MANIFEST_FLAGS.items():
        assert loaded[key] == expected
    assert consistency(sandbox_batch_run)["consistency_passed"] is True
